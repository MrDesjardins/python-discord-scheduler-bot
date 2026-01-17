"""
Ranking data access functions for analytics.

This module contains all top-N ranking functions that retrieve leaderboard-style
data across various metrics for users in the Discord server. These functions
filter users based on activity from a specified date and return the top N results.

All functions follow the pattern:
- Parameters: from_data (date) - filter users active since this date
              top (int) - number of results to return
- Returns: List of tuples containing user display names and metric values
"""

from datetime import date
from typing import List

from deps.system_database import database_manager


def data_access_fetch_top_matches_played(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the count of match played
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.total_matches_played
    FROM
    user_full_stats_info
    LEFT JOIN user_info ON
        user_info.id = user_full_stats_info.user_id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
    ORDER BY
        user_full_stats_info.total_matches_played DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]


def data_access_fetch_top_ranked_matches_played(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the count of match played
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.rank_match_played
    FROM
    user_full_stats_info
    LEFT JOIN user_info ON
        user_info.id = user_full_stats_info.user_id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
    ORDER BY
        user_full_stats_info.rank_match_played DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    print(query)
    print(from_data.isoformat())
    return [(row[0], row[1]) for row in result]


def data_access_fetch_top_win_rateranked_matches_played(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the count of match played
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.rank_win_percentage
    FROM
    user_full_stats_info
    LEFT JOIN user_info ON
        user_info.id = user_full_stats_info.user_id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
    ORDER BY
        user_full_stats_info.rank_win_percentage DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]


def data_access_fetch_top_team_kill(from_data: date, top: int) -> list[tuple[str, int, int, float]]:
    """
    Get the count of match played
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.total_team_kills,
    user_full_stats_info.total_matches_played,
    user_full_stats_info.total_team_kills * 100.0 / user_full_stats_info.total_matches_played as pct
    FROM
    user_full_stats_info
    LEFT JOIN user_info ON
        user_info.id = user_full_stats_info.user_id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
    ORDER BY
        pct DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1], row[2], row[3]) for row in result]


def data_access_fetch_top_kill_per_match_rank(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the average kill per match in rank
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.rank_kill_per_match
    FROM
    user_full_stats_info
    LEFT JOIN user_info ON
        user_info.id = user_full_stats_info.user_id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
    ORDER BY
        user_full_stats_info.rank_kill_per_match DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]


def data_access_fetch_top_breacher(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the average kill per match in rank
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.attacked_breacher_count
    FROM
    user_full_stats_info
    LEFT JOIN user_info ON
        user_info.id = user_full_stats_info.user_id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
    ORDER BY
        user_full_stats_info.attacked_breacher_count DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]


def data_access_fetch_count_total_wallbangs(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the total count of wall bangs
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.total_wall_bang
    FROM
    user_full_stats_info
    LEFT JOIN user_info ON
        user_info.id = user_full_stats_info.user_id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
    ORDER BY
        user_full_stats_info.total_wall_bang DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]


def data_access_fetch_attacker_fragger_count(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the total count of fragger
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.attacked_fragger_count
    FROM
    user_full_stats_info
    LEFT JOIN user_info ON
        user_info.id = user_full_stats_info.user_id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
    ORDER BY
        user_full_stats_info.attacked_fragger_count DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]


def data_access_fetch_time_played_siege(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the total hours
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.time_played_seconds/3600
    FROM
    user_full_stats_info
    LEFT JOIN user_info ON
        user_info.id = user_full_stats_info.user_id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
    ORDER BY
        user_full_stats_info.time_played_seconds DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]


def data_access_fetch_time_played_siege_on_server(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the total hours played on the server
    """
    query = """
    WITH
    user_sessions AS (
        SELECT
        user_id,
        channel_id,
        guild_id,
        timestamp AS connect_time,
        LEAD (timestamp) OVER (
            PARTITION BY
            user_id,
            channel_id,
            guild_id
            ORDER BY
            timestamp
        ) AS disconnect_time,
        event,
        LEAD (event) OVER (
            PARTITION BY
            user_id,
            channel_id,
            guild_id
            ORDER BY
            timestamp
        ) AS next_event
        FROM
        user_activity
        WHERE
        event in ('connect', 'disconnect')
        AND timestamp > :from_data
    )
    SELECT
    user1_info.display_name AS user1_display_name,
    SUM(
        CAST(
        (
            strftime ('%s', MIN(a.disconnect_time, b.disconnect_time)) - strftime ('%s', MAX(a.connect_time, b.connect_time))
        ) AS INTEGER
        )
    )/3600 AS total_overlap_seconds
    FROM
    user_sessions a
    JOIN user_sessions b ON a.guild_id = b.guild_id
    AND a.user_id < b.user_id -- Avoid duplicate comparisons
    AND a.connect_time < b.disconnect_time
    AND b.connect_time < a.disconnect_time
    AND a.event = 'connect'
    AND a.next_event = 'disconnect'
    AND b.event = 'connect'
    AND b.next_event = 'disconnect'
    LEFT JOIN user_info AS user1_info ON user1_info.id = a.user_id
    WHERE
    a.connect_time IS NOT NULL -- Ensure proper session pairing
    GROUP BY
    a.user_id
    ORDER BY
    total_overlap_seconds DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]


def data_access_fetch_time_duo_partners(from_data: date, top: int) -> list[tuple[str, str, int]]:
    """
    Get the total hours played with someone else
    """
    query = """
    WITH
    user_sessions AS (
        SELECT
        user_id,
        channel_id,
        guild_id,
        timestamp AS connect_time,
        LEAD (timestamp) OVER (
            PARTITION BY
            user_id,
            channel_id,
            guild_id
            ORDER BY
            timestamp
        ) AS disconnect_time,
        event,
        LEAD (event) OVER (
            PARTITION BY
            user_id,
            channel_id,
            guild_id
            ORDER BY
            timestamp
        ) AS next_event
        FROM
        user_activity
        WHERE
        event in ('connect', 'disconnect')
        AND timestamp > :from_data
    )
    SELECT
    user1_info.display_name AS user1_display_name,
    user2_info.display_name AS user2_display_name,
    SUM(
        CAST(
        (
            strftime ('%s', MIN(a.disconnect_time, b.disconnect_time)) - strftime ('%s', MAX(a.connect_time, b.connect_time))
        ) AS INTEGER
        )
    ) / 3600 AS total_overlap_seconds
    FROM
    user_sessions a
    JOIN user_sessions b ON a.guild_id = b.guild_id
    AND a.user_id < b.user_id -- Avoid duplicate comparisons
    AND a.connect_time < b.disconnect_time
    AND b.connect_time < a.disconnect_time
    AND a.event = 'connect'
    AND a.next_event = 'disconnect'
    AND b.event = 'connect'
    AND b.next_event = 'disconnect'
    LEFT JOIN user_info AS user1_info ON user1_info.id = a.user_id
    LEFT JOIN user_info AS user2_info ON user2_info.id = b.user_id
    WHERE
    a.connect_time IS NOT NULL -- Ensure proper session pairing
    GROUP BY
    a.user_id,
    b.user_id
    ORDER BY
    total_overlap_seconds DESC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top},
        )
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in result]
