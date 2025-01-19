"""
Module to gather user activity data and calculate the time spent together
"""

import datetime
from typing import Dict, List, Optional
from deps.data_access_data_class import UserInfo, UserActivity
from deps.system_database import database_manager
from deps.analytic_functions import compute_users_weights
from deps.cache import (
    get_cache,
)
from deps.functions import ensure_utc
from deps.models import UserFullMatchStats
from deps.log import print_error_log, print_log

KEY_USER_INFO = "user_info"
KEY_TOURNAMENT_GUILD = "tournament_guild"
KEY_TOURNAMENT_GAMES = "tournament_games"

USER_ACTIVITY_SELECT_FIELD = "user_id, channel_id, event, timestamp, guild_id"
USER_INFO_SELECT_FIELD = (
    "id, display_name, ubisoft_username_max, ubisoft_username_active, r6_tracker_active_id, time_zone"
)


def delete_all_tables() -> None:
    """
    Delete all tables
    """
    # print(f"Deleting all tables from database {database_manager.get_database_name()}")
    database_manager.get_cursor().execute("DELETE FROM user_info")
    database_manager.get_cursor().execute("DELETE FROM user_activity")
    database_manager.get_cursor().execute("DELETE FROM user_weights")
    database_manager.get_cursor().execute("DELETE FROM user_full_match_info")
    database_manager.get_conn().commit()


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

    result_with_none = []
    for user_id in user_id_list:
        user_info = result.get(user_id)
        if user_info is None:
            result_with_none.append(None)
        else:
            result_with_none.append(user_info)
    return result_with_none


def fetch_all_user_activities(from_day: int = 3600, to_day: int = 0) -> list[UserActivity]:
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    database_manager.get_cursor().execute(
        f"""
        SELECT {USER_ACTIVITY_SELECT_FIELD}
        FROM user_activity
        WHERE timestamp >= datetime('now', ? ) AND timestamp <= datetime('now', ?)
        ORDER BY timestamp
        """,
        (f"-{from_day} days", f"-{to_day} days"),
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
        ORDER BY timestamp
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
        ORDER BY timestamp
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
    Set the timezone for a user
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET ubisoft_username_active = :name
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
    user_id, display_name, user_max_account_name, user_active_account, r6_tracker_active_id, user_timezone
) -> None:
    """
    Log a user activity in the database
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
    return [user_info for user_info in user_infos if user_info.ubisoft_username_active is not None]


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
        print_log("insert_if_nonexistant_full_match_info: No pair to insert, leaving the function early")
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
        f"insert_if_nonexistant_full_match_info: Found {len(filtered_data)} new matches to insert out of {len(list_matches)}"
    )
    # Try to insert the match that are not yet in the database
    try:
        for match in filtered_data:
            database_manager.get_cursor().execute(
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
        database_manager.get_conn().commit()
    except Exception as e:
        print_error_log(f"insert_if_nonexistant_full_match_info: Error inserting match: {e}")
        raise e
