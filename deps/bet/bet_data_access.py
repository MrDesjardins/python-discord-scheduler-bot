"""
Logic that interact with the database
"""

from datetime import datetime
from typing import List, Optional

from deps.bet.bet_data_class import BetGame, BetLedgerEntry, BetUserGame, BetUserTournament
from deps.system_database import database_manager

SELECT_BET_USER_GAME = """
    bet_user_game.id, 
    bet_user_game.tournament_id, 
    bet_user_game.bet_game_id, 
    bet_user_game.user_id, 
    bet_user_game.amount, 
    bet_user_game.user_id_bet_placed, 
    bet_user_game.time_bet_placed, 
    bet_user_game.probability_user_win_when_bet_placed,
    bet_user_game.bet_distributed
"""

SELECT_BET_USER_TOURNAMENT = """
    bet_user_tournament.id, 
    bet_user_tournament.tournament_id, 
    bet_user_tournament.user_id, 
    bet_user_tournament.amount 
"""

SELECT_BET_GAME = """
    bet_game.id, 
    bet_game.tournament_id, 
    bet_game.tournament_game_id, 
    bet_game.probability_user_1_win, 
    bet_game.probability_user_2_win,
    bet_game.bet_distributed
"""
SELECT_LEDGER = """
    bet_ledger_entry.id,
    bet_ledger_entry.tournament_id, 
    bet_ledger_entry.tournament_game_id, 
    bet_ledger_entry.bet_game_id, 
    bet_ledger_entry.bet_user_game_id, 
    bet_ledger_entry.user_id, 
    bet_ledger_entry.amount
"""


def delete_all_bet_tables() -> None:
    """
    Delete all tables
    """
    # print(f"Deleting all tables from database {database_manager.get_database_name()}")
    database_manager.get_cursor().execute("DROP TABLE bet_user_tournament")
    database_manager.get_cursor().execute("DROP TABLE bet_game")
    database_manager.get_cursor().execute("DROP TABLE bet_user_game")
    database_manager.get_cursor().execute("DROP TABLE bet_ledger_entry")
    database_manager.get_conn().commit()
    database_manager.init_database()


def data_access_get_all_wallet_for_tournament(tournament_id: int) -> List[BetUserTournament]:
    """
    Get the wallet of a user for a specific tournament
    """
    query = f"""
        SELECT 
        {SELECT_BET_USER_TOURNAMENT}
        FROM bet_user_tournament
        WHERE tournament_id = :tournament_id 
        """
    database_manager.get_cursor().execute(
        query,
        {"tournament_id": tournament_id},
    )
    rows = database_manager.get_cursor().fetchall()
    return [BetUserTournament.from_db_row(row) for row in rows]


def data_access_get_bet_user_wallet_for_tournament(tournament_id: int, user_id: int) -> BetUserTournament:
    """
    Get the wallet of a user for a specific tournament
    """
    query = f"""
        SELECT 
        {SELECT_BET_USER_TOURNAMENT}
        FROM bet_user_tournament
        WHERE tournament_id = :tournament_id 
        AND user_id = :user_id 
        """
    database_manager.get_cursor().execute(
        query,
        {"tournament_id": tournament_id, "user_id": user_id},
    )
    row = database_manager.get_cursor().fetchone()
    if row is None:
        return None
    return BetUserTournament.from_db_row(row)


def data_access_update_bet_user_tournament(
    bet_user_tournament_id: int, amount: float, auto_commit: bool = False
) -> None:
    """
    Update the wallet of a user for a specific tournament
    """
    database_manager.get_cursor().execute(
        """
        UPDATE bet_user_tournament 
        SET amount = :amount 
        WHERE id = :bet_user_tournament_id
        """,
        {"bet_user_tournament_id": bet_user_tournament_id, "amount": amount},
    )
    if auto_commit:
        database_manager.get_conn().commit()


def data_access_create_bet_user_wallet_for_tournament(tournament_id: int, user_id: int, initial_amount: float) -> None:
    """
    Create a wallet for a user for a specific tournament
    """
    database_manager.get_cursor().execute(
        """
        INSERT INTO bet_user_tournament (tournament_id, user_id, amount) 
        VALUES (:tournament_id, :user_id, :money)
        """,
        {"tournament_id": tournament_id, "user_id": user_id, "money": initial_amount},
    )
    database_manager.get_conn().commit()


def data_access_fetch_bet_games_by_tournament_id(tournament_id: int) -> List[BetGame]:
    """
    Fetch all the bet games for a tournament
    """
    query = f"""
        SELECT 
        {SELECT_BET_GAME}
        FROM bet_game
        WHERE tournament_id = :tournament_id
        """
    database_manager.get_cursor().execute(
        query,
        {"tournament_id": tournament_id},
    )
    rows = database_manager.get_cursor().fetchall()
    return [BetGame.from_db_row(row) for row in rows]


def data_access_create_bet_game(
    tournament_id: int, tournament_game_id: int, probability_user_1_win: float, probability_user_2_win: float
) -> None:
    """
    Create a bet game
    """
    database_manager.get_cursor().execute(
        """
        INSERT INTO bet_game(
          tournament_id, 
          tournament_game_id, 
          probability_user_1_win, 
          probability_user_2_win,
          bet_distributed
        ) 
        VALUES (
          :tournament_id,
          :tournament_game_id,
          :probability_user_1_win,
          :probability_user_2_win,
          false
        )
        """,
        {
            "tournament_id": tournament_id,
            "tournament_game_id": tournament_game_id,
            "probability_user_1_win": probability_user_1_win,
            "probability_user_2_win": probability_user_2_win,
        },
    )
    database_manager.get_conn().commit()


def data_access_fetch_bet_user_game_by_tournament_id(tournament_id: int) -> List[BetUserGame]:
    """
    Fetch all the bet games for a tournament
    """
    query = f"""
        SELECT 
        {SELECT_BET_USER_GAME}
        FROM bet_user_game
        WHERE tournament_id = :tournament_id
        """
    database_manager.get_cursor().execute(
        query,
        {"tournament_id": tournament_id},
    )
    rows = database_manager.get_cursor().fetchall()
    return [BetUserGame.from_db_row(row) for row in rows]


def data_access_create_bet_user_game(
    tournament_id: int,
    bet_game_id: int,
    user_id: int,
    amount: float,
    user_id_bet_placed: int,
    time_bet_placed: datetime,
    probability: float,
) -> None:
    """
    Create a user bet
    """
    database_manager.get_cursor().execute(
        """
            INSERT INTO bet_user_game (
              tournament_id,
              bet_game_id,
              user_id,
              amount,
              user_id_bet_placed,
              time_bet_placed,
              probability_user_win_when_bet_placed,
              bet_distributed
              )
            VALUES (
              :tournament_id,
              :bet_game_id,
              :user_id,
              :amount,
              :user_id_bet_placed,
              :time_bet_placed,
              :probability_user_win_when_bet_placed,
              false
            )
            """,
        {
            "tournament_id": tournament_id,
            "bet_game_id": bet_game_id,
            "user_id": user_id,
            "amount": amount,
            "user_id_bet_placed": user_id_bet_placed,
            "time_bet_placed": time_bet_placed,
            "probability_user_win_when_bet_placed": probability,
        },
    )
    database_manager.get_conn().commit()


def data_access_get_bet_user_game_for_tournament(tournament_id: int) -> List[BetUserGame]:
    """
    Get all the bet games user for a tournament_id
    """
    query = f"""
        SELECT 
        {SELECT_BET_USER_GAME}
        FROM bet_user_game
        INNER JOIN bet_game 
          ON bet_user_game.bet_game_id = bet_game.id
        INNER JOIN tournament_game
          ON bet_game.tournament_game_id = tournament_game.id
        WHERE
          bet_user_game.tournament_id = :tournament_id
        """
    database_manager.get_cursor().execute(
        query,
        {"tournament_id": tournament_id},
    )
    rows = database_manager.get_cursor().fetchall()
    return [BetUserGame.from_db_row(row) for row in rows]


def data_access_get_bet_user_game_ready_for_distribution(tournament_id: int) -> List[BetUserGame]:
    """
    Get all the bet games user that are ready for distribution
    """
    query = f"""
        SELECT 
        {SELECT_BET_USER_GAME}
        FROM bet_user_game
        INNER JOIN bet_game 
          ON bet_user_game.bet_game_id = bet_game.id
        INNER JOIN tournament_game
          ON bet_game.tournament_game_id = tournament_game.id
          AND tournament_game.user_winner_id IS NOT NULL
        WHERE
          bet_user_game.tournament_id = :tournament_id
        AND 
          bet_user_game.bet_distributed = false
        """
    database_manager.get_cursor().execute(
        query,
        {"tournament_id": tournament_id},
    )
    rows = database_manager.get_cursor().fetchall()
    return [BetUserGame.from_db_row(row) for row in rows]


def data_access_get_bet_game_ready_to_close(tournament_id: int) -> List[BetGame]:
    """
    Get all the bet games that are ready for distribution
    """
    query = f"""
        SELECT 
        {SELECT_BET_GAME}
        FROM bet_game
        INNER JOIN tournament_game
          ON bet_game.tournament_game_id = tournament_game.id
          AND tournament_game.user_winner_id IS NOT NULL
        WHERE
          bet_game.tournament_id = :tournament_id
        AND 
          bet_game.bet_distributed = false
        """
    database_manager.get_cursor().execute(
        query,
        {"tournament_id": tournament_id},
    )
    rows = database_manager.get_cursor().fetchall()
    return [BetGame.from_db_row(row) for row in rows]


def data_access_insert_bet_ledger_entry(entry: BetLedgerEntry, auto_commit: bool = False) -> None:
    """Insert in the table the bet ledger entry"""
    database_manager.get_cursor().execute(
        """
        INSERT INTO bet_ledger_entry (
          tournament_id,
          tournament_game_id,
          bet_game_id,
          bet_user_game_id,
          user_id,
          amount
        )
        VALUES (
          :tournament_id,
          :tournament_game_id,
          :bet_game_id,
          :bet_user_game_id,
          :user_id,
          :amount
        )
        """,
        {
            "tournament_id": entry.tournament_id,
            "tournament_game_id": entry.tournament_game_id,
            "bet_game_id": entry.bet_game_id,
            "bet_user_game_id": entry.bet_user_game_id,
            "user_id": entry.user_id,
            "amount": entry.amount,
        },
    )
    if auto_commit:
        database_manager.get_conn().commit()


def data_access_update_bet_user_game_distribution_completed(bet_id: int, auto_commit: bool = False) -> None:
    """Update the bet user game to be distributed"""
    database_manager.get_cursor().execute(
        """
        UPDATE bet_user_game
        SET bet_distributed = true
        WHERE id = :bet_id
        """,
        {"bet_id": bet_id},
    )
    if auto_commit:
        database_manager.get_conn().commit()


def data_access_update_bet_game_distribution_completed(bet_id: int, auto_commit: bool = False) -> None:
    """Update the bet game to be distributed"""
    database_manager.get_cursor().execute(
        """
        UPDATE bet_game
        SET bet_distributed = true
        WHERE id = :bet_id
        """,
        {"bet_id": bet_id},
    )
    if auto_commit:
        database_manager.get_conn().commit()


def data_access_get_bet_ledger_entry_for_tournament(tournament_id: int) -> List[BetLedgerEntry]:
    """Get the list of entry for a specific tournament"""
    query = f"""
        SELECT
            {SELECT_LEDGER}
        FROM bet_ledger_entry
        WHERE tournament_id = :tournament_id
    """
    database_manager.get_cursor().execute(
        query,
        {"tournament_id": tournament_id},
    )
    rows = database_manager.get_cursor().fetchall()
    return [BetLedgerEntry.from_db_row(row) for row in rows]


def data_access_update_bet_game_probability(bet_game: BetGame, auto_commit: bool = False) -> None:
    """Update the bet game probability"""
    database_manager.get_cursor().execute(
        """
        UPDATE bet_game
        SET probability_user_1_win = :p1,
        probability_user_2_win = :p2
        WHERE id = :bet_id
        """,
        {"bet_id": bet_game.id, "p1": bet_game.probability_user_1_win, "p2": bet_game.probability_user_2_win},
    )
    if auto_commit:
        database_manager.get_conn().commit()
