"""Tests for AI graph planning and deterministic rendering."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from deps.ai.graph_functions import _voice_time_by_month, render_graph, validate_graph_plan
from deps.data_access_data_class import UserActivity, UserInfo


def _user() -> UserInfo:
    return UserInfo(
        id=42,
        display_name="DiscordName",
        ubisoft_username_max="MainName",
        ubisoft_username_active="ActiveName",
        r6_tracker_active_id="tracker-42",
        time_zone="UTC",
        max_mmr=3000,
    )


def _activities() -> list[UserActivity]:
    now = datetime.now(timezone.utc).replace(day=15, hour=12, minute=0, second=0, microsecond=0)
    return [
        UserActivity(42, 100, "connect", (now - timedelta(hours=2)).isoformat(), 7),
        UserActivity(42, 100, "disconnect", now.isoformat(), 7),
    ]


def test_graph_plan_defaults_to_requester_and_validates_explicit_user():
    plan = validate_graph_plan(
        {"needs_graph": True, "metric": "voice_time", "chart_type": "line", "months": 2},
        42,
        [42],
    )

    assert plan["user_ids"] == [42]
    assert plan["months"] == 2


def test_graph_plan_does_not_trust_model_selected_user_ids():
    requester_plan = validate_graph_plan(
        {"needs_graph": True, "metric": "voice_time", "user_ids": [999]}, 42, []
    )
    mentioned_plan = validate_graph_plan(
        {"needs_graph": True, "metric": "voice_time", "user_ids": [42, 999]}, 42, [42]
    )

    assert requester_plan["user_ids"] == [42]
    assert mentioned_plan["user_ids"] == [42]


def test_voice_time_pairs_events_by_channel_and_normalizes_naive_timestamps():
    activities = [
        UserActivity(42, 1, "connect", "2026-01-01T10:00:00", 7),
        UserActivity(42, 2, "connect", "2026-01-01T11:00:00", 7),
        UserActivity(42, 1, "disconnect", "2026-01-01T12:00:00", 7),
        UserActivity(42, 2, "disconnect", "2026-01-01T13:00:00", 7),
    ]

    totals = _voice_time_by_month(activities)

    assert totals["2026-01"][42] == 4 * 60 * 60


@pytest.mark.parametrize("chart_type", ["line", "bar", "stacked_bar", "area", "scatter"])
def test_voice_graph_renders_supported_chart_types(chart_type):
    plan = validate_graph_plan(
        {
            "needs_graph": True,
            "metric": "voice_time",
            "chart_type": chart_type,
            "months": 2,
            "user_ids": [42],
        },
        42,
        [42],
    )
    with (
        patch("deps.ai.graph_functions.fetch_all_user_activities", return_value=_activities()),
        patch("deps.ai.graph_functions.fetch_user_info", return_value={42: _user()}),
    ):
        result = render_graph(plan, guild_id=7)

    assert result.image_bytes.startswith(b"\x89PNG")
    assert result.filename == "ai_graph.png"


def test_graph_plan_rejects_unsupported_metric():
    with pytest.raises(ValueError, match="Unsupported graph metric"):
        validate_graph_plan(
            {"needs_graph": True, "metric": "arbitrary_python", "user_ids": [42]}, 42, [42]
        )


def test_kd_graph_renders_weekly_totals():
    from types import SimpleNamespace

    now = datetime.now(timezone.utc)
    match = SimpleNamespace(
        user_id=42,
        match_timestamp=now - timedelta(days=2),
        kill_count=12,
        death_count=6,
    )
    plan = validate_graph_plan(
        {
            "needs_graph": True,
            "metric": "kd_ratio",
            "group_by": "week",
            "chart_type": "line",
            "months": 8,
            "user_ids": [42],
        },
        42,
        [42],
    )
    with (
        patch("deps.ai.graph_functions.data_access_fetch_user_matches_in_time_range", return_value={42: [match]}),
        patch("deps.ai.graph_functions.fetch_user_info", return_value={42: _user()}),
    ):
        result = render_graph(plan, guild_id=7)

    assert result.image_bytes.startswith(b"\x89PNG")
    assert "weekly K/D" in result.text
