"""
Data Access Unit Tests using pytest
"""

from unittest.mock import patch
import asyncio
from datetime import datetime, timezone
import pytest
from deps.data_access_data_class import UserInfo
from deps.cache import remove_cache, set_cache
from deps.data_access import (
    KEY_QUEUE_USER_STATS,
    data_access_add_list_member_stats,
    data_access_get_list_member_stats,
    data_acess_remove_list_member_stats,
)
from deps.models import UserQueueForStats

lock = asyncio.Lock()


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
        user1 = UserQueueForStats(UserInfo(1, "user1", "ubi1", "ubi1_1", "US/Pacific"), "Diamond", time1)
        await data_access_add_list_member_stats(user1)

        time2 = datetime(2024, 11, 25, 11, 31, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = time2
        user2 = UserQueueForStats(UserInfo(2, "user2", "ubi2", "ubi1_2", "US/Pacific"), "Diamond", time2)
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
        user1 = UserQueueForStats(UserInfo(1, "user1", "ubi1", "ubi1_1", "US/Pacific"), "Diamond", time1)
        await data_access_add_list_member_stats(user1)

        time2 = datetime(2024, 11, 25, 11, 31, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = time2
        user2 = UserQueueForStats(UserInfo(2, "user2", "ubi2", "ubi1_2", "US/Pacific"), "Diamond", time2)
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
        user1 = UserQueueForStats(UserInfo(1, "user1", "ubi1", "ubi1_1", "US/Pacific"), "Diamond", time1)

        time2 = datetime(2024, 11, 25, 10, 1, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = time2
        user2 = UserQueueForStats(UserInfo(2, "user2", "ubi2", "ubi1_2", "US/Pacific"), "Diamond", time2)

        set_cache(True, KEY_QUEUE_USER_STATS, [user1, user2])
        await data_acess_remove_list_member_stats(user1)  # Remove one user (we sent the stats)

        list_users = await data_access_get_list_member_stats()
        assert len(list_users) == 1
