"""
Contains shareable Discord actions for the tournament bot. 
The function might be used by several different Discord interactions.
"""

import io
from typing import List, Optional
import discord
from deps.data_access import data_access_get_channel, data_access_get_guild_tournament_text_channel_id
from deps.tournament_data_class import Tournament, TournamentGame
from deps.tournament_functions import build_tournament_tree, start_tournament
from deps.log import print_error_log, print_log
from deps.tournament_data_access import (
    fetch_active_tournament_by_guild,
    fetch_tournament_by_id,
    fetch_tournament_games_by_tournament_id,
    fetch_tournament_open_registration,
    fetch_tournament_start_today,
)
from deps.tournament_visualizer import plot_tournament_bracket
from deps.values import (
    COMMAND_TOURNAMENT_REGISTER_TOURNAMENT,
    COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT,
    COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT,
)


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


async def send_tournament_bracket_to_a_guild(guild: discord.guild) -> None:
    """
    Send the tournament bracket to a guild
    """
    guild_id = guild.id
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


async def send_tournament_registration_to_a_guild(guild: discord.guild) -> None:
    """
    Sending a message once a day to remind the registration for the tournament
    """
    guild_id = guild.id
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
            start_date = tournament.start_date.strftime("%Y-%m-%d")
            msg += f"➡️ {tournament.name} Start the {start_date} with currently {tournament.registered_user_count}/{tournament.max_players} participants\n"
        msg += f"Use the command `/{COMMAND_TOURNAMENT_REGISTER_TOURNAMENT}` to join a tournament."
        await channel.send(content=msg)
    else:
        print_log(f"send_daily_tournament_registration_message: No open registration for guild {guild_id}")


async def send_tournament_starting_to_a_guild(guild: discord.guild) -> None:
    """
    Send a message once at the date of a tournament is starting
    """
    guild_id = guild.id
    channel_id: int = await data_access_get_guild_tournament_text_channel_id(guild_id)
    if channel_id is None:
        print_error_log(
            f"\t⚠️ send_tournament_starting_to_a_guild: Tournament Channel id (configuration) not found for guild {guild.name}. Skipping."
        )
        return
    channel: discord.TextChannel = await data_access_get_channel(channel_id)
    tournaments: List[Tournament] = fetch_tournament_start_today(guild_id)
    if len(tournaments) > 0:
        msg = f"Tournaments starting today:\nUse the command /{COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT} to report your lost (winner has nothing to do).\nUse the command /{COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT} to see who you are facing."
        msg += f"\nUse the command `/{COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT}` to report your lost (winner has nothing to do)."
        for tournament in tournaments:
            try:
                start_tournament(tournament)
                msg += f"\n{tournament.name}"

            except Exception as e:
                print_error_log(f"send_tournament_starting_to_a_guild: Error starting tournament {tournament.id}: {e}")
       
        await channel.send(content=msg)
        for tournament in tournaments:
            file = generate_bracket_file(tournament.id)
            await channel.send(content=f"Bracket for {tournament.name}", file=file)
    else:
        print_log(f"send_tournament_starting_to_a_guild: No open registration for guild {guild_id}")
