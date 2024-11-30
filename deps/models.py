""" Class, enum and other data structure used in the bot"""

import dataclasses
from datetime import datetime
from enum import Enum
from typing import List

from deps.data_access_data_class import UserInfo


class DayOfWeek(Enum):
    """Represents the days of the week"""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


@dataclasses.dataclass
class TimeLabel:
    """Contains the value of the supported time with label and description
    Mainly used for the dropdown menu in the discord bot
    """

    def __init__(self, value: str, label: str, description: str):
        self.value = value
        self.label = label
        self.description = description


@dataclasses.dataclass
class SimpleUser:
    """Represent the value for a user of Discord without the full object that has functions performing API request
    The goal is avoiding the number of Disrcord API requests by caching information about the user
    """

    def __init__(self, user_id: int, display_name: str, rank_emoji: str):
        self.user_id = user_id
        self.display_name = display_name
        self.rank_emoji = rank_emoji

    def __str__(self):
        return f"User ID: {self.user_id}, Display Name: {self.display_name}"


@dataclasses.dataclass
class SimpleUserHour:
    """Represent for bot's purpose, a user and the hour they voted for"""

    def __init__(self, user: SimpleUser, hour: str):
        self.simple_user = user
        self.hour = hour


@dataclasses.dataclass
class UserMatchInfo:
    """
    Represent the information from a single match for a specific user
    Information coming from this URL:
        https://api.tracker.gg/api/v2/r6siege/standard/matches/uplay/noSleep_rb6?gamemode=pvp_ranked
    Could also get more detail about the match:
        https://api.tracker.gg/api/v1/r6siege/ow-ingest/match/get/9681f59e-80db-4b2e-b54b-3631af76b074/877a703b-0d29-4779-8fbf-ccd165c2b7f6
    """

    def __init__(
        self,
        match_uuid: str,
        r6_tracker_user_uuid: str,
        ubisoft_username: str,
        match_timestamp: datetime,
        match_duration_ms: int,
        map_name: str,
        has_win: bool,
        kill_count: int,
        death_count: int,
        assist_count: int,
        kd_ratio: float,
        ace_count: int,
        kill_3_count: int,
        kill_4_count: int,
        rank_points: int,
        points_gained: int,
        round_count: int,
        round_win_count: int,
        tk_count: int,
        clutches_win_count: int,
        clutches_loss_count: int,
        first_death_count: int,
        first_kill_count: int,
    ):
        self.match_uuid = match_uuid
        self.r6_tracker_user_uuid = r6_tracker_user_uuid
        self.ubisoft_username = ubisoft_username
        self.match_timestamp = match_timestamp
        self.match_duration_ms = match_duration_ms
        self.map_name = map_name
        self.has_win = has_win
        self.kill_count = kill_count
        self.death_count = death_count
        self.assist_count = assist_count
        self.kd_ratio = kd_ratio
        self.ace_count = ace_count
        self.kill_3_count = kill_3_count
        self.kill_4_count = kill_4_count
        self.rank_points = rank_points
        self.points_gained = points_gained
        self.round_count = round_count
        self.round_win_count = round_win_count
        self.tk_count = tk_count
        self.clutches_win_count = clutches_win_count
        self.clutches_loss_count = clutches_loss_count
        self.first_death_count = first_death_count
        self.first_kill_count = first_kill_count


@dataclasses.dataclass
class UserMatchInfoSessionAggregate:
    """
    Summary of a gaming session which is a list of matches
    """

    def __init__(
        self,
        ubisoft_username_active: str,
        match_count: int,
        match_win_count: int,
        match_loss_count: int,
        total_kill_count: int,
        total_death_count: int,
        total_assist_count: int,
        started_rank_points: int,
        ended_rank_points: int,
        total_gained_points: int,
        total_tk_count: int,
        total_round_with_aces: int,
        total_round_with_3k: int,
        total_round_with_4k: int,
        total_clutches_win_count: int,
        total_clutches_loss_count: int,
        total_first_death_count: int,
        total_first_kill_count: int,
        matches_recent: List[UserMatchInfo],
    ):
        self.ubisoft_username_active = ubisoft_username_active
        self.match_count = match_count
        self.match_win_count = match_win_count
        self.match_loss_count = match_loss_count
        self.total_kill_count = total_kill_count
        self.total_death_count = total_death_count
        self.total_assist_count = total_assist_count
        self.started_rank_points = started_rank_points
        self.ended_rank_points = ended_rank_points
        self.total_gained_points = total_gained_points
        self.total_tk_count = total_tk_count
        self.total_round_with_aces = total_round_with_aces
        self.total_round_with_3k = total_round_with_3k
        self.total_round_with_4k = total_round_with_4k
        self.matches_recent = matches_recent
        self.total_clutches_win_count = total_clutches_win_count
        self.total_clutches_loss_count = total_clutches_loss_count
        self.total_first_death_count = total_first_death_count
        self.total_first_kill_count = total_first_kill_count


@dataclasses.dataclass
class UserQueueForStats:
    """
    Represent the user that is in the queue to get their stats
    """

    def __init__(self, user_info: UserInfo, guild_id: str, time_queue: datetime):
        self.user_info = user_info
        self.guild_id = guild_id
        self.time_queue = time_queue


@dataclasses.dataclass
class UserWithUserMatchInfo:
    """Represent the user and their match info"""

    def __init__(self, user: UserQueueForStats, user_match_info: List["UserMatchInfo"]):
        self.user = user
        self.user_match_info = user_match_info
