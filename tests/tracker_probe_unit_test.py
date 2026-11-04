"""Unit tests for the owner-facing tracker.gg probe"""

from unittest.mock import MagicMock, patch

from deps import tracker_probe
from deps.browser_exceptions import TrackerBlockedException


def test_probe_reports_cooldown_without_launching_browser():
    with (
        patch.object(tracker_probe, "tracker_block_remaining_seconds", return_value=120),
        patch.object(tracker_probe, "BrowserContextManager") as manager_class,
    ):
        result = tracker_probe.probe_tracker_api()

    assert result["state"] == "blocked"
    manager_class.assert_not_called()


def test_probe_reports_busy_without_launching_browser():
    with (
        patch.object(tracker_probe, "tracker_block_remaining_seconds", return_value=0),
        patch.object(tracker_probe, "is_browser_busy", return_value=True),
        patch.object(tracker_probe, "BrowserContextManager") as manager_class,
    ):
        result = tracker_probe.probe_tracker_api()

    assert result["state"] == "browser_busy"
    manager_class.assert_not_called()


def test_probe_returns_the_context_result():
    context = MagicMock()
    context.__enter__.return_value = context
    context.probe_api.return_value = {"state": "ok", "detail": "JSON received"}

    with (
        patch.object(tracker_probe, "tracker_block_remaining_seconds", return_value=0),
        patch.object(tracker_probe, "BrowserContextManager", return_value=context),
    ):
        assert tracker_probe.probe_tracker_api()["state"] == "ok"


def test_probe_maps_a_warden_block():
    context = MagicMock()
    context.__enter__.return_value = context
    context.probe_api.side_effect = TrackerBlockedException(60)

    with (
        patch.object(tracker_probe, "tracker_block_remaining_seconds", return_value=0),
        patch.object(tracker_probe, "BrowserContextManager", return_value=context),
    ):
        assert tracker_probe.probe_tracker_api()["state"] == "blocked"


def test_probe_detail_stays_short_enough_for_a_discord_message():
    context = MagicMock()
    context.__enter__.side_effect = RuntimeError("x" * 5000)

    with (
        patch.object(tracker_probe, "tracker_block_remaining_seconds", return_value=0),
        patch.object(tracker_probe, "BrowserContextManager", return_value=context),
    ):
        result = tracker_probe.probe_tracker_api()

    assert result["state"] == "browser_unavailable"
    assert len(result["detail"]) == tracker_probe.MAX_DETAIL_CHARACTERS
