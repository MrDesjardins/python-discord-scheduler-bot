"""
Create Fake Data for Testing Analytics
"""

import unittest
from datetime import datetime


# pylint: disable=import-error
from deps.data_access_data_class import UserInfo
from deps.analytic_database import DATABASE_NAME, DATABASE_NAME_TEST, EVENT_CONNECT, EVENT_DISCONNECT, database_manager

# pylint: disable=import-error
from deps.analytic_data_access import (
    compute_users_weights,
    delete_all_tables,
    fetch_user_activities,
    fetch_user_info_by_user_id_list,
    insert_user_activity,
)


class TestUserActivityAnalyticDatabase(unittest.TestCase):
    """Test Analytic Database"""

    CHANNEL1_ID = 100
    CHANNEL2_ID = 200
    GUILD_ID = 1000

    def setUp(self):
        database_manager.set_database_name(DATABASE_NAME_TEST)
        delete_all_tables()

    def tearDown(self):
        database_manager.set_database_name(DATABASE_NAME)
        return super().tearDown()

    def test_two_users_same_channels(self):
        """Insert two users in the same channel and calculate the weight"""

        insert_user_activity(
            10,
            "user_10",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_CONNECT,
            datetime(2024, 9, 20, 13, 20, 0, 6318),
        )
        insert_user_activity(
            11,
            "user_11",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_CONNECT,
            datetime(2024, 9, 20, 13, 20, 0, 6318),
        )
        insert_user_activity(
            10,
            "user_10",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_DISCONNECT,
            datetime(2024, 9, 20, 13, 50, 0, 6318),
        )
        insert_user_activity(
            11,
            "user_11",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_DISCONNECT,
            datetime(2024, 9, 20, 13, 50, 0, 6318),
        )
        activity_data = fetch_user_activities()
        user_weights = compute_users_weights(activity_data)
        self.assertEqual(user_weights, {(10, 11, 100): 1800.0})

    def test_many_users_same_channel(self):
        """Insert four users in the same channel and calculate the weight"""
        insert_user_activity(
            2,
            "user_2",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_CONNECT,
            datetime(2024, 9, 20, 13, 20, 0, 6318),
        )
        insert_user_activity(
            3,
            "user_3",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_CONNECT,
            datetime(2024, 9, 20, 13, 21, 0, 6318),
        )

        insert_user_activity(
            2,
            "user_2",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_DISCONNECT,
            datetime(2024, 9, 20, 13, 30, 0, 6318),
        )
        insert_user_activity(
            4,
            "user_4",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_CONNECT,
            datetime(2024, 9, 20, 13, 31, 0, 6318),
        )
        insert_user_activity(
            3,
            "user_3",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_DISCONNECT,
            datetime(2024, 9, 20, 13, 32, 0, 6318),
        )
        insert_user_activity(
            4,
            "user_4",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_DISCONNECT,
            datetime(2024, 9, 20, 13, 33, 0, 6318),
        )
        insert_user_activity(
            1,
            "user_1",
            self.CHANNEL1_ID,
            self.GUILD_ID,
            EVENT_DISCONNECT,
            datetime(2024, 9, 20, 13, 38, 0, 6318),
        )

        activity_data = fetch_user_activities()
        user_weights = compute_users_weights(activity_data)
        self.assertEqual(user_weights, {(2, 3, 100): 540.0, (3, 4, 100): 60.0})


class TestUserInfoAnalyticDatabase(unittest.TestCase):
    """
    Test Analytic Database for User Info
    """

    def setUp(self):
        database_manager.set_database_name(DATABASE_NAME_TEST)
        delete_all_tables()

    def tearDown(self):
        database_manager.set_database_name(DATABASE_NAME)
        return super().tearDown()

    def test_user_not_in_user_info_table(self):
        """
        Testing when user does not have an entry in the info table
        """
        users = fetch_user_info_by_user_id_list([1, 2, 3])
        self.assertEqual(users, [None, None, None])

    def test_user_in_and_not_in_user_info_table(self):
        """
        Testing when 1 user in and 2 does not have an entry in the info table
        """
        insert_user_activity(1, "user_1", 1, 1, EVENT_CONNECT, datetime(2024, 9, 20, 13, 20, 0, 6318))
        users = fetch_user_info_by_user_id_list([1, 2, 3])
        self.assertEqual(
            users,
            [
                UserInfo(
                    id=1,
                    display_name="user_1",
                    ubisoft_username_active=None,
                    ubisoft_username_max=None,
                    time_zone="US/Eastern",
                ),
                None,
                None,
            ],
        )


if __name__ == "__main__":
    unittest.main()
