"""
Contains shareable Discord actions for the tournament bot. 
The function might be used by several different Discord interactions.
"""

import io
from typing import List, Optional
import discord
from deps.data_access import data_access_get_channel, data_access_get_guild_tournament_text_channel_id
from deps.tournament_data_class import Tournament, TournamentGame
from deps.tournament_functions import build_tournament_tree
from deps.log import print_error_log, print_log
from deps.tournament_data_access import (
    fetch_active_tournament_by_guild,
    fetch_tournament_by_id,
    fetch_tournament_games_by_tournament_id,
    fetch_tournament_open_registration,
)
from deps.tournament_visualizer import plot_tournament_bracket
from deps.values import COMMAND_TOURNAMENT_REGISTER_TOURNAMENT


def generate_bracket_file(tournament_id: int, file_name: str = "tournament_bracket.png") -> Optional[discord.File]:
    """
    Generate the image to share in a Discord message
    """
    tournament: Tournament = fetch_tournament_by_id(tournament_id)
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        print_error_log(
            f"generate_braket_file: Failed to build tournament tree for tournament {tournament_id}. Skipping."
        )

    # Generate the tournament bracket image
    img_bytes = plot_tournament_bracket(tournament, tournament_tree, False)
    if img_bytes is None:
        print_error_log(
            f"generate_braket_file: Failed to generate tournament bracket image for tournament {tournament_id}. Skipping."
        )
        return None
    bytesio = io.BytesIO(img_bytes)
    bytesio.seek(0)  # Ensure the BytesIO cursor is at the beginning
    file = discord.File(fp=bytesio, filename=file_name)
    return file


async def send_tournament_bracket_to_a_guild(guild_id: int) -> None:
    channel_id: int = await data_access_get_guild_tournament_text_channel_id(guild_id)
    if channel_id is None:
        print_error_log(
            f"\t⚠️ send_daily_tournament_bracket_message: Tournament Channel id (configuration) not found for guild {guild.name}. Skipping."
        )
        return
    channel: discord.TextChannel = await data_access_get_channel(channel_id)
    tournaments: List[Tournament] = fetch_active_tournament_by_guild(guild_id)
    for tournament in tournaments:
        file = generate_bracket_file(tournament.id)
        if file is None:
            print_error_log(
                f"\t⚠️ send_daily_tournament_bracket_message: Failed to generate tournament bracket image for tournament {tournament.id}. Skipping."
            )
            continue
        await channel.send(file=file, content=f"Bracket for {tournament.name}")


async def send_tournament_registration_to_a_guild(guild_id: int) -> None:
    channel_id: int = await data_access_get_guild_tournament_text_channel_id(guild_id)
    if channel_id is None:
        print_error_log(
            f"\t⚠️ send_daily_tournament_registration_message: Tournament Channel id (configuration) not found for guild {guild.name}. Skipping."
        )
        return
    channel: discord.TextChannel = await data_access_get_channel(channel_id)
    tournaments: List[Tournament] = fetch_tournament_open_registration(guild_id)
    if len(tournaments) > 0:
        msg = "There are still open registrations for the following tournaments:\n"
        for tournament in tournaments:
            msg += f"{tournament.name}\n"
        msg += f"Use the command /{COMMAND_TOURNAMENT_REGISTER_TOURNAMENT} to join a tournament."
        await channel.send(content=msg)
    else:
        print_log(f"send_daily_tournament_registration_message: No open registration for guild {guild_id}")
