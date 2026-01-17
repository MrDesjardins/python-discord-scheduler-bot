"""
Analytics Leaderboard Data Access Module

This module contains all leaderboard-related data access functions that fetch
community-wide statistics and rankings from the database.

These functions:
- Start with `data_access_fetch_`
- Take `from_data: date` or `from_data: datetime` as the primary parameter
- Return community-wide leaderboard statistics (e.g., TK counts, rollback stats,
  match counts, K/D ratios, best duos/trios, first kill/death rates, etc.)
- Filter users by activity in the specified date range
"""

from datetime import date, datetime
from typing import List, Tuple
from deps.analytic_models import UserOperatorCount
from deps.system_database import database_manager


def data_access_fetch_tk_count_by_user(from_data: datetime) -> list[tuple[int, str, int]]:
    """
    Fetch the TK count for each user
    """
    query = """
        SELECT
            user_full_match_info.user_id,
            user_info.display_name,
            count(user_full_match_info.id) as count_tk
        FROM
            user_full_match_info
        LEFT JOIN user_info
            ON user_info.id = user_full_match_info.user_id
        WHERE
            user_full_match_info.tk_count > 0
            AND user_full_match_info.match_timestamp >= :from_data
            AND user_full_match_info.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
        GROUP BY user_id
        ORDER BY count_tk DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()
    # Convert the result to a dictionary of user_id -> tk_count
    return [(row[0], row[1], row[2]) for row in result]


def data_access_fetch_rollback_positive_count_by_user(from_data: date) -> list[tuple[int, str, int, int]]:
    """
    Fetch the rollback count for each user that gave back points
    """
    query = """
        SELECT
            user_full_match_info.user_id,
            user_info.display_name,
            count(user_full_match_info.id) as count_rollbacks,
            sum(points_gained) as total_points_gained
        FROM
            user_full_match_info
        LEFT JOIN user_info
            ON user_info.id = user_full_match_info.user_id
        WHERE
            user_full_match_info.is_rollback = true
            AND points_gained > 0
            AND user_full_match_info.match_timestamp >= :from_data
            AND user_full_match_info.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
        GROUP BY user_id
        order by count_rollbacks desc, total_points_gained desc;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()
    # Convert the result to a dictionary of user_id -> tk_count
    return [(row[0], row[1], row[2], row[3]) for row in result]


def data_access_fetch_rollback_negative_count_by_user(from_data: date) -> list[tuple[int, str, int, int]]:
    """
    Fetch the rollback count for each user that gave back points
    """
    query = """
        SELECT
            user_full_match_info.user_id,
            user_info.display_name,
            count(user_full_match_info.id) as count_rollbacks,
            sum(points_gained) as total_points_gained
        FROM
            user_full_match_info
        LEFT JOIN user_info
            ON user_info.id = user_full_match_info.user_id
        WHERE
            user_full_match_info.is_rollback = true
            AND points_gained < 0
            AND user_full_match_info.match_timestamp >= :from_data
            AND user_full_match_info.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
        GROUP BY user_id
        order by
            count_rollbacks desc, total_points_gained asc;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()
    # Convert the result to a dictionary of user_id -> tk_count
    return [(row[0], row[1], row[2], row[3]) for row in result]


def data_access_fetch_avg_kill_match(from_data: date) -> list[tuple[int, str, int]]:
    """
    Fetch the average kill for each user
    """
    query = """
    SELECT
        user_id,
        display_name,
        avg_kill
    FROM
    (
        SELECT
            user_full_match_info.user_id,
            user_info.display_name,
            sum(user_full_match_info.kill_count) as sum_kill,
            count(user_full_match_info.id) as count_match,
            sum(user_full_match_info.kill_count) * 1.0 / count(user_full_match_info.id) as avg_kill
        FROM
            user_full_match_info
        LEFT JOIN user_info on user_info.id = user_full_match_info.user_id
        WHERE
            is_rollback = false
            AND match_timestamp >= :from_data
            AND user_full_match_info.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
        GROUP BY user_id
    )
    ORDER BY
        avg_kill desc;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()
    # Convert the result to a dictionary of user_id -> tk_count
    return [(row[0], row[1], row[2]) for row in result]


def data_access_fetch_match_played_count_by_user(from_data: date) -> list[tuple[int, str, int]]:
    """
    Fetch the match count for each user
    """
    query = """
        SELECT
            user_full_match_info.user_id,
            user_info.display_name,
            count(user_full_match_info.id) as count_match
        FROM
            user_full_match_info
        LEFT JOIN user_info
            ON user_info.id = user_full_match_info.user_id
        WHERE
            user_full_match_info.is_rollback = false
            AND user_full_match_info.match_timestamp >= :from_data
            AND user_full_match_info.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
        GROUP BY user_id
        ORDER BY count_match DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()
    # Convert the result to a dictionary of user_id -> tk_count
    return [(row[0], row[1], row[2]) for row in result]


def data_access_fetch_most_voice_time_by_user(from_data: date) -> list[tuple[int, str, int]]:
    """
    Fetch the match count for each user
    """
    query = """
        SELECT
            user_full_match_info.user_id,
            user_info.display_name,
            count(user_full_match_info.id) as count_match
        FROM
            user_full_match_info
        LEFT JOIN user_info
            ON user_info.id = user_full_match_info.user_id
        WHERE
            user_full_match_info.is_rollback = false
            AND user_full_match_info.match_timestamp >= :from_data
            AND user_full_match_info.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
        GROUP BY user_id
        ORDER BY count_match DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()
    # Convert the result to a dictionary of user_id -> tk_count
    return [(row[0], row[1], row[2]) for row in result]


def data_access_fetch_users_operators(from_data: date) -> list[UserOperatorCount]:
    """
    Get a list of user with operator and the count
    """
    query = """
        WITH RECURSIVE
        split_operators AS (
            -- Base case: Split the first operator from the string
            SELECT
            user_full_match_info.user_id,
            user_info.display_name,
            TRIM(
                SUBSTR (
                user_full_match_info.operators,
                0,
                INSTR (user_full_match_info.operators || ',', ',')
                )
            ) AS operator,
            SUBSTR (
                user_full_match_info.operators,
                INSTR (user_full_match_info.operators || ',', ',') + 1
            ) AS remaining_operators
            FROM
            user_full_match_info
            LEFT JOIN user_info ON user_info.id = user_full_match_info.user_id
            WHERE
                match_timestamp >= :from_data
            AND user_full_match_info.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
            UNION ALL
            -- Recursive case: Split the next operator from the remaining string
            SELECT
            user_id,
            display_name,
            TRIM(
                SUBSTR (
                remaining_operators,
                0,
                INSTR (remaining_operators || ',', ',')
                )
            ) AS operator,
            SUBSTR (
                remaining_operators,
                INSTR (remaining_operators || ',', ',') + 1
            ) AS remaining_operators
            FROM
            split_operators
            WHERE
            remaining_operators <> ''
        ),
        operator_counts AS (
            -- Aggregate the results to count occurrences of each operator
            SELECT
            display_name,
            operator,
            COUNT(*) AS operator_count
            FROM
            split_operators
            WHERE
            operator <> ''
            GROUP BY
            display_name,
            operator
        ),
        ranked_operators AS (
            -- Add a row number to rank operators for each person by count
            SELECT
            display_name,
            operator,
            operator_count,
            ROW_NUMBER() OVER (
                PARTITION BY
                display_name
                ORDER BY
                operator_count DESC,
                operator ASC
            ) AS rank
            FROM
            operator_counts
        )
        -- Select only the top 8 operators for each person
        SELECT
        display_name,
        operator,
        operator_count
        FROM
        ranked_operators
        WHERE
        rank <= :top
        ORDER BY
        display_name ASC,
        rank ASC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
                "top": 50,
            },
        )
    ).fetchall()

    # Convert to UserOperatorCount
    return [UserOperatorCount(user=row[0], operator_name=row[1], count=row[2]) for row in result]


def data_access_fetch_kd_by_user(from_data: date) -> list[tuple[int, str, int]]:
    """
    Get all the kills and count for each user
    """
    query = """
   SELECT
    user_id,
    display_name,
    sum_kill * 1.0 / sum_death as kd
    FROM
    (
        SELECT
            user_full_match_info.user_id,
            user_info.display_name,
            sum(user_full_match_info.kill_count) as sum_kill,
            sum(user_full_match_info.death_count) as sum_death
        FROM
            user_full_match_info
            LEFT JOIN user_info on user_info.id = user_full_match_info.user_id
        WHERE
            is_rollback = false
            AND match_timestamp > :from_data
            AND user_full_match_info.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
        GROUP BY user_id
    )
    ORDER BY kd DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()
    # Convert the result to a dictionary of user_id -> tk_count
    return [(row[0], row[1], row[2]) for row in result]


def data_access_fetch_best_duo(from_data: date) -> list[tuple[str, str, int, int, float]]:
    """
    Get the user 1 name, user 2 name, the number of game played, the number of wins and the win %
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
                m1.match_timestamp >= :from_data
            AND m1.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
            AND m2.user_id IN (
                    SELECT DISTINCT
                    user_id
                    from
                    user_activity
                    where
                    timestamp >= :from_data
                )
        )
        SELECT
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
        GROUP BY
            user1,
            user2
        HAVING
            games_played >= 10
        ORDER BY
            win_rate_percentage DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()

    return [(row[0], row[1], row[2], row[3], row[4]) for row in result]


def data_access_fetch_best_trio(from_data: date) -> list[tuple[str, str, str, int, int, float]]:
    """
    Get the user 1 name, user 2 name, user 3 name the number of game played, the number of wins and the win %
    """
    query = """
        WITH
        MatchPairs AS (
            SELECT
            m1.match_uuid,
            m2.match_uuid,
            m3.match_uuid,
            m1.user_id AS user1,
            m2.user_id AS user2,
            m3.user_id AS user3,
            m1.has_win AS has_win
            FROM
                user_full_match_info m1
            JOIN user_full_match_info m2 ON m1.match_uuid = m2.match_uuid
            JOIN user_full_match_info m3 ON m2.match_uuid = m3.match_uuid
            AND m1.user_id < m2.user_id -- Avoid duplicate pairs and self-joins
            AND m2.user_id < m3.user_id -- Avoid duplicate pairs and self-joins
            WHERE
                m1.match_timestamp >= :from_data
            AND m1.user_id IN (
                SELECT DISTINCT
                user_id
                from
                user_activity
                where
                timestamp >= :from_data
            )
            AND m2.user_id IN (
                SELECT DISTINCT
                user_id
                from
                user_activity
                where
                timestamp >= :from_data
            )
            AND m3.user_id IN (
                SELECT DISTINCT
                user_id
                from
                user_activity
                where
                timestamp >= :from_data
            )
        )
        SELECT
            UI_1.display_name AS user1_name,
            UI_2.display_name AS user2_name,
            UI_3.display_name AS user3_name,
            COUNT(*) AS games_played,
            SUM(has_win) AS has_win_sum,
            SUM(has_win) * 1.0 / COUNT(*) AS win_rate_percentage
        FROM
            MatchPairs
        LEFT JOIN user_info AS UI_1 ON UI_1.id = user1
        LEFT JOIN user_info AS UI_2 ON UI_2.id = user2
        LEFT JOIN user_info AS UI_3 ON UI_3.id = user3
        WHERE
            user1 IS NOT NULL
            AND user2 IS NOT NULL
            AND user3 IS NOT NULL
        GROUP BY
            user1,
            user2,
            user3
        HAVING
            games_played >= 10
        ORDER BY
        win_rate_percentage DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()

    return [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in result]


def data_access_fetch_first_death(from_data: date) -> list[tuple[str, int, int, float]]:
    """
    Get the user name, the number of first death, the number of first rounds and the number of first death
    """
    query = """
    SELECT
        user_info.display_name,
        SUM(first_death_count) AS first_death_count_sum,
        SUM(round_played_count) AS round_played_count_sum,
        SUM(first_death_count) * 1.0 / SUM(round_played_count) AS first_death_rate
    FROM user_full_match_info
    LEFT JOIN user_info ON user_info.id = user_id
    WHERE
        match_timestamp >= :from_data
    AND user_full_match_info.user_id IN (
        SELECT DISTINCT
        user_id
        from
        user_activity
        where
        timestamp >= :from_data
    )
    GROUP BY user_id
    HAVING
        round_played_count_sum > 20
    ORDER BY first_death_rate DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()

    return [(row[0], row[1], row[2], row[3]) for row in result]


def data_access_fetch_first_kill(from_data: date) -> list[tuple[str, int, int, float]]:
    """
    Get the user name, the number of first death, the number of first rounds and the number of first death
    """
    query = """
        SELECT
            user_info.display_name,
            SUM(first_kill_count) AS first_kill_count_sum,
            SUM(round_played_count) AS round_played_count_sum,
            SUM(first_kill_count) * 1.0 / SUM(round_played_count) AS first_kill_rate
        FROM
            user_full_match_info
        LEFT JOIN user_info ON user_info.id = user_id
        WHERE
            match_timestamp >= :from_data
        AND user_full_match_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        GROUP BY
            user_id
        HAVING
            round_played_count_sum > 20
        ORDER BY
        first_kill_rate DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()

    return [(row[0], row[1], row[2], row[3]) for row in result]


def data_access_fetch_success_fragging(from_data: date) -> list[tuple[str, float]]:
    """
    Get the user name, the number of first death, the number of first rounds and the number of first death
    """
    query = """
        SELECT
            user_info.display_name,
            SUM(first_death_count) AS first_death_count_sum,
            SUM(first_kill_count) AS first_kill_count_sum,
            SUM(round_played_count) AS round_played_count_sum,
            SUM(first_death_count) * 1.0 / SUM(round_played_count) AS first_death_rate,
            SUM(first_kill_count) * 1.0 / SUM(round_played_count) AS first_kill_rate,
            (
                SUM(first_kill_count) * 1.0 / SUM(round_played_count)
            ) - (
                SUM(first_death_count) * 1.0 / SUM(round_played_count)
            ) AS delta,
            SUM(first_kill_count) * 1.0 / (SUM(first_kill_count) + SUM(first_death_count)) AS first_kill_ratio
        FROM
            user_full_match_info
        LEFT JOIN user_info ON user_info.id = user_id
        WHERE
            match_timestamp >= :from_data
        AND user_full_match_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        GROUP BY
            user_id
        HAVING
            round_played_count_sum > 20
        ORDER BY
            first_kill_ratio DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()

    return [(row[0], row[7]) for row in result]


def data_access_fetch_clutch_win_rate(from_data: date) -> list[tuple[str, int, int, float]]:
    """
    Get the user name, the number of clutch win, the number of clutch played and the clutch win rate
    """
    query = """
        SELECT
            user_info.display_name,
            SUM(clutches_win_count) AS win,
            SUM(clutches_loss_count) AS loss,
            SUM(clutches_win_count) * 1.0 / (SUM(clutches_win_count) + SUM(clutches_loss_count)) AS ratio
        FROM
            user_full_match_info
        LEFT JOIN user_info ON user_info.id = user_id
        WHERE
            match_timestamp >= :from_data
        AND user_full_match_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        GROUP BY
            user_id
        ORDER BY
            ratio DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()

    return [(row[0], row[1], row[2], row[3]) for row in result]


def data_access_fetch_ace_4k_3k(from_data: date) -> list[tuple[str, int, int, int, int]]:
    """
    Get the user name, 5k, 4k, 3k count
    """
    query = """
        SELECT
            user_info.display_name,
            SUM(kill_5_count) AS ace,
            SUM(kill_4_count) AS kill4,
            SUM(kill_3_count) AS kill3,
            SUM(kill_5_count) + SUM(kill_4_count) + SUM(kill_3_count) as total
        FROM
            user_full_match_info
        LEFT JOIN user_info ON user_info.id = user_id
        WHERE
            match_timestamp >= :from_data
        AND user_full_match_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= :from_data
        )
        GROUP BY
            user_id
        ORDER BY
            total DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()

    return [(row[0], row[1], row[2], row[3], row[4]) for row in result]


def data_access_fetch_clutch_round_rate(from_data: date) -> list[tuple[str, int, int, int, float]]:
    """
    Get the amount of time someone is in a clutch situation
    """
    query = """
        SELECT
            user_info.display_name,
            SUM(clutches_win_count) AS win,
            SUM(clutches_loss_count) AS loss,
            SUM(round_played_count) AS round_played_count_sum,
            (
                SUM(clutches_win_count) + SUM(clutches_loss_count) * 1.0
            ) / SUM(round_played_count) AS ratio
        FROM
            user_full_match_info
        LEFT JOIN user_info ON user_info.id = user_id
        WHERE
            match_timestamp >= '2025-02-10'
        AND user_full_match_info.user_id IN (
            SELECT DISTINCT
            user_id
            from
            user_activity
            where
            timestamp >= '2025-02-10'
        )
        GROUP BY
            user_id
        ORDER BY
            ratio DESC;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()

    return [(row[0], row[1], row[2], row[3], row[4]) for row in result]


def data_access_fetch_win_rate_server(
    from_data: date, to_data: date
) -> list[tuple[str, int, int, float, float, float]]:
    """
    Get the rate of playing in circus, the win rate in circus, the win rate outside circus, the win rate in circus
    """
    query = """
        WITH
        user_sessions AS (
            SELECT
            ua1.user_id,
            ua1.timestamp AS session_start,
            MIN(ua2.timestamp) AS session_end
            FROM
            user_activity ua1
            LEFT JOIN user_activity ua2 ON ua1.user_id = ua2.user_id
            AND ua1.timestamp < ua2.timestamp
            AND ua2.event = 'disconnect'
            WHERE
            ua1.event = 'connect'
            and ua1.timestamp >= :from_data
            and ua1.timestamp <= :to_data
            and ua2.timestamp >= :from_data
            and ua2.timestamp <= :to_data
            GROUP BY
            ua1.id
        ),
        matches_in_session AS (
            SELECT
            ufm.user_id,
            COUNT(ufm.id) AS matches_during_activity,
            SUM(
                CASE
                WHEN ufm.has_win = 1 THEN 1
                ELSE 0
                END
            ) AS wins_during_activity
            FROM
            user_full_match_info ufm
            JOIN user_sessions us ON ufm.user_id = us.user_id
            AND ufm.match_timestamp BETWEEN us.session_start AND us.session_end
            and ufm.match_timestamp >= :from_data
            and ufm.match_timestamp <= :to_data
            GROUP BY
            ufm.user_id
        ),
        matches_outside_session AS (
            SELECT
                ufm.user_id,
                COUNT(ufm.id) AS matches_outside_activity,
                SUM(CASE WHEN ufm.has_win = 1 THEN 1 ELSE 0 END) AS wins_outside_activity
            FROM user_full_match_info ufm
            WHERE NOT EXISTS (
                SELECT 1
                FROM user_sessions us
                WHERE ufm.user_id = us.user_id
                AND ufm.match_timestamp BETWEEN us.session_start AND us.session_end
            )
            and ufm.match_timestamp >= :from_data
            and ufm.match_timestamp <= :to_data
            GROUP BY ufm.user_id
        ),
        total_matches AS (
            SELECT
            user_id,
            COUNT(id) AS total_matches
            FROM
            user_full_match_info
            WHERE
            user_full_match_info.match_timestamp >= :from_data
            and user_full_match_info.match_timestamp <= :to_data
            GROUP BY
            user_id
        )
        SELECT
        user_info.display_name,
        total_matches AS total_rank_matches,
        COALESCE(mis.matches_during_activity, 0) AS matches_count_in_circus,
        -- COALESCE(mis.wins_during_activity, 0) AS wins_during_activity,
        CASE
            WHEN COALESCE(mis.matches_during_activity, 0) = 0 THEN 0
            ELSE ROUND(
            (mis.wins_during_activity * 100.0) / mis.matches_during_activity,
            2
            )
        END AS win_rate_circus,
        --COALESCE(mos.matches_outside_activity, 0) AS matches_outside_activity,
        --COALESCE(mos.wins_outside_activity, 0) AS wins_outside_activity,
        CASE
            WHEN COALESCE(mos.matches_outside_activity, 0) = 0 THEN 0
            ELSE ROUND(
            (mos.wins_outside_activity * 100.0) / mos.matches_outside_activity,
            2
            )
        END AS win_rate_not_circus,
        CASE
            WHEN COALESCE(tm.total_matches, 0) = 0 THEN 0
            ELSE ROUND(
            (COALESCE(mis.matches_during_activity, 0) * 100.0) / tm.total_matches,
            2
            )
        END AS rate_play_in_circus
        FROM
        total_matches tm
        LEFT JOIN matches_in_session mis ON tm.user_id = mis.user_id
        LEFT JOIN matches_outside_session mos ON tm.user_id = mos.user_id
        LEFT JOIN user_info ON tm.user_id = user_info.id
        ORDER BY
        rate_play_in_circus DESC
        LIMIT 60 OFFSET 0;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
                "to_data": to_data.isoformat(),
            },
        )
    ).fetchall()
    return [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in result]


def data_access_fetch_best_worse_map(from_data: date) -> list[tuple[str, str, int, str, int]]:
    """
    Get the best and worse map for each user
    """
    query = """
        WITH
        match_stats AS (
            SELECT
            user_info.display_name,
            user_full_match_info.map_name,
            SUM(
                CASE
                WHEN user_full_match_info.has_win = TRUE THEN 1
                ELSE 0
                END
            ) AS wins,
            SUM(
                CASE
                WHEN user_full_match_info.has_win = FALSE THEN 1
                ELSE 0
                END
            ) AS losses
            FROM
                user_full_match_info
            INNER JOIN user_info ON user_info.id = user_id
            WHERE
                match_timestamp >= :from_data
            AND user_full_match_info.user_id IN (
                SELECT DISTINCT
                user_id
                from
                user_activity
                where
                timestamp >= :from_data
            )
            GROUP BY
            user_info.display_name,
            user_full_match_info.map_name
        ),
        max_wins AS (
            SELECT
            display_name,
            MAX(wins) AS max_wins
            FROM
            match_stats
            GROUP BY
            display_name
        ),
        max_losses AS (
            SELECT
            display_name,
            MAX(losses) AS max_losses
            FROM
            match_stats
            GROUP BY
            display_name
        ),
        most_won_maps AS (
            SELECT
            ms.display_name,
            GROUP_CONCAT (ms.map_name, ', ') AS most_won_maps,
            mw.max_wins AS wins
            FROM
            match_stats ms
            JOIN max_wins mw ON ms.display_name = mw.display_name
            AND ms.wins = mw.max_wins
            GROUP BY
            ms.display_name
        ),
        most_lost_maps AS (
            SELECT
            ms.display_name,
            GROUP_CONCAT (ms.map_name, ', ') AS most_lost_maps,
            ml.max_losses AS losses
            FROM
            match_stats ms
            JOIN max_losses ml ON ms.display_name = ml.display_name
            AND ms.losses = ml.max_losses
            GROUP BY
            ms.display_name
        )
        SELECT
            mw.display_name,
            mw.most_won_maps,
            mw.wins,
            ml.most_lost_maps,
            ml.losses
        FROM
            most_won_maps mw
        LEFT JOIN most_lost_maps ml ON mw.display_name = ml.display_name
        WHERE
            mw.wins > 1
            AND ml.losses > 1;
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {
                "from_data": from_data.isoformat(),
            },
        )
    ).fetchall()
    return [(row[0], row[1], row[2], row[3], row[4]) for row in result]


def data_access_fetch_unique_user_per_day(from_data: date) -> List[tuple[str, int]]:
    """
    Count the number of unique person who played per day
    """
    query = """
    SELECT DATE(timestamp) AS day, COUNT(DISTINCT user_id) as unique_users
    FROM user_activity
    WHERE event = 'connect'
    AND timestamp > :from_data
    GROUP BY day
    ORDER BY day
    """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"from_data": from_data.isoformat()},
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]
