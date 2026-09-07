"""Unit tests for the automatic Cloudflare challenge solver and profile-lock hardening."""

import os
from unittest.mock import MagicMock

import pytest

from deps.browser_config import BrowserConfig
from deps.browser_context_manager import BrowserContextManager
from deps.browser_exceptions import BrowserTimeoutException


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


def test_wait_for_json_raises_when_challenge_never_clears():
    manager = _manager(cloudflare_auto_solve_seconds=1, cloudflare_manual_wait_seconds=0)
    driver = MagicMock()
    manager.driver = driver
    driver.find_elements.return_value = []
    driver.page_source = "cloudflare - verify you are human"
    driver.title = "Just a moment..."
    driver.execute_cdp_cmd.side_effect = _cdp_router(dom={"root": {"nodeName": "#document", "children": []}})

    with pytest.raises(BrowserTimeoutException):
        manager._wait_for_json("test")


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
