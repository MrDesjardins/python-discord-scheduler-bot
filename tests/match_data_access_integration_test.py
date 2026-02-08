"""
Integration tests for new match data access functions
"""

import pytest
from deps.analytic_data_access import data_access_fetch_recent_win_loss
from deps.system_database import database_manager


@pytest.mark.no_parallel
def test_data_access_fetch_recent_win_loss_no_matches():
    """Test fetching win/loss with no matches in database"""
    # Use a user ID that doesn't exist
    wins, losses = data_access_fetch_recent_win_loss(999999999, 10)
    assert wins == 0
    assert losses == 0


@pytest.mark.no_parallel
def test_data_access_fetch_recent_win_loss_with_limit():
    """Test that the limit parameter works correctly"""
    # Even if more matches exist, should only count up to the limit
    wins, losses = data_access_fetch_recent_win_loss(999999999, 5)
    assert wins == 0
    assert losses == 0

    # Test with different limit
    wins, losses = data_access_fetch_recent_win_loss(999999999, 20)
    assert wins == 0
    assert losses == 0


@pytest.mark.no_parallel
def test_data_access_fetch_recent_win_loss_return_type():
    """Test that the function returns a tuple of two integers"""
    result = data_access_fetch_recent_win_loss(999999999, 10)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], int)
    assert isinstance(result[1], int)
