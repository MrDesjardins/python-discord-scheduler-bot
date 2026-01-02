"""
Data access functions for custom match features.
"""

from datetime import datetime
from typing import List
from deps.custom_match.custom_match_data_class import MapSuggestion
from deps.system_database import database_manager
from deps.models import Reason


def data_access_subscribe_custom_game(user_id: int, guild_id: int, date_subscribe: datetime) -> Reason:
    """Subscribe a user to custom games in the specified guild."""
    query = """
        INSERT OR IGNORE INTO custom_game_user_subscription (user_id, guild_id, follow_datetime)
        VALUES (:user_id, :guild_id, :follow_datetime);
        """
    database_manager.get_cursor().execute(
        query, {"user_id": user_id, "guild_id": guild_id, "follow_datetime": date_subscribe}
    )
    database_manager.get_conn().commit()
    return Reason(True)


def data_access_unsubscribe_custom_game(user_id: int, guild_id: int) -> Reason:
    """Unsubscribe a user from custom games in the specified guild."""
    query = """
        DELETE FROM custom_game_user_subscription
        WHERE user_id = :user_id AND guild_id = :guild_id;
        """
    database_manager.get_cursor().execute(query, {"user_id": user_id, "guild_id": guild_id})
    database_manager.get_conn().commit()
    return Reason(True)


def data_access_fetch_user_subscription_for_guild(guild_id: int) -> list[int]:
    """Fetch all user IDs subscribed to custom games in the specified guild."""

    query = """
        SELECT user_id FROM custom_game_user_subscription
        WHERE guild_id = :guild_id;
        """
    result = database_manager.get_cursor().execute(query, {"guild_id": guild_id}).fetchall()
    return [row[0] for row in result]


def data_access_fetch_best_maps_first(user_ids: List[int]) -> List[MapSuggestion]:
    """Fetch the map that is least played by the given user IDs."""
    if not user_ids:
        return []

    placeholders = ",".join(["?"] * len(user_ids))
    query = f"""
SELECT
    map_name,
    ROUND(
        SUM(CASE WHEN has_win = 1 THEN 1 ELSE 0 END) * 1.0
        / COUNT(*),
        3
    ) AS win_rate
FROM user_full_match_info
WHERE map_name <> 'Unknown'
AND user_id IN ({placeholders})
GROUP BY map_name
HAVING COUNT(*) >= 20
ORDER BY win_rate DESC
LIMIT 5
;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            user_ids,
        )
    ).fetchall()

    # Convert to UserOperatorCount
    return [MapSuggestion.from_db_row(row) for row in result]


def data_access_fetch_worse_maps_first(user_ids: List[int]) -> List[MapSuggestion]:
    """Fetch the map that is least played by the given user IDs."""
    if not user_ids:
        return []

    placeholders = ",".join(["?"] * len(user_ids))
    query = f"""
SELECT
    map_name,
    ROUND(
        SUM(CASE WHEN has_win = 0 THEN 1 ELSE 0 END) * 1.0
        / COUNT(*),
        3
    ) AS loss_rate
FROM user_full_match_info
WHERE map_name <> 'Unknown'
AND user_id IN ({placeholders})
GROUP BY map_name
HAVING COUNT(*) >= 20
ORDER BY loss_rate DESC
LIMIT 5
;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            user_ids,
        )
    ).fetchall()

    # Convert to UserOperatorCount
    return [MapSuggestion.from_db_row(row) for row in result]


def data_access_fetch_less_played_maps_first(user_ids: List[int]) -> List[MapSuggestion]:
    """Fetch the map that is least played by the given user IDs."""
    if not user_ids:
        return []
    placeholders = ",".join(["?"] * len(user_ids))
    query = f"""
        SELECT
            map_name,
            COUNT(*) AS play_count
        FROM user_full_match_info
        WHERE user_id IN ({placeholders})
        AND map_name <> 'Unknown'
        GROUP BY map_name
        ORDER BY play_count ASC
        LIMIT 5;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            user_ids,
        )
    ).fetchall()

    # Convert to UserOperatorCount
    return [MapSuggestion.from_db_row(row) for row in result]


def data_access_fetch_all_maps(user_ids: List[int]) -> List[MapSuggestion]:
    """Fetch the map that is least played by the given user IDs."""
    if not user_ids:
        return []

    placeholders = ",".join(["?"] * len(user_ids))
    query = f"""
        SELECT DISTINCT
            map_name,
            COUNT(*) AS play_count
        FROM user_full_match_info
        WHERE user_id IN ({placeholders})
        AND map_name <> 'Unknown'
        GROUP BY map_name
        ORDER BY play_count ASC
        LIMIT 50;
        """
    result = (database_manager.get_cursor().execute(query, user_ids)).fetchall()

    # Convert to UserOperatorCount
    return [MapSuggestion.from_db_row(row) for row in result]
