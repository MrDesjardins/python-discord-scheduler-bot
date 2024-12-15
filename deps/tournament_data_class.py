"""Data classes for the tournament access layer table"""

from dataclasses import dataclass
from typing import Optional


from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Tournament:
    """Data class for the tournament table"""

    id: Optional[int]  # Optional because it is AUTOINCREMENT
    guild_id: int
    name: str
    registration_date: datetime
    start_date: datetime
    end_date: datetime
    best_of: int
    max_players: int
    maps: str


@dataclass
class UserTournament:
    """Data class for the user_tournament table"""

    id: Optional[int]  # Optional because it is AUTOINCREMENT
    user_id: int
    tournament_id: int
    registration_date: datetime


@dataclass
class TournamentGame:
    """Data class for the tournament_game table"""

    id: Optional[int]  # Optional because it is AUTOINCREMENT
    tournament_id: int
    user1_id: Optional[int] = None  # Nullable column
    user2_id: Optional[int] = None  # Nullable column
    user_winner_id: Optional[int] = None  # Nullable column
    timestamp: Optional[datetime] = None  # Nullable column
    next_game1_id: Optional[int] = None  # Nullable column
    next_game2_id: Optional[int] = None  # Nullable column
