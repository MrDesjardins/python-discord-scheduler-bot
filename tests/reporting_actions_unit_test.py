"""Tests for action generation limits and priorities."""

from datetime import datetime, timezone

from deps.reporting.insights import build_actions
from deps.reporting.models import DataQuality, ReportWindow, UserMetrics, WindowMetrics


def _user(user_id: int, out_rows: int) -> UserMetrics:
    user = UserMetrics(
        user_id=user_id,
        display_name=f"User {user_id}",
        ubisoft_name=f"user{user_id}",
        time_zone="US/Eastern",
        max_mmr=3000,
        out_rows=out_rows,
        out_seconds=out_rows * 1800,
        match_rows=out_rows,
        match_seconds=out_rows * 1800,
        voice_seconds=3600,
        outside_while_active=4,
    )
    user.flags.append("elsewhere_while_active")
    return user


def test_elsewhere_actions_are_capped() -> None:
    window = WindowMetrics(
        window=ReportWindow(
            "previous_month",
            "Previous Month",
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 11, 1, tzinfo=timezone.utc),
        ),
        users=[_user(user_id, 10 + user_id) for user_id in range(1, 21)],
        data_quality=DataQuality(),
    )
    actions = build_actions(window, {})
    elsewhere = [action for action in actions if action.category == "elsewhere"]
    assert len(elsewhere) == 10
    assert all(action.priority == "P1" for action in elsewhere)


def test_action_ids_are_unique() -> None:
    window = WindowMetrics(
        window=ReportWindow(
            "previous_month",
            "Previous Month",
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 11, 1, tzinfo=timezone.utc),
        ),
        users=[_user(1, 20)],
        data_quality=DataQuality(stale_days=30),
    )
    actions = build_actions(window, {})
    ids = [action.action_id for action in actions]
    assert len(ids) == len(set(ids))
