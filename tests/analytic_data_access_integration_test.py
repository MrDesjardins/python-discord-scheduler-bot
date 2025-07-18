"""Test that touch the bet and the database"""

import json
from datetime import datetime, timezone
from unittest.mock import call, patch
import pytest

from deps.analytic_functions import compute_users_weights
from deps.data_access_data_class import UserInfo
from deps.analytic_data_access import (
    data_access_fetch_tk_count_by_user,
    data_access_fetch_user_full_match_info,
    data_access_fetch_user_full_user_info,
    fetch_all_user_activities,
    fetch_user_info_by_user_id_list,
    get_active_user_info,
    insert_if_nonexistant_full_match_info,
    insert_if_nonexistant_full_user_info,
    insert_user_activity,
    upsert_user_info,
)
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, EVENT_CONNECT, EVENT_DISCONNECT, database_manager
from deps.models import UserFullMatchStats
from deps.functions_r6_tracker import parse_json_from_full_matches, parse_json_user_full_stats_info
from deps import analytic_data_access

fake_date = datetime(2024, 11, 1, 12, 30, 0, tzinfo=timezone.utc)
CHANNEL1_ID = 100
CHANNEL2_ID = 200
GUILD_ID = 1000


# # Apply patch globally
# patcher = patch("deps.analytic_data_access.print_log", lambda *args, **kwargs: None)
# patcher.start()  # Start the patch before tests run
def get_test_data():
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


def get_user_full_info_test_data():
    """Load test data for user full info."""
    with open("./tests/tests_assets/player_profile.json", "r", encoding="utf8") as file:
        data_1 = json.loads(file.read())
    with open("./tests/tests_assets/player_profile2.json", "r", encoding="utf8") as file:
        data_2 = json.loads(file.read())
    return data_1, data_2


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


def test_user_not_in_user_info_table():
    """Testing when user does not have an entry in the info table"""
    users = fetch_user_info_by_user_id_list([1, 2, 3])
    assert users == [None, None, None]


def test_user_in_and_not_in_user_info_table():
    """Testing when 1 user in and 2 does not have an entry in the info table"""
    insert_user_activity(1, "user_1", 1, 1, EVENT_CONNECT, datetime(2024, 9, 20, 13, 20, 0, 6318))
    users = fetch_user_info_by_user_id_list([1, 2, 3])
    assert len(users) == 3
    assert users[0].id == 1
    assert users[1] is None
    assert users[2] is None


def test_get_only_user_active():
    """
    Insert many activity, get the active one and retrieve only the one in the between the time
    Return unique user
    Return max account if no active defined
    """
    upsert_user_info(1, "DiscordName1", "ubi_1_max", "ubi_1_active", None, "US/Eastern")
    upsert_user_info(2, "DiscordName2", "ubi_2_max", "ubi_2_active", None, "US/Eastern")
    upsert_user_info(3, "DiscordName2", "ubi_3_max", None, None, "US/Eastern")
    upsert_user_info(4, "DiscordName4", None, None, None, "US/Eastern")
    insert_user_activity(
        1,
        "user_1",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 13, 20, 0, 0),
    )
    insert_user_activity(
        1,
        "user_1",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 13, 25, 0, 0),
    )
    insert_user_activity(
        2,
        "user_2",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 18, 20, 0, 0),
    )
    insert_user_activity(
        3,
        "user_3",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 21, 6, 0, 0, 0),
    )
    insert_user_activity(
        4,
        "user_4",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 14, 0, 0, 0),
    )
    users = get_active_user_info(datetime(2024, 9, 20, 0, 0, 0, 0), datetime(2024, 9, 20, 19, 0, 0, 0))
    assert len(users) == 2
    assert users[0].id == 1
    assert users[1].id == 2


@patch.object(analytic_data_access, analytic_data_access.print_log.__name__)
def test_insert_if_nonexistant_user_full_stats_info(mock_log):
    """
    Test the insertion of statistic into the database
    """
    data_1, data_2 = get_user_full_info_test_data()
    mock_log.side_effect = None
    user_info = UserInfo(1, "DiscordName1", "ubi_1_max", "ubi_1_active", None, "US/Eastern")
    user_info2 = UserInfo(2, "DiscordName1", "ubi_1_max", "ubi_1_active", None, "US/Eastern")
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        None,
        user_info.time_zone,
    )
    upsert_user_info(
        user_info2.id,
        user_info2.display_name,
        user_info2.ubisoft_username_max,
        user_info.ubisoft_username_active,
        None,
        user_info2.time_zone,
    )
    user_full_1 = parse_json_user_full_stats_info(user_info.id, data_1)
    user_full_2 = parse_json_user_full_stats_info(user_info2.id, data_2)

    insert_if_nonexistant_full_user_info(user_info, user_full_1)
    insert_if_nonexistant_full_user_info(user_info2, user_full_2)


@patch.object(analytic_data_access, analytic_data_access.print_log.__name__)
def test_insert_if_nonexistant_user_full_stats_info_then_fetch_back(mock_log):
    """
    Test the insertion of statistic into the database
    """
    data_1, _ = get_user_full_info_test_data()
    mock_log.side_effect = None
    user_info = UserInfo(1, "DiscordName1", "ubi_1_max", "ubi_1_active", None, "US/Eastern")

    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        None,
        user_info.time_zone,
    )

    user_full_1 = parse_json_user_full_stats_info(user_info.id, data_1)

    insert_if_nonexistant_full_user_info(user_info, user_full_1)
    result = data_access_fetch_user_full_user_info(user_info.id)
    assert result is not None
    assert result.user_id == user_full_1.user_id
    assert result.r6_tracker_user_uuid == user_full_1.r6_tracker_user_uuid
    assert result.total_matches_played == user_full_1.total_matches_played
    assert result.total_matches_won == user_full_1.total_matches_won
    assert result.total_matches_lost == user_full_1.total_matches_lost
    assert result.total_matches_abandoned == user_full_1.total_matches_abandoned
    assert result.time_played_seconds == user_full_1.time_played_seconds
    assert result.total_kills == user_full_1.total_kills
    assert result.total_deaths == user_full_1.total_deaths
    assert result.total_attacker_round_wins == user_full_1.total_attacker_round_wins
    assert result.total_defender_round_wins == user_full_1.total_defender_round_wins
    assert result.total_headshots == user_full_1.total_headshots
    assert result.total_headshots_missed == user_full_1.total_headshots_missed
    assert result.headshot_percentage == user_full_1.headshot_percentage
    assert result.total_wall_bang == user_full_1.total_wall_bang
    assert result.total_damage == user_full_1.total_damage
    assert result.total_assists == user_full_1.total_assists
    assert result.total_team_kills == user_full_1.total_team_kills
    assert result.attacked_breacher_count == user_full_1.attacked_breacher_count
    assert result.attacked_breacher_percentage == user_full_1.attacked_breacher_percentage
    assert result.attacked_fragger_count == user_full_1.attacked_fragger_count
    assert result.attacked_fragger_percentage == user_full_1.attacked_fragger_percentage
    assert result.attacked_intel_count == user_full_1.attacked_intel_count
    assert result.attacked_intel_percentage == user_full_1.attacked_intel_percentage
    assert result.attacked_roam_count == user_full_1.attacked_roam_count
    assert result.attacked_roam_percentage == user_full_1.attacked_roam_percentage
    assert result.attacked_support_count == user_full_1.attacked_support_count
    assert result.attacked_support_percentage == user_full_1.attacked_support_percentage
    assert result.attacked_utility_count == user_full_1.attacked_utility_count
    assert result.attacked_utility_percentage == user_full_1.attacked_utility_percentage
    assert result.defender_debuffer_count == user_full_1.defender_debuffer_count
    assert result.defender_debuffer_percentage == user_full_1.defender_debuffer_percentage
    assert result.defender_entry_denier_count == user_full_1.defender_entry_denier_count
    assert result.defender_entry_denier_percentage == user_full_1.defender_entry_denier_percentage
    assert result.defender_intel_count == user_full_1.defender_intel_count
    assert result.defender_intel_percentage == user_full_1.defender_intel_percentage
    assert result.defender_support_count == user_full_1.defender_support_count
    assert result.defender_support_percentage == user_full_1.defender_support_percentage
    assert result.defender_trapper_count == user_full_1.defender_trapper_count
    assert result.defender_trapper_percentage == user_full_1.defender_trapper_percentage
    assert result.defender_utility_denier_count == user_full_1.defender_utility_denier_count
    assert result.defender_utility_denier_percentage == user_full_1.defender_utility_denier_percentage
    assert result.kd_ratio == user_full_1.kd_ratio
    assert result.kill_per_match == user_full_1.kill_per_match
    assert result.kill_per_minute == user_full_1.kill_per_minute
    assert result.win_percentage == user_full_1.win_percentage
    assert result.rank_match_played == user_full_1.rank_match_played
    assert result.rank_match_won == user_full_1.rank_match_won
    assert result.rank_match_lost == user_full_1.rank_match_lost
    assert result.rank_match_abandoned == user_full_1.rank_match_abandoned
    assert result.rank_kills_count == user_full_1.rank_kills_count
    assert result.rank_deaths_count == user_full_1.rank_deaths_count
    assert result.rank_kd_ratio == user_full_1.rank_kd_ratio
    assert result.rank_kill_per_match == user_full_1.rank_kill_per_match
    assert result.rank_win_percentage == user_full_1.rank_win_percentage
    assert result.arcade_match_played == user_full_1.arcade_match_played
    assert result.arcade_match_won == user_full_1.arcade_match_won
    assert result.arcade_match_lost == user_full_1.arcade_match_lost
    assert result.arcade_match_abandoned == user_full_1.arcade_match_abandoned
    assert result.arcade_kills_count == user_full_1.arcade_kills_count
    assert result.arcade_deaths_count == user_full_1.arcade_deaths_count
    assert result.arcade_kd_ratio == user_full_1.arcade_kd_ratio
    assert result.arcade_kill_per_match == user_full_1.arcade_kill_per_match
    assert result.arcade_win_percentage == user_full_1.arcade_win_percentage
    assert result.quickmatch_match_played == user_full_1.quickmatch_match_played
    assert result.quickmatch_match_won == user_full_1.quickmatch_match_won
    assert result.quickmatch_match_lost == user_full_1.quickmatch_match_lost
    assert result.quickmatch_match_abandoned == user_full_1.quickmatch_match_abandoned
    assert result.quickmatch_kills_count == user_full_1.quickmatch_kills_count
    assert result.quickmatch_deaths_count == user_full_1.quickmatch_deaths_count
    assert result.quickmatch_kd_ratio == user_full_1.quickmatch_kd_ratio
    assert result.quickmatch_kill_per_match == user_full_1.quickmatch_kill_per_match
    assert result.quickmatch_win_percentage == user_full_1.quickmatch_win_percentage


@patch.object(analytic_data_access, analytic_data_access.print_log.__name__)
def test_insert_if_nonexistant_full_match_info(mock_log):
    """
    Test the insertion of statistic into the database
    """
    data_1, data_3, data_4, data_5, data_6 = get_test_data()
    mock_log.side_effect = None
    user_info = UserInfo(1, "DiscordName1", "ubi_1_max", "ubi_1_active", None, "US/Eastern")
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        None,
        user_info.time_zone,
    )
    matches_1 = parse_json_from_full_matches(data_1, user_info)
    matches_3 = parse_json_from_full_matches(data_3, user_info)
    matches_4 = parse_json_from_full_matches(data_4, user_info)
    matches_5 = parse_json_from_full_matches(data_5, user_info)
    matches_6 = parse_json_from_full_matches(data_6, user_info)

    insert_if_nonexistant_full_match_info(user_info, matches_1)
    insert_if_nonexistant_full_match_info(user_info, matches_3)
    insert_if_nonexistant_full_match_info(user_info, matches_4)
    insert_if_nonexistant_full_match_info(user_info, matches_5)
    insert_if_nonexistant_full_match_info(user_info, matches_6)


def test_insert_if_nonexistant_no_match():
    """
    Test if there isn't any match to insert
    """

    user_info = UserInfo(1, "DiscordName1", "ubi_1_max", "ubi_1_active", None, "US/Eastern")
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        None,
        user_info.time_zone,
    )

    insert_if_nonexistant_full_match_info(user_info, [])


@patch.object(analytic_data_access, analytic_data_access.print_log.__name__)
def test_insert_if_nonexistant_with_duplicate(mock_log):
    """
    Test if there isn't any match to insert
    """
    # Get only one data
    data_1 = get_test_data()[0]
    data_1["data"]["matches"] = data_1["data"]["matches"][:1]
    mock_log.side_effect = None

    user_info = UserInfo(1, "DiscordName1", "ubi_1_max", "ubi_1_active", None, "US/Eastern")
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        None,
        user_info.time_zone,
    )

    matches_1 = parse_json_from_full_matches(data_1, user_info)
    insert_if_nonexistant_full_match_info(user_info, matches_1)
    # Reset all the calls
    mock_log.reset_mock()
    insert_if_nonexistant_full_match_info(user_info, matches_1)
    mock_log.assert_called_once_with(
        "insert_if_nonexistant_full_match_info: Found 0 new matches to insert out of 1 for DiscordName1"
    )


@patch.object(analytic_data_access, analytic_data_access.print_log.__name__)
def test_insert_if_nonexistant_with_no_duplicate(mock_log):
    """
    Test if there isn't any match to insert
    """
    # Get only one data
    data_1 = get_test_data()[0]
    all_matches = data_1["data"]["matches"]
    data_1["data"]["matches"] = all_matches[:1]
    mock_log.side_effect = None

    user_info = UserInfo(1, "DiscordName1", "ubi_1_max", "ubi_1_active", None, "US/Eastern")
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        None,
        user_info.time_zone,
    )
    mock_log.reset_mock()
    matches_1 = parse_json_from_full_matches(data_1, user_info)
    insert_if_nonexistant_full_match_info(user_info, matches_1)
    # Reset all the calls
    mock_log.reset_mock()
    data_1["data"]["matches"] = all_matches[1:2]
    matches_1 = parse_json_from_full_matches(data_1, user_info)
    insert_if_nonexistant_full_match_info(user_info, matches_1)

    mock_log.assert_has_calls(
        [
            call("insert_if_nonexistant_full_match_info: Found 1 new matches to insert out of 1 for DiscordName1"),
            call(
                "insert_if_nonexistant_full_match_info: Inserted match 1 for DiscordName1. Match id 9681f59e-80db-4b2e-b54b-3631af76b074 and user id 1"
            ),
        ]
    )


@patch.object(analytic_data_access, analytic_data_access.print_log.__name__)
def test_insert_if_nonexistant_with_no_match(mock_log):
    """
    Test if there isn't any match to insert
    """
    # Get only one data
    data_1 = get_test_data()[0]
    data_1["data"]["matches"] = []
    mock_log.side_effect = None

    user_info = UserInfo(1, "DiscordName1", "ubi_1_max", "ubi_1_active", None, "US/Eastern")
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        None,
        user_info.time_zone,
    )

    matches_1 = parse_json_from_full_matches(data_1, user_info)
    insert_if_nonexistant_full_match_info(user_info, matches_1)
    mock_log.assert_called_once_with(
        "insert_if_nonexistant_full_match_info: No user-match pair to insert, leaving the function early"
    )


def test_two_users_same_channels():
    """Insert two users in the same channel and calculate the weight"""
    insert_user_activity(
        10,
        "user_10",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 13, 20, 0, 6318),
    )
    insert_user_activity(
        11,
        "user_11",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 13, 20, 0, 6318),
    )
    insert_user_activity(
        10,
        "user_10",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_DISCONNECT,
        datetime(2024, 9, 20, 13, 50, 0, 6318),
    )
    insert_user_activity(
        11,
        "user_11",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_DISCONNECT,
        datetime(2024, 9, 20, 13, 50, 0, 6318),
    )
    activity_data = fetch_all_user_activities()
    user_weights = compute_users_weights(activity_data)
    assert user_weights == {(10, 11, 100): 1800.0}


def test_many_users_same_channel():
    """Insert four users in the same channel and calculate the weight"""
    insert_user_activity(
        2,
        "user_2",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 13, 20, 0, 6318),
    )
    insert_user_activity(
        3,
        "user_3",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 13, 21, 0, 6318),
    )
    insert_user_activity(
        2,
        "user_2",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_DISCONNECT,
        datetime(2024, 9, 20, 13, 30, 0, 6318),
    )
    insert_user_activity(
        4,
        "user_4",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 13, 31, 0, 6318),
    )
    insert_user_activity(
        3,
        "user_3",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_DISCONNECT,
        datetime(2024, 9, 20, 13, 32, 0, 6318),
    )
    insert_user_activity(
        4,
        "user_4",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_DISCONNECT,
        datetime(2024, 9, 20, 13, 33, 0, 6318),
    )
    insert_user_activity(
        1,
        "user_1",
        CHANNEL1_ID,
        GUILD_ID,
        EVENT_DISCONNECT,
        datetime(2024, 9, 20, 13, 38, 0, 6318),
    )
    activity_data = fetch_all_user_activities()
    user_weights = compute_users_weights(activity_data)
    assert user_weights == {(2, 3, 100): 540.0, (3, 4, 100): 60.0}


def test_analytic_insert_and_fetch_full_match_info_for_user() -> None:
    """
    Create a stats and fetch it
    """
    user_info: UserInfo = UserInfo(1, "user1", "user1#1234", "user1", None, "US/Pacific")
    list_matches: list[UserFullMatchStats] = [
        UserFullMatchStats(
            id=None,
            user_id=1,
            match_uuid="match-uuid-1",
            match_timestamp=fake_date,
            match_duration_ms=60000,
            data_center="US East",
            session_type="ranked",
            map_name="villa",
            is_surrender=False,
            is_forfeit=False,
            is_rollback=False,
            r6_tracker_user_uuid="111-222-333-444",
            ubisoft_username="noSleep_rb6",
            operators="ace,bandit",
            round_played_count=3,
            round_won_count=3,
            round_lost_count=0,
            round_disconnected_count=0,
            kill_count=5,
            death_count=1,
            assist_count=2,
            head_shot_count=2,
            tk_count=0,
            ace_count=0,
            first_kill_count=1,
            first_death_count=1,
            clutches_win_count=0,
            clutches_loss_count=0,
            clutches_win_count_1v1=0,
            clutches_win_count_1v2=0,
            clutches_win_count_1v3=0,
            clutches_win_count_1v4=0,
            clutches_win_count_1v5=0,
            clutches_lost_count_1v1=0,
            clutches_lost_count_1v2=0,
            clutches_lost_count_1v3=0,
            clutches_lost_count_1v4=0,
            clutches_lost_count_1v5=0,
            kill_1_count=1,
            kill_2_count=1,
            kill_3_count=1,
            kill_4_count=1,
            kill_5_count=1,
            rank_points=4567,
            rank_name="Diamond 3",
            points_gained=23,
            rank_previous=4544,
            kd_ratio=0.7,
            head_shot_percentage=0.34,
            kills_per_round=1,
            deaths_per_round=2,
            assists_per_round=1,
            has_win=True,
        )
    ]
    insert_if_nonexistant_full_match_info(user_info, list_matches)
    result = data_access_fetch_user_full_match_info(user_info.id)
    assert result is not None
    assert len(result) == 1


def test_fetch_tk() -> None:
    """Test that we can fetch the tk"""
    # Arrange
    user_info: UserInfo = UserInfo(1, "user1", "user1#1234", "user1", None, "US/Pacific")
    list_matches: list[UserFullMatchStats] = [
        UserFullMatchStats(
            id=None,
            user_id=user_info.id,
            match_uuid="match-uuid-1",
            match_timestamp=fake_date,
            match_duration_ms=60000,
            data_center="US East",
            session_type="ranked",
            map_name="villa",
            is_surrender=False,
            is_forfeit=False,
            is_rollback=False,
            r6_tracker_user_uuid="111-222-333-444",
            ubisoft_username="noSleep_rb6",
            operators="ace,bandit",
            round_played_count=3,
            round_won_count=3,
            round_lost_count=0,
            round_disconnected_count=0,
            kill_count=5,
            death_count=1,
            assist_count=2,
            head_shot_count=2,
            tk_count=1,
            ace_count=0,
            first_kill_count=1,
            first_death_count=1,
            clutches_win_count=0,
            clutches_loss_count=0,
            clutches_win_count_1v1=0,
            clutches_win_count_1v2=0,
            clutches_win_count_1v3=0,
            clutches_win_count_1v4=0,
            clutches_win_count_1v5=0,
            clutches_lost_count_1v1=0,
            clutches_lost_count_1v2=0,
            clutches_lost_count_1v3=0,
            clutches_lost_count_1v4=0,
            clutches_lost_count_1v5=0,
            kill_1_count=1,
            kill_2_count=1,
            kill_3_count=1,
            kill_4_count=1,
            kill_5_count=1,
            rank_points=4567,
            rank_name="Diamond 3",
            points_gained=23,
            rank_previous=4544,
            kd_ratio=0.7,
            head_shot_percentage=0.34,
            kills_per_round=1,
            deaths_per_round=2,
            assists_per_round=1,
            has_win=True,
        )
    ]
    insert_if_nonexistant_full_match_info(user_info, list_matches)
    insert_user_activity(
        user_info.id, user_info.display_name, 1, 1, EVENT_CONNECT, fake_date
    )  # Need to have activity to be part of the fetching operation
    # Act
    result = data_access_fetch_tk_count_by_user(fake_date)
    # Assert
    assert result is not None
    assert len(result) == 1
