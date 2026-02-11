"""
Unit tests for stats.cc activity detection and aggregation
"""

from typing import Union
from unittest.mock import MagicMock

import discord

from deps.models import ActivityTransition
from deps.siege import (
    get_statscc_activity,
    get_aggregation_statscc_activity,
    get_aggregation_all_activities,
    _is_statscc_detail,
)


# --- get_statscc_activity tests ---


def _make_activity(name: str, details: str = "") -> discord.Activity:
    """Create a real discord.Activity so isinstance checks work."""
    return discord.Activity(name=name, details=details, type=discord.ActivityType.playing)


def test_get_statscc_activity_found() -> None:
    """Test that stats.cc activity is detected"""
    activity = _make_activity("stats.cc", "At the Main Menu")
    member = MagicMock(spec=discord.Member)
    member.activities = [activity]
    result = get_statscc_activity(member)
    assert result is not None
    assert result.name == "stats.cc"


def test_get_statscc_activity_not_found() -> None:
    """Test that non-stats.cc activities are ignored"""
    activity = _make_activity("Rainbow Six Siege", "in MENU")
    member = MagicMock(spec=discord.Member)
    member.activities = [activity]
    result = get_statscc_activity(member)
    assert result is None


def test_get_statscc_activity_no_activities() -> None:
    """Test with no activities"""
    member = MagicMock(spec=discord.Member)
    member.activities = []
    result = get_statscc_activity(member)
    assert result is None


# --- _is_statscc_detail tests ---


def test_is_statscc_detail_main_menu() -> None:
    assert _is_statscc_detail("At the Main Menu") is True


def test_is_statscc_detail_in_queue() -> None:
    assert _is_statscc_detail("In Queue") is True


def test_is_statscc_detail_match_started() -> None:
    assert _is_statscc_detail("Match Started") is True


def test_is_statscc_detail_ranked() -> None:
    assert _is_statscc_detail("Ranked") is True


def test_is_statscc_detail_standard() -> None:
    assert _is_statscc_detail("Standard") is True


def test_is_statscc_detail_picking_operators() -> None:
    assert _is_statscc_detail("Picking Operators: Ranked on Villa") is True


def test_is_statscc_detail_in_round() -> None:
    assert _is_statscc_detail("In round: Ranked on Coastline") is True


def test_is_statscc_detail_match_ending() -> None:
    assert _is_statscc_detail("Match Ending: Ranked on Bank") is True


def test_is_statscc_detail_banning_operators() -> None:
    assert _is_statscc_detail("Banning Operators: Ranked on Clubhouse") is True


def test_is_statscc_detail_prep_phase() -> None:
    assert _is_statscc_detail("Prep Phase: Ranked on Oregon") is True


def test_is_statscc_detail_siege_format() -> None:
    """Native Siege details should NOT match"""
    assert _is_statscc_detail("in MENU") is False
    assert _is_statscc_detail("RANKED match 1 of 2") is False
    assert _is_statscc_detail("Looking for RANKED match") is False
    assert _is_statscc_detail("Playing Map Training") is False


def test_is_statscc_detail_none() -> None:
    assert _is_statscc_detail(None) is False


# --- get_aggregation_statscc_activity tests ---


def test_statscc_aggregation_no_data() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.playing_rank == 0
    assert result.looking_ranked_match == 0


def test_statscc_aggregation_none_entry() -> None:
    dict_users_activities: dict[int, Union[ActivityTransition, None]] = {1: None}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0


def test_statscc_aggregation_both_none() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, None)}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.game_not_started == 1


def test_statscc_aggregation_at_main_menu() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "At the Main Menu")}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0


def test_statscc_aggregation_in_queue() -> None:
    """Menu to In Queue should count as looking_ranked_match"""
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("At the Main Menu", "In Queue")}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.looking_ranked_match == 1


def test_statscc_aggregation_playing_ranked() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("In Queue", "Ranked")}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.playing_rank == 1


def test_statscc_aggregation_picking_operators_ranked() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("In Queue", "Picking Operators: Ranked on Villa")
    }
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.playing_rank == 1


def test_statscc_aggregation_in_round_ranked() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("Picking Operators: Ranked on Villa", "In round: Ranked on Villa")
    }
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.playing_rank == 1


def test_statscc_aggregation_match_ending_ranked() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("In round: Ranked on Villa", "Match Ending: Ranked on Villa")
    }
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.playing_rank == 1


def test_statscc_aggregation_ranked_done_back_to_menu() -> None:
    """Ranked match done, back to menu"""
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("Match Ending: Ranked on Villa", "At the Main Menu")
    }
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.done_match_waiting_in_menu == 1
    assert result.count_in_menu == 1


def test_statscc_aggregation_ranked_bare_done_back_to_menu() -> None:
    """Bare 'Ranked' detail done, back to menu"""
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("Ranked", "At the Main Menu")}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.done_match_waiting_in_menu == 1
    assert result.count_in_menu == 1


def test_statscc_aggregation_standard_done_back_to_menu() -> None:
    """Standard match done, back to menu"""
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("Standard", "At the Main Menu")}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.done_match_waiting_in_menu == 1
    assert result.count_in_menu == 1


def test_statscc_aggregation_user_leaving() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("At the Main Menu", None)}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.user_leaving == 1


def test_statscc_aggregation_playing_standard() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("In Queue", "Standard")}
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.playing_standard == 1


def test_statscc_aggregation_multiple_users() -> None:
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("At the Main Menu", "In Queue"),
        2: ActivityTransition("At the Main Menu", "In Queue"),
        3: ActivityTransition(None, "At the Main Menu"),
    }
    result = get_aggregation_statscc_activity(dict_users_activities)
    assert result.looking_ranked_match == 2
    assert result.count_in_menu == 1


# --- get_aggregation_all_activities tests ---


def test_all_activities_mixed_siege_and_statscc() -> None:
    """Test mixed voice channel with both native Siege and stats.cc users"""
    dict_users_activities: dict[int, Union[ActivityTransition, None]] = {
        1: ActivityTransition("in MENU", "Looking for RANKED match"),  # Native Siege
        2: ActivityTransition("At the Main Menu", "In Queue"),  # stats.cc
        3: ActivityTransition(None, "At the Main Menu"),  # stats.cc
    }
    result = get_aggregation_all_activities(dict_users_activities)
    assert result.looking_ranked_match == 2  # 1 from Siege + 1 from stats.cc
    assert result.count_in_menu == 1  # 1 from stats.cc


def test_all_activities_only_siege() -> None:
    """All native Siege users"""
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("in MENU", "Looking for RANKED match"),
        2: ActivityTransition("in MENU", "RANKED match"),
    }
    result = get_aggregation_all_activities(dict_users_activities)
    assert result.looking_ranked_match == 1
    assert result.playing_rank == 1


def test_all_activities_only_statscc() -> None:
    """All stats.cc users"""
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("At the Main Menu", "In Queue"),
        2: ActivityTransition("In Queue", "Ranked"),
    }
    result = get_aggregation_all_activities(dict_users_activities)
    assert result.looking_ranked_match == 1
    assert result.playing_rank == 1


def test_all_activities_none_entries() -> None:
    """None entries handled correctly"""
    dict_users_activities: dict[int, Union[ActivityTransition, None]] = {
        1: None,
        2: ActivityTransition("in MENU", "RANKED match"),
    }
    result = get_aggregation_all_activities(dict_users_activities)
    assert result.playing_rank == 1


def test_all_activities_done_match_mixed() -> None:
    """Done match transitions from both sources"""
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("RANKED match 1 of 2", "in MENU"),  # Native Siege
        2: ActivityTransition("Match Ending: Ranked on Villa", "At the Main Menu"),  # stats.cc
    }
    result = get_aggregation_all_activities(dict_users_activities)
    assert result.done_match_waiting_in_menu == 2
    assert result.count_in_menu == 2
