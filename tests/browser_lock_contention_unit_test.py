"""Unit tests for browser lock contention handling"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from filelock import Timeout as FileLockTimeout

from deps.browser import download_full_matches
from deps.browser_config import BrowserConfig
from deps.browser_context_manager import BrowserContextManager
from deps.browser_exceptions import BrowserLockContentionException
from deps.models import UserQueueForStats
from tests.mock_model import mock_user1


def test_lock_timeout_raises_contention_without_circuit_breaker_failure():
    """A file lock timeout is contention: no circuit breaker failure and no retry"""
    config = BrowserConfig(circuit_breaker_enabled=True)
    manager = BrowserContextManager(config=config)

    mock_lock = MagicMock()
    mock_lock.acquire.side_effect = FileLockTimeout("/tmp/chromium.lock")
    manager._lock = mock_lock

    mock_breaker = MagicMock()
    mock_breaker.allow_request.return_value = True

    with patch("deps.browser_context_manager._CIRCUIT_BREAKER", mock_breaker):
        with pytest.raises(BrowserLockContentionException):
            manager.__enter__()

    mock_breaker.record_failure.assert_not_called()
    mock_breaker.record_success.assert_not_called()
    # Contention must not retry in place: the holder can keep the lock for minutes
    mock_lock.acquire.assert_called_once()


def test_download_full_matches_returns_empty_on_lock_contention():
    """Lock contention aborts the batch quietly so the users stay queued for the next cycle"""
    user_queue = UserQueueForStats(mock_user1, 100, datetime.now(timezone.utc))
    with patch("deps.browser.BrowserContextManager") as mock_cm:
        mock_cm.return_value.__enter__.side_effect = BrowserLockContentionException("busy")
        result = download_full_matches([user_queue])
    assert result == []
