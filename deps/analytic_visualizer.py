"""
Code to show the relationsip between the users
"""

import io
from collections import defaultdict
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from typing import List, Dict, Tuple, Union, Any
import plotly.graph_objs as go  # type: ignore
import seaborn as sns
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import community as community_louvain  # type: ignore
from deps.analytic_models import UserInfoWithCount
from deps.data_access_data_class import UserActivity, UserInfo
from deps.analytic_functions import (
    computer_users_voice_in_out,
    compute_users_voice_channel_time_sec,
    times_by_months,
    user_times_by_month,
    users_last_played_over_day,
    users_by_weekday,
)
from deps.analytic_data_access import (
    data_access_fetch_users_operators,
    data_access_fetch_win_rate_server,
    fetch_all_user_activities,
    fetch_user_activities,
    fetch_user_info,
    calculate_time_spent_from_db,
)
from deps.system_database import EVENT_CONNECT, EVENT_DISCONNECT, database_manager


@dataclass
class UsersRelationship:
    """
    User 1 and 2 with names and weight (int)
    """

    user1_id: int
    user2_id: int
    user1_display_name: str
    user2_display_name: str
    weight: int


def get_unidirection_users(data: List[UsersRelationship]) -> Tuple[Dict[int, Dict[int, int]], int]:
    """
    Get the weight regardless of the direction of a relationship
    """
    users_uni_direction: Dict[int, Dict[int, int]] = {}
    max_weight = 0
    for user in data:
        if user.user1_id in users_uni_direction:
            if user.user2_id in users_uni_direction[user.user1_id]:
                users_uni_direction[user.user1_id][user.user2_id] = (
                    users_uni_direction[user.user1_id][user.user2_id] + user.weight
                )
            else:
                users_uni_direction[user.user1_id][user.user2_id] = user.weight
        else:
            users_uni_direction[user.user1_id] = {user.user2_id: user.weight}
        max_weight = max(max_weight, users_uni_direction[user.user1_id][user.user2_id])
    return (users_uni_direction, max_weight)


def _get_data(from_day, to_day) -> list[UsersRelationship]:
    """
    Display the relationship between users in a graph
    """
    calculate_time_spent_from_db(from_day, to_day)

    # Fetch the data from the user_weights table
    database_manager.get_cursor().execute(
        """
    SELECT 
        ui1.id as user1_id, 
        ui2.id as user2_id, 
        ui1.display_name as user1_display_name, 
        ui2.display_name as user2_display_name, 
        weight 
    FROM user_weights 
    left join 
        user_info as ui1 on user_weights.user_a = ui1.id 
    left join 
        user_info as ui2 on user_weights.user_b = ui2.id
    """
    )
    all_data = [UsersRelationship(*row) for row in database_manager.get_cursor().fetchall()]
    # Remove relationship with not a lot of time spent together (under 1 hour)
    data = [user for user in all_data if user.weight > 3600]  # 1 hour

    return data


def display_graph_cluster_people(show: bool = True, from_day: int = 3600, to_day: int = 0) -> Union[bytes, None]:
    """
    Determine the clusters of users and display them in a graph
    """
    data = _get_data(from_day, to_day)

    # Create a graph using NetworkX
    graph_network = nx.Graph()

    (users_uni_direction, max_weight) = get_unidirection_users(data)

    # Get the names of the users
    users_name: Dict[int, str] = {}
    for user in data:
        users_name[user.user1_id] = user.user1_display_name
        users_name[user.user2_id] = user.user2_display_name

    # Add edges with normalized weights between users
    for user_1_id, value in users_uni_direction.items():
        for user_2_id, weight in value.items():
            normalized_weight = (weight / max_weight) * 14  # Normalize to max 14 (width line)
            user_a = users_name[user_1_id][:8]  # Truncate to 8 characters for better visualization
            user_b = users_name[user_2_id][:8]  # Truncate to 8 characters for better visualization
            graph_network.add_edge(user_a, user_b, weight=normalized_weight)

    # Detect communities using Louvain method
    partition = community_louvain.best_partition(graph_network)

    # Get unique community IDs and colors for visualization
    communities = set(partition.values())
    colors = plt.cm.get_cmap("viridis", len(communities))

    # Draw the graph
    plt.figure(figsize=(24, 24))

    # Position the nodes using the spring layout
    pos = nx.spring_layout(graph_network, scale=None, k=5)

    # Draw nodes, coloring by community
    for community_id in communities:
        nodes_in_community = [node for node in partition if partition[node] == community_id]
        nx.draw_networkx_nodes(
            graph_network,
            pos,
            nodelist=nodes_in_community,
            node_color=[colors(community_id)],
            label=f"Community {community_id}",
            node_size=700,
        )

    # Draw edges, adjusting width based on the normalized weight
    normalized_weights = nx.get_edge_attributes(graph_network, "weight")
    all_width: List[float] = [weight for weight in normalized_weights.values()]
    nx.draw_networkx_edges(graph_network, pos, width=all_width)

    # Draw labels for users (nodes), adjusted to be above the nodes
    label_pos = {node: (x, y + 0.15) for node, (x, y) in pos.items()}  # Adjust y-coordinate
    nx.draw_networkx_labels(
        graph_network,
        label_pos,
        labels={node: node for node in graph_network.nodes()},
        font_size=12,
        font_family="sans-serif",
        font_color="#209ef7",
    )

    # Draw edge labels (normalized weights)
    # nx.draw_networkx_edge_labels(
    #     graph_network,
    #     pos,
    #     edge_labels={k: f"{v:.2f}" for k, v in normalized_weights.items()},
    # )

    # Show plot
    plt.title("User Relationship Graph with Clusters (Edge Tickness = More Time Together)")
    plt.axis("off")  # Turn off the axis
    plt.legend()
    return _plot_return(plt, show)


def _plot_return(plot: Any, show: bool = True) -> Union[bytes, None]:
    """
    Return an image or the bytes of the iamge
    """
    if show:
        plot.show()
        return None

    buf = io.BytesIO()
    plot.savefig(buf, format="png")
    buf.seek(0)

    # Get the bytes data
    image_bytes = buf.getvalue()
    buf.close()
    return image_bytes


def display_graph_cluster_people_3d_animated(
    show: bool = True, from_day: int = 3600, to_day: int = 0
) -> Union[bytes, None]:
    """
    Determine the clusters of users and display them in a 3D animated graph
    """
    data = _get_data(from_day, to_day)

    # Create a graph using NetworkX
    graph_network = nx.Graph()

    (users_uni_direction, max_weight) = get_unidirection_users(data)

    # Get the names of the users
    users_name: Dict[int, str] = {}
    for user in data:
        users_name[user.user1_id] = user.user1_display_name
        users_name[user.user2_id] = user.user2_display_name

    # Add edges with normalized weights between users
    for user_1_id, value in users_uni_direction.items():
        for user_2_id, weight in value.items():
            normalized_weight = (weight / max_weight) * 25  # Normalize to max value
            user_a = users_name[user_1_id][:8]  # Truncate to 8 characters for better visualization
            user_b = users_name[user_2_id][:8]  # Truncate to 8 characters for better visualization
            graph_network.add_edge(user_a, user_b, weight=normalized_weight)

    # Detect communities using Louvain method
    partition = community_louvain.best_partition(graph_network)

    # Get unique community IDs and assign colors
    communities = set(partition.values())
    color_map = plt.cm.get_cmap("viridis", len(communities))
    node_colors = [color_map(partition[node])[:3] for node in graph_network.nodes()]

    # Get spring layout positions
    pos = nx.spring_layout(graph_network, dim=3)

    # Extract coordinates for the nodes
    node_x = [pos[node][0] for node in graph_network.nodes()]
    node_y = [pos[node][1] for node in graph_network.nodes()]
    node_z = [pos[node][2] for node in graph_network.nodes()]

    # Create the 3D scatter plot for nodes with text
    node_trace = go.Scatter3d(
        x=node_x,
        y=node_y,
        z=node_z,
        mode="markers+text",  # Display markers and text
        marker=dict(size=10, color=node_colors, opacity=0.8),
        text=list(graph_network.nodes()),  # User names as text
        textposition="top center",  # Position text above nodes
        hoverinfo="text",
    )

    # Create the edges for the 3D plot with proportional widths
    edge_x, edge_y, edge_z = [], [], []
    edge_traces = []  # Store separate traces for each edge
    for edge in graph_network.edges(data=True):
        x0, y0, z0 = pos[edge[0]]
        x1, y1, z1 = pos[edge[1]]
        edge_x.append(x0)
        edge_x.append(x1)
        edge_x.append(None)  # None to break line segments
        edge_y.append(y0)
        edge_y.append(y1)
        edge_y.append(None)  # None to break line segments
        edge_z.append(z0)
        edge_z.append(z1)
        edge_z.append(None)  # None to break line segments

        # Normalize width for each edge
        edge_width = edge[2]["weight"] if edge[2]["weight"] > 0 else 1  # Prevent zero width
        edge_trace = go.Scatter3d(
            x=edge_x[-3:],  # Last three values for this edge
            y=edge_y[-3:],  # Last three values for this edge
            z=edge_z[-3:],  # Last three values for this edge
            mode="lines",
            line=dict(width=edge_width, color="#0e004f"),
            hoverinfo="none",
        )
        edge_traces.append(edge_trace)

    # Create the layout for the 3D plot
    scene_options = {"showbackground": False}
    layout = go.Layout(
        title="3D Animated User Relationship Graph with Clusters",
        scene=dict(xaxis=scene_options, yaxis=scene_options, zaxis=scene_options),
        showlegend=False,
        hovermode="closest",
        updatemenus=[
            dict(
                type="buttons",
                showactive=False,
            )
        ],
    )

    # Plot the initial state and animate
    fig = go.Figure(data=[node_trace] + edge_traces, layout=layout)
    return _plot_return(fig, show)


def display_time_relationship(show: bool = True, from_day: int = 3600, to_day: int = 0) -> Union[bytes, None]:
    """
    Display the time between two people
    """
    top = 50
    data = _get_data(from_day, to_day)
    from_date = datetime.now().date() - timedelta(days=from_day)
    to_date = datetime.now().date() - timedelta(days=to_day)

    (users_uni_direction, max_weight) = get_unidirection_users(data)

    # Get the names of the users
    users_name: Dict[int, str] = {}
    for user in data:
        users_name[user.user1_id] = user.user1_display_name
        users_name[user.user2_id] = user.user2_display_name

    data_for_plot = []
    # Add edges with normalized weights between users
    for user_1_id, value in users_uni_direction.items():
        for user_2_id, weight in value.items():
            data_for_plot.append(
                {
                    "user1": users_name[user_1_id],
                    "user2": users_name[user_2_id],
                    "weight": weight,
                }
            )
    # Sort by weight
    data_for_plot.sort(key=lambda x: x["weight"], reverse=True)
    # Get the top 20
    data_for_plot = data_for_plot[:top]

    # Create a bar chart
    fig, ax = plt.subplots(figsize=(10, 10))

    # Get the names
    names = [f"{user['user1']} - {user['user2']}" for user in data_for_plot]
    # Get the weights
    weights = [(user["weight"] / 3600) for user in data_for_plot]
    # Create the bar chart
    plt.barh(names, weights)
    plt.xlabel("Hours spent together")
    plt.ylabel("User pairs")

    fig.suptitle(f"Top {top} user pairs with the most time spent together", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    plt.xticks(fontsize=10)  # Reduce x-axis font size if needed
    plt.yticks(fontsize=8)  # Reduce y-axis font size to fit long names
    plt.gca().invert_yaxis()  # Invert the y-axis to have larger weights at the top
    plt.tight_layout()  # Automatically adjust layout to prevent truncatio
    return _plot_return(plt, show)


def display_time_voice_channel(show: bool = True, from_day: int = 3600, to_day: int = 0) -> Union[bytes, None]:
    """
    Display the total time a user has spent in a voice channel
    """
    top = 30
    data_user_activity = fetch_all_user_activities(from_day, to_day)
    data_user_id_name = fetch_user_info()

    from_date = datetime.now().date() - timedelta(days=from_day)
    to_date = datetime.now().date() - timedelta(days=to_day)

    auser_in_outs = computer_users_voice_in_out(data_user_activity)
    user_times = compute_users_voice_channel_time_sec(auser_in_outs)

    # Convert seconds to hours for all users
    user_times_in_hours = {user: time_sec / 3600 for user, time_sec in user_times.items()}

    # Sort users by total time in descending order and select the top N
    sorted_users = sorted(user_times_in_hours.items(), key=lambda x: x[1], reverse=True)[:top]

    # Unpack the sorted list into two lists: one for user names and one for times
    users, times_in_hours = zip(*sorted_users)
    users_display_name: List[str] = [data_user_id_name[user_id].display_name for user_id in users]  # Convert user

    # Create the bar plot
    fig, ax = plt.subplots(figsize=(10, 8))

    plt.bar(users_display_name, times_in_hours, color="skyblue")

    # Add labels and title
    plt.xlabel("Users")
    plt.ylabel("Total Time (Hours)")
    fig.suptitle(f"Top {top} Users by Total Voice Channel Time (in Hours)", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    plt.xticks(rotation=90)  # Rotate user names for better readability
    plt.tight_layout()  # Adjust layout to fit labels better
    return _plot_return(plt, show)


def display_inactive_user(show: bool = True, from_day: int = 3600, to_day: int = 0) -> Union[bytes, None]:
    """
    Show inactive user in time
    """
    top = 50
    data_user_activity = fetch_all_user_activities(from_day, to_day)
    data_user_id_name = fetch_user_info()
    from_date = datetime.now().date() - timedelta(days=from_day)
    to_date = datetime.now().date() - timedelta(days=to_day)

    auser_in_outs = computer_users_voice_in_out(data_user_activity)
    user_times = users_last_played_over_day(auser_in_outs)

    # Sort users by total time in descending order and select the top N
    sorted_users = sorted(user_times.items(), key=lambda x: x[1], reverse=True)[:top]

    # Unpack the sorted list into two lists: one for user names and one for times
    user_ids, time_day = zip(*sorted_users)
    user_names = [data_user_id_name[user_id].display_name for user_id in user_ids]  # Convert user

    # Create the horizontal bar plot
    fig, ax = plt.subplots(figsize=(10, 8))
    plt.barh(user_names, time_day, color="skyblue")  # Swap axes here: barh for horizontal bars

    # Add labels and title
    plt.ylabel("Users")  # Change x and y labels accordingly
    plt.xlabel("Days Inactive")
    fig.suptitle(f"Top {top} Users Inactive Users (in Days)", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    # Ensure X-axis shows only integers
    plt.xticks(np.arange(0, max(time_day) + 1, step=1))

    # Add a vertical line at 7 days to indicate a threshold
    plt.axvline(x=7, color="red", linestyle="--", linewidth=2, label="7-Day Threshold")  # Swap axhline to axvline

    plt.tight_layout()  # Adjust layout to fit labels better
    return _plot_return(plt, show)


def display_user_day_week(show: bool = True, from_day: int = 3600, to_day: int = 0) -> Union[bytes, None]:
    """
    Display the user activity by weekday
    """
    data_user_activity: list[UserActivity] = fetch_all_user_activities(from_day, to_day)
    data_user_id_name: Dict[int, UserInfo] = fetch_user_info()
    users_by_weekday_dict: Dict[int, list[UserInfoWithCount]] = users_by_weekday(data_user_activity, data_user_id_name)

    from_date = datetime.now().date() - timedelta(days=from_day)
    to_date = datetime.now().date() - timedelta(days=to_day)

    # Get unique users and weekdays
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    user_ids = sorted(data_user_id_name.keys())  # Get a sorted list of user IDs
    user_names = [data_user_id_name[user_id].display_name for user_id in user_ids]  # Map user IDs to names

    # Initialize an empty matrix (len(users) x 7) for 7 days in a week
    activity_matrix = np.zeros((len(user_ids), 7))

    # Fill the matrix with user activity counts
    for weekday, users in users_by_weekday_dict.items():
        for user_info in users:
            user_idx = user_ids.index(user_info.user.id)  # Find the row corresponding to the user
            activity_matrix[user_idx, weekday] = user_info.count

    # Replace all 0 values with NaN for visualization
    activity_matrix_with_nan = np.where(activity_matrix == 0, np.nan, activity_matrix)

    # Create a heatmap
    fig, ax = plt.subplots(figsize=(20, 20))
    sns.heatmap(
        activity_matrix_with_nan,
        annot=True,
        fmt="g",
        cmap="Blues",
        xticklabels=weekdays,
        yticklabels=user_names,
        mask=np.isnan(activity_matrix_with_nan),
    )
    fig.suptitle("User Activity by Weekday", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    plt.xlabel("Weekday")
    plt.ylabel("Users")

    return _plot_return(plt, show)


def display_user_voice_per_month(show: bool = True, from_day: int = 3600, to_day: int = 0) -> Union[bytes, None]:
    """
    Graph that display the amount of time played per month using stacked bar. Each bar is a month. The stacked information if every user.
    """
    user_activities: list[UserActivity] = fetch_all_user_activities(from_day, to_day)
    data_user_id_name: Dict[int, UserInfo] = fetch_user_info()

    # Dictionary to hold total time played per user per month [month_year][user_id] = time_played
    time_played_per_month = user_times_by_month(user_activities)

    # Convert data to a pandas DataFrame for easy plotting
    df = pd.DataFrame(time_played_per_month).fillna(0)
    df = df.T  # Transpose to have months as index and users as columns

    # Calculate the total playtime per user and sort in descending order
    total_time_per_user = df.sum(axis=0)
    top_user_ids = total_time_per_user.nlargest(15).index  # Get the top 15 user IDs
    other_user_ids = total_time_per_user.index.difference(top_user_ids)  # Get all other user IDs

    # Create a new column "Other" by summing playtime for all users not in the top 15
    df["Other"] = df[other_user_ids].sum(axis=1)

    # Filter DataFrame to only include the top 15 users and the "Other" column
    df = df[top_user_ids.tolist() + ["Other"]]

    # Rename columns to include both user_id and display_name (e.g., "1 - Alice") for top users
    list_display_name = [
        data_user_id_name[int(user_id)].display_name if user_id in data_user_id_name else "Other"
        for user_id in df.columns
    ]
    df.columns = pd.Index(list_display_name)
    # Plot stacked bar chart
    df.plot(kind="bar", stacked=True, figsize=(12, 6), colormap="viridis")
    plt.xlabel("Month")
    plt.ylabel("Time Played")
    plt.title("Time Played per Month (Stacked by User)")
    plt.legend(title="User ID", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    return _plot_return(plt, show)


def display_user_timeline_voice_time_by_day(
    show: bool = True, from_day: int = 3600, to_day: int = 0
) -> Union[bytes, None]:
    """Display the user timeline voice time"""
    user_activities: list[UserActivity] = fetch_all_user_activities(from_day, to_day)
    data_user_id_name: Dict[int, UserInfo] = fetch_user_info()
    # Dictionary to store total time played per user
    user_play_times: Dict[int, float] = defaultdict(int)
    # Dictionary to store daily time played for each user
    user_daily_play_times: dict[int, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    # Temporary dictionary to hold start times
    start_times = {}

    from_date = datetime.now().date() - timedelta(days=from_day)
    to_date = datetime.now().date() - timedelta(days=to_day)

    # Parse timestamps and compute playtime
    for activity in user_activities:
        timestamp = datetime.fromisoformat(activity.timestamp)

        if activity.event == EVENT_CONNECT:
            start_times[(activity.user_id, activity.channel_id)] = timestamp
        elif activity.event == EVENT_DISCONNECT:
            start_key = (activity.user_id, activity.channel_id)
            if start_key in start_times:
                start_time = start_times.pop(start_key)
                play_duration: float = (timestamp - start_time).total_seconds() / 60  # Convert to minutes
                play_date: date = start_time.date()
                user_play_times[activity.user_id] += play_duration
                user_daily_play_times[activity.user_id][play_date] += play_duration

    # Get top 20 most active users by total play time
    top_users = sorted(user_play_times.items(), key=lambda x: x[1], reverse=True)[:20]
    top_user_ids = {user[0] for user in top_users}

    # Prepare plot
    fig, ax = plt.subplots(figsize=(12, 8))
    for user_id in top_user_ids:
        dates = sorted(user_daily_play_times[user_id].keys())
        times = [user_daily_play_times[user_id][date] for date in dates]
        user_name = data_user_id_name[user_id].display_name  # Fetch the user name
        ax.plot(dates, times, label=user_name, marker="o", linestyle="-")

    # Format plot
    ax.set_xlabel("Date")
    ax.set_ylabel("Time Played (seconds)")
    fig.suptitle("Daily Playtime for Top 20 Active Users", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1), title="User ID")
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%Y-%m-%d"))
    ax.grid(True)
    fig.autofmt_xdate()

    plt.tight_layout()
    return _plot_return(plt, show)


def iso_to_gregorian(year: int, week: int) -> datetime:
    """Convert ISO year and week to the starting date of that ISO week (Monday)."""
    return datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")


def display_user_timeline_voice_time_by_week(
    show: bool = True, from_day: int = 3600, to_day: int = 0
) -> Union[bytes, None]:
    """Display the user timeline voice time"""
    user_activities: List[UserActivity] = fetch_all_user_activities(from_day, to_day)
    data_user_id_name: Dict[int, UserInfo] = fetch_user_info()

    # Dictionary to store total time played per user
    user_play_times: Dict[int, float] = defaultdict(int)

    # Dictionary to store weekly time played for each user
    user_weekly_play_times: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    # Temporary dictionary to hold start times
    start_times = {}

    from_date = datetime.now().date() - timedelta(days=from_day)
    to_date = datetime.now().date() - timedelta(days=to_day)

    # Parse timestamps and compute playtime
    for activity in user_activities:
        timestamp = datetime.fromisoformat(activity.timestamp)

        if activity.event == EVENT_CONNECT:
            # Store the start time for the user and channel
            start_times[(activity.user_id, activity.channel_id)] = timestamp

        elif activity.event == EVENT_DISCONNECT:
            start_key = (activity.user_id, activity.channel_id)
            if start_key in start_times:
                start_time = start_times.pop(start_key)
                play_duration: float = (timestamp - start_time).total_seconds() / 60  # Convert to minutes

                week_start = f"{timestamp.isocalendar().year}-{timestamp.isocalendar().week}"
                user_weekly_play_times[activity.user_id][week_start] += play_duration
                user_play_times[activity.user_id] += play_duration  # Track total time per user

    # Get top 30 most active users by total play time
    top_users = sorted(user_play_times.items(), key=lambda x: x[1], reverse=True)[:30]

    # Identify all unique weeks across top users for consistent x-axis alignment
    all_weeks = sorted(set(week for user_data in user_weekly_play_times.values() for week in user_data.keys()))
    all_dates = [iso_to_gregorian(int(w.split("-")[0]), int(w.split("-")[1])) for w in all_weeks]
    # Prepare plot with three subplots
    fig, axs = plt.subplots(3, 1, figsize=(12, 18))
    segments = [top_users[:10], top_users[10:20], top_users[20:30]]  # Split top_users into three segments
    titles = ["Top 10 Active Users", "Users 11-20", "Users 21-30"]
    for ax, segment, title in zip(axs, segments, titles):
        for user_id, _ in segment:
            # Fill in missing weeks with zero to create a continuous line
            user_times = [user_weekly_play_times[user_id].get(week, 0) for week in all_weeks]

            if any(user_times):  # Only plot if there's data
                user_name = data_user_id_name[user_id].display_name  # Fetch the user name
                ax.plot(all_dates, user_times, label=user_name, marker="o", linestyle="-")

        # Format each subplot
        ax.set_xlabel("Week Starting (Monday)")
        ax.set_ylabel("Time Played (minutes)")
        fig.suptitle(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=16)
        ax.set_title(title, fontsize=14)

        ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1), title="User Names")
        ax.grid(True)
        fig.autofmt_xdate()

    plt.tight_layout()
    return _plot_return(plt, show)


def display_user_timeline_voice_by_months(
    show: bool = True, from_day: int = 3600, to_day: int = 0
) -> Union[bytes, None]:
    """Display the user timeline voice time"""
    user_activities: list[UserActivity] = fetch_all_user_activities(from_day, to_day)
    monthly_sessions = times_by_months(user_activities)
    monthly_sessions.plot(kind="bar", color="skyblue")
    plt.xlabel("Month")
    plt.ylabel("Total Voice Session Time (Hours)")
    plt.title("Total Voice Session Time per Month")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.tight_layout()
    return _plot_return(plt, show)


def display_user_line_graph_time(
    user_id: int, show: bool = True, from_day: int = 3600, to_day: int = 0
) -> Union[bytes, None]:
    """Display the user timeline voice time"""
    user_activities: List[UserActivity] = fetch_user_activities(user_id, from_day, to_day)
    data_user_id_name: Dict[int, UserInfo] = fetch_user_info()
    user_info = data_user_id_name[user_id]

    # Dictionary to store total time played per user
    user_play_times: float = 0.0

    # Dictionary to store weekly time played for each user
    user_weekly_play_times: Dict[str, float] = defaultdict(int)

    # Temporary dictionary to hold start times
    start_times = {}

    from_date = datetime.now().date() - timedelta(days=from_day)
    to_date = datetime.now().date() - timedelta(days=to_day)

    # Parse timestamps and compute playtime
    for activity in user_activities:
        timestamp = datetime.fromisoformat(activity.timestamp)

        if activity.event == EVENT_CONNECT:
            # Store the start time for the user and channel
            start_times[(activity.user_id, activity.channel_id)] = timestamp

        elif activity.event == EVENT_DISCONNECT:
            start_key = (activity.user_id, activity.channel_id)
            if start_key in start_times:
                start_time = start_times.pop(start_key)
                play_duration = (timestamp - start_time).total_seconds() / 60  # Convert to minutes

                week_start = f"{timestamp.isocalendar().year}-{timestamp.isocalendar().week}"
                user_weekly_play_times[week_start] += play_duration
                user_play_times += play_duration  # Track total time per user

    all_weeks = sorted(set(user_weekly_play_times.keys()))
    all_dates: list[datetime] = [iso_to_gregorian(int(w.split("-")[0]), int(w.split("-")[1])) for w in all_weeks]

    # Prepare plot with three subplots
    fig, ax = plt.subplots(figsize=(12, 8))

    # Fill in missing weeks with zero to create a continuous line
    user_times = [user_weekly_play_times.get(week, 0) for week in all_weeks]

    if any(user_times):  # Only plot if there's data
        user_name = data_user_id_name[user_id].display_name  # Fetch the user name
        plt.plot(all_dates, user_times, label=user_name, marker="o", linestyle="-")

    # Format each subplot
    plt.xlabel("Week Starting (Monday)")
    plt.ylabel("Time Played (minutes)")

    fig.suptitle(f"Weekly Time Played for {user_info.display_name} (total: {user_play_times//60} hours)", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    plt.grid(True)
    plt.tight_layout()
    return _plot_return(plt, show)


def display_user_top_operators(
    from_date: date,
    show: bool = True,
) -> Union[bytes, None]:
    """
    Generate a matrix heatmap of the top operators used by each user
    """
    users_operators_count = data_access_fetch_users_operators(from_date)
    # Extract unique users and operators
    users = sorted({item.user for item in users_operators_count})
    operators = sorted({item.operator_name for item in users_operators_count})

    # Create a mapping for indexing
    user_index = {name: i for i, name in enumerate(users)}
    operator_index = {name: i for i, name in enumerate(operators)}

    # Create a matrix for counts
    matrix = np.zeros((len(operators), len(users)))

    # Populate the matrix
    for item in users_operators_count:
        row = operator_index[item.operator_name]
        col = user_index[item.user]
        matrix[row, col] = item.count

    # Plot the heatmap
    fig, ax = plt.subplots(figsize=(16, 10))
    cax = ax.imshow(matrix, cmap="Blues", aspect="auto")

    # Set axis labels
    ax.set_xticks(np.arange(len(users)))
    ax.set_yticks(np.arange(len(operators)))
    ax.set_xticklabels(users, rotation=45, ha="right")
    ax.set_yticklabels(operators)

    # Add operator names on the right side
    ax2 = ax.twinx()
    ax2.set_yticks(np.arange(len(operators)))
    ax2.set_yticklabels(operators)
    ax2.set_ylim(ax.get_ylim())  # Align y-axis

    # Display values on heatmap
    for i in range(len(operators)):
        for j in range(len(users)):
            if matrix[i, j] > 0:  # Only display nonzero values
                ax.text(
                    j,
                    i,
                    str(matrix[i, j]),
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="black" if matrix[i, j] < matrix.max() / 2 else "white",
                )
    # Add vertical and horizontal grid lines
    ax.set_xticks(np.arange(len(users)) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(operators)) - 0.5, minor=True)
    ax.grid(which="minor", color="gray", linestyle="-", linewidth=0.5)
    ax.tick_params(which="minor", size=0)  # Hide minor ticks

    # Colorbar
    cbar = fig.colorbar(cax)
    cbar.ax.tick_params(labelsize=12)

    ax.set_xlabel("Users", fontsize=12)
    ax.set_ylabel("Operators", fontsize=12)
    fig.suptitle("Top User-Operator Count Heatmap", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}", fontsize=14)
    return _plot_return(plt, show)


def display_user_rank_match_played_server(
    from_date: datetime,
    to_date: datetime,
    show: bool = True,
) -> Union[bytes, None]:
    """
    Show how much of rank matches played by each user in the server
    """
    data = data_access_fetch_win_rate_server(from_date, to_date)
    # Extract names and values
    (
        names,
        total_rank_matches,
        matches_count_in_circus,
        win_rate_circus,
        win_rate_not_circus,
        rate_play_in_circus,
    ) = zip(*data)

    # Define colors based on value thresholds
    colors = []
    for v in rate_play_in_circus:
        v_percentage = float(v)  # Convert to percentage
        if v_percentage >= 80:
            colors.append("green")
        elif v_percentage >= 65:
            colors.append("purple")
        elif v_percentage >= 50:
            colors.append("blue")
        else:
            colors.append("red")

    # Create horizontal bar chart
    fig, ax = plt.subplots(figsize=(12, 8))
    y_pos = np.arange(len(names))

    # Set x-axis ticks every 5%
    ax.set_xticks(np.arange(0, 105, 5))
    ax.set_xticklabels([f"{int(x)}%" for x in np.arange(0, 105, 5)])

    # Plot bars with individual colors
    ax.barh(y_pos, rate_play_in_circus, color=colors)

    # Add vertical reference line at 50%
    ax.axvline(50, color="blue", linestyle="--", linewidth=1, label="50%")
    ax.axvline(65, color="purple", linestyle="--", linewidth=1, label="65%")
    ax.axvline(80, color="green", linestyle="--", linewidth=1, label="80%")

    # Set labels and title
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=10)
    ax.set_xlabel("Rate", fontsize=12)
    fig.suptitle("User Percentage Playing Rank in Circus Maximus", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    # Add legend
    ax.legend()

    return _plot_return(plt, show)


def display_user_rank_match_win_rate_played_server(
    from_date: date,
    to_date: date,
    show: bool = True,
) -> Union[bytes, None]:
    """
    Show how much of rank matches played by each user in the server
    """
    data = data_access_fetch_win_rate_server(from_date, to_date)
    data = sorted(data, key=lambda x: x[3], reverse=True)
    # Extract names and values
    (
        names,
        total_rank_matches,
        matches_count_in_circus,
        win_rate_circus,
        win_rate_not_circus,
        rate_play_in_circus,
    ) = zip(*data)

    # Convert values to float if needed
    win_rate_circus_float: List[float] = [float(v) for v in win_rate_circus]
    win_rate_not_circus_float: List[float] = [float(v) for v in win_rate_not_circus]

    names_with_star: List[str] = [
        f"{name} *" if win_rate_circus_float[i] > win_rate_not_circus_float[i] else name for i, name in enumerate(names)
    ]

    # Define bar width and y positions
    y_pos = np.arange(len(names_with_star))
    bar_width = 0.4  # Controls spacing between bars

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(16, 12))

    # Plot bars
    ax.barh(y_pos - bar_width / 2, win_rate_circus_float, height=bar_width, color="green", label="Win Rate in Circus")
    ax.barh(
        y_pos + bar_width / 2, win_rate_not_circus_float, height=bar_width, color="red", label="Win Rate Not in Circus"
    )

    # Add vertical reference line at 50%
    ax.axvline(50, color="blue", linestyle="--", linewidth=1, label="50% Reference")

    # Set labels and title
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names_with_star, fontsize=10)
    ax.set_xlabel("Win Rate", fontsize=12)
    fig.suptitle("User Win Rate in and outside Circus Maximus", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    # Add legend
    ax.legend()

    return _plot_return(plt, show)
