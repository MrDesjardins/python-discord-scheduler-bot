"""Unit tests for stopping browser work while tracker.gg blocks requests"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from deps.browser import download_full_matches
from deps.browser_context_manager import BrowserContextManager, is_browser_busy
from deps.browser_exceptions import (
    BrowserTimeoutException,
    CloudflareChallengeNotClearedException,
    TrackerBlockedException,
)
from deps.data_access import _download_current_season_ranks_sync
from deps.models import UserQueueForStats
from tests.mock_model import mock_user1, mock_user2, mock_user3


def test_browser_is_not_launched_while_blocked():
    manager = BrowserContextManager()
    manager._lock = MagicMock()
    with (
        patch("deps.browser_context_manager.tracker_block_remaining_seconds", return_value=600.0),
        pytest.raises(TrackerBlockedException),
    ):
        manager.__enter__()
    manager._lock.acquire.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [TrackerBlockedException(3600), CloudflareChallengeNotClearedException("challenge was not cleared")],
)
def test_download_full_matches_stops_the_batch_when_tracker_is_unavailable(error):
    """Users after the failure are not requested and are left out so they stay queued"""
    first, second, third = [
        UserQueueForStats(user, 100, datetime.now(timezone.utc)) for user in (mock_user1, mock_user2, mock_user3)
    ]
    with patch("deps.browser.BrowserContextManager") as mock_cm:
        context = mock_cm.return_value.__enter__.return_value
        context.download_full_matches.side_effect = [[], error]
        mock_cm.return_value.__exit__.return_value = None
        result = download_full_matches([first, second, third])

    assert [entry.user_request_stats for entry in result] == [first]
    assert context.download_full_matches.call_count == 2


def test_download_full_matches_continues_after_an_ordinary_timeout():
    """A timeout that is not a challenge concerns one user only"""
    first, second = [UserQueueForStats(user, 100, datetime.now(timezone.utc)) for user in (mock_user1, mock_user2)]
    with patch("deps.browser.BrowserContextManager") as mock_cm:
        context = mock_cm.return_value.__enter__.return_value
        context.download_full_matches.side_effect = [BrowserTimeoutException("slow"), []]
        mock_cm.return_value.__exit__.return_value = None
        result = download_full_matches([first, second])

    assert [entry.user_request_stats for entry in result] == [second]


def test_rank_prefetch_stops_when_a_challenge_is_not_cleared():
    with patch("deps.data_access.BrowserContextManager") as mock_cm:
        context = mock_cm.return_value.__enter__.return_value
        context.download_current_season_rank.side_effect = [
            ("Gold", 1),
            CloudflareChallengeNotClearedException("challenge was not cleared"),
        ]
        mock_cm.return_value.__exit__.return_value = None
        result = _download_current_season_ranks_sync(["a", "b", "c"])

    assert result == {"a": ("Gold", 1)}
    assert context.download_current_season_rank.call_count == 2


def test_browser_is_busy_only_while_a_session_holds_the_lock():
    manager = BrowserContextManager()
    manager._lock = MagicMock()
    manager._lock_acquired = True
    manager._set_browser_lock_held(True)
    assert is_browser_busy()

    manager._cleanup()

    assert not is_browser_busy()
    manager._lock.release.assert_called_once()
