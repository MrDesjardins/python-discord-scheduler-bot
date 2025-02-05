""" Integration tests about the cache """

import time
import pytest
from deps.cache_data_access import delete_all_tables
from deps.cache import set_cache
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    database_manager.set_database_name(DATABASE_NAME_TEST)
    delete_all_tables()

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
