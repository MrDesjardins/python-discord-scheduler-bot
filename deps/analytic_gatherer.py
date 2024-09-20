"""
Module to gather user activity data and calculate the time spent together
"""

import sqlite3
from datetime import datetime

EVENT_CONNECT = "connect"
EVENT_DISCONNECT = "disconnect"

# Connect to SQLite database (it will create the database file if it doesn't exist)
conn = sqlite3.connect("user_activity.db")
cursor = conn.cursor()

# Create the tables
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS user_info (
    id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL
)
"""
)

cursor.execute(
    f"""
CREATE TABLE IF NOT EXISTS user_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    event TEXT CHECK(event IN ('{EVENT_CONNECT}', '{EVENT_DISCONNECT}')) NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES user_info(id)
)
"""
)
cursor.execute(
    """
CREATE TABLE  IF NOT EXISTS user_weights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_a TEXT NOT NULL,
    user_b TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    weight REAL NOT NULL
);
"""
)


def log_activity(user_id, user_display_name, channel_id, guild_id, event) -> None:
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
        (user_id, channel_id, guild_id, event, datetime.now()),
    )
    conn.commit()


def fetch_user_activity():
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    query = """
    SELECT user_id, channel_id, event, timestamp
    FROM user_activity
    ORDER BY channel_id, timestamp
    """
    cursor.execute(query)
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
def calculate_time_spent():
    """
    Function to calculate time spent together and insert weights
    """
    flush_user_weights()

    # Fetch all user activity data, ordered by room and timestamp
    activity_data = fetch_user_activity()

    # Dictionary to store connection times of users in rooms
    user_connections = {}  # { channel_id: { user_id: [(connect_time, disconnect_time), ...] } }

    # Iterate over the activity data and populate user_connections
    for user_id, channel_id, event, timestamp in activity_data:
        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

        if channel_id not in user_connections:
            user_connections[channel_id] = {}

        if user_id not in user_connections[channel_id]:
            user_connections[channel_id][user_id] = []

        if event == "connect":
            # Log the connection time
            user_connections[channel_id][user_id].append([timestamp, None])  # Connect time with None for disconnect
        elif event == "disconnect" and user_connections[channel_id][user_id]:
            # Update the latest disconnect time for the most recent connect entry
            user_connections[channel_id][user_id][-1][1] = timestamp

    # Now calculate overlapping time between users in the same room
    user_weights = {}  # { (user_a, user_b, channel_id): total_weight }

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
