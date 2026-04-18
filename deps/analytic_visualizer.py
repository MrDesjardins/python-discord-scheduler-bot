"""
Code to show the relationsip between the users
"""

import io
from collections import Counter, defaultdict
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple, Union, cast
import plotly.graph_objs as go  # type: ignore
import seaborn as sns
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.dates import DateFormatter, AutoDateLocator
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
    data_access_fetch_unique_user_per_day,
    data_access_fetch_users_operators,
    data_access_fetch_win_rate_server,
    fetch_all_user_activities,
    fetch_user_activities,
    fetch_user_info,
    calculate_time_spent_from_db,
)
from deps.system_database import EVENT_CONNECT, EVENT_DISCONNECT, database_manager
from deps.functions_date import iso_to_gregorian


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


def _add_voice_minutes_across_iso_weeks(
    user_weekly_play_times: dict[int, dict[str, float]],
    user_id: int,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """
    Spread each voice session across ISO weeks (Mon 00:00 UTC boundary).

    Previously the chart credited the entire session to the disconnect's week only,
    which made long sessions (or AFK in one channel) look like a single huge spike.
    """
    if end_time <= start_time:
        return
    t = start_time
    end_t = end_time
    if t.tzinfo is None and end_t.tzinfo is not None:
        t = t.replace(tzinfo=end_t.tzinfo)
    elif end_t.tzinfo is None and t.tzinfo is not None:
        end_t = end_t.replace(tzinfo=t.tzinfo)

    guard = 0
    while t < end_t and guard < 5000:
        guard += 1
        year, week, _ = t.isocalendar()
        monday_naive = datetime.strptime(f"{year}-W{week}-1", "%G-W%V-%u")
        monday = monday_naive.replace(tzinfo=t.tzinfo) if t.tzinfo is not None else monday_naive
        next_monday = monday + timedelta(days=7)
        seg_end = min(end_t, next_monday)
        minutes = max(0.0, (seg_end - t).total_seconds() / 60.0)
        if minutes > 0:
            user_weekly_play_times[user_id][f"{year}-{week}"] += minutes
        if seg_end <= t:
            break
        t = seg_end


def _add_voice_minutes_across_calendar_days(
    user_daily_play_times: dict[int, dict[date, float]],
    user_id: int,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """Spread session minutes across calendar dates (midnight boundary in the session timestamps' tz)."""
    if end_time <= start_time:
        return
    t = start_time
    end_t = end_time
    if t.tzinfo is None and end_t.tzinfo is not None:
        t = t.replace(tzinfo=end_t.tzinfo)
    elif end_t.tzinfo is None and t.tzinfo is not None:
        end_t = end_t.replace(tzinfo=t.tzinfo)

    guard = 0
    while t < end_t and guard < 5000:
        guard += 1
        d = t.date()
        next_mid = datetime.combine(d + timedelta(days=1), time.min)
        if t.tzinfo is not None:
            next_mid = next_mid.replace(tzinfo=t.tzinfo)
        seg_end = min(end_t, next_mid)
        minutes = max(0.0, (seg_end - t).total_seconds() / 60.0)
        if minutes > 0:
            user_daily_play_times[user_id][d] += minutes
        if seg_end <= t:
            break
        t = seg_end


def display_graph_cluster_people(show: bool = True, from_day: int = 3600, to_day: int = 0) -> Union[bytes, None]:
    """
    Clusters from co-voice time (Louvain) with a layout and styling that highlight subgroups.
    """
    data = _get_data(from_day, to_day)
    from_date = datetime.now().date() - timedelta(days=from_day)
    to_date = datetime.now().date() - timedelta(days=to_day)

    if not data:
        plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, "No co-voice pairs above 1h for this period.", ha="center", va="center")
        plt.axis("off")
        return _plot_return(plt, show)

    (users_uni_direction, _max_weight) = get_unidirection_users(data)

    # Undirected seconds-together; merge (u,v) and (v,u) from directional dict
    edge_weights_sec: Dict[Tuple[int, int], float] = defaultdict(float)
    for u, neighbors in users_uni_direction.items():
        for v, w in neighbors.items():
            a, b = (u, v) if u < v else (v, u)
            edge_weights_sec[(a, b)] += float(w)

    users_name: Dict[int, str] = {}
    for user in data:
        users_name[user.user1_id] = user.user1_display_name
        users_name[user.user2_id] = user.user2_display_name

    graph_network: nx.Graph = nx.Graph()
    max_sec = max(edge_weights_sec.values()) if edge_weights_sec else 1.0
    for (u, v), sec in edge_weights_sec.items():
        graph_network.add_edge(u, v, weight=sec, together_sec=sec)

    if graph_network.number_of_nodes() == 0:
        plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, "No graph nodes for this period.", ha="center", va="center")
        plt.axis("off")
        return _plot_return(plt, show)

    partition = community_louvain.best_partition(graph_network, weight="weight")
    communities_sorted = sorted(set(partition.values()))
    n_comm = len(communities_sorted)

    cmap = plt.colormaps["tab20"]
    if n_comm > 20:
        cmap = plt.colormaps["hsv"]

    def color_for_community(cid: int) -> Any:
        if n_comm > 20:
            return cast(Any, cmap(cid / max(n_comm, 1)))
        return cast(Any, cmap((cid % 20) / 20.0))

    n_nodes = max(graph_network.number_of_nodes(), 1)
    pos = nx.spring_layout(
        graph_network,
        weight="weight",
        k=2.4 / np.sqrt(n_nodes),
        iterations=220,
        seed=42,
    )

    degree_pairs = cast(Iterable[Tuple[Any, Any]], graph_network.degree(weight="weight"))
    strengths = {node: float(weight) for node, weight in degree_pairs}
    max_strength = max(strengths.values()) if strengths else 1.0

    fig, ax = plt.subplots(figsize=(20, 18))
    ax.set_facecolor("#f7f7f8")

    intra: List[Tuple[int, int, Dict[str, Any]]] = []
    inter: List[Tuple[int, int, Dict[str, Any]]] = []
    for u, v, ed in graph_network.edges(data=True):
        if partition[u] == partition[v]:
            intra.append((u, v, ed))
        else:
            inter.append((u, v, ed))

    def edge_linewidth(sec: float) -> float:
        t = (sec / max_sec) ** 0.55
        return 0.35 + 4.2 * t

    for u, v, ed in inter:
        sec = float(ed.get("together_sec", ed.get("weight", 0.0)))
        xdata = (pos[u][0], pos[v][0])
        ydata = (pos[u][1], pos[v][1])
        ax.plot(
            xdata,
            ydata,
            color="#9aa0a6",
            alpha=0.28,
            linewidth=edge_linewidth(sec) * 0.55,
            solid_capstyle="round",
            zorder=1,
        )

    for u, v, ed in intra:
        sec = float(ed.get("together_sec", ed.get("weight", 0.0)))
        cid = partition[u]
        xdata = (pos[u][0], pos[v][0])
        ydata = (pos[u][1], pos[v][1])
        ax.plot(
            xdata,
            ydata,
            color=color_for_community(cid),
            alpha=0.55 + 0.35 * (sec / max_sec) ** 0.5,
            linewidth=edge_linewidth(sec),
            solid_capstyle="round",
            zorder=2,
        )

    for node in graph_network.nodes():
        cid = partition[node]
        size = 320 + 1450 * (strengths.get(node, 0.0) / max_strength) ** 0.5
        ax.scatter(
            pos[node][0],
            pos[node][1],
            s=size,
            c=[color_for_community(cid)],
            edgecolors="#1a1a1a",
            linewidths=0.6,
            zorder=3,
        )

    def short_label(uid: int) -> str:
        name = users_name.get(uid, str(uid))
        return name if len(name) <= 18 else f"{name[:16]}…"

    for node in graph_network.nodes():
        ax.annotate(
            short_label(node),
            (pos[node][0], pos[node][1]),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="#0b3d6d",
            zorder=4,
        )

    comm_counts = Counter(partition.values())
    legend_patches: List[Patch] = []
    for cid in communities_sorted[:18]:
        legend_patches.append(
            Patch(
                facecolor=color_for_community(cid),
                edgecolor="#333333",
                linewidth=0.5,
                label=f"Subgroup {cid + 1} — {comm_counts[cid]} people",
            )
        )
    if n_comm > 18:
        legend_patches.append(Patch(facecolor="#cccccc", label=f"… +{n_comm - 18} more subgroups"))

    ax.legend(
        handles=legend_patches,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=True,
        fontsize=9,
        title="Louvain clusters\n(co-voice time)",
        title_fontsize=10,
    )

    ax.set_title(
        "Thicker, brighter lines = more hours in voice together. Same color = same subgroup; gray = ties across subgroups.\n"
        f"Window: {from_date} → {to_date}",
        fontsize=11,
        pad=12,
    )
    fig.suptitle("Community map — who hangs out in voice together", fontsize=16, y=0.995)
    ax.axis("off")
    plt.tight_layout(rect=(0.0, 0.0, 0.84, 0.96))
    return _plot_return(plt, show)


def _plot_return(plot: Any, show: bool = True) -> Union[bytes, None]:
    """
    Return an image or the bytes of the iamge
    """
    if show:
        plot.show()
        return None

    buf = io.BytesIO()
    if hasattr(plot, "write_image"):
        try:
            plot.write_image(buf, format="png")
        except ValueError:
            buf.close()
            return None
    else:
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
    graph_network: nx.Graph = nx.Graph()

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
    data_for_plot.sort(key=lambda x: float(cast(Any, x["weight"])), reverse=True)
    # Get the top 20
    data_for_plot = data_for_plot[:top]

    # Create a bar chart
    fig, ax = plt.subplots(figsize=(10, 10))

    # Get the names
    names = [f"{user['user1']} - {user['user2']}" for user in data_for_plot]
    # Get the weights
    weights = [float(cast(Any, user["weight"])) / 3600 for user in data_for_plot]
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

    # Create the bar plot (horizontal: user names on y-axis, time on x-axis)
    fig, ax = plt.subplots(figsize=(10, 8))

    plt.barh(users_display_name, times_in_hours, color="skyblue")

    # Add labels and title
    plt.xlabel("Total Time (Hours)")
    plt.ylabel("Users")
    fig.suptitle(f"Top {top} Users by Total Voice Channel Time (in Hours)", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    plt.yticks(fontsize=8)
    plt.gca().invert_yaxis()  # Highest voice time at the top
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

    # Convert data to a pandas DataFrame for easy plotting (stored values are seconds → hours)
    df = pd.DataFrame(time_played_per_month).fillna(0)
    df = df.T / 3600.0  # Transpose to have months as index and users as columns; seconds → hours

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
    plt.ylabel("Time Played (hours)")
    plt.title("Time Played per Month (Stacked by User)")
    plt.legend(title="Users", bbox_to_anchor=(1.05, 1), loc="upper left")
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
                user_play_times[activity.user_id] += play_duration
                _add_voice_minutes_across_calendar_days(user_daily_play_times, activity.user_id, start_time, timestamp)

    # Get top 20 most active users by total play time
    top_users = sorted(user_play_times.items(), key=lambda x: x[1], reverse=True)[:20]
    top_user_ids = {user[0] for user in top_users}

    # Prepare plot
    fig, ax = plt.subplots(figsize=(12, 8))
    for user_id in top_user_ids:
        dates = sorted(user_daily_play_times[user_id].keys())
        times = [user_daily_play_times[user_id][date] for date in dates]
        user_name = data_user_id_name[user_id].display_name  # Fetch the user name
        ax.plot(cast(Any, dates), times, label=user_name, marker="o", linestyle="-")

    # Format plot
    ax.set_xlabel("Date")
    ax.set_ylabel("Time Played (minutes)")
    fig.suptitle("Daily Playtime for Top 20 Active Users", fontsize=16)
    ax.set_title(f"From {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}", fontsize=14)

    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1), title="Users")
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%Y-%m-%d"))
    ax.grid(True)
    fig.autofmt_xdate()

    plt.tight_layout()
    return _plot_return(plt, show)


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
                user_play_times[activity.user_id] += play_duration  # Track total time per user
                _add_voice_minutes_across_iso_weeks(user_weekly_play_times, activity.user_id, start_time, timestamp)

    # Get top 30 most active users by total play time
    top_users = sorted(user_play_times.items(), key=lambda x: x[1], reverse=True)[:30]

    # Identify all unique weeks across top users for consistent x-axis alignment
    all_weeks = sorted(set(week for user_data in user_weekly_play_times.values() for week in user_data.keys()))
    all_dates = [iso_to_gregorian(int(w.split("-")[0]), int(w.split("-")[1])) for w in all_weeks]
    all_dates.sort()
    # Prepare plot with three subplots
    fig, axs = plt.subplots(3, 1, figsize=(18, 18))
    segments = [top_users[:10], top_users[10:20], top_users[20:30]]  # Split top_users into three segments
    titles = ["Top 10 Active Users", "Users 11-20", "Users 21-30"]
    for ax, segment, title in zip(axs, segments, titles):
        for user_id, _ in segment:
            # Fill in missing weeks with zero to create a continuous line

            user_times = [
                user_weekly_play_times[user_id].get(f"{timestamp.isocalendar().year}-{timestamp.isocalendar().week}", 0)
                for timestamp in all_dates
            ]
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
                user_play_times += play_duration  # Track total time per user
                tmp_weekly: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
                _add_voice_minutes_across_iso_weeks(tmp_weekly, activity.user_id, start_time, timestamp)
                for wk, mins in tmp_weekly[activity.user_id].items():
                    user_weekly_play_times[wk] += mins

    all_weeks = sorted(set(user_weekly_play_times.keys()))

    all_dates: list[datetime] = [iso_to_gregorian(int(w.split("-")[0]), int(w.split("-")[1])) for w in all_weeks]
    # Sort dates in ascending order
    all_dates.sort()

    # Prepare plot with three subplots
    fig, ax = plt.subplots(figsize=(12, 8))

    # Fill in missing weeks with zero to create a continuous line
    user_times = [
        user_weekly_play_times.get(f"{timestamp.isocalendar().year}-{timestamp.isocalendar().week}", 0)
        for timestamp in all_dates
    ]

    if any(user_times):  # Only plot if there's data
        user_name = data_user_id_name[user_id].display_name  # Fetch the user name
        plt.plot(cast(Any, all_dates), user_times, label=user_name, marker="o", linestyle="-")

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
                    str(int(matrix[i, j])),
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


def display_unique_user_per_day(from_date: datetime, show: bool = True) -> Union[bytes, None]:
    """Bar chart of distinct users seen in voice per day, from from_date through today."""
    rows = data_access_fetch_unique_user_per_day(from_date)

    # Parse data
    dates_str = [row[0] for row in rows]
    counts = [row[1] for row in rows]
    dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates_str]

    # Calendar quarter starts (Jan / Apr / Jul / Oct)
    quarter_starts: list[date] = []
    for d in dates:
        if d.month in (1, 4, 7, 10) and d.day == 1:
            quarter_starts.append(d)
    quarter_starts = sorted(quarter_starts)

    # Plot
    fig, ax = plt.subplots(figsize=(20, 10))
    ax.bar(cast(Any, dates), counts, color="skyblue")
    ax.set_xlabel("Date")
    ax.set_ylabel("Unique Users Connected")
    ax.set_title("Daily Unique Online Users")

    # Format x-axis
    ax.xaxis.set_major_locator(AutoDateLocator())
    ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)

    # Add vertical lines for quarters
    for q_date in quarter_starts:
        ax.axvline(cast(Any, q_date), color="red", linestyle="--", linewidth=1)
        ax.text(
            cast(Any, q_date),
            max(counts) * 0.90,
            f"Y{q_date.year-2015}S{((q_date.month-1)//3)+1}",
            rotation=90,
            color="red",
            verticalalignment="bottom",
        )

    plt.tight_layout()
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    return _plot_return(plt, show)
