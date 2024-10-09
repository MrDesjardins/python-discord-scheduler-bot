""" Unit tests for the analytic_gatherer module """

from datetime import datetime
import unittest
from unittest.mock import patch
from deps.analytic import EVENT_CONNECT, EVENT_DISCONNECT, UserActivity
from deps.analytic_gatherer import (
    calculate_overlap,
    calculate_user_connections,
    compute_users_weights,
    computer_users_voice_in_out,
    compute_users_voice_channel_time_sec,
    users_last_played_over_day,
)


class TestCalculateOverlap(unittest.TestCase):
    """Unit test for calculate_overlap function"""

    def setUp(self):
        pass

    def test_full_overlap(self):
        start1 = datetime(2024, 9, 20, 13, 18, 0, 6318)
        end1 = datetime(2024, 9, 20, 13, 20, 0, 6318)
        start2 = datetime(2024, 9, 20, 13, 18, 0, 6318)
        end2 = datetime(2024, 9, 20, 13, 20, 0, 6318)
        result = calculate_overlap(start1, end1, start2, end2)
        self.assertEqual(result, 120)

    def test_no_overlap(self):
        start1 = datetime(2024, 9, 20, 13, 18, 0, 6318)
        end1 = datetime(2024, 9, 20, 13, 20, 0, 6318)
        start2 = datetime(2024, 9, 20, 14, 18, 0, 6318)
        end2 = datetime(2024, 9, 20, 14, 20, 0, 6318)
        result = calculate_overlap(start1, end1, start2, end2)
        self.assertEqual(result, 0)

    def test_partial_overlap(self):
        start1 = datetime(2024, 9, 20, 13, 0, 0, 6318)
        end1 = datetime(2024, 9, 20, 13, 0, 20, 6318)
        start2 = datetime(2024, 9, 20, 13, 0, 10, 6318)
        end2 = datetime(2024, 9, 20, 13, 0, 50, 6318)
        result = calculate_overlap(start1, end1, start2, end2)
        self.assertEqual(result, 10)


class TestCalculateUserConnections(unittest.TestCase):
    """Unit test for compute_users_weights function"""

    def setUp(self):
        pass

    def test_two_users_connection_with_single_connect_disconnect(self):
        activity_data = [
            UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
            UserActivity(channel_id=1, user_id=2, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:1.6318", guild_id=1),
            UserActivity(
                channel_id=1, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:18:3.6318", guild_id=1
            ),
            UserActivity(
                channel_id=1, user_id=2, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:18:4.6318", guild_id=1
            ),
        ]
        result = calculate_user_connections(activity_data)
        self.assertEqual(
            result,
            {
                1: {
                    1: [[datetime(2024, 9, 20, 13, 18, 0, 631800), datetime(2024, 9, 20, 13, 18, 3, 631800)]],
                    2: [[datetime(2024, 9, 20, 13, 18, 1, 631800), datetime(2024, 9, 20, 13, 18, 4, 631800)]],
                }
            },
        )

    def test_two_users_connection_with_many_connect_disconnect(self):
        activity_data = [
            UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
            UserActivity(channel_id=1, user_id=2, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:1.6318", guild_id=1),
            UserActivity(
                channel_id=1, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:18:3.6318", guild_id=1
            ),
            UserActivity(
                channel_id=1, user_id=2, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:18:4.6318", guild_id=1
            ),
            UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:20:1.6318", guild_id=1),
            UserActivity(
                channel_id=1, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:20:10.6318", guild_id=1
            ),
        ]
        result = calculate_user_connections(activity_data)
        self.assertEqual(
            result,
            {
                1: {
                    1: [
                        [datetime(2024, 9, 20, 13, 18, 0, 631800), datetime(2024, 9, 20, 13, 18, 3, 631800)],
                        [datetime(2024, 9, 20, 13, 20, 1, 631800), datetime(2024, 9, 20, 13, 20, 10, 631800)],
                    ],
                    2: [[datetime(2024, 9, 20, 13, 18, 1, 631800), datetime(2024, 9, 20, 13, 18, 4, 631800)]],
                }
            },
        )

    def test_user_connect_in_two_different_channels(self):
        activity_data = [
            UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
            UserActivity(
                channel_id=1, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:19:0.6318", guild_id=1
            ),
            UserActivity(channel_id=2, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:28:3.6318", guild_id=1),
            UserActivity(
                channel_id=2, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:29:3.6318", guild_id=1
            ),
        ]

        result = calculate_user_connections(activity_data)
        self.assertEqual(
            result,
            {
                1: {
                    1: [
                        [datetime(2024, 9, 20, 13, 18, 0, 631800), datetime(2024, 9, 20, 13, 19, 0, 631800)],
                    ],
                },
                2: {
                    1: [
                        [datetime(2024, 9, 20, 13, 28, 3, 631800), datetime(2024, 9, 20, 13, 29, 3, 631800)],
                    ],
                },
            },
        )

    def test_user_connect_never_disconnected(self):
        activity_data = [
            UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
        ]
        result = calculate_user_connections(activity_data)
        self.assertEqual(
            result,
            {
                1: {
                    1: [
                        [datetime(2024, 9, 20, 13, 18, 0, 631800), None],
                    ],
                }
            },
        )

    def test_user_connect_disconnected_two_different_channels(self):
        activity_data = [
            UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
            UserActivity(channel_id=2, user_id=2, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
        ]
        result = calculate_user_connections(activity_data)
        self.assertEqual(
            result,
            {
                1: {
                    1: [
                        [datetime(2024, 9, 20, 13, 18, 0, 631800), None],
                    ],
                },
                2: {
                    2: [
                        [datetime(2024, 9, 20, 13, 18, 0, 631800), None],
                    ],
                },
            },
        )


class TestComputeUsersWeights(unittest.TestCase):
    def setUp(self):
        pass

    def test_two_users_same_channel_single_overlap(self):
        activity_data = [
            UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
            UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
            UserActivity(2, 100, EVENT_CONNECT, "2024-09-20 13:05:0.6318", 1),
            UserActivity(2, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
        ]
        result = compute_users_weights(activity_data)
        self.assertEqual(result, {(1, 2, 100): 300})

    def test_two_users_same_channel_many_overlap(self):
        activity_data = [
            UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
            UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:30:0.6318", 1),
            UserActivity(2, 100, EVENT_CONNECT, "2024-09-20 13:05:0.6318", 1),
            UserActivity(2, 100, EVENT_DISCONNECT, "2024-09-20 13:06:0.6318", 1),
            UserActivity(2, 100, EVENT_CONNECT, "2024-09-20 13:15:0.6318", 1),
            UserActivity(2, 100, EVENT_DISCONNECT, "2024-09-20 13:16:0.6318", 1),
        ]
        result = compute_users_weights(activity_data)
        self.assertEqual(result, {(1, 2, 100): 120})

    def test_two_users_many_channels_no_overlap(self):
        activity_data = [
            UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
            UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:30:0.6318", 1),
            UserActivity(2, 200, EVENT_CONNECT, "2024-09-20 13:05:0.6318", 1),
            UserActivity(2, 200, EVENT_DISCONNECT, "2024-09-20 13:06:0.6318", 1),
        ]
        result = compute_users_weights(activity_data)
        self.assertEqual(result, {})

    def test_two_users_many_channels_many_overlap(self):
        activity_data = [
            UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
            UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
            UserActivity(2, 100, EVENT_CONNECT, "2024-09-20 13:09:0.6318", 1),
            UserActivity(2, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
            UserActivity(1, 200, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
            UserActivity(1, 200, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
            UserActivity(2, 200, EVENT_CONNECT, "2024-09-20 13:08:0.6318", 1),
            UserActivity(2, 200, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
        ]
        result = compute_users_weights(activity_data)
        self.assertEqual(result, {(1, 2, 100): 60.0, (1, 2, 200): 120.0})


class TestComputer_users_voice_in_out(unittest.TestCase):
    def setUp(self):
        pass

    def test_single_user_single_channel(self):
        activity_data = [
            UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
            UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
            UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:15:0.6318", 1),
            UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:20:0.6318", 1),
        ]
        result = computer_users_voice_in_out(activity_data)

        self.assertEqual(
            result,
            {
                1: [
                    (
                        datetime(2024, 9, 20, 13, 0, 0, 631800),
                        datetime(2024, 9, 20, 13, 10, 0, 631800),
                    ),
                    (
                        datetime(2024, 9, 20, 13, 15, 0, 631800),
                        datetime(2024, 9, 20, 13, 20, 0, 631800),
                    ),
                ]
            },
        )

    def test_many_user_single_channel(self):
        activity_data = [
            UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
            UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
            UserActivity(2, 100, EVENT_CONNECT, "2024-09-20 13:05:0.6318", 1),
            UserActivity(2, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
        ]
        result = computer_users_voice_in_out(activity_data)
        self.assertEqual(
            result,
            {
                1: [
                    (
                        datetime(2024, 9, 20, 13, 0, 0, 631800),
                        datetime(2024, 9, 20, 13, 10, 0, 631800),
                    ),
                ],
                2: [
                    (
                        datetime(2024, 9, 20, 13, 5, 0, 631800),
                        datetime(2024, 9, 20, 13, 10, 0, 631800),
                    ),
                ],
            },
        )

    def test_single_user_many_channel(self):
        activity_data = [
            UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
            UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
            UserActivity(1, 200, EVENT_CONNECT, "2024-09-20 13:15:0.6318", 1),
            UserActivity(1, 200, EVENT_DISCONNECT, "2024-09-20 13:20:0.6318", 1),
        ]
        result = computer_users_voice_in_out(activity_data)

        self.assertEqual(
            result,
            {
                1: [
                    (
                        datetime(2024, 9, 20, 13, 0, 0, 631800),
                        datetime(2024, 9, 20, 13, 10, 0, 631800),
                    ),
                    (
                        datetime(2024, 9, 20, 13, 15, 0, 631800),
                        datetime(2024, 9, 20, 13, 20, 0, 631800),
                    ),
                ]
            },
        )


class TestCompute_users_voice_channel_time_sec(unittest.TestCase):
    def setUp(self):
        pass

    def test_single_user(self):
        users_in_out = {
            1: [
                (
                    datetime(2024, 9, 20, 13, 0, 0, 631800),
                    datetime(2024, 9, 20, 13, 10, 0, 631800),
                ),
                (
                    datetime(2024, 9, 20, 13, 15, 0, 631800),
                    datetime(2024, 9, 20, 13, 20, 0, 631800),
                ),
            ]
        }
        result = compute_users_voice_channel_time_sec(users_in_out)

        self.assertEqual(
            result,
            {
                1: 900,
            },
        )

    def test_many_user(self):
        users_in_out = {
            1: [
                (
                    datetime(2024, 9, 20, 13, 0, 0, 631800),
                    datetime(2024, 9, 20, 13, 10, 0, 631800),
                ),
                (
                    datetime(2024, 9, 20, 13, 15, 0, 631800),
                    datetime(2024, 9, 20, 13, 20, 0, 631800),
                ),
            ],
            2: [
                (
                    datetime(2024, 9, 20, 13, 5, 0, 631800),
                    datetime(2024, 9, 20, 13, 10, 0, 631800),
                ),
            ],
        }
        result = compute_users_voice_channel_time_sec(users_in_out)

        self.assertEqual(
            result,
            {
                1: 900,
                2: 300,
            },
        )

    def test_single_user_without_disconnect(self):
        users_in_out = {
            1: [
                (
                    datetime(2024, 9, 20, 13, 0, 0, 631800),
                    datetime(2024, 9, 20, 13, 10, 0, 631800),
                ),
                (
                    datetime(2024, 9, 20, 13, 15, 0, 631800),
                    None,
                ),
            ]
        }
        result = compute_users_voice_channel_time_sec(users_in_out)

        self.assertEqual(
            result,
            {
                1: 600,
            },
        )


class TestUsers_last_played_over_day(unittest.TestCase):
    def setUp(self):
        pass

    @patch("deps.analytic_gatherer.datetime")
    def test_single_user_inactive(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 9, 22, 13, 30, 45)
        users_in_out = {
            1: [
                (
                    datetime(2024, 9, 20, 13, 0, 0, 631800),
                    datetime(2024, 9, 20, 13, 10, 0, 631800),
                ),
                (
                    datetime(2024, 9, 20, 13, 15, 0, 631800),
                    datetime(2024, 9, 20, 13, 20, 0, 631800),
                ),
            ]
        }
        result = users_last_played_over_day(users_in_out)

        self.assertEqual(
            result,
            {
                1: 2,
            },
        )

    @patch("deps.analytic_gatherer.datetime")
    def test_single_user_active(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 9, 21, 1, 30, 45)
        users_in_out = {
            1: [
                (
                    datetime(2024, 9, 20, 13, 0, 0, 631800),
                    datetime(2024, 9, 20, 13, 10, 0, 631800),
                ),
                (
                    datetime(2024, 9, 20, 13, 15, 0, 631800),
                    datetime(2024, 9, 20, 13, 20, 0, 631800),
                ),
            ]
        }
        result = users_last_played_over_day(users_in_out)

        self.assertEqual(
            result,
            {},
        )

    @patch("deps.analytic_gatherer.datetime")
    def test_single_user_active_data_unordered_recent_last(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 9, 21, 1, 30, 45)
        users_in_out = {
            1: [
                (
                    datetime(2024, 9, 10, 13, 0, 0, 631800),
                    datetime(2024, 9, 10, 13, 10, 0, 631800),
                ),
                (
                    datetime(2024, 9, 20, 13, 15, 0, 631800),
                    datetime(2024, 9, 20, 13, 20, 0, 631800),
                ),
            ]
        }
        result = users_last_played_over_day(users_in_out)

        self.assertEqual(
            result,
            {},
        )

    @patch("deps.analytic_gatherer.datetime")
    def test_single_user_active_data_unordered_recent_firstt(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 9, 21, 1, 30, 45)
        users_in_out = {
            1: [
                (
                    datetime(2024, 9, 20, 13, 0, 0, 631800),
                    datetime(2024, 9, 20, 13, 10, 0, 631800),
                ),
                (
                    datetime(2024, 9, 10, 13, 15, 0, 631800),
                    datetime(2024, 9, 10, 13, 20, 0, 631800),
                ),
            ]
        }
        result = users_last_played_over_day(users_in_out)

        self.assertEqual(
            result,
            {},
        )


if __name__ == "__main__":
    unittest.main()
