"""Unit tests for the automatic Cloudflare challenge solver and profile-lock hardening."""

import os
from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from deps import tracker_pacing
from deps.browser_config import BrowserConfig
from deps.browser_context_manager import BrowserContextManager
from deps.browser_exceptions import BrowserException, BrowserTimeoutException, TrackerBlockedException


def _manager(**config_kwargs) -> BrowserContextManager:
    config = BrowserConfig(circuit_breaker_enabled=False, **config_kwargs)
    return BrowserContextManager(config=config)


def test_wait_for_json_returns_when_no_challenge_and_pre_present():
    manager = _manager()
    driver = MagicMock()
    driver.title = "api.tracker.gg"
    driver.page_source = "<pre>{}</pre>"
    driver.find_elements.return_value = [MagicMock()]
    manager.driver = driver

    manager._wait_for_json("test")  # should not raise


_CF_DOM_WITH_IFRAME = {
    "root": {
        "nodeName": "#document",
        "children": [
            {
                "nodeName": "IFRAME",
                "backendNodeId": 42,
                "attributes": ["src", "https://challenges.cloudflare.com/turnstile/abc"],
            }
        ],
    }
}
_CF_BOX_MODEL = {"model": {"content": [512.0, 304.0, 812.0, 304.0, 812.0, 369.0, 512.0, 369.0]}}


def _cdp_router(dom=_CF_DOM_WITH_IFRAME, box=_CF_BOX_MODEL, on_click=None):
    def route(command, _params=None):
        if command == "DOM.getDocument":
            return dom
        if command == "DOM.getBoxModel":
            return box
        if command == "Input.dispatchMouseEvent" and on_click is not None:
            on_click()
        return {}

    return route


def test_attempt_cloudflare_solve_clicks_widget_then_succeeds():
    manager = _manager(cloudflare_auto_solve_seconds=10)
    driver = MagicMock()
    manager.driver = driver
    states = {"solved": False}

    driver.find_elements.side_effect = lambda _by, _tag: [MagicMock()] if states["solved"] else []
    driver.page_source = "Just a moment... verify you are human"
    driver.title = "Just a moment..."
    driver.execute_cdp_cmd.side_effect = _cdp_router(on_click=lambda: states.__setitem__("solved", True))

    assert manager._attempt_cloudflare_solve("test") is True
    dispatched = [c.args[0] for c in driver.execute_cdp_cmd.call_args_list]
    assert "DOM.getDocument" in dispatched and "Input.dispatchMouseEvent" in dispatched


def test_attempt_cloudflare_solve_times_out_returns_false():
    manager = _manager(cloudflare_auto_solve_seconds=1)
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = []
    driver.page_source = "verify you are human"
    driver.title = "Just a moment..."
    driver.execute_cdp_cmd.side_effect = _cdp_router(dom={"root": {"nodeName": "#document", "children": []}})

    assert manager._attempt_cloudflare_solve("test") is False


def test_wait_for_json_requests_human_dm_only_after_first_two_fallbacks_fail():
    manager = _manager(cloudflare_auto_solve_seconds=1, cloudflare_manual_wait_seconds=0)
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = []
    driver.page_source = "cloudflare - verify you are human"
    driver.title = "Just a moment..."
    driver.execute_cdp_cmd.side_effect = _cdp_router(dom={"root": {"nodeName": "#document", "children": []}})

    with (
        patch("deps.browser_context_manager.request_tracker_attention") as mock_attention,
        pytest.raises(BrowserTimeoutException),
    ):
        manager._wait_for_json("test")
    mock_attention.assert_called_once_with()


def test_cookie_replay_is_tried_before_cloudflare_solver_and_human_dm():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = []
    driver.page_source = "verify you are human"
    driver.title = "Just a moment..."

    with (
        patch.object(manager, "_http_fetch_json", return_value={"data": "cached cookie"}) as mock_cookie,
        patch.object(manager, "_attempt_cloudflare_solve") as mock_solver,
        patch.object(manager, "_wait_for_manual_cloudflare_solve") as mock_manual,
        patch("deps.browser_context_manager.request_tracker_attention") as mock_attention,
    ):
        assert manager._wait_for_json("test", "https://api.tracker.gg/x") == {"data": "cached cookie"}

    mock_cookie.assert_called_once_with("https://api.tracker.gg/x", "test")
    mock_solver.assert_not_called()
    mock_manual.assert_not_called()
    mock_attention.assert_not_called()


def test_cloudflare_solver_runs_after_cookie_replay_fails_and_precedes_human_dm():
    manager = _manager(cloudflare_manual_wait_seconds=0)
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = []
    driver.page_source = "verify you are human"
    driver.title = "Just a moment..."

    with (
        patch.object(manager, "_http_fetch_json", return_value=None) as mock_cookie,
        patch.object(manager, "_attempt_cloudflare_solve", return_value=True) as mock_solver,
        patch.object(manager, "_wait_for_manual_cloudflare_solve") as mock_manual,
        patch("deps.browser_context_manager.request_tracker_attention") as mock_attention,
    ):
        assert manager._wait_for_json("test", "https://api.tracker.gg/x") is None

    mock_cookie.assert_called_once_with("https://api.tracker.gg/x", "test")
    mock_solver.assert_called_once_with("test", "https://api.tracker.gg/x")
    mock_manual.assert_not_called()
    mock_attention.assert_not_called()


def test_visible_browser_manual_wait_precedes_human_dm():
    manager = _manager(cloudflare_manual_wait_seconds=10)
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = []
    driver.page_source = "verify you are human"
    driver.title = "Just a moment..."

    with (
        patch.object(manager, "_http_fetch_json", return_value=None),
        patch.object(manager, "_attempt_cloudflare_solve", return_value=False),
        patch.object(manager, "_wait_for_manual_cloudflare_solve", return_value=True) as mock_manual,
        patch("deps.browser_context_manager.request_tracker_attention") as mock_attention,
    ):
        assert manager._wait_for_json("test", "https://api.tracker.gg/x") is None

    mock_manual.assert_called_once_with("test")
    mock_attention.assert_not_called()


def test_clear_cloudflare_cookies_keeps_unrelated_cookies():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    driver.get_cookies.return_value = [
        {"name": "cf_clearance", "value": "x"},
        {"name": "theme", "value": "dark"},
        {"name": "__cf_bm", "value": "y"},
        {"name": "_cfuvid", "value": "z"},
    ]

    manager._clear_cloudflare_cookies()

    assert [call.args[0] for call in driver.delete_cookie.call_args_list] == [
        "cf_clearance",
        "__cf_bm",
        "_cfuvid",
    ]


def test_http_fetch_json_sends_browser_cookies_and_returns_data():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    driver.execute_script.return_value = "TestUA"
    driver.get_cookies.return_value = [{"name": "cf_clearance", "value": "token"}]
    response = MagicMock(status_code=200)
    response.json.return_value = {"data": 1}

    with (
        patch("deps.browser_context_manager.wait_before_request") as mock_pacing,
        patch("deps.browser_context_manager.requests.get", return_value=response) as mock_get,
    ):
        result = manager._http_fetch_json("https://api.tracker.gg/x", "test")

    assert result == {"data": 1}
    assert mock_get.call_args.kwargs["cookies"] == {"cf_clearance": "token"}
    assert mock_get.call_args.kwargs["headers"]["User-Agent"] == "TestUA"
    mock_pacing.assert_called_once_with("test")


def _http_fetch_with_response(status_code, body):
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    driver.execute_script.return_value = "TestUA"
    driver.get_cookies.return_value = [{"name": "cf_clearance", "value": "token"}]
    response = MagicMock(status_code=status_code)
    response.json.return_value = body

    with (
        patch("deps.browser_context_manager.wait_before_request"),
        patch("deps.browser_context_manager.requests.get", return_value=response),
    ):
        return manager._http_fetch_json("https://api.tracker.gg/x", "test")


def test_http_fetch_json_returns_an_error_body_so_a_warden_block_starts_the_cooldown():
    warden = {"errors": [{"code": "Warden::Challenge"}]}

    assert _http_fetch_with_response(403, warden) == warden


def test_http_fetch_json_ignores_a_refusal_without_an_error_body():
    assert _http_fetch_with_response(403, {"message": "denied"}) is None


def test_http_fetch_json_skipped_without_clearance_cookie():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    driver.get_cookies.return_value = [{"name": "theme", "value": "dark"}]

    with patch("deps.browser_context_manager.requests.get") as mock_get:
        assert manager._http_fetch_json("https://api.tracker.gg/x", "test") is None

    mock_get.assert_not_called()


def test_challenge_after_initial_page_wait_uses_cookie_replay_before_auto_solve():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = []

    with (
        patch.object(manager, "_is_cloudflare_challenge", side_effect=[False, True]),
        patch("deps.browser_context_manager.WebDriverWait") as mock_wait,
        patch.object(manager, "_http_fetch_json", return_value={"data": "cookie"}) as mock_cookie,
        patch.object(manager, "_attempt_cloudflare_solve") as mock_solver,
        patch("deps.browser_context_manager.request_tracker_attention") as mock_attention,
    ):
        mock_wait.return_value.until.side_effect = TimeoutException
        assert manager._wait_for_json("test", "https://api.tracker.gg/x") == {"data": "cookie"}

    mock_wait.return_value.until.assert_called_once()
    mock_cookie.assert_called_once_with("https://api.tracker.gg/x", "test")
    mock_solver.assert_not_called()
    mock_attention.assert_not_called()


def test_page_already_holding_json_skips_replay_when_challenge_detection_misfires():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = [MagicMock()]
    driver.title = ""
    driver.page_source = '<pre>{"note": "cloudflare"}</pre>'

    with patch.object(manager, "_http_fetch_json") as mock_cookie:
        assert manager._wait_for_json("test", "https://api.tracker.gg/x") is None

    mock_cookie.assert_not_called()


def test_reload_failure_does_not_abort_the_batch():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    driver.get.side_effect = WebDriverException("tab crashed")

    manager._reload_challenge_page("https://api.tracker.gg/x")  # should not raise


def _run_solver_on_a_fake_clock(manager, widget_clicked):
    """Run a solver that never clears; returns the clock time of each reload and the mocked pacing."""
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = []
    driver.page_source = "verify you are human"
    driver.title = "Just a moment..."
    clock = {"now": 0.0}
    reload_times = []

    def fake_sleep(seconds):
        clock["now"] += seconds

    with (
        patch.object(manager, "_click_cloudflare_widget", return_value=widget_clicked),
        patch.object(manager, "_clear_cloudflare_cookies"),
        patch.object(manager, "_reload_challenge_page", side_effect=lambda _url: reload_times.append(clock["now"])),
        patch("deps.browser_context_manager.wait_before_request") as mock_pacing,
        patch("deps.browser_context_manager.time.sleep", side_effect=fake_sleep),
        patch("deps.browser_context_manager.time.time", side_effect=lambda: clock["now"]),
    ):
        assert manager._attempt_cloudflare_solve("test", "https://api.tracker.gg/x") is False
    return reload_times, mock_pacing


def test_solver_reloads_with_fresh_cookies_only_after_the_widget_had_its_time():
    manager = _manager(cloudflare_auto_solve_seconds=45, cloudflare_max_reloads=1, cloudflare_reload_after_seconds=25)

    reload_times, mock_pacing = _run_solver_on_a_fake_clock(manager, widget_clicked=True)

    assert len(reload_times) == 1
    assert reload_times[0] >= 25
    mock_pacing.assert_called_once_with("test")


def test_solver_keeps_clicking_without_a_reload_when_the_budget_is_shorter_than_the_patience():
    manager = _manager(cloudflare_auto_solve_seconds=20, cloudflare_max_reloads=1, cloudflare_reload_after_seconds=25)

    reload_times, _ = _run_solver_on_a_fake_clock(manager, widget_clicked=True)

    assert reload_times == []


def test_solver_does_not_interrupt_a_challenge_that_shows_no_widget():
    """Without a widget the non-interactive check may still be running."""
    manager = _manager(cloudflare_auto_solve_seconds=45, cloudflare_max_reloads=1, cloudflare_reload_after_seconds=25)

    reload_times, _ = _run_solver_on_a_fake_clock(manager, widget_clicked=False)

    assert reload_times == []


def test_probe_reports_an_unsolved_challenge_without_queuing_the_owner_dm():
    manager = _manager(cloudflare_auto_solve_seconds=0)
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = []
    driver.title = "Just a moment..."
    driver.page_source = "verify you are human"

    with (
        patch("deps.browser_context_manager.wait_before_request"),
        patch("deps.browser_context_manager.request_tracker_attention") as mock_attention,
    ):
        assert manager.probe_api("someone")["state"] == "challenge"

    mock_attention.assert_not_called()


def test_probe_still_queues_the_owner_dm_on_a_warden_block(monkeypatch):
    """The cooldown stops the jobs that would otherwise alert the owner."""
    monkeypatch.setattr(tracker_pacing, "_blocked_until", 0.0)
    monkeypatch.setattr(tracker_pacing, "_consecutive_blocks", 0)
    manager = _manager()
    manager.driver = MagicMock()

    with (
        patch("deps.browser_context_manager.wait_before_request"),
        patch.object(manager, "_wait_for_json", return_value={"errors": [{"code": "Warden::Challenge"}]}),
        patch("deps.tracker_pacing.request_tracker_attention") as mock_attention,
        pytest.raises(TrackerBlockedException),
    ):
        manager.probe_api("someone")

    mock_attention.assert_called_once_with()


def test_probe_api_reports_challenge_when_auto_solve_cannot_clear():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver

    with (
        patch("deps.browser_context_manager.wait_before_request"),
        patch.object(manager, "_wait_for_json", return_value=None),
        patch.object(manager, "_extract_json_from_page", side_effect=BrowserException("no json")),
        patch.object(manager, "_is_cloudflare_challenge", return_value=True),
    ):
        assert manager.probe_api("someone")["state"] == "challenge"


def test_probe_api_reports_ok_when_json_is_present():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver

    with (
        patch("deps.browser_context_manager.wait_before_request"),
        patch.object(manager, "_wait_for_json", return_value=None),
        patch.object(manager, "_extract_json_from_page", return_value={"data": {}}),
    ):
        assert manager.probe_api("someone") == {"state": "ok", "detail": "JSON received"}


def test_cdp_trusted_click_dispatches_move_press_release():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver

    manager._cdp_trusted_click(10.0, 20.0)

    event_types = [call.args[1]["type"] for call in driver.execute_cdp_cmd.call_args_list]
    assert event_types == ["mouseMoved", "mousePressed", "mouseReleased"]


def test_find_cloudflare_widget_rect_pierces_shadow_dom():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    nested = {
        "root": {
            "nodeName": "#document",
            "children": [
                {
                    "nodeName": "DIV",
                    "shadowRoots": [
                        {
                            "nodeName": "#document-fragment",
                            "children": [
                                {
                                    "nodeName": "IFRAME",
                                    "backendNodeId": 7,
                                    "attributes": ["src", "https://challenges.cloudflare.com/x"],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    }
    driver.execute_cdp_cmd.side_effect = _cdp_router(dom=nested)
    rect = manager._find_cloudflare_widget_rect()
    assert rect == {"x": 512.0, "y": 304.0, "width": 300.0, "height": 65.0}


def test_find_cloudflare_widget_rect_none_when_absent():
    manager = _manager()
    driver = MagicMock()
    manager.driver = driver
    driver.execute_cdp_cmd.side_effect = _cdp_router(dom={"root": {"nodeName": "#document", "children": []}})
    assert manager._find_cloudflare_widget_rect() is None


def test_clear_stale_profile_locks_removes_singleton_files(tmp_path):
    manager = _manager()
    manager._profile_dir = str(tmp_path)
    lock = tmp_path / "SingletonLock"
    lock.symlink_to("dead-host-123")
    (tmp_path / "SingletonCookie").write_text("x")

    manager._clear_stale_profile_locks()

    assert not lock.exists()
    assert not (tmp_path / "SingletonCookie").exists()


def test_wipe_persistent_profile_only_when_configured(tmp_path, monkeypatch):
    manager = _manager()
    manager._profile_dir = str(tmp_path)
    (tmp_path / "marker").write_text("x")

    monkeypatch.delenv("BROWSER_PROFILE_DIR", raising=False)
    manager._wipe_persistent_profile()
    assert (tmp_path / "marker").exists()  # temp profiles are left to the normal cleanup

    monkeypatch.setenv("BROWSER_PROFILE_DIR", str(tmp_path))
    manager._wipe_persistent_profile()
    assert not tmp_path.exists()


@pytest.mark.parametrize("environment,wipes", [("prod", True), ("dev", False)])
def test_chrome_startup_failure_wipes_the_shared_profile_only_on_the_bot(environment, wipes):
    """A manual session without a display fails the same way as a corrupt profile."""
    manager = _manager(max_retries=1)
    manager.environment = environment
    manager._lock = MagicMock()

    with (
        patch("deps.browser_context_manager.tracker_block_remaining_seconds", return_value=0.0),
        patch.object(manager, "_config_browser", side_effect=RuntimeError("chrome not reachable")),
        patch.object(manager, "_cleanup"),
        patch.object(manager, "_wipe_persistent_profile") as mock_wipe,
        pytest.raises(BrowserException),
    ):
        manager.__enter__()

    assert mock_wipe.called is wipes


@pytest.mark.parametrize(
    "message,expected",
    [
        ("session not created: cannot connect to chrome at 127.0.0.1:1", True),
        ("chrome not reachable", True),
        ("DevToolsActivePort file doesn't exist", True),
        ("tab crashed", True),
        ("Ubisoft username not found", False),
        ("timeout waiting for json data", False),
    ],
)
def test_looks_like_corrupt_profile_error(message, expected):
    assert BrowserContextManager._looks_like_corrupt_profile_error(message) is expected
