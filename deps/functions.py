""" Utility functions used by the bot. """

import subprocess
from typing import Union, Optional, List
import discord
from discord import app_commands
from deps.values import (
    EMOJI_TO_TIME,
    MSG_UNIQUE_STRING,
    URL_TRN_API_RANKED_MATCHES,
    URL_TRN_PROFILE_MAIN,
    URL_TRN_PROFILE_OVERVIEW,
    URL_TRN_RANKED_PAGE,
)
from deps.mybot import MyBot
from deps.siege import siege_ranks

def get_reactions() -> List[str]:
    """
    Returns a list of all the emojis that can be used to vote.
    """
    return list(EMOJI_TO_TIME.keys())


def get_time_choices() -> List[app_commands.Choice]:
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
    bot: MyBot, channel: Union[discord.TextChannel, discord.VoiceChannel, None]
) -> Optional[discord.Message]:
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


def get_sha() -> str:
    """Get the latest git SHA"""
    return subprocess.check_output(["git", "rev-parse", "HEAD"]).strip().decode()


def most_common(lst) -> str:
    """Returns the most common element in a list."""
    return max(set(lst), key=lst.count)


async def set_member_role_from_rank(guild: discord.Guild, member: discord.Member, rank: str) -> None:
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


def get_url_user_profile_main(ubisoft_user_name: str) -> str:
    """Get the URL for the user profile."""
    return URL_TRN_PROFILE_MAIN.format(account_name=ubisoft_user_name)


def get_url_user_profile_overview(ubisoft_user_name: str) -> str:
    """Get the URL for the user profile."""
    return URL_TRN_PROFILE_OVERVIEW.format(account_name=ubisoft_user_name)


def get_url_user_ranked_matches(ubisoft_user_name: str) -> str:
    """
    Get the URL for the user match."
    This is used to set the cookie in the browser for future API calls
    """
    return URL_TRN_RANKED_PAGE.format(account_name=ubisoft_user_name)


def get_url_api_ranked_matches(ubisoft_user_name: str) -> str:
    """Get the URL for the API to get the stats."""
    return URL_TRN_API_RANKED_MATCHES.format(account_name=ubisoft_user_name)



