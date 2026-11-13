"""Unit tests for the maintenance command used to solve a tracker.gg challenge by hand"""

from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import InvalidSessionIdException

from deployment.validate_tracker_cloudflare import clearance_works, main
from deps.browser_exceptions import BrowserTimeoutException, TrackerBlockedException


def test_answered_request_means_it_worked():
    context = MagicMock(default_profile="profile")

    assert clearance_works(context) is True
    context.download_current_season_rank.assert_called_once_with("profile")


@pytest.mark.parametrize(
    "error",
    [TrackerBlockedException(3600), BrowserTimeoutException("challenge was not cleared")],
)
def test_refused_request_means_it_did_not_work(error):
    context = MagicMock()
    context.download_current_season_rank.side_effect = error

    assert clearance_works(context) is False


def test_missing_display_stops_before_chrome_touches_the_shared_profile(monkeypatch):
    monkeypatch.setenv("BROWSER_PROFILE_DIR", "/tmp/profile")
    monkeypatch.delenv("DISPLAY", raising=False)

    with (
        patch("deployment.validate_tracker_cloudflare.load_dotenv"),
        patch("deployment.validate_tracker_cloudflare.BrowserContextManager") as manager_class,
        pytest.raises(SystemExit, match="WSL"),
    ):
        main()

    manager_class.assert_not_called()


def test_closed_window_says_so_instead_of_crashing():
    context = MagicMock()
    context.download_current_season_rank.side_effect = InvalidSessionIdException("browser has closed the connection")

    with pytest.raises(SystemExit, match="closed"):
        clearance_works(context)
