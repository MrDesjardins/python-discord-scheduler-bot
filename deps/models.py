from enum import Enum


class DayOfWeek(Enum):
    """ Represents the days of the week """
    monday = 0
    tuesday = 1
    wednesday = 2
    thursday = 3
    friday = 4
    saturday = 5
    sunday = 6


class TimeLabel:
    """ Contains the value of the supported time with label and description
    Mainly used for the dropdown menu in the discord bot
    """

    def __init__(self, value: str, label: str, description: str):
        self.value = value
        self.label = label
        self.description = description


class SimpleUser:
    """ Represent the value for a user of Discord without the full object that has functions performing API request 
    The goal is avoiding the number of Disrcord API requests by caching information about the user
    """

    def __init__(self, user_id: int, display_name: str, rank_emoji: str):
        self.user_id = user_id
        self.display_name = display_name
        self.rank_emoji = rank_emoji

    def __str__(self):
        return f"User ID: {self.user_id}, Display Name: {self.display_name}"


class SimpleUserHour:
    """ Represent for bot's purpose, a user and the hour they voted for
    """

    def __init__(self, user: SimpleUser, hour: int):
        self.simpleUser = user
        self.hour = hour
