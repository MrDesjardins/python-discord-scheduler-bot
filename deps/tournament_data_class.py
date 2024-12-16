"""Data classes for the tournament access layer table"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


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
    has_started: int

    @staticmethod
    def from_db_row(row):
        """Create a Tournament object from a database row"""
        return Tournament(
            id=row[0],
            guild_id=row[1],
            name=row[2],
            registration_date=row[3],
            start_date=row[4],
            end_date=row[5],
            best_of=row[6],
            max_players=row[7],
            maps=row[8],
            has_started=bool(row[9]),  # Convert integer to boolean
        )


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
    score: Optional[str] = None  # Nullable column
    map: Optional[str] = None  # Nullable column
    timestamp: Optional[datetime] = None  # Nullable column
    next_game1_id: Optional[int] = None  # Nullable column
    next_game2_id: Optional[int] = None  # Nullable column
