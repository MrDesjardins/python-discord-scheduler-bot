"""
Integration test for the bet functions
"""

from typing import List
from unittest.mock import patch
from datetime import datetime, timezone
import pytest
from deps.data_access_data_class import UserInfo
from deps.bet.bet_data_access import data_access_fetch_bet_games_by_tournament_id
from deps.bet.bet_functions import system_generate_game_odd
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from deps.bet import bet_functions

fake_date = datetime(2024, 9, 20, 13, 20, 0, 6318)
tournament_1v1 = Tournament(1, 100, "Tournament 1", fake_date, fake_date, fake_date, 5, 16, "villa", False, False, 0, 1)
tournament_team = Tournament(
    1, 100, "Tournament 1", fake_date, fake_date, fake_date, 5, 16, "villa", False, False, 0, 2
)
dict_user_info = {
    1: UserInfo(1, "User1", "", "", "", ""),
    2: UserInfo(2, "User2", "", "", "", ""),
    3: UserInfo(3, "User3", "", "", "", ""),
    4: UserInfo(4, "User4", "", "", "", ""),
    5: UserInfo(5, "User5", "", "", "", ""),
    6: UserInfo(6, "User6", "", "", "", ""),
}


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()

    # Yield control to the test functions
    yield

    # Teardown
    database_manager.set_database_name(DATABASE_NAME)


@patch.object(bet_functions, bet_functions.define_odds_between_two_users.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
async def test_generating_odd_for_tournament_that_does_not_exist(
    mock_fetch_tournament_games, mock_fetch_tournament, mock_define_odds_between_two_users
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = None
    mock_fetch_tournament_games.return_value = list_tournament_games
    mock_define_odds_between_two_users.return_value = (1.5, 2.0)
    # Act
    with pytest.raises(ValueError, match="Tournament with id 10000 does not exist"):
        await system_generate_game_odd(10000)
    mock_define_odds_between_two_users.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.define_odds_between_two_teams.__name__)
@patch.object(bet_functions, bet_functions.define_odds_between_two_users.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
async def test_generating_odd_for_tournament_games_for_only_game_without_ones(
    mock_fetch_tournament_games,
    mock_fetch_tournament,
    mock_define_odds_between_two_users,
    mock_define_odds_between_two_teams,
    mock_fetch_user_info_by_user_id,
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = tournament_1v1
    mock_fetch_tournament_games.return_value = list_tournament_games
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: dict_user_info.get(user_id, None)
    mock_define_odds_between_two_users.return_value = (1.5, 2.0)
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_fetch_tournament.assert_called_once_with(1)
    bet_games = data_access_fetch_bet_games_by_tournament_id(1)
    assert len(bet_games) == 4
    mock_define_odds_between_two_users.assert_called()
    mock_define_odds_between_two_teams.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.define_odds_between_two_teams.__name__)
@patch.object(bet_functions, bet_functions.define_odds_between_two_users.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
async def test_generating_odd_for_tournament_games_once_per_game(
    mock_fetch_tournament_games,
    mock_fetch_tournament,
    mock_define_odds_between_two_users,
    mock_define_odds_between_two_teams,
    mock_fetch_user_info_by_user_id,
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = tournament_1v1
    mock_fetch_tournament_games.return_value = list_tournament_games
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: dict_user_info.get(user_id, None)
    mock_define_odds_between_two_users.return_value = (1.5, 2.0)
    # Act
    await system_generate_game_odd(1)
    # Assert
    bet_games = data_access_fetch_bet_games_by_tournament_id(1)
    assert len(bet_games) == 4
    mock_define_odds_between_two_users.assert_called()
    mock_define_odds_between_two_teams.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.define_odds_between_two_teams.__name__)
@patch.object(bet_functions, bet_functions.define_odds_between_two_users.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
async def test_generating_odd_for_tournament_games_once_per_game_team(
    mock_fetch_tournament_games,
    mock_fetch_tournament,
    mock_define_odds_between_two_users,
    mock_define_odds_between_two_teams,
    mock_fetch_user_info_by_user_id,
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = tournament_team
    mock_fetch_tournament_games.return_value = list_tournament_games
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: dict_user_info.get(user_id, None)
    mock_define_odds_between_two_teams.return_value = (1.5, 2.0)
    # Act
    await system_generate_game_odd(1)
    # Assert
    bet_games = data_access_fetch_bet_games_by_tournament_id(1)
    assert len(bet_games) == 4
    mock_define_odds_between_two_users.assert_not_called()
    mock_define_odds_between_two_teams.assert_called()
