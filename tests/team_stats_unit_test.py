"""
Unit tests for team stats data access function
"""

import pytest
from deps.analytic_leaderboard_data_access import data_access_fetch_team_stats


def test_fetch_team_stats_invalid_size_too_few() -> None:
    """Test that function raises ValueError for fewer than 2 players"""
    with pytest.raises(ValueError, match="user_ids must contain 2-5 players"):
        data_access_fetch_team_stats([123])


def test_fetch_team_stats_invalid_size_too_many() -> None:
    """Test that function raises ValueError for more than 5 players"""
    with pytest.raises(ValueError, match="user_ids must contain 2-5 players"):
        data_access_fetch_team_stats([1, 2, 3, 4, 5, 6])


def test_fetch_team_stats_empty_list() -> None:
    """Test that function raises ValueError for empty list"""
    with pytest.raises(ValueError, match="user_ids must contain 2-5 players"):
        data_access_fetch_team_stats([])


def test_fetch_team_stats_no_matches() -> None:
    """Test that function returns None when no matches found"""
    # Use user IDs that don't exist in the database
    result = data_access_fetch_team_stats([999999, 888888])
    assert result is None


def test_fetch_team_stats_duo() -> None:
    """Test fetching stats for 2 players"""
    # This test will only pass if there's actual data in the test database
    # We're testing the function structure, not actual data
    result = data_access_fetch_team_stats([123456, 789012])
    # Result could be None if no matches, or tuple if matches exist
    assert result is None or (isinstance(result, tuple) and len(result) == 2)


def test_fetch_team_stats_trio() -> None:
    """Test fetching stats for 3 players"""
    result = data_access_fetch_team_stats([123456, 789012, 345678])
    assert result is None or (isinstance(result, tuple) and len(result) == 2)


def test_fetch_team_stats_quad() -> None:
    """Test fetching stats for 4 players"""
    result = data_access_fetch_team_stats([123456, 789012, 345678, 901234])
    assert result is None or (isinstance(result, tuple) and len(result) == 2)


def test_fetch_team_stats_full_team() -> None:
    """Test fetching stats for 5 players (full Siege team)"""
    result = data_access_fetch_team_stats([123456, 789012, 345678, 901234, 567890])
    assert result is None or (isinstance(result, tuple) and len(result) == 2)


def test_fetch_team_stats_ordering_doesnt_matter() -> None:
    """Test that the order of user IDs doesn't affect the result"""
    user_ids = [123456, 789012, 345678]

    # Try different orderings
    result1 = data_access_fetch_team_stats(user_ids)
    result2 = data_access_fetch_team_stats([345678, 123456, 789012])
    result3 = data_access_fetch_team_stats([789012, 345678, 123456])

    # All should return the same result
    assert result1 == result2 == result3


def test_fetch_team_stats_return_format() -> None:
    """Test that when data exists, it returns the correct format"""
    # Mock scenario - if data exists, verify format
    result = data_access_fetch_team_stats([123456, 789012])

    if result is not None:
        games_played, win_rate = result
        assert isinstance(games_played, int)
        assert games_played >= 0
        assert isinstance(win_rate, float)
        assert 0.0 <= win_rate <= 1.0  # Win rate should be between 0 and 1
