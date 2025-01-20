""" Test that touch the bet and the database """

from datetime import datetime
from unittest.mock import patch
import pytest
from deps.bet.bet_functions import (
    distribute_gain_on_recent_ended_game,
    get_bet_user_wallet_for_tournament,
    place_bet_for_game,
    system_generate_game_odd,
)
from deps.bet.bet_data_access import (
    data_access_create_bet_user_wallet_for_tournament,
    data_access_fetch_bet_user_game_by_tournament_id,
    data_access_get_bet_ledger_entry_for_tournament,
    data_access_get_bet_user_wallet_for_tournament,
    delete_all_bet_tables,
    data_access_fetch_bet_games_by_tournament_id,
    data_access_get_bet_user_game_ready_for_distribution,
)
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from deps.tournament_data_access import (
    data_access_insert_tournament,
    delete_all_tournament_tables,
    fetch_tournament_games_by_tournament_id,
    register_user_for_tournament,
)
from deps.tournament_functions import report_lost_tournament, start_tournaments
from deps.bet import bet_functions


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


def test_get_user_wallet_if_no_wallet() -> None:
    """Test that check if the user has no wallet"""
    # Arrange
    user_id = 1
    tournament_id = 1

    # Act
    wallet = data_access_get_bet_user_wallet_for_tournament(tournament_id, user_id)

    # Assert
    assert wallet is None


def test_create_and_get_wallet() -> None:
    """Test that create a wallet and then get it"""
    # Arrange
    user_id = 1
    tournament_id = 1
    initial_amount = 100

    # Act
    data_access_create_bet_user_wallet_for_tournament(tournament_id, user_id, initial_amount)
    wallet = data_access_get_bet_user_wallet_for_tournament(tournament_id, user_id)

    # Assert
    assert wallet is not None
    assert wallet.tournament_id == tournament_id
    assert wallet.user_id == user_id
    assert wallet.amount == initial_amount


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
    bet_games = data_access_get_bet_user_game_ready_for_distribution(tournament_id)
    # Assert
    assert len(bet_games) == 0


async def test_get_bet_game_ready_for_distribution_one_game_done_with_one_user_lose_bet() -> None:
    """Test that check if there is no game ready for distribution"""
    # Arrange
    user_placing_the_bet_id = 1009
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
        tournament_id, one_bet_game.id, user_placing_the_bet_id, 10, games_dict[one_bet_game.game_id].user1_id
    )  # Bet user 1
    report_lost_tournament(tournament_id, games_dict[one_bet_game.game_id].user2_id, "1-1")  # Lost user 2
    # Act
    bet_games = data_access_get_bet_user_game_ready_for_distribution(tournament_id)  # Winner bet here

    # Assert
    assert len(bet_games) == 1


async def test_distribute_gain_on_recent_ended_game_winning_bet_scenario() -> None:
    """Test the distribution to the user who won the bet"""
    # Arrange
    user_placing_the_bet_id = 1009
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
        tournament_id, one_bet_game.id, user_placing_the_bet_id, 10, games_dict[one_bet_game.game_id].user1_id
    )  # Bet user 1
    report_lost_tournament(tournament_id, games_dict[one_bet_game.game_id].user2_id, "1-1")  # Lost user 2
    # Act
    distribute_gain_on_recent_ended_game(tournament_id)  # Winner bet here
    # Assert
    user_wallet = get_bet_user_wallet_for_tournament(tournament_id=tournament_id, user_id=1009)
    assert user_wallet.amount == 1010
    # Assert ledger
    full_ledger_entries = data_access_get_bet_ledger_entry_for_tournament(tournament_id)
    assert len(full_ledger_entries) == 1
    assert full_ledger_entries[0].amount == 20  # The gain is 10$ (the bet amount) + 10$ (the gain)
    # Assert the bet_game to not be yet distributed
    bet_games = data_access_fetch_bet_games_by_tournament_id(tournament_id)
    assert bet_games[0].bet_distributed is True
    # Assert the bet_user_game to not be yet distributed
    bet_user_game = data_access_fetch_bet_user_game_by_tournament_id(tournament_id)
    assert bet_user_game[0].bet_distributed is True


async def test_distribute_gain_on_recent_ended_game_losing_bet_scenario() -> None:
    """Test the distribution to the user who won the bet"""
    # Arrange
    user_placing_the_bet_id = 1009
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
        tournament_id, one_bet_game.id, user_placing_the_bet_id, 10, games_dict[one_bet_game.game_id].user1_id
    )  # Bet user 1
    report_lost_tournament(tournament_id, games_dict[one_bet_game.game_id].user1_id, "1-1")  # Lost user 1
    # Act
    distribute_gain_on_recent_ended_game(tournament_id)  # Loser bet here
    # Assert user wallet (bet_user_tournament)
    user_wallet = get_bet_user_wallet_for_tournament(tournament_id=tournament_id, user_id=1009)
    assert user_wallet.amount == 990
    # Assert ledger
    full_ledger_entries = data_access_get_bet_ledger_entry_for_tournament(tournament_id)
    assert len(full_ledger_entries) == 1
    assert (
        full_ledger_entries[0].amount == 0
    )  # The lost is 10$ (the bet amount) but the ledger contains only the data movement (so 0$ since nothing distributed)
    # Assert the bet_game to not be yet distributed
    bet_games = data_access_fetch_bet_games_by_tournament_id(tournament_id)
    assert bet_games[0].bet_distributed is True
    # Assert the bet_user_game to not be yet distributed
    bet_user_game = data_access_fetch_bet_user_game_by_tournament_id(tournament_id)
    assert bet_user_game[0].bet_distributed is True

@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
async def test_distribute_gain_on_recent_ended_game_error_rollback(update_wallet_mock) -> None:
    """Test the distribution to the user who won the bet"""
    # Arrange
    user_placing_the_bet_id = 1009
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
        tournament_id, one_bet_game.id, user_placing_the_bet_id, 10, games_dict[one_bet_game.game_id].user1_id
    )  # Bet user 1
    report_lost_tournament(tournament_id, games_dict[one_bet_game.game_id].user2_id, "1-1")  # User 1 win
    # Act
    update_wallet_mock.side_effect = Exception("Error")
    distribute_gain_on_recent_ended_game(tournament_id)  # Loser bet here
    # Assert user wallet (bet_user_tournament)
    user_wallet = get_bet_user_wallet_for_tournament(tournament_id=tournament_id, user_id=1009)
    assert user_wallet.amount == 1000  # did not change! because of the error (rollback)
    # Assert ledger
    full_ledger_entries = data_access_get_bet_ledger_entry_for_tournament(tournament_id)
    assert len(full_ledger_entries) == 0  # No entry because of the error (rollback)
    # Assert the bet_game to not be yet distributed
    bet_games = data_access_fetch_bet_games_by_tournament_id(tournament_id)
    assert bet_games[0].bet_distributed is False
    # Assert the bet_user_game to not be yet distributed
    bet_user_game = data_access_fetch_bet_user_game_by_tournament_id(tournament_id)
    assert bet_user_game[0].bet_distributed is False
