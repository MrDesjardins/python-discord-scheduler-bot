"""
Module to gather user activity data and calculate the time spent together
"""

from typing import Dict
from deps.data_access_data_class import UserInfo, UserActivity
from deps.analytic_database import database_manager
from deps.analytic_functions import compute_users_weights
from deps.cache import (
    get_cache,
)

KEY_USER_INFO = "user_info"


def delete_all_tables() -> None:
    """
    Delete all tables
    """
    print(f"Deleting all tables from database {database_manager.get_database_name()}")
    database_manager.get_cursor().execute("DELETE FROM user_info")
    database_manager.get_cursor().execute("DELETE FROM user_activity")
    database_manager.get_cursor().execute("DELETE FROM user_weights")
    database_manager.get_conn().commit()


def delete_all_user_weights():
    """
    Erase everything to start the calculation from scratch
    """
    database_manager.get_cursor().execute("DELETE FROM user_weights")
    database_manager.get_conn().commit()


def insert_user_activity(user_id, user_display_name, channel_id, guild_id, event, time) -> None:
    """
    Log a user activity in the database
    """
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
    VALUES (?, ?, ?, ?, ?)
    """,
        (user_id, channel_id, guild_id, event, time),
    )
    database_manager.get_conn().commit()


def fetch_user_info() -> Dict[int, UserInfo]:
    """
    Fetch all user names from the user_info table
    """
    database_manager.get_cursor().execute("SELECT id, display_name, time_zone FROM user_info")
    return {row[0]: UserInfo(*row) for row in database_manager.get_cursor().fetchall()}


def fetch_user_info_by_user_id(user_id: int) -> UserInfo:
    """
    Fetch a user name from the user_info table
    """

    def fetch_from_db():
        print(f"Fetching user info from database for user {user_id}")
        result = (
            database_manager.get_cursor()
            .execute("SELECT id, display_name, time_zone FROM user_info WHERE id = ?", (user_id,))
            .fetchone()
        )
        if result is not None:
            return UserInfo(*result)
        else:
            # Handle the case where no user was found, e.g., return None or raise an exception
            return None  # Or raise an appropriate exception

    return get_cache(True, f"{KEY_USER_INFO}:{user_id}", fetch_from_db)


def fetch_user_activities(from_day: int = 3600, to_day: int = 0) -> list[UserActivity]:
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    database_manager.get_cursor().execute(
        """
        SELECT user_id, channel_id, event, timestamp, guild_id
        FROM user_activity
        WHERE timestamp >= datetime('now', ? ) AND timestamp <= datetime('now', ?)
        ORDER BY channel_id, timestamp
        """,
        (f"-{from_day} days", f"-{to_day} days"),
    )
    # Convert the result to a list of UserActivity objects
    return [UserActivity(*row) for row in database_manager.get_cursor().fetchall()]


def calculate_time_spent_from_db(from_day: int, to_day: int) -> None:
    """
    Function to calculate time spent together and insert weights
    """
    delete_all_user_weights()

    # Fetch all user activity data, ordered by room and timestamp
    activity_data = fetch_user_activities(from_day, to_day)

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
