"""
Unit tests for streak logic.
No database, no Discord — only pure Python date arithmetic.
"""

from datetime import date, timedelta

import pytest

from deps.streak_data_access import compute_current_streak

# Pin "today" for all tests so results don't change depending on when they run.
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def days_ago(n: int) -> date:
    """Return the date n days before today."""
    return TODAY - timedelta(days=n)


# ---------------------------------------------------------------------------
# No streak
# ---------------------------------------------------------------------------


def test_empty_list_returns_zero():
    """A user with no recorded play days has no streak."""
    assert compute_current_streak([]) == 0


def test_last_played_two_days_ago_returns_zero():
    """A gap of two full days breaks the streak."""
    assert compute_current_streak([days_ago(2), days_ago(3)]) == 0


def test_last_played_a_week_ago_returns_zero():
    """A user who stopped playing a week ago has no active streak."""
    assert compute_current_streak([days_ago(7), days_ago(8), days_ago(9)]) == 0


# ---------------------------------------------------------------------------
# Active streak ending today
# ---------------------------------------------------------------------------


def test_played_only_today_returns_one():
    """Playing for the first time today gives a streak of 1."""
    assert compute_current_streak([TODAY]) == 1


def test_two_consecutive_days_ending_today():
    assert compute_current_streak([TODAY, YESTERDAY]) == 2


def test_seven_consecutive_days_ending_today():
    dates = [days_ago(i) for i in range(7)]  # today, yesterday, ..., 6 days ago
    assert compute_current_streak(dates) == 7


def test_thirty_consecutive_days_ending_today():
    dates = [days_ago(i) for i in range(30)]
    assert compute_current_streak(dates) == 30


# ---------------------------------------------------------------------------
# Active streak ending yesterday (user hasn't played yet today)
# ---------------------------------------------------------------------------


def test_played_only_yesterday_returns_one():
    """A streak is still active if the most recent day is yesterday."""
    assert compute_current_streak([YESTERDAY]) == 1


def test_seven_consecutive_days_ending_yesterday():
    dates = [days_ago(i) for i in range(1, 8)]  # yesterday, ..., 7 days ago
    assert compute_current_streak(dates) == 7


# ---------------------------------------------------------------------------
# Gap in the middle — streak stops at the gap
# ---------------------------------------------------------------------------


def test_gap_in_middle_counts_only_recent_run():
    """A gap two days into the past stops the streak at the recent run."""
    # Played today and yesterday, then gap, then played 3+ days ago.
    dates = [TODAY, YESTERDAY, days_ago(3), days_ago(4)]
    assert compute_current_streak(dates) == 2


def test_played_today_but_gap_after_today():
    """Only one day of recent play; older dates don't extend it."""
    dates = [TODAY, days_ago(3), days_ago(4), days_ago(5)]
    assert compute_current_streak(dates) == 1


def test_played_yesterday_gap_then_older():
    """Streak ends at the gap even when there are older consecutive days."""
    dates = [YESTERDAY, days_ago(3), days_ago(4), days_ago(5)]
    assert compute_current_streak(dates) == 1


# ---------------------------------------------------------------------------
# Milestone boundary checks
# ---------------------------------------------------------------------------


def test_streak_of_three_exactly():
    dates = [days_ago(i) for i in range(3)]
    assert compute_current_streak(dates) == 3


def test_streak_of_fourteen_exactly():
    dates = [days_ago(i) for i in range(14)]
    assert compute_current_streak(dates) == 14
