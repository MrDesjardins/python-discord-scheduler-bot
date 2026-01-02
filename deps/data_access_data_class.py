"""Data classes for the data access layer"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UserInfo:
    """Match an user id with a display name. SQL table user_info"""

    """ Discord user id """
    id: int
    """ Discord display name """
    display_name: str
    """ Ubisoft main account """
    ubisoft_username_max: Optional[str]
    """ Ubisoft active account (could be the same as the main)"""
    ubisoft_username_active: Optional[str]
    """  R6Tracker active account (could be the same as the main)"""
    r6_tracker_active_id: Optional[str]  # UUID
    """ List of time zones: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones """
    time_zone: str
    """ User's best MMR recorded """
    max_mmr: int


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
