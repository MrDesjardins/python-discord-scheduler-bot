"""
Module to gather user activity data and calculate the time spent together
"""

from typing import Dict
from deps.data_access_data_class import UserInfo, UserActivity
from deps.analytic_database import cursor, conn
from deps.analytic_functions import compute_users_weights

def delete_all_tables() -> None:
    """
    Delete all tables
    """
    cursor.execute("DELETE FROM user_info")
    cursor.execute("DELETE FROM user_activity")
    cursor.execute("DELETE FROM user_weights")
    conn.commit()


def delete_all_user_weights():
    """
    Erase everything to start the calculation from scratch
    """
    cursor.execute("DELETE FROM user_weights")
    conn.commit()


def insert_user_activity(user_id, user_display_name, channel_id, guild_id, event, time) -> None:
    """
    Log a user activity in the database
    """
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
    VALUES (?, ?, ?, ?, ?)
    """,
        (user_id, channel_id, guild_id, event, time),
    )
    conn.commit()


def fetch_user_names() -> Dict[int, UserInfo]:
    """
    Fetch all user names from the user_info table
    """
    cursor.execute("SELECT id, display_name FROM user_info")
    return {row[0]: UserInfo(*row) for row in cursor.fetchall()}


def fetch_user_activities(from_day: int = 3600, to_day: int = 0) -> list[UserActivity]:
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    cursor.execute(
        """
        SELECT user_id, channel_id, event, timestamp, guild_id
        FROM user_activity
        WHERE timestamp >= datetime('now', ? ) AND timestamp <= datetime('now', ?)
        ORDER BY channel_id, timestamp
        """,
        (f"-{from_day} days", f"-{to_day} days"),
    )
    # Convert the result to a list of UserActivity objects
    return [UserActivity(*row) for row in cursor.fetchall()]



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
        cursor.execute(
            """
        INSERT INTO user_weights (user_a, user_b, channel_id, weight)
        VALUES (?, ?, ?, ?)
        """,
            (user_a, user_b, channel_id, total_weight),
        )
    conn.commit()