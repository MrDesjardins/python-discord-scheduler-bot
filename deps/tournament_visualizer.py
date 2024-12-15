""" Generate an image of a tournament bracket """

import io
import matplotlib.pyplot as plt
from matplotlib.patches import ConnectionPatch

from deps.tournament_models import TournamentNode

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

def plot_tournament_bracket(root: TournamentNode, show: bool = True):
    """
    Generates an image of a tournament bracket from the root node of a tree.

    Args:
        root (TournamentNode): The root node of the tournament tree.
    """
    # Prepare lists to store node positions and labels
    positions = {}
    labels = {}
    max_depth = 0

    def traverse(node: TournamentNode, depth: int, x_offset: float):
        nonlocal max_depth

        if node is None:
            return x_offset

        max_depth = max(max_depth, depth)

        # Traverse left and right child nodes to determine their positions
        left_x = traverse(node.next_game1_id, depth + 1, x_offset)
        right_x = traverse(node.next_game2_id, depth + 1, left_x + 1)

        # Assign the current node's position based on its children
        current_x = (left_x + right_x) / 2 if node.next_game1_id or node.next_game2_id else x_offset

        # Store position and label
        positions[node.id] = (depth, current_x)
        labels[node.id] = f"{node.user1_id or 'N/A'} vs {node.user2_id or 'N/A'}"

        return current_x

    traverse(root, depth=0, x_offset=0)

    # Initialize the figure
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")

    # Plot the nodes and connections
    for node_id, (depth, x_pos) in positions.items():
        # Draw the current node
        ax.text(
            x_pos,
            -depth,
            labels[node_id],
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white"),
        )

        # Draw connections to child nodes
        node = next((n for n in positions if n == node_id), None)
        if node and node.next_game1_id:
            child_pos = positions[node.next_game1_id.id]
            con = ConnectionPatch(
                xyA=(x_pos, -depth),
                xyB=(child_pos[1], -child_pos[0]),
                coordsA="data",
                coordsB="data",
                arrowstyle="-",
                color="black",
            )
            ax.add_artist(con)

        if node and node.next_game2_id:
            child_pos = positions[node.next_game2_id.id]
            con = ConnectionPatch(
                xyA=(x_pos, -depth),
                xyB=(child_pos[1], -child_pos[0]),
                coordsA="data",
                coordsB="data",
                arrowstyle="-",
                color="black",
            )
            ax.add_artist(con)

    return _plot_return(plt, show)


