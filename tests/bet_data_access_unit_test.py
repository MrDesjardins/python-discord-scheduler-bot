from datetime import datetime, timezone
from deps.bet.bet_data_class import BetGame, BetLedgerEntry, BetUserGame, BetUserTournament


def test_bet_game_odd_user():
    """Return the odd for user 1"""
    game = BetGame(1, 1, 1, 0.5, 0.5, False)
    result = game.odd_user_1()
    assert result == 2.0
    result = game.odd_user_2()
    assert result == 2.0


def test_bet_game_odd_user_different_odd():
    """Return the odd for user 1"""
    game = BetGame(1, 1, 1, 0.2, 0.8, False)
    result = game.odd_user_1()
    assert result == 5.0
    result = game.odd_user_2()
    assert result == 1.25


def test_bet_game_money_line():
    """Return the odd for user 1"""
    game = BetGame(1, 1, 1, 0.2, 0.8, False)
    result = game.moneyline_odd_user_1()
    assert result == 500
    result = game.moneyline_odd_user_2()
    assert result == -400


def test_bet_game_from_db():
    """
    Test loading using the bet game from the database using a static method
    """
    game = BetGame.from_db_row(
        (
            1,
            2,
            3,
            0.2,
            0.8,
            0,
        )
    )
    assert game.id == 1
    assert game.tournament_id == 2
    assert game.tournament_game_id == 3
    assert game.probability_user_1_win == 0.2
    assert game.probability_user_2_win == 0.8
    assert game.bet_distributed is False


def test_bet_user_game_from_db():
    """
    Test loading using the bet game from the database using a static method
    """
    game = BetUserGame.from_db_row(
        (
            1,
            2,
            3,
            4,
            5,
            6,
            datetime(2021, 1, 2, 12, 0, 0, 0, timezone.utc).isoformat(),
            0.8,
            0,
        )
    )
    assert game.id == 1
    assert game.tournament_id == 2
    assert game.bet_game_id == 3
    assert game.user_id == 4
    assert game.amount == 5
    assert game.user_id_bet_placed == 6
    assert game.time_bet_placed == datetime(2021, 1, 2, 12, 0, 0, 0, timezone.utc)
    assert game.probability_user_win_when_bet_placed == 0.8
    assert game.bet_distributed is False


def test_bet_ledger_game_from_db():
    """
    Test loading using the bet ledget game from the database using a static method
    """
    game = BetLedgerEntry.from_db_row(
        (
            1,
            2,
            3,
            4,
            5,
            6,
            7,
        )
    )
    assert game.id == 1
    assert game.tournament_id == 2
    assert game.tournament_game_id == 3
    assert game.bet_game_id == 4
    assert game.bet_user_game_id == 5
    assert game.user_id == 6
    assert game.amount == 7


def test_bet_user_tournament_from_db():
    """
    Test loading using the bet user tournament from the database using a static method
    """
    game = BetUserTournament.from_db_row(
        (
            1,
            2,
            3,
            4,
        )
    )
    assert game.id == 1
    assert game.tournament_id == 2
    assert game.user_id == 3
    assert game.amount == 4
