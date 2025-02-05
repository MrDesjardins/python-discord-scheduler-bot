"""
Functions that apply on the model
"""

from typing import Dict, List

from deps.values import (
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
