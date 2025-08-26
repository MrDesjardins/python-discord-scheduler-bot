"""
Test for the Tracker
"""

import json
from typing import Any, Dict

from deps.functions_r6_tracker import parse_json_user_info
from deps.models import UserInformation


def get_test_data(dataset: int) -> Dict[str, Any]:
    """Pre-loaded real JSON file"""
    if dataset == 1:
        with open("./tests/tests_assets/full_user_stats_fridge.json", "r", encoding="utf8") as file:
            return json.loads(file.read())
    elif dataset == 8:
        with open("./tests/tests_assets/player_profile.json", "r", encoding="utf8") as file:
            return json.loads(file.read())
    return {}


def test_parsing_json_1():
    """Testing loading Fridge stats"""
    data = get_test_data(1)
    user_info: UserInformation = parse_json_user_info(1223, data)
    assert user_info.rank_deaths_count == 11983
    assert user_info.rank_kd_ratio == 1.23
    assert user_info.kd_ratio == 1.24
    assert user_info.quickmatch_kd_ratio == 1.27
    assert user_info.attacked_breacher_count == 976
    assert user_info.attacked_breacher_percentage == 8.71
    assert user_info.total_matches_played == 4439



def test_get_r6tracker_user_info():
    """Test to parse JSON to find the user info from the JSON file."""
    data = get_test_data(8)
    user_info: UserInformation = parse_json_user_info(1223, data)

    # Test user identification information
    assert user_info.user_id == 1223
    assert user_info.r6_tracker_user_uuid == "877a703b-0d29-4779-8fbf-ccd165c2b7f6"

    # Test general match stats from overview segment
    assert user_info.total_matches_played == 5609
    assert user_info.total_matches_won == 2826
    assert user_info.total_matches_lost == 2606
    assert user_info.total_matches_abandoned == 177
    assert user_info.time_played_seconds == 7316390
    assert user_info.total_kills == 20461
    assert user_info.total_deaths == 21605
    assert user_info.total_headshots == 7637
    assert user_info.total_headshots_missed == 8086
    assert user_info.headshot_percentage == 48.57
    assert user_info.total_wall_bang == 1168
    assert user_info.total_damage == 1649043
    assert user_info.total_assists == 3092
    assert user_info.total_team_kills == 127
    assert user_info.rounds_played == 13
    assert user_info.rounds_won == 3
    assert user_info.rounds_lost == 10
    assert user_info.rounds_disconnected == 2
    assert user_info.rounds_win_percentage == 23.076923076923077

    # Test performance ratios
    assert user_info.kd_ratio == 0.95
    assert user_info.kill_per_match == 3.65
    assert user_info.kill_per_minute == 0.17
    assert user_info.win_percentage == 50.38

    # Test attacker playstyles
    assert user_info.attacked_breacher_count == 5159
    assert user_info.attacked_fragger_count == 4598
    assert user_info.attacked_intel_count == 4289
    assert user_info.attacked_roam_count == 5159
    assert user_info.attacked_support_count == 5924
    assert user_info.attacked_utility_count == 4485

    # Test defender playstyles
    assert user_info.defender_debuffer_count == 4090
    assert user_info.defender_entry_denier_count == 4495
    assert user_info.defender_intel_count == 4801
    assert user_info.defender_support_count == 4371
    assert user_info.defender_trapper_count == 5577
    assert user_info.defender_utility_denier_count == 3459

    # Test ranked game mode stats
    assert user_info.rank_match_played == 2171
    assert user_info.rank_match_won == 1071
    assert user_info.rank_match_lost == 1094
    assert user_info.rank_match_abandoned == 6
    assert user_info.rank_kills_count == 7860
    assert user_info.rank_deaths_count == 9332
    assert user_info.rank_kd_ratio == 0.84
    assert user_info.rank_kill_per_match == 3.62
    assert user_info.rank_win_percentage == 49.33

    # Test arcade game mode stats
    assert user_info.arcade_match_played == 269
    assert user_info.arcade_match_won == 142
    assert user_info.arcade_match_lost == 88
    assert user_info.arcade_match_abandoned == 39
    assert user_info.arcade_kills_count == 4161
    assert user_info.arcade_deaths_count == 3050
    assert user_info.arcade_kd_ratio == 1.36
    assert user_info.arcade_kill_per_match == 15.47
    assert user_info.arcade_win_percentage == 52.79

    # Test quickmatch game mode stats
    assert user_info.quickmatch_match_played == 2986
    assert user_info.quickmatch_match_won == 1511
    assert user_info.quickmatch_match_lost == 1351
    assert user_info.quickmatch_match_abandoned == 124
    assert user_info.quickmatch_kills_count == 7774
    assert user_info.quickmatch_deaths_count == 8429
    assert user_info.quickmatch_kd_ratio == 0.92
    assert user_info.quickmatch_kill_per_match == 2.6
    assert user_info.quickmatch_win_percentage == 50.6
