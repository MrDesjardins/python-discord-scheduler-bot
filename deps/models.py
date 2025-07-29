"""Class, enum and other data structure used in the bot"""

import dataclasses
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Union

from deps.data_access_data_class import UserInfo
from deps.functions_date import convert_to_datetime


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


class UserFullMatchStats:
    """
    Represent the information from a single match for a specific user
    Information coming from this URL:
        https://api.tracker.gg/api/v2/r6siege/standard/matches/uplay/noSleep_rb6?gamemode=pvp_ranked
    Could also get more detail about the match:
        https://api.tracker.gg/api/v1/r6siege/ow-ingest/match/get/9681f59e-80db-4b2e-b54b-3631af76b074/877a703b-0d29-4779-8fbf-ccd165c2b7f6
    """

    def __init__(
        self,
        id: Union[int, None],
        match_uuid: str,
        user_id: int,
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
        kd_ratio: float,
        head_shot_percentage: float,
        kills_per_round: float,
        deaths_per_round: float,
        assists_per_round: float,
        has_win: bool,
    ):
        self.id = id
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

    @staticmethod
    def from_db_row(row):
        """Create a Tournament object from a database row"""
        return UserFullMatchStats(
            id=row[0],
            match_uuid=row[1],
            user_id=row[2],
            match_timestamp=convert_to_datetime(row[3]),
            match_duration_ms=row[4],
            data_center=row[5],
            session_type=row[6],
            map_name=row[7],
            is_surrender=bool(row[8]),
            is_forfeit=bool(row[9]),
            is_rollback=bool(row[10]),
            r6_tracker_user_uuid=row[11],
            ubisoft_username=row[12],
            operators=row[13],
            round_played_count=row[14],
            round_won_count=row[15],
            round_lost_count=row[16],
            round_disconnected_count=row[17],
            kill_count=row[18],
            death_count=row[19],
            assist_count=row[20],
            head_shot_count=row[21],
            tk_count=row[22],
            ace_count=row[23],
            first_kill_count=row[24],
            first_death_count=row[25],
            clutches_win_count=row[26],
            clutches_loss_count=row[27],
            clutches_win_count_1v1=row[28],
            clutches_win_count_1v2=row[29],
            clutches_win_count_1v3=row[30],
            clutches_win_count_1v4=row[31],
            clutches_win_count_1v5=row[32],
            clutches_lost_count_1v1=row[33],
            clutches_lost_count_1v2=row[34],
            clutches_lost_count_1v3=row[35],
            clutches_lost_count_1v4=row[36],
            clutches_lost_count_1v5=row[37],
            kill_1_count=row[38],
            kill_2_count=row[39],
            kill_3_count=row[40],
            kill_4_count=row[41],
            kill_5_count=row[42],
            rank_points=row[43],
            rank_name=row[44],
            points_gained=row[45],
            rank_previous=row[46],
            kd_ratio=row[47],
            head_shot_percentage=row[48],
            kills_per_round=row[49],
            deaths_per_round=row[50],
            assists_per_round=row[51],
            has_win=bool(row[52]),
        )

    def to_dict(self):
        """
        Convert the object to a dictionary representation
        """
        return {
            key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in self.__dict__.items()
        }


@dataclasses.dataclass
class UserWithUserFullMatchInfo:
    """Represent the user and their match info"""

    def __init__(self, user: UserInfo, user_match_info: List[UserFullMatchStats]):
        self.user = user
        self.user_match_info = user_match_info


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
        matches_recent: List[UserFullMatchStats],
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

    user_info: UserInfo
    guild_id: int
    time_queue: datetime


@dataclasses.dataclass
class UserWithUserMatchInfo:
    """Represent the user who request stats and their match stats response"""

    user_request_stats: UserQueueForStats
    match_stats: List[UserFullMatchStats]


@dataclasses.dataclass
class Reason:
    """Instead of a boolean, a function can return a reason why it failed"""

    def __init__(self, is_successful: bool, text: Optional[str] = None, context: Any = None):
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
        done_warming_up_waiting_in_menu: int,
        done_match_waiting_in_menu: int,
        playing_rank: int,
        playing_standard: int,
    ):
        self.count_in_menu = count_in_menu
        self.game_not_started = game_not_started
        self.user_leaving = user_leaving
        self.warming_up = warming_up
        self.done_warming_up_waiting_in_menu = done_warming_up_waiting_in_menu
        self.done_match_waiting_in_menu = done_match_waiting_in_menu
        self.playing_rank = playing_rank
        self.playing_standard = playing_standard


class UserInformation:
    """
    Represent the information of a user
    Information coming from this URL:
        https://api.tracker.gg/api/v2/r6siege/standard/profile/ubi/noSleep_rb6?
    """

    def __init__(
        self,
        user_id: int,
        r6_tracker_user_uuid: str,
        total_matches_played: int = 0,
        total_matches_won: int = 0,
        total_matches_lost: int = 0,
        total_matches_abandoned: int = 0,
        time_played_seconds: int = 0,
        total_kills: int = 0,
        total_deaths: int = 0,
        total_attacker_round_wins: int = 0,
        total_defender_round_wins: int = 0,
        total_headshots: int = 0,
        total_headshots_missed: int = 0,
        headshot_percentage: float = 0.0,
        total_wall_bang: int = 0,
        total_damage: int = 0,
        total_assists: int = 0,
        total_team_kills: int = 0,
        attacked_breacher_count: int = 0,
        attacked_breacher_percentage: float = 0.0,
        attacked_fragger_count: int = 0,
        attacked_fragger_percentage: float = 0.0,
        attacked_intel_count: int = 0,
        attacked_intel_percentage: float = 0.0,
        attacked_roam_count: int = 0,
        attacked_roam_percentage: float = 0.0,
        attacked_support_count: int = 0,
        attacked_support_percentage: float = 0.0,
        attacked_utility_count: int = 0,
        attacked_utility_percentage: float = 0.0,
        defender_debuffer_count: int = 0,
        defender_debuffer_percentage: float = 0.0,
        defender_entry_denier_count: int = 0,
        defender_entry_denier_percentage: float = 0.0,
        defender_intel_count: int = 0,
        defender_intel_percentage: float = 0.0,
        defender_support_count: int = 0,
        defender_support_percentage: float = 0.0,
        defender_trapper_count: int = 0,
        defender_trapper_percentage: float = 0.0,
        defender_utility_denier_count: int = 0,
        defender_utility_denier_percentage: float = 0.0,
        kd_ratio: float = 0.0,
        kill_per_match: float = 0.0,
        kill_per_minute: float = 0.0,
        win_percentage: float = 0.0,
        rank_match_played: int = 0,
        rank_match_won: int = 0,
        rank_match_lost: int = 0,
        rank_match_abandoned: int = 0,
        rank_kills_count: int = 0,
        rank_deaths_count: int = 0,
        rank_kd_ratio: float = 0.0,
        rank_kill_per_match: float = 0.0,
        rank_win_percentage: float = 0.0,
        arcade_match_played: int = 0,
        arcade_match_won: int = 0,
        arcade_match_lost: int = 0,
        arcade_match_abandoned: int = 0,
        arcade_kills_count: int = 0,
        arcade_deaths_count: int = 0,
        arcade_kd_ratio: float = 0.0,
        arcade_kill_per_match: float = 0.0,
        arcade_win_percentage: float = 0.0,
        quickmatch_match_played: int = 0,
        quickmatch_match_won: int = 0,
        quickmatch_match_lost: int = 0,
        quickmatch_match_abandoned: int = 0,
        quickmatch_kills_count: int = 0,
        quickmatch_deaths_count: int = 0,
        quickmatch_kd_ratio: float = 0.0,
        quickmatch_kill_per_match: float = 0.0,
        quickmatch_win_percentage: float = 0.0,
    ):
        self.id = id
        self.r6_tracker_user_uuid = r6_tracker_user_uuid
        self.user_id = user_id
        self.total_matches_played = total_matches_played
        self.total_matches_won = total_matches_won
        self.total_matches_lost = total_matches_lost
        self.total_matches_abandoned = total_matches_abandoned
        self.time_played_seconds = time_played_seconds
        self.total_kills = total_kills
        self.total_deaths = total_deaths
        self.total_attacker_round_wins = total_attacker_round_wins
        self.total_defender_round_wins = total_defender_round_wins
        self.total_headshots = total_headshots
        self.total_headshots_missed = total_headshots_missed
        self.headshot_percentage = headshot_percentage
        self.total_wall_bang = total_wall_bang
        self.total_damage = total_damage
        self.total_assists = total_assists
        self.total_team_kills = total_team_kills
        self.attacked_breacher_count = attacked_breacher_count
        self.attacked_breacher_percentage = attacked_breacher_percentage
        self.attacked_fragger_count = attacked_fragger_count
        self.attacked_fragger_percentage = attacked_fragger_percentage
        self.attacked_intel_count = attacked_intel_count
        self.attacked_intel_percentage = attacked_intel_percentage
        self.attacked_roam_count = attacked_roam_count
        self.attacked_roam_percentage = attacked_roam_percentage
        self.attacked_support_count = attacked_support_count
        self.attacked_support_percentage = attacked_support_percentage
        self.attacked_utility_count = attacked_utility_count
        self.attacked_utility_percentage = attacked_utility_percentage
        self.defender_debuffer_count = defender_debuffer_count
        self.defender_debuffer_percentage = defender_debuffer_percentage
        self.defender_entry_denier_count = defender_entry_denier_count
        self.defender_entry_denier_percentage = defender_entry_denier_percentage
        self.defender_intel_count = defender_intel_count
        self.defender_intel_percentage = defender_intel_percentage
        self.defender_support_count = defender_support_count
        self.defender_support_percentage = defender_support_percentage
        self.defender_trapper_count = defender_trapper_count
        self.defender_trapper_percentage = defender_trapper_percentage
        self.defender_utility_denier_count = defender_utility_denier_count
        self.defender_utility_denier_percentage = defender_utility_denier_percentage
        self.kd_ratio = kd_ratio
        self.kill_per_match = kill_per_match
        self.kill_per_minute = kill_per_minute
        self.win_percentage = win_percentage
        self.rank_match_played = rank_match_played
        self.rank_match_won = rank_match_won
        self.rank_match_lost = rank_match_lost
        self.rank_match_abandoned = rank_match_abandoned
        self.rank_kills_count = rank_kills_count
        self.rank_deaths_count = rank_deaths_count
        self.rank_kd_ratio = rank_kd_ratio
        self.rank_kill_per_match = rank_kill_per_match
        self.rank_win_percentage = rank_win_percentage
        self.arcade_match_played = arcade_match_played
        self.arcade_match_won = arcade_match_won
        self.arcade_match_lost = arcade_match_lost
        self.arcade_match_abandoned = arcade_match_abandoned
        self.arcade_kills_count = arcade_kills_count
        self.arcade_deaths_count = arcade_deaths_count
        self.arcade_kd_ratio = arcade_kd_ratio
        self.arcade_kill_per_match = arcade_kill_per_match
        self.arcade_win_percentage = arcade_win_percentage
        self.quickmatch_match_played = quickmatch_match_played
        self.quickmatch_match_won = quickmatch_match_won
        self.quickmatch_match_lost = quickmatch_match_lost
        self.quickmatch_match_abandoned = quickmatch_match_abandoned
        self.quickmatch_kills_count = quickmatch_kills_count
        self.quickmatch_deaths_count = quickmatch_deaths_count
        self.quickmatch_kd_ratio = quickmatch_kd_ratio
        self.quickmatch_kill_per_match = quickmatch_kill_per_match
        self.quickmatch_win_percentage = quickmatch_win_percentage

    @staticmethod
    def from_db_row(row):
        """Create an object from a database row"""
        return UserInformation(
            user_id=row[0],
            r6_tracker_user_uuid=row[1],
            total_matches_played=row[2],
            total_matches_won=row[3],
            total_matches_lost=row[4],
            total_matches_abandoned=row[5],
            time_played_seconds=row[6],
            total_kills=row[7],
            total_deaths=row[8],
            total_attacker_round_wins=row[9],
            total_defender_round_wins=row[10],
            total_headshots=row[11],
            total_headshots_missed=row[12],
            headshot_percentage=row[13],
            total_wall_bang=row[14],
            total_damage=row[15],
            total_assists=row[16],
            total_team_kills=row[17],
            attacked_breacher_count=row[18],
            attacked_breacher_percentage=row[19],
            attacked_fragger_count=row[20],
            attacked_fragger_percentage=row[21],
            attacked_intel_count=row[22],
            attacked_intel_percentage=row[23],
            attacked_roam_count=row[24],
            attacked_roam_percentage=row[25],
            attacked_support_count=row[26],
            attacked_support_percentage=row[27],
            attacked_utility_count=row[28],
            attacked_utility_percentage=row[29],
            defender_debuffer_count=row[30],
            defender_debuffer_percentage=row[31],
            defender_entry_denier_count=row[32],
            defender_entry_denier_percentage=row[33],
            defender_intel_count=row[34],
            defender_intel_percentage=row[35],
            defender_support_count=row[36],
            defender_support_percentage=row[37],
            defender_trapper_count=row[38],
            defender_trapper_percentage=row[39],
            defender_utility_denier_count=row[40],
            defender_utility_denier_percentage=row[41],
            kd_ratio=row[42],
            kill_per_match=row[43],
            kill_per_minute=row[44],
            win_percentage=row[45],
            rank_match_played=row[46],
            rank_match_won=row[47],
            rank_match_lost=row[48],
            rank_match_abandoned=row[49],
            rank_kills_count=row[50],
            rank_deaths_count=row[51],
            rank_kd_ratio=row[52],
            rank_kill_per_match=row[53],
            rank_win_percentage=row[54],
            arcade_match_played=row[55],
            arcade_match_won=row[56],
            arcade_match_lost=row[57],
            arcade_match_abandoned=row[58],
            arcade_kills_count=row[59],
            arcade_deaths_count=row[60],
            arcade_kd_ratio=row[61],
            arcade_kill_per_match=row[62],
            arcade_win_percentage=row[63],
            quickmatch_match_played=row[64],
            quickmatch_match_won=row[65],
            quickmatch_match_lost=row[66],
            quickmatch_match_abandoned=row[67],
            quickmatch_kills_count=row[68],
            quickmatch_deaths_count=row[69],
            quickmatch_kd_ratio=row[70],
            quickmatch_kill_per_match=row[71],
            quickmatch_win_percentage=row[72],
        )

    def to_dict(self):
        """
        Convert the object to a dictionary representation
        """
        return {
            key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in self.__dict__.items()
        }


@dataclasses.dataclass
class UserWithUserInformation:
    """Represent the user who request stats and their stats"""

    user_request_stats: UserQueueForStats
    full_stats: UserInformation
