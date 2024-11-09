from datetime import datetime
import unittest
from deps.functions_r6_tracker import get_user_gaming_session_stats, parse_json_from_matches
import json

data = None


def setUpModule():
    global data
    with open("./tests/tests_assets/player_rank_history.json", "r", encoding="utf8") as file:
        data = json.loads(file.read())


class MatchStatsExtration(unittest.TestCase):
    """Test to get statistic about the user's match"""

    def test_data_exist_for_tests(self):
        """Test to ensure the testing file is there"""
        self.assertIsNotNone(data)

    def test_get_r6tracker_user_recent_matches(self):
        """Test if we can parse the data from the json file"""
        lst = parse_json_from_matches(data, "noSleep_rb6")
        self.assertGreaterEqual(len(lst), 1)
        match = lst[0]
        self.assertEqual(match.r6_tracker_user_uuid, "877a703b-0d29-4779-8fbf-ccd165c2b7f6")
        self.assertEqual(match.ubisoft_username, "noSleep_rb6")
        self.assertEqual(match.match_duration_ms, 895284)
        self.assertEqual(match.map_name, "Bank")
        self.assertEqual(match.has_win, False)
        self.assertEqual(match.kill_count, 0)
        self.assertEqual(match.death_count, 4)
        self.assertEqual(match.assist_count, 0)
        self.assertEqual(match.kd_ratio, 0)
        self.assertEqual(match.ace_count, 0)
        self.assertEqual(match.kill_3_count, 0)
        self.assertEqual(match.kill_4_count, 0)
        match = lst[1]
        self.assertEqual(match.r6_tracker_user_uuid, "877a703b-0d29-4779-8fbf-ccd165c2b7f6")
        self.assertEqual(match.ubisoft_username, "noSleep_rb6")
        self.assertEqual(match.match_duration_ms, 1438032)
        self.assertEqual(match.match_timestamp, datetime.fromisoformat("2024-11-07T05:38:39.175+00:00"))
        self.assertEqual(match.map_name, "Coastline")
        self.assertEqual(match.has_win, True)
        self.assertEqual(match.kill_count, 6)
        self.assertEqual(match.death_count, 2)
        self.assertEqual(match.assist_count, 1)
        self.assertEqual(match.kd_ratio, 3.0)
        self.assertEqual(match.ace_count, 0)
        self.assertEqual(match.kill_3_count, 1)
        self.assertEqual(match.kill_4_count, 0)

    def test_individual_gaming_session_stats(self):
        """Test if we can get an aggregate of a session"""
        lst = parse_json_from_matches(data, "noSleep_rb6")
        result = get_user_gaming_session_stats(
            "noSleep_rb6", datetime.fromisoformat("2024-11-07T00:00:00.000+00:00"), lst
        )
        self.assertEqual(result.match_count, 8)
        self.assertEqual(result.match_win_count, 4)
        self.assertEqual(result.match_loss_count, 4)
        self.assertEqual(result.total_kill_count, 36)
        self.assertEqual(result.total_death_count, 27)
        self.assertEqual(result.total_assist_count, 8)
        self.assertEqual(result.started_rank_points, 4038)
        self.assertEqual(result.ended_rank_points, 4051)
        self.assertEqual(result.total_gained_points, 13)
        self.assertEqual(result.total_tk_count, 0)
        self.assertEqual(result.total_round_with_aces, 0)
        self.assertEqual(result.total_round_with_4k, 0)
        self.assertEqual(result.total_round_with_3k, 2)
        self.assertEqual(result.ubisoft_username_active, "noSleep_rb6")
        self.assertEqual(result.kill_death_assist, ["0/4/0", "6/2/1", "7/4/1", "6/4/3", "4/4/1", "6/1/0", "2/2/1", "5/6/1"])


if __name__ == "__main__":
    unittest.main()
