""" Utility functions used by the bot. """

import subprocess
from datetime import datetime
from typing import Union, Optional, List
import json
from dataclasses import dataclass, field
import pytz
import discord
from discord import app_commands
import requests
from bs4 import BeautifulSoup
from deps.values import EMOJI_TO_TIME, MSG_UNIQUE_STRING
from deps.models import TimeLabel, UserMatchInfo
from deps.siege import siege_ranks


def get_empty_votes():
    """Returns an empty votes dictionary.
    Used to initialize the votes cache for a single day.
    Each array contains SimpleUser
    Result is { '3pm': [], '4pm': [], ... }
    """
    return {time: [] for time in EMOJI_TO_TIME.values()}


def get_reactions():
    """
    Returns a list of all the emojis that can be used to vote.
    """
    return list(EMOJI_TO_TIME.keys())


def get_supported_time_time_label():
    """
    Returns a list of TimeLabel objects that represent the supported times.
    """
    supported_times = []
    for time in EMOJI_TO_TIME.values():
        # time[:-2]  # Extracts the numeric part of the time
        short_label = time  # E.g. 2pm
        display_label = time  # E.g. 2pm
        description = f"{time} Eastern Time"
        supported_times.append(TimeLabel(short_label, display_label, description))
    return supported_times


def get_time_choices():
    """
    Returns a list of OptionChoice objects that represent the supported times.
    """
    supported_times = []
    for time in EMOJI_TO_TIME.values():
        short_label = time
        display_label = time
        supported_times.append(app_commands.Choice(name=short_label, value=display_label))
    return supported_times


async def get_last_schedule_message(
    bot: discord.Client, channel: Union[discord.TextChannel, discord.VoiceChannel, None]
):
    """
    Returns the last schedule message id for the given channel.
    """
    if channel is None:
        return None

    async for message in channel.history(limit=20):
        if (
            message.author.bot
            and message.author == bot.user
            and (message.content.startswith(MSG_UNIQUE_STRING) or len(message.embeds) > 0)
        ):
            last_message = message
            return last_message
    return None


def get_current_hour_eastern(add_hour: Optional[int] = None) -> str:
    """
    Returns the current hour in Eastern Time. In the format 3am or 3pm.
    """
    eastern = pytz.timezone("US/Eastern")
    if add_hour:
        current_time_eastern = datetime.now(eastern).replace(hour=datetime.now(eastern).hour + add_hour)
    else:
        current_time_eastern = datetime.now(eastern)
    # Strip leading zero by converting the hour to an integer before formatting
    return (
        current_time_eastern.strftime("%-I%p").lower()
        if hasattr(datetime.now(eastern), "strftime")
        else current_time_eastern.strftime("%I%p").lstrip("0").lower()
    )


def get_sha() -> str:
    """Get the latest git SHA"""
    return subprocess.check_output(["git", "rev-parse", "HEAD"]).strip().decode()


def write_git_sha_to_file():
    """Get the latest git SHA and write it to version.txt"""
    git_sha = get_sha()

    # Write the SHA to version.txt
    with open("version.txt", "w", encoding="utf-8") as f:
        f.write(git_sha)


def most_common(lst):
    """Returns the most common element in a list."""
    return max(set(lst), key=lst.count)


async def set_member_role_from_rank(guild: discord.Guild, member: discord.Member, rank: str):
    """Set the user role based on the rank."""
    # Remove all roles
    for r_name in siege_ranks:
        role_to_remove = discord.utils.get(guild.roles, name=r_name)
        if role_to_remove in member.roles:
            await member.remove_roles(role_to_remove, reason=f"Bot removed {r_name} before assigning new rank role.")

    # Get the Role object from the guild using the rank string
    role = discord.utils.get(guild.roles, name=rank)

    if role is None:
        raise ValueError(f"The guild does not have a role named '{rank}'.")
    # Pass the role object (not the name/str)
    await member.add_roles(role, reason="Bot assigned role based on rank from R6 Tracker")
    