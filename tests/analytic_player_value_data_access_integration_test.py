"""Integration tests for the user_player_value data access"""

from datetime import datetime, timedelta, timezone

import pytest

from deps.analytic_data_access import insert_if_nonexistant_full_match_info, upsert_user_info
from deps.analytic_player_value_data_access import (
    data_access_fetch_all_user_ids_with_matches,
    data_access_fetch_player_value,
    data_access_fetch_player_values_by_algorithm,
    data_access_upsert_player_value,
)
from deps.data_access_data_class import UserInfo
from deps.models import PlayerValueAlgorithm, PlayerValueResult
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from tests.analytic_player_value_functions_unit_test import make_match

NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.no_parallel


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()

    yield

    database_manager.set_database_name(DATABASE_NAME)


def insert_user_with_match(user_id: int, match_timestamp: datetime) -> None:
    """Insert a user and one ranked match at the given time"""
    user_info = UserInfo(user_id, f"user{user_id}", f"ubi{user_id}", f"ubi{user_id}", f"uuid{user_id}", "US/Eastern", 0)
    upsert_user_info(
        user_id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        None,
        "US/Eastern",
        0,
    )
    match = make_match(user_id=user_id, match_uuid=f"match-{user_id}", match_timestamp=match_timestamp)
    insert_if_nonexistant_full_match_info(user_info, [match])


def test_upsert_then_fetch_player_value():
    result = PlayerValueResult(value=95.5, rating=4123.0, match_count=42, last_match_timestamp=NOW)
    data_access_upsert_player_value(1, PlayerValueAlgorithm.PERFORMANCE_ELO, result, NOW)

    assert data_access_fetch_player_value(1, PlayerValueAlgorithm.PERFORMANCE_ELO) == 95.5
    assert data_access_fetch_player_value(1, PlayerValueAlgorithm.CURRENT_FORM) is None
    assert data_access_fetch_player_value(999, PlayerValueAlgorithm.PERFORMANCE_ELO) is None


def test_upsert_twice_updates_value():
    first = PlayerValueResult(value=95.5, rating=4123.0, match_count=42, last_match_timestamp=NOW)
    second = PlayerValueResult(value=101.2, rating=4200.0, match_count=45, last_match_timestamp=NOW)
    data_access_upsert_player_value(1, PlayerValueAlgorithm.PERFORMANCE_ELO, first, NOW)
    data_access_upsert_player_value(1, PlayerValueAlgorithm.PERFORMANCE_ELO, second, NOW)

    assert data_access_fetch_player_value(1, PlayerValueAlgorithm.PERFORMANCE_ELO) == 101.2


def test_fetch_player_values_by_algorithm():
    result_user1 = PlayerValueResult(value=95.5, rating=4123.0, match_count=42, last_match_timestamp=NOW)
    result_user2 = PlayerValueResult(value=55.0, rating=3200.0, match_count=10, last_match_timestamp=NOW)
    data_access_upsert_player_value(1, PlayerValueAlgorithm.PERFORMANCE_ELO, result_user1, NOW)
    data_access_upsert_player_value(2, PlayerValueAlgorithm.PERFORMANCE_ELO, result_user2, NOW)
    data_access_upsert_player_value(2, PlayerValueAlgorithm.CURRENT_FORM, result_user2, NOW)

    values = data_access_fetch_player_values_by_algorithm(PlayerValueAlgorithm.PERFORMANCE_ELO)
    assert values == {1: 95.5, 2: 55.0}


def test_fetch_all_user_ids_with_matches():
    insert_user_with_match(1, NOW - timedelta(hours=3))
    insert_user_with_match(2, NOW - timedelta(days=5))

    assert sorted(data_access_fetch_all_user_ids_with_matches()) == [1, 2]
