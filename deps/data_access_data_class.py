"""Data classes for the data access layer"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class UserInfo:
    """Match an user id with a display name. SQL table user_info"""

    id: int
    display_name: str
    ubisoft_username_max: Optional[str]
    ubisoft_username_active: Optional[str]
    r6_tracker_active_id: Optional[str]  # UUID
    """ List of time zones: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones """
    time_zone: str


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
