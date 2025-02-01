"""
Functions that apply on the model
"""

from datetime import date
from typing import Dict, List

from deps.values import (
    COMMAND_SCHEDULE_ADD,
    DATE_FORMAT,
    MSG_UNIQUE_STRING,
    SUPPORTED_TIMES_ARR,
)
from deps.models import SimpleUser, TimeLabel


def get_empty_votes() -> Dict[str, List[SimpleUser]]:
    """Returns an empty votes dictionary.
    Used to initialize the votes cache for a single day.
    Each array contains SimpleUser
    Result is { '3pm': [], '4pm': [], ... }
    """
    return {time: [] for time in SUPPORTED_TIMES_ARR}


def get_supported_time_time_label() -> List[TimeLabel]:
    """
    Returns a list of TimeLabel objects that represent the supported times.
    """
    supported_times = []
    for time in SUPPORTED_TIMES_ARR:
        # time[:-2]  # Extracts the numeric part of the time
        short_label = time  # E.g. 2pm
        display_label = time  # E.g. 2pm
        description = f"{time} Eastern Time"
        supported_times.append(TimeLabel(short_label, display_label, description))
    return supported_times


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
