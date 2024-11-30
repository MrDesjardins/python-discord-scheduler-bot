"""
Code to show the relationsip between the users
"""

import io
from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Tuple
import plotly.graph_objs as go
import seaborn as sns
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import community as community_louvain
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
from deps.analytic_data_access import fetch_user_activities, fetch_user_info, calculate_time_spent_from_db
from deps.analytic_database import EVENT_CONNECT, EVENT_DISCONNECT, database_manager


@dataclass
class UsersRelationship:
    user1_id: int
    user2_id: int
    user1_display_name: str
    user2_display_name: str
    weight: int


def get_unidirection_users(data: List[UsersRelationship]) -> Tuple[Dict[str, Dict[str, int]], int]:
    users_uni_direction: Dict[str, Dict[str, int]] = {}
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
    SELECT ui1.id as user1_id, ui2.id as user2_id, ui1.display_name as user1_display_name, ui2.display_name as user2_display_name, weight 
    FROM user_weights 
    left join user_info as ui1 on user_weights.user_a = ui1.id 
    left join user_info as ui2 on user_weights.user_b = ui2.id
    """
    )
    return [UsersRelationship(*row) for row in database_manager.get_cursor().fetchall()]


# def display_graph_network_relationship(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
#     """
#     Display the relationship between users in a graph
#     """
#     data = _get_data(from_day, to_day)

#     # Create a graph using NetworkX
#     graph_network = nx.Graph()

#     # Create a structure that store users unidirectional to add the weight from both sides (user1, user2) and (user2, user1)
#     (users_uni_direction, max_weight) = get_unidirection_users(data)

#     # Get the names of the users
#     users_name: Dict[int, str] = {}
#     for user in data:
#         users_name[user.user1_id] = user.user1_display_name
#         users_name[user.user2_id] = user.user2_display_name

#     # Add edges with weights between users
#     for user_1_id, value in users_uni_direction.items():
#         for user_2_id, weight in value.items():
#             normalized_weight = (weight / max_weight) * 100  # Normalize to max 100
#             graph_network.add_edge(users_name[user_1_id], users_name[user_2_id], weight=normalized_weight)

#     # Draw the graph
#     plt.figure(figsize=(10, 10))

#     # Position the nodes using the spring layout for a better spread
#     pos = nx.spring_layout(graph_network)

#     # Draw nodes
#     nx.draw_networkx_nodes(graph_network, pos, node_size=700, node_color="skyblue")

#     # Draw edges, adjusting width based on the weight
#     weights = nx.get_edge_attributes(graph_network, "weight")
#     nx.draw_networkx_edges(graph_network, pos, width=[w / 10 for w in weights.values()])

#     # Draw labels for users (nodes)
#     nx.draw_networkx_labels(graph_network, pos, font_size=12, font_family="sans-serif")

#     # Draw edge labels (weights)
#     nx.draw_networkx_edge_labels(graph_network, pos, edge_labels={k: f"{v:.2f}" for k, v in weights.items()})

#     # Show plot
#     plt.title("User Relationship Graph (Edge Tickness = More Time Together)")
#     plt.axis("off")  # Turn off the axis
#     return _plot_return(plt, show)


def display_graph_cluster_people(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
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
            normalized_weight = (weight / max_weight) * 100  # Normalize to max 100
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
    nx.draw_networkx_edges(graph_network, pos, width=[w / 10 for w in normalized_weights.values()])

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
    nx.draw_networkx_edge_labels(
        graph_network,
        pos,
        edge_labels={k: f"{v:.2f}" for k, v in normalized_weights.items()},
    )

    # Show plot
    plt.title("User Relationship Graph with Clusters (Edge Tickness = More Time Together)")
    plt.axis("off")  # Turn off the axis
    plt.legend()
    return _plot_return(plt, show)


def _plot_return(plot: plt, show: bool = True):
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


def display_graph_cluster_people_3d_animated(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
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


def display_time_relationship(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    top = 50
    data = _get_data(from_day, to_day)

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
    plt.figure(figsize=(10, 10))
    # Get the names
    names = [f"{user['user1']} - {user['user2']}" for user in data_for_plot]
    # Get the weights
    weights = [(user["weight"] / 3600) for user in data_for_plot]
    # Create the bar chart
    plt.barh(names, weights)
    plt.xlabel("Hours spent together")
    plt.ylabel("User pairs")
    plt.title(f"Top {top} user pairs with the most time spent together")
    plt.xticks(fontsize=10)  # Reduce x-axis font size if needed
    plt.yticks(fontsize=8)  # Reduce y-axis font size to fit long names
    plt.gca().invert_yaxis()  # Invert the y-axis to have larger weights at the top
    plt.tight_layout()  # Automatically adjust layout to prevent truncatio
    return _plot_return(plt, show)


def display_time_voice_channel(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    top = 30
    data_user_activity = fetch_user_activities(from_day, to_day)
    data_user_id_name = fetch_user_info()

    auser_in_outs = computer_users_voice_in_out(data_user_activity)
    user_times = compute_users_voice_channel_time_sec(auser_in_outs)

    # Convert seconds to hours for all users
    user_times_in_hours = {user: time_sec / 3600 for user, time_sec in user_times.items()}

    # Sort users by total time in descending order and select the top N
    sorted_users = sorted(user_times_in_hours.items(), key=lambda x: x[1], reverse=True)[:top]

    # Unpack the sorted list into two lists: one for user names and one for times
    users, times_in_hours = zip(*sorted_users)
    users = [data_user_id_name[user_id].display_name for user_id in users]  # Convert user

    # Create the bar plot
    plt.figure(figsize=(12, 6))
    plt.bar(users, times_in_hours, color="skyblue")

    # Add labels and title
    plt.xlabel("Users")
    plt.ylabel("Total Time (Hours)")
    plt.title(f"Top {top} Users by Total Voice Channel Time (in Hours)")
    plt.xticks(rotation=90)  # Rotate user names for better readability
    plt.tight_layout()  # Adjust layout to fit labels better
    return _plot_return(plt, show)


def display_inactive_user(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    top = 50
    data_user_activity = fetch_user_activities(from_day, to_day)
    data_user_id_name = fetch_user_info()

    auser_in_outs = computer_users_voice_in_out(data_user_activity)
    user_times = users_last_played_over_day(auser_in_outs)

    # Sort users by total time in descending order and select the top N
    sorted_users = sorted(user_times.items(), key=lambda x: x[1], reverse=True)[:top]

    # Unpack the sorted list into two lists: one for user names and one for times
    user_ids, time_day = zip(*sorted_users)
    user_names = [data_user_id_name[user_id].display_name for user_id in user_ids]  # Convert user

    # Create the bar plot
    plt.figure(figsize=(10, 6))
    plt.bar(user_names, time_day, color="skyblue")

    # Add labels and title
    plt.xlabel("Users")
    plt.ylabel("Days Inactive")
    plt.title(f"Top {top} Users Inactive Users (in Days)")
    plt.xticks(rotation=90)  # Rotate user names for better readability
    # Ensure Y-axis shows only integers
    plt.yticks(np.arange(0, max(time_day) + 1, step=1))
    # Add a horizontal line at 7 days to indicate a threshold
    plt.axhline(y=7, color="red", linestyle="--", linewidth=2, label="7-Day Threshold")
    plt.tight_layout()  # Adjust layout to fit labels better
    return _plot_return(plt, show)


def display_user_day_week(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    data_user_activity: list[UserActivity] = fetch_user_activities(from_day, to_day)
    data_user_id_name: Dict[int, UserInfo] = fetch_user_info()
    users_by_weekday_dict: Dict[int, list[UserInfoWithCount]] = users_by_weekday(data_user_activity, data_user_id_name)
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
    plt.figure(figsize=(20, 20))
    sns.heatmap(
        activity_matrix_with_nan,
        annot=True,
        fmt="g",
        cmap="Blues",
        xticklabels=weekdays,
        yticklabels=user_names,
        mask=np.isnan(activity_matrix_with_nan),
    )
    plt.title("User Activity by Weekday")
    plt.xlabel("Weekday")
    plt.ylabel("Users")

    return _plot_return(plt, show)


def display_user_voice_per_month(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    """
    Graph that display the amount of time played per month using stacked bar. Each bar is a month. The stacked information if every user.
    """
    user_activities: list[UserActivity] = fetch_user_activities(from_day, to_day)
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
    df.columns = [
        f"{data_user_id_name[user_id].display_name}" if user_id in data_user_id_name else "Other"
        for user_id in df.columns
    ]
    print(df)
    # Plot stacked bar chart
    df.plot(kind="bar", stacked=True, figsize=(12, 6), colormap="viridis")
    plt.xlabel("Month")
    plt.ylabel("Time Played")
    plt.title("Time Played per Month (Stacked by User)")
    plt.legend(title="User ID", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    return _plot_return(plt, show)


def display_user_timeline_voice_time_by_day(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    """Display the user timeline voice time"""
    user_activities: list[UserActivity] = fetch_user_activities(from_day, to_day)
    data_user_id_name: Dict[int, UserInfo] = fetch_user_info()
    # Dictionary to store total time played per user
    user_play_times = defaultdict(int)
    # Dictionary to store daily time played for each user
    user_daily_play_times = defaultdict(lambda: defaultdict(int))
    # Temporary dictionary to hold start times
    start_times = {}

    # Parse timestamps and compute playtime
    for activity in user_activities:
        timestamp = datetime.fromisoformat(activity.timestamp)

        if activity.event == EVENT_CONNECT:
            start_times[(activity.user_id, activity.channel_id)] = timestamp
        elif activity.event == EVENT_DISCONNECT:
            start_key = (activity.user_id, activity.channel_id)
            if start_key in start_times:
                start_time = start_times.pop(start_key)
                play_duration = (timestamp - start_time).total_seconds() / 60  # Convert to minutes
                play_date = start_time.date()
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
    ax.set_title("Daily Playtime for Top 20 Active Users")
    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1), title="User ID")
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%Y-%m-%d"))
    ax.grid(True)
    fig.autofmt_xdate()

    plt.tight_layout()
    return _plot_return(plt, show)


def iso_to_gregorian(year: int, week: int) -> datetime:
    """Convert ISO year and week to the starting date of that ISO week (Monday)."""
    return datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")


def display_user_timeline_voice_time_by_week(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    """Display the user timeline voice time"""
    user_activities: List[UserActivity] = fetch_user_activities(from_day, to_day)
    data_user_id_name: Dict[int, UserInfo] = fetch_user_info()

    # Dictionary to store total time played per user
    user_play_times = defaultdict(int)

    # Dictionary to store weekly time played for each user
    user_weekly_play_times = defaultdict(lambda: defaultdict(int))

    # Temporary dictionary to hold start times
    start_times = {}

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

                week_start = f"{timestamp.year}-{timestamp.isocalendar().week}"
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
        ax.set_title(title)
        ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1), title="User Names")
        ax.grid(True)
        fig.autofmt_xdate()

    plt.tight_layout()
    return _plot_return(plt, show)


def display_user_timeline_voice_by_months(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    """Display the user timeline voice time"""
    user_activities: list[UserActivity] = fetch_user_activities(from_day, to_day)
    monthly_sessions = times_by_months(user_activities)
    monthly_sessions.plot(kind="bar", color="skyblue")
    plt.xlabel("Month")
    plt.ylabel("Total Voice Session Time (Hours)")
    plt.title("Total Voice Session Time per Month")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.tight_layout()
    return _plot_return(plt, show)
