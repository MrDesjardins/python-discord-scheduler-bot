""" Model for the tournament feature """

import dataclasses
from enum import Enum


class BestOf(Enum):
    """Represents the days of the week"""

    THREE = 3
    FIVE = 5
    SEVEN = 7
    NINE = 9


class TournamentSize(Enum):
    """Represents the size of the tournament"""

    FOUR = 4
    EIGHT = 8
    SIXTEEN = 16
    THIRTY_TWO = 32
