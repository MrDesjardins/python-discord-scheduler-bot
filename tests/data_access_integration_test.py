"""
Data Access Unit Tests using pytest
"""

from unittest.mock import patch
import asyncio
from datetime import datetime, timezone
import pytest
from deps.cache import remove_cache, set_cache
from deps.data_access import (
    KEY_QUEUE_USER_STATS,
    data_access_add_list_member_stats,
    data_access_get_list_member_stats,
    data_access_get_r6tracker_max_rank,
    data_acess_remove_list_member_stats,
)
from deps.models import UserQueueForStats
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from tests.mock_model import mock_user1, mock_user2

lock = asyncio.Lock()


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


@pytest.fixture(scope="function", autouse=True)
def setup_function():
    """Setup function"""
    remove_cache(True, KEY_QUEUE_USER_STATS)


@pytest.mark.no_parallel
@pytest.mark.asyncio
@patch("deps.data_access.datetime")
async def test_adding_two_members_stat_within_a_minute(mock_datetime):
    """Test adding two members stats within a minute"""
    async with lock:
        remove_cache(False, KEY_QUEUE_USER_STATS)
        time1 = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = time1
        user1 = UserQueueForStats(mock_user1, "Diamond", time1)
        await data_access_add_list_member_stats(user1)

        time2 = datetime(2024, 11, 25, 11, 31, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = time2
        user2 = UserQueueForStats(mock_user2, "Diamond", time2)
        await data_access_add_list_member_stats(user2)

        list_users = await data_access_get_list_member_stats()
        mock_datetime.now.assert_called()
        assert len(list_users) == 2


@pytest.mark.no_parallel
@pytest.mark.asyncio
@patch("deps.data_access.datetime")
async def test_adding_two_members_stat_with_first_one_expired(mock_datetime):
    """Test adding two members stats with the first one expired"""
    async with lock:
        remove_cache(False, KEY_QUEUE_USER_STATS)
        time1 = datetime(2024, 11, 25, 10, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = time1
        user1 = UserQueueForStats(mock_user1, "Diamond", time1)
        await data_access_add_list_member_stats(user1)

        time2 = datetime(2024, 11, 25, 11, 31, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = time2
        user2 = UserQueueForStats(mock_user2, "Diamond", time2)
        await data_access_add_list_member_stats(user2)

        list_users = await data_access_get_list_member_stats()
        mock_datetime.now.assert_called()
        assert len(list_users) == 1


@pytest.mark.no_parallel
@pytest.mark.asyncio
@patch("deps.data_access.datetime")
async def test_remove_expired_user(mock_datetime):
    """Test removing an expired user"""
    async with lock:
        remove_cache(False, KEY_QUEUE_USER_STATS)
        time1 = datetime(2024, 11, 25, 10, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = time1
        user1 = UserQueueForStats(mock_user1, "Diamond", time1)

        time2 = datetime(2024, 11, 25, 10, 1, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = time2
        user2 = UserQueueForStats(mock_user2, "Diamond", time2)

        set_cache(True, KEY_QUEUE_USER_STATS, [user1, user2])
        await data_acess_remove_list_member_stats(user1)  # Remove one user (we sent the stats)

        list_users = await data_access_get_list_member_stats()
        assert len(list_users) == 1


async def test_data_access_get_r6tracker_max_rank_test_diamond() -> None:
    """
    Test the function to get the max rank from R6Tracker
    """

    result = await data_access_get_r6tracker_max_rank("noSleep_rb6", True)
    # Add a delay between each individual test of 5 seconds to avoid spamming the TRN API
    await asyncio.sleep(5)
    assert result == "Diamond"


async def test_data_access_get_r6tracker_max_rank_test_platinum() -> None:
    """
    Test the function to get the max rank from R6Tracker
    """

    result = await data_access_get_r6tracker_max_rank("LebronsCock", True)
    # Add a delay between each individual test of 5 seconds to avoid spamming the TRN API
    await asyncio.sleep(5)
    assert result == "Platinum"


async def test_data_access_get_r6tracker_max_rank_test_does_not_exist() -> None:
    """
    Test the function to get the max rank from R6Tracker
    """

    result = await data_access_get_r6tracker_max_rank("DoesNotExist123000Name", True)
    # Add a delay between each individual test of 5 seconds to avoid spamming the TRN API
    await asyncio.sleep(5)
    assert result == "Copper"


async def test_data_access_get_r6tracker_max_rank_test_champion() -> None:
    """
    Test the function to get the max rank from R6Tracker
    """

    result = await data_access_get_r6tracker_max_rank("Funkyshmug", True)
    # Add a delay between each individual test of 5 seconds to avoid spamming the TRN API
    await asyncio.sleep(5)
    assert result == "Champion"


async def test_data_access_get_r6tracker_max_rank_test_emerald_period() -> None:
    """
    Test the function to get the max rank from R6Tracker
    """

    result = await data_access_get_r6tracker_max_rank("Adahdf.", True)
    # Add a delay between each individual test of 5 seconds to avoid spamming the TRN API
    await asyncio.sleep(5)
    assert result == "Emerald"


async def test_data_access_get_r6tracker_max_rank_test_gold() -> None:
    """
    Test the function to get the max rank from R6Tracker
    """

    result = await data_access_get_r6tracker_max_rank("J0hn_Th1cc", True)
    # Add a delay between each individual test of 5 seconds to avoid spamming the TRN API
    await asyncio.sleep(5)
    assert result == "Gold"
