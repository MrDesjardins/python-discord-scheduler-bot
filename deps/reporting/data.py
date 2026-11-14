"""Read-only data collection and deterministic metrics for the HTML report."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from deps.reporting.models import (
    DataQuality,
    MatchRow,
    NetworkEdge,
    NetworkNode,
    PairRelationship,
    ReportData,
    ReportWindow,
    UserInfo,
    UserMetrics,
    VoiceSession,
    WindowMetrics,
)

WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
HOUR_LABELS = tuple(f"{h:02d}" for h in range(24))
SESSION_BUCKETS = (
    ("<15m", 0, 15),
    ("15-30m", 15, 30),
    ("30-60m", 30, 60),
    ("1-2h", 60, 120),
    ("2-4h", 120, 240),
    ("4h+", 240, 10**9),
)
LONG_SESSION_HOURS = 12
OUTSIDE_ACTIVE_THRESHOLD = 3
SMALL_SAMPLE = 5
MIN_EDGE_CO_VOICE_SECONDS = 30 * 60
MIN_EDGE_CO_MATCHES = 2
NETWORK_NODE_LIMIT = 60
NETWORK_EDGE_LIMIT = 90


def parse_db_datetime(raw: object) -> datetime:
    """Parse SQLite ISO-8601 text into an aware UTC datetime."""
    parsed = datetime.fromisoformat(str(raw).replace(" ", "T"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def _add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    return date(year, month, 1)


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def _percent(part: float, whole: float) -> float:
    return (float(part) * 100.0 / float(whole)) if whole else 0.0


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _connect(path: str | Path) -> sqlite3.Connection:
    """Open the report database read-only so a report can never mutate it."""
    uri = f"file:{Path(path).resolve()}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


def _fetchall(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[tuple]:
    return conn.execute(query, params).fetchall()


def get_report_windows(reference_date: date, all_data_start: date) -> tuple[str, list[ReportWindow]]:
    """Return the report month and every window the report renders."""
    current_month_start = _month_start(reference_date)
    previous_month_start = _add_months(current_month_start, -1)
    previous_three_months_start = _add_months(current_month_start, -3)
    ytd_start = date(previous_month_start.year, 1, 1)
    report_month = previous_month_start.strftime("%Y-%m")
    end_exclusive = _utc_start(current_month_start)
    return report_month, [
        ReportWindow(
            key="previous_month",
            title="Previous Month",
            start=_utc_start(previous_month_start),
            end_exclusive=end_exclusive,
        ),
        ReportWindow(
            key="previous_three_months",
            title="Previous 3 Complete Months",
            start=_utc_start(previous_three_months_start),
            end_exclusive=end_exclusive,
        ),
        ReportWindow(
            key="year_to_date",
            title="Year to Date",
            start=_utc_start(ytd_start),
            end_exclusive=end_exclusive,
        ),
        ReportWindow(
            key="all_data",
            title="All Tracked Data",
            start=_utc_start(all_data_start),
            end_exclusive=end_exclusive,
        ),
        ReportWindow(
            key="last_28_days",
            title="Last 28 Days (Action Window)",
            start=_utc_start(reference_date - timedelta(days=28)),
            end_exclusive=_utc_start(reference_date),
        ),
    ]


def load_user_infos(conn: sqlite3.Connection) -> dict[int, UserInfo]:
    rows = _fetchall(
        conn,
        """
        SELECT id, display_name, ubisoft_username_active, ubisoft_username_max, time_zone, max_mmr
        FROM user_info;
        """,
    )
    users: dict[int, UserInfo] = {}
    for user_id, display_name, active_name, max_name, tz_name, max_mmr in rows:
        users[int(user_id)] = UserInfo(
            user_id=int(user_id),
            display_name=str(display_name or user_id),
            ubisoft_name=str(active_name or max_name or ""),
            time_zone=str(tz_name or "UTC"),
            max_mmr=int(max_mmr or 0),
        )
    return users


def load_snapshot_bounds(conn: sqlite3.Connection) -> tuple[Optional[datetime], Optional[datetime], Optional[date]]:
    activity = _fetchall(conn, "SELECT MAX(timestamp) FROM user_activity;")[0][0]
    match = _fetchall(conn, "SELECT MAX(match_timestamp) FROM user_full_match_info;")[0][0]
    start = _fetchall(
        conn,
        """
        SELECT MIN(ts) FROM (
            SELECT MIN(timestamp) AS ts FROM user_activity
            UNION ALL
            SELECT MIN(match_timestamp) AS ts FROM user_full_match_info
        )
        WHERE ts IS NOT NULL;
        """,
    )[0][0]
    max_activity = parse_db_datetime(activity) if activity else None
    max_match = parse_db_datetime(match) if match else None
    min_day = parse_db_datetime(start).date() if start else None
    return max_activity, max_match, min_day


def load_sessions(
    conn: sqlite3.Connection, end_exclusive: datetime
) -> tuple[list[VoiceSession], list[datetime], list[datetime]]:
    """Pair connect/disconnect events per user and channel.

    Pairing per (user_id, channel_id) is deliberate. The older report query paired a
    connect with the earliest later disconnect across every channel, which mispairs
    users who switch channels. Unmatched disconnects and sessions still open at the
    report end are returned so the report can show data-quality counts.
    """
    rows = _fetchall(
        conn,
        """
        SELECT user_id, channel_id, event, timestamp
        FROM user_activity
        WHERE julianday(timestamp) < julianday(?)
        ORDER BY user_id, channel_id, julianday(timestamp), id;
        """,
        (end_exclusive.isoformat(),),
    )
    opened: dict[tuple[int, int], datetime] = {}
    sessions: list[VoiceSession] = []
    unmatched: list[datetime] = []
    for user_id_raw, channel_id_raw, event, timestamp_raw in rows:
        user_id = int(user_id_raw)
        channel_id = int(channel_id_raw)
        timestamp = parse_db_datetime(timestamp_raw)
        key = (user_id, channel_id)
        if event == "connect":
            opened[key] = timestamp
            continue
        if event != "disconnect":
            continue
        start = opened.pop(key, None)
        if start is None:
            unmatched.append(timestamp)
            continue
        if timestamp > start:
            sessions.append(VoiceSession(user_id=user_id, channel_id=channel_id, start=start, end=timestamp))
    open_sessions = [start for start in opened.values() if start < end_exclusive]
    return sessions, unmatched, open_sessions


def load_matches(conn: sqlite3.Connection, end_exclusive: datetime) -> list[MatchRow]:
    rows = _fetchall(
        conn,
        """
        SELECT user_id, match_uuid, match_timestamp, match_duration_ms, has_win,
               data_center, points_gained, rank_name, map_name, operators,
               round_disconnected_count, is_surrender, is_forfeit
        FROM user_full_match_info
        WHERE julianday(match_timestamp) < julianday(?)
          AND LOWER(session_type) = 'ranked'
          AND is_rollback = 0;
        """,
        (end_exclusive.isoformat(),),
    )
    matches: list[MatchRow] = []
    for row in rows:
        (
            user_id,
            match_uuid,
            match_timestamp,
            duration_ms,
            has_win,
            data_center,
            points_gained,
            rank_name,
            map_name,
            operators,
            round_disconnected_count,
            is_surrender,
            is_forfeit,
        ) = row
        matches.append(
            MatchRow(
                user_id=int(user_id),
                match_uuid=str(match_uuid),
                match_timestamp=parse_db_datetime(match_timestamp),
                duration_ms=int(duration_ms or 0),
                has_win=bool(has_win),
                data_center=str(data_center or "Unknown"),
                points_gained=int(points_gained or 0),
                rank_name=str(rank_name or ""),
                map_name=str(map_name or ""),
                operators=str(operators or ""),
                round_disconnected_count=int(round_disconnected_count or 0),
                is_surrender=bool(is_surrender),
                is_forfeit=bool(is_forfeit),
            )
        )
    return matches


def load_messages(conn: sqlite3.Connection, window: ReportWindow) -> tuple[int, int, dict[int, int]]:
    """Return human messages, distinct authors, and per-user counts for a window."""
    try:
        rows = _fetchall(
            conn,
            """
            SELECT author_id, COUNT(*)
            FROM archived_message
            WHERE julianday(created_at) >= julianday(?)
              AND julianday(created_at) < julianday(?)
              AND author_is_bot = 0
              AND channel_name != 'moderator-audit'
            GROUP BY author_id;
            """,
            (window.start.isoformat(), window.end_exclusive.isoformat()),
        )
    except sqlite3.Error:
        return 0, 0, {}
    counts = {int(author_id): int(count) for author_id, count in rows}
    return sum(counts.values()), len(counts), counts


def load_rollback_counts(conn: sqlite3.Connection, windows: Iterable[ReportWindow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for window in windows:
        row = _fetchall(
            conn,
            """
            SELECT COUNT(*)
            FROM user_full_match_info
            WHERE julianday(match_timestamp) >= julianday(?)
              AND julianday(match_timestamp) < julianday(?)
              AND LOWER(session_type) = 'ranked'
              AND is_rollback = 1;
            """,
            (window.start.isoformat(), window.end_exclusive.isoformat()),
        )[0][0]
        counts[window.key] = int(row or 0)
    return counts


def merge_intervals(intervals: Iterable[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Merge overlapping voice intervals for one user."""
    ordered = sorted((s, e) for s, e in intervals if e > s)
    merged: list[tuple[datetime, datetime]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def intervals_by_user(sessions: Iterable[VoiceSession]) -> dict[int, list[tuple[datetime, datetime]]]:
    grouped: dict[int, list[tuple[datetime, datetime]]] = defaultdict(list)
    for session in sessions:
        grouped[session.user_id].append((session.start, session.end))
    return {user_id: merge_intervals(values) for user_id, values in grouped.items()}


def clip_sessions(sessions: Iterable[VoiceSession], window: ReportWindow) -> list[VoiceSession]:
    clipped: list[VoiceSession] = []
    for session in sessions:
        if session.end <= window.start or session.start >= window.end_exclusive:
            continue
        start = max(session.start, window.start)
        end = min(session.end, window.end_exclusive)
        if end > start:
            clipped.append(VoiceSession(session.user_id, session.channel_id, start, end))
    return clipped


def overlap_seconds(
    intervals_a: Iterable[tuple[datetime, datetime]],
    intervals_b: Iterable[tuple[datetime, datetime]],
) -> float:
    total = 0.0
    a = list(intervals_a)
    b = list(intervals_b)
    i = j = 0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if end > start:
            total += (end - start).total_seconds()
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return total


def _local_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _split_hours(session: VoiceSession, zone: ZoneInfo) -> Iterable[tuple[tuple[int, int], float]]:
    """Yield ((weekday, local_hour), seconds) segments for a session."""
    cursor = session.start.astimezone(zone)
    end = session.end.astimezone(zone)
    guard = 0
    while cursor < end and guard < 24 * 14:
        guard += 1
        next_hour = cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        segment_end = min(end, next_hour)
        seconds = max(0.0, (segment_end - cursor).total_seconds())
        if seconds > 0:
            yield (cursor.weekday(), cursor.hour), seconds
        cursor = next_hour


def _session_bucket(minutes: float) -> str:
    for label, low, high in SESSION_BUCKETS:
        if low <= minutes < high:
            return label
    return SESSION_BUCKETS[-1][0]


def _concurrency(sessions: Iterable[VoiceSession], window: ReportWindow) -> tuple[int, Optional[datetime], float]:
    """Peak and time-weighted average concurrent users from clipped sessions."""
    by_user = intervals_by_user(sessions)
    events: list[tuple[datetime, int]] = []
    for intervals in by_user.values():
        for start, end in intervals:
            events.append((start, 1))
            events.append((end, -1))
    events.sort()
    current = 0
    peak = 0
    peak_at: Optional[datetime] = None
    last_t: Optional[datetime] = None
    integral = 0.0
    for timestamp, delta in events:
        if last_t is not None and timestamp > last_t:
            integral += current * (timestamp - last_t).total_seconds()
        current += delta
        if current > peak:
            peak = current
            peak_at = timestamp
        last_t = timestamp
    total_seconds = max(1.0, (window.end_exclusive - window.start).total_seconds())
    return peak, peak_at, integral / total_seconds


def _unique_users_per_day(sessions: Iterable[VoiceSession]) -> list[tuple[date, int]]:
    days: dict[date, set[int]] = defaultdict(set)
    for session in sessions:
        cursor = session.start.date()
        last = (session.end - timedelta(microseconds=1)).date()
        while cursor <= last:
            days[cursor].add(session.user_id)
            cursor += timedelta(days=1)
    return sorted((day, len(users)) for day, users in days.items())


def _trends(
    sessions: Iterable[VoiceSession],
    matches: Iterable[MatchRow],
) -> tuple[list[tuple[date, float]], list[tuple[date, int]], list[tuple[str, float]], list[tuple[str, int]]]:
    weekly_voice: dict[date, float] = defaultdict(float)
    weekly_matches: dict[date, int] = defaultdict(int)
    monthly_voice: dict[str, float] = defaultdict(float)
    monthly_matches: dict[str, int] = defaultdict(int)
    for session in sessions:
        cursor = session.start
        while cursor < session.end:
            if cursor.month == 12:
                boundary = cursor.replace(
                    year=cursor.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
                )
            else:
                boundary = cursor.replace(month=cursor.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            segment_end = min(session.end, boundary)
            seconds = max(0.0, (segment_end - cursor).total_seconds())
            weekly_voice[_week_start(cursor.date())] += seconds
            monthly_voice[cursor.strftime("%Y-%m")] += seconds
            cursor = segment_end
    for match in matches:
        weekly_matches[_week_start(match.match_timestamp.date())] += 1
        monthly_matches[match.match_timestamp.strftime("%Y-%m")] += 1
    return (
        sorted(weekly_voice.items()),
        sorted(weekly_matches.items()),
        sorted(monthly_voice.items()),
        sorted(monthly_matches.items()),
    )


def _co_voice_pairs(sessions: Iterable[VoiceSession]) -> dict[tuple[int, int], float]:
    """Overlap seconds for every pair of users who shared voice time.

    Uses a sweep over merged per-user intervals. This stays cheap for a month and
    avoids the double counting that per-session pairs would introduce when a user
    moves between channels.
    """
    intervals: list[tuple[datetime, datetime, int]] = []
    for user_id, values in intervals_by_user(sessions).items():
        for start, end in values:
            intervals.append((start, end, user_id))
    intervals.sort(key=lambda item: item[0])
    active: list[tuple[datetime, datetime, int]] = []
    pairs: dict[tuple[int, int], float] = defaultdict(float)
    for start, end, user_id in intervals:
        active = [item for item in active if item[1] > start]
        for other_start, other_end, other_id in active:
            if other_id == user_id:
                continue
            overlap = (min(end, other_end) - max(start, other_start)).total_seconds()
            if overlap > 0:
                key = (min(user_id, other_id), max(user_id, other_id))
                pairs[key] += overlap
        active.append((start, end, user_id))
    return dict(pairs)


def _co_match_pairs(matches: Iterable[MatchRow]) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], int]]:
    by_match: dict[str, list[MatchRow]] = defaultdict(list)
    for match in matches:
        by_match[match.match_uuid].append(match)
    pairs: dict[tuple[int, int], int] = defaultdict(int)
    wins: dict[tuple[int, int], int] = defaultdict(int)
    for rows in by_match.values():
        unique: dict[int, MatchRow] = {}
        for row in rows:
            unique.setdefault(row.user_id, row)
        ids = sorted(unique)
        for i, user_a in enumerate(ids):
            for user_b in ids[i + 1 :]:
                key = (user_a, user_b)
                pairs[key] += 1
                if unique[user_a].has_win == unique[user_b].has_win:
                    wins[key] += 1
    return dict(pairs), dict(wins)


def _outside_matches(
    matches: Iterable[MatchRow], global_intervals: dict[int, list[tuple[datetime, datetime]]]
) -> list[MatchRow]:
    outside: list[MatchRow] = []
    for match in matches:
        in_server = any(
            start <= match.match_timestamp and end >= match.start
            for start, end in global_intervals.get(match.user_id, [])
        )
        if not in_server:
            outside.append(match)
    return outside


def _outside_partner_counts(outside_matches: Iterable[MatchRow]) -> dict[int, dict[int, int]]:
    by_match: dict[str, set[int]] = defaultdict(set)
    for match in outside_matches:
        by_match[match.match_uuid].add(match.user_id)
    counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for user_ids in by_match.values():
        ids = sorted(user_ids)
        for i, user_a in enumerate(ids):
            for user_b in ids[i + 1 :]:
                counts[user_a][user_b] += 1
                counts[user_b][user_a] += 1
    return {user_id: dict(partners) for user_id, partners in counts.items()}


def _outside_while_active(
    matches: Iterable[MatchRow],
    sessions: Iterable[VoiceSession],
    threshold: int = OUTSIDE_ACTIVE_THRESHOLD,
) -> dict[int, int]:
    """Count outside matches played while at least `threshold` other users were in voice.

    Only computed for one-month/action windows; all-data would be quadratic.
    """
    intervals = [(s.start, s.end, s.user_id) for s in sessions]
    counts: dict[int, int] = defaultdict(int)
    for match in matches:
        start, end = match.start, match.match_timestamp
        others: set[int] = set()
        for session_start, session_end, user_id in intervals:
            if user_id == match.user_id:
                continue
            if session_start <= end and session_end >= start:
                others.add(user_id)
        if len(others) >= threshold:
            counts[match.user_id] += 1
    return dict(counts)


def _classify(user: UserMetrics) -> str:
    if user.match_rows == 0 and user.voice_seconds == 0:
        return "inactive"
    if user.match_rows == 0 and user.voice_hours >= 4:
        return "voice_only"
    if user.match_rows >= 5 and user.voice_hours < 1:
        return "match_only"
    if user.in_rows >= 5 and user.in_percent >= 60:
        return "core_in_server"
    if user.in_rows >= 3 and user.out_rows >= 3:
        return "mixed"
    if user.out_rows >= 5 and user.out_percent >= 60:
        return "elsewhere_heavy"
    return "mixed" if user.match_rows else "voice_only"


def _activity_timestamps(sessions: Iterable[VoiceSession], matches: Iterable[MatchRow]) -> dict[int, list[datetime]]:
    activity: dict[int, list[datetime]] = defaultdict(list)
    for session in sessions:
        activity[session.user_id].append(session.start)
    for match in matches:
        activity[match.user_id].append(match.match_timestamp)
    for user_id in activity:
        activity[user_id].sort()
    return dict(activity)


def _voice_seconds_between(intervals: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> float:
    total = 0.0
    for interval_start, interval_end in intervals:
        overlap_start = max(interval_start, start)
        overlap_end = min(interval_end, end)
        if overlap_end > overlap_start:
            total += (overlap_end - overlap_start).total_seconds()
    return total


def _data_quality(
    users: dict[int, UserInfo],
    window: ReportWindow,
    clipped_sessions: list[VoiceSession],
    window_matches: list[MatchRow],
    all_sessions: list[VoiceSession],
    all_matches: list[MatchRow],
    unmatched: list[datetime],
    open_sessions: list[datetime],
    rollback_count: int,
    snapshot_max_activity: Optional[datetime],
    snapshot_max_match: Optional[datetime],
    reference_date: date,
) -> DataQuality:
    name_counts: dict[str, int] = defaultdict(int)
    for info in users.values():
        name_counts[info.display_name] += 1
    all_voice_users = {session.user_id for session in all_sessions}
    all_match_users = {match.user_id for match in all_matches}
    stale = 0
    if snapshot_max_activity is not None:
        stale = max(0, (reference_date - snapshot_max_activity.date()).days)
    return DataQuality(
        unmatched_disconnects=sum(1 for timestamp in unmatched if window.start <= timestamp < window.end_exclusive),
        open_sessions_at_end=sum(1 for start in open_sessions if start < window.end_exclusive),
        long_sessions=sum(1 for s in clipped_sessions if s.seconds > LONG_SESSION_HOURS * 3600),
        rollback_rows_excluded=rollback_count,
        missing_duration_rows=sum(1 for m in window_matches if m.duration_ms <= 0),
        missing_timezone_users=sum(1 for u in users.values() if not u.time_zone or u.time_zone == "UTC"),
        missing_ubisoft_users=sum(1 for u in users.values() if not u.ubisoft_name),
        voice_only_users=sum(
            1 for u in users.values() if u.user_id in all_voice_users and u.user_id not in all_match_users
        ),
        match_only_users=sum(
            1 for u in users.values() if u.user_id in all_match_users and u.user_id not in all_voice_users
        ),
        duplicate_display_names=sum(1 for count in name_counts.values() if count > 1),
        snapshot_max_activity=snapshot_max_activity,
        snapshot_max_match=snapshot_max_match,
        stale_days=stale,
    )


def _build_window(
    window: ReportWindow,
    users: dict[int, UserInfo],
    all_sessions: list[VoiceSession],
    all_matches: list[MatchRow],
    global_intervals: dict[int, list[tuple[datetime, datetime]]],
    activity: dict[int, list[datetime]],
    messages_by_window: dict[str, dict[int, int]],
    rollback_counts: dict[str, int],
    unmatched: list[datetime],
    open_sessions: list[datetime],
    snapshot_max_activity: Optional[datetime],
    snapshot_max_match: Optional[datetime],
    reference_date: date,
) -> WindowMetrics:
    clipped = clip_sessions(all_sessions, window)
    window_matches = [m for m in all_matches if window.start <= m.match_timestamp < window.end_exclusive]
    user_metrics: dict[int, UserMetrics] = {
        user_id: UserMetrics(
            user_id=user_id,
            display_name=info.display_name,
            ubisoft_name=info.ubisoft_name,
            time_zone=info.time_zone,
            max_mmr=info.max_mmr,
        )
        for user_id, info in users.items()
    }
    for session in clipped:
        user = user_metrics.get(session.user_id)
        if user is None:
            continue
        user.voice_seconds += session.seconds
        user.session_count += 1
        user.session_minutes.append(session.seconds / 60.0)
        user.last_voice = max(user.last_voice, session.start) if user.last_voice else session.start
        for key, seconds in _split_hours(session, _local_zone(user.time_zone)):
            user.weekday_hour_voice[key] = user.weekday_hour_voice.get(key, 0.0) + seconds
    in_data_centers: dict[str, int] = defaultdict(int)
    out_data_centers: dict[str, int] = defaultdict(int)
    for match in window_matches:
        user = user_metrics.get(match.user_id)
        if user is None:
            continue
        user.match_rows += 1
        user.match_seconds += match.seconds
        user.last_match = max(user.last_match, match.match_timestamp) if user.last_match else match.match_timestamp
        local = match.match_timestamp.astimezone(_local_zone(user.time_zone))
        key = (local.weekday(), local.hour)
        user.weekday_hour_matches[key] = user.weekday_hour_matches.get(key, 0) + 1
        in_server = any(
            start <= match.match_timestamp and end >= match.start
            for start, end in global_intervals.get(match.user_id, [])
        )
        if in_server:
            in_data_centers[match.data_center] += 1
        else:
            out_data_centers[match.data_center] += 1
        if in_server:
            user.in_rows += 1
            user.in_seconds += match.seconds
            user.in_wins += int(match.has_win)
            user.in_rank_delta += match.points_gained
        else:
            user.out_rows += 1
            user.out_seconds += match.seconds
            user.out_wins += int(match.has_win)
            user.out_rank_delta += match.points_gained
    for user_id, uuids in _distinct_matches_by_user(window_matches).items():
        if user_id in user_metrics:
            user_metrics[user_id].distinct_matches = len(uuids)
    outside_matches = _outside_matches(window_matches, global_intervals)
    if window.key in ("previous_month", "last_28_days"):
        for user_id, count in _outside_while_active(outside_matches, clipped).items():
            if user_id in user_metrics:
                user_metrics[user_id].outside_while_active = count
    message_counts = messages_by_window.get(window.key, {})
    for user_id, count in message_counts.items():
        if user_id in user_metrics:
            user_metrics[user_id].messages = count
    for user_id, user in user_metrics.items():
        user.first_seen = activity.get(user_id, [None])[0]
        stamps = activity.get(user_id, [])
        if stamps:
            user.last_seen = stamps[-1]
        intervals = global_intervals.get(user_id, [])
        user.prior_28d_voice_seconds = _voice_seconds_between(
            intervals, window.end_exclusive - timedelta(days=28), window.end_exclusive
        )
        user.current_14d_voice_seconds = _voice_seconds_between(
            intervals, window.end_exclusive - timedelta(days=14), window.end_exclusive
        )
        user.weekly_voice_seconds = [
            _voice_seconds_between(
                intervals,
                window.end_exclusive - timedelta(days=7 * week_index),
                window.end_exclusive - timedelta(days=7 * (week_index - 1)),
            )
            / 3600.0
            for week_index in range(8, 0, -1)
        ]
        user.classification = _classify(user)
        if user.outside_while_active >= 3:
            user.flags.append("elsewhere_while_active")
        if user.match_rows >= SMALL_SAMPLE and user.out_percent >= 60:
            user.flags.append("outside_heavy")
        if user.voice_hours >= 4 and user.match_rows == 0:
            user.flags.append("voice_only")
        if user.match_rows >= SMALL_SAMPLE and user.voice_hours < 1:
            user.flags.append("match_only")
        if user.prior_28d_voice_seconds >= 2 * 3600 and user.current_14d_voice_seconds == 0:
            user.flags.append("at_risk")
    # Pair relationships and per-user partner lists.
    co_voice = _co_voice_pairs(clipped)
    co_match, co_wins = _co_match_pairs(window_matches)
    pair_keys = set(co_voice) | set(co_match)
    pairs: list[PairRelationship] = []
    for key in pair_keys:
        pairs.append(
            PairRelationship(
                user_a=key[0],
                user_b=key[1],
                co_voice_seconds=co_voice.get(key, 0.0),
                co_matches=co_match.get(key, 0),
                co_wins=co_wins.get(key, 0),
            )
        )
    pairs.sort(key=lambda p: (-p.score, p.user_a, p.user_b))
    pair_map: dict[int, list[PairRelationship]] = defaultdict(list)
    for pair in pairs:
        pair_map[pair.user_a].append(pair)
        pair_map[pair.user_b].append(pair)
    outside_partners = _outside_partner_counts(outside_matches)
    for user_id, user in user_metrics.items():
        related = pair_map.get(user_id, [])
        user.top_voice_partners = sorted(
            (
                (
                    user_metrics[pair.user_b if pair.user_a == user_id else pair.user_a].display_name,
                    pair.co_voice_seconds / 3600.0,
                )
                for pair in related
                if pair.co_voice_seconds > 0
            ),
            key=lambda item: -item[1],
        )[:8]
        user.top_match_partners = sorted(
            (
                (
                    user_metrics[pair.user_b if pair.user_a == user_id else pair.user_a].display_name,
                    pair.co_matches,
                )
                for pair in related
                if pair.co_matches > 0
            ),
            key=lambda item: -item[1],
        )[:8]
        user.top_outside_partners = sorted(
            (
                (user_metrics[partner_id].display_name, count)
                for partner_id, count in outside_partners.get(user_id, {}).items()
                if partner_id in user_metrics
            ),
            key=lambda item: -item[1],
        )[:8]
    # Aggregate metrics.
    total_voice = sum(u.voice_seconds for u in user_metrics.values())
    match_rows = sum(u.match_rows for u in user_metrics.values())
    voice_users = sum(1 for u in user_metrics.values() if u.voice_seconds > 0)
    match_users = sum(1 for u in user_metrics.values() if u.match_rows > 0)
    any_users = sum(1 for u in user_metrics.values() if u.voice_seconds > 0 or u.match_rows > 0)
    new_users = sum(
        1 for u in user_metrics.values() if u.first_seen and window.start <= u.first_seen < window.end_exclusive
    )
    returning_users = 0
    churned_users = 0
    for user_id, stamps in activity.items():
        active_in_window = any(window.start <= stamp < window.end_exclusive for stamp in stamps)
        prior = [stamp for stamp in stamps if stamp < window.start]
        if active_in_window and prior and window.start - prior[-1] >= timedelta(days=28):
            returning_users += 1
        prior_window = [
            stamp
            for stamp in stamps
            if window.end_exclusive - timedelta(days=56) <= stamp < window.end_exclusive - timedelta(days=28)
        ]
        current_window = [
            stamp for stamp in stamps if window.end_exclusive - timedelta(days=28) <= stamp < window.end_exclusive
        ]
        if prior_window and not current_window:
            churned_users += 1
    peak, peak_at, avg = _concurrency(clipped, window)
    weekday_hour_voice: dict[tuple[int, int], float] = defaultdict(float)
    weekday_hour_matches: dict[tuple[int, int], int] = defaultdict(int)
    for u in user_metrics.values():
        for key, seconds in u.weekday_hour_voice.items():
            weekday_hour_voice[key] += seconds
        for key, count in u.weekday_hour_matches.items():
            weekday_hour_matches[key] += count
    weekly_voice, weekly_matches, monthly_voice, monthly_matches = _trends(clipped, window_matches)
    session_length_counts = {label: 0 for label, _, _ in SESSION_BUCKETS}
    for u in user_metrics.values():
        for minutes in u.session_minutes:
            session_length_counts[_session_bucket(minutes)] += 1
    messages = sum(message_counts.values())
    dq = _data_quality(
        users,
        window,
        clipped,
        window_matches,
        all_sessions,
        all_matches,
        unmatched,
        open_sessions,
        rollback_counts.get(window.key, 0),
        snapshot_max_activity,
        snapshot_max_match,
        reference_date,
    )
    return WindowMetrics(
        window=window,
        users=sorted(user_metrics.values(), key=lambda u: (-u.voice_hours, -u.match_rows, u.display_name.lower())),
        data_quality=dq,
        total_voice_seconds=total_voice,
        session_count=sum(u.session_count for u in user_metrics.values()),
        match_rows=match_rows,
        distinct_matches=len({m.match_uuid for m in window_matches}),
        match_seconds=sum(u.match_seconds for u in user_metrics.values()),
        in_rows=sum(u.in_rows for u in user_metrics.values()),
        out_rows=sum(u.out_rows for u in user_metrics.values()),
        in_seconds=sum(u.in_seconds for u in user_metrics.values()),
        out_seconds=sum(u.out_seconds for u in user_metrics.values()),
        voice_users=voice_users,
        match_users=match_users,
        any_users=any_users,
        new_users=new_users,
        returning_users=returning_users,
        churned_users=churned_users,
        peak_concurrent=peak,
        peak_concurrent_at=peak_at,
        avg_concurrent=avg,
        unique_users_per_day=_unique_users_per_day(clipped),
        messages=messages,
        message_users=len(message_counts),
        weekday_hour_voice=dict(weekday_hour_voice),
        weekday_hour_matches=dict(weekday_hour_matches),
        weekly_voice=weekly_voice,
        weekly_matches=weekly_matches,
        monthly_voice=monthly_voice,
        monthly_matches=monthly_matches,
        session_length_counts=session_length_counts,
        in_data_centers=dict(in_data_centers),
        out_data_centers=dict(out_data_centers),
        pairs=pairs,
    )


def _distinct_matches_by_user(matches: Iterable[MatchRow]) -> dict[int, set[str]]:
    by_user: dict[int, set[str]] = defaultdict(set)
    for match in matches:
        by_user[match.user_id].add(match.match_uuid)
    return dict(by_user)


def _build_network(window: WindowMetrics, users: dict[int, UserInfo]) -> tuple[list[NetworkNode], list[NetworkEdge]]:
    edge_pairs = [
        pair
        for pair in window.pairs
        if pair.co_voice_seconds >= MIN_EDGE_CO_VOICE_SECONDS or pair.co_matches >= MIN_EDGE_CO_MATCHES
    ]
    if not edge_pairs:
        return [], []
    try:
        import networkx as nx
    except ImportError:
        return [], []
    graph: Any = nx.Graph()
    for pair in edge_pairs:
        graph.add_edge(pair.user_a, pair.user_b, weight=pair.score)
    communities: dict[int, int] = {}
    try:
        groups = nx.community.greedy_modularity_communities(graph)
        for index, group in enumerate(groups):
            for user_id in group:
                communities[int(user_id)] = index
    except Exception:
        communities = {}
    degree = {int(node): int(value) for node, value in graph.degree()}
    try:
        betweenness = nx.betweenness_centrality(graph, weight="weight") if graph.number_of_nodes() > 2 else {}
    except Exception:
        betweenness = {}

    def _voice_hours(user_id: Any) -> float:
        metric = window.user(int(user_id))
        return metric.voice_hours if metric is not None else 0.0

    ranked_users = sorted(
        graph.nodes,
        key=lambda user_id: (-_voice_hours(user_id), -(degree.get(int(user_id), 0))),
    )[:NETWORK_NODE_LIMIT]
    kept = set(ranked_users)
    nodes: list[NetworkNode] = []
    for user_id in ranked_users:
        user = window.user(int(user_id))
        info = users.get(int(user_id))
        nodes.append(
            NetworkNode(
                user_id=int(user_id),
                label=(user.display_name if user else (info.display_name if info else str(user_id))),
                voice_hours=user.voice_hours if user else 0.0,
                classification=user.classification if user else "inactive",
                degree=int(degree.get(user_id, 0)),
                betweenness=float(betweenness.get(user_id, 0.0)),
                community=communities.get(int(user_id), 0),
            )
        )
    edges: list[NetworkEdge] = []
    for pair in edge_pairs:
        if pair.user_a not in kept or pair.user_b not in kept:
            continue
        user_a = window.user(pair.user_a)
        user_b = window.user(pair.user_b)
        edges.append(
            NetworkEdge(
                user_a=pair.user_a,
                user_b=pair.user_b,
                label_a=user_a.display_name if user_a else str(pair.user_a),
                label_b=user_b.display_name if user_b else str(pair.user_b),
                co_voice_hours=pair.co_voice_seconds / 3600.0,
                co_matches=pair.co_matches,
                score=pair.score,
            )
        )
    edges.sort(key=lambda edge: -edge.score)
    return nodes, edges[:NETWORK_EDGE_LIMIT]


def build_report(
    database_path: str | Path,
    reference_date: date,
    include_ai: bool = True,
    window_keys: Optional[Iterable[str]] = None,
) -> ReportData:
    """Collect every deterministic metric and action for one report run."""
    from deps.reporting.insights import build_actions, build_narrative, deterministic_narrative

    conn = _connect(database_path)
    try:
        snapshot_max_activity, snapshot_max_match, min_day = load_snapshot_bounds(conn)
        if min_day is None:
            raise ValueError("The database has no activity or match data.")
        report_month, windows = get_report_windows(reference_date, min_day)
        if window_keys:
            allowed = set(window_keys)
            windows = [window for window in windows if window.key in allowed]
        users = load_user_infos(conn)
        end_exclusive = windows[0].end_exclusive
        all_sessions, unmatched, open_sessions = load_sessions(conn, end_exclusive)
        all_matches = load_matches(conn, end_exclusive)
        messages_by_window = {window.key: load_messages(conn, window)[2] for window in windows}
        rollback_counts = load_rollback_counts(conn, windows)
        global_intervals = intervals_by_user(all_sessions)
        activity = _activity_timestamps(all_sessions, all_matches)
        window_metrics = [
            _build_window(
                window,
                users,
                all_sessions,
                all_matches,
                global_intervals,
                activity,
                messages_by_window,
                rollback_counts,
                unmatched,
                open_sessions,
                snapshot_max_activity,
                snapshot_max_match,
                reference_date,
            )
            for window in windows
        ]
        primary = next(
            (window for window in window_metrics if window.window.key == "previous_month"), window_metrics[0]
        )
        actions = build_actions(primary, users)
        fact_values = build_narrative_facts(primary)
        narrative, source = deterministic_narrative(primary), "deterministic"
        if include_ai:
            narrative, source = build_narrative(primary, fact_values, fallback=narrative)
        nodes, edges = _build_network(primary, users)
        timezone_counts: dict[str, int] = defaultdict(int)
        for info in users.values():
            timezone_counts[info.time_zone] += 1
        return ReportData(
            report_month=report_month,
            reference_date=reference_date,
            generated_at=datetime.now(timezone.utc),
            database_path=str(database_path),
            windows=window_metrics,
            primary=primary,
            actions=actions,
            narrative=narrative,
            narrative_source=source,
            narrative_facts=fact_values,
            users=users,
            network_nodes=nodes,
            network_edges=edges,
            time_zone_distribution=dict(timezone_counts),
        )
    finally:
        conn.close()


def build_narrative_facts(window: WindowMetrics) -> dict[str, str]:
    """Flatten the primary window into fact ids the narrative may cite."""
    facts = {
        "pulse.voice_users": str(window.voice_users),
        "pulse.match_users": str(window.match_users),
        "pulse.voice_hours": f"{window.total_voice_hours:.1f}",
        "pulse.match_rows": str(window.match_rows),
        "pulse.distinct_matches": str(window.distinct_matches),
        "pulse.match_hours": f"{window.match_hours:.1f}",
        "pulse.new_users": str(window.new_users),
        "pulse.returning_users": str(window.returning_users),
        "pulse.churned_users": str(window.churned_users),
        "pulse.peak_concurrent": str(window.peak_concurrent),
        "pulse.messages": str(window.messages),
        "split.in_rows": str(window.in_rows),
        "split.out_rows": str(window.out_rows),
        "split.in_percent": f"{window.in_percent:.1f}",
        "split.out_percent": f"{window.out_percent:.1f}",
        "split.in_hours": f"{window.in_seconds / 3600.0:.1f}",
        "split.out_hours": f"{window.out_seconds / 3600.0:.1f}",
    }
    top_voice = [user for user in window.users if user.voice_hours > 0][:3]
    for index, user in enumerate(top_voice, start=1):
        facts[f"people.top_voice_{index}"] = f"{user.display_name}: {user.voice_hours:.1f}h voice"
    top_outside = sorted([user for user in window.users if user.out_rows > 0], key=lambda user: -user.out_rows)[:3]
    for index, user in enumerate(top_outside, start=1):
        facts[f"people.top_outside_{index}"] = f"{user.display_name}: {user.out_rows} outside rows"
    at_risk = [user for user in window.users if "at_risk" in user.flags][:3]
    for index, user in enumerate(at_risk, start=1):
        facts[f"people.at_risk_{index}"] = (
            f"{user.display_name}: last seen {user.last_seen.date().isoformat() if user.last_seen else 'unknown'}"
        )
    return facts
