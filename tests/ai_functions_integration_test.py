"""Integration tests for AI summary generation"""

import pytest
from datetime import datetime, timezone, timedelta
from deps.ai.ai_functions import BotAI
from deps.analytic_data_access import (
    insert_if_nonexistant_full_match_info,
    insert_user_activity,
    upsert_user_info,
)
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, EVENT_CONNECT, EVENT_DISCONNECT, database_manager


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


def create_test_match(
    match_uuid: str,
    user_id: int,
    match_timestamp: datetime,
    r6_tracker_user_uuid: str,
    ubisoft_username: str
) -> UserFullMatchStats:
    """Helper function to create a test match"""
    return UserFullMatchStats(
        id=None,
        match_uuid=match_uuid,
        user_id=user_id,
        match_timestamp=match_timestamp,
        match_duration_ms=1800000,
        data_center="eus",
        session_type="ranked",
        map_name="Bank",
        is_surrender=False,
        is_forfeit=False,
        is_rollback=False,
        r6_tracker_user_uuid=r6_tracker_user_uuid,
        ubisoft_username=ubisoft_username,
        operators="Ash,Jager",
        round_played_count=9,
        round_won_count=5,
        round_lost_count=4,
        round_disconnected_count=0,
        kill_count=10,
        death_count=8,
        assist_count=3,
        head_shot_count=5,
        tk_count=0,
        ace_count=1,
        first_kill_count=2,
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
        kill_1_count=3,
        kill_2_count=2,
        kill_3_count=1,
        kill_4_count=1,
        kill_5_count=1,
        rank_points=3500,
        rank_name="Gold I",
        points_gained=50,
        rank_previous=3450,
        kd_ratio=1.25,
        head_shot_percentage=0.50,
        kills_per_round=1.11,
        deaths_per_round=0.89,
        assists_per_round=0.33,
        has_win=True
    )


@pytest.mark.no_parallel
def test_gather_information_includes_all_users_with_matches():
    """Test that all users with matches in time range are included"""
    # Create 3 test users
    user1_id = 100001
    user2_id = 100002
    user3_id = 100003
    guild_id = 999999
    channel_id = 888888

    # Setup users in database
    for uid, name in [(user1_id, "Player1"), (user2_id, "Player2"), (user3_id, "Player3")]:
        upsert_user_info(uid, name, f"ubi_{uid}", f"ubi_{uid}", f"uuid-{uid}", "US/Eastern", 3000)

    # Current time and time range
    now = datetime.now(timezone.utc)
    time_6_hours_ago = now - timedelta(hours=6)
    time_3_hours_ago = now - timedelta(hours=3)

    # Insert voice activity for all 3 users in the time range
    for uid in [user1_id, user2_id, user3_id]:
        insert_user_activity(uid, f"Player{uid-100000}", channel_id, guild_id, EVENT_CONNECT, time_6_hours_ago)
        insert_user_activity(uid, f"Player{uid-100000}", channel_id, guild_id, EVENT_DISCONNECT, time_3_hours_ago)

    # Insert matches for only 2 users in time range
    user1_info = UserInfo(user1_id, "Player1", "ubi_100001", "ubi_100001", "uuid-100001", "US/Eastern", 3000)
    user2_info = UserInfo(user2_id, "Player2", "ubi_100002", "ubi_100002", "uuid-100002", "US/Eastern", 3000)

    # User 1: 2 matches
    insert_if_nonexistant_full_match_info(user1_info, [
        create_test_match("u1m1", user1_id, time_6_hours_ago + timedelta(hours=1), "uuid-100001", "ubi_100001"),
        create_test_match("u1m2", user1_id, time_6_hours_ago + timedelta(hours=2), "uuid-100001", "ubi_100001"),
    ])

    # User 2: 3 matches
    insert_if_nonexistant_full_match_info(user2_info, [
        create_test_match("u2m1", user2_id, time_6_hours_ago + timedelta(hours=1), "uuid-100002", "ubi_100002"),
        create_test_match("u2m2", user2_id, time_6_hours_ago + timedelta(hours=2), "uuid-100002", "ubi_100002"),
        create_test_match("u2m3", user2_id, time_6_hours_ago + timedelta(hours=3), "uuid-100002", "ubi_100002"),
    ])

    # User 3: No matches in time range (has activity but no matches)

    # Execute the function
    bot_ai = BotAI()
    users, matches = bot_ai.gather_information_for_generating_message_summary(hours=6)

    # Verify: Only 2 users returned (not 3, since user3 has no matches)
    assert len(users) == 2, f"Expected 2 users with matches, got {len(users)}"

    # Verify user IDs
    user_ids = {user.id for user in users}
    assert user1_id in user_ids, "User1 should be included (has matches)"
    assert user2_id in user_ids, "User2 should be included (has matches)"
    assert user3_id not in user_ids, "User3 should not be included (no matches)"

    # Verify match counts
    assert len(matches) == 5, f"Expected 5 total matches (2+3), got {len(matches)}"


@pytest.mark.no_parallel
def test_gather_information_with_no_active_users():
    """Test when no users are active in the time range"""
    bot_ai = BotAI()
    users, matches = bot_ai.gather_information_for_generating_message_summary(hours=6)

    assert len(users) == 0
    assert len(matches) == 0


@pytest.mark.no_parallel
def test_gather_information_with_active_users_but_no_matches():
    """Test when users are active but have no matches"""
    user_id = 200001
    guild_id = 999999
    channel_id = 888888

    # Setup user
    upsert_user_info(user_id, "NoMatchPlayer", "ubi_200001", "ubi_200001", "uuid-200001", "US/Eastern", 3000)

    # Insert voice activity
    now = datetime.now(timezone.utc)
    time_6_hours_ago = now - timedelta(hours=6)
    insert_user_activity(user_id, "NoMatchPlayer", channel_id, guild_id, EVENT_CONNECT, time_6_hours_ago)

    # No matches inserted

    bot_ai = BotAI()
    users, matches = bot_ai.gather_information_for_generating_message_summary(hours=6)

    # User should not be included because they have no matches
    assert len(users) == 0
    assert len(matches) == 0


@pytest.mark.no_parallel
def test_gather_information_pagination_bug_fixed():
    """
    Test that the pagination bug is fixed - users with >50 matches in time range
    should have all their matches included, not just the first 50
    """
    user_id = 300001
    guild_id = 999999
    channel_id = 888888

    # Setup user
    upsert_user_info(user_id, "HeavyPlayer", "ubi_300001", "ubi_300001", "uuid-300001", "US/Eastern", 4000)

    # Use fixed timestamps
    base_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
    time_24_hours_ago = base_time - timedelta(hours=24)

    # Insert voice activity
    insert_user_activity(user_id, "HeavyPlayer", channel_id, guild_id, EVENT_CONNECT, time_24_hours_ago)

    # Insert 60 matches in the last 24 hours (simulating a very active player)
    user_info = UserInfo(user_id, "HeavyPlayer", "ubi_300001", "ubi_300001", "uuid-300001", "US/Eastern", 4000)
    matches_to_insert = []
    for i in range(60):
        match_time = time_24_hours_ago + timedelta(minutes=i * 20)  # One match every 20 minutes
        matches_to_insert.append(
            create_test_match(f"match_{i}", user_id, match_time, "uuid-300001", "ubi_300001")
        )
    insert_if_nonexistant_full_match_info(user_info, matches_to_insert)

    # Query for the specific time range
    from deps.analytic_data_access import get_active_user_info
    users_active = get_active_user_info(time_24_hours_ago, base_time)

    # Manually call the data access function to test it directly
    from deps.analytic_match_data_access import data_access_fetch_user_matches_in_time_range
    matches_by_user = data_access_fetch_user_matches_in_time_range(
        [user_id], time_24_hours_ago, base_time
    )

    # Verify all 60 matches are included (not limited to 50)
    assert user_id in matches_by_user
    assert len(matches_by_user[user_id]) == 60, f"Expected all 60 matches, got {len(matches_by_user[user_id])} (pagination bug if 50)"


@pytest.mark.no_parallel
def test_gather_information_filters_by_time_correctly():
    """Test that matches outside the time range are not included"""
    user_id = 400001
    guild_id = 999999
    channel_id = 888888

    # Setup user
    upsert_user_info(user_id, "TimeTestPlayer", "ubi_400001", "ubi_400001", "uuid-400001", "US/Eastern", 3200)

    # Use fixed timestamps
    base_time = datetime(2026, 1, 20, 18, 0, 0, tzinfo=timezone.utc)
    time_6_hours_ago = base_time - timedelta(hours=6)
    time_12_hours_ago = base_time - timedelta(hours=12)

    # Insert voice activity in the 6-hour window
    insert_user_activity(user_id, "TimeTestPlayer", channel_id, guild_id, EVENT_CONNECT, time_6_hours_ago)

    user_info = UserInfo(user_id, "TimeTestPlayer", "ubi_400001", "ubi_400001", "uuid-400001", "US/Eastern", 3200)

    # Insert matches: 2 within 6 hours, 2 older than 6 hours
    insert_if_nonexistant_full_match_info(user_info, [
        # Within range
        create_test_match("recent1", user_id, time_6_hours_ago + timedelta(hours=1), "uuid-400001", "ubi_400001"),
        create_test_match("recent2", user_id, time_6_hours_ago + timedelta(hours=3), "uuid-400001", "ubi_400001"),
        # Outside range (too old)
        create_test_match("old1", user_id, time_12_hours_ago, "uuid-400001", "ubi_400001"),
        create_test_match("old2", user_id, time_12_hours_ago + timedelta(hours=1), "uuid-400001", "ubi_400001"),
    ])

    # Manually call the data access function to test it directly
    from deps.analytic_match_data_access import data_access_fetch_user_matches_in_time_range
    matches_by_user = data_access_fetch_user_matches_in_time_range(
        [user_id], time_6_hours_ago, base_time
    )

    # Should only include the 2 recent matches
    assert user_id in matches_by_user
    assert len(matches_by_user[user_id]) == 2, f"Expected 2 matches within 6-hour window, got {len(matches_by_user[user_id])}"
