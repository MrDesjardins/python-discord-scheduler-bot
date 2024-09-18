from deps.values import emoji_to_time, COMMAND_SCHEDULE_ADD
from deps.models import TimeLabel
import discord
from discord import app_commands
from datetime import datetime, date
from typing import Union
import pytz


def get_empty_votes():
    """ Returns an empty votes dictionary.
    Used to initialize the votes cache for a single day.
    Each array contains SimpleUser
    Result is { '3pm': [], '4pm': [], ... }
    """
    return {time: [] for time in emoji_to_time.values()}


def get_reactions():
    """
    Returns a list of all the emojis that can be used to vote.
    """
    return list(emoji_to_time.keys())


def get_supported_time_time_label():
    """
    Returns a list of TimeLabel objects that represent the supported times.
    """
    supported_times = []
    for time in emoji_to_time.values():
        # time[:-2]  # Extracts the numeric part of the time
        short_label = time  # E.g. 2pm
        display_label = time  # E.g. 2pm
        description = f"{time} Eastern Time"
        supported_times.append(
            TimeLabel(short_label, display_label, description))
    return supported_times


def get_time_choices():
    """
    Returns a list of OptionChoice objects that represent the supported times.
    """
    supported_times = []
    for time in emoji_to_time.values():
        short_label = time
        display_label = time
        supported_times.append(
            app_commands.Choice(name=short_label, value=display_label))
    return supported_times


def get_poll_message():
    current_date = date.today().strftime("%B %d, %Y")
    return f"What time will you play today ({current_date})?\n⚠️Time in Eastern Time (Pacific adds 3, Central adds 1).\nReact with all the time you plan to be available. You can use /{COMMAND_SCHEDULE_ADD} to set recurrent day and hours."


async def get_last_schedule_message(channel: Union[discord.TextChannel, discord.VoiceChannel, None]):
    """
    Returns the last schedule message id for the given channel.
    """
    if channel is None:
        return None

    today_message = get_poll_message()[:10]
    async for message in channel.history(limit=20):
        if message.content.startswith(today_message) and message.author.bot:
            last_message = message
            return last_message
    return None


def get_current_hour_eastern() -> str:
    """
    Returns the current hour in Eastern Time. In the format 3am or 3pm.
    """
    eastern = pytz.timezone('US/Eastern')
    current_time_eastern = datetime.now(eastern)
    # Strip leading zero by converting the hour to an integer before formatting
    return current_time_eastern.strftime('%-I%p').lower() if hasattr(datetime.now(eastern), 'strftime') else current_time_eastern.strftime('%I%p').lstrip('0').lower()
