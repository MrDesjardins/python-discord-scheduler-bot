"""
Unit test for the bet functions
"""

from unittest.mock import patch
from datetime import datetime, timezone
import pytest
from deps.bet.bet_data_access import delete_all_bet_tables, data_access_fetch_bet_games_by_tournament_id
from deps.bet.bet_data_class import BetGame, BetUserGame, BetUserTournament
from deps.bet.bet_functions import (
    DEFAULT_MONEY,
    calculate_gain_lost_for_open_bet_game,
    get_open_bet_games_for_tournament,
    get_total_pool_for_game,
    get_bet_user_wallet_for_tournament,
    place_bet_for_game,
    system_generate_game_odd,
)
from deps.tournament_data_class import TournamentGame
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager

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


@patch("deps.bet.bet_functions.get_total_pool_for_game")
def test_calculate_all_bets_for_a_game_winner_user_1(mock_get_total_pool_for_game) -> None:
    """
    Test the result of a bet with 2 winners and 3 losers
    """
    mock_get_total_pool_for_game.return_value = (75, 30, 45)
    tournament_game = TournamentGame(1, 2, 300, 400, 300, "3-5", "Villa", fake_date, None, None)  # Winner is 300
    bet_on_games = [
        BetUserGame(1, 1, 2, 1001, 10, 300, fake_date, 0.4, False),  # Winner
        BetUserGame(2, 1, 2, 1002, 20, 300, fake_date, 0.4, False),  # Winner
        BetUserGame(3, 1, 2, 1003, 15, 400, fake_date, 0.4, False),
        BetUserGame(4, 1, 2, 1004, 25, 400, fake_date, 0.4, False),
        BetUserGame(5, 1, 2, 1005, 5, 400, fake_date, 0.4, False),
    ]
    all_bets = calculate_gain_lost_for_open_bet_game(tournament_game, bet_on_games)
    assert len(all_bets) == 5
    winnings = [x for x in all_bets if x.amount > 0]
    assert len(winnings) == 2
    assert winnings[0].amount == 25
    assert winnings[1].amount == 50


@patch("deps.bet.bet_functions.get_total_pool_for_game")
def test_calculate_all_bets_for_a_game_winner_user_with_diff_dynamic_odd(mock_get_total_pool_for_game) -> None:
    """
    Test the result of a bet with 2 winners and 3 losers
    """
    mock_get_total_pool_for_game.return_value = (75, 30, 45)
    tournament_game = TournamentGame(1, 2, 300, 400, 300, "3-5", "Villa", fake_date, None, None)  # Winner is 300
    bet_on_games = [
        BetUserGame(1, 1, 2, 1001, 10, 300, fake_date, 0.4, False),  # Winner
        BetUserGame(2, 1, 2, 1002, 10, 300, fake_date, 0.5, False),  # Winner, augmented odd (will do less money)
        BetUserGame(3, 1, 2, 1003, 15, 400, fake_date, 0.4, False),
        BetUserGame(4, 1, 2, 1004, 25, 400, fake_date, 0.4, False),
        BetUserGame(5, 1, 2, 1005, 5, 400, fake_date, 0.4, False),
    ]
    all_bets = calculate_gain_lost_for_open_bet_game(tournament_game, bet_on_games)
    assert len(all_bets) == 5
    winnings = [x for x in all_bets if x.amount > 0]
    assert len(winnings) == 2
    assert winnings[0].amount == 25
    assert winnings[1].amount == 20


@patch("deps.bet.bet_functions.get_total_pool_for_game")
def test_calculate_all_bets_for_a_game_winner_house_cut(mock_get_total_pool_for_game) -> None:
    """
    Test the result of a bet with 2 winners and 3 losers
    """
    mock_get_total_pool_for_game.return_value = (75, 30, 45)
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


@patch("deps.bet.bet_functions.get_total_pool_for_game")
def test_calculate_all_bets_for_a_game_winner_user_2(mock_get_total_pool_for_game) -> None:
    """
    Test the result of a bet with 3 winners and 2 losers
    """
    mock_get_total_pool_for_game.return_value = (75, 30, 45)
    tournament_game = TournamentGame(1, 2, 300, 400, 400, "3-5", "Villa", fake_date, None, None)  # Winner is 400
    bet_on_games = [
        BetUserGame(1, 1, 2, 1001, 10, 300, fake_date, 0.4, False),
        BetUserGame(2, 1, 2, 1002, 20, 300, fake_date, 0.4, False),
        BetUserGame(3, 1, 2, 1003, 15, 400, fake_date, 0.4, False),  # Winner
        BetUserGame(4, 1, 2, 1004, 25, 400, fake_date, 0.4, False),  # Winner
        BetUserGame(5, 1, 2, 1005, 5, 400, fake_date, 0.4, False),  # Winner
    ]
    all_bets = calculate_gain_lost_for_open_bet_game(tournament_game, bet_on_games)
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


def test_get_wallet_for_tournament_no_wallet():
    """
    Test the get_wallet_for_tournament function
    """
    wallet = get_bet_user_wallet_for_tournament(1, 1)
    assert wallet is not None


@patch("deps.bet.bet_functions.data_access_create_bet_user_wallet_for_tournament")
def test_get_wallet_for_tournament_no_wallet_creation(mock_create):
    """
    Test the get_wallet_for_tournament function
    """
    mock_create.return_value = BetUserTournament(67, 44, 12, 100)
    get_bet_user_wallet_for_tournament(44, 12)
    mock_create.assert_called_once_with(44, 12, DEFAULT_MONEY)


@patch("deps.bet.bet_functions.data_access_get_bet_user_wallet_for_tournament")
def test_get_wallet_for_tournament_with_wallet(mock_get_user_wallet_for_tournament):
    """
    Test the get_wallet_for_tournament function
    """
    mock_get_user_wallet_for_tournament.return_value = BetUserTournament(121, 1, 1, 100)
    wallet = get_bet_user_wallet_for_tournament(1, 1)
    mock_get_user_wallet_for_tournament.assert_called_once_with(1, 1)
    assert wallet is not None
    assert wallet.id == 121


@patch("deps.bet.bet_functions.data_access_fetch_bet_games_by_tournament_id")
@patch("deps.bet.bet_functions.fetch_tournament_games_by_tournament_id")
async def test_generating_odd_for_tournament_games(mock_fetch_tournament, mock_fetch_bet_games) -> None:
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
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_fetch_tournament.assert_called_once_with(1)
    mock_fetch_bet_games.assert_called_once_with(1)

    bet_games = data_access_fetch_bet_games_by_tournament_id(1)
    assert len(bet_games) == 4


@patch("deps.bet.bet_functions.data_access_fetch_bet_games_by_tournament_id")
@patch("deps.bet.bet_functions.fetch_tournament_games_by_tournament_id")
async def test_get_open_bet_games_for_tournament(mock_fetch_tournament, mock_fetch_bet_games) -> None:
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


@patch("deps.bet.bet_functions.data_access_fetch_bet_games_by_tournament_id")
@patch("deps.bet.bet_functions.fetch_tournament_games_by_tournament_id")
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


@patch("deps.bet.bet_functions.data_access_fetch_bet_games_by_tournament_id")
@patch("deps.bet.bet_functions.fetch_tournament_games_by_tournament_id")
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


@patch("deps.bet.bet_functions.data_access_update_user_wallet_for_tournament")
@patch("deps.bet.bet_functions.data_access_create_bet_user_game")
@patch("deps.bet.bet_functions.data_access_fetch_bet_games_by_tournament_id")
@patch("deps.bet.bet_functions.fetch_tournament_games_by_tournament_id")
@patch("deps.bet.bet_functions.get_bet_user_wallet_for_tournament")
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


@patch("deps.bet.bet_functions.data_access_update_user_wallet_for_tournament")
@patch("deps.bet.bet_functions.data_access_create_bet_user_game")
@patch("deps.bet.bet_functions.data_access_fetch_bet_games_by_tournament_id")
@patch("deps.bet.bet_functions.fetch_tournament_games_by_tournament_id")
@patch("deps.bet.bet_functions.get_bet_user_wallet_for_tournament")
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
