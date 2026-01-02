"""
Unit test for the bet functions
"""

from typing import List
from unittest.mock import patch, call
from datetime import datetime, timezone
import pytest
from deps.data_access_data_class import UserInfo
from deps.bet.bet_data_class import BetGame, BetLedgerEntry, BetUserGame, BetUserTournament
from deps.bet.bet_functions import (
    DEFAULT_MONEY,
    MIN_BET_AMOUNT,
    calculate_gain_lost_for_open_bet_game,
    define_odds_between_two_users,
    define_odds_between_two_teams,
    distribute_gain_on_recent_ended_game,
    dynamically_adjust_bet_game_odd,
    generate_msg_bet_game,
    get_bet_user_amount_active_bet,
    get_open_bet_games_for_tournament,
    get_total_pool_for_game,
    get_bet_user_wallet_for_tournament,
    place_bet_for_game,
    system_generate_game_odd,
)
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.bet import bet_functions
from deps.models import UserFullMatchStats
from deps.tournaments.tournament_models import TournamentNode

now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
later_date = datetime(2025, 7, 3, 17, 36, 0, tzinfo=timezone.utc)
fake_date = datetime(2024, 9, 20, 13, 20, 0, 6318)
tournament = Tournament(1, 2, "Tournament 1", fake_date, fake_date, fake_date, 5, 16, "villa", False, False, 0)
HOUSE_CUT = 0  # The house cut between 0 and 1 is the percentage of the money that the house takes


def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    global tournament
    tournament = Tournament(1, 2, "Tournament 1", fake_date, fake_date, fake_date, 5, 16, "villa", False, False, 0)

    # Yield control to the test functions
    yield

    # Teardown
    tournament = None


def test_calculate_gain_lost_for_open_bet_game_with_game_not_defined() -> None:
    """
    Test the exceptional case of a tournament game without an id
    """
    tournament_game = TournamentGame(None, 2, 300, 400, 300, "3-5", "Villa", fake_date, None, None)
    result = calculate_gain_lost_for_open_bet_game(tournament_game, [], HOUSE_CUT)
    assert not result


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
    tournament = BetUserTournament(67, 44, 12, 100)
    mock_get_user_wallet_for_tournament.side_effect = [None, tournament]
    mock_create_bet.return_value = tournament
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
def test_get_wallet_for_tournament_no_wallet_create_one_fail(mock_get_user_wallet_for_tournament, mock_create_bet):
    """
    Test the user scenario that a user does not have a wallet
    """
    # Arrange
    tournament = BetUserTournament(67, 44, 12, 100)
    mock_get_user_wallet_for_tournament.side_effect = [None, None]
    mock_create_bet.return_value = tournament
    # Act & Assert
    with pytest.raises(ValueError, match="Error creating wallet"):
        get_bet_user_wallet_for_tournament(44, 12)


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


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
async def test_generating_odd_for_tournament_games_for_only_game_without_ones_and_unknown_user(
    mock_create_bet_game, mock_fetch_tournament_game, mock_fetch_bet_games, mock_fetch_user, mock_fetch_tournament
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament_game.return_value = list_tournament_games
    mock_fetch_tournament.return_value = tournament
    list_existing_bet_games: List[BetGame] = []
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


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.define_odds_between_two_users.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
async def test_generating_odd_for_tournament_games_for_only_game_without_ones_and_known_user(
    mock_create_bet_game,
    mock_fetch_tournament_game,
    mock_fetch_bet_games,
    mock_fetch_user,
    mock_define_odds,
    mock_fetch_tournament,
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament_game.return_value = list_tournament_games
    mock_fetch_tournament.return_value = tournament
    list_existing_bet_games: List[BetGame] = []
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_fetch_user.side_effect = lambda user_id: UserInfo(user_id, f"User {user_id}", None, None, None, "pst", 0)
    mock_define_odds.return_value = (0.5, 0.5)
    mock_create_bet_game.return_value = None
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_fetch_tournament_game.assert_called_once_with(1)
    mock_fetch_bet_games.assert_called_once_with(1)
    mock_define_odds.call_count = 4


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
async def test_generating_odd_for_tournament_games_calls_create_bet(
    mock_create_bet_game,
    mock_fetch_tournament_game,
    mock_fetch_bet_games,
    mock_fetch_tournament,
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament_game.return_value = list_tournament_games
    mock_fetch_tournament.return_value = tournament
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


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
async def test_get_open_bet_games_for_tournament(
    mock_create_bet_game, mock_fetch_tournament_game, mock_fetch_bet_games, mock_fetch_tournament
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, 1, "3-5", None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament_game.return_value = list_tournament_games
    mock_fetch_tournament.return_value = tournament
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
    mock_fetch_tournament_game.assert_called_once_with(1)
    mock_fetch_bet_games.assert_called_once_with(1)

    bet_games = get_open_bet_games_for_tournament(1)
    assert len(bet_games) == 3
    assert len([game for game in bet_games if game.id == 2]) == 1
    assert len([game for game in bet_games if game.id == 3]) == 1
    assert len([game for game in bet_games if game.id == 4]) == 1


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_game.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
async def test_system_generate_game_odd_with_game_without_two_users(
    mock_fetch_user, mock_create_bet_game, mock_fetch_tournament_game, mock_fetch_bet_games, mock_fetch_tournament
) -> None:
    """Test that generate the odd for the tournament games"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, 1, "3-5", None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, None, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    mock_fetch_tournament_game.return_value = list_tournament_games
    mock_fetch_tournament.return_value = tournament
    list_existing_bet_games: List[BetGame] = []
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_game.return_value = None
    mock_fetch_user.return_value = None
    # Act
    await system_generate_game_odd(1)
    # Assert
    mock_fetch_tournament_game.assert_called_once_with(1)
    mock_fetch_bet_games.assert_called_once_with(1)
    # We do not have 4 and 5 because one of the two are None
    assert mock_create_bet_game.call_args_list == [
        call(1, 2, 0.5, 0.5),
        call(1, 3, 0.5, 0.5),
    ]


@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_completed_game(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
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
    # Assert
    mock_wallet.assert_not_called()
    mock_create_bet_user_game.assert_not_called()
    mock_update_user_wallet_for_tournament.assert_not_called()
    mock_probability_update.assert_not_called()
    mock_dynamically_adjust_bet_game_odd.assert_not_called()


@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_inexisting_game(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
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
    with pytest.raises(ValueError, match="The bet on this game does not exist"):
        place_bet_for_game(1, 99999999, 1001, 99.65, 1)
    # Assert
    mock_wallet.assert_not_called()
    mock_create_bet_user_game.assert_not_called()
    mock_update_user_wallet_for_tournament.assert_not_called()
    mock_probability_update.assert_not_called()
    mock_dynamically_adjust_bet_game_odd.assert_not_called()


@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
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
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
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
    # Assert
    mock_probability_update.assert_not_called()
    mock_dynamically_adjust_bet_game_odd.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_without_fund(
    mock_wallet,
    mock_fetch_tournament_games,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_fetch_tournament_by_id,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, 1, "3-5", None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, 9, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]

    mock_wallet.return_value = BetUserTournament(1, 1, 100, 10.99)
    mock_fetch_tournament_games.return_value = list_tournament_games
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
        BetGame(4, 1, 4, 0.5, 0.5, False),
    ]
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_user_game.return_value = None
    mock_update_user_wallet_for_tournament.return_value = None
    mock_fetch_tournament_by_id.return_value = tournament

    # Act
    with pytest.raises(ValueError, match="The user does not have enough money"):
        place_bet_for_game(1, 2, 1001, 11, 1)
    # Assert
    mock_probability_update.assert_not_called()
    mock_dynamically_adjust_bet_game_odd.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
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
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_fetch_tournament_by_id,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
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
    mock_fetch_tournament_by_id.return_value = tournament

    # Act
    with pytest.raises(ValueError, match="The user cannot bet on a game where he/she is playing"):
        place_bet_for_game(1, 1, 1, 99.99, 1)
    # Assert
    mock_probability_update.assert_not_called()
    mock_dynamically_adjust_bet_game_odd.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_tournament_team_members_by_leader.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_you_are_part_of_the_team_as_leader(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_fetch_tournament_by_id,
    mock_fetch_tournament_team_members_by_leader,
) -> None:
    """Test the scenario of a team tournament and a leader place a bet on a game where he/she is part of the team"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 3, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 5, 7, None, None, None, now_date, None, None),
        TournamentGame(3, 1, None, None, None, None, None, now_date, 1, 2),
    ]
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
    ]
    mock_wallet.return_value = BetUserTournament(1, 1, 100, 1000)
    mock_fetch_tournament.return_value = list_tournament_games
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_user_game.return_value = None
    mock_update_user_wallet_for_tournament.return_value = None
    tournament.team_size = 2
    mock_fetch_tournament_by_id.return_value = tournament
    mock_fetch_tournament_team_members_by_leader.return_value = {1: [2], 3: [4], 5: [6], 7: [8]}

    # Act
    with pytest.raises(ValueError, match="The user cannot bet on a game where a member of their team is playing"):
        place_bet_for_game(1, 1, 1, 99.99, 1)
    # Assert
    mock_probability_update.assert_not_called()
    mock_dynamically_adjust_bet_game_odd.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_tournament_team_members_by_leader.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_leader_bid_teammate(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_fetch_tournament_by_id,
    mock_fetch_tournament_team_members_by_leader,
) -> None:
    """Test the scenario of a team tournament and a teammate place a bet on a game where he/she is part of the team"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 3, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 5, 7, None, None, None, now_date, None, None),
        TournamentGame(3, 1, None, None, None, None, None, now_date, 1, 2),
    ]
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
    ]
    mock_wallet.return_value = BetUserTournament(1, 1, 100, 1000)
    mock_fetch_tournament.return_value = list_tournament_games
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_user_game.return_value = None
    mock_update_user_wallet_for_tournament.return_value = None
    tournament.team_size = 2
    mock_fetch_tournament_by_id.return_value = tournament
    mock_fetch_tournament_team_members_by_leader.return_value = {1: [2], 3: [4], 5: [6], 7: [8]}

    # Act
    with pytest.raises(ValueError, match="The user cannot bet on a game where a member of their team is playing"):
        place_bet_for_game(1, 1, 1, 99.99, 2)
    # Assert
    mock_probability_update.assert_not_called()
    mock_dynamically_adjust_bet_game_odd.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_tournament_team_members_by_leader.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_teammate_bid_leader(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_fetch_tournament_by_id,
    mock_fetch_tournament_team_members_by_leader,
) -> None:
    """Test the scenario of a team tournament and a teammate place a bet on a game where he/she is part of the team"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 3, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 5, 7, None, None, None, now_date, None, None),
        TournamentGame(3, 1, None, None, None, None, None, now_date, 1, 2),
    ]
    list_existing_bet_games = [
        BetGame(1, 1, 1, 0.5, 0.5, False),
        BetGame(2, 1, 2, 0.5, 0.5, False),
        BetGame(3, 1, 3, 0.5, 0.5, False),
    ]
    mock_wallet.return_value = BetUserTournament(1, 1, 100, 1000)
    mock_fetch_tournament.return_value = list_tournament_games
    mock_fetch_bet_games.return_value = list_existing_bet_games
    mock_create_bet_user_game.return_value = None
    mock_update_user_wallet_for_tournament.return_value = None
    tournament.team_size = 2
    mock_fetch_tournament_by_id.return_value = tournament
    mock_fetch_tournament_team_members_by_leader.return_value = {1: [2], 3: [4], 5: [6], 7: [8]}

    # Act
    with pytest.raises(ValueError, match="The user cannot bet on a game where a member of their team is playing"):
        place_bet_for_game(1, 1, 2, 99.99, 1)
    # Assert
    mock_probability_update.assert_not_called()
    mock_dynamically_adjust_bet_game_odd.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_user1(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_fetch_tournament_by_id,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    with patch("deps.bet.bet_functions.datetime") as mock_datetime:
        mock_datetime.now.return_value = now_date
        list_tournament_games: List[TournamentGame] = [
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
            BetGame(1, 1, 1, 0.4, 0.6, False),
            BetGame(2, 1, 2, 0.5, 0.5, False),
            BetGame(3, 1, 3, 0.5, 0.5, False),
            BetGame(4, 1, 4, 0.5, 0.5, False),
        ]
        mock_fetch_bet_games.return_value = list_existing_bet_games
        mock_create_bet_user_game.return_value = None
        mock_update_user_wallet_for_tournament.return_value = None
        mock_fetch_tournament_by_id.return_value = tournament
        # Act
        place_bet_for_game(1, 1, 5, 99.99, 1)
        mock_probability_update.assert_called_once()
        mock_dynamically_adjust_bet_game_odd.assert_called_once()
        mock_create_bet_user_game.assert_called_once_with(1, 1, 5, 99.99, 1, now_date, 0.4)


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_user2(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_fetch_tournament_by_id,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    with patch("deps.bet.bet_functions.datetime") as mock_datetime:
        mock_datetime.now.return_value = now_date
        list_tournament_games: List[TournamentGame] = [
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
            BetGame(1, 1, 1, 0.4, 0.6, False),
            BetGame(2, 1, 2, 0.5, 0.5, False),
            BetGame(3, 1, 3, 0.5, 0.5, False),
            BetGame(4, 1, 4, 0.5, 0.5, False),
        ]
        mock_fetch_bet_games.return_value = list_existing_bet_games
        mock_create_bet_user_game.return_value = None
        mock_update_user_wallet_for_tournament.return_value = None
        mock_fetch_tournament_by_id.return_value = tournament
        # Act
        place_bet_for_game(1, 1, 5, 99.99, 2)
        mock_probability_update.assert_called_once()
        mock_dynamically_adjust_bet_game_odd.assert_called_once()
        mock_create_bet_user_game.assert_called_once_with(1, 1, 5, 99.99, 2, now_date, 0.6)


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.print_error_log.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_user_with_dynamic_adjust_bet_failing(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_print_error_log,
    mock_fetch_tournament_by_id,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    with patch("deps.bet.bet_functions.datetime") as mock_datetime:
        mock_datetime.now.return_value = now_date
        list_tournament_games: List[TournamentGame] = [
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
            BetGame(1, 1, 1, 0.4, 0.6, False),
            BetGame(2, 1, 2, 0.5, 0.5, False),
            BetGame(3, 1, 3, 0.5, 0.5, False),
            BetGame(4, 1, 4, 0.5, 0.5, False),
        ]
        mock_fetch_bet_games.return_value = list_existing_bet_games
        mock_create_bet_user_game.return_value = None
        mock_update_user_wallet_for_tournament.return_value = None
        mock_dynamically_adjust_bet_game_odd.side_effect = Exception("Error")
        mock_fetch_tournament_by_id.return_value = tournament
        # Act
        place_bet_for_game(1, 1, 5, 99.99, 2)
        mock_probability_update.assert_not_called()
        mock_print_error_log.assert_called_once()


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.print_error_log.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_user_with_update_bet_probability_failing(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_print_error_log,
    mock_fetch_tournament_by_id,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    with patch("deps.bet.bet_functions.datetime") as mock_datetime:
        mock_datetime.now.return_value = now_date
        list_tournament_games: List[TournamentGame] = [
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
            BetGame(1, 1, 1, 0.4, 0.6, False),
            BetGame(2, 1, 2, 0.5, 0.5, False),
            BetGame(3, 1, 3, 0.5, 0.5, False),
            BetGame(4, 1, 4, 0.5, 0.5, False),
        ]
        mock_fetch_bet_games.return_value = list_existing_bet_games
        mock_create_bet_user_game.return_value = None
        mock_update_user_wallet_for_tournament.return_value = None
        mock_probability_update.side_effect = Exception("Error")
        mock_fetch_tournament_by_id.return_value = tournament
        # Act
        place_bet_for_game(1, 1, 5, 99.99, 2)
        mock_dynamically_adjust_bet_game_odd.assert_called_once()
        mock_print_error_log.assert_called_once()


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
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
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_fetch_tournament_by_id,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
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
    mock_fetch_tournament_by_id.return_value = tournament
    # Act
    with pytest.raises(ValueError, match=rf"The minimum amount to bet is \${MIN_BET_AMOUNT}"):
        place_bet_for_game(1, 2, 1, 0.99, 1)
    # Assert
    mock_probability_update.assert_not_called()
    mock_dynamically_adjust_bet_game_odd.assert_not_called()


@patch.object(bet_functions, bet_functions.fetch_tournament_by_id.__name__)
@patch.object(bet_functions, bet_functions.dynamically_adjust_bet_game_odd.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_probability.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_create_bet_user_game.__name__)
@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
async def test_placing_bet_on_game_dynamically_change_bet_and_update(
    mock_wallet,
    mock_fetch_tournament,
    mock_fetch_bet_games,
    mock_create_bet_user_game,
    mock_update_user_wallet_for_tournament,
    mock_probability_update,
    mock_dynamically_adjust_bet_game_odd,
    mock_fetch_tournament_by_id,
) -> None:
    """Test the scenario of the user who place a bet on a completed game"""
    # Arrange
    list_tournament_games: List[TournamentGame] = [
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
    mock_fetch_tournament_by_id.return_value = tournament
    # Act
    place_bet_for_game(1, 2, 1, 99.99, 1)
    # Assert
    mock_probability_update.assert_called_once()
    mock_dynamically_adjust_bet_game_odd.assert_called_once()


@patch.object(bet_functions, bet_functions.data_access_get_all_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_ready_for_distribution.__name__)
async def test_generate_msg_bet_leaderboard_no_users(mock_bet_user, mock_get_all_wallet) -> None:
    """
    Test the generate_msg_bet_leaderboard function
    """
    # Arrange
    mock_get_all_wallet.return_value = []
    mock_bet_user.return_value = []
    # Act
    msg = await bet_functions.generate_msg_bet_leaderboard(tournament)
    # Assert
    assert msg == ""


@patch.object(bet_functions, bet_functions.data_access_get_all_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_ready_for_distribution.__name__)
async def test_generate_msg_bet_leaderboard_tournament_no_id(mock_bet_user, mock_get_all_wallet) -> None:
    """
    Test the generate_msg_bet_leaderboard function
    """
    # Arrange
    mock_get_all_wallet.return_value = []
    tournament_no_id = Tournament(
        None, 2, "Tournament 1", fake_date, fake_date, fake_date, 5, 16, "villa", False, False, 0
    )
    mock_bet_user.return_value = []
    # Act
    msg = await bet_functions.generate_msg_bet_leaderboard(tournament_no_id)
    # Assert
    assert msg == ""


@patch.object(bet_functions, bet_functions.data_access_get_all_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_ready_for_distribution.__name__)
async def test_generate_msg_bet_leaderboard_users(mock_bet_user, mock_fetch_user, mock_get_all_wallet) -> None:
    """
    Test the generate_msg_bet_leaderboard function
    """
    # Arrange
    mock_get_all_wallet.return_value = [
        BetUserTournament(1, 2, 100, 10.99),
        BetUserTournament(2, 2, 200, 20.99),
        BetUserTournament(3, 2, 300, 30.99),
    ]
    mock_fetch_user.side_effect = lambda user_id: UserInfo(user_id, f"User {user_id}", None, None, None, "pst", 0)
    mock_bet_user.return_value = []
    # Act
    msg = await bet_functions.generate_msg_bet_leaderboard(tournament)
    # Assert
    assert msg == "1 - User 300 - $30.99\n2 - User 200 - $20.99\n3 - User 100 - $10.99"


@patch.object(bet_functions, bet_functions.data_access_get_all_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_waiting_match_complete.__name__)
async def test_generate_msg_bet_leaderboard_users_with_active_bet(
    mock_bet_user, mock_fetch_user, mock_get_all_wallet
) -> None:
    """
    Test the generate_msg_bet_leaderboard function
    """
    # Arrange
    mock_get_all_wallet.return_value = [
        BetUserTournament(1, 2, 100, 10.99),
        BetUserTournament(2, 2, 200, 20.99),
        BetUserTournament(3, 2, 300, 30.99),
    ]
    mock_fetch_user.side_effect = lambda user_id: UserInfo(user_id, f"User {user_id}", None, None, None, "pst", 0)
    mock_bet_user.return_value = [
        BetUserGame(1, 1, 33, 100, 1000, 10, fake_date, 0.5, False),
    ]
    # Act
    msg = await bet_functions.generate_msg_bet_leaderboard(tournament)
    # Assert
    assert msg == "1 - User 100 - $1010.99\n2 - User 300 - $30.99\n3 - User 200 - $20.99"


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
    if tournament.id is None:
        assert False, "The tournament id should not be None"
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
def test_distribute_gain_on_recent_ended_game_success_scenario_many_winning_bet(
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
    if tournament.id is None:
        assert False, "The tournament id should not be None"
    mock_fetch_tournament_games_by_tournament_id.return_value = [
        TournamentGame(1, tournament.id, 10, 11, 10, "1-4", None, None, None, None)
    ]
    mock_data_access_get_bet_game_ready_to_close.return_value = [BetGame(33, tournament.id, 1, 0.5, 0.5, False)]
    mock_data_access_get_bet_user_game_ready_for_distribution.return_value = [
        BetUserGame(7, 1, 33, 13, 350, 10, fake_date, 0.5, False),
        BetUserGame(8, 1, 33, 14, 150, 10, fake_date, 0.5, False),
    ]
    ledger_entry_1 = BetLedgerEntry(888, 1, 1, 33, 7, 13, 350)
    ledger_entry_2 = BetLedgerEntry(888, 1, 1, 33, 7, 14, 50)
    mock_calculate_gain_lost_for_open_bet_game.side_effect = [[ledger_entry_1], [ledger_entry_2]]
    bet_user_tour_1 = BetUserTournament(62, 1, 13, 1000)
    bet_user_tour_2 = BetUserTournament(63, 1, 14, 1000)
    mock_get_bet_user_wallet_for_tournament.side_effect = [bet_user_tour_1, bet_user_tour_2]

    # Act
    distribute_gain_on_recent_ended_game(1)
    # Assert
    assert mock_get_bet_user_wallet_for_tournament.call_count == 2
    calls = mock_data_access_update_bet_user_tournament.call_args_list
    assert calls == [call(62, 1350), call(63, 1050)]
    assert mock_data_access_insert_bet_ledger_entry.call_count == 2
    calls = mock_data_access_insert_bet_ledger_entry.call_args_list
    assert calls == [call(ledger_entry_1), call(ledger_entry_2)]
    assert mock_data_access_update_bet_user_game_distribution_completed.call_count == 2
    calls = mock_data_access_update_bet_user_game_distribution_completed.call_args_list
    assert calls == [call(7), call(8)]
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
    if tournament.id is None:
        assert False, "The tournament id should not be None"
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


@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_game_ready_to_close.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_ready_for_distribution.__name__)
@patch.object(bet_functions, bet_functions.calculate_gain_lost_for_open_bet_game.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_insert_bet_ledger_entry.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_game_distribution_completed.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_distribution_completed.__name__)
def test_distribute_gain_on_recent_ended_game_without_winner_id(
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
    if tournament.id is None:
        assert False, "The tournament id should not be None"
    mock_fetch_tournament_games_by_tournament_id.return_value = [
        TournamentGame(1, tournament.id, 10, 11, None, "1-4", None, None, None, None)  # no winner id
    ]
    mock_data_access_get_bet_game_ready_to_close.return_value = [BetGame(33, tournament.id, 1, 0.5, 0.5, False)]
    mock_data_access_get_bet_user_game_ready_for_distribution.return_value = [
        BetUserGame(7, 1, 33, 13, 99.98, 11, fake_date, 0.5, False)
    ]

    # Act
    distribute_gain_on_recent_ended_game(1)
    # Assert
    mock_calculate_gain_lost_for_open_bet_game.assert_not_called()
    mock_get_bet_user_wallet_for_tournament.assert_not_called()
    mock_data_access_update_bet_user_tournament.assert_not_called()
    mock_data_access_insert_bet_ledger_entry.assert_not_called()
    mock_data_access_update_bet_user_game_distribution_completed.assert_not_called()  # Cannot be called because the array remains empty
    mock_data_access_update_bet_game_distribution_completed.assert_called_once()  # Always called because we loop outside the for loop


@patch.object(bet_functions, bet_functions.print_error_log.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_game_ready_to_close.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_ready_for_distribution.__name__)
@patch.object(bet_functions, bet_functions.calculate_gain_lost_for_open_bet_game.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_insert_bet_ledger_entry.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_game_distribution_completed.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_distribution_completed.__name__)
def test_distribute_gain_on_recent_ended_game_with_mismatch_bet_game(
    mock_data_access_update_bet_game_distribution_completed,
    mock_data_access_update_bet_user_game_distribution_completed,
    mock_data_access_insert_bet_ledger_entry,
    mock_data_access_update_bet_user_tournament,
    mock_get_bet_user_wallet_for_tournament,
    mock_calculate_gain_lost_for_open_bet_game,
    mock_data_access_get_bet_user_game_ready_for_distribution,
    mock_data_access_get_bet_game_ready_to_close,
    mock_fetch_tournament_games_by_tournament_id,
    mock_print_error_log,
) -> None:
    """
    Unit test for a bet that failed, it should not give the money but still register in the ledger
    and close the game bet + user bet
    """
    # Arrange
    if tournament.id is None:
        assert False, "The tournament id should not be None"
    mock_fetch_tournament_games_by_tournament_id.return_value = [
        TournamentGame(1, tournament.id, 10, 11, None, "1-4", None, None, None, None)  # no winner id
    ]
    mock_data_access_get_bet_game_ready_to_close.return_value = [BetGame(33, tournament.id, 1, 0.5, 0.5, False)]
    mock_data_access_get_bet_user_game_ready_for_distribution.return_value = [
        BetUserGame(7, 1, 33333333, 13, 99.98, 11, fake_date, 0.5, False)  # 33333333 does not match 33
    ]

    # Act
    distribute_gain_on_recent_ended_game(1)
    # Assert
    mock_print_error_log.assert_called_once()
    mock_calculate_gain_lost_for_open_bet_game.assert_not_called()
    mock_get_bet_user_wallet_for_tournament.assert_not_called()
    mock_data_access_update_bet_user_tournament.assert_not_called()
    mock_data_access_insert_bet_ledger_entry.assert_not_called()
    mock_data_access_update_bet_user_game_distribution_completed.assert_not_called()  # Cannot be called because the array remains empty
    mock_data_access_update_bet_game_distribution_completed.assert_called_once()  # Always called because we loop outside the for loop


@patch.object(bet_functions, bet_functions.print_error_log.__name__)
@patch.object(bet_functions, bet_functions.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_game_ready_to_close.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_ready_for_distribution.__name__)
@patch.object(bet_functions, bet_functions.calculate_gain_lost_for_open_bet_game.__name__)
@patch.object(bet_functions, bet_functions.get_bet_user_wallet_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_insert_bet_ledger_entry.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_user_game_distribution_completed.__name__)
@patch.object(bet_functions, bet_functions.data_access_update_bet_game_distribution_completed.__name__)
def test_distribute_gain_on_recent_ended_game_with_mismatch_tournament_game(
    mock_data_access_update_bet_game_distribution_completed,
    mock_data_access_update_bet_user_game_distribution_completed,
    mock_data_access_insert_bet_ledger_entry,
    mock_data_access_update_bet_user_tournament,
    mock_get_bet_user_wallet_for_tournament,
    mock_calculate_gain_lost_for_open_bet_game,
    mock_data_access_get_bet_user_game_ready_for_distribution,
    mock_data_access_get_bet_game_ready_to_close,
    mock_fetch_tournament_games_by_tournament_id,
    mock_print_error_log,
) -> None:
    """
    Unit test for a bet that failed, it should not give the money but still register in the ledger
    and close the game bet + user bet
    """
    # Arrange
    if tournament.id is None:
        assert False, "The tournament id should not be None"
    mock_fetch_tournament_games_by_tournament_id.return_value = [
        TournamentGame(1, tournament.id, 10, 11, None, "1-4", None, None, None, None)  # no winner id
    ]
    mock_data_access_get_bet_game_ready_to_close.return_value = [
        BetGame(33, tournament.id, 1111111, 0.5, 0.5, False)
    ]  # 1111111 does not match 1
    mock_data_access_get_bet_user_game_ready_for_distribution.return_value = [
        BetUserGame(7, 1, 33, 13, 99.98, 11, fake_date, 0.5, False)
    ]

    # Act
    distribute_gain_on_recent_ended_game(1)
    # Assert
    mock_print_error_log.assert_called_once()
    mock_calculate_gain_lost_for_open_bet_game.assert_not_called()
    mock_get_bet_user_wallet_for_tournament.assert_not_called()
    mock_data_access_update_bet_user_tournament.assert_not_called()
    mock_data_access_insert_bet_ledger_entry.assert_not_called()
    mock_data_access_update_bet_user_game_distribution_completed.assert_not_called()  # Cannot be called because the array remains empty
    mock_data_access_update_bet_game_distribution_completed.assert_called_once()  # Always called because we loop outside the for loop


@patch.object(bet_functions, bet_functions.data_access_fetch_user_full_match_info.__name__)
def test_define_odds_between_two_users_users_no_data(mock_data_access_full_match) -> None:
    """
    Test when both users does not have data
    """
    data_user_1: List[UserFullMatchStats] = []
    data_user_2: List[UserFullMatchStats] = []
    mock_data_access_full_match.side_effect = lambda user_id: data_user_1 if user_id == 1 else data_user_2
    result = define_odds_between_two_users(1, 2)
    assert result == (0.5, 0.5)


@patch.object(bet_functions, bet_functions.data_access_fetch_user_full_match_info.__name__)
def test_define_odds_between_two_users_one_user_no_data(mock_data_access_full_match) -> None:
    """
    Test when one of the two users does not have data
    """
    data_user_1 = [
        UserFullMatchStats(
            id=None,
            user_id=1,
            match_uuid="match-uuid-1",
            match_timestamp=fake_date,
            match_duration_ms=60000,
            data_center="US East",
            session_type="ranked",
            map_name="villa",
            is_surrender=False,
            is_forfeit=False,
            is_rollback=False,
            r6_tracker_user_uuid="111-222-333-444",
            ubisoft_username="noSleep_rb6",
            operators="ace,bandit",
            round_played_count=3,
            round_won_count=3,
            round_lost_count=0,
            round_disconnected_count=0,
            kill_count=5,
            death_count=1,
            assist_count=2,
            head_shot_count=2,
            tk_count=0,
            ace_count=0,
            first_kill_count=1,
            first_death_count=1,
            clutches_win_count=0,
            clutches_loss_count=0,
            clutches_win_count_1v1=0,
            clutches_win_count_1v2=0,
            clutches_win_count_1v3=0,
            clutches_win_count_1v4=0,
            clutches_win_count_1v5=0,
            clutches_lost_count_1v1=0,
            clutches_lost_count_1v2=0,
            clutches_lost_count_1v3=0,
            clutches_lost_count_1v4=0,
            clutches_lost_count_1v5=0,
            kill_1_count=1,
            kill_2_count=1,
            kill_3_count=1,
            kill_4_count=1,
            kill_5_count=1,
            rank_points=4567,
            rank_name="Diamond 3",
            points_gained=23,
            rank_previous=4544,
            kd_ratio=0.7,
            head_shot_percentage=0.34,
            kills_per_round=1,
            deaths_per_round=2,
            assists_per_round=1,
            has_win=True,
        )
    ]
    data_user_2: List[UserFullMatchStats] = []
    mock_data_access_full_match.side_effect = lambda user_id: data_user_1 if user_id == 1 else data_user_2
    result = define_odds_between_two_users(1, 2)
    assert result == (0.5, 0.5)


@patch.object(bet_functions, bet_functions.data_access_fetch_user_full_match_info.__name__)
def test_define_odds_between_two_users_both_data(mock_data_access_full_match) -> None:
    """
    Test when both users have data
    """
    data_user_1 = [
        UserFullMatchStats(
            id=None,
            user_id=1,
            match_uuid="match-uuid-1",
            match_timestamp=fake_date,
            match_duration_ms=60000,
            data_center="US East",
            session_type="ranked",
            map_name="villa",
            is_surrender=False,
            is_forfeit=False,
            is_rollback=False,
            r6_tracker_user_uuid="111-222-333-444",
            ubisoft_username="noSleep_rb6",
            operators="ace,bandit",
            round_played_count=3,
            round_won_count=3,
            round_lost_count=0,
            round_disconnected_count=0,
            kill_count=10,
            death_count=1,
            assist_count=2,
            head_shot_count=2,
            tk_count=0,
            ace_count=0,
            first_kill_count=1,
            first_death_count=1,
            clutches_win_count=0,
            clutches_loss_count=0,
            clutches_win_count_1v1=0,
            clutches_win_count_1v2=0,
            clutches_win_count_1v3=0,
            clutches_win_count_1v4=0,
            clutches_win_count_1v5=0,
            clutches_lost_count_1v1=0,
            clutches_lost_count_1v2=0,
            clutches_lost_count_1v3=0,
            clutches_lost_count_1v4=0,
            clutches_lost_count_1v5=0,
            kill_1_count=1,
            kill_2_count=1,
            kill_3_count=1,
            kill_4_count=1,
            kill_5_count=1,
            rank_points=4567,
            rank_name="Diamond 3",
            points_gained=23,
            rank_previous=4544,
            kd_ratio=0.7,
            head_shot_percentage=0.34,
            kills_per_round=1,
            deaths_per_round=2,
            assists_per_round=1,
            has_win=True,
        )
    ]
    data_user_2 = [
        UserFullMatchStats(
            id=None,
            user_id=1,
            match_uuid="match-uuid-1",
            match_timestamp=fake_date,
            match_duration_ms=60000,
            data_center="US East",
            session_type="ranked",
            map_name="villa",
            is_surrender=False,
            is_forfeit=False,
            is_rollback=False,
            r6_tracker_user_uuid="111-222-333-444",
            ubisoft_username="noSleep_rb6",
            operators="ace,bandit",
            round_played_count=3,
            round_won_count=3,
            round_lost_count=0,
            round_disconnected_count=0,
            kill_count=5,
            death_count=1,
            assist_count=2,
            head_shot_count=2,
            tk_count=0,
            ace_count=0,
            first_kill_count=1,
            first_death_count=1,
            clutches_win_count=0,
            clutches_loss_count=0,
            clutches_win_count_1v1=0,
            clutches_win_count_1v2=0,
            clutches_win_count_1v3=0,
            clutches_win_count_1v4=0,
            clutches_win_count_1v5=0,
            clutches_lost_count_1v1=0,
            clutches_lost_count_1v2=0,
            clutches_lost_count_1v3=0,
            clutches_lost_count_1v4=0,
            clutches_lost_count_1v5=0,
            kill_1_count=1,
            kill_2_count=1,
            kill_3_count=1,
            kill_4_count=1,
            kill_5_count=1,
            rank_points=4567,
            rank_name="Diamond 3",
            points_gained=23,
            rank_previous=4544,
            kd_ratio=0.7,
            head_shot_percentage=0.34,
            kills_per_round=1,
            deaths_per_round=2,
            assists_per_round=1,
            has_win=True,
        )
    ]
    mock_data_access_full_match.side_effect = lambda user_id: data_user_1 if user_id == 1 else data_user_2
    result = define_odds_between_two_users(1, 2)
    assert result == (pytest.approx(0.666, abs=1e-3), pytest.approx(0.333, abs=1e-3))


@patch.object(bet_functions, bet_functions.data_access_fetch_users_full_match_info.__name__)
def test_define_odds_between_two_teams_users_no_data(mock_data_access_full_match) -> None:
    """
    Test when both users does not have data
    """
    data_user_1: List[UserFullMatchStats] = []
    data_user_2: List[UserFullMatchStats] = []
    mock_data_access_full_match.side_effect = lambda user_id: data_user_1 if user_id == 1 else data_user_2
    result = define_odds_between_two_teams([1], [2])
    assert result == (0.5, 0.5)


@patch.object(bet_functions, bet_functions.data_access_fetch_users_full_match_info.__name__)
def test_define_odds_between_two_teams_one_team_no_data(mock_data_access_full_match) -> None:
    """
    Test when one of the two users does not have data
    """
    data_user_1 = [
        UserFullMatchStats(
            id=None,
            user_id=1,
            match_uuid="match-uuid-1",
            match_timestamp=fake_date,
            match_duration_ms=60000,
            data_center="US East",
            session_type="ranked",
            map_name="villa",
            is_surrender=False,
            is_forfeit=False,
            is_rollback=False,
            r6_tracker_user_uuid="111-222-333-444",
            ubisoft_username="noSleep_rb6",
            operators="ace,bandit",
            round_played_count=3,
            round_won_count=3,
            round_lost_count=0,
            round_disconnected_count=0,
            kill_count=5,
            death_count=1,
            assist_count=2,
            head_shot_count=2,
            tk_count=0,
            ace_count=0,
            first_kill_count=1,
            first_death_count=1,
            clutches_win_count=0,
            clutches_loss_count=0,
            clutches_win_count_1v1=0,
            clutches_win_count_1v2=0,
            clutches_win_count_1v3=0,
            clutches_win_count_1v4=0,
            clutches_win_count_1v5=0,
            clutches_lost_count_1v1=0,
            clutches_lost_count_1v2=0,
            clutches_lost_count_1v3=0,
            clutches_lost_count_1v4=0,
            clutches_lost_count_1v5=0,
            kill_1_count=1,
            kill_2_count=1,
            kill_3_count=1,
            kill_4_count=1,
            kill_5_count=1,
            rank_points=4567,
            rank_name="Diamond 3",
            points_gained=23,
            rank_previous=4544,
            kd_ratio=0.7,
            head_shot_percentage=0.34,
            kills_per_round=1,
            deaths_per_round=2,
            assists_per_round=1,
            has_win=True,
        )
    ]
    data_user_2: List[UserFullMatchStats] = []
    mock_data_access_full_match.side_effect = lambda user_id: data_user_1 if user_id == 1 else data_user_2
    result = define_odds_between_two_teams([1], [2])
    assert result == (0.5, 0.5)


@patch.object(bet_functions, bet_functions.data_access_fetch_users_full_match_info.__name__)
def test_define_odds_between_two_teams_both_data(mock_data_access_full_match) -> None:
    """
    Test when both users have data
    """
    data_user_1 = [
        UserFullMatchStats(
            id=None,
            user_id=1,
            match_uuid="match-uuid-1",
            match_timestamp=fake_date,
            match_duration_ms=60000,
            data_center="US East",
            session_type="ranked",
            map_name="villa",
            is_surrender=False,
            is_forfeit=False,
            is_rollback=False,
            r6_tracker_user_uuid="111-222-333-444",
            ubisoft_username="noSleep_rb6",
            operators="ace,bandit",
            round_played_count=3,
            round_won_count=3,
            round_lost_count=0,
            round_disconnected_count=0,
            kill_count=10,
            death_count=1,
            assist_count=2,
            head_shot_count=2,
            tk_count=0,
            ace_count=0,
            first_kill_count=1,
            first_death_count=1,
            clutches_win_count=0,
            clutches_loss_count=0,
            clutches_win_count_1v1=0,
            clutches_win_count_1v2=0,
            clutches_win_count_1v3=0,
            clutches_win_count_1v4=0,
            clutches_win_count_1v5=0,
            clutches_lost_count_1v1=0,
            clutches_lost_count_1v2=0,
            clutches_lost_count_1v3=0,
            clutches_lost_count_1v4=0,
            clutches_lost_count_1v5=0,
            kill_1_count=1,
            kill_2_count=1,
            kill_3_count=1,
            kill_4_count=1,
            kill_5_count=1,
            rank_points=4567,
            rank_name="Diamond 3",
            points_gained=23,
            rank_previous=4544,
            kd_ratio=0.7,
            head_shot_percentage=0.34,
            kills_per_round=1,
            deaths_per_round=2,
            assists_per_round=1,
            has_win=True,
        )
    ]
    data_user_2 = [
        UserFullMatchStats(
            id=None,
            user_id=1,
            match_uuid="match-uuid-1",
            match_timestamp=fake_date,
            match_duration_ms=60000,
            data_center="US East",
            session_type="ranked",
            map_name="villa",
            is_surrender=False,
            is_forfeit=False,
            is_rollback=False,
            r6_tracker_user_uuid="111-222-333-444",
            ubisoft_username="noSleep_rb6",
            operators="ace,bandit",
            round_played_count=3,
            round_won_count=3,
            round_lost_count=0,
            round_disconnected_count=0,
            kill_count=5,
            death_count=1,
            assist_count=2,
            head_shot_count=2,
            tk_count=0,
            ace_count=0,
            first_kill_count=1,
            first_death_count=1,
            clutches_win_count=0,
            clutches_loss_count=0,
            clutches_win_count_1v1=0,
            clutches_win_count_1v2=0,
            clutches_win_count_1v3=0,
            clutches_win_count_1v4=0,
            clutches_win_count_1v5=0,
            clutches_lost_count_1v1=0,
            clutches_lost_count_1v2=0,
            clutches_lost_count_1v3=0,
            clutches_lost_count_1v4=0,
            clutches_lost_count_1v5=0,
            kill_1_count=1,
            kill_2_count=1,
            kill_3_count=1,
            kill_4_count=1,
            kill_5_count=1,
            rank_points=4567,
            rank_name="Diamond 3",
            points_gained=23,
            rank_previous=4544,
            kd_ratio=0.7,
            head_shot_percentage=0.34,
            kills_per_round=1,
            deaths_per_round=2,
            assists_per_round=1,
            has_win=True,
        )
    ]
    mock_data_access_full_match.side_effect = lambda user_id: data_user_1 if user_id[0] == 1 else data_user_2
    result = define_odds_between_two_teams([1], [2])
    assert result == (pytest.approx(0.666, abs=1e-3), pytest.approx(0.333, abs=1e-3))


def test_dynamically_adjust_bet_game_odd_bet_game_user1() -> None:
    """
    Test the dynamically_adjust_bet_game_odd function
    """
    # Arrange
    bet_game = BetGame(1, 2, 3, 0.5, 0.5, False)
    # Act
    dynamically_adjust_bet_game_odd(bet_game, True)
    # Assert
    assert bet_game.probability_user_1_win == pytest.approx(0.55, abs=1e-3)
    assert bet_game.probability_user_2_win == pytest.approx(0.45, abs=1e-3)


def test_dynamically_adjust_bet_game_odd_bet_game_user2() -> None:
    """
    Test the dynamically_adjust_bet_game_odd function for user 2
    """
    # Arrange
    bet_game = BetGame(1, 2, 3, 0.5, 0.5, False)
    # Act
    dynamically_adjust_bet_game_odd(bet_game, False)
    # Assert
    assert bet_game.probability_user_1_win == pytest.approx(0.45, abs=1e-3)
    assert bet_game.probability_user_2_win == pytest.approx(0.55, abs=1e-3)


def test_dynamically_adjust_bet_game_odd_bet_game_several_times() -> None:
    """
    Test the dynamically_adjust_bet_game_odd function
    """
    # Arrange
    bet_game = BetGame(1, 2, 3, 0.5, 0.5, False)
    # Act
    dynamically_adjust_bet_game_odd(bet_game, True)
    dynamically_adjust_bet_game_odd(bet_game, True)
    dynamically_adjust_bet_game_odd(bet_game, True)
    dynamically_adjust_bet_game_odd(bet_game, True)
    dynamically_adjust_bet_game_odd(bet_game, True)
    # Assert
    assert bet_game.probability_user_1_win == pytest.approx(0.805, abs=1e-3)
    assert bet_game.probability_user_2_win == pytest.approx(0.194, abs=1e-3)


# def test_define_odds_between_two_users_users_db() -> None:
#     """
#     Test when both users does not have data
#     """
#     result = define_odds_between_two_users(225233803185094656, 318126349648920577)
#     assert result == (0.5, 0.5)


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_ledger_entry_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
async def test_generate_msg_bet_game_no_bet(
    mock_fetch_user_info_by_user_id,
    mock_data_access_get_bet_ledger_entry_for_tournament,
    mock_mock_data_access_get_bet_user_game_for_tournament,
    mock_data_access_fetch_bet_games_by_tournament_id,
) -> None:
    """Test when there is not bet on a game, no message should show up"""
    # Arrange
    tournament_id = 1
    tournament_game_id = 100
    bet_game_id = 200
    user1_id = 500
    user2_id = 501
    tournament_node = TournamentNode(
        tournament_game_id, tournament_id, user1_id, user2_id, None, "5-0", "villa", fake_date
    )
    bet_game1 = BetGame(bet_game_id, tournament_id, tournament_game_id, 0.5, 0.5, True)
    bet_game2 = BetGame(bet_game_id + 1, tournament_id, tournament_game_id + 1, 0.5, 0.5, True)
    bet_game3 = BetGame(bet_game_id + 2, tournament_id, tournament_game_id + 2, 0.5, 0.5, True)
    bet_game4 = BetGame(bet_game_id + 3, tournament_id, tournament_game_id + 3, 0.5, 0.5, True)

    mock_data_access_fetch_bet_games_by_tournament_id.return_value = [bet_game1, bet_game2, bet_game3, bet_game4]
    mock_mock_data_access_get_bet_user_game_for_tournament.return_value = []  # No bet
    mock_data_access_get_bet_ledger_entry_for_tournament.return_value = []  # No entry because no bet
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: UserInfo(
        user_id, f"User {user_id}", None, None, None, "pst", 0
    )
    # Act
    msg = await generate_msg_bet_game(tournament_node)
    # Asert
    assert msg == ""


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_ledger_entry_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.print_error_log.__name__)
async def test_generate_msg_bet_game_no_betgame(
    mock_print_error_log,
    mock_fetch_user_info_by_user_id,
    mock_data_access_get_bet_ledger_entry_for_tournament,
    mock_mock_data_access_get_bet_user_game_for_tournament,
    mock_data_access_fetch_bet_games_by_tournament_id,
) -> None:
    """Test when there is not bet on a game, no message should show up"""
    # Arrange
    tournament_id = 1
    tournament_game_id = 100
    bet_game_id = 200
    user1_id = 500
    user2_id = 501
    tournament_node = TournamentNode(
        tournament_game_id, tournament_id, user1_id, user2_id, None, "5-0", "villa", fake_date
    )
    bet_game1 = BetGame(bet_game_id, tournament_id, tournament_game_id + 1, 0.5, 0.5, True)
    bet_game2 = BetGame(bet_game_id + 1, tournament_id, tournament_game_id + 1, 0.5, 0.5, True)
    bet_game3 = BetGame(bet_game_id + 2, tournament_id, tournament_game_id + 2, 0.5, 0.5, True)
    bet_game4 = BetGame(bet_game_id + 3, tournament_id, tournament_game_id + 3, 0.5, 0.5, True)

    mock_data_access_fetch_bet_games_by_tournament_id.return_value = [bet_game1, bet_game2, bet_game3, bet_game4]
    mock_mock_data_access_get_bet_user_game_for_tournament.return_value = []  # No bet
    mock_data_access_get_bet_ledger_entry_for_tournament.return_value = []  # No entry because no bet
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: UserInfo(
        user_id, f"User {user_id}", None, None, None, "pst", 0
    )
    # Act
    await generate_msg_bet_game(tournament_node)
    # Asert
    mock_print_error_log.assert_called_once()


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_ledger_entry_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
async def test_generate_msg_bet_game_many_bets_same_match(
    mock_fetch_user_info_by_user_id,
    mock_data_access_get_bet_ledger_entry_for_tournament,
    mock_mock_data_access_get_bet_user_game_for_tournament,
    mock_data_access_fetch_bet_games_by_tournament_id,
) -> None:
    """Test when there is not bet on a game, no message should show up"""
    # Arrange
    tournament_id = 1
    tournament_game_id = 100
    bet_game_id = 200
    user1_id = 500
    user2_id = 501
    tournament_node = TournamentNode(tournament_game_id, tournament_id, 8886, 8887, 8887, "5-0", "villa", fake_date)
    bet_game1 = BetGame(bet_game_id, tournament_id, tournament_game_id, 0.5, 0.5, True)
    bet_game2 = BetGame(bet_game_id + 1, tournament_id, tournament_game_id + 1, 0.5, 0.5, True)
    bet_game3 = BetGame(bet_game_id + 2, tournament_id, tournament_game_id + 2, 0.5, 0.5, True)
    bet_game4 = BetGame(bet_game_id + 3, tournament_id, tournament_game_id + 3, 0.5, 0.5, True)

    # Two bets from two differents user on the same 8887 user for the same match (bet_game1.id)
    bet_user_game1 = BetUserGame(1, tournament_id, bet_game1.id, user1_id, 100, 8887, fake_date, 0.5, True)
    bet_user_game2 = BetUserGame(1, tournament_id, bet_game1.id, user2_id, 110, 8887, fake_date, 0.5, True)

    ledger_entry1 = BetLedgerEntry(1, tournament_id, 1, bet_game1.id, bet_user_game1.id, user1_id, 200)
    ledger_entry2 = BetLedgerEntry(1, tournament_id, 1, bet_game1.id, bet_user_game1.id, user2_id, 220)

    mock_data_access_fetch_bet_games_by_tournament_id.return_value = [bet_game1, bet_game2, bet_game3, bet_game4]
    mock_mock_data_access_get_bet_user_game_for_tournament.return_value = [bet_user_game1, bet_user_game2]
    mock_data_access_get_bet_ledger_entry_for_tournament.return_value = [
        ledger_entry1,
        ledger_entry2,
    ]  # No entry because no bet
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: UserInfo(
        user_id, f"User {user_id}", None, None, None, "pst", 0
    )
    # Act
    msg = await generate_msg_bet_game(tournament_node)
    # Asert
    assert (
        msg == "📈 User 500 bet $110.00 and won $200.00 (+81.82%)\n📈 User 501 bet $110.00 and won $220.00 (+100.00%)"
    )


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_ledger_entry_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
async def test_generate_msg_bet_game_many_bets_win_loss_match(
    mock_fetch_user_info_by_user_id,
    mock_data_access_get_bet_ledger_entry_for_tournament,
    mock_mock_data_access_get_bet_user_game_for_tournament,
    mock_data_access_fetch_bet_games_by_tournament_id,
) -> None:
    """Test when there is not bet on a game, no message should show up"""
    # Arrange
    tournament_id = 1
    tournament_game_id = 100
    bet_game_id = 200
    user1_id = 500
    user2_id = 501
    tournament_node = TournamentNode(tournament_game_id, tournament_id, 8886, 8887, 8886, "5-0", "villa", fake_date)
    bet_game1 = BetGame(bet_game_id, tournament_id, tournament_game_id, 0.5, 0.5, True)
    bet_game2 = BetGame(bet_game_id + 1, tournament_id, tournament_game_id + 1, 0.5, 0.5, True)
    bet_game3 = BetGame(bet_game_id + 2, tournament_id, tournament_game_id + 2, 0.5, 0.5, True)
    bet_game4 = BetGame(bet_game_id + 3, tournament_id, tournament_game_id + 3, 0.5, 0.5, True)

    # Two bets from two differents user on each user (win and loss) for the same match (bet_game1.id)
    bet_user_game1 = BetUserGame(1, tournament_id, bet_game1.id, user1_id, 100, 8886, fake_date, 0.5, True)
    bet_user_game2 = BetUserGame(1, tournament_id, bet_game1.id, user2_id, 110, 8887, fake_date, 0.5, True)  # Loss

    ledger_entry1 = BetLedgerEntry(1, tournament_id, 1, bet_game1.id, bet_user_game1.id, user1_id, 200)
    ledger_entry2 = BetLedgerEntry(1, tournament_id, 1, bet_game1.id, bet_user_game1.id, user2_id, 0)

    mock_data_access_fetch_bet_games_by_tournament_id.return_value = [bet_game1, bet_game2, bet_game3, bet_game4]
    mock_mock_data_access_get_bet_user_game_for_tournament.return_value = [bet_user_game1, bet_user_game2]
    mock_data_access_get_bet_ledger_entry_for_tournament.return_value = [
        ledger_entry1,
        ledger_entry2,
    ]
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: UserInfo(
        user_id, f"User {user_id}", None, None, None, "pst", 0
    )
    # Act
    msg = await generate_msg_bet_game(tournament_node)
    # Asert
    assert msg == "📈 User 500 bet $110.00 and won $200.00 (+81.82%)\n📉 User 501 bet $110.00 and loss it all"


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_ledger_entry_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
async def test_generate_msg_bet_game_many_bets_win_loss_match_not_distributed(
    mock_fetch_user_info_by_user_id,
    mock_data_access_get_bet_ledger_entry_for_tournament,
    mock_mock_data_access_get_bet_user_game_for_tournament,
    mock_data_access_fetch_bet_games_by_tournament_id,
) -> None:
    """Test when there is not bet on a game, no message should show up"""
    # Arrange
    tournament_id = 1
    tournament_game_id = 100
    bet_game_id = 200
    user1_id = 500
    user2_id = 501
    tournament_node = TournamentNode(tournament_game_id, tournament_id, 8886, 8887, 8886, "5-0", "villa", fake_date)
    bet_game1 = BetGame(bet_game_id, tournament_id, tournament_game_id, 0.5, 0.5, True)
    bet_game2 = BetGame(bet_game_id + 1, tournament_id, tournament_game_id + 1, 0.5, 0.5, True)
    bet_game3 = BetGame(bet_game_id + 2, tournament_id, tournament_game_id + 2, 0.5, 0.5, True)
    bet_game4 = BetGame(bet_game_id + 3, tournament_id, tournament_game_id + 3, 0.5, 0.5, True)

    # Two bets from two differents user on each user (win and loss) for the same match (bet_game1.id)
    bet_user_game1 = BetUserGame(1, tournament_id, bet_game1.id, user1_id, 100, 8886, fake_date, 0.5, False)
    bet_user_game2 = BetUserGame(1, tournament_id, bet_game1.id, user2_id, 110, 8887, fake_date, 0.5, False)  # Loss

    ledger_entry1 = BetLedgerEntry(1, tournament_id, 1, bet_game1.id, bet_user_game1.id, user1_id, 200)
    ledger_entry2 = BetLedgerEntry(1, tournament_id, 1, bet_game1.id, bet_user_game1.id, user2_id, 0)

    mock_data_access_fetch_bet_games_by_tournament_id.return_value = [bet_game1, bet_game2, bet_game3, bet_game4]
    mock_mock_data_access_get_bet_user_game_for_tournament.return_value = [bet_user_game1, bet_user_game2]
    mock_data_access_get_bet_ledger_entry_for_tournament.return_value = [
        ledger_entry1,
        ledger_entry2,
    ]
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: UserInfo(
        user_id, f"User {user_id}", None, None, None, "pst", 0
    )
    # Act
    msg = await generate_msg_bet_game(tournament_node)
    # Asert
    assert msg == "📈 User 500 bet $110.00 and won $200.00 (+81.82%)\n📉 User 501 bet $110.00 and loss it all"


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_ledger_entry_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
async def test_generate_msg_bet_game_many_bets_inn_other_matches(
    mock_fetch_user_info_by_user_id,
    mock_data_access_get_bet_ledger_entry_for_tournament,
    mock_mock_data_access_get_bet_user_game_for_tournament,
    mock_data_access_fetch_bet_games_by_tournament_id,
) -> None:
    """Test when there is not bet on a game, no message should show up"""
    # Arrange
    tournament_id = 1
    tournament_game_id = 100
    bet_game_id = 200
    user1_id = 500
    user2_id = 501
    tournament_node = TournamentNode(tournament_game_id, tournament_id, 8886, 8887, 8886, "5-0", "villa", fake_date)
    bet_game1 = BetGame(bet_game_id, tournament_id, tournament_game_id, 0.5, 0.5, True)
    bet_game2 = BetGame(bet_game_id + 1, tournament_id, tournament_game_id + 1, 0.5, 0.5, True)
    bet_game3 = BetGame(bet_game_id + 2, tournament_id, tournament_game_id + 2, 0.5, 0.5, True)
    bet_game4 = BetGame(bet_game_id + 3, tournament_id, tournament_game_id + 3, 0.5, 0.5, True)

    # Two bets from two differents user on each user (win and loss) for the same match (bet_game1.id)
    bet_user_game1 = BetUserGame(1, tournament_id, bet_game1.id, user1_id, 100, 8886, fake_date, 0.5, True)
    bet_user_game2 = BetUserGame(1, tournament_id, bet_game1.id, user2_id, 110, 8887, fake_date, 0.5, True)  # Loss
    bet_user_game3 = BetUserGame(
        1, tournament_id, bet_game2.id, user2_id, 110, 8887, fake_date, 0.5, True
    )  # Not from the game finished
    bet_user_game4 = BetUserGame(
        1, tournament_id, bet_game4.id, user2_id, 110, 8887, fake_date, 0.5, True
    )  # Not from the game finished

    ledger_entry1 = BetLedgerEntry(1, tournament_id, 1, bet_game1.id, bet_user_game1.id, user1_id, 200)
    ledger_entry2 = BetLedgerEntry(1, tournament_id, 1, bet_game1.id, bet_user_game1.id, user2_id, 0)
    ledger_entry3 = BetLedgerEntry(
        1, tournament_id, 1, bet_game2.id, bet_user_game1.id, user2_id, 0
    )  # Not from the game
    ledger_entry4 = BetLedgerEntry(
        1, tournament_id, 1, bet_game3.id, bet_user_game1.id, user2_id, 0
    )  # Not from the game

    mock_data_access_fetch_bet_games_by_tournament_id.return_value = [bet_game1, bet_game2, bet_game3, bet_game4]
    mock_mock_data_access_get_bet_user_game_for_tournament.return_value = [
        bet_user_game1,
        bet_user_game2,
        bet_user_game3,
        bet_user_game4,
    ]
    mock_data_access_get_bet_ledger_entry_for_tournament.return_value = [
        ledger_entry1,
        ledger_entry2,
        ledger_entry3,
        ledger_entry4,
    ]
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: UserInfo(
        user_id, f"User {user_id}", None, None, None, "pst", 0
    )
    # Act
    msg = await generate_msg_bet_game(tournament_node)
    # Asert
    assert msg == "📈 User 500 bet $110.00 and won $200.00 (+81.82%)\n📉 User 501 bet $110.00 and loss it all"


@patch.object(bet_functions, bet_functions.data_access_fetch_bet_games_by_tournament_id.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.data_access_get_bet_ledger_entry_for_tournament.__name__)
@patch.object(bet_functions, bet_functions.fetch_user_info_by_user_id.__name__)
@patch.object(bet_functions, bet_functions.print_error_log.__name__)
async def test_generate_msg_bet_game_many_bets_in_mismatch_ledget_user_bet(
    mock_print_error_log,
    mock_fetch_user_info_by_user_id,
    mock_data_access_get_bet_ledger_entry_for_tournament,
    mock_mock_data_access_get_bet_user_game_for_tournament,
    mock_data_access_fetch_bet_games_by_tournament_id,
) -> None:
    """Test when there is not bet on a game, no message should show up"""
    # Arrange
    tournament_id = 1
    tournament_game_id = 100
    bet_game_id = 200
    user1_id = 500
    user2_id = 501
    tournament_node = TournamentNode(tournament_game_id, tournament_id, 8886, 8887, 8886, "5-0", "villa", fake_date)
    bet_game1 = BetGame(bet_game_id, tournament_id, tournament_game_id, 0.5, 0.5, True)
    bet_game2 = BetGame(bet_game_id + 1, tournament_id, tournament_game_id + 1, 0.5, 0.5, True)
    bet_game3 = BetGame(bet_game_id + 2, tournament_id, tournament_game_id + 2, 0.5, 0.5, True)
    bet_game4 = BetGame(bet_game_id + 3, tournament_id, tournament_game_id + 3, 0.5, 0.5, True)

    # Two bets from two differents user on each user (win and loss) for the same match (bet_game1.id)
    bet_user_game1 = BetUserGame(1, tournament_id, bet_game1.id, user1_id, 100, 8886, fake_date, 0.5, True)
    bet_user_game2 = BetUserGame(1, tournament_id, bet_game1.id, user2_id, 110, 8887, fake_date, 0.5, True)  # Loss
    bet_user_game3 = BetUserGame(
        1, tournament_id, bet_game2.id, user2_id, 110, 8887, fake_date, 0.5, True
    )  # Not from the game finished
    bet_user_game4 = BetUserGame(
        1, tournament_id, bet_game4.id, user2_id, 110, 8887, fake_date, 0.5, True
    )  # Not from the game finished

    ledger_entry1 = BetLedgerEntry(1, tournament_id, 1, bet_game1.id, 9999999, user1_id, 200)
    ledger_entry2 = BetLedgerEntry(
        1, tournament_id, 1, bet_game1.id, 9999999, user2_id, 0
    )  # Only this one will call the error log (because 0$)

    mock_data_access_fetch_bet_games_by_tournament_id.return_value = [bet_game1, bet_game2, bet_game3, bet_game4]
    mock_mock_data_access_get_bet_user_game_for_tournament.return_value = [
        bet_user_game1,
        bet_user_game2,
        bet_user_game3,
        bet_user_game4,
    ]
    mock_data_access_get_bet_ledger_entry_for_tournament.return_value = [
        ledger_entry1,
        ledger_entry2,
    ]
    mock_fetch_user_info_by_user_id.side_effect = lambda user_id: UserInfo(
        user_id, f"User {user_id}", None, None, None, "pst", 0
    )
    # Act
    await generate_msg_bet_game(tournament_node)
    # Asert
    assert mock_print_error_log.call_count == 2


def test_calculate_gain_lost_for_open_bet_game_no_winner_id() -> None:
    """
    Calculate the gain with no winner
    """
    # Arrange
    tournament_id = 2
    tournament_game = TournamentGame(
        1, tournament_id, 3, 4, None, "1-4", None, None, None, None
    )  # First None is the winner id
    bet_user_games = [
        BetUserGame(10, tournament_id, 3, 4, 100, 5, fake_date, 0.5, False),
        BetUserGame(20, tournament_id, 3, 4, 100, 5, fake_date, 0.5, False),
    ]
    # Act
    result = calculate_gain_lost_for_open_bet_game(tournament_game, bet_user_games, 0)
    # Assert
    assert len(result) == 0


def test_calculate_gain_lost_for_open_bet_game_filter_out_distributed_bet() -> None:
    """
    Calculate the gain with no winner
    """
    # Arrange
    tournament_id = 2
    tournament_game = TournamentGame(
        1, tournament_id, 3, 4, 3, "1-4", None, None, None, None
    )  # First None is the winner id
    bet_user_games = [
        BetUserGame(10, tournament_id, 3, 4, 100, 5, fake_date, 0.5, False),
        BetUserGame(20, tournament_id, 3, 4, 100, 5, fake_date, 0.5, True),  # Already distributed
        BetUserGame(30, tournament_id, 3, 4, 100, 5, fake_date, 0.5, False),
    ]
    # Act
    result = calculate_gain_lost_for_open_bet_game(tournament_game, bet_user_games, 0)
    # Assert
    assert len(result) == 2


def test_calculate_gain_lost_for_open_bet_game_with_loss_at_zero_win_at_bet_amount() -> None:
    """
    Calculate the gain with no winner
    """
    # Arrange
    tournament_id = 2
    tournament_game = TournamentGame(
        1, tournament_id, 40, 50, 40, "1-4", None, None, None, None
    )  # First None is the winner id
    bet_user_games = [
        BetUserGame(10, tournament_id, 3, 60, 100, 40, fake_date, 0.5, False),  # Winner
        BetUserGame(20, tournament_id, 3, 70, 100, 50, fake_date, 0.5, False),
    ]
    # Act
    result = calculate_gain_lost_for_open_bet_game(tournament_game, bet_user_games, 0)
    # Assert
    assert len(result) == 2
    assert result[0].amount == 200  # 100 initial bet and the odd at 0.5 double
    assert result[1].amount == 0  # Nothing because loss


def test_calculate_gain_lost_for_open_bet_game_with_loss_at_zero_win_at_bet_amount_with_cut_house() -> None:
    """
    Calculate the gain with no winner
    """
    # Arrange
    tournament_id = 2
    tournament_game = TournamentGame(
        1, tournament_id, 40, 50, 40, "1-4", None, None, None, None
    )  # First None is the winner id
    bet_user_games = [
        BetUserGame(10, tournament_id, 3, 60, 100, 40, fake_date, 0.5, False),  # Winner
        BetUserGame(20, tournament_id, 3, 70, 100, 50, fake_date, 0.5, False),
    ]
    # Act
    result = calculate_gain_lost_for_open_bet_game(tournament_game, bet_user_games, 0.1)
    # Assert
    assert len(result) == 2
    assert result[0].amount == pytest.approx(181.818, abs=0.3)  # 100 initial bet and the odd at 0.5 double
    assert result[1].amount == 0  # Nothing because loss


@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_waiting_match_complete.__name__)
async def test_get_bet_user_amount_active_bet_no_bet(
    mock_data_access_get_bet_user_game_waiting_match_complete,
) -> None:
    """Test the user has not bet"""
    # Arrange
    mock_data_access_get_bet_user_game_waiting_match_complete.return_value = []
    # Act
    result = get_bet_user_amount_active_bet(1, 2)
    # Assert
    assert result == 0


@patch.object(bet_functions, bet_functions.data_access_get_bet_user_game_waiting_match_complete.__name__)
async def test_get_bet_user_amount_active_bet_many_ets(
    mock_data_access_get_bet_user_game_waiting_match_complete,
) -> None:
    """Test whe more than one bet is made, should retun the sum"""
    # Arrange
    user_id = 2
    mock_data_access_get_bet_user_game_waiting_match_complete.return_value = [
        BetUserGame(10, 1, 3, user_id, 100, 40, fake_date, 0.5, False),
        BetUserGame(20, 1, 3, user_id, 150, 50, fake_date, 0.5, False),
        BetUserGame(20, 1, 3, 2000, 1000, 50, fake_date, 0.5, False),
    ]
    # Act
    result = get_bet_user_amount_active_bet(1, user_id)
    # Assert
    assert result == 250
