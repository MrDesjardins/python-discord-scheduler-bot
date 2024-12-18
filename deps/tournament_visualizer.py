""" Generate an image of a tournament bracket """

import io
import matplotlib.pyplot as plt
from matplotlib.patches import ConnectionPatch

from deps.analytic_data_access import fetch_user_info
from deps.tournament_models import TournamentNode
from deps.tournament_data_class import Tournament
from deps.values import COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT


def get_name(user_id: str, users_map: dict) -> str:
    """
    Get the name of a user
    """
    if user_id in users_map:
        return users_map[user_id].display_name[:8]
    return user_id


def _plot_return(plot: plt, show: bool = True):
    """
    Return an image or the bytes of the iamge
    """
    if show:
        # plot.show()
        plot.savefig("bracket.png", format="png")
        return None

    buf = io.BytesIO()
    plot.savefig(buf, format="png")
    buf.seek(0)

    # Get the bytes data
    image_bytes = buf.getvalue()
    buf.close()
    return image_bytes


def plot_tournament_bracket(tournament: Tournament, root: TournamentNode, show: bool = True):
    """
    Generates an image of a tournament bracket from the root node of a tree.

    Args:
        tournament (Tournament): The tournament object containing metadata (name, dates).
        root (TournamentNode): The root node of the tournament tree.
        show (bool): Whether to display the plot or return the figure and axis.
    """
    users_map = fetch_user_info()
    positions = {}
    labels = {}
    node_lookup = {}
    max_depth = 0
    node_count = 0

    def traverse(node: TournamentNode, depth: int, x_offset: float):
        nonlocal max_depth, node_count

        if node is None:
            return x_offset

        max_depth = max(max_depth, depth)
        node_count += 1

        # Store the current node in the lookup
        node_lookup[node.id] = node

        # Traverse left and right child nodes to determine their positions
        left_x = traverse(node.next_game1, depth + 1, x_offset)
        right_x = traverse(node.next_game2, depth + 1, left_x + 5)  # Increase the gap to allow for longer names

        # Assign the current node's position based on its children
        current_x = (left_x + right_x) / 2 if node.next_game1 or node.next_game2 else x_offset

        # Store position and label
        if node.user1_id is None:
            user1_name = "N/A"
        else:
            user1_name = (
                get_name(node.user1_id, users_map)
                if node.user1_id != node.user_winner_id
                else f"*{ get_name(node.user1_id, users_map)}*"
            )
        if node.user2_id is None:
            user2_name = "N/A"
        else:
            user2_name = (
                get_name(node.user2_id, users_map)
                if node.user2_id != node.user_winner_id
                else f"*{ get_name(node.user2_id, users_map)}*"
            )

        labels[node.id] = (
            f"{user1_name} vs {user2_name}\n{node.map} - {node.score if node.score is not None else '0-0'}"
        )

        positions[node.id] = (depth, current_x)
        return current_x

    # Traverse the tree starting from the root node
    traverse(root, depth=0, x_offset=0)

    # Dynamically scale figure size based on tree dimensions
    fig_width = max(node_count * 0.8, 15)  # Minimum width of 15
    fig_height = max_depth * 2  # Scale height based on depth
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    # Adjust layout to include the title
    fig.subplots_adjust(top=0.9)  # Adjust top to make room for the title

    ax.axis("off")

    # Reverse y-axis to place the root at the top
    ax.invert_yaxis()

    # Adjust axis limits to fit all nodes with more spacing
    x_positions = [pos[1] for pos in positions.values()]
    y_positions = [-pos[0] for pos in positions.values()]  # Negate depth for inverted y-axis
    ax.set_xlim(min(x_positions) - 2, max(x_positions) + 2)  # Add horizontal padding
    ax.set_ylim(min(y_positions) - 1, max(y_positions) + 1)  # Add vertical padding

    # Plot the nodes and connections
    for node_id, (depth, x_pos) in positions.items():
        # Fetch the actual node object
        node = node_lookup[node_id]

        # Determine background color based on winner presence
        bgcolor = "lightgreen" if node.user_winner_id else "white"

        # Format label with bolded winner
        if node.user_winner_id:
            label = labels[node_id].replace(f"<b>{node.user_winner_id}</b>", f"{node.user_winner_id}", 1)
        else:
            label = labels[node_id]

        # Draw the current node
        ax.text(
            x_pos,
            -depth,
            label,
            ha="center",
            va="center",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor=bgcolor),
        )

        # Draw connections to child nodes
        if node.next_game1:
            child_pos = positions[node.next_game1.id]
            con = ConnectionPatch(
                xyA=(x_pos, -depth),
                xyB=(child_pos[1], -child_pos[0]),
                coordsA="data",
                coordsB="data",
                arrowstyle="-",
                color="black",
            )
            ax.add_artist(con)

        if node.next_game2:
            child_pos = positions[node.next_game2.id]
            con = ConnectionPatch(
                xyA=(x_pos, -depth),
                xyB=(child_pos[1], -child_pos[0]),
                coordsA="data",
                coordsB="data",
                arrowstyle="-",
                color="black",
            )
            ax.add_artist(con)

    # Add tournament title with adjusted padding
    ax.set_title(
        f"Tournament: {tournament.name}",
        fontsize=16,
        weight="bold",
        loc="center",
        pad=0,
    )

    # Add footer with start and end dates
    footer_text = f"Start Date: {tournament.start_date.strftime('%Y-%m-%d')}, End Date: {tournament.end_date.strftime('%Y-%m-%d')}"
    fig.text(0.5, 0.02, footer_text, ha="center", fontsize=12, color="gray")
    footer_text2 = f"Use the command /{COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT} to report a lost match"
    fig.text(0.5, 0.10, footer_text2, ha="center", fontsize=12, color="gray")
    return _plot_return(plt, show)
