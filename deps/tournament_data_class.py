"""Data classes for the tournament access layer table"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone


def convert_to_datetime(date_str):
    """Convert a date string to a timezone-aware datetime object (UTC)"""
    if not date_str:  # Handle None or empty string
        return None
    # Parse the date string and assume it's in UTC if no timezone is provided
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # Make the datetime UTC-aware
    return dt


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
    has_started: bool
    registered_user_count: int = 0  # Default value

    @staticmethod
    def from_db_row(row):
        """Create a Tournament object from a database row"""
        return Tournament(
            id=row[0],
            guild_id=row[1],
            name=row[2],
            registration_date=convert_to_datetime(row[3]),
            start_date=convert_to_datetime(row[4]),
            end_date=convert_to_datetime(row[5]),
            best_of=row[6],
            max_players=row[7],
            maps=row[8],
            has_started=bool(row[9]),  # Convert integer to boolean
            registered_user_count=row[10],
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

    @staticmethod
    def from_db_row(row):
        """Create a Tournament object from a database row"""
        return TournamentGame(
            id=row[0],
            tournament_id=row[1],
            user1_id=row[2],
            user2_id=row[3],
            user_winner_id=row[4],
            score=row[5],
            map=row[6],
            timestamp=convert_to_datetime(row[7]),
            next_game1_id=row[8],
            next_game2_id=row[9],
        )
