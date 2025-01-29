""" Test that touch the bet and the database """

from datetime import datetime, timezone
import pytest

from deps.data_access_data_class import UserInfo
from deps.analytic_data_access import (
    data_access_fetch_tk_count_by_user,
    data_access_fetch_user_full_match_info,
    delete_all_analytic_tables,
    insert_if_nonexistant_full_match_info,
)
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from deps.models import UserFullMatchStats

fake_date = datetime(2024, 11, 1, 12, 30, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    database_manager.set_database_name(DATABASE_NAME_TEST)

    delete_all_analytic_tables()

    # Yield control to the test functions
    yield

    # Teardown
    database_manager.set_database_name(DATABASE_NAME)


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
    # Act
    result = data_access_fetch_tk_count_by_user(fake_date)
    # Assert
    assert result is not None
    assert len(result) == 1
