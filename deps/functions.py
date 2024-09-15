from deps.values import emoji_to_time
from deps.models import TimeLabel
from discord import app_commands


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


def get_supported_time():
    """
    Returns a list of TimeLabel objects that represent the supported times.
    """
    supported_times = []
    for time in emoji_to_time.values():
        short_label = time[:-2]  # Extracts the numeric part of the time
        display_label = time
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
