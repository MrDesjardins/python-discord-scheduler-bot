"""
Unit tests for analytic data access functions
"""

# pylint: disable=line-too-long
# pylint: disable=too-many-arguments

import pytest
from datetime import datetime, timezone, timedelta
from deps.analytic_match_data_access import data_access_fetch_user_matches_in_time_range
from deps.analytic_data_access import (
    data_access_fetch_user_outside_ranked_match_partners,
    data_access_fetch_user_ranked_match_server_split_by_week,
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
    r6_tracker_user_uuid: str = "test-uuid-123",
    ubisoft_username: str = "test_user",
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
        has_win=True,
    )


def create_test_user(user_id: int, display_name: str) -> UserInfo:
    """Helper function to create and persist a test user."""
    user_info = UserInfo(
        id=user_id,
        display_name=display_name,
        ubisoft_username_max=f"{display_name}_max",
        ubisoft_username_active=f"{display_name}_active",
        r6_tracker_active_id=f"tracker-{user_id}",
        time_zone="US/Eastern",
        max_mmr=3500,
    )
    upsert_user_info(
        user_id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        user_info.r6_tracker_active_id,
        user_info.time_zone,
        user_info.max_mmr,
    )
    return user_info


@pytest.mark.no_parallel
def test_fetch_matches_in_time_range_single_user():
    """Test fetching matches for single user in time range"""
    user_id = 123456
    from_date = datetime(2026, 1, 20, tzinfo=timezone.utc)
    to_date = datetime(2026, 1, 22, tzinfo=timezone.utc)

    # Create test user
    user_info = UserInfo(
        id=user_id,
        display_name="TestUser",
        ubisoft_username_max="test_ubi",
        ubisoft_username_active="test_ubi",
        r6_tracker_active_id="test-uuid-123",
        time_zone="US/Eastern",
        max_mmr=3500,
    )
    upsert_user_info(
        user_id,
        user_info.display_name,
        user_info.ubisoft_username_max,
        user_info.ubisoft_username_active,
        user_info.r6_tracker_active_id,
        user_info.time_zone,
        user_info.max_mmr,
    )

    # Insert 5 matches: 2 before range, 2 in range, 1 after range
    matches = [
        create_test_match("match1", user_id, datetime(2026, 1, 19, 10, 0, tzinfo=timezone.utc)),
        create_test_match("match2", user_id, datetime(2026, 1, 19, 20, 0, tzinfo=timezone.utc)),
        create_test_match("match3", user_id, datetime(2026, 1, 20, 15, 0, tzinfo=timezone.utc)),
        create_test_match("match4", user_id, datetime(2026, 1, 21, 18, 0, tzinfo=timezone.utc)),
        create_test_match("match5", user_id, datetime(2026, 1, 23, 12, 0, tzinfo=timezone.utc)),
    ]
    insert_if_nonexistant_full_match_info(user_info, matches)

    # Fetch matches in time range
    result = data_access_fetch_user_matches_in_time_range([user_id], from_date, to_date)

    assert user_id in result
    assert len(result[user_id]) == 2  # Only 2 in range
    for match in result[user_id]:
        assert from_date <= match.match_timestamp <= to_date


@pytest.mark.no_parallel
def test_fetch_matches_multiple_users():
    """Test fetching matches for multiple users"""
    user1_id = 111111
    user2_id = 222222
    user3_id = 333333
    from_date = datetime(2026, 1, 20, tzinfo=timezone.utc)
    to_date = datetime(2026, 1, 22, tzinfo=timezone.utc)

    # Create test users
    for uid, name in [(user1_id, "User1"), (user2_id, "User2"), (user3_id, "User3")]:
        upsert_user_info(uid, name, f"ubi_{uid}", f"ubi_{uid}", f"uuid-{uid}", "US/Eastern", 3000)

    # Insert matches for each user
    user1_info = UserInfo(user1_id, "User1", "ubi_111111", "ubi_111111", "uuid-111111", "US/Eastern", 3000)
    user2_info = UserInfo(user2_id, "User2", "ubi_222222", "ubi_222222", "uuid-222222", "US/Eastern", 3000)
    user3_info = UserInfo(user3_id, "User3", "ubi_333333", "ubi_333333", "uuid-333333", "US/Eastern", 3000)

    # User 1: 3 matches in range
    insert_if_nonexistant_full_match_info(
        user1_info,
        [
            create_test_match(
                "u1m1", user1_id, datetime(2026, 1, 20, 10, 0, tzinfo=timezone.utc), "uuid-111111", "ubi_111111"
            ),
            create_test_match(
                "u1m2", user1_id, datetime(2026, 1, 21, 11, 0, tzinfo=timezone.utc), "uuid-111111", "ubi_111111"
            ),
            create_test_match(
                "u1m3", user1_id, datetime(2026, 1, 21, 20, 0, tzinfo=timezone.utc), "uuid-111111", "ubi_111111"
            ),
        ],
    )

    # User 2: 1 match in range
    insert_if_nonexistant_full_match_info(
        user2_info,
        [
            create_test_match(
                "u2m1", user2_id, datetime(2026, 1, 21, 15, 0, tzinfo=timezone.utc), "uuid-222222", "ubi_222222"
            ),
        ],
    )

    # User 3: 0 matches in range (1 before, 1 after)
    insert_if_nonexistant_full_match_info(
        user3_info,
        [
            create_test_match(
                "u3m1", user3_id, datetime(2026, 1, 19, 10, 0, tzinfo=timezone.utc), "uuid-333333", "ubi_333333"
            ),
            create_test_match(
                "u3m2", user3_id, datetime(2026, 1, 23, 10, 0, tzinfo=timezone.utc), "uuid-333333", "ubi_333333"
            ),
        ],
    )

    result = data_access_fetch_user_matches_in_time_range([user1_id, user2_id, user3_id], from_date, to_date)

    assert len(result[user1_id]) == 3
    assert len(result[user2_id]) == 1
    assert user3_id not in result  # No matches in range


@pytest.mark.no_parallel
def test_fetch_matches_exceeds_pagination_limit():
    """Test that fetching 75 matches works (proves no 50-match limit)"""
    user_id = 999999
    from_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    to_date = datetime(2026, 2, 15, tzinfo=timezone.utc)  # Extend to mid-February

    # Create test user
    user_info = UserInfo(user_id, "PaginationTest", "ubi_test", "ubi_test", "uuid-test", "US/Eastern", 4000)
    upsert_user_info(user_id, "PaginationTest", "ubi_test", "ubi_test", "uuid-test", "US/Eastern", 4000)

    # Insert 75 matches in the time range (one per 12 hours to fit in ~6 weeks)
    matches = []
    for i in range(75):
        # Spread matches across January and early February (every 12 hours)
        hours_offset = i * 12
        match_time = from_date + timedelta(hours=hours_offset)
        if match_time <= to_date:  # Stay within time range
            matches.append(create_test_match(f"match_{i}", user_id, match_time, "uuid-test", "ubi_test"))

    insert_if_nonexistant_full_match_info(user_info, matches)

    result = data_access_fetch_user_matches_in_time_range([user_id], from_date, to_date)

    # Verify all matches are returned (not limited to 50)
    assert user_id in result
    assert len(result[user_id]) == len(matches), f"Expected {len(matches)} matches, got {len(result[user_id])}"


@pytest.mark.no_parallel
def test_fetch_matches_no_results():
    """Test with time range that has no matches"""
    result = data_access_fetch_user_matches_in_time_range(
        [999999], datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2020, 1, 2, tzinfo=timezone.utc)
    )
    assert result == {}


@pytest.mark.no_parallel
def test_fetch_matches_empty_user_list():
    """Test with empty user list"""
    result = data_access_fetch_user_matches_in_time_range(
        [], datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 31, tzinfo=timezone.utc)
    )
    assert result == {}


@pytest.mark.no_parallel
def test_fetch_matches_unbounded_from():
    """Test with None as from_timestamp (unbounded start)"""
    user_id = 444444
    upsert_user_info(user_id, "UnboundedTest", "ubi_unbound", "ubi_unbound", "uuid-unbound", "US/Eastern", 3200)
    user_info = UserInfo(user_id, "UnboundedTest", "ubi_unbound", "ubi_unbound", "uuid-unbound", "US/Eastern", 3200)

    matches = [
        create_test_match("old", user_id, datetime(2020, 1, 1, tzinfo=timezone.utc), "uuid-unbound", "ubi_unbound"),
        create_test_match("recent", user_id, datetime(2026, 1, 15, tzinfo=timezone.utc), "uuid-unbound", "ubi_unbound"),
    ]
    insert_if_nonexistant_full_match_info(user_info, matches)

    result = data_access_fetch_user_matches_in_time_range(
        [user_id], from_timestamp=None, to_timestamp=datetime(2026, 1, 20, tzinfo=timezone.utc)
    )

    assert len(result[user_id]) == 2  # Both matches before to_timestamp


@pytest.mark.no_parallel
def test_fetch_matches_unbounded_to():
    """Test with None as to_timestamp (unbounded end)"""
    user_id = 555555
    upsert_user_info(user_id, "UnboundedEndTest", "ubi_end", "ubi_end", "uuid-end", "US/Eastern", 3300)
    user_info = UserInfo(user_id, "UnboundedEndTest", "ubi_end", "ubi_end", "uuid-end", "US/Eastern", 3300)

    matches = [
        create_test_match("m1", user_id, datetime(2026, 1, 10, tzinfo=timezone.utc), "uuid-end", "ubi_end"),
        create_test_match("m2", user_id, datetime(2026, 2, 15, tzinfo=timezone.utc), "uuid-end", "ubi_end"),
    ]
    insert_if_nonexistant_full_match_info(user_info, matches)

    result = data_access_fetch_user_matches_in_time_range(
        [user_id], from_timestamp=datetime(2026, 1, 5, tzinfo=timezone.utc), to_timestamp=None
    )

    assert len(result[user_id]) == 2  # Both matches after from_timestamp


@pytest.mark.no_parallel
def test_ranked_match_server_split_by_week_classifies_inside_outside_and_excludes_rollback():
    """Test selected-user ranked matches are split by server voice state at match start."""
    user = create_test_user(1, "Alice")
    partner = create_test_user(2, "Bob")
    from_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    to_date = datetime(2026, 1, 31, tzinfo=timezone.utc)

    insert_user_activity(1, "Alice", 100, 1000, EVENT_CONNECT, datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc))
    insert_user_activity(1, "Alice", 100, 1000, EVENT_DISCONNECT, datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc))

    inside_match = create_test_match("inside", 1, datetime(2026, 1, 8, 11, 0, tzinfo=timezone.utc))
    outside_match = create_test_match("outside", 1, datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc))
    rollback_match = create_test_match("rollback", 1, datetime(2026, 1, 16, 11, 0, tzinfo=timezone.utc))
    rollback_match.is_rollback = True
    partner_inside_match = create_test_match("inside", 2, datetime(2026, 1, 8, 11, 0, tzinfo=timezone.utc))
    partner_outside_match = create_test_match("outside", 2, datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc))
    partner_rollback_match = create_test_match("rollback", 2, datetime(2026, 1, 16, 11, 0, tzinfo=timezone.utc))
    partner_rollback_match.is_rollback = True

    insert_if_nonexistant_full_match_info(user, [inside_match, outside_match, rollback_match])
    insert_if_nonexistant_full_match_info(
        partner, [partner_inside_match, partner_outside_match, partner_rollback_match]
    )

    rows = data_access_fetch_user_ranked_match_server_split_by_week(1, from_date, to_date)

    assert rows == [("2026-01-05", 1, 0), ("2026-01-12", 0, 1)]


@pytest.mark.no_parallel
def test_outside_ranked_match_partners_counts_shared_matches_for_selected_user_outside():
    """Test outside-server partners are ranked by same-team shared match IDs while selected user is outside."""
    user = create_test_user(1, "Alice")
    bob = create_test_user(2, "Bob")
    charlie = create_test_user(3, "Charlie")
    opponent = create_test_user(4, "Opponent")
    from_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    to_date = datetime(2026, 1, 31, tzinfo=timezone.utc)

    insert_user_activity(1, "Alice", 100, 1000, EVENT_CONNECT, datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc))
    insert_user_activity(1, "Alice", 100, 1000, EVENT_DISCONNECT, datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc))

    alice_matches = [
        create_test_match("inside", 1, datetime(2026, 1, 8, 11, 0, tzinfo=timezone.utc)),
        create_test_match("outside-bob-1", 1, datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc)),
        create_test_match("outside-bob-2", 1, datetime(2026, 1, 16, 11, 0, tzinfo=timezone.utc)),
        create_test_match("outside-charlie", 1, datetime(2026, 1, 17, 11, 0, tzinfo=timezone.utc)),
        create_test_match("outside-rollback", 1, datetime(2026, 1, 18, 11, 0, tzinfo=timezone.utc)),
        create_test_match("outside-opponent", 1, datetime(2026, 1, 19, 11, 0, tzinfo=timezone.utc)),
    ]
    alice_matches[-1].is_rollback = True
    bob_matches = [
        create_test_match("inside", 2, datetime(2026, 1, 8, 11, 0, tzinfo=timezone.utc)),
        create_test_match("outside-bob-1", 2, datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc)),
        create_test_match("outside-bob-2", 2, datetime(2026, 1, 16, 11, 0, tzinfo=timezone.utc)),
        create_test_match("outside-rollback", 2, datetime(2026, 1, 18, 11, 0, tzinfo=timezone.utc)),
    ]
    bob_matches[-1].is_rollback = True
    charlie_matches = [
        create_test_match("outside-charlie", 3, datetime(2026, 1, 17, 11, 0, tzinfo=timezone.utc)),
    ]
    opponent_match = create_test_match("outside-opponent", 4, datetime(2026, 1, 19, 11, 0, tzinfo=timezone.utc))
    opponent_match.has_win = False

    insert_if_nonexistant_full_match_info(user, alice_matches)
    insert_if_nonexistant_full_match_info(bob, bob_matches)
    insert_if_nonexistant_full_match_info(charlie, charlie_matches)
    insert_if_nonexistant_full_match_info(opponent, [opponent_match])

    rows = data_access_fetch_user_outside_ranked_match_partners(1, from_date, to_date, 1)

    assert rows == [("Bob", 2, 2, 100.0)]
