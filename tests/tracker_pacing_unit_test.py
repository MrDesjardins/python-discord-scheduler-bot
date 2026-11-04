"""Unit tests for the tracker.gg request pacing and Warden block cooldown"""

from unittest.mock import patch

import pytest

from deps import tracker_pacing
from deps.browser_exceptions import TrackerBlockedException

WARDEN_RESPONSE = {
    "errors": [
        {
            "code": "Warden::Challenge",
            "message": "You are making too many requests and must solve a captcha to continue.",
            "data": {},
        }
    ]
}


@pytest.fixture(autouse=True)
def reset_pacing_state(monkeypatch):
    """Each test starts with no previous request and no block"""
    monkeypatch.setattr(tracker_pacing, "_last_request_at", float("-inf"))
    monkeypatch.setattr(tracker_pacing, "_blocked_until", 0.0)
    monkeypatch.setattr(tracker_pacing, "_consecutive_blocks", 0)


def test_first_request_does_not_wait():
    with patch("deps.tracker_pacing.time.sleep") as mock_sleep:
        tracker_pacing.wait_before_request("test")
    mock_sleep.assert_not_called()


def test_back_to_back_requests_wait_a_random_gap():
    with (
        patch("deps.tracker_pacing.time.monotonic", return_value=1000.0),
        patch("deps.tracker_pacing.random.uniform", return_value=30.0) as mock_uniform,
        patch("deps.tracker_pacing.time.sleep") as mock_sleep,
    ):
        tracker_pacing.wait_before_request("test")
        tracker_pacing.wait_before_request("test")

    mock_uniform.assert_called_with(tracker_pacing.MIN_REQUEST_GAP_SECONDS, tracker_pacing.MAX_REQUEST_GAP_SECONDS)
    mock_sleep.assert_called_once_with(30.0)


def test_warden_response_raises_and_blocks_further_requests():
    with pytest.raises(TrackerBlockedException):
        tracker_pacing.check_tracker_response(WARDEN_RESPONSE, "test")

    assert tracker_pacing.tracker_block_remaining_seconds() > 0
    with patch("deps.tracker_pacing.time.sleep") as mock_sleep, pytest.raises(TrackerBlockedException):
        tracker_pacing.wait_before_request("test")
    mock_sleep.assert_not_called()


def test_consecutive_blocks_escalate_the_cooldown_up_to_the_cap():
    cooldowns = []
    for _ in range(len(tracker_pacing.BLOCK_COOLDOWNS_SECONDS) + 1):
        with pytest.raises(TrackerBlockedException) as exc_info:
            tracker_pacing.check_tracker_response(WARDEN_RESPONSE, "test")
        cooldowns.append(exc_info.value.retry_in_seconds)

    assert cooldowns == [*tracker_pacing.BLOCK_COOLDOWNS_SECONDS, tracker_pacing.BLOCK_COOLDOWNS_SECONDS[-1]]


def test_valid_response_resets_the_escalation():
    with pytest.raises(TrackerBlockedException):
        tracker_pacing.check_tracker_response(WARDEN_RESPONSE, "test")

    tracker_pacing.check_tracker_response({"data": {"matches": []}}, "test")

    with pytest.raises(TrackerBlockedException) as exc_info:
        tracker_pacing.check_tracker_response(WARDEN_RESPONSE, "test")
    assert exc_info.value.retry_in_seconds == tracker_pacing.BLOCK_COOLDOWNS_SECONDS[0]


def test_other_tracker_errors_are_not_a_block():
    tracker_pacing.check_tracker_response({"errors": [{"code": "StandardApiV2::NoData"}]}, "test")
    assert tracker_pacing.tracker_block_remaining_seconds() == 0
