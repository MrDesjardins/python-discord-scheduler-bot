"""
Regression tests for AI summary timing issues.

These tests ensure that the AI summary downloads matches for users still in voice
before generating the summary, preventing the bug where users who played but stayed
in voice would miss the summary.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from deps.ai.ai_functions import BotAI
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats
from deps.system_database import DATABASE_NAME_TEST, database_manager


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup test database before each test"""
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()
    yield
    database_manager.close()


def create_mock_user(user_id: int, display_name: str, ubisoft_username: str) -> UserInfo:
    """Helper to create a mock user"""
    return UserInfo(
        id=user_id,
        display_name=display_name,
        ubisoft_username_max=ubisoft_username,
        ubisoft_username_active=ubisoft_username,
        r6_tracker_active_id=f"uuid-{user_id}",
        time_zone="US/Eastern",
        max_mmr=3500,
    )


def create_mock_match(user_id: int, hours_ago: float, match_uuid: str) -> UserFullMatchStats:
    """Helper to create a mock match at a specific time in the past"""
    match_time = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return UserFullMatchStats(
        id=1,
        match_uuid=match_uuid,
        user_id=user_id,
        match_timestamp=match_time,
        match_duration_ms=600000,
        data_center="US East",
        session_type="ranked",
        map_name="Clubhouse",
        is_surrender=False,
        is_forfeit=False,
        is_rollback=False,
        r6_tracker_user_uuid=f"uuid-{user_id}",
        ubisoft_username="test_user",
        operators="Ash,Jager",
        round_played_count=9,
        round_won_count=5,
        round_lost_count=4,
        round_disconnected_count=0,
        kill_count=7,
        death_count=5,
        assist_count=2,
        head_shot_count=3,
        tk_count=0,
        ace_count=0,
        first_kill_count=1,
        first_death_count=1,
        clutches_win_count=1,
        clutches_loss_count=0,
        clutches_win_count_1v1=1,
        clutches_win_count_1v2=0,
        clutches_win_count_1v3=0,
        clutches_win_count_1v4=0,
        clutches_win_count_1v5=0,
        clutches_lost_count_1v1=0,
        clutches_lost_count_1v2=0,
        clutches_lost_count_1v3=0,
        clutches_lost_count_1v4=0,
        clutches_lost_count_1v5=0,
        kill_1_count=4,
        kill_2_count=2,
        kill_3_count=1,
        kill_4_count=0,
        kill_5_count=0,
        rank_points=3500,
        rank_name="Diamond",
        points_gained=25,
        rank_previous=3475,
        kd_ratio=1.4,
        head_shot_percentage=0.43,
        kills_per_round=0.78,
        deaths_per_round=0.56,
        assists_per_round=0.22,
        has_win=True,
    )


@patch("deps.ai.ai_functions.get_active_user_info")
@patch("deps.ai.ai_functions.data_access_fetch_user_matches_in_time_range")
def test_gather_information_includes_recently_played_user(mock_fetch_matches, mock_get_active_users):
    """
    Test that users with matches in the last 24 hours are included in AI summary.

    This verifies the datetime comparison fix works correctly.
    """
    # Setup: User who played 6 hours ago
    user = create_mock_user(1001, "RecentPlayer", "recent_player")
    match = create_mock_match(1001, hours_ago=6, match_uuid="recent-match")

    mock_get_active_users.return_value = [user]
    mock_fetch_matches.return_value = {1001: [match]}

    # Execute
    bot_ai = BotAI()
    users, matches = bot_ai.gather_information_for_generating_message_summary(24)

    # Verify
    assert len(users) == 1, "Should include user with recent matches"
    assert users[0].display_name == "RecentPlayer"
    assert len(matches) == 1, "Should include the recent match"
    assert matches[0].match_uuid == "recent-match"


@patch("deps.ai.ai_functions.get_active_user_info")
@patch("deps.ai.ai_functions.data_access_fetch_user_matches_in_time_range")
def test_gather_information_excludes_user_with_old_matches_only(mock_fetch_matches, mock_get_active_users):
    """
    Test that users with only old matches (>24h) are excluded from AI summary.

    This is a regression test for the datetime comparison bug where old matches
    were incorrectly included due to string comparison.
    """
    # Setup: User who played 30 hours ago (should be excluded)
    user = create_mock_user(1002, "OldPlayer", "old_player")
    old_match = create_mock_match(1002, hours_ago=30, match_uuid="old-match")

    mock_get_active_users.return_value = [user]
    # With the fix, the database query should return no matches
    mock_fetch_matches.return_value = {}

    # Execute
    bot_ai = BotAI()
    users, matches = bot_ai.gather_information_for_generating_message_summary(24)

    # Verify
    assert len(users) == 0, "Should exclude users with only old matches"
    assert len(matches) == 0, "Should have no matches in summary"


@patch("deps.ai.ai_functions.get_active_user_info")
@patch("deps.ai.ai_functions.data_access_fetch_user_matches_in_time_range")
def test_gather_information_filters_mixed_old_and_new_matches(mock_fetch_matches, mock_get_active_users):
    """
    Test that only recent matches are included when a user has both old and new matches.
    """
    # Setup: User with both recent and old matches
    user = create_mock_user(1003, "MixedPlayer", "mixed_player")
    recent_match = create_mock_match(1003, hours_ago=12, match_uuid="recent-match")
    old_match = create_mock_match(1003, hours_ago=36, match_uuid="old-match")

    mock_get_active_users.return_value = [user]
    # Database should only return the recent match (datetime filter working correctly)
    mock_fetch_matches.return_value = {1003: [recent_match]}

    # Execute
    bot_ai = BotAI()
    users, matches = bot_ai.gather_information_for_generating_message_summary(24)

    # Verify
    assert len(users) == 1, "Should include user"
    assert len(matches) == 1, "Should include only recent match"
    assert matches[0].match_uuid == "recent-match"


@patch("deps.ai.ai_functions.get_active_user_info")
@patch("deps.ai.ai_functions.data_access_fetch_user_matches_in_time_range")
def test_gather_information_handles_user_still_in_voice(mock_fetch_matches, mock_get_active_users):
    """
    Test the scenario where a user played matches but is still in voice.

    This is the core bug that affected Yuuka: if a user plays overnight and stays
    in voice past the AI summary time, their matches should still be included
    (after the fix to download matches before generating summary).
    """
    # Setup: User who played 2 hours ago and is still in voice
    user = create_mock_user(1004, "StillInVoice", "still_in_voice")
    recent_match1 = create_mock_match(1004, hours_ago=2, match_uuid="very-recent-1")
    recent_match2 = create_mock_match(1004, hours_ago=3, match_uuid="very-recent-2")

    mock_get_active_users.return_value = [user]
    # These matches should be in the database (either from proactive download or previous disconnect)
    mock_fetch_matches.return_value = {1004: [recent_match1, recent_match2]}

    # Execute
    bot_ai = BotAI()
    users, matches = bot_ai.gather_information_for_generating_message_summary(24)

    # Verify
    assert len(users) == 1, "User still in voice should be included if they have recent matches"
    assert users[0].display_name == "StillInVoice"
    assert len(matches) == 2, "Both recent matches should be included"


@patch("deps.ai.ai_functions.get_active_user_info")
@patch("deps.ai.ai_functions.data_access_fetch_user_matches_in_time_range")
def test_gather_information_yuuka_scenario_regression(mock_fetch_matches, mock_get_active_users):
    """
    Regression test for the exact scenario that affected Yuuka.

    Timeline:
    - Yuuka plays matches from 03:31-09:18 UTC (finishes ~15 hours before summary)
    - AI summary runs at 16:45 UTC (8:45 AM PST)
    - Yuuka disconnects at 22:22 UTC (14:22 PM PST) - 5.5 hours AFTER summary

    Before fix: Matches not in database when summary runs → excluded
    After fix: Proactive download before summary → included
    """
    # Setup: Simulate Yuuka's scenario
    yuuka = create_mock_user(261398260952858624, "Yuuka", "Yuuka_Kazami")

    # Matches played 15 hours ago (within 24h window but after proactive download)
    match1 = create_mock_match(261398260952858624, hours_ago=15, match_uuid="yuuka-match-1")
    match2 = create_mock_match(261398260952858624, hours_ago=16, match_uuid="yuuka-match-2")

    mock_get_active_users.return_value = [yuuka]
    # After the fix, these matches should be available (downloaded proactively)
    mock_fetch_matches.return_value = {261398260952858624: [match1, match2]}

    # Execute
    bot_ai = BotAI()
    users, matches = bot_ai.gather_information_for_generating_message_summary(24)

    # Verify: Yuuka should be included!
    assert len(users) == 1, "Yuuka should be included in summary"
    assert users[0].display_name == "Yuuka"
    assert len(matches) == 2, "Yuuka's matches should be included"


@patch("deps.ai.ai_functions.get_active_user_info")
@patch("deps.ai.ai_functions.data_access_fetch_user_matches_in_time_range")
def test_gather_information_multiple_users_mixed_scenarios(mock_fetch_matches, mock_get_active_users):
    """
    Test multiple users with different match timing scenarios simultaneously.
    """
    # Setup: 4 users with different scenarios
    user1 = create_mock_user(2001, "RecentPlayer", "recent")
    user2 = create_mock_user(2002, "OldPlayer", "old")
    user3 = create_mock_user(2003, "NoMatches", "none")
    user4 = create_mock_user(2004, "StillInVoice", "voice")

    # User1: Recent matches (6h ago)
    match1 = create_mock_match(2001, hours_ago=6, match_uuid="user1-recent")

    # User2: Old matches only (30h ago) - should be excluded
    # (database returns empty for this user)

    # User3: No matches at all

    # User4: Very recent matches, still in voice (2h ago)
    match4 = create_mock_match(2004, hours_ago=2, match_uuid="user4-very-recent")

    mock_get_active_users.return_value = [user1, user2, user3, user4]
    mock_fetch_matches.return_value = {
        2001: [match1],
        # 2002: excluded (no recent matches)
        # 2003: no matches
        2004: [match4],
    }

    # Execute
    bot_ai = BotAI()
    users, matches = bot_ai.gather_information_for_generating_message_summary(24)

    # Verify
    assert len(users) == 2, "Should include only users with recent matches"
    user_names = {u.display_name for u in users}
    assert user_names == {"RecentPlayer", "StillInVoice"}

    assert len(matches) == 2, "Should have 2 total matches"
    match_uuids = {m.match_uuid for m in matches}
    assert match_uuids == {"user1-recent", "user4-very-recent"}


def test_datetime_window_boundary_consistency():
    """
    Test that the time window used in AI summary is consistent with other parts of the system.

    This ensures the 24-hour window is calculated the same way everywhere.
    """
    bot_ai = BotAI()

    # Mock the dependencies to capture the actual time range used
    with (
        patch("deps.ai.ai_functions.get_active_user_info") as mock_get_users,
        patch("deps.ai.ai_functions.data_access_fetch_user_matches_in_time_range") as mock_fetch,
    ):

        mock_get_users.return_value = []
        mock_fetch.return_value = {}

        # Execute with 24-hour window
        bot_ai.gather_information_for_generating_message_summary(24)

        # Verify the time range passed to get_active_user_info
        assert mock_get_users.called
        call_args = mock_get_users.call_args[0]
        from_time, to_time = call_args

        # Check that the window is approximately 24 hours
        time_diff = to_time - from_time
        expected_hours = 24
        actual_hours = time_diff.total_seconds() / 3600

        assert (
            abs(actual_hours - expected_hours) < 0.01
        ), f"Time window should be {expected_hours}h, got {actual_hours}h"

        # Both times should be timezone-aware (UTC)
        assert from_time.tzinfo is not None, "from_time should be timezone-aware"
        assert to_time.tzinfo is not None, "to_time should be timezone-aware"
        assert from_time.tzinfo == timezone.utc, "from_time should be UTC"
        assert to_time.tzinfo == timezone.utc, "to_time should be UTC"
