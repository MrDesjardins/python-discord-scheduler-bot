"""Integration tests about the cache"""

import time
import pytest
from deps.cache import set_cache
from deps.data_access import (
    data_access_clear_match_gif_awaiting_result,
    data_access_list_match_gifs_awaiting_result,
    data_access_set_match_gif_awaiting_result,
)
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()

    # Yield control to the test functions
    yield

    # Teardown
    database_manager.set_database_name(DATABASE_NAME)


def test_set_cache_performance_database():
    """Performance test for setting cache"""

    start = time.perf_counter()
    for i in range(100):
        set_cache(False, f"key_{i}", f"value_{i}", 60)
    end = time.perf_counter()
    elapsed = (end - start) * 1000
    assert elapsed < 500  # 4 ms per set_cache call


def test_set_cache_performance_memory():
    """Performance test for setting cache"""

    start = time.perf_counter()
    for i in range(100):
        set_cache(True, f"key_{i}", f"value_{i}", 60)
    end = time.perf_counter()
    elapsed = (end - start) * 1000
    assert elapsed < 5


def test_awaiting_match_gifs_round_trip_and_expire():
    """Match GIFs awaiting a score are listed until cleared or expired."""
    data_access_set_match_gif_awaiting_result({"message_id": 1, "member_ids": [7]}, 60)
    data_access_set_match_gif_awaiting_result({"message_id": 2, "member_ids": [8]}, 60)
    data_access_set_match_gif_awaiting_result({"message_id": 3, "member_ids": [9]}, -1)  # already expired
    set_cache(False, "UnrelatedKey:1", "noise", 60)

    listed = sorted(record["message_id"] for record in data_access_list_match_gifs_awaiting_result())
    assert listed == [1, 2]

    data_access_clear_match_gif_awaiting_result(1)
    assert [record["message_id"] for record in data_access_list_match_gifs_awaiting_result()] == [2]
