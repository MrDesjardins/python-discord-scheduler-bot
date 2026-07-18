"""Unit tests for the weekly player value leaderboard"""

from datetime import datetime, timedelta, timezone

from deps.analytic_player_value_weekly import (
    WEEKLY_VALUE_TOP_COUNT,
    build_weekly_value_rows,
    generate_weekly_value_image,
)
from tests.analytic_player_value_functions_unit_test import make_match

NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)


def matches_for(user_id: int, count: int, days_ago_last: int, kill_count: int = 8) -> list:
    """Matches ending days_ago_last days ago, one per day going backward"""
    return [
        make_match(
            user_id=user_id,
            match_uuid=f"u{user_id}m{i}",
            match_timestamp=NOW - timedelta(days=days_ago_last + i),
            kill_count=kill_count,
        )
        for i in range(count)
    ]


def test_inactive_user_keeps_rank_number_but_is_not_displayed():
    # User 2 has the highest value but has not played in the last 30 days
    matches_by_user = {
        1: matches_for(1, 30, days_ago_last=2, kill_count=10),
        2: matches_for(2, 30, days_ago_last=40, kill_count=30),
        3: matches_for(3, 30, days_ago_last=3, kill_count=8),
    }
    names = {1: "one", 2: "two", 3: "three"}
    rows = build_weekly_value_rows(matches_by_user, names, NOW)
    displayed = [(row.rank, row.display_name) for row in rows]
    assert "two" not in [name for _, name in displayed]
    ranks = [rank for rank, _ in displayed]
    assert 1 in ranks or 2 in ranks  # the inactive top user consumed one rank number
    assert len(ranks) == len(set(ranks))
    # User two is ranked first overall, so displayed ranks start at 2
    assert min(ranks) == 2


def test_delta_versus_previous_week():
    # 30 strong matches before last week, then a terrible last week: value must drop
    matches = matches_for(1, 30, days_ago_last=8, kill_count=14) + [
        make_match(
            user_id=1,
            match_uuid=f"recent{i}",
            match_timestamp=NOW - timedelta(days=1, hours=i),
            kill_count=1,
            death_count=10,
        )
        for i in range(20)
    ]
    rows = build_weekly_value_rows({1: matches}, {1: "one"}, NOW)
    assert len(rows) == 1
    assert rows[0].previous_value is not None
    assert rows[0].value < rows[0].previous_value


def test_new_player_has_no_previous_value():
    rows = build_weekly_value_rows({1: matches_for(1, 5, days_ago_last=1)}, {1: "one"}, NOW)
    assert rows[0].previous_value is None


def test_top_count_limit():
    matches_by_user = {uid: matches_for(uid, 12, days_ago_last=2) for uid in range(1, 41)}
    names = {uid: f"user{uid}" for uid in range(1, 41)}
    rows = build_weekly_value_rows(matches_by_user, names, NOW)
    assert len(rows) == WEEKLY_VALUE_TOP_COUNT


def test_generate_weekly_value_image_returns_png_bytes():
    rows = build_weekly_value_rows({1: matches_for(1, 12, days_ago_last=2)}, {1: "one"}, NOW)
    image_bytes = generate_weekly_value_image(rows, NOW)
    assert image_bytes.startswith(b"\x89PNG")
