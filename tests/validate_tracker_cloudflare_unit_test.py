"""Unit tests for the maintenance command used to solve a tracker.gg challenge by hand"""

from unittest.mock import MagicMock

import pytest

from deployment.validate_tracker_cloudflare import clearance_works
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
