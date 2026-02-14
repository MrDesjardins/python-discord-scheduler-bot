"""
Siege functions logics
"""

from typing import Union
from deps.siege import get_aggregation_siege_activity
from deps.models import ActivityTransition


def test_get_aggregation_siege_activity_no_data() -> None:
    """
    Test the case where there isn't any data
    """
    dict_users_activities: dict[int, ActivityTransition] = {}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_none_entry() -> None:
    """
    Test the case where a None is part of the dictionary
    """
    dict_users_activities: dict[int, Union[ActivityTransition, None]] = {1: None}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_no_after() -> None:
    """
    Test the case where before activity is none and after is not
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, None)}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 1
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_in_menu() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_playing_map_training() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "Playing Map Training")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_playing_shooting_range() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "Playing SHOOTING RANGE")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_arcade() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "ARCADE match 1 of 2")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_ai() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "VERSUS AI match 1 of 2")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_no_after() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("in Menu", None)}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 1
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_1() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("Playing SHOOTING RANGE", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 1
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_2() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("Playing Map Training", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 1
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_3() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("ARCADE Match ...", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 1
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_4() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("VERSUS AI ...", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 1
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_5() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("RANKED match", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 1
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_6() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("STANDARD match", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 1
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_7() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("in Menu", "RANKED match")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 1
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_8() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("in Menu", "STANDARD match")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 1
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_looking_for_ranked_match() -> None:
    """
    Test the case where a user transitions from Looking for RANKED match to RANKED match (match starts)
    """
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("Looking for RANKED match", "RANKED match")
    }
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 1  # Now in ranked match
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 1  # Match just started


def test_get_aggregation_siege_activity_looking_for_ranked_match_multiple_users() -> None:
    """
    Test the case where multiple users just started a ranked match
    """
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("Looking for RANKED match", "RANKED match"),
        2: ActivityTransition("Looking for RANKED match", "RANKED match"),
        3: ActivityTransition("in MENU", "Playing Map Training"),
    }
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 2  # Two users now in ranked match
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 2  # Two matches just started
