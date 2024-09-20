"""
Module to gather user activity data and calculate the time spent together
"""

from datetime import datetime
from typing import Dict, Tuple

from deps.analytic import cursor, conn, EVENT_CONNECT, EVENT_DISCONNECT


def delete_all_tables() -> None:
    """
    Delete all tables
    """
    cursor.execute("DELETE FROM user_info")
    cursor.execute("DELETE FROM user_activity")
    cursor.execute("DELETE FROM user_weights")
    conn.commit()


def log_activity(user_id, user_display_name, channel_id, guild_id, event, time=datetime.now()) -> None:
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


def fetch_user_activity(from_day: int = 3600, to_day: int = 0):
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    cursor.execute(
        """
        SELECT user_id, channel_id, event, timestamp
        FROM user_activity
        WHERE timestamp >= datetime('now', ? ) AND timestamp <= datetime('now', ?)
        ORDER BY channel_id, timestamp
        """,
        (f"-{from_day} days", f"-{to_day} days"),
    )
    return cursor.fetchall()


def calculate_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> float:
    """
    Function to calculate overlapping time between two time
    """
    latest_start = max(start1, start2)
    earliest_end = min(end1, end2)

    # If there's overlap, calculate the duration
    overlap = (earliest_end - latest_start).total_seconds()
    return max(0, overlap)  # If overlap is negative, it means no overlap


def flush_user_weights():
    """
    Erase everything to start the calculation from scratch
    """
    cursor.execute("DELETE FROM user_weights")
    conn.commit()


# Function to calculate time spent together and insert weights
def calculate_time_spent_from_db(from_day: int, to_day: int) -> None:
    """
    Function to calculate time spent together and insert weights
    """
    flush_user_weights()

    # Fetch all user activity data, ordered by room and timestamp
    activity_data = fetch_user_activity(from_day, to_day)

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


def compute_users_weights(activity_data) -> Dict[Tuple[int, int, int], int]:
    """
    Compute the weights of users in the same channel in seconds
    """
    # Dictionary to store connection times of users in rooms
    user_connections: Dict[int, Dict[int, (int, int)]] = (
        {}
    )  # { channel_id: { user_id: [(connect_time, disconnect_time), ...] } }

    # Iterate over the activity data and populate user_connections
    for user_id, channel_id, event, timestamp in activity_data:
        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

        if channel_id not in user_connections:
            user_connections[channel_id] = {}

        if user_id not in user_connections[channel_id]:
            user_connections[channel_id][user_id] = []

        if event == EVENT_CONNECT:
            # Log the connection time
            user_connections[channel_id][user_id].append([timestamp, None])  # Connect time with None for disconnect
        elif event == EVENT_DISCONNECT and user_connections[channel_id][user_id]:
            # Update the latest disconnect time for the most recent connect entry
            user_connections[channel_id][user_id][-1][1] = timestamp

    # Now calculate overlapping time between users in the same room
    user_weights: Dict[Tuple[int, int, int], int] = {}  # { (user_a, user_b, channel_id): total_weight }

    for channel_id, users in user_connections.items():
        user_ids = list(users.keys())
        for i in range(len(user_ids)):  # pylint: disable=consider-using-enumerate
            for j in range(i + 1, len(user_ids)):  # pylint: disable=consider-using-enumerate
                user_a = user_ids[i]
                user_b = user_ids[j]

                total_overlap_time = 0  # Accumulate total overlap time for this pair

                # Compare all connect/disconnect periods for user_a and user_b
                for connect_a, disconnect_a in users[user_a]:
                    for connect_b, disconnect_b in users[user_b]:
                        # Ensure both users have valid connect and disconnect times
                        if disconnect_a and disconnect_b:
                            overlap_time = calculate_overlap(connect_a, disconnect_a, connect_b, disconnect_b)
                            total_overlap_time += overlap_time

                # Store the total weight if there's any overlap
                if total_overlap_time > 0:
                    key = (user_a, user_b, channel_id)
                    if key in user_weights:
                        user_weights[key] += total_overlap_time
                    else:
                        user_weights[key] = total_overlap_time
    return user_weights
