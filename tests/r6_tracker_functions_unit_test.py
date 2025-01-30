import json
from datetime import datetime, timezone
import pytest
from deps.data_access_data_class import UserInfo
from deps.functions_r6_tracker import get_user_gaming_session_stats, parse_json_from_full_matches

mock_user1 = UserInfo(1, "noSleep_rb6", "noSleep_rb6", "noSleep_rb6", "877a703b-0d29-4779-8fbf-ccd165c2b7f6", "UTC")
mock_user2 = UserInfo(2, "joechod", "joechod", "joechod", None, "UTC")


@pytest.fixture(scope="module")
def test_data():
    """Load test data for all test cases."""
    with open("./tests/tests_assets/player_rank_history.json", "r", encoding="utf8") as file:
        data_1 = json.loads(file.read())
    with open("./tests/tests_assets/player3_rank_history.json", "r", encoding="utf8") as file:
        data_3 = json.loads(file.read())
    with open("./tests/tests_assets/player4_rank_history.json", "r", encoding="utf8") as file:
        data_4 = json.loads(file.read())
    with open("./tests/tests_assets/player5_rank_history.json", "r", encoding="utf8") as file:
        data_5 = json.loads(file.read())
    with open("./tests/tests_assets/player6_rank_history.json", "r", encoding="utf8") as file:
        data_6 = json.loads(file.read())
    return data_1, data_3, data_4, data_5, data_6


def test_data_exist_for_tests(test_data):
    """Test to ensure the testing files are loaded correctly."""
    data_1, data_3, data_4, data_5, data_6 = test_data
    assert data_1 is not None
    assert data_3 is not None
    assert data_4 is not None
    assert data_5 is not None
    assert data_6 is not None


def test_get_r6tracker_user_recent_matches(test_data):
    """Test if we can parse the data from the JSON file."""
    data_1, _, _, _, _ = test_data
    lst = parse_json_from_full_matches(data_1, mock_user1)
    assert len(lst) >= 1

    match = lst[0]
    assert match.r6_tracker_user_uuid == "877a703b-0d29-4779-8fbf-ccd165c2b7f6"
    assert match.ubisoft_username == "noSleep_rb6"
    assert match.match_duration_ms == 895284
    assert match.map_name == "Bank"
    assert match.has_win is False
    assert match.kill_count == 0
    assert match.death_count == 4
    assert match.assist_count == 0
    assert match.kd_ratio == 0
    assert match.ace_count == 0
    assert match.kill_3_count == 0
    assert match.kill_4_count == 0

    match = lst[1]
    assert match.r6_tracker_user_uuid == "877a703b-0d29-4779-8fbf-ccd165c2b7f6"
    assert match.ubisoft_username == "noSleep_rb6"
    assert match.match_duration_ms == 1438032
    assert match.match_timestamp == datetime.fromisoformat("2024-11-07T05:38:39.175+00:00")
    assert match.map_name == "Coastline"
    assert match.has_win is True
    assert match.kill_count == 6
    assert match.death_count == 2
    assert match.assist_count == 1
    assert match.kd_ratio == 3.0
    assert match.ace_count == 0
    assert match.kill_3_count == 1
    assert match.kill_4_count == 0


def test_individual_gaming_session_stats(test_data):
    """Test if we can get an aggregate of a session."""
    data_1, _, _, _, _ = test_data
    lst = parse_json_from_full_matches(data_1, mock_user1)
    result = get_user_gaming_session_stats("noSleep_rb6", datetime.fromisoformat("2024-11-07T00:00:00.000+00:00"), lst)
    assert result.match_count == 8
    assert result.match_win_count == 4
    assert result.match_loss_count == 4
    assert result.total_kill_count == 36
    assert result.total_death_count == 27
    assert result.total_assist_count == 8
    assert result.started_rank_points == 4038
    assert result.ended_rank_points == 4051
    assert result.total_gained_points == 13
    assert result.total_tk_count == 0
    assert result.total_round_with_aces == 0
    assert result.total_round_with_4k == 0
    assert result.total_round_with_3k == 2
    assert result.ubisoft_username_active == "noSleep_rb6"


def test_get_r6tracker_user_recent_matches2(test_data):
    """Test if we can parse the data from the JSON file."""
    _, data_3, _, _, _ = test_data
    lst = parse_json_from_full_matches(data_3, mock_user2)
    assert len(lst) >= 1
    assert lst[0].map_name == "Villa"
    assert lst[1].map_name == "Chalet"
    assert lst[2].map_name == "Oregon"
    assert lst[3].map_name == "Clubhouse"


def test_get_r6tracker_user_recent_matches_aggregation2(test_data):
    """Test if we can parse the data from the JSON file."""
    _, _, data_4, _, _ = test_data
    lst = parse_json_from_full_matches(data_4, mock_user1)
    datetime_last = datetime.fromisoformat("2024-11-09T00:00:00.000+00:00")
    agg = get_user_gaming_session_stats("noSleep_rb6", datetime_last, lst)
    assert len(lst) >= 1
    assert [match.map_name for match in agg.matches_recent] == [
        "Skyscraper",
        "Chalet",
        "Villa",
        "Villa",
        "Chalet",
        "Oregon",
        "Clubhouse",
    ]
    assert agg.match_count == 7
    assert agg.match_win_count == 3
    assert agg.total_kill_count == 26
    assert agg.matches_recent[6].kill_4_count == 1
    assert agg.total_round_with_4k == 1


def test_get_r6tracker_user_recent_matches_with_rollback(test_data):
    """Test if we can parse the data from the JSON file."""
    _, _, _, _, data_6 = test_data
    lst = parse_json_from_full_matches(data_6, mock_user1)
    datetime_last = datetime.fromisoformat("2024-12-26T00:00:00.000+00:00")
    agg = get_user_gaming_session_stats("noSleep_rb6", datetime_last, lst)
    assert len(lst) == 21
    assert len([match for match in lst if match.is_rollback]) == 1  # One rollback
    assert [match.map_name for match in agg.matches_recent] == [
        "Villa",
        "Chalet",
        "Consulate",
        "Clubhouse",
        "Kafe Dostoyevsky",
        "Outback",
    ]
    assert agg.match_count == 6
    assert agg.match_win_count == 2
    assert agg.total_kill_count == 23
    assert agg.total_round_with_4k == 1


def test_get_r6tracker_user_recent_matches_aggregation3(test_data):
    """Test if we can parse the data from the JSON file."""
    _, _, _, data_5, _ = test_data
    lst = parse_json_from_full_matches(data_5, mock_user1)
    datetime_last = datetime.fromisoformat("2024-11-11T00:00:00.000+00:00")
    agg = get_user_gaming_session_stats("noSleep_rb6", datetime_last, lst)
    assert len(lst) >= 1
    assert [match.map_name for match in agg.matches_recent] == ["Outback", "Bank"]
    assert agg.match_count == 2
    assert agg.total_kill_count == 7
    assert agg.total_death_count == 4
    assert agg.started_rank_points == 4045
    assert agg.ended_rank_points == 4108


def test_get_r6tracker_user_recent_matches_rollback(test_data):
    """Test that we skip the rollback"""
    _, _, _, _, data_6 = test_data
    lst = parse_json_from_full_matches(data_6, mock_user1)
    assert len(lst) == 21, "Should not skip the rollback"


def test_parse_json_from_full_matches_dataset_1(test_data):
    """Test if we can parse the data from the JSON file."""
    data_1, _, _, _, _ = test_data
    lst = parse_json_from_full_matches(data_1, mock_user1)
    assert len(lst) >= 1

    match = lst[0]
    assert match.match_uuid == "c898ccca-00d9-4b85-abe7-4e45b0b3be9e"
    assert match.match_timestamp == datetime(2024, 11, 7, 5, 56, 8, 916000, tzinfo=timezone.utc)
    assert match.match_duration_ms == 895284
    assert match.data_center == "Central US"
    assert match.session_type == "Ranked"
    assert match.map_name == "Bank"
    assert match.is_surrender is False
    assert match.is_forfeit is False
    assert match.is_rollback is False
    assert match.r6_tracker_user_uuid == "877a703b-0d29-4779-8fbf-ccd165c2b7f6"
    assert match.ubisoft_username == "noSleep_rb6"
    assert match.operators == "Mozzie,Capitão,Thatcher,Nomad"
    assert match.round_played_count == 4
    assert match.round_won_count == 0
    assert match.round_lost_count == 4
    assert match.round_disconnected_count == 0
    assert match.kill_count == 0
    assert match.death_count == 4
    assert match.assist_count == 0
    assert match.head_shot_count == 0
    assert match.tk_count == 0
    assert match.ace_count == 0
    assert match.first_kill_count == 0
    assert match.first_death_count == 1
    assert match.clutches_win_count == 0
    assert match.clutches_loss_count == 1
    assert match.clutches_win_count_1v1 == 0
    assert match.clutches_win_count_1v2 == 0
    assert match.clutches_win_count_1v3 == 0
    assert match.clutches_win_count_1v4 == 0
    assert match.clutches_win_count_1v5 == 0
    assert match.clutches_lost_count_1v1 == 0
    assert match.clutches_lost_count_1v2 == 0
    assert match.clutches_lost_count_1v3 == 1
    assert match.clutches_lost_count_1v4 == 0
    assert match.clutches_lost_count_1v5 == 0
    assert match.kill_1_count == 0
    assert match.kill_2_count == 0
    assert match.kill_3_count == 0
    assert match.kill_4_count == 0
    assert match.kill_5_count == 0
    assert match.rank_points == 4051
    assert match.rank_name == "DIAMOND V"
    assert match.points_gained == -18
    assert match.rank_previous == 4069
    assert match.kd_ratio == 0
    assert match.head_shot_percentage == 0
    assert match.kills_per_round == 0
    assert match.deaths_per_round == 1.0
    assert match.assists_per_round == 0
    assert match.has_win is False

    match = lst[1]
    assert match.match_uuid == "9681f59e-80db-4b2e-b54b-3631af76b074"
    assert match.match_timestamp == datetime(2024, 11, 7, 5, 38, 39, 175000, tzinfo=timezone.utc)
    assert match.match_duration_ms == 1438032
    assert match.data_center == "Central US"
    assert match.session_type == "Ranked"
    assert match.map_name == "Coastline"
    assert match.is_surrender is False
    assert match.is_forfeit is False
    assert match.is_rollback is False
    assert match.r6_tracker_user_uuid == "877a703b-0d29-4779-8fbf-ccd165c2b7f6"
    assert match.ubisoft_username == "noSleep_rb6"
    assert match.operators == "Mozzie,Ace,IQ,Finka"
    assert match.round_played_count == 6
    assert match.round_won_count == 4
    assert match.round_lost_count == 2
    assert match.round_disconnected_count == 0
    assert match.kill_count == 6
    assert match.death_count == 2
    assert match.assist_count == 1
    assert match.head_shot_count == 3
    assert match.tk_count == 0
    assert match.ace_count == 0
    assert match.first_kill_count == 0
    assert match.first_death_count == 0
    assert match.clutches_win_count == 0
    assert match.clutches_loss_count == 0
    assert match.clutches_win_count_1v1 == 0
    assert match.clutches_win_count_1v2 == 0
    assert match.clutches_win_count_1v3 == 0
    assert match.clutches_win_count_1v4 == 0
    assert match.clutches_win_count_1v5 == 0
    assert match.clutches_lost_count_1v1 == 0
    assert match.clutches_lost_count_1v2 == 0
    assert match.clutches_lost_count_1v3 == 0
    assert match.clutches_lost_count_1v4 == 0
    assert match.clutches_lost_count_1v5 == 0
    assert match.kill_1_count == 1
    assert match.kill_2_count == 1
    assert match.kill_3_count == 1
    assert match.kill_4_count == 0
    assert match.kill_5_count == 0
    assert match.rank_points == 4069
    assert match.rank_name == "DIAMOND V"
    assert match.points_gained == 21
    assert match.rank_previous == 4048
    assert match.kd_ratio == 3
    assert match.head_shot_percentage == 50.0
    assert match.kills_per_round == 1.0
    assert match.deaths_per_round == 0.3333333333333333
    assert match.assists_per_round == 0.16666666666666666
    assert match.has_win is True


def test_parse_json_from_full_matches_dataset_6_rollback(test_data):
    """Test if we can parse the data from the JSON file."""
    _, _, _, _, data_6 = test_data
    lst = parse_json_from_full_matches(data_6, mock_user1)
    assert len(lst) >= 1

    match = lst[3]
    assert match.match_uuid == "rollback-1735219556"
    assert match.match_timestamp == datetime(2024, 12, 26, 13, 25, 56, 781231, tzinfo=timezone.utc)
    assert match.match_duration_ms == 0
    assert match.data_center == "Unknown"
    assert match.session_type == "Ranked"
    assert match.map_name == "Unknown"
    assert match.is_surrender is False
    assert match.is_forfeit is False
    assert match.is_rollback is True
    assert match.r6_tracker_user_uuid == "17d71d95-21d1-427a-979b-c8798fec55ef"
    assert match.ubisoft_username == "noSleep_rb6"
    assert match.operators == ""
    assert match.round_played_count == 0
    assert match.round_won_count == 0
    assert match.round_lost_count == 0
    assert match.round_disconnected_count == 0
    assert match.kill_count == 0
    assert match.death_count == 0
    assert match.assist_count == 0
    assert match.head_shot_count == 0
    assert match.tk_count == 0
    assert match.ace_count == 0
    assert match.first_kill_count == 0
    assert match.first_death_count == 0
    assert match.clutches_win_count == 0
    assert match.clutches_loss_count == 0
    assert match.clutches_win_count_1v1 == 0
    assert match.clutches_win_count_1v2 == 0
    assert match.clutches_win_count_1v3 == 0
    assert match.clutches_win_count_1v4 == 0
    assert match.clutches_win_count_1v5 == 0
    assert match.clutches_lost_count_1v1 == 0
    assert match.clutches_lost_count_1v2 == 0
    assert match.clutches_lost_count_1v3 == 0
    assert match.clutches_lost_count_1v4 == 0
    assert match.clutches_lost_count_1v5 == 0
    assert match.kill_1_count == 0
    assert match.kill_2_count == 0
    assert match.kill_3_count == 0
    assert match.kill_4_count == 0
    assert match.kill_5_count == 0
    assert match.rank_points == 2183
    assert match.rank_name == "SILVER IV"
    assert match.points_gained == 24
    assert match.rank_previous == 2159
    assert match.kd_ratio == 0
    assert match.head_shot_percentage == 0
    assert match.kills_per_round == 0
    assert match.deaths_per_round == 0
    assert match.assists_per_round == 0
    assert match.has_win is False


def test_get_r6tracker_parse_one_map(test_data):
    """
    Test that we can load a string
    """
    data_dict = json.loads(
        """{
            "data": {
                "matches": [
                    {
                        "attributes": {
                            "id": "4085b427-bc6f-4e6d-a1cc-97278f0483a3",
                            "sessionType": "ranked",
                            "sessionGameMode": "bomb",
                            "sessionMode": "bomb",
                            "sessionMap": "villa",
                            "datacenter": "US East",
                            "gamemode": "pvp_ranked"
                        },
                        "metadata": {
                            "timestamp": "2024-12-28T12:36:40.035+00:00",
                            "duration": 1308215,
                            "datacenter": "US East",
                            "sessionTypeName": "Ranked",
                            "sessionGameModeName": "Bomb",
                            "sessionModeName": "Bomb",
                            "sessionMapName": "Villa",
                            "sessionMapImageUrl": "https://trackercdn.com/cdn/r6.tracker.network/images/maps/villa.jpg",
                            "isSurrender": false,
                            "isForfeit": false,
                            "isRollback": false,
                            "hasOverwolfRoster": true,
                            "overwolfMatchVariants": [
                                {
                                    "matchId": "4085b427-bc6f-4e6d-a1cc-97278f0483a3",
                                    "platformUserId": "17d71d95-21d1-427a-979b-c8798fec55ef",
                                    "platformUserHandle": "swirlllllll"
                                },
                                {
                                    "matchId": "4085b427-bc6f-4e6d-a1cc-97278f0483a3",
                                    "platformUserId": "1f0ccd82-7258-46e1-bf90-1b000bc497ab",
                                    "platformUserHandle": "maxxdaboss_123"
                                },
                                {
                                    "matchId": "4085b427-bc6f-4e6d-a1cc-97278f0483a3",
                                    "platformUserId": "1fb0bc42-4547-4573-9adc-6d294a1b212f",
                                    "platformUserHandle": "z3n_on_tt"
                                }
                            ],
                            "gamemodeName": "Ranked",
                            "hasSessionData": true,
                            "hasSessionKillRecordsData": false
                        },
                        "segments": [
                            {
                                "type": "overview",
                                "attributes": {
                                    "playerId": "17d71d95-21d1-427a-979b-c8798fec55ef",
                                    "teamId": 1
                                },
                                "metadata": {
                                    "platformFamily": "pc",
                                    "platformSlug": "ubi",
                                    "result": "loss",
                                    "hasWon": false,
                                    "status": "connected",
                                    "hasExtraStats": false,
                                    "platformUserId": "17d71d95-21d1-427a-979b-c8798fec55ef",
                                    "platformUserHandle": "swirlllllll",
                                    "platformUserIdentifier": "swirlllllll",
                                    "avatarUrl": "https://ubisoft-avatars.akamaized.net/17d71d95-21d1-427a-979b-c8798fec55ef/default_256_256.png",
                                    "operators": [
                                        {
                                            "name": "Fenrir",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/operators/badges/fenrir.png"
                                        },
                                        {
                                            "name": "Ace",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/operators/badges/ace.png"
                                        },
                                        {
                                            "name": "Mute",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/operators/badges/mute.png"
                                        },
                                        {
                                            "name": "Echo",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/operators/badges/echo.png"
                                        }
                                    ]
                                },
                                "expiryDate": "0001-01-01T00:00:00+00:00",
                                "stats": {
                                    "timePlayed": {
                                        "displayName": "Time Played",
                                        "metadata": {},
                                        "value": 1308215,
                                        "displayValue": "21m 48s",
                                        "displayType": "TimeMilliseconds"
                                    },
                                    "roundsPlayed": {
                                        "displayName": "Rounds Played",
                                        "metadata": {},
                                        "value": 6,
                                        "displayValue": "6",
                                        "displayType": "Number"
                                    },
                                    "roundsWon": {
                                        "displayName": "Wins",
                                        "metadata": {},
                                        "value": 2,
                                        "displayValue": "2",
                                        "displayType": "Number"
                                    },
                                    "roundsLost": {
                                        "displayName": "Losses",
                                        "metadata": {},
                                        "value": 4,
                                        "displayValue": "4",
                                        "displayType": "Number"
                                    },
                                    "roundsDisconnected": {
                                        "displayName": "Disconnected",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "roundWinPct": {
                                        "displayName": "Win %",
                                        "metadata": {},
                                        "value": 33.33333333333333,
                                        "displayValue": "33.3%",
                                        "displayType": "NumberPercentage"
                                    },
                                    "score": {
                                        "displayName": "Score",
                                        "metadata": {},
                                        "value": 2,
                                        "displayValue": "2",
                                        "displayType": "Number"
                                    },
                                    "kills": {
                                        "displayName": "Kills",
                                        "metadata": {},
                                        "value": 6,
                                        "displayValue": "6",
                                        "displayType": "Number"
                                    },
                                    "deaths": {
                                        "displayName": "Deaths",
                                        "metadata": {},
                                        "value": 5,
                                        "displayValue": "5",
                                        "displayType": "Number"
                                    },
                                    "assists": {
                                        "displayName": "Assists",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "headshots": {
                                        "displayName": "Headshots",
                                        "metadata": {},
                                        "value": 5,
                                        "displayValue": "5",
                                        "displayType": "Number"
                                    },
                                    "teamKills": {
                                        "displayName": "TKs",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "aces": {
                                        "displayName": "Aces",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "firstBloods": {
                                        "displayName": "First Bloods",
                                        "metadata": {},
                                        "value": 1,
                                        "displayValue": "1",
                                        "displayType": "Number"
                                    },
                                    "firstDeaths": {
                                        "displayName": "First Deaths",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches": {
                                        "displayName": "Clutches",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost": {
                                        "displayName": "Clutches Lost",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v1": {
                                        "displayName": "Clutches 1v1",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v2": {
                                        "displayName": "Clutches 1v2",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v3": {
                                        "displayName": "Clutches 1v3",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v4": {
                                        "displayName": "Clutches 1v4",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v5": {
                                        "displayName": "Clutches 1v5",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v1": {
                                        "displayName": "Clutches Lost 1v1",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v2": {
                                        "displayName": "Clutches Lost 1v2",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v3": {
                                        "displayName": "Clutches Lost 1v3",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v4": {
                                        "displayName": "Clutches Lost 1v4",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v5": {
                                        "displayName": "Clutches Lost 1v5",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "kills1K": {
                                        "displayName": "Kills 1K",
                                        "metadata": {},
                                        "value": 2,
                                        "displayValue": "2",
                                        "displayType": "Number"
                                    },
                                    "kills2K": {
                                        "displayName": "Kills 2K",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "kills3K": {
                                        "displayName": "Kills 3K",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "kills4K": {
                                        "displayName": "Kills 4K",
                                        "metadata": {},
                                        "value": 1,
                                        "displayValue": "1",
                                        "displayType": "Number"
                                    },
                                    "kills5K": {
                                        "displayName": "Aces",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "kills6K": {
                                        "displayName": "Kills 6K+",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "rank": {
                                        "displayName": "Rank",
                                        "metadata": {},
                                        "value": 12,
                                        "displayValue": "12",
                                        "displayType": "Number"
                                    },
                                    "rankPoints": {
                                        "displayName": "Rank Points",
                                        "metadata": {
                                            "name": "SILVER IV",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-4.png",
                                            "topRankPosition": null
                                        },
                                        "value": 2168,
                                        "displayValue": "2,168",
                                        "displayType": "Number"
                                    },
                                    "topRankPosition": {
                                        "displayName": "Top Rank Position",
                                        "metadata": {},
                                        "value": null,
                                        "displayValue": null,
                                        "displayType": "Number"
                                    },
                                    "rankPointsDelta": {
                                        "displayName": "Rank Points Delta",
                                        "metadata": {
                                            "name": "SILVER IV",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-4.png"
                                        },
                                        "value": -22,
                                        "displayValue": "-22",
                                        "displayType": "String"
                                    },
                                    "rankPrevious": {
                                        "displayName": "Rank",
                                        "metadata": {},
                                        "value": 12,
                                        "displayValue": "12",
                                        "displayType": "Number"
                                    },
                                    "rankPointsPrevious": {
                                        "displayName": "Rank Points",
                                        "metadata": {},
                                        "value": 2190,
                                        "displayValue": "2,190",
                                        "displayType": "Number"
                                    },
                                    "topRankPositionPrevious": {
                                        "displayName": "Top Rank Position",
                                        "metadata": {},
                                        "value": null,
                                        "displayValue": null,
                                        "displayType": "Number"
                                    },
                                    "kdRatio": {
                                        "displayName": "K/D",
                                        "metadata": {},
                                        "value": 1.2,
                                        "displayValue": "1.20",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "headshotPct": {
                                        "displayName": "HS %",
                                        "metadata": {},
                                        "value": 83.33333333333334,
                                        "displayValue": "83.3%",
                                        "displayType": "NumberPercentage"
                                    },
                                    "killsPerRound": {
                                        "displayName": "Kills/Round",
                                        "metadata": {},
                                        "value": 1.0,
                                        "displayValue": "1.00",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "deathsPerRound": {
                                        "displayName": "Deaths/Round",
                                        "metadata": {},
                                        "value": 0.8333333333333334,
                                        "displayValue": "0.83",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "assistsPerRound": {
                                        "displayName": "Assists/Round",
                                        "metadata": {},
                                        "value": 0.0,
                                        "displayValue": "0.00",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "headshotsPerRound": {
                                        "displayName": "Headshots/Round",
                                        "metadata": {},
                                        "value": 0.8333333333333334,
                                        "displayValue": "0.83",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "esr": {
                                        "displayName": "ESR",
                                        "metadata": {},
                                        "value": 1.0,
                                        "displayValue": "1.00",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "eloDelta": {
                                        "displayName": "Elo Delta",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "matches": {
                                        "displayName": "Matches",
                                        "metadata": {},
                                        "value": 1,
                                        "displayValue": "1",
                                        "displayType": "Number"
                                    },
                                    "wins": {
                                        "displayName": "Wins",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "losses": {
                                        "displayName": "Losses",
                                        "metadata": {},
                                        "value": 1,
                                        "displayValue": "1",
                                        "displayType": "Number"
                                    },
                                    "abandons": {
                                        "displayName": "Abandons",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "matchesWinPct": {
                                        "displayName": "Win %",
                                        "metadata": {},
                                        "value": 0.0,
                                        "displayValue": "0.0%",
                                        "displayType": "NumberPercentage"
                                    },
                                    "killsPerMatch": {
                                        "displayName": "Kills/Match",
                                        "metadata": {},
                                        "value": 6,
                                        "displayValue": "6.00",
                                        "displayType": "NumberPrecision2"
                                    }
                                }
                            }
                        ],
                        "streams": null,
                        "expiryDate": "0001-01-01T00:00:00+00:00"
                    }
                ]
            }
        }
    """
    )
    lst = parse_json_from_full_matches(data_dict, mock_user1)

    assert len(lst) >= 1


def test_get_r6tracker_parse_with_null_map(test_data):
    """
    Test that we can load a string but with a map to null
    """
    data_dict = json.loads(
        """{
            "data": {
                "matches": [
                    {
                        "attributes": {
                            "id": "4085b427-bc6f-4e6d-a1cc-97278f0483a3",
                            "sessionType": "ranked",
                            "sessionGameMode": "bomb",
                            "sessionMode": "bomb",
                            "sessionMap": "villa",
                            "datacenter": "US East",
                            "gamemode": "pvp_ranked"
                        },
                        "metadata": {
                            "timestamp": "2024-12-28T12:36:40.035+00:00",
                            "duration": 1308215,
                            "datacenter": "US East",
                            "sessionTypeName": "Ranked",
                            "sessionGameModeName": "Bomb",
                            "sessionModeName": "Bomb",
                            "sessionMapName": null,
                            "sessionMapImageUrl": "https://trackercdn.com/cdn/r6.tracker.network/images/maps/villa.jpg",
                            "isSurrender": false,
                            "isForfeit": false,
                            "isRollback": false,
                            "hasOverwolfRoster": true,
                            "overwolfMatchVariants": [
                                {
                                    "matchId": "4085b427-bc6f-4e6d-a1cc-97278f0483a3",
                                    "platformUserId": "17d71d95-21d1-427a-979b-c8798fec55ef",
                                    "platformUserHandle": "swirlllllll"
                                },
                                {
                                    "matchId": "4085b427-bc6f-4e6d-a1cc-97278f0483a3",
                                    "platformUserId": "1f0ccd82-7258-46e1-bf90-1b000bc497ab",
                                    "platformUserHandle": "maxxdaboss_123"
                                },
                                {
                                    "matchId": "4085b427-bc6f-4e6d-a1cc-97278f0483a3",
                                    "platformUserId": "1fb0bc42-4547-4573-9adc-6d294a1b212f",
                                    "platformUserHandle": "z3n_on_tt"
                                }
                            ],
                            "gamemodeName": "Ranked",
                            "hasSessionData": true,
                            "hasSessionKillRecordsData": false
                        },
                        "segments": [
                            {
                                "type": "overview",
                                "attributes": {
                                    "playerId": "17d71d95-21d1-427a-979b-c8798fec55ef",
                                    "teamId": 1
                                },
                                "metadata": {
                                    "platformFamily": "pc",
                                    "platformSlug": "ubi",
                                    "result": "loss",
                                    "hasWon": false,
                                    "status": "connected",
                                    "hasExtraStats": false,
                                    "platformUserId": "17d71d95-21d1-427a-979b-c8798fec55ef",
                                    "platformUserHandle": "swirlllllll",
                                    "platformUserIdentifier": "swirlllllll",
                                    "avatarUrl": "https://ubisoft-avatars.akamaized.net/17d71d95-21d1-427a-979b-c8798fec55ef/default_256_256.png",
                                    "operators": [
                                        {
                                            "name": "Fenrir",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/operators/badges/fenrir.png"
                                        },
                                        {
                                            "name": "Ace",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/operators/badges/ace.png"
                                        },
                                        {
                                            "name": "Mute",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/operators/badges/mute.png"
                                        },
                                        {
                                            "name": "Echo",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/operators/badges/echo.png"
                                        }
                                    ]
                                },
                                "expiryDate": "0001-01-01T00:00:00+00:00",
                                "stats": {
                                    "timePlayed": {
                                        "displayName": "Time Played",
                                        "metadata": {},
                                        "value": 1308215,
                                        "displayValue": "21m 48s",
                                        "displayType": "TimeMilliseconds"
                                    },
                                    "roundsPlayed": {
                                        "displayName": "Rounds Played",
                                        "metadata": {},
                                        "value": 6,
                                        "displayValue": "6",
                                        "displayType": "Number"
                                    },
                                    "roundsWon": {
                                        "displayName": "Wins",
                                        "metadata": {},
                                        "value": 2,
                                        "displayValue": "2",
                                        "displayType": "Number"
                                    },
                                    "roundsLost": {
                                        "displayName": "Losses",
                                        "metadata": {},
                                        "value": 4,
                                        "displayValue": "4",
                                        "displayType": "Number"
                                    },
                                    "roundsDisconnected": {
                                        "displayName": "Disconnected",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "roundWinPct": {
                                        "displayName": "Win %",
                                        "metadata": {},
                                        "value": 33.33333333333333,
                                        "displayValue": "33.3%",
                                        "displayType": "NumberPercentage"
                                    },
                                    "score": {
                                        "displayName": "Score",
                                        "metadata": {},
                                        "value": 2,
                                        "displayValue": "2",
                                        "displayType": "Number"
                                    },
                                    "kills": {
                                        "displayName": "Kills",
                                        "metadata": {},
                                        "value": 6,
                                        "displayValue": "6",
                                        "displayType": "Number"
                                    },
                                    "deaths": {
                                        "displayName": "Deaths",
                                        "metadata": {},
                                        "value": 5,
                                        "displayValue": "5",
                                        "displayType": "Number"
                                    },
                                    "assists": {
                                        "displayName": "Assists",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "headshots": {
                                        "displayName": "Headshots",
                                        "metadata": {},
                                        "value": 5,
                                        "displayValue": "5",
                                        "displayType": "Number"
                                    },
                                    "teamKills": {
                                        "displayName": "TKs",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "aces": {
                                        "displayName": "Aces",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "firstBloods": {
                                        "displayName": "First Bloods",
                                        "metadata": {},
                                        "value": 1,
                                        "displayValue": "1",
                                        "displayType": "Number"
                                    },
                                    "firstDeaths": {
                                        "displayName": "First Deaths",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches": {
                                        "displayName": "Clutches",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost": {
                                        "displayName": "Clutches Lost",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v1": {
                                        "displayName": "Clutches 1v1",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v2": {
                                        "displayName": "Clutches 1v2",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v3": {
                                        "displayName": "Clutches 1v3",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v4": {
                                        "displayName": "Clutches 1v4",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutches1v5": {
                                        "displayName": "Clutches 1v5",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v1": {
                                        "displayName": "Clutches Lost 1v1",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v2": {
                                        "displayName": "Clutches Lost 1v2",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v3": {
                                        "displayName": "Clutches Lost 1v3",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v4": {
                                        "displayName": "Clutches Lost 1v4",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "clutchesLost1v5": {
                                        "displayName": "Clutches Lost 1v5",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "kills1K": {
                                        "displayName": "Kills 1K",
                                        "metadata": {},
                                        "value": 2,
                                        "displayValue": "2",
                                        "displayType": "Number"
                                    },
                                    "kills2K": {
                                        "displayName": "Kills 2K",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "kills3K": {
                                        "displayName": "Kills 3K",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "kills4K": {
                                        "displayName": "Kills 4K",
                                        "metadata": {},
                                        "value": 1,
                                        "displayValue": "1",
                                        "displayType": "Number"
                                    },
                                    "kills5K": {
                                        "displayName": "Aces",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "kills6K": {
                                        "displayName": "Kills 6K+",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "rank": {
                                        "displayName": "Rank",
                                        "metadata": {},
                                        "value": 12,
                                        "displayValue": "12",
                                        "displayType": "Number"
                                    },
                                    "rankPoints": {
                                        "displayName": "Rank Points",
                                        "metadata": {
                                            "name": "SILVER IV",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-4.png",
                                            "topRankPosition": null
                                        },
                                        "value": 2168,
                                        "displayValue": "2,168",
                                        "displayType": "Number"
                                    },
                                    "topRankPosition": {
                                        "displayName": "Top Rank Position",
                                        "metadata": {},
                                        "value": null,
                                        "displayValue": null,
                                        "displayType": "Number"
                                    },
                                    "rankPointsDelta": {
                                        "displayName": "Rank Points Delta",
                                        "metadata": {
                                            "name": "SILVER IV",
                                            "imageUrl": "https://trackercdn.com/cdn/r6.tracker.network/ranks/s28/small/silver-4.png"
                                        },
                                        "value": -22,
                                        "displayValue": "-22",
                                        "displayType": "String"
                                    },
                                    "rankPrevious": {
                                        "displayName": "Rank",
                                        "metadata": {},
                                        "value": 12,
                                        "displayValue": "12",
                                        "displayType": "Number"
                                    },
                                    "rankPointsPrevious": {
                                        "displayName": "Rank Points",
                                        "metadata": {},
                                        "value": 2190,
                                        "displayValue": "2,190",
                                        "displayType": "Number"
                                    },
                                    "topRankPositionPrevious": {
                                        "displayName": "Top Rank Position",
                                        "metadata": {},
                                        "value": null,
                                        "displayValue": null,
                                        "displayType": "Number"
                                    },
                                    "kdRatio": {
                                        "displayName": "K/D",
                                        "metadata": {},
                                        "value": 1.2,
                                        "displayValue": "1.20",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "headshotPct": {
                                        "displayName": "HS %",
                                        "metadata": {},
                                        "value": 83.33333333333334,
                                        "displayValue": "83.3%",
                                        "displayType": "NumberPercentage"
                                    },
                                    "killsPerRound": {
                                        "displayName": "Kills/Round",
                                        "metadata": {},
                                        "value": 1.0,
                                        "displayValue": "1.00",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "deathsPerRound": {
                                        "displayName": "Deaths/Round",
                                        "metadata": {},
                                        "value": 0.8333333333333334,
                                        "displayValue": "0.83",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "assistsPerRound": {
                                        "displayName": "Assists/Round",
                                        "metadata": {},
                                        "value": 0.0,
                                        "displayValue": "0.00",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "headshotsPerRound": {
                                        "displayName": "Headshots/Round",
                                        "metadata": {},
                                        "value": 0.8333333333333334,
                                        "displayValue": "0.83",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "esr": {
                                        "displayName": "ESR",
                                        "metadata": {},
                                        "value": 1.0,
                                        "displayValue": "1.00",
                                        "displayType": "NumberPrecision2"
                                    },
                                    "eloDelta": {
                                        "displayName": "Elo Delta",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "matches": {
                                        "displayName": "Matches",
                                        "metadata": {},
                                        "value": 1,
                                        "displayValue": "1",
                                        "displayType": "Number"
                                    },
                                    "wins": {
                                        "displayName": "Wins",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "losses": {
                                        "displayName": "Losses",
                                        "metadata": {},
                                        "value": 1,
                                        "displayValue": "1",
                                        "displayType": "Number"
                                    },
                                    "abandons": {
                                        "displayName": "Abandons",
                                        "metadata": {},
                                        "value": 0,
                                        "displayValue": "0",
                                        "displayType": "Number"
                                    },
                                    "matchesWinPct": {
                                        "displayName": "Win %",
                                        "metadata": {},
                                        "value": 0.0,
                                        "displayValue": "0.0%",
                                        "displayType": "NumberPercentage"
                                    },
                                    "killsPerMatch": {
                                        "displayName": "Kills/Match",
                                        "metadata": {},
                                        "value": 6,
                                        "displayValue": "6.00",
                                        "displayType": "NumberPrecision2"
                                    }
                                }
                            }
                        ],
                        "streams": null,
                        "expiryDate": "0001-01-01T00:00:00+00:00"
                    }
                ]
            }
        }
    """
    )
    lst = parse_json_from_full_matches(data_dict, mock_user1)

    assert len(lst) == 0
