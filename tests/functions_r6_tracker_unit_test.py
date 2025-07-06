"""
Test for the Tracker
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import patch
import pytz

from deps.functions_r6_tracker import parse_json_user_info
from deps.models import UserInformation


def get_test_data(dataset: int) -> Dict[str, Any]:
    """Pre-loaded real JSON file"""
    if dataset == 1:
        with open("./tests/tests_assets/r6tracker_data_full_user_stats_fridge.json", "r", encoding="utf8") as file:
            return json.loads(file.read())
    return ""


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
