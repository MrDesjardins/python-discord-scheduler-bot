""" Unit tests for the analytic_gatherer module """

from datetime import datetime
import unittest
from deps.analytic import EVENT_CONNECT, EVENT_DISCONNECT
from deps.analytic_gatherer import calculate_overlap, calculate_user_connections


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
            (1, 1, EVENT_CONNECT, "2024-09-20 13:18:0.6318", 1),
            (2, 1, EVENT_CONNECT, "2024-09-20 13:18:1.6318", 1),
            (1, 1, EVENT_DISCONNECT, "2024-09-20 13:18:3.6318", 1),
            (2, 1, EVENT_DISCONNECT, "2024-09-20 13:18:4.6318", 1),
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
            (1, 1, EVENT_CONNECT, "2024-09-20 13:18:0.6318", 1),
            (2, 1, EVENT_CONNECT, "2024-09-20 13:18:1.6318", 1),
            (1, 1, EVENT_DISCONNECT, "2024-09-20 13:18:3.6318", 1),
            (2, 1, EVENT_DISCONNECT, "2024-09-20 13:18:4.6318", 1),
            (1, 1, EVENT_CONNECT, "2024-09-20 13:20:1.6318", 1),
            (1, 1, EVENT_DISCONNECT, "2024-09-20 13:20:10.6318", 1),
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

    def test_user_connect_and_never_disconnected(self):
        activity_data = [
            (1, 1, EVENT_CONNECT, "2024-09-20 13:18:0.6318", 1),
            (1, 1, EVENT_DISCONNECT, "2024-09-20 13:18:3.6318", 1),
            (1, 2, EVENT_CONNECT, "2024-09-20 13:28:1.6318", 1),
            (1, 2, EVENT_DISCONNECT, "2024-09-20 13:28:4.6318", 1),
        ]
        result = calculate_user_connections(activity_data)
        self.assertEqual(
            result,
            {
                1: {
                    1: [
                        [datetime(2024, 9, 20, 13, 18, 0, 631800), datetime(2024, 9, 20, 13, 18, 3, 631800)],
                    ],
                },
                2: {
                    1: [
                        [datetime(2024, 9, 20, 13, 28, 1, 631800), datetime(2024, 9, 20, 13, 28, 4, 631800)],
                    ],
                },
            },
        )

    def test_user_connect_disconnected_two_different_channels(self):
        activity_data = [(1, 1, EVENT_CONNECT, "2024-09-20 13:18:0.6318", 1)]
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


if __name__ == "__main__":
    unittest.main()
