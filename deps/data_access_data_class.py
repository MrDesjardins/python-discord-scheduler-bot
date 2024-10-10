"""Data classes for the data access layer"""
from dataclasses import dataclass

@dataclass
class UserInfo:
    """Match an user id with a display name. SQL table user_info"""

    id: int
    display_name: str


@dataclass
class UserActivity:
    """Match the SQL table user_activity"""

    user_id: int
    channel_id: int
    event: str
    timestamp: str
    guild_id: int


@dataclass
class UserWeight:
    """Match the SQL table user_weights"""

    user_a: str
    user_b: str
    channel_id: str
    weight: float
