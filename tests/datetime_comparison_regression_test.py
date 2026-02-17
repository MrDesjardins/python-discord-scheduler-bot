"""
Regression tests for datetime comparison bugs.

These tests ensure that the SQLite datetime comparison bug (comparing TEXT timestamps
with timezone info against Python datetime objects) doesn't reoccur.
"""

import pytest
from datetime import datetime, timezone, timedelta
from deps.analytic_match_data_access import data_access_fetch_user_matches_in_time_range
from deps.analytic_settings_data_access import upsert_user_info
from deps.models import UserFullMatchStats
from deps.data_access_data_class import UserInfo
from deps.system_database import DATABASE_NAME_TEST, database_manager


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup test database before each test"""
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()
    yield
    database_manager.close()


def create_test_match(user_id: int, match_timestamp: datetime, match_uuid: str) -> UserFullMatchStats:
    """Helper to create a test match"""
    return UserFullMatchStats(
        id=None,
        match_uuid=match_uuid,
        user_id=user_id,
        match_timestamp=match_timestamp,
        match_duration_ms=600000,
        data_center="US East",
        session_type="ranked",
        map_name="Clubhouse",
        is_surrender=False,
        is_forfeit=False,
        is_rollback=False,
        r6_tracker_user_uuid="test-uuid",
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


def test_datetime_comparison_with_recent_match():
    """
    Test that matches within the time window are correctly returned.

    This is a regression test for the SQLite datetime comparison bug where
    TEXT timestamps with 'T' separator were incorrectly compared to datetime
    strings with space separator.
    """
    # Setup user
    user_id = 12345
    user_info = UserInfo(user_id, "TestUser", "test_max", "test_active", None, "US/Eastern", 0)
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        user_info.r6_tracker_active_id,
        user_info.time_zone,
        user_info.max_mmr,
    )

    # Create a match 6 hours ago (should be included in 24-hour window)
    now = datetime.now(timezone.utc)
    match_time = now - timedelta(hours=6)
    match = create_test_match(user_id, match_time, "match-6h-ago")

    # Insert match
    from deps.analytic_match_data_access import insert_if_nonexistant_full_match_info

    insert_if_nonexistant_full_match_info(user_info, [match])

    # Query with 24-hour window
    from_time = now - timedelta(hours=24)
    to_time = now

    matches = data_access_fetch_user_matches_in_time_range([user_id], from_time, to_time)

    # Should find the match
    assert user_id in matches, "User should be in results"
    assert len(matches[user_id]) == 1, "Should find exactly 1 match"
    assert matches[user_id][0].match_uuid == "match-6h-ago"


def test_datetime_comparison_excludes_old_matches():
    """
    Test that matches outside the time window are correctly excluded.

    Regression test ensuring old matches don't get incorrectly included
    due to string comparison ('T' > ' ') bug.
    """
    # Setup user
    user_id = 12346
    user_info = UserInfo(user_id, "TestUser2", "test_max2", "test_active2", None, "US/Eastern", 0)
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        user_info.r6_tracker_active_id,
        user_info.time_zone,
        user_info.max_mmr,
    )

    # Create a match 30 hours ago (should be excluded from 24-hour window)
    now = datetime.now(timezone.utc)
    match_time = now - timedelta(hours=30)
    match = create_test_match(user_id, match_time, "match-30h-ago")

    # Insert match
    from deps.analytic_match_data_access import insert_if_nonexistant_full_match_info

    insert_if_nonexistant_full_match_info(user_info, [match])

    # Query with 24-hour window
    from_time = now - timedelta(hours=24)
    to_time = now

    matches = data_access_fetch_user_matches_in_time_range([user_id], from_time, to_time)

    # Should NOT find the match
    assert user_id not in matches or len(matches[user_id]) == 0, "Should not find matches older than 24 hours"


def test_datetime_comparison_boundary_cases():
    """
    Test exact boundary conditions for datetime comparison.

    Ensures matches exactly at the boundary are handled correctly.
    """
    # Setup user
    user_id = 12347
    user_info = UserInfo(user_id, "TestUser3", "test_max3", "test_active3", None, "US/Eastern", 0)
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        user_info.r6_tracker_active_id,
        user_info.time_zone,
        user_info.max_mmr,
    )

    # Create matches at exact boundary points
    now = datetime.now(timezone.utc)

    # Match exactly 24 hours ago
    match_24h = create_test_match(user_id, now - timedelta(hours=24), "match-exactly-24h")
    # Match 1 second after 24 hours ago (should be included)
    match_23h59m59s = create_test_match(user_id, now - timedelta(hours=24, seconds=-1), "match-23h59m59s")
    # Match 1 second before 24 hours ago (should be excluded)
    match_24h1s = create_test_match(user_id, now - timedelta(hours=24, seconds=1), "match-24h1s")

    # Insert matches
    from deps.analytic_match_data_access import insert_if_nonexistant_full_match_info

    insert_if_nonexistant_full_match_info(user_info, [match_24h, match_23h59m59s, match_24h1s])

    # Query with 24-hour window
    from_time = now - timedelta(hours=24)
    to_time = now

    matches = data_access_fetch_user_matches_in_time_range([user_id], from_time, to_time)

    # Should find exactly the matches >= from_time
    assert user_id in matches, "User should be in results"
    found_uuids = {m.match_uuid for m in matches[user_id]}

    # Match exactly at boundary should be included (>= comparison)
    assert "match-exactly-24h" in found_uuids, "Match exactly at 24h boundary should be included"
    assert "match-23h59m59s" in found_uuids, "Match just inside window should be included"
    assert "match-24h1s" not in found_uuids, "Match just outside window should be excluded"


def test_datetime_comparison_with_microseconds():
    """
    Test that datetime comparison works correctly with microsecond precision.

    The bug involved ISO format strings with microseconds (e.g., "2026-02-15T09:18:01.437000+00:00")
    being compared incorrectly.
    """
    # Setup user
    user_id = 12348
    user_info = UserInfo(user_id, "TestUser4", "test_max4", "test_active4", None, "US/Eastern", 0)
    upsert_user_info(
        user_info.id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        user_info.r6_tracker_active_id,
        user_info.time_zone,
        user_info.max_mmr,
    )

    # Create matches with microsecond precision
    now = datetime.now(timezone.utc)
    # Use a specific microsecond value
    match_time = datetime(2026, 2, 15, 12, 30, 45, 437000, tzinfo=timezone.utc)
    match = create_test_match(user_id, match_time, "match-with-microseconds")

    # Insert match
    from deps.analytic_match_data_access import insert_if_nonexistant_full_match_info

    insert_if_nonexistant_full_match_info(user_info, [match])

    # Query with a wide window to include this match
    from_time = datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
    to_time = datetime(2026, 2, 16, 0, 0, 0, tzinfo=timezone.utc)

    matches = data_access_fetch_user_matches_in_time_range([user_id], from_time, to_time)

    # Should find the match
    assert user_id in matches, "User should be in results"
    assert len(matches[user_id]) == 1, "Should find the match with microseconds"

    # Verify the timestamp was preserved with microsecond precision
    retrieved_timestamp = matches[user_id][0].match_timestamp
    assert retrieved_timestamp.microsecond > 0, "Microseconds should be preserved (non-zero)"
    # Note: exact microsecond value may vary due to storage/retrieval, but should be present


def test_multiple_users_datetime_filtering():
    """
    Test that datetime filtering works correctly for multiple users simultaneously.

    This ensures the fix works when querying multiple users at once, as done
    by the AI summary generation.
    """
    # Setup multiple users
    user1_id = 12349
    user2_id = 12350
    user3_id = 12351

    user1 = UserInfo(user1_id, "User1", "max1", "active1", None, "US/Eastern", 0)
    user2 = UserInfo(user2_id, "User2", "max2", "active2", None, "US/Eastern", 0)
    user3 = UserInfo(user3_id, "User3", "max3", "active3", None, "US/Eastern", 0)

    for user in [user1, user2, user3]:
        upsert_user_info(
            user.id,
            user.display_name,
            user.ubisoft_username_max,
            user.ubisoft_username_active,
            user.r6_tracker_active_id,
            user.time_zone,
            user.max_mmr,
        )

    # Create matches at different times
    now = datetime.now(timezone.utc)

    # User1: match 6 hours ago (should be included)
    match1 = create_test_match(user1_id, now - timedelta(hours=6), "user1-recent")

    # User2: match 30 hours ago (should be excluded)
    match2 = create_test_match(user2_id, now - timedelta(hours=30), "user2-old")

    # User3: two matches, one recent (12h) and one old (36h)
    match3a = create_test_match(user3_id, now - timedelta(hours=12), "user3-recent")
    match3b = create_test_match(user3_id, now - timedelta(hours=36), "user3-old")

    # Insert matches
    from deps.analytic_match_data_access import insert_if_nonexistant_full_match_info

    insert_if_nonexistant_full_match_info(user1, [match1])
    insert_if_nonexistant_full_match_info(user2, [match2])
    insert_if_nonexistant_full_match_info(user3, [match3a, match3b])

    # Query all users with 24-hour window
    from_time = now - timedelta(hours=24)
    to_time = now

    matches = data_access_fetch_user_matches_in_time_range([user1_id, user2_id, user3_id], from_time, to_time)

    # User1 should have 1 match
    assert user1_id in matches, "User1 should have matches"
    assert len(matches[user1_id]) == 1
    assert matches[user1_id][0].match_uuid == "user1-recent"

    # User2 should have NO matches (old match excluded)
    assert user2_id not in matches or len(matches[user2_id]) == 0, "User2 old match should be excluded"

    # User3 should have only the recent match
    assert user3_id in matches, "User3 should have matches"
    assert len(matches[user3_id]) == 1, "User3 should have only 1 recent match"
    assert matches[user3_id][0].match_uuid == "user3-recent"
