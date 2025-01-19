"""
Logic that interact with the database
"""

from datetime import datetime
from typing import List, Optional

from deps.bet.bet_data_class import BetGame, BetUserTournament
from deps.system_database import database_manager


def delete_all_tables() -> None:
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


def get_user_wallet_for_tournament(tournament_id: int, user_id: int) -> Optional[BetUserTournament]:
    """
    Get the wallet of a user for a specific tournament
    """
    database_manager.get_cursor().execute(
        """
        SELECT id, tournament_id, user_id, amount 
        FROM bet_user_tournament 
        WHERE tournament_id = :tournament_id 
        AND user_id = :user_id 
        """,
        {"tournament_id": tournament_id, "user_id": user_id},
    )
    row = database_manager.get_cursor().fetchone()
    if row is None:
        return None
    return BetUserTournament.from_db_row(row)


def update_user_wallet_for_tournament(wallet_id: int, amount: float) -> None:
    """
    Update the wallet of a user for a specific tournament
    """
    database_manager.get_cursor().execute(
        """
        UPDATE bet_user_tournament 
        SET amount = :amount 
        WHERE wallet_id = :wallet_id
        """,
        {"wallet_id": wallet_id, "amount": amount},
    )
    database_manager.get_conn().commit()


def create_user_wallet_for_tournament(tournament_id: int, user_id: int, initial_amount: float) -> None:
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


def fetch_bet_games_by_tournament_id(tournament_id: int) -> List[BetGame]:
    """
    Fetch all the bet games for a tournament
    """
    database_manager.get_cursor().execute(
        """
        SELECT 
          id, 
          tournament_id, 
          game_id, 
          probability_user_1_win, 
          probability_user_2_win
        FROM bet_game
        WHERE tournament_id = :tournament_id
        """,
        {"tournament_id": tournament_id},
    )
    rows = database_manager.get_cursor().fetchall()
    return [BetGame.from_db_row(row) for row in rows]


def create_bet_game(
    tournament_id: int, game_id: int, probability_user_1_win: float, probability_user_2_win: float
) -> None:
    """
    Create a bet game
    """
    database_manager.get_cursor().execute(
        """
        INSERT INTO bet_game(
          tournament_id, 
          game_id, 
          probability_user_1_win, 
          probability_user_2_win
        ) 
        VALUES (
          :tournament_id,
          :game_id,
          :probability_user_1_win,
          :probability_user_2_win
        )
        """,
        {
            "tournament_id": tournament_id,
            "game_id": game_id,
            "probability_user_1_win": probability_user_1_win,
            "probability_user_2_win": probability_user_2_win,
        },
    )
    database_manager.get_conn().commit()


def fetch_bet_user_game_by_tournament_id(tournament_id: int) -> List[BetUserTournament]:
    """
    Fetch all the bet games for a tournament
    """
    database_manager.get_cursor().execute(
        """
        SELECT 
          id, 
          tournament_id, 
          bet_game_id, 
          user_id, 
          amount, 
          user_id_bet_placed, 
          time_bet_placed, 
          probability_user_win_when_bet_placed
        FROM bet_user_game
        WHERE tournament_id = :tournament_id
        """,
        {"tournament_id": tournament_id},
    )
    rows = database_manager.get_cursor().fetchall()
    return [BetUserTournament.from_db_row(row) for row in rows]


def create_bet_user_game(
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
              probability_user_win_when_bet_placed)
            VALUES (
              :tournament_id,
              :bet_game_id,
              :user_id,
              :amount,
              :user_id_bet_placed,
              :time_bet_placed,
              :probability_user_win_when_bet_placed
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
