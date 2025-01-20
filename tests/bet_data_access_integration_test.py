""" Test that touch the bet and the database """

from datetime import datetime
from unittest.mock import patch
import pytest
from deps.bet.bet_functions import place_bet_for_game, system_generate_game_odd
from deps.bet.bet_data_access import (
    delete_all_bet_tables,
    data_access_fetch_bet_games_by_tournament_id,
    data_access_fetch_bet_user_game_by_tournament_id,
    data_access_get_bet_game_ready_for_distribution,
)
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from deps.tournament_data_access import (
    data_access_create_bracket,
    data_access_insert_tournament,
    delete_all_tournament_tables,
    fetch_tournament_games_by_tournament_id,
    register_user_for_tournament,
)
from deps.tournament_functions import report_lost_tournament, start_tournaments


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    database_manager.set_database_name(DATABASE_NAME_TEST)
    delete_all_tournament_tables()
    delete_all_bet_tables()

    # Yield control to the test functions
    yield

    # Teardown
    database_manager.set_database_name(DATABASE_NAME)


async def test_get_bet_game_ready_for_distribution_no_bet_placed() -> None:
    """Test that check if there is no game ready for distribution"""
    # Arrange
    tournament_id = data_access_insert_tournament(
        1, "Test Tournament", datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3), 3, 4, "Villa"
    )
    register_user_for_tournament(tournament_id, 10, datetime(2021, 1, 1))
    register_user_for_tournament(tournament_id, 11, datetime(2021, 1, 1))
    register_user_for_tournament(tournament_id, 12, datetime(2021, 1, 1))
    register_user_for_tournament(tournament_id, 13, datetime(2021, 1, 1))
    start_tournaments(datetime(2021, 1, 2))
    await system_generate_game_odd(tournament_id)
    # Tournament started but no bet by any user
    # Act
    bet_games = data_access_get_bet_game_ready_for_distribution(tournament_id)
    # Assert
    assert len(bet_games) == 0


async def test_get_bet_game_ready_for_distribution_one_game_done_with_one_user_lose_bet() -> None:
    """Test that check if there is no game ready for distribution"""
    # Arrange
    tournament_id = data_access_insert_tournament(
        1, "Test Tournament", datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3), 3, 4, "Villa"
    )
    register_user_for_tournament(tournament_id, 10, datetime(2021, 1, 1))
    register_user_for_tournament(tournament_id, 11, datetime(2021, 1, 1))
    register_user_for_tournament(tournament_id, 12, datetime(2021, 1, 1))
    register_user_for_tournament(tournament_id, 13, datetime(2021, 1, 1))
    start_tournaments(datetime(2021, 1, 2))
    await system_generate_game_odd(tournament_id)
    games = fetch_tournament_games_by_tournament_id(tournament_id)
    games_dict = {game.id: game for game in games}
    bet_games = data_access_fetch_bet_games_by_tournament_id(tournament_id)
    one_bet_game = bet_games[0]
    place_bet_for_game(
        tournament_id, one_bet_game.id, games_dict[one_bet_game.game_id].user1_id, 10, 1009
    )  # Bet user 1
    report_lost_tournament(tournament_id, games_dict[one_bet_game.game_id].user2_id, "1-1")  # Lost user 2
    # Act
    bet_games = data_access_get_bet_game_ready_for_distribution(tournament_id)  # Winner bet here

    # Assert
    assert len(bet_games) == 1
