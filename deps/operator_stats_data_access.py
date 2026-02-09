"""
Operator Stats Data Access Module

Handles storage and retrieval of per-operator statistics from R6 Tracker API.
"""

from typing import List, Dict, Any
from deps.system_database import database_manager
from deps.log import print_error_log, print_log


def upsert_operator_stats(operator_stats: List[Dict[str, Any]]) -> None:
    """
    Insert or update operator statistics in the database.

    Uses UPSERT (INSERT OR REPLACE) to handle both new and existing records.
    The unique constraint is on (user_id, operator_name, session_type, gamemode).

    Args:
        operator_stats: List of operator stat dictionaries
    """
    if not operator_stats:
        print_log("upsert_operator_stats: No operator stats to insert")
        return

    try:
        with database_manager.data_access_transaction():
            cursor = database_manager.get_cursor()

            for stat in operator_stats:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO operator_stats (
                        user_id,
                        operator_name,
                        session_type,
                        side,
                        gamemode,
                        matches_played,
                        matches_won,
                        matches_lost,
                        win_percentage,
                        time_played,
                        rounds_played,
                        rounds_won,
                        rounds_lost,
                        round_win_pct,
                        kills,
                        deaths,
                        kd_ratio,
                        kills_per_game,
                        kills_per_round,
                        last_updated
                    ) VALUES (
                        :user_id,
                        :operator_name,
                        :session_type,
                        :side,
                        :gamemode,
                        :matches_played,
                        :matches_won,
                        :matches_lost,
                        :win_percentage,
                        :time_played,
                        :rounds_played,
                        :rounds_won,
                        :rounds_lost,
                        :round_win_pct,
                        :kills,
                        :deaths,
                        :kd_ratio,
                        :kills_per_game,
                        :kills_per_round,
                        CURRENT_TIMESTAMP
                    )
                    """,
                    stat,
                )

            print_log(f"upsert_operator_stats: Successfully upserted {len(operator_stats)} operator stats")

    except Exception as e:
        print_error_log(f"upsert_operator_stats: Error inserting operator stats: {e}")
        raise


def fetch_operator_stats_for_user(user_id: int, session_type: str = "ranked") -> List[Dict[str, Any]]:
    """
    Fetch operator statistics for a specific user.

    Args:
        user_id: Discord user ID
        session_type: Type of session (default: "ranked")

    Returns:
        List of operator stat dictionaries
    """
    try:
        query = """
            SELECT
                operator_name,
                session_type,
                side,
                gamemode,
                matches_played,
                matches_won,
                matches_lost,
                win_percentage,
                time_played,
                rounds_played,
                rounds_won,
                rounds_lost,
                round_win_pct,
                kills,
                deaths,
                kd_ratio,
                kills_per_game,
                kills_per_round,
                last_updated
            FROM operator_stats
            WHERE user_id = :user_id AND session_type = :session_type
            ORDER BY matches_played DESC
        """

        cursor = database_manager.get_cursor()
        cursor.execute(query, {"user_id": user_id, "session_type": session_type})

        results = []
        for row in cursor.fetchall():
            results.append(
                {
                    "operator_name": row[0],
                    "session_type": row[1],
                    "side": row[2],
                    "gamemode": row[3],
                    "matches_played": row[4],
                    "matches_won": row[5],
                    "matches_lost": row[6],
                    "win_percentage": row[7],
                    "time_played": row[8],
                    "rounds_played": row[9],
                    "rounds_won": row[10],
                    "rounds_lost": row[11],
                    "round_win_pct": row[12],
                    "kills": row[13],
                    "deaths": row[14],
                    "kd_ratio": row[15],
                    "kills_per_game": row[16],
                    "kills_per_round": row[17],
                    "last_updated": row[18],
                }
            )

        return results

    except Exception as e:
        print_error_log(f"fetch_operator_stats_for_user: Error fetching stats for user {user_id}: {e}")
        return []


def delete_operator_stats_for_user(user_id: int) -> None:
    """
    Delete all operator statistics for a specific user.

    Args:
        user_id: Discord user ID
    """
    try:
        cursor = database_manager.get_cursor()
        cursor.execute("DELETE FROM operator_stats WHERE user_id = :user_id", {"user_id": user_id})
        database_manager.get_conn().commit()
        print_log(f"delete_operator_stats_for_user: Deleted stats for user {user_id}")
    except Exception as e:
        print_error_log(f"delete_operator_stats_for_user: Error deleting stats for user {user_id}: {e}")
        raise
