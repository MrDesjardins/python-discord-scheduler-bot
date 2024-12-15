""" Model for the tournament feature """

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional


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


class TournamentNode:
    """A node in the bracket tree"""

    def __init__(
        self,
        id: int,
        tournament_id: int,
        user1_id: Optional[int] = None,
        user2_id: Optional[int] = None,
        user_winner_id: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.id = id
        self.tournament_id = tournament_id
        self.user1_id = user1_id
        self.user2_id = user2_id
        self.user_winner_id = user_winner_id
        self.timestamp = timestamp
        self.next_game1: Optional[TournamentNode] = None
        self.next_game2: Optional[TournamentNode] = None
