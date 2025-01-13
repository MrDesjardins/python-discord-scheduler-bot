""" Class, enum and other data structure used in the bot"""

import dataclasses
from datetime import datetime
from enum import Enum
from typing import List, Optional

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
class UserWithUserFullMatchInfo:
    """Represent the user and their match info"""

    def __init__(self, user: UserInfo, user_match_info: List["UserFullMatchInfo"]):
        self.user = user
        self.user_match_info = user_match_info


@dataclasses.dataclass
class UserFullMatchInfo:
    """
    Represent the information from a single match for a specific user
    Information coming from this URL:
        https://api.tracker.gg/api/v2/r6siege/standard/matches/uplay/noSleep_rb6?gamemode=pvp_ranked
    Could also get more detail about the match:
        https://api.tracker.gg/api/v1/r6siege/ow-ingest/match/get/9681f59e-80db-4b2e-b54b-3631af76b074/877a703b-0d29-4779-8fbf-ccd165c2b7f6
    """

    def __init__(
        self,
        user_id:int,
        match_uuid: str,
        match_timestamp: datetime,
        match_duration_ms: int,
        data_center: str,  # US East, US West
        session_type: str,  # ranked, standard
        map_name: str,
        is_surrender: bool,
        is_forfeit: bool,
        is_rollback: bool,
        r6_tracker_user_uuid: str,
        ubisoft_username: str,
        operators: str,
        round_played_count: int,
        round_won_count: int,
        round_lost_count: int,
        round_disconnected_count: int,
        kill_count: int,
        death_count: int,
        assist_count: int,
        head_shot_count: int,
        tk_count: int,
        ace_count: int,
        first_kill_count: int,
        first_death_count: int,
        clutches_win_count: int,
        clutches_loss_count: int,
        clutches_win_count_1v1: int,
        clutches_win_count_1v2: int,
        clutches_win_count_1v3: int,
        clutches_win_count_1v4: int,
        clutches_win_count_1v5: int,
        clutches_lost_count_1v1: int,
        clutches_lost_count_1v2: int,
        clutches_lost_count_1v3: int,
        clutches_lost_count_1v4: int,
        clutches_lost_count_1v5: int,
        kill_1_count: int,
        kill_2_count: int,
        kill_3_count: int,
        kill_4_count: int,
        kill_5_count: int,
        rank_points: int,
        rank_name: str,
        points_gained: int,
        rank_previous: int,
        kd_ratio: int,
        head_shot_percentage: int,
        kills_per_round: int,
        deaths_per_round: int,
        assists_per_round: int,
        has_win: bool,
    ):
        self.user_id = user_id
        self.match_uuid = match_uuid
        self.match_timestamp = match_timestamp
        self.match_duration_ms = match_duration_ms
        self.data_center = data_center
        self.session_type = session_type
        self.map_name = map_name
        self.is_surrender = is_surrender
        self.is_forfeit = is_forfeit
        self.is_rollback = is_rollback
        self.r6_tracker_user_uuid = r6_tracker_user_uuid
        self.ubisoft_username = ubisoft_username
        self.operators = operators
        self.round_played_count = round_played_count
        self.round_won_count = round_won_count
        self.round_lost_count = round_lost_count
        self.round_disconnected_count = round_disconnected_count
        self.kill_count = kill_count
        self.death_count = death_count
        self.assist_count = assist_count
        self.head_shot_count = head_shot_count
        self.tk_count = tk_count
        self.ace_count = ace_count
        self.first_kill_count = first_kill_count
        self.first_death_count = first_death_count
        self.clutches_win_count = clutches_win_count
        self.clutches_loss_count = clutches_loss_count
        self.clutches_win_count_1v1 = clutches_win_count_1v1
        self.clutches_win_count_1v2 = clutches_win_count_1v2
        self.clutches_win_count_1v3 = clutches_win_count_1v3
        self.clutches_win_count_1v4 = clutches_win_count_1v4
        self.clutches_win_count_1v5 = clutches_win_count_1v5
        self.clutches_lost_count_1v1 = clutches_lost_count_1v1
        self.clutches_lost_count_1v2 = clutches_lost_count_1v2
        self.clutches_lost_count_1v3 = clutches_lost_count_1v3
        self.clutches_lost_count_1v4 = clutches_lost_count_1v4
        self.clutches_lost_count_1v5 = clutches_lost_count_1v5
        self.kill_1_count = kill_1_count
        self.kill_2_count = kill_2_count
        self.kill_3_count = kill_3_count
        self.kill_4_count = kill_4_count
        self.kill_5_count = kill_5_count
        self.rank_points = rank_points
        self.rank_name = rank_name
        self.points_gained = points_gained
        self.rank_previous = rank_previous
        self.kd_ratio = kd_ratio
        self.head_shot_percentage = head_shot_percentage
        self.kills_per_round = kills_per_round
        self.deaths_per_round = deaths_per_round
        self.assists_per_round = assists_per_round
        self.has_win = has_win


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


@dataclasses.dataclass
class Reason:
    """Instead of a boolean, a function can return a reason why it failed"""

    def __init__(self, is_successful: bool, text: Optional[str] = None, context: any = None):
        self.is_successful = is_successful
        self.text = text
        self.context = context


@dataclasses.dataclass
class ActivityTransition:
    """Keep Track of the last two activity details"""

    def __init__(self, before: Optional[str], after: Optional[str]):
        self.before = before
        self.after = after


@dataclasses.dataclass
class SiegeActivityAggregation:
    """Get aggregation of activity from Activity transition dictionary"""

    def __init__(
        self,
        count_in_menu: int,
        game_not_started: int,
        user_leaving: int,
        warming_up: int,
        done_warming_up: int,
        done_match_waiting_in_menu: int,
        playing_rank: int,
        playing_standard: int,
    ):
        self.count_in_menu = count_in_menu
        self.game_not_started = game_not_started
        self.user_leaving = user_leaving
        self.warming_up = warming_up
        self.done_warming_up = done_warming_up
        self.done_match_waiting_in_menu = done_match_waiting_in_menu
        self.playing_rank = playing_rank
        self.playing_standard = playing_standard
