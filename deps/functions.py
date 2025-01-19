""" Utility functions used by the bot. """

import subprocess
from datetime import date, datetime, timezone
from typing import Dict, Union, Optional, List
import pytz
import discord
from discord import app_commands
from deps.values import (
    COMMAND_SCHEDULE_ADD,
    DATE_FORMAT,
    EMOJI_TO_TIME,
    MSG_UNIQUE_STRING,
    URL_TRN_API_RANKED_MATCHES,
    URL_TRN_PROFILE_MAIN,
    URL_TRN_PROFILE_OVERVIEW,
    URL_TRN_RANKED_PAGE,
)
from deps.models import SimpleUser, TimeLabel
from deps.mybot import MyBot
from deps.siege import siege_ranks


def get_empty_votes() -> Dict[str, List[SimpleUser]]:
    """Returns an empty votes dictionary.
    Used to initialize the votes cache for a single day.
    Each array contains SimpleUser
    Result is { '3pm': [], '4pm': [], ... }
    """
    return {time: [] for time in EMOJI_TO_TIME.values()}


def get_reactions() -> List[str]:
    """
    Returns a list of all the emojis that can be used to vote.
    """
    return list(EMOJI_TO_TIME.keys())


def get_supported_time_time_label() -> List[TimeLabel]:
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


def get_current_hour_eastern(add_hour: Optional[int] = None) -> str:
    """
    Returns the current hour in Eastern Time. In the format 3am or 3pm.
    """
    eastern = pytz.timezone("US/Eastern")
    # Get the current time in Eastern timezone once
    current_time_eastern = datetime.now(eastern)

    if add_hour:
        # Adjust the hour by the add_hour parameter
        current_time_eastern = current_time_eastern.replace(hour=current_time_eastern.hour + add_hour)

    # Strip leading zero by converting the hour to an integer before formatting
    return (
        current_time_eastern.strftime("%-I%p").lower()
        if hasattr(current_time_eastern, "strftime")
        else current_time_eastern.strftime("%I%p").lstrip("0").lower()
    )


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


def get_daily_string_message(vote_for_message: Dict[str, List[SimpleUser]]) -> str:
    """Create the daily message"""
    current_date = date.today().strftime(DATE_FORMAT)
    vote_message = f"{MSG_UNIQUE_STRING} today **{current_date}**?"
    vote_message += "\n\n**Schedule**\n"
    for key_time, users in vote_for_message.items():
        if users:
            vote_message += f"{key_time}: {','.join([f'{user.rank_emoji}{user.display_name}' for user in users])}\n"
        else:
            vote_message += f"{key_time}: -\n"
    vote_message += f"\n⚠️Time in Eastern Time (Pacific adds 3, Central adds 1).\nYou can use `/{COMMAND_SCHEDULE_ADD}` to set recurrent day and hours or click the emoji corresponding to your time:"
    return vote_message


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


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure a datetime is in UTC.
    - If naive, assume it's in the local timezone and convert to UTC.
    - If timezone-aware, convert to UTC if needed.
    """
    if dt.tzinfo is None:
        # Assume naive datetime is in the local timezone
        local_dt = dt.replace(tzinfo=timezone.utc).astimezone()
        return local_dt.astimezone(timezone.utc)
    # Convert to UTC if not already in UTC
    return dt.astimezone(timezone.utc)


def convert_to_datetime(date_str):
    """Convert a date string to a timezone-aware datetime object (UTC)"""
    if not date_str:  # Handle None or empty string
        return None
    # Parse the date string and assume it's in UTC if no timezone is provided
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # Make the datetime UTC-aware
    return dt
