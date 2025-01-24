"""
Integration test for the bet functions
"""

from unittest.mock import patch
from datetime import datetime, timezone
import pytest
from deps.bet.bet_data_access import delete_all_bet_tables, data_access_fetch_bet_games_by_tournament_id
from deps.bet.bet_functions import (
    system_generate_game_odd,
)
from deps.tournament_data_class import TournamentGame
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from deps.bet import bet_functions

fake_date = datetime(2024, 9, 20, 13, 20, 0, 6318)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    database_manager.set_database_name(DATABASE_NAME_TEST)
    delete_all_bet_tables()

    # Yield control to the test functions
    yield

    # Teardown
    database_manager.set_database_name(DATABASE_NAME)


@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
async def test_generating_odd_for_tournament_games_for_only_game_without_ones(mock_fetch_tournament) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = list_tournament_games
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_fetch_tournament.assert_called_once_with(1)
    bet_games = data_access_fetch_bet_games_by_tournament_id(1)
    assert len(bet_games) == 4


@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
async def test_generating_odd_for_tournament_games_once_per_game(mock_fetch_tournament) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = list_tournament_games
    # Act
    await system_generate_game_odd(1)
    # Assert
    bet_games = data_access_fetch_bet_games_by_tournament_id(1)
    assert len(bet_games) == 4
