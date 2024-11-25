"""
Data Access Unit Tests
"""

import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from deps.data_access_data_class import UserInfo
from deps.cache import remove_cache, set_cache
from deps.data_access import (
    KEY_QUEUE_USER_STATS,
    data_access_add_list_member_stats,
    data_access_get_list_member_stats,
    data_acess_remove_list_member_stats,
)
from deps.models import UserQueueForStats


class TestDataAccess(unittest.IsolatedAsyncioTestCase):
    """Data Access Unit Tests"""

    @patch("deps.data_access.datetime")
    async def test_adding_two_members_stat_within_a_minute(self, mock_datetime):
        """Test adding two members stats"""

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
        self.assertEqual(len(list_users), 2)

    @patch("deps.data_access.datetime")
    async def test_adding_two_members_stat_with_first_one_expired(self, mock_datetime):
        """Test adding two members stats"""
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
        self.assertEqual(len(list_users), 1)

    @patch("deps.data_access.datetime")
    async def test_remove_expired_user(self, mock_datetime):
        """Test adding two members stats"""
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
        self.assertEqual(len(list_users), 1)
