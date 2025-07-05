"""Generate an image of a tournament bracket"""

import io
import os
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from deps.analytic_data_access import fetch_user_info
from deps.tournaments.tournament_models import TournamentNode
from deps.tournaments.tournament_data_class import Tournament
from deps.values import COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT
from deps.tournaments.tournament_functions import get_node_by_levels
from deps.tournaments.tournament_data_access import fetch_tournament_team_members_by_leader
from deps.functions import get_name

font_path = os.path.abspath("./fonts/Minecraft.ttf")
font1 = ImageFont.truetype(font_path, 16)
font2 = ImageFont.truetype(font_path, 20)
font3 = ImageFont.truetype(font_path, 22)

def _image_return(im: Image.Image, show: bool = True, file_name: str = "bracket.png"):
    """
    Return an image or the bytes of the iamge
    """
    if show:
        # plot.show()
        im.save(file_name)
        return None

    with io.BytesIO() as buf:
        im.save(buf, format="PNG")
        buf.seek(0)

        return buf.getvalue()


def plot_tournament_bracket(
    tournament: Tournament, root: TournamentNode, show: bool = True, file_name: str = "bracket.png"
) -> Optional[bytes]:
    """
    Generates an image of a tournament bracket from the root node of a tree.

    Args:
        tournament (Tournament): The tournament object containing metadata (name, dates).
        root (TournamentNode): The root node of the tournament tree.
        show (bool): Whether to display the plot or return the figure and axis.
    """
    image_header_space = 60
    image_margin = 25
    node_width = 300
    node_height = 70
    node_margin_vertical = 25
    node_margin_horizontal = 35
    node_padding = 10

    users_map = fetch_user_info()
    if tournament.id is None:
        raise ValueError("Tournament ID is None. Cannot fetch team members.")
    leader_partners: dict[int, list[int]] = fetch_tournament_team_members_by_leader(tournament.id)
    positions: dict[int, tuple[int, int]] = {}
    labels = {}
    node_lookup = {}

    levels = get_node_by_levels(root)
    number_of_depth = len(levels)
    maximum_node_vertically = len(levels[0])

    # Dynamically scale figure size based on tree dimensions
    fig_width = 2 * image_margin + (number_of_depth * node_width) + (number_of_depth * node_margin_horizontal)
    fig_height = image_header_space + 2 * image_margin + maximum_node_vertically * (node_height + node_margin_vertical)
    im = Image.new("RGB", (fig_width, fig_height), "white")
    draw = ImageDraw.Draw(im)

    for i, n in enumerate(levels):
        for j, node in enumerate(n):
            x_pos = image_margin + node_margin_vertical + i * (node_width + node_margin_horizontal)
            # y_pos = image_header_space + j * (node_height + NODE_MARGIN) + (diff) * (node_height + NODE_MARGIN) // 2
            y_pos = (
                image_header_space
                + j * (node_height + node_margin_vertical)
                + (2**i - 1) * (j * node_height + node_margin_vertical)
            )
            if node.next_game1 is not None and node.next_game2 is not None:
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
                user1_name = get_name(node.user1_id, users_map)
                if tournament.team_size > 1:
                    if node.user1_id in leader_partners:
                        teammates = leader_partners[node.user1_id]
                        for teammate in teammates:
                            user1_name += f", {get_name(teammate, users_map)}"

            if node.user2_id is None:
                user2_name = "?"
            else:
                user2_name = get_name(node.user2_id, users_map)
                if tournament.team_size > 1:
                    if node.user2_id in leader_partners:
                        teammates = leader_partners[node.user2_id]
                        for teammate in teammates:
                            user2_name += f", {get_name(teammate, users_map)}"

            skip_user_1 = node.user1_id is None
            skip_user_2 = node.user2_id is None
            label_names_team_1 = user1_name + " (win)" if node.user1_id == node.user_winner_id and not skip_user_1 else user1_name
            label_names_team_2 = user2_name + " (win)" if node.user2_id == node.user_winner_id and not skip_user_2 else user2_name
            label_map = f"{node.map} - {node.score if node.score is not None else '0-0'}"

            # Add node to the graph
            draw.rectangle((x_pos, y_pos, x_pos + node_width, y_pos + node_height), fill=bgcolor, outline="black")

            # Draw the current node with label
            draw.text(
                (x_pos + node_padding, y_pos + node_padding),
                label_names_team_1,
                fill="black",
                anchor="la",
                align="left",
                font=font1,
            )
            draw.text(
                (x_pos + node_padding, y_pos + node_padding * 3),
                label_names_team_2,
                fill="black",
                anchor="la",
                align="left",
                font=font1,
            )
            draw.text(
                (x_pos + node_padding, y_pos + node_padding * 5),
                label_map,
                fill="black",
                anchor="la",
                align="left",
                font=font1,
            )

            # Draw connections to child nodes
            if node.next_game1:
                child_pos = positions[node.next_game1.id]
                draw.line(
                    (x_pos, y_pos + node_height // 2, child_pos[0] + node_width, child_pos[1] + node_height // 2),
                    fill="black",
                )

            if node.next_game2:
                child_pos = positions[node.next_game2.id]
                draw.line(
                    (x_pos, y_pos + node_height // 2, child_pos[0] + node_width, child_pos[1] + node_height // 2),
                    fill="black",
                )

    # Add tournament title with adjusted padding
    draw.text(
        (fig_width // 2, image_margin),
        f"Tournament: {tournament.name}",
        fill="black",
        anchor="mm",
        font=font3,
    )

    # Add footer with start and end dates
    # Anchor mm means the text is centered
    draw.text(
        (fig_width // 2, fig_height - image_margin),
        f"Start Date: {tournament.start_date.strftime('%Y-%m-%d')}, End Date: {tournament.end_date.strftime('%Y-%m-%d')}",
        fill="gray",
        anchor="mm",
        font=font2,
    )
    draw.text(
        (fig_width // 2, fig_height - image_margin + 15),
        f"Use the command /{COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT} to report a lost match",
        fill="gray",
        anchor="mm",
        font=font2,
    )
    # Set axis limits based on positions

    return _image_return(im, show, file_name)
