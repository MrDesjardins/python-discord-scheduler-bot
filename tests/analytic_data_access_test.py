"""
Create Fake Data for Testing Analytics
"""

import unittest
from datetime import datetime


# pylint: disable=import-error
# pylint: disable=wrong-import-position
from deps.analytic_database import (
    set_database_name,
    EVENT_CONNECT,
    EVENT_DISCONNECT,
)
from deps.analytic_data_access import (
    compute_users_weights,
    delete_all_tables,
    fetch_user_activities,
    insert_user_activity,
)


class TestAnalyticDatabase(unittest.TestCase):
    """Test Analytic Database"""

    CHANNEL1_ID = 100
    CHANNEL2_ID = 200
    GUILD_ID = 1000

    def setUp(self):
        set_database_name("user_activity.test.db")
        # delete_all_tables()

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


if __name__ == "__main__":
    unittest.main()
