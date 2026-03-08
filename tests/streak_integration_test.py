"""
Integration tests for streak data access functions.
Uses the test database — no Discord.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from deps.analytic_data_access import insert_user_activity
from deps.streak_data_access import (
    compute_current_streak,
    fetch_distinct_play_dates,
    fetch_user_ids_active_on_date,
)
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, EVENT_CONNECT, EVENT_DISCONNECT, database_manager

USER_1 = 1001
USER_2 = 1002
GUILD_A = 9001
GUILD_B = 9002
CHANNEL = 100

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def days_ago(n: int) -> date:
    return TODAY - timedelta(days=n)


def connect_at(user_id: int, guild_id: int, d: date, hour: int = 20) -> None:
    """Insert a connect event for a user on a given date."""
    ts = datetime(d.year, d.month, d.day, hour, 0, 0, tzinfo=timezone.utc)
    insert_user_activity(user_id, f"user_{user_id}", CHANNEL, guild_id, EVENT_CONNECT, ts)


def disconnect_at(user_id: int, guild_id: int, d: date, hour: int = 22) -> None:
    """Insert a disconnect event for a user on a given date."""
    ts = datetime(d.year, d.month, d.day, hour, 0, 0, tzinfo=timezone.utc)
    insert_user_activity(user_id, f"user_{user_id}", CHANNEL, guild_id, EVENT_DISCONNECT, ts)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Reset the test database before each test and restore the real one after."""
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()

    yield

    database_manager.set_database_name(DATABASE_NAME)


# ---------------------------------------------------------------------------
# fetch_distinct_play_dates
# ---------------------------------------------------------------------------


@pytest.mark.no_parallel
def test_no_activity_returns_empty_list():
    """A user who never connected has no play dates."""
    result = fetch_distinct_play_dates(USER_1, GUILD_A)
    assert result == []


@pytest.mark.no_parallel
def test_single_connect_returns_one_date():
    """One connect event gives exactly one play date."""
    connect_at(USER_1, GUILD_A, days_ago(0))
    result = fetch_distinct_play_dates(USER_1, GUILD_A)
    assert result == [TODAY]


@pytest.mark.no_parallel
def test_multiple_connects_same_day_returns_one_date():
    """Several connect events on the same calendar day collapse to a single date."""
    connect_at(USER_1, GUILD_A, TODAY, hour=18)
    connect_at(USER_1, GUILD_A, TODAY, hour=20)
    connect_at(USER_1, GUILD_A, TODAY, hour=22)
    result = fetch_distinct_play_dates(USER_1, GUILD_A)
    assert result == [TODAY]


@pytest.mark.no_parallel
def test_connects_on_multiple_days_returns_all_dates_newest_first():
    """Three distinct play days are returned sorted newest first."""
    connect_at(USER_1, GUILD_A, days_ago(0))
    connect_at(USER_1, GUILD_A, days_ago(1))
    connect_at(USER_1, GUILD_A, days_ago(3))  # Gap on day 2
    result = fetch_distinct_play_dates(USER_1, GUILD_A)
    assert result == [days_ago(0), days_ago(1), days_ago(3)]


@pytest.mark.no_parallel
def test_disconnect_only_does_not_count_as_play_day():
    """A disconnect event without a prior connect does not create a play day."""
    disconnect_at(USER_1, GUILD_A, TODAY)
    result = fetch_distinct_play_dates(USER_1, GUILD_A)
    assert result == []


@pytest.mark.no_parallel
def test_guild_isolation_different_guild_not_counted():
    """Activity in guild B is not included in guild A's play dates."""
    connect_at(USER_1, GUILD_A, days_ago(0))
    connect_at(USER_1, GUILD_B, days_ago(1))
    result = fetch_distinct_play_dates(USER_1, GUILD_A)
    assert result == [TODAY]  # Only today from GUILD_A


@pytest.mark.no_parallel
def test_user_isolation_other_user_not_counted():
    """Activity from USER_2 does not appear in USER_1's play dates."""
    connect_at(USER_1, GUILD_A, days_ago(0))
    connect_at(USER_2, GUILD_A, days_ago(1))
    result = fetch_distinct_play_dates(USER_1, GUILD_A)
    assert result == [TODAY]


# ---------------------------------------------------------------------------
# fetch_user_ids_active_on_date
# ---------------------------------------------------------------------------


@pytest.mark.no_parallel
def test_no_users_active_on_date_returns_empty():
    """No connects on the target date returns an empty list."""
    result = fetch_user_ids_active_on_date(GUILD_A, TODAY)
    assert result == []


@pytest.mark.no_parallel
def test_one_user_active_on_date():
    """A single user who connected today appears in the result."""
    connect_at(USER_1, GUILD_A, TODAY)
    result = fetch_user_ids_active_on_date(GUILD_A, TODAY)
    assert result == [USER_1]


@pytest.mark.no_parallel
def test_two_users_active_on_same_date():
    """Both users who connected today are returned."""
    connect_at(USER_1, GUILD_A, TODAY)
    connect_at(USER_2, GUILD_A, TODAY)
    result = fetch_user_ids_active_on_date(GUILD_A, TODAY)
    assert set(result) == {USER_1, USER_2}


@pytest.mark.no_parallel
def test_user_active_yesterday_not_included_for_today():
    """A user who only connected yesterday does not appear for today."""
    connect_at(USER_1, GUILD_A, days_ago(1))
    result = fetch_user_ids_active_on_date(GUILD_A, TODAY)
    assert result == []


@pytest.mark.no_parallel
def test_guild_isolation_for_active_users():
    """Users from a different guild are not returned."""
    connect_at(USER_1, GUILD_B, TODAY)
    result = fetch_user_ids_active_on_date(GUILD_A, TODAY)
    assert result == []


@pytest.mark.no_parallel
def test_multiple_connects_same_day_user_appears_once():
    """A user who connected multiple times today appears only once."""
    connect_at(USER_1, GUILD_A, TODAY, hour=18)
    connect_at(USER_1, GUILD_A, TODAY, hour=21)
    result = fetch_user_ids_active_on_date(GUILD_A, TODAY)
    assert result == [USER_1]


# ---------------------------------------------------------------------------
# End-to-end: DB → streak calculation
# ---------------------------------------------------------------------------


@pytest.mark.no_parallel
def test_end_to_end_seven_day_streak():
    """Insert 7 consecutive days of activity and verify a 7-day streak."""
    for i in range(7):
        connect_at(USER_1, GUILD_A, days_ago(i))

    play_dates = fetch_distinct_play_dates(USER_1, GUILD_A)
    streak = compute_current_streak(play_dates)

    assert streak == 7


@pytest.mark.no_parallel
def test_end_to_end_streak_broken_by_gap():
    """A gap in the middle means only the recent run counts."""
    connect_at(USER_1, GUILD_A, TODAY)
    connect_at(USER_1, GUILD_A, YESTERDAY)
    # Day 2 missing — gap here
    connect_at(USER_1, GUILD_A, days_ago(3))
    connect_at(USER_1, GUILD_A, days_ago(4))

    play_dates = fetch_distinct_play_dates(USER_1, GUILD_A)
    streak = compute_current_streak(play_dates)

    assert streak == 2  # Only today + yesterday


@pytest.mark.no_parallel
def test_end_to_end_no_streak_when_last_play_was_two_days_ago():
    """If the user last played 2 days ago the streak is 0."""
    connect_at(USER_1, GUILD_A, days_ago(2))
    connect_at(USER_1, GUILD_A, days_ago(3))

    play_dates = fetch_distinct_play_dates(USER_1, GUILD_A)
    streak = compute_current_streak(play_dates)

    assert streak == 0
