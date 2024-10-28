"""
Module to gather user activity data and calculate the time spent together
"""

from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, Tuple, List
import pandas as pd
from dateutil import parser
from deps.analytic_models import UserInfoWithCount
from deps.analytic_database import EVENT_CONNECT, EVENT_DISCONNECT
from deps.data_access_data_class import UserActivity, UserInfo


def calculate_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> float:
    """
    Function to calculate overlapping time between two time
    """
    latest_start = max(start1, start2)
    earliest_end = min(end1, end2)

    # If there's overlap, calculate the duration
    overlap = (earliest_end - latest_start).total_seconds()
    return max(0, overlap)  # If overlap is negative, it means no overlap


def calculate_user_connections(activity_data: list[UserActivity]) -> Dict[int, Dict[int, Tuple[int, int]]]:
    """The return is { channel_id: { user_id: [(connect_time, disconnect_time), ...] } }"""
    # Dictionary to store connection times of users in rooms
    user_connections: Dict[int, Dict[int, Tuple[int, int]]] = (
        {}
    )  # { channel_id: { user_id: [(connect_time, disconnect_time), ...] } }

    # Iterate over the activity data and populate user_connections
    for activity in activity_data:
        timestamp = parser.parse(activity.timestamp)  # String to datetime

        if activity.channel_id not in user_connections:
            user_connections[activity.channel_id] = {}

        if activity.user_id not in user_connections[activity.channel_id]:
            user_connections[activity.channel_id][activity.user_id] = []

        if activity.event == EVENT_CONNECT:
            # Log the connection time
            user_connections[activity.channel_id][activity.user_id].append(
                [timestamp, None]
            )  # Connect time with None for disconnect
        elif activity.event == EVENT_DISCONNECT and user_connections[activity.channel_id][activity.user_id]:
            # Update the latest disconnect time for the most recent connect entry
            user_connections[activity.channel_id][activity.user_id][-1][1] = timestamp
    return user_connections


def compute_users_weights(activity_data: list[UserActivity]) -> Dict[Tuple[int, int, int], int]:
    """
    Compute the weights of users in the same channel in seconds
    The return is (channel_id, user_a, user_b) -> total time in seconds
    """
    # Dictionary to store connection times of users in rooms
    user_connections = calculate_user_connections(activity_data)

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


def computer_users_voice_in_out(activity_data: list[UserActivity]) -> Dict[int, List[Tuple[datetime, datetime]]]:
    """
    Give an array of in-out for each user
    """
    users_in_out: Dict[int, List[Tuple[datetime, datetime]]] = {}  # { user_id: (enter, left)[] }

    # Iterate over the activity data and populate user_connections
    for activity in activity_data:
        timestamp = parser.parse(activity.timestamp)  # String to datetime

        if activity.user_id not in users_in_out:
            users_in_out[activity.user_id] = []

        if activity.event == EVENT_CONNECT:
            # Log the connection time
            users_in_out[activity.user_id].append((timestamp, None))
        elif activity.event == EVENT_DISCONNECT and users_in_out[activity.user_id]:
            # Update the latest disconnect time for the most recent connect entry
            users_in_out[activity.user_id][-1] = (users_in_out[activity.user_id][-1][0], timestamp)
    return users_in_out


def compute_users_voice_channel_time_sec(users_in_out: Dict[int, List[Tuple[datetime, datetime]]]) -> Dict[int, int]:
    """
    Compute the total time in second in all voice channels
    The return is user_id -> total time in seconds
    """

    # Now calculate overlapping time between users in the same room
    total_times: Dict[int, int] = {}  # { user_id: time_sec }

    # Iterate over the activity data and populate user_connections
    for user in users_in_out:
        total_times[user] = 0
        for connect, disconnect in users_in_out[user]:
            if disconnect:
                total_times[user] += (disconnect - connect).total_seconds()

    return total_times


def users_last_played_over_day(
    user_in_outs: Dict[int, List[Tuple[datetime, datetime]]],
    days_threshold: int = 1,
) -> Dict[int, int]:
    """
    Compute the number of days since each user last played, and only return users who have not played for over `days_threshold` days.
    """
    inactive_users = {}

    # Get the current time
    now = datetime.now(timezone.utc)

    # Iterate over each user's activity
    for user_id, sessions in user_in_outs.items():
        last_disconnect = None
        if sessions:
            # Get the last session's disconnect time (the most recent time)
            for _connect, disconnect in sessions:
                if last_disconnect is None or disconnect is None:
                    last_disconnect = disconnect
                else:
                    if disconnect > last_disconnect:
                        last_disconnect = disconnect

            if last_disconnect is not None:
                # Calculate the number of days since the last disconnect
                days_since_last_played = (now - last_disconnect).days

                # Only include users who haven't played for more than `days_threshold` days
                if days_since_last_played > days_threshold:
                    inactive_users[user_id] = days_since_last_played

    return inactive_users


def users_by_weekday(
    users: list[UserActivity], users_id_display: Dict[int, UserInfo]
) -> Dict[int, list[UserInfoWithCount]]:
    """
    Return the users per weekday
    """
    data = [
        {
            "user_id": activity.user_id,
            "timestamp": activity.timestamp,
        }
        for activity in users
    ]

    df = pd.DataFrame(data)
    # Convert the timestamp column to datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", errors="coerce")

    # Extract the ISO week number and the weekday (Monday = 0, Sunday = 6)
    df["week"] = df["timestamp"].dt.isocalendar().week
    df["day_of_week"] = df["timestamp"].dt.dayofweek

    # Group by week, day_of_week, and user_id to get unique user activity per weekday for each week
    unique_users_per_weekday = df.groupby(["week", "day_of_week", "user_id"]).size().reset_index(name="count")

    # Group by day_of_week and user_id, and count distinct weeks for each user on each day_of_week
    user_activity_count = (
        unique_users_per_weekday.groupby(["day_of_week", "user_id"])
        .agg(distinct_week_count=("week", "nunique"))
        .reset_index()
    )

    # Create a dictionary mapping each user_id to their distinct week count
    weekday_group = (
        user_activity_count.groupby("day_of_week")
        .apply(
            lambda group: [
                UserInfoWithCount(users_id_display[user_id], row["distinct_week_count"])
                for user_id, row in group.set_index("user_id").iterrows()
            ]
        )
        .reset_index(name="users")
    )
    # Convert the result to a dictionary where the key is the day_of_week
    result = {row["day_of_week"]: row["users"] for _, row in weekday_group.iterrows()}

    return result


def user_times_by_month(user_activities: list[UserActivity]) -> defaultdict[str, defaultdict[int, int]]:
    """Calculate the total time played per user per month"""
    user_sessions = defaultdict(list)

    # Group activities by user
    for activity in user_activities:
        user_sessions[activity.user_id].append(activity)

    # Dictionary to hold total time played per user per month [month_year][user_id] = time_played
    time_played_per_month = defaultdict(lambda: defaultdict(float))

    for user_id, activities in user_sessions.items():
        # Sort activities by timestamp for each user
        activities.sort(key=lambda x: x.timestamp)

        connect_time = None

        for activity in activities:
            event_time = datetime.fromisoformat(activity.timestamp)

            if activity.event == EVENT_CONNECT:
                connect_time = event_time
            elif activity.event == EVENT_DISCONNECT and connect_time:
                # Calculate session duration in hours
                session_duration = (event_time - connect_time).total_seconds()
                month_year = event_time.strftime("%Y-%m")  # e.g., "2024-10"
                time_played_per_month[month_year][user_id] += session_duration
                connect_time = None  # Reset connect time for next session
    return time_played_per_month


def times_by_months(user_activities: list[UserActivity]) -> pd.Series:
    """Display a month after month the total time played by all users"""
    df = pd.DataFrame(user_activities)
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed")  # Ensure timestamps are in datetime format
    # Create an empty list to hold the session times
    sessions = []

    # Iterate through the dataframe and calculate session durations
    for user_id, group in df.groupby(["user_id", "guild_id"]):
        connect_time = None
        for _, row in group.iterrows():
            if row["event"] == EVENT_CONNECT:
                connect_time = row["timestamp"]
            elif row["event"] == EVENT_DISCONNECT and connect_time:
                # Calculate session duration in seconds
                session_duration = (row["timestamp"] - connect_time).total_seconds()
                sessions.append(
                    {
                        "user_id": user_id[0],
                        "guild_id": user_id[1],
                        "month": connect_time.strftime("%Y-%m"),
                        "duration": session_duration,
                    }
                )
                connect_time = None  # Reset connect time after disconnect

    # Convert the session list to a DataFrame and print to debug
    sessions_df = pd.DataFrame(sessions)

    # Check if 'month' column exists before proceeding
    if "month" not in sessions_df.columns:
        raise ValueError("Expected 'month' column not found in sessions DataFrame.")

    # Aggregate by month to get the total session time per month
    monthly_sessions = sessions_df.groupby("month")["duration"].sum() / 3600  # Convert seconds to hours
    return monthly_sessions
