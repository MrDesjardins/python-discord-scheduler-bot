"""
Analytics Activity Data Access Module

This module handles user voice channel activity tracking including join/leave events,
time-spent calculations, and relationship weight computations.

Functions:
- delete_all_user_weights: Erase all user weight calculations
- insert_user_activity: Log user voice activity events
- fetch_user_info: Get all user profile information
- fetch_user_info_by_user_id: Get specific user profile by ID (cached)
- fetch_user_info_by_user_id_list: Get multiple user profiles by ID list
- fetch_all_user_activities: Fetch all user activities in date range
- fetch_all_user_activities2: Fetch user overlap time calculations
- fetch_user_activities: Fetch activities for specific user
- fetch_user_infos_with_activity: Get user IDs with activity in time range
- calculate_time_spent_from_db: Calculate and persist user relationship weights
"""

from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Union

from deps.analytic_constants import (
    KEY_USER_INFO,
    USER_ACTIVITY_SELECT_FIELD,
    USER_INFO_SELECT_FIELD,
)
from deps.data_access_data_class import UserInfo, UserActivity
from deps.system_database import database_manager
from deps.analytic_functions import compute_users_weights
from deps.cache import get_cache
from deps.functions_date import ensure_utc
from deps.log import print_warning_log


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
    Log a user activity in the database with deduplication
    """
    time = ensure_utc(time)

    # Wrap duplicate check + insert in transaction to prevent race condition
    with database_manager.data_access_transaction() as cursor:
        # FIX: Check for duplicate events within 1-second window
        time_start = (time - timedelta(seconds=1)).isoformat()
        time_end = (time + timedelta(seconds=1)).isoformat()

        cursor.execute(
            """
            SELECT COUNT(*) FROM user_activity
            WHERE user_id = ? AND channel_id = ? AND guild_id = ? AND event = ?
            AND timestamp >= ? AND timestamp <= ?
            """,
            (user_id, channel_id, guild_id, event, time_start, time_end),
        )

        if cursor.fetchone()[0] > 0:

            print_warning_log(
                f"Duplicate activity event detected for user {user_id} in channel {channel_id} "
                f"(event={event}, time={time.isoformat()}). Skipping."
            )
            return

        # Original insert logic
        cursor.execute(
            """
        INSERT INTO user_info(id, display_name)
          VALUES(:user_id, :user_display_name)
          ON CONFLICT(id) DO UPDATE SET
            display_name = :user_display_name
          WHERE id = :user_id;
        """,
            {"user_id": user_id, "user_display_name": user_display_name},
        )
        cursor.execute(
            """
        INSERT INTO user_activity (user_id, channel_id, guild_id, event, timestamp)
        VALUES (:user_id, :channel_id, :guild_id, :event, :time)
        """,
            {"user_id": user_id, "channel_id": channel_id, "guild_id": guild_id, "event": event, "time": time.isoformat()},
        )
        # Transaction will be committed automatically by context manager


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
    from_date = datetime.now(timezone.utc) - timedelta(days=from_day)
    to_date = datetime.now(timezone.utc) - timedelta(days=to_day)
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
        SELECT user_id
        FROM user_activity
        WHERE timestamp >= ?
        AND timestamp <= ?
        GROUP BY user_id
        """,
        (from_utc.isoformat(), to_utc.isoformat()),
    )
    return [row[0] for row in database_manager.get_cursor().fetchall()]


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
