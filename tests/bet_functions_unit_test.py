"""
Unit test for the bet functions
"""

from unittest.mock import patch, call
from datetime import datetime, timezone
import pytest
from deps.data_access_data_class import UserInfo
from deps.bet.bet_data_access import delete_all_bet_tables
from deps.bet.bet_data_class import BetGame, BetLedgerEntry, BetUserGame, BetUserTournament
from deps.bet.bet_functions import (
    DEFAULT_MONEY,
    MIN_BET_AMOUNT,
    calculate_gain_lost_for_open_bet_game,
    distribute_gain_on_recent_ended_game,
    get_open_bet_games_for_tournament,
    get_total_pool_for_game,
    get_bet_user_wallet_for_tournament,
    place_bet_for_game,
    system_generate_game_odd,
)
from deps.tournament_data_class import Tournament, TournamentGame
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from deps.bet import bet_functions

fake_date = datetime(2024, 9, 20, 13, 20, 0, 6318)

HOUSE_CUT = 0  # The house cut between 0 and 1 is the percentage of the money that the house takes


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


def test_get_total_pool_for_game() -> None:
    """
    Test the get_total_pool_for_game function
    """
    tournament_game = TournamentGame(1, 2, 300, 400, 300, "3-5", "Villa", fake_date, None, None)
    bet_on_games = [
        BetUserGame(1, 1, 2, 1001, 10, 300, fake_date, 0.4, False),
        BetUserGame(2, 1, 2, 1002, 20, 300, fake_date, 0.4, False),
        BetUserGame(3, 1, 2, 1003, 15, 400, fake_date, 0.4, False),
        BetUserGame(4, 1, 2, 1004, 25, 400, fake_date, 0.4, False),
    ]
    total_amount_bet, total_amount_bet_on_user_1, total_amount_bet_on_user_2 = get_total_pool_for_game(
        tournament_game, bet_on_games
    )
    assert total_amount_bet == 70
    assert total_amount_bet_on_user_1 == 30
    assert total_amount_bet_on_user_2 == 40


def test_calculate_all_bets_for_a_game_winner_user_1() -> None:
    """
    Test the result of a bet with 2 winners and 3 losers
    """
    tournament_game = TournamentGame(1, 2, 300, 400, 300, "3-5", "Villa", fake_date, None, None)  # Winner is 300
    bet_on_games = [
        BetUserGame(1, 1, 2, 1001, 10, 300, fake_date, 0.4, False),  # Winner
        BetUserGame(2, 1, 2, 1002, 20, 300, fake_date, 0.4, False),  # Winner
        BetUserGame(3, 1, 2, 1003, 15, 400, fake_date, 0.4, False),
        BetUserGame(4, 1, 2, 1004, 25, 400, fake_date, 0.4, False),
        BetUserGame(5, 1, 2, 1005, 5, 400, fake_date, 0.4, False),
    ]
    all_bets = calculate_gain_lost_for_open_bet_game(tournament_game, bet_on_games, HOUSE_CUT)
    assert len(all_bets) == 5
    winnings = [x for x in all_bets if x.amount > 0]
    assert len(winnings) == 2
    assert winnings[0].amount == 25
    assert winnings[1].amount == 50


def test_calculate_all_bets_for_a_game_winner_user_with_diff_dynamic_odd() -> None:
    """
    Test the result of a bet with 2 winners and 3 losers
    """
    tournament_game = TournamentGame(1, 2, 300, 400, 300, "3-5", "Villa", fake_date, None, None)  # Winner is 300
    bet_on_games = [
        BetUserGame(1, 1, 2, 1001, 10, 300, fake_date, 0.4, False),  # Winner
        BetUserGame(2, 1, 2, 1002, 10, 300, fake_date, 0.5, False),  # Winner, augmented odd (will do less money)
        BetUserGame(3, 1, 2, 1003, 15, 400, fake_date, 0.4, False),
        BetUserGame(4, 1, 2, 1004, 25, 400, fake_date, 0.4, False),
        BetUserGame(5, 1, 2, 1005, 5, 400, fake_date, 0.4, False),
    ]
    all_bets = calculate_gain_lost_for_open_bet_game(tournament_game, bet_on_games, HOUSE_CUT)
    assert len(all_bets) == 5
    winnings = [x for x in all_bets if x.amount > 0]
    assert len(winnings) == 2
    assert winnings[0].amount == 25
    assert winnings[1].amount == 20


def test_calculate_all_bets_for_a_game_winner_house_cut() -> None:
    """
    Test the result of a bet with 2 winners and 3 losers
    """
    tournament_game = TournamentGame(1, 2, 300, 400, 300, "3-5", "Villa", fake_date, None, None)  # Winner is 300
    bet_on_games = [
        BetUserGame(1, 1, 2, 1001, 10, 300, fake_date, 0.4, False),  # Winner
        BetUserGame(2, 1, 2, 1002, 20, 300, fake_date, 0.4, False),  # Winner
        BetUserGame(3, 1, 2, 1003, 15, 400, fake_date, 0.4, False),
        BetUserGame(4, 1, 2, 1004, 25, 400, fake_date, 0.4, False),
        BetUserGame(5, 1, 2, 1005, 5, 400, fake_date, 0.4, False),
    ]
    all_bets = calculate_gain_lost_for_open_bet_game(tournament_game, bet_on_games, 0.1)
    assert len(all_bets) == 5
    winnings = [x for x in all_bets if x.amount > 0]
    assert len(winnings) == 2
    assert winnings[0].amount == pytest.approx(22.727272, abs=1e-3)
    assert winnings[1].amount == pytest.approx(45.454545, abs=1e-3)


def test_calculate_all_bets_for_a_game_winner_user_2() -> None:
    """
    Test the result of a bet with 3 winners and 2 losers
    """
    # Arrange
    tournament_game = TournamentGame(1, 2, 300, 400, 400, "3-5", "Villa", fake_date, None, None)  # Winner is 400
    bet_on_games = [
        BetUserGame(1, 1, 2, 1001, 10, 300, fake_date, 0.4, False),
        BetUserGame(2, 1, 2, 1002, 20, 300, fake_date, 0.4, False),
        BetUserGame(3, 1, 2, 1003, 15, 400, fake_date, 0.4, False),  # Winner
        BetUserGame(4, 1, 2, 1004, 25, 400, fake_date, 0.4, False),  # Winner
        BetUserGame(5, 1, 2, 1005, 5, 400, fake_date, 0.4, False),  # Winner
    ]
    # Act
    all_bets = calculate_gain_lost_for_open_bet_game(tournament_game, bet_on_games, HOUSE_CUT)
    # Assert
    assert len(all_bets) == 5
    winnings = [x for x in all_bets if x.amount > 0]
    assert len(winnings) == 3
    assert winnings[0].amount == 37.5
    assert winnings[1].amount == pytest.approx(62.5, abs=1e-3)
    assert winnings[2].amount == pytest.approx(12.5, abs=1e-3)


def test_moneyline_odd_user():
    """
    Test the moneyline_odd_user_1 function
    """
    bet_game = BetGame(1, 1, 2, 0.5, 0.5, False)
    assert bet_game.moneyline_odd_user_1() == -100
    assert bet_game.moneyline_odd_user_2() == -100

    bet_game = BetGame(1, 1, 2, 0.4, 0.6, False)
    assert bet_game.moneyline_odd_user_1() == 250
    assert bet_game.moneyline_odd_user_2() == -150

    bet_game = BetGame(1, 1, 2, 0.6, 0.4, False)
    assert bet_game.moneyline_odd_user_1() == -150
    assert bet_game.moneyline_odd_user_2() == 250


@patch.object(bet_functions, bet_functions.data_access_create_bet_user_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_wallet_for_tournament.__name__)
def test_get_wallet_for_tournament_no_wallet_create_one(mock_get_user_wallet_for_tournament, mock_create_bet):
    """
    Test the user scenario that a user does not have a wallet
    """
    # Arrange
    mock_get_user_wallet_for_tournament.return_value = None
    mock_create_bet.return_value = BetUserTournament(67, 44, 12, 100)
    # Act
    get_bet_user_wallet_for_tournament(44, 12)
    # Assert
    mock_create_bet.assert_called_once_with(44, 12, DEFAULT_MONEY)
    mock_get_user_wallet_for_tournament.assert_called()
    assert (
        mock_get_user_wallet_for_tournament.call_count == 2
    )  # One time for the None and one time for the created wallet


@patch.object(bet_functions, bet_functions.data_access_create_bet_user_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_wallet_for_tournament.__name__)
def test_get_wallet_for_tournament_with_wallet(mock_get_user_wallet_for_tournament, mock_create_bet):
    """
    Test the get_wallet_for_tournament function
    """
    mock_get_user_wallet_for_tournament.return_value = BetUserTournament(121, 1, 1, 100)
    wallet = get_bet_user_wallet_for_tournament(1, 1)
    mock_get_user_wallet_for_tournament.assert_called_once_with(1, 1)
    mock_create_bet.assert_not_called()
    assert wallet is not None
    assert wallet.id == 121


@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
async def test_generating_odd_for_tournament_games_for_only_game_without_ones_and_unknown_user(
    mock_create_bet_game, mock_fetch_tournament, mock_fetch_bet_games, mock_fetch_user
) -> None:
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
    list_existing_bet_games = []
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_fetch_user.return_value = None
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_fetch_tournament.assert_called_once_with(1)
    mock_fetch_bet_games.assert_called_once_with(1)
    assert mock_create_bet_game.call_args_list == [
        call(1, 1, 0.5, 0.5),
        call(1, 2, 0.5, 0.5),
        call(1, 3, 0.5, 0.5),
        call(1, 4, 0.5, 0.5),
    ]


@patch.object(bet_functions, bet_functions.define_odds_between_two_users.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
async def test_generating_odd_for_tournament_games_for_only_game_without_ones_and_known_user(
    mock_create_bet_game, mock_fetch_tournament, mock_fetch_bet_games, mock_fetch_user, mock_define_odds
) -> None:
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
    list_existing_bet_games = []
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_fetch_user.side_effect = lambda user_id: UserInfo(user_id, f"User {user_id}", None, None, None, "pst")
    mock_define_odds.return_value = (0.5, 0.5)
    mock_create_bet_game.return_value = None
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_fetch_tournament.assert_called_once_with(1)
    mock_fetch_bet_games.assert_called_once_with(1)
    mock_define_odds.call_count = 4


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
async def test_generating_odd_for_tournament_games_calls_create_bet(
    mock_create_bet_game, mock_fetch_tournament, mock_fetch_bet_games
) -> None:
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
    mock_fetch_bet_games.return_value = []
    mock_create_bet_game.return_value = None
    await system_generate_game_odd(1)
    mock_fetch_bet_games.return_value = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(1, 1, 2, 0.5, 0.5, False),
        BetGame(1, 1, 3, 0.5, 0.5, False),
        BetGame(1, 1, 4, 0.5, 0.5, False),
    ]
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_create_bet_game.call_count = 4


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
async def test_get_open_bet_games_for_tournament(
    mock_create_bet_game, mock_fetch_tournament, mock_fetch_bet_games
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, 1, "3-5", None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = list_tournament_games
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
        BetGame(4, 1, 4, 0.5, 0.5, False),
    ]
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_game.return_value = None
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_fetch_tournament.assert_called_once_with(1)
    mock_fetch_bet_games.assert_called_once_with(1)

    bet_games = get_open_bet_games_for_tournament(1)
    assert len(bet_games) == 3
    assert len([game for game in bet_games if game.id == 2]) == 1
    assert len([game for game in bet_games if game.id == 3]) == 1
    assert len([game for game in bet_games if game.id == 4]) == 1


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
async def test_system_generate_game_odd_with_game_without_two_users(
    mock_fetch_user, mock_create_bet_game, mock_fetch_tournament, mock_fetch_bet_games
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, 1, "3-5", None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, None, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = list_tournament_games
    list_existing_bet_games = []
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_game.return_value = None
    mock_fetch_user.return_value = None
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_fetch_tournament.assert_called_once_with(1)
    mock_fetch_bet_games.assert_called_once_with(1)
    # We do not have 4 and 5 because one of the two are None
    assert mock_create_bet_game.call_args_list == [
        call(1, 2, 0.5, 0.5),
        call(1, 3, 0.5, 0.5),
    ]


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
async def test_placing_bet_on_completed_game(mock_fetch_tournament, mock_fetch_bet_games) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, 1, "3-5", None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = list_tournament_games
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
        BetGame(4, 1, 4, 0.5, 0.5, False),
    ]
    mock_fetch_bet_games.return_value = list_existing_bet_games
    # Act
    with pytest.raises(ValueError, match="The game is already finished"):
        place_bet_for_game(1, 1, 1001, 99.65, 1)


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
async def test_placing_bet_on_inexisting_game(mock_fetch_tournament, mock_fetch_bet_games) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, 1, "3-5", None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament.return_value = list_tournament_games
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
        BetGame(4, 1, 4, 0.5, 0.5, False),
    ]
    mock_fetch_bet_games.return_value = list_existing_bet_games
    # Act
    with pytest.raises(ValueError, match="The Bet on this game does not exist"):
        place_bet_for_game(1, 99999999, 1001, 99.65, 1)


@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_that_no_exist(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, 1, "3-5", None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_wallet.return_value = BetUserTournament(1, 1, 100, 10.99)
    mock_fetch_tournament.return_value = list_tournament_games
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 200, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
        BetGame(4, 1, 4, 0.5, 0.5, False),
    ]
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_user_game.return_value = None
    mock_update_user_wallet_for_tournament.return_value = None
    # Act
    with pytest.raises(ValueError, match="The game does not exist"):
        place_bet_for_game(1, 2, 1001, 99.65, 1)


@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_without_fund(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, 1, "3-5", None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]

    mock_wallet.return_value = BetUserTournament(1, 1, 100, 10.99)
    mock_fetch_tournament.return_value = list_tournament_games
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
        BetGame(4, 1, 4, 0.5, 0.5, False),
    ]
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_user_game.return_value = None
    mock_update_user_wallet_for_tournament.return_value = None
    # Act
    with pytest.raises(ValueError, match="The user does not have enough money"):
        place_bet_for_game(1, 2, 1001, 11, 1)


@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_you_are_part(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]

    mock_wallet.return_value = BetUserTournament(1, 1, 100, 1000)
    mock_fetch_tournament.return_value = list_tournament_games
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
        BetGame(4, 1, 4, 0.5, 0.5, False),
    ]
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_user_game.return_value = None
    mock_update_user_wallet_for_tournament.return_value = None
    # Act
    with pytest.raises(ValueError, match="The user cannot bet on a game where he/she is playing"):
        place_bet_for_game(1, 1, 1, 99.99, 1)


@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_good_scenario(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]

    mock_wallet.return_value = BetUserTournament(1, 1, 100, 1000)
    mock_fetch_tournament.return_value = list_tournament_games
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
        BetGame(4, 1, 4, 0.5, 0.5, False),
    ]
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_user_game.return_value = None
    mock_update_user_wallet_for_tournament.return_value = None
    # Act
    place_bet_for_game(1, 2, 1, 99.99, 1)


@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_too_small_amount(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]

    mock_wallet.return_value = BetUserTournament(1, 1, 100, 1000)
    mock_fetch_tournament.return_value = list_tournament_games
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
        BetGame(4, 1, 4, 0.5, 0.5, False),
    ]
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_user_game.return_value = None
    mock_update_user_wallet_for_tournament.return_value = None
    # Act
    with pytest.raises(ValueError, match=f"The minimum amount to bet is \${MIN_BET_AMOUNT}"):
        place_bet_for_game(1, 2, 1, 0.99, 1)


@patch.object(bet_functions, bet_functions.data_access_get_all_wallet_for_tournament.__name__)
async def test_generate_msg_bet_leaderboard_no_users(mock_get_all_wallet) -> None:
    """
    Test the generate_msg_bet_leaderboard function
    """
    # Arrange
    mock_get_all_wallet.return_value = []
    tournament = Tournament(1, 2, "Tournament 1", fake_date, fake_date, fake_date, 5, 16, "villa", False, 0)
    # Act
    msg = await bet_functions.generate_msg_bet_leaderboard(tournament)
    # Assert
    assert msg == ""


@patch.object(bet_functions, bet_functions.data_access_get_all_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
async def test_generate_msg_bet_leaderboard_users(mock_fetch_user, mock_get_all_wallet) -> None:
    """
    Test the generate_msg_bet_leaderboard function
    """
    # Arrange
    mock_get_all_wallet.return_value = [
        BetUserTournament(1, 2, 100, 10.99),
        BetUserTournament(2, 2, 200, 20.99),
        BetUserTournament(3, 2, 300, 30.99),
    ]
    mock_fetch_user.side_effect = lambda user_id: UserInfo(user_id, f"User {user_id}", None, None, None, "pst")
    tournament = Tournament(1, 2, "Tournament 1", fake_date, fake_date, fake_date, 5, 16, "villa", False, 0)
    # Act
    msg = await bet_functions.generate_msg_bet_leaderboard(tournament)
    # Assert
    assert msg == "1 - User 300 - $30.99\n2 - User 200 - $20.99\n3 - User 100 - $10.99"


@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_game_ready_to_close.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_ready_for_distribution.__name__)
@patch.object(bet_functions, bet_functions.calculate_gain_lost_for_open_bet_game.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_insert_bet_ledger_entry.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_game_distribution_completed.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_distribution_completed.__name__)
def test_distribute_gain_on_recent_ended_game_success_scenario_winning_bet(
    mock_data_access_update_bet_game_distribution_completed,
    mock_data_access_update_bet_user_game_distribution_completed,
    mock_data_access_insert_bet_ledger_entry,
    mock_data_access_update_bet_user_tournament,
    mock_get_bet_user_wallet_for_tournament,
    mock_calculate_gain_lost_for_open_bet_game,
    mock_data_access_get_bet_user_game_ready_for_distribution,
    mock_data_access_get_bet_game_ready_to_close,
    mock_fetch_tournament_games_by_tournament_id,
) -> None:
    """
    Unit test that checks if the specific call to the database occurs according to the scenario
    that there is a single bet on a game that just ended
    """
    # Arrange
    tournament = Tournament(1, 2, "Tournament 1", fake_date, fake_date, fake_date, 5, 16, "villa", False, 0)
    mock_fetch_tournament_games_by_tournament_id.return_value = [
        TournamentGame(1, tournament.id, 10, 11, 10, "1-4", None, None, None, None)
    ]
    mock_data_access_get_bet_game_ready_to_close.return_value = [BetGame(33, tournament.id, 1, 0.5, 0.5, False)]
    mock_data_access_get_bet_user_game_ready_for_distribution.return_value = [
        BetUserGame(7, 1, 33, 13, 99.98, 10, fake_date, 0.5, False)
    ]
    ledger_entry_1 = BetLedgerEntry(888, 1, 1, 33, 7, 13, 99.98)
    mock_calculate_gain_lost_for_open_bet_game.return_value = [ledger_entry_1]
    bet_user_tour = BetUserTournament(62, 1, 100, 500)
    mock_get_bet_user_wallet_for_tournament.return_value = bet_user_tour

    # Act
    distribute_gain_on_recent_ended_game(1)
    # Assert
    mock_data_access_update_bet_user_tournament.assert_called_once_with(62, 599.98)
    mock_data_access_insert_bet_ledger_entry.assert_called_once_with(ledger_entry_1)
    mock_data_access_update_bet_user_game_distribution_completed.assert_called_once_with(7)
    mock_data_access_update_bet_game_distribution_completed.assert_called_once_with(33)


@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_game_ready_to_close.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_ready_for_distribution.__name__)
@patch.object(bet_functions, bet_functions.calculate_gain_lost_for_open_bet_game.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_insert_bet_ledger_entry.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_game_distribution_completed.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_distribution_completed.__name__)
def test_distribute_gain_on_recent_ended_game_success_scenario_losing_bet(
    mock_data_access_update_bet_game_distribution_completed,
    mock_data_access_update_bet_user_game_distribution_completed,
    mock_data_access_insert_bet_ledger_entry,
    mock_data_access_update_bet_user_tournament,
    mock_get_bet_user_wallet_for_tournament,
    mock_calculate_gain_lost_for_open_bet_game,
    mock_data_access_get_bet_user_game_ready_for_distribution,
    mock_data_access_get_bet_game_ready_to_close,
    mock_fetch_tournament_games_by_tournament_id,
) -> None:
    """
    Unit test for a bet that failed, it should not give the money but still register in the ledger
    and close the game bet + user bet
    """
    # Arrange
    tournament = Tournament(1, 2, "Tournament 1", fake_date, fake_date, fake_date, 5, 16, "villa", False, 0)
    mock_fetch_tournament_games_by_tournament_id.return_value = [
        TournamentGame(1, tournament.id, 10, 11, 10, "1-4", None, None, None, None)
    ]
    mock_data_access_get_bet_game_ready_to_close.return_value = [BetGame(33, tournament.id, 1, 0.5, 0.5, False)]
    mock_data_access_get_bet_user_game_ready_for_distribution.return_value = [
        BetUserGame(7, 1, 33, 13, 99.98, 11, fake_date, 0.5, False)
    ]
    ledger_entry_1 = BetLedgerEntry(888, 1, 1, 33, 7, 13, 99.98)
    mock_calculate_gain_lost_for_open_bet_game.return_value = [ledger_entry_1]
    bet_user_tour = BetUserTournament(62, 1, 100, 500)
    mock_get_bet_user_wallet_for_tournament.return_value = bet_user_tour

    # Act
    distribute_gain_on_recent_ended_game(1)
    # Assert
    mock_data_access_update_bet_user_tournament.asset_called_none()
    mock_data_access_insert_bet_ledger_entry.assert_called_once_with(ledger_entry_1)
    mock_data_access_update_bet_user_game_distribution_completed.assert_called_once_with(7)
    mock_data_access_update_bet_game_distribution_completed.assert_called_once_with(33)
