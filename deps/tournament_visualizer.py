""" Generate an image of a tournament bracket """

import io
import os
from PIL import Image, ImageDraw, ImageFont
from deps.analytic_data_access import fetch_user_info
from deps.tournament_models import TournamentNode
from deps.tournament_data_class import Tournament
from deps.values import COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT
from deps.tournament_functions import get_node_by_levels

font_path = os.path.abspath("./fonts/Minecraft.ttf")
font1 = ImageFont.truetype(font_path, 12)
font2 = ImageFont.truetype(font_path, 16)
font3 = ImageFont.truetype(font_path, 18)


def get_name(user_id: str, users_map: dict) -> str:
    """
    Get the name of a user
    """
    if user_id in users_map:
        return users_map[user_id].display_name[:8]
    return user_id


def _image_return(im: Image, show: bool = True):
    """
    Return an image or the bytes of the iamge
    """
    if show:
        # plot.show()
        im.save("bracket.png")
        return None

    with io.BytesIO() as buf:
        im.save(buf, format="PNG")
        buf.seek(0)

        return buf.getvalue()


def plot_tournament_bracket(tournament: Tournament, root: TournamentNode, show: bool = True):
    """
    Generates an image of a tournament bracket from the root node of a tree.

    Args:
        tournament (Tournament): The tournament object containing metadata (name, dates).
        root (TournamentNode): The root node of the tournament tree.
        show (bool): Whether to display the plot or return the figure and axis.
    """
    IMAGE_HEADER_SPACE = 60
    IMAGE_MARGIN = 25
    NODE_WIDTH = 150
    NODE_HEIGHT = 50
    NODE_MARGIN_VERTICAL = 25
    NODE_MARGIN_HORIZONTAL = 35
    NODE_PADDING = 10

    users_map = fetch_user_info()
    positions = {}
    labels = {}
    node_lookup = {}

    levels = get_node_by_levels(root)
    number_of_depth = len(levels)
    maximum_node_vertically = len(levels[0])

    # Dynamically scale figure size based on tree dimensions
    fig_width = 2 * IMAGE_MARGIN + (number_of_depth * NODE_WIDTH) + (number_of_depth * NODE_MARGIN_HORIZONTAL)
    fig_height = IMAGE_HEADER_SPACE + 2 * IMAGE_MARGIN + maximum_node_vertically * (NODE_HEIGHT + NODE_MARGIN_VERTICAL)
    im = Image.new("RGB", (fig_width, fig_height), "white")
    draw = ImageDraw.Draw(im)

    for i, n in enumerate(levels):
        diff = maximum_node_vertically - len(n)
        for j, node in enumerate(n):
            x_pos = IMAGE_MARGIN + NODE_MARGIN_VERTICAL + i * (NODE_WIDTH + NODE_MARGIN_HORIZONTAL)
            # y_pos = IMAGE_HEADER_SPACE + j * (NODE_HEIGHT + NODE_MARGIN) + (diff) * (NODE_HEIGHT + NODE_MARGIN) // 2
            y_pos = (
                IMAGE_HEADER_SPACE
                + j * (NODE_HEIGHT + NODE_MARGIN_VERTICAL)
                + (2**i - 1) * (j * NODE_HEIGHT + NODE_MARGIN_VERTICAL)
            )
            if node.next_game2 is not None:
                top1 = positions[node.next_game1.id][1]
                top2 = positions[node.next_game2.id][1]
                y_pos = (top1 + top2) // 2

            positions[node.id] = (x_pos, y_pos)
            node_lookup[node.id] = node
            labels[node.id] = f"{get_name(node.user_winner_id, users_map)}" if node.user_winner_id else f"{node.map}"
            bgcolor = "lightgreen" if node.user_winner_id else "white"

            if node.user1_id is None:
                user1_name = "?"
            else:
                user1_name = (
                    get_name(node.user1_id, users_map)
                    if node.user1_id != node.user_winner_id
                    else f"*{ get_name(node.user1_id, users_map)}*"
                )
            if node.user2_id is None:
                user2_name = "?"
            else:
                user2_name = (
                    get_name(node.user2_id, users_map)
                    if node.user2_id != node.user_winner_id
                    else f"*{ get_name(node.user2_id, users_map)}*"
                )

            label = f"{user1_name} vs {user2_name}\n{node.map} - {node.score if node.score is not None else '0-0'}"

            # Add node to the graph
            draw.rectangle((x_pos, y_pos, x_pos + NODE_WIDTH, y_pos + NODE_HEIGHT), fill=bgcolor, outline="black")

            # Draw the current node with label
            draw.text(
                (x_pos + NODE_PADDING, y_pos + NODE_PADDING), label, fill="black", anchor="la", align="left", font=font1
            )

            # Draw connections to child nodes
            if node.next_game1:
                child_pos = positions[node.next_game1.id]
                draw.line(
                    (x_pos, y_pos + NODE_HEIGHT // 2, child_pos[0] + NODE_WIDTH, child_pos[1] + NODE_HEIGHT // 2),
                    fill="black",
                )

            if node.next_game2:
                child_pos = positions[node.next_game2.id]
                draw.line(
                    (x_pos, y_pos + NODE_HEIGHT // 2, child_pos[0] + NODE_WIDTH, child_pos[1] + NODE_HEIGHT // 2),
                    fill="black",
                )

    # Add tournament title with adjusted padding
    draw.text(
        (fig_width // 2, IMAGE_MARGIN),
        f"Tournament: {tournament.name}",
        fill="black",
        anchor="mm",
        font=font3,
    )

    # Add footer with start and end dates
    # Anchor mm means the text is centered
    draw.text(
        (fig_width // 2, fig_height - IMAGE_MARGIN),
        f"Start Date: {tournament.start_date.strftime('%Y-%m-%d')}, End Date: {tournament.end_date.strftime('%Y-%m-%d')}",
        fill="gray",
        anchor="mm",
        font=font2,
    )
    draw.text(
        (fig_width // 2, fig_height - IMAGE_MARGIN + 15),
        f"Use the command /{COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT} to report a lost match",
        fill="gray",
        anchor="mm",
        font=font2,
    )
    # Set axis limits based on positions

    return _image_return(im, show)
