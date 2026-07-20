"""
Data access for the user_player_value table: the nightly computed
team-balancing value per user per algorithm.
"""

from datetime import datetime
from typing import Dict, List, Optional

from deps.models import PlayerValueAlgorithm, PlayerValueResult
from deps.system_database import database_manager


def data_access_fetch_all_user_ids_with_matches() -> List[int]:
    """All users that have at least one stored ranked match."""
    result = database_manager.get_cursor().execute("SELECT DISTINCT user_id FROM user_full_match_info").fetchall()
    return [row[0] for row in result]


def data_access_upsert_player_value(
    user_id: int,
    algorithm: PlayerValueAlgorithm,
    result: PlayerValueResult,
    computed_at: datetime,
) -> None:
    """Insert or update the computed value of one user for one algorithm."""
    database_manager.get_cursor().execute(
        """
        INSERT INTO user_player_value
            (user_id, algorithm, value, rating, match_count, last_match_timestamp, computed_at)
        VALUES (:user_id, :algorithm, :value, :rating, :match_count, :last_match_timestamp, :computed_at)
        ON CONFLICT(user_id, algorithm) DO UPDATE SET
            value = excluded.value,
            rating = excluded.rating,
            match_count = excluded.match_count,
            last_match_timestamp = excluded.last_match_timestamp,
            computed_at = excluded.computed_at
        """,
        {
            "user_id": user_id,
            "algorithm": algorithm.value,
            "value": result.value,
            "rating": result.rating,
            "match_count": result.match_count,
            "last_match_timestamp": (
                result.last_match_timestamp.isoformat() if result.last_match_timestamp is not None else None
            ),
            "computed_at": computed_at.isoformat(),
        },
    )
    database_manager.get_conn().commit()


def data_access_fetch_player_value(user_id: int, algorithm: PlayerValueAlgorithm) -> Optional[float]:
    """The stored value of one user for one algorithm, None when never computed."""
    row = (
        database_manager.get_cursor()
        .execute(
            "SELECT value FROM user_player_value WHERE user_id = :user_id AND algorithm = :algorithm",
            {"user_id": user_id, "algorithm": algorithm.value},
        )
        .fetchone()
    )
    return row[0] if row is not None else None


def data_access_fetch_player_values_by_algorithm(algorithm: PlayerValueAlgorithm) -> Dict[int, float]:
    """All stored values for one algorithm, keyed by user id."""
    result = (
        database_manager.get_cursor()
        .execute(
            "SELECT user_id, value FROM user_player_value WHERE algorithm = :algorithm",
            {"algorithm": algorithm.value},
        )
        .fetchall()
    )
    return {row[0]: row[1] for row in result}
