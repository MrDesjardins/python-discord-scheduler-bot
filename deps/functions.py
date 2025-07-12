"""Utility functions used by the bot."""

import os
from datetime import timedelta
import subprocess
from typing import Union, Optional, List
import discord
from discord import app_commands
from dotenv import load_dotenv
from deps.values import (
    MSG_UNIQUE_STRING,
    SUPPORTED_TIMES_ARR,
    URL_TRN_API_RANKED_MATCHES,
    URL_TRN_API_USER_INFO,
    URL_TRN_PROFILE_MAIN,
    URL_TRN_PROFILE_OVERVIEW,
    URL_TRN_RANKED_PAGE,
)
from deps.mybot import MyBot
from deps.siege import siege_ranks
from deps.functions_date import get_now_eastern


def get_time_choices() -> List[app_commands.Choice]:
    """
    Returns a list of OptionChoice objects that represent the supported times.
    """
    supported_times = []
    for time in SUPPORTED_TIMES_ARR:
        short_label = time
        display_label = time
        supported_times.append(app_commands.Choice(name=short_label, value=display_label))
    return supported_times


async def get_last_schedule_message(
    bot: MyBot, channel: Union[discord.TextChannel, discord.VoiceChannel, None], hours_threshold: int = 24
) -> Optional[discord.Message]:
    """
    Returns the last schedule message id for the given channel.
    """
    if channel is None:
        return None

    current_datetime = get_now_eastern()
    time_threshold = current_datetime - timedelta(hours=hours_threshold)
    async for message in channel.history(limit=20):
        if (
            message.author.bot
            and message.author == bot.user
            # and message.created_at >= time_threshold
            and (message.content.startswith(MSG_UNIQUE_STRING) or len(message.embeds) > 0)
        ):
            return message
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
    return URL_TRN_PROFILE_MAIN.format(account_name=ubisoft_user_name.strip())


def get_url_user_profile_overview(ubisoft_user_name: str) -> str:
    """Get the URL for the user profile."""
    return URL_TRN_PROFILE_OVERVIEW.format(account_name=ubisoft_user_name.strip())


def get_url_user_ranked_matches(ubisoft_user_name: str) -> str:
    """
    Get the URL for the user match."
    This is used to set the cookie in the browser for future API calls
    """
    return URL_TRN_RANKED_PAGE.format(account_name=ubisoft_user_name.strip())


def get_url_api_ranked_matches(ubisoft_user_name: str) -> str:
    """Get the URL for the API to get the stats."""
    return URL_TRN_API_RANKED_MATCHES.format(account_name=ubisoft_user_name.strip())


def get_rotated_number_from_current_day(max_number: int) -> int:
    """
    Get a number from the current date that will rotate every max_number of day
    Use case: 1 stats per day and we show back the stats every x days where x is the
    total number of different stats
    """
    today = get_now_eastern().date()
    day_of_year = today.timetuple().tm_yday  # 1 for Jan 1, 365 for Dec 31
    function_number = (day_of_year - 1) % max_number
    return function_number


def get_url_api_user_info(ubisoft_user_name: str) -> str:
    """
    Get the URL for the API to get the user info.
    """
    return URL_TRN_API_USER_INFO.format(account_name=ubisoft_user_name.strip())


def get_name(user_id: int, users_map: dict) -> str:
    """
    Get the name of a user
    """
    if user_id in users_map:
        return users_map[user_id].display_name[:16]
    return str(user_id)


def is_production_env() -> bool:
    """
    Check if the environment is production.
    """
    load_dotenv()
    env = os.getenv("ENV", "dev")
    return env == "prod"