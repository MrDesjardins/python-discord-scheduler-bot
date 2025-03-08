"""
Module to gather user activity data and calculate the time spent together
"""

from dataclasses import asdict
from datetime import datetime, date, timedelta
import json
from typing import Dict, List, Optional, Union
from deps.analytic_models import UserOperatorCount
from deps.data_access_data_class import UserInfo, UserActivity
from deps.system_database import database_manager
from deps.analytic_functions import compute_users_weights
from deps.cache import (
    get_cache,
)
from deps.functions_date import ensure_utc
from deps.models import UserFullMatchStats
from deps.log import print_error_log, print_log

KEY_USER_INFO = "user_info"
KEY_TOURNAMENT_GUILD = "tournament_guild"
KEY_TOURNAMENT_GAMES = "tournament_games"

USER_ACTIVITY_SELECT_FIELD = "user_id, channel_id, event, timestamp, guild_id"
USER_INFO_SELECT_FIELD = (
    "id, display_name, ubisoft_username_max, ubisoft_username_active, r6_tracker_active_id, time_zone"
)

SELECT_USER_FULL_MATCH_INFO = """
    user_full_match_info.id,
    user_full_match_info.match_uuid,
    user_full_match_info.user_id,
    user_full_match_info.match_timestamp,
    user_full_match_info.match_duration_ms,
    user_full_match_info.data_center,
    user_full_match_info.session_type,
    user_full_match_info.map_name,
    user_full_match_info.is_surrender,
    user_full_match_info.is_forfeit,
    user_full_match_info.is_rollback,
    user_full_match_info.r6_tracker_user_uuid,
    user_full_match_info.ubisoft_username,
    user_full_match_info.operators,
    user_full_match_info.round_played_count,
    user_full_match_info.round_won_count,
    user_full_match_info.round_lost_count,
    user_full_match_info.round_disconnected_count,
    user_full_match_info.kill_count,
    user_full_match_info.death_count,
    user_full_match_info.assist_count,
    user_full_match_info.head_shot_count,
    user_full_match_info.tk_count,
    user_full_match_info.ace_count,
    user_full_match_info.first_kill_count,
    user_full_match_info.first_death_count,
    user_full_match_info.clutches_win_count,
    user_full_match_info.clutches_loss_count,
    user_full_match_info.clutches_win_count_1v1,
    user_full_match_info.clutches_win_count_1v2,
    user_full_match_info.clutches_win_count_1v3,
    user_full_match_info.clutches_win_count_1v4,
    user_full_match_info.clutches_win_count_1v5,
    user_full_match_info.clutches_lost_count_1v1,
    user_full_match_info.clutches_lost_count_1v2,
    user_full_match_info.clutches_lost_count_1v3,
    user_full_match_info.clutches_lost_count_1v4,
    user_full_match_info.clutches_lost_count_1v5,
    user_full_match_info.kill_1_count,
    user_full_match_info.kill_2_count,
    user_full_match_info.kill_3_count,
    user_full_match_info.kill_4_count,
    user_full_match_info.kill_5_count,
    user_full_match_info.rank_points,
    user_full_match_info.rank_name,
    user_full_match_info.points_gained,
    user_full_match_info.rank_previous,
    user_full_match_info.kd_ratio,
    user_full_match_info.head_shot_percentage,
    user_full_match_info.kills_per_round,
    user_full_match_info.deaths_per_round,
    user_full_match_info.assists_per_round,
    user_full_match_info.has_win
"""


def delete_all_user_weights():
    """
    Erase everything to start the calculation from scratch
    """
    database_manager.get_cursor().execute("DELETE FROM user_weights")
    database_manager.get_conn().commit()


def insert_user_activity(
    user_id: int, user_display_name: str, channel_id: int, guild_id: int, event: str, time: datetime
) -> None:
    """
    Log a user activity in the database
    """
    time = ensure_utc(time)
    database_manager.get_cursor().execute(
        """
    INSERT INTO user_info(id, display_name)
      VALUES(:user_id, :user_display_name)
      ON CONFLICT(id) DO UPDATE SET
        display_name = :user_display_name
      WHERE id = :user_id;
    """,
        {"user_id": user_id, "user_display_name": user_display_name},
    )
    database_manager.get_cursor().execute(
        """
    INSERT INTO user_activity (user_id, channel_id, guild_id, event, timestamp)
    VALUES (:user_id, :channel_id, :guild_id, :event, :time)
    """,
        {"user_id": user_id, "channel_id": channel_id, "guild_id": guild_id, "event": event, "time": time.isoformat()},
    )
    database_manager.get_conn().commit()


def fetch_user_info() -> Dict[int, UserInfo]:
    """
    Fetch all user names from the user_info table
    """
    database_manager.get_cursor().execute(f"SELECT {USER_INFO_SELECT_FIELD} FROM user_info")
    return {row[0]: UserInfo(*row) for row in database_manager.get_cursor().fetchall()}


async def fetch_user_info_by_user_id(user_id: int) -> Optional[UserInfo]:
    """
    Fetch a user name from the user_info table
    """

    def fetch_from_db():
        result = (
            database_manager.get_cursor()
            .execute(
                f"SELECT {USER_INFO_SELECT_FIELD} FROM user_info WHERE id = ?",
                (user_id,),
            )
            .fetchone()
        )
        if result is not None:
            return UserInfo(*result)
        else:
            # Handle the case where no user was found, e.g., return None or raise an exception
            return None  # Or raise an appropriate exception

    return await get_cache(True, f"{KEY_USER_INFO}:{user_id}", fetch_from_db)


def fetch_user_info_by_user_id_list(user_id_list: list[int]) -> List[Optional[UserInfo]]:
    """
    Return the list of user info for the given list of user ids.
    If not user info is found, return None
    """
    list_ids = ",".join("?" for _ in user_id_list)
    database_manager.get_cursor().execute(
        f"""
        SELECT {USER_INFO_SELECT_FIELD} 
        FROM user_info WHERE id IN ({list_ids})
        """,
        user_id_list,  # Pass user_id_list as the parameter values for the ? placeholders
    )
    # Fetch all results and store them in a dictionary by user id
    result = {user.id: user for user in (UserInfo(*row) for row in database_manager.get_cursor().fetchall())}

    result_with_none: list[Union[None, UserInfo]] = []
    for user_id in user_id_list:
        user_info = result.get(user_id)
        if user_info is None:
            result_with_none.append(None)
        else:
            result_with_none.append(user_info)
    return result_with_none


def fetch_all_user_activities2(from_date: date) -> list[tuple[str, str, int]]:
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    query = """  
            WITH
            user_sessions AS (
                SELECT
                ua1.user_id,
                ua1.channel_id,
                ua1.guild_id,
                ua1.timestamp AS connect_time,
                ua2.timestamp AS disconnect_time
                FROM
                user_activity ua1
                JOIN user_activity ua2 ON ua1.user_id = ua2.user_id
                AND ua1.channel_id = ua2.channel_id
                AND ua1.guild_id = ua2.guild_id
                AND ua1.event = 'connect'
                AND ua2.event = 'disconnect'
                AND ua2.timestamp > ua1.timestamp
                AND ua1.timestamp > :date_from
                AND ua2.timestamp > :date_from
                WHERE
                NOT EXISTS (
                    SELECT
                    1
                    FROM
                    user_activity ua3
                    WHERE
                    ua3.user_id = ua1.user_id
                    AND ua3.channel_id = ua1.channel_id
                    AND ua3.guild_id = ua1.guild_id
                    AND ua3.event = 'connect'
                    AND ua3.timestamp > ua1.timestamp
                    AND ua3.timestamp < ua2.timestamp
                    AND ua1.timestamp > :date_from
                    AND ua2.timestamp > :date_from
                    AND ua3.timestamp > :date_from
                )
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
            ) AS total_overlap_seconds
            FROM
            user_sessions a
            JOIN user_sessions b ON a.guild_id = b.guild_id
            AND a.user_id < b.user_id -- Avoid duplicate comparisons
            AND a.connect_time < b.disconnect_time
            AND b.connect_time < a.disconnect_time
            LEFT JOIN user_info AS user1_info on user1_info.id = a.user_id
            LEFT JOIN user_info AS user2_info on user2_info.id = b.user_id
            GROUP BY
            a.user_id,
            b.user_id
            ORDER BY total_overlap_seconds DESC;
        """
    result = (
        database_manager.get_cursor()
        .execute(
            query,
            {
                "date_from": from_date.isoformat(),
            },
        )
        .fetchall()
    )

    return [(row[0], row[1], row[2]) for row in result]


def fetch_all_user_activities(from_day: int = 3600, to_day: int = 0) -> list[UserActivity]:
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    from_date = datetime.now() - timedelta(days=from_day)
    to_date = datetime.now() - timedelta(days=to_day)
    # from_date = datetime(2025, 2, 5, 0, 0, 0)
    # to_date = datetime(2025, 2, 20, 23, 59, 59)
    query = f"""
        SELECT {USER_ACTIVITY_SELECT_FIELD}
        FROM user_activity
        WHERE timestamp >= :from_date AND timestamp <= :to_date
        ORDER BY timestamp ASC
        """
    database_manager.get_cursor().execute(
        query,
        {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        },
    )
    # Convert the result to a list of UserActivity objects
    return [UserActivity(*row) for row in database_manager.get_cursor().fetchall()]


def fetch_user_activities(user_id: int, from_day: int = 3600, to_day: int = 0) -> list[UserActivity]:
    """
    Fetch all connect and disconnect events from the user_activity table for a specific user
    """
    database_manager.get_cursor().execute(
        f"""
        SELECT {USER_ACTIVITY_SELECT_FIELD}
        FROM user_activity
        WHERE timestamp >= datetime('now', ? ) AND timestamp <= datetime('now', ?)
        AND user_id = ?
        ORDER BY timestamp ASC
        """,
        (f"-{from_day} days", f"-{to_day} days", user_id),
    )
    # Convert the result to a list of UserActivity objects
    return [UserActivity(*row) for row in database_manager.get_cursor().fetchall()]


def fetch_user_infos_with_activity(from_utc: datetime, to_utc: datetime) -> list[int]:
    """
    Fetch user ids that had at least one activity between the two timestamps
    """
    # Ensure the input datetimes are timezone-aware and in UTC
    from_utc = ensure_utc(from_utc)
    to_utc = ensure_utc(to_utc)

    database_manager.get_cursor().execute(
        f"""
        SELECT {USER_ACTIVITY_SELECT_FIELD}
        FROM user_activity
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp ASC
        """,
        (from_utc.isoformat(), to_utc.isoformat()),
    )
    # Convert the result to a list of UserActivity objects
    activities = [UserActivity(*row) for row in database_manager.get_cursor().fetchall()]
    # Extract unique user ids
    return list(set([activity.user_id for activity in activities]))


def calculate_time_spent_from_db(from_day: int, to_day: int) -> None:
    """
    Function to calculate time spent together and insert weights
    """
    delete_all_user_weights()

    # Fetch all user activity data, ordered by room and timestamp
    activity_data = fetch_all_user_activities(from_day, to_day)

    user_weights = compute_users_weights(activity_data)

    # Insert accumulated weights into the user_weights table
    for (user_a, user_b, channel_id), total_weight in user_weights.items():
        database_manager.get_cursor().execute(
            """
        INSERT INTO user_weights (user_a, user_b, channel_id, weight)
        VALUES (?, ?, ?, ?)
        """,
            (user_a, user_b, channel_id, total_weight),
        )
    database_manager.get_conn().commit()


def data_access_set_usertimezone(user_id: int, timezone: str) -> None:
    """
    Set the timezone for a user
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET time_zone = :timezone
      WHERE id = :user_id
    """,
        {"user_id": user_id, "timezone": timezone},
    )
    database_manager.get_conn().commit()


def data_access_set_ubisoft_username_max(user_id: int, username: str) -> None:
    """
    Set the timezone for a user
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET ubisoft_username_max = :name
      WHERE id = :user_id
    """,
        {"user_id": user_id, "name": username},
    )
    database_manager.get_conn().commit()


def data_access_set_ubisoft_username_active(user_id: int, username: str) -> None:
    """
    Set the active user name and reset the R6 Tracker ID which will be set back from the active
    user name once the user play
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET ubisoft_username_active = :name,
      r6_tracker_active_id = NULL
      WHERE id = :user_id
    """,
        {"user_id": user_id, "name": username},
    )
    database_manager.get_conn().commit()


def data_access_set_r6_tracker_id(user_id: int, r6_tracker_active_id: str) -> None:
    """
    Set the r6_tracker_active_id for a user
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET r6_tracker_active_id = :r6_tracker_active_id
      WHERE id = :user_id
    """,
        {"user_id": user_id, "r6_tracker_active_id": r6_tracker_active_id},
    )
    database_manager.get_conn().commit()


def upsert_user_info(
    user_id: int,
    display_name: str,
    user_max_account_name: str,
    user_active_account: str,
    r6_tracker_active_id: Union[str, None],
    user_timezone: str,
) -> None:
    """
    Insert or Update the user info
    """
    database_manager.get_cursor().execute(
        """
    INSERT INTO user_info(id, display_name, ubisoft_username_max, ubisoft_username_active, r6_tracker_active_id, time_zone)
      VALUES(:user_id, :user_display_name, :user_max_account_name, :user_active_account, :r6_tracker_active_id, :user_timezone)
      ON CONFLICT(id) DO UPDATE SET
        display_name = :user_display_name,
        ubisoft_username_max = :user_max_account_name,
        ubisoft_username_active = :user_active_account,
        r6_tracker_active_id = :r6_tracker_active_id,
        time_zone = :user_timezone
      WHERE id = :user_id;
    """,
        {
            "user_id": user_id,
            "user_display_name": display_name,
            "user_max_account_name": user_max_account_name,
            "user_active_account": user_active_account,
            "r6_tracker_active_id": r6_tracker_active_id,
            "user_timezone": user_timezone,
        },
    )

    database_manager.get_conn().commit()


def get_active_user_info(from_time: datetime, to_time: datetime) -> list[UserInfo]:
    """
    Get the list of UserInfo of active user
    """
    # Get the list of user who were active
    user_ids = fetch_user_infos_with_activity(from_time, to_time)

    # Get the user info to get the ubisoft name
    user_infos = fetch_user_info_by_user_id_list(user_ids)

    # Remove user without active or max account
    return [
        user_info for user_info in user_infos if user_info is not None and user_info.ubisoft_username_active is not None
    ]


def insert_if_nonexistant_full_match_info(user_info: UserInfo, list_matches: list[UserFullMatchStats]) -> None:
    """
    We have a list of full match info, we want to insert them if they do not exist
    A match might exist in the case we fetched more and the user already had some matches recorded.
    """

    match_user_pairs = [
        (
            match.match_uuid,
            match.user_id,
        )
        for match in list_matches
    ]

    # Construct a query using AND and OR instead of row-value comparisons
    conditions = " OR ".join(["(match_uuid = ? AND user_id = ?)" for _ in match_user_pairs])

    if not conditions.strip():  # Ensure conditions exist
        print_log("insert_if_nonexistant_full_match_info: No user-match pair to insert, leaving the function early")
        return

    query = f"""
        SELECT match_uuid, user_id
        FROM user_full_match_info
        WHERE {conditions}
    """
    params = [item for pair in match_user_pairs for item in pair]

    if len(params) == 0:
        print_log("insert_if_nonexistant_full_match_info: No match to insert, leaving the function early")
        return

    # Get the list of match that is already in the database that matches a match+user pair
    database_manager.get_cursor().execute(query, params)

    existing_records = database_manager.get_cursor().fetchall()
    existing_set = set(existing_records)
    filtered_data = [obj for obj in list_matches if (obj.match_uuid, obj.user_id) not in existing_set]
    print_log(
        f"insert_if_nonexistant_full_match_info: Found {len(filtered_data)} new matches to insert out of {len(list_matches)} for {user_info.display_name}"
    )
    # Try to insert the match that are not yet in the database
    # Todo: Batch insert
    last_match: Union[UserFullMatchStats, None] = None
    try:
        with database_manager.data_access_transaction():
            cursor = database_manager.get_cursor()
            for match in filtered_data:
                last_match = match
                cursor.execute(
                    """
                INSERT INTO user_full_match_info (
                    match_uuid,
                    user_id,
                    match_timestamp,
                    match_duration_ms,
                    data_center,
                    session_type,
                    map_name,
                    is_surrender,
                    is_forfeit,
                    is_rollback,
                    r6_tracker_user_uuid,
                    ubisoft_username,
                    operators,
                    round_played_count,
                    round_won_count,
                    round_lost_count,
                    round_disconnected_count,
                    kill_count,
                    death_count,
                    assist_count,
                    head_shot_count,
                    tk_count,
                    ace_count,
                    first_kill_count,
                    first_death_count,
                    clutches_win_count,
                    clutches_loss_count,
                    clutches_win_count_1v1,
                    clutches_win_count_1v2,
                    clutches_win_count_1v3,
                    clutches_win_count_1v4,
                    clutches_win_count_1v5,
                    clutches_lost_count_1v1,
                    clutches_lost_count_1v2,
                    clutches_lost_count_1v3,
                    clutches_lost_count_1v4,
                    clutches_lost_count_1v5,
                    kill_1_count,
                    kill_2_count,
                    kill_3_count,
                    kill_4_count,
                    kill_5_count,
                    rank_points,
                    rank_name,
                    points_gained,
                    rank_previous,
                    kd_ratio,
                    head_shot_percentage,
                    kills_per_round,
                    deaths_per_round,
                    assists_per_round,
                    has_win)
                VALUES (
                    :match_uuid,
                    :user_id,
                    :match_timestamp,
                    :match_duration_ms,
                    :data_center,
                    :session_type,
                    :map_name,
                    :is_surrender,
                    :is_forfeit,
                    :is_rollback,
                    :r6_tracker_user_uuid,
                    :ubisoft_username,
                    :operators,
                    :round_played_count,
                    :round_won_count,
                    :round_lost_count,
                    :round_disconnected_count,
                    :kill_count,
                    :death_count,
                    :assist_count,
                    :head_shot_count,
                    :tk_count,
                    :ace_count,
                    :first_kill_count,
                    :first_death_count,
                    :clutches_win_count,
                    :clutches_loss_count,
                    :clutches_win_count_1v1,
                    :clutches_win_count_1v2,
                    :clutches_win_count_1v3,
                    :clutches_win_count_1v4,
                    :clutches_win_count_1v5,
                    :clutches_lost_count_1v1,
                    :clutches_lost_count_1v2,
                    :clutches_lost_count_1v3,
                    :clutches_lost_count_1v4,
                    :clutches_lost_count_1v5,
                    :kill_1_count,
                    :kill_2_count,
                    :kill_3_count,
                    :kill_4_count,
                    :kill_5_count,
                    :rank_points,
                    :rank_name,
                    :points_gained,
                    :rank_previous,
                    :kd_ratio,
                    :head_shot_percentage,
                    :kills_per_round,
                    :deaths_per_round,
                    :assists_per_round,
                    :has_win
                )
                """,
                    {
                        "match_uuid": match.match_uuid,
                        "user_id": user_info.id,
                        "match_timestamp": match.match_timestamp,
                        "match_duration_ms": match.match_duration_ms,
                        "data_center": match.data_center,
                        "session_type": match.session_type,
                        "map_name": match.map_name,
                        "is_surrender": match.is_surrender,
                        "is_forfeit": match.is_forfeit,
                        "is_rollback": match.is_rollback,
                        "r6_tracker_user_uuid": match.r6_tracker_user_uuid,
                        "ubisoft_username": match.ubisoft_username,
                        "operators": match.operators,
                        "round_played_count": match.round_played_count,
                        "round_won_count": match.round_won_count,
                        "round_lost_count": match.round_lost_count,
                        "round_disconnected_count": match.round_disconnected_count,
                        "kill_count": match.kill_count,
                        "death_count": match.death_count,
                        "assist_count": match.assist_count,
                        "head_shot_count": match.head_shot_count,
                        "tk_count": match.tk_count,
                        "ace_count": match.ace_count,
                        "first_kill_count": match.first_kill_count,
                        "first_death_count": match.first_death_count,
                        "clutches_win_count": match.clutches_win_count,
                        "clutches_loss_count": match.clutches_loss_count,
                        "clutches_win_count_1v1": match.clutches_win_count_1v1,
                        "clutches_win_count_1v2": match.clutches_win_count_1v2,
                        "clutches_win_count_1v3": match.clutches_win_count_1v3,
                        "clutches_win_count_1v4": match.clutches_win_count_1v4,
                        "clutches_win_count_1v5": match.clutches_win_count_1v5,
                        "clutches_lost_count_1v1": match.clutches_lost_count_1v1,
                        "clutches_lost_count_1v2": match.clutches_lost_count_1v2,
                        "clutches_lost_count_1v3": match.clutches_lost_count_1v3,
                        "clutches_lost_count_1v4": match.clutches_lost_count_1v4,
                        "clutches_lost_count_1v5": match.clutches_lost_count_1v5,
                        "kill_1_count": match.kill_1_count,
                        "kill_2_count": match.kill_2_count,
                        "kill_3_count": match.kill_3_count,
                        "kill_4_count": match.kill_4_count,
                        "kill_5_count": match.kill_5_count,
                        "rank_points": match.rank_points,
                        "rank_name": match.rank_name,
                        "points_gained": match.points_gained,
                        "rank_previous": match.rank_previous,
                        "kd_ratio": match.kd_ratio,
                        "head_shot_percentage": match.head_shot_percentage,
                        "kills_per_round": match.kills_per_round,
                        "deaths_per_round": match.deaths_per_round,
                        "assists_per_round": match.assists_per_round,
                        "has_win": match.has_win,
                    },
                )
                print_log(
                    f"insert_if_nonexistant_full_match_info: Inserted match {cursor.rowcount} for {user_info.display_name}"
                )
        # End transaction
    except Exception as e:
        if last_match is None:
            print_error_log("insert_if_nonexistant_full_match_info: Error inserting match: No match to insert")
        stringify_match = json.dumps(asdict(last_match), indent=4) if last_match is not None else "No match data"
        print_error_log(f"insert_if_nonexistant_full_match_info: Error inserting match: {e}\n{stringify_match}")
        raise e


def data_access_fetch_user_full_match_info(
    user_id: int, page_number_zero_index: int = 0, page_size: int = 50
) -> list[UserFullMatchStats]:
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    query = f"""
        SELECT {SELECT_USER_FULL_MATCH_INFO}
        FROM user_full_match_info
        WHERE user_full_match_info.user_id = :user_id
        ORDER BY match_timestamp DESC
        LIMIT :page_size OFFSET :offset
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id, "page_size": page_size, "offset": page_number_zero_index * page_size},
        )
    ).fetchall()
    # Convert the result to a list of Stats
    return [UserFullMatchStats.from_db_row(row) for row in result]


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


def data_access_fetch_rollback_count_by_user(from_data: date) -> list[tuple[int, str, int]]:
    """
    Fetch the rollback count for each user
    """
    query = """
        SELECT
            user_full_match_info.user_id,
            user_info.display_name,
            count(user_full_match_info.id) as count_rollbacks
        FROM
            user_full_match_info
        LEFT JOIN user_info 
            ON user_info.id = user_full_match_info.user_id
        WHERE
            user_full_match_info.is_rollback = true
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
        ORDER BY count_rollbacks DESC;
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
