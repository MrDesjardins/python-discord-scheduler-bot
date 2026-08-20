"""Deterministic graph planning output and rendering for AI requests."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from deps.analytic_data_access import (
    data_access_fetch_user_matches_in_time_range,
    fetch_all_user_activities,
    fetch_user_info,
)
from deps.data_access_data_class import UserActivity
from deps.system_database import EVENT_CONNECT, EVENT_DISCONNECT


SUPPORTED_CHART_TYPES = {"line", "bar", "stacked_bar", "area", "scatter"}


@dataclass
class GraphResponse:
    """A Discord-ready graph response."""

    text: str
    image_bytes: bytes
    filename: str = "ai_graph.png"


def looks_like_graph_request(message: str) -> bool:
    """Cheap routing guard; the AI plan remains authoritative afterward."""
    return bool(re.search(r"\b(graph|plot|chart|visuali[sz]e|plotting)\b", message.casefold()))


def validate_graph_plan(plan: dict, requester_id: int, resolved_user_ids: list[int]) -> dict:
    """Validate and normalize the small graph-plan contract."""
    if plan.get("needs_graph") is not True:
        raise ValueError("The request is not a graph request")
    chart_type = plan.get("chart_type") or "line"
    if chart_type not in SUPPORTED_CHART_TYPES:
        raise ValueError(f"Unsupported chart type: {chart_type}")
    metric = plan.get("metric", "voice_time")
    if metric not in {"voice_time", "kd_ratio"}:
        raise ValueError(f"Unsupported graph metric: {metric}")
    months = plan.get("months", 12)
    if not isinstance(months, int) or not 1 <= months <= 36:
        raise ValueError("Graph months must be between 1 and 36")
    # Never trust model-selected identities. Explicit mentions are authoritative;
    # otherwise the only supported implicit identity is the requester ("my/me").
    requested_user_ids = plan.get("user_ids")
    if requested_user_ids is not None and (
        not isinstance(requested_user_ids, list)
        or not all(isinstance(value, int) for value in requested_user_ids)
    ):
        raise ValueError("Graph user_ids must be integers")
    user_ids = list(dict.fromkeys(resolved_user_ids or [requester_id]))
    if len(user_ids) > 10:
        raise ValueError("Graphs are limited to 10 users")
    group_by = plan.get("group_by") or ("week" if metric == "kd_ratio" else "month")
    if group_by not in {"week", "month"}:
        raise ValueError("Graphs support weekly or monthly grouping")
    normalized = dict(plan)
    normalized.update(
        {
            "chart_type": chart_type,
            "metric": metric,
            "months": months,
            "user_ids": user_ids,
            "group_by": group_by,
        }
    )
    return normalized


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _subtract_months(value: datetime, months: int) -> datetime:
    index = value.year * 12 + value.month - 1 - months
    return value.replace(year=index // 12, month=index % 12 + 1, day=1)


def _parse_activity_timestamp(timestamp: str) -> datetime:
    """Normalize database timestamps before comparing or sorting them."""
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _distribute_session_by_month(start: datetime, end: datetime) -> dict[str, float]:
    """Split one voice session across calendar months in seconds."""
    if end <= start:
        return {}
    values: dict[str, float] = defaultdict(float)
    cursor = start
    while cursor < end:
        month_end = _subtract_months(cursor.replace(day=1), -1)
        segment_end = min(end, month_end)
        values[cursor.strftime("%Y-%m")] += (segment_end - cursor).total_seconds()
        cursor = segment_end
    return dict(values)


def _voice_time_by_month(activities: list[UserActivity]) -> dict[str, dict[int, float]]:
    """Pair activity per user/channel, preventing cross-channel event pairing."""
    sessions: dict[tuple[int, int], datetime] = {}
    totals: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for activity in sorted(activities, key=lambda item: _parse_activity_timestamp(item.timestamp)):
        key = (activity.user_id, activity.channel_id)
        timestamp = _parse_activity_timestamp(activity.timestamp)
        if activity.event == EVENT_CONNECT:
            sessions[key] = timestamp
        elif activity.event == EVENT_DISCONNECT and key in sessions:
            for month, seconds in _distribute_session_by_month(sessions.pop(key), timestamp).items():
                totals[month][activity.user_id] += seconds
    return totals


def _render_voice_time_graph(plan: dict, guild_id: int | None) -> GraphResponse:
    now = datetime.now(timezone.utc)
    end_month = _month_start(now)
    start_month = _subtract_months(end_month, plan["months"] - 1)
    activities = fetch_all_user_activities(
        from_day=max(31, plan["months"] * 32), to_day=0, guild_id=guild_id
    )
    activities = [
        activity
        for activity in activities
        if start_month <= _parse_activity_timestamp(activity.timestamp) < now
        and (not plan["user_ids"] or activity.user_id in plan["user_ids"])
    ]
    monthly_by_user = _voice_time_by_month(activities)
    month_keys = []
    cursor = start_month
    for _ in range(plan["months"]):
        month_keys.append(cursor.strftime("%Y-%m"))
        cursor = _subtract_months(cursor, -1)
    users = fetch_user_info()
    labels = {
        user_id: (
            users[user_id].ubisoft_username_active
            or users[user_id].ubisoft_username_max
            or users[user_id].display_name
        )
        for user_id in plan["user_ids"]
        if user_id in users
    }
    if not labels:
        raise ValueError("No matching user data was found")
    values = {
        user_id: [monthly_by_user.get(month, {}).get(user_id, 0.0) / 3600 for month in month_keys]
        for user_id in labels
    }
    if not any(any(series) for series in values.values()):
        raise ValueError("No activity data was found for the requested period")

    fig, ax = plt.subplots(figsize=(12, 6))
    chart_type = plan["chart_type"]
    if chart_type == "line" or chart_type == "scatter":
        for user_id, series in values.items():
            if chart_type == "scatter":
                ax.scatter(month_keys, series, label=labels[user_id])
            else:
                ax.plot(month_keys, series, marker="o", label=labels[user_id])
    elif chart_type == "area":
        for user_id, series in values.items():
            ax.fill_between(range(len(month_keys)), series, alpha=0.35, label=labels[user_id])
        ax.set_xticks(range(len(month_keys)), month_keys)
    elif chart_type == "stacked_bar":
        bottom = [0.0] * len(month_keys)
        for user_id, series in values.items():
            ax.bar(month_keys, series, bottom=bottom, label=labels[user_id])
            bottom = [left + right for left, right in zip(bottom, series)]
    else:
        width = 0.8 / max(1, len(values))
        for index, (user_id, series) in enumerate(values.items()):
            offsets = [x + (index - (len(values) - 1) / 2) * width for x in range(len(month_keys))]
            ax.bar(offsets, series, width=width, label=labels[user_id])
        ax.set_xticks(range(len(month_keys)), month_keys)
    ax.set_title(plan.get("title") or "Time on this server per month")
    ax.set_xlabel("Month")
    ax.set_ylabel("Hours")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.autofmt_xdate()
    fig.tight_layout()
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=150)
    plt.close(fig)
    return GraphResponse(
        text=f"Here is the {chart_type.replace('_', ' ')} graph for the last {plan['months']} months.",
        image_bytes=output.getvalue(),
    )


def _render_kd_graph(plan: dict) -> GraphResponse:
    """Render weekly K/D using total kills divided by total deaths."""
    now = datetime.now(timezone.utc)
    start = _subtract_months(_month_start(now), plan["months"] - 1)
    start -= timedelta(days=start.weekday())
    matches_by_user = data_access_fetch_user_matches_in_time_range(plan["user_ids"], start, now)
    week_keys: list[str] = []
    cursor = start
    while cursor < now:
        week_keys.append(cursor.date().isoformat())
        cursor += timedelta(days=7)
    totals: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for user_id, matches in matches_by_user.items():
        for match in matches:
            timestamp = match.match_timestamp
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            week_start = timestamp - timedelta(days=timestamp.weekday())
            week_key = week_start.date().isoformat()
            if week_key in week_keys:
                totals[week_key][user_id][0] += int(match.kill_count or 0)
                totals[week_key][user_id][1] += int(match.death_count or 0)
    users = fetch_user_info()
    labels = {
        user_id: (
            users[user_id].ubisoft_username_active
            or users[user_id].ubisoft_username_max
            or users[user_id].display_name
        )
        for user_id in plan["user_ids"]
        if user_id in users
    }
    values = {}
    for user_id in labels:
        values[user_id] = [
            (
                totals[week].get(user_id, [0, 0])[0]
                / totals[week].get(user_id, [0, 0])[1]
            )
            if totals[week].get(user_id, [0, 0])[1] > 0
            else float("nan")
            for week in week_keys
        ]
    if not labels or not any(any(value == value for value in series) for series in values.values()):
        raise ValueError("No K/D data was found for the requested period")

    fig, ax = plt.subplots(figsize=(12, 6))
    chart_type = plan["chart_type"]
    if chart_type in {"line", "area"}:
        for user_id, series in values.items():
            ax.plot(week_keys, series, marker="o", label=labels[user_id])
            if chart_type == "area":
                ax.fill_between(range(len(week_keys)), series, alpha=0.25)
        ax.set_xticks(range(len(week_keys)), week_keys)
    else:
        width = 0.8 / max(1, len(values))
        for index, (user_id, series) in enumerate(values.items()):
            offsets = [x + (index - (len(values) - 1) / 2) * width for x in range(len(week_keys))]
            ax.bar(offsets, series, width=width, label=labels[user_id])
        ax.set_xticks(range(len(week_keys)), week_keys)
    ax.set_title(plan.get("title") or "Weekly K/D")
    ax.set_xlabel("Week starting")
    ax.set_ylabel("K/D")
    ax.axhline(1.0, color="gray", linewidth=1, alpha=0.5)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.autofmt_xdate()
    fig.tight_layout()
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=150)
    plt.close(fig)
    return GraphResponse(
        text=f"Here is the weekly K/D {chart_type.replace('_', ' ')} for the last {plan['months']} months.",
        image_bytes=output.getvalue(),
    )


def render_graph(plan: dict, guild_id: int | None) -> GraphResponse:
    """Render a validated graph plan using fixed Python renderers."""
    if plan["metric"] == "voice_time":
        return _render_voice_time_graph(plan, guild_id)
    if plan["metric"] == "kd_ratio":
        return _render_kd_graph(plan)
    raise ValueError(f"No renderer exists for metric {plan['metric']}")
