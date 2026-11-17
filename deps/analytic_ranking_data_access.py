"""
Ranking data access functions for analytics.

This module contains all top-N ranking functions that retrieve leaderboard-style
data across various metrics for users in the Discord server. These functions
filter users based on activity from a specified date and return the top N results.

All functions follow the pattern:
- Parameters: from_data (date) - filter users active since this date
              top (int) - number of results to return
- Returns: List of tuples containing user display names and metric values

Top lists only keep rows whose metric is positive (or whose ranked-match count is
positive for ratios). tracker.gg intermittently returns 0 for lifetime counters
(playstyle/round wins, and occasionally time played), so without this a list fills
up with users who have no value instead of showing the real leaders.
"""

from datetime import date
from typing import List

from deps.system_database import database_manager

# stats.cc publishes operator playstyles on each round. These legacy operator lists remain
# only as a compatibility fallback for rows collected before the stats.cc migration.
BREACH_OPERATOR_NAMES = ("ace", "hibana", "maverick", "sledge", "thermite")
ENTRY_FRAGGER_OPERATOR_NAMES = ("amaru", "ash", "buck", "ying", "zofia")


def _named_operator_params(prefix: str, names: tuple[str, ...]) -> tuple[str, dict[str, str]]:
    """Build a comma-separated placeholder list and its bound values for an IN clause."""
    placeholders = ", ".join(f":{prefix}_{index}" for index in range(len(names)))
    params = {f"{prefix}_{index}": name for index, name in enumerate(names)}
    return placeholders, params


def data_access_fetch_top_matches_played(from_data: date, top: int) -> list[tuple[str, int]]:
    """
    Get the count of match played
    """
    query = """
    SELECT
    user_info.display_name,
    user_full_stats_info.total_matches_played
    FROM
    user_info
    LEFT JOIN user_full_stats_info ON
        user_full_stats_info.user_id = user_info.id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        AND user_full_stats_info.total_matches_played > 0
    ORDER BY
        user_full_stats_info.total_matches_played DESC,
        user_info.display_name ASC
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
    user_info
    LEFT JOIN user_full_stats_info ON
        user_full_stats_info.user_id = user_info.id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        AND user_full_stats_info.rank_match_played > 0
    ORDER BY
        user_full_stats_info.rank_match_played DESC,
        user_info.display_name ASC
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
    user_info
    LEFT JOIN user_full_stats_info ON
        user_full_stats_info.user_id = user_info.id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        AND user_full_stats_info.rank_match_played > 0
    ORDER BY
        user_full_stats_info.rank_win_percentage DESC,
        user_info.display_name ASC
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
    user_full_stats_info.total_team_kills * 100.0 / NULLIF(user_full_stats_info.total_matches_played, 0) as pct
    FROM
    user_info
    LEFT JOIN user_full_stats_info ON
        user_full_stats_info.user_id = user_info.id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        AND user_full_stats_info.total_matches_played > 0
    ORDER BY
        pct DESC,
        user_info.display_name ASC
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
    user_info
    LEFT JOIN user_full_stats_info ON
        user_full_stats_info.user_id = user_info.id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        AND user_full_stats_info.rank_match_played > 0
    ORDER BY
        user_full_stats_info.rank_kill_per_match DESC,
        user_info.display_name ASC
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
    Get the top breaching count.

    Uses tracker.gg's lifetime playstyle counter when it is present. That counter is
    frequently 0 now, so for those rows the number of rounds on breach operators is
    used instead (see BREACH_OPERATOR_NAMES).
    """
    placeholders, operator_params = _named_operator_params("breach_op", BREACH_OPERATOR_NAMES)
    query = f"""
    SELECT
    user_info.display_name,
    COALESCE(
        stats_cc_rounds.total_rounds,
        NULLIF(user_full_stats_info.attacked_breacher_count, 0),
        breach_rounds.total_rounds,
        0
    ) AS breach_count
    FROM
    user_info
    LEFT JOIN user_full_stats_info ON
        user_full_stats_info.user_id = user_info.id
    LEFT JOIN (
        SELECT user_id, SUM(rounds_played) AS total_rounds
        FROM user_match_playstyle_rounds
        WHERE playstyle_key = 'attacker-breacher'
        GROUP BY user_id
    ) AS stats_cc_rounds ON stats_cc_rounds.user_id = user_info.id
    LEFT JOIN (
        SELECT user_id, SUM(rounds_played) AS total_rounds
        FROM operator_stats
        WHERE operator_name IN ({placeholders})
        GROUP BY user_id
    ) AS breach_rounds ON breach_rounds.user_id = user_info.id
    WHERE user_info.id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        AND (
            COALESCE(
                stats_cc_rounds.total_rounds,
                NULLIF(user_full_stats_info.attacked_breacher_count, 0),
                NULLIF(breach_rounds.total_rounds, 0),
                0
            ) > 0
            OR COALESCE(breach_rounds.total_rounds, 0) > 0
        )
    ORDER BY
        breach_count DESC,
        user_info.display_name ASC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top, **operator_params},
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
    user_info
    LEFT JOIN user_full_stats_info ON
        user_full_stats_info.user_id = user_info.id
    WHERE user_full_stats_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        AND user_full_stats_info.total_wall_bang > 0
    ORDER BY
        user_full_stats_info.total_wall_bang DESC,
        user_info.display_name ASC
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
    Get the total count of fragger.

    Uses tracker.gg's lifetime playstyle counter when it is present; otherwise the
    rounds on entry-fragger operators (see ENTRY_FRAGGER_OPERATOR_NAMES).
    """
    placeholders, operator_params = _named_operator_params("fragger_op", ENTRY_FRAGGER_OPERATOR_NAMES)
    query = f"""
    SELECT
    user_info.display_name,
    COALESCE(
        stats_cc_rounds.total_rounds,
        NULLIF(user_full_stats_info.attacked_fragger_count, 0),
        fragger_rounds.total_rounds,
        0
    ) AS fragger_count
    FROM
    user_info
    LEFT JOIN user_full_stats_info ON
        user_full_stats_info.user_id = user_info.id
    LEFT JOIN (
        SELECT user_id, SUM(rounds_played) AS total_rounds
        FROM user_match_playstyle_rounds
        WHERE playstyle_key = 'attacker-entry-fragger'
        GROUP BY user_id
    ) AS stats_cc_rounds ON stats_cc_rounds.user_id = user_info.id
    LEFT JOIN (
        SELECT user_id, SUM(rounds_played) AS total_rounds
        FROM operator_stats
        WHERE operator_name IN ({placeholders})
        GROUP BY user_id
    ) AS fragger_rounds ON fragger_rounds.user_id = user_info.id
    WHERE user_info.id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        AND (
            COALESCE(
                stats_cc_rounds.total_rounds,
                NULLIF(user_full_stats_info.attacked_fragger_count, 0),
                NULLIF(fragger_rounds.total_rounds, 0),
                0
            ) > 0
            OR COALESCE(fragger_rounds.total_rounds, 0) > 0
        )
    ORDER BY
        fragger_count DESC,
        user_info.display_name ASC
    LIMIT :top_result;
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat(), "top_result": top, **operator_params},
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
        AND user_full_stats_info.time_played_seconds > 0
    ORDER BY
        user_full_stats_info.time_played_seconds DESC,
        user_info.display_name ASC
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
