"""
Module containing individual user profile data access functions.

This module provides functions to query individual user statistics and metrics
from the database, including MMR data, activity timestamps, play time, and
partnership statistics.
"""

from datetime import datetime
from typing import List, Tuple

from deps.system_database import database_manager


def data_access_fetch_user_max_current_mmr(user_id: int) -> int | None:
    """
    Get the max mmr for a user
    """
    query = """
    SELECT
        rank_points AS max_mmr
    FROM
        user_full_match_info
    WHERE
        user_id = :user_id
    ORDER BY
        match_timestamp DESC
    LIMIT 1;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id},
        )
    ).fetchone()
    if result and result[0] is not None:
        return int(result[0])
    return None


def data_access_fetch_user_max_mmr(user_id: int) -> int | None:
    """
    Get the max mmr for a user
    """
    query = """
    SELECT
        max_mmr
    FROM
        user_info
    WHERE
        id = :user_id;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id},
        )
    ).fetchone()
    if result and result[0] is not None:
        return int(result[0])
    return None


def data_access_fetch_first_activity(user_id: int) -> datetime | None:
    """
    Get the first activity timestamp for a user
    """
    query = """
    SELECT
        MIN(timestamp) AS first_activity
    FROM
        user_activity
    WHERE
        user_id = :user_id;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id},
        )
    ).fetchone()
    if result and result[0] is not None:
        return datetime.fromisoformat(result[0])
    return None


def data_access_fetch_last_activity(user_id: int) -> datetime | None:
    """
    Get the last activity timestamp for a user
    """
    query = """
    SELECT
        MAX(timestamp) AS last_activity
    FROM
        user_activity
    WHERE
        user_id = :user_id;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id},
        )
    ).fetchone()
    if result and result[0] is not None:
        return datetime.fromisoformat(result[0])
    return None


def data_access_fetch_total_hours(user_id: int) -> int:
    """
    Get the total hours played on the server
    """
    query = """
WITH user_event_sequence AS (
    SELECT
        id,
        user_id,
        event,
        timestamp,
        LAG(id) OVER (PARTITION BY user_id ORDER BY timestamp) AS previous_id,
        LAG(event) OVER (PARTITION BY user_id ORDER BY timestamp) AS previous_event,
        LAG(timestamp) OVER (PARTITION BY user_id ORDER BY timestamp) AS previous_timestamp
    FROM
        user_activity
    WHERE user_id = :user_id
),
valid_pairs AS (
    SELECT
        previous_id,
        id,
        user_id,
        previous_event,
        event,
        previous_timestamp,
        timestamp,
        (strftime('%s', timestamp) - strftime('%s', previous_timestamp)) AS seconds_between_events
    FROM
        user_event_sequence
    WHERE
        event = 'disconnect'
        AND previous_event = 'connect'
        AND previous_timestamp IS NOT NULL -- Ensures valid pairs
),
aggregated_time AS (
    SELECT
        user_id,
        SUM(seconds_between_events) AS total_time
    FROM
        valid_pairs
    GROUP BY
        user_id
)
SELECT
    ua.display_name,
    at.total_time / 3600 AS total_hours
FROM
    aggregated_time at
LEFT JOIN
    user_info ua
    ON at.user_id = ua.id
WHERE
    at.total_time > 0
ORDER BY
    at.total_time DESC;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id},
        )
    ).fetchone()
    if result and result[1] is not None:
        return int(result[1])
    return 0


def data_access_fetch_top_game_played_for_user(user_id: int, top: int = 5) -> list[tuple[str, int]]:
    """
    Get the top games played for a user
    """
    query = """
WITH
  MatchPairs AS (
    SELECT
      m1.match_uuid,
      m2.match_uuid,
      m1.user_id AS user1,
      m2.user_id AS user2
    FROM
      user_full_match_info m1
      JOIN user_full_match_info m2 ON m1.match_uuid = m2.match_uuid
      AND m1.user_id < m2.user_id -- Avoid duplicate pairs and self-joins
    WHERE
      m1.match_timestamp >= '2025-01-15'
  )
SELECT
  UI_1.id AS user1_id,
  UI_2.id AS user2_id,
  UI_1.display_name AS user1_name,
  UI_2.display_name AS user2_name,
  COUNT(*) AS games_played
FROM
  MatchPairs
  LEFT JOIN user_info AS UI_1 ON UI_1.id = user1
  LEFT JOIN user_info AS UI_2 ON UI_2.id = user2
WHERE
  user1 IS NOT NULL
  AND user2 IS NOT NULL
  AND (user1 = :user_id OR user2 = :user_id)
GROUP BY
  user1,
  user2
HAVING
  games_played >= 10
ORDER BY
  games_played DESC
LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id, "top_result": top},
        )
    ).fetchall()
    return [(row[2] if row[0] != user_id else row[3], row[4]) for row in result]


def data_access_fetch_top_winning_partners_for_user(user_id: int, top: int = 5) -> list[tuple[str, int, float]]:
    """
    Get the top winning partners for a user
    """
    query = """
WITH
  MatchPairs AS (
    SELECT
      m1.match_uuid,
      m2.match_uuid,
      m1.user_id AS user1,
      m2.user_id AS user2,
      m1.has_win AS has_win
    FROM
      user_full_match_info m1
      JOIN user_full_match_info m2 ON m1.match_uuid = m2.match_uuid
      AND m1.user_id < m2.user_id -- Avoid duplicate pairs and self-joins
    WHERE
      m1.match_timestamp >= '2025-01-15'
  )
SELECT
  UI_1.id AS user1_id,
  UI_2.id AS user2_id,
  UI_1.display_name AS user1_name,
  UI_2.display_name AS user2_name,
  COUNT(*) AS games_played,
  SUM(has_win) AS has_win_sum,
  SUM(has_win) * 1.0 / COUNT(*) AS win_rate_percentage
FROM
  MatchPairs
  LEFT JOIN user_info AS UI_1 ON UI_1.id = user1
  LEFT JOIN user_info AS UI_2 ON UI_2.id = user2
WHERE
  user1 IS NOT NULL
  AND user2 IS NOT NULL
  AND (user1 = :user_id OR user2 = :user_id)
GROUP BY
  user1,
  user2
HAVING
  games_played >= 10
ORDER BY
  win_rate_percentage DESC
LIMIT :top_result;
"""
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id, "top_result": top},
        )
    ).fetchall()
    return [(row[2] if row[0] != user_id else row[3], row[5], row[6]) for row in result]
