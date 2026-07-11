"""Monthly analytics PDF report generation."""

from __future__ import annotations

import asyncio
import bisect
import io
import textwrap
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import discord
import matplotlib
import networkx as nx

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from deps import monthly_report_style as style
from deps.ai.ai_functions import BotAISingleton
from deps.analytic_data_access import (
    data_access_fetch_user_outside_ranked_match_partners,
    data_access_fetch_user_ranked_match_server_split_by_week,
)
from deps.data_access import (
    data_access_get_analytics_report_text_channel_id,
    data_access_get_channel,
    data_access_get_monthly_analytics_report_sent,
    data_access_set_monthly_analytics_report_sent,
)
from deps.log import print_error_log, print_log, print_warning_log
from deps.system_database import database_manager


REPORT_TOP_USERS = 20
REPORT_PARTNER_TOP = 5
LOW_SAMPLE_RANKED_ROWS = 5


@dataclass(frozen=True)
class ReportWindow:
    """One report time window."""

    key: str
    title: str
    start: datetime
    end_exclusive: datetime

    @property
    def start_date(self) -> date:
        return self.start.date()

    @property
    def end_date(self) -> date:
        return self.end_exclusive.date()

    def label(self) -> str:
        return f"{self.start_date.isoformat()} to {(self.end_exclusive.date()).isoformat()} (exclusive)"


@dataclass(frozen=True)
class UserWindowMetrics:
    """Per-user metrics for a report window."""

    user_id: int
    display_name: str
    voice_hours: float
    ranked_matches: int
    in_server_matches: int
    outside_server_matches: int
    outside_partners: list[tuple[str, int, int, float]]

    @property
    def classified_ranked_matches(self) -> int:
        return self.in_server_matches + self.outside_server_matches

    @property
    def in_server_percent(self) -> float:
        return _percent(self.in_server_matches, self.classified_ranked_matches)

    @property
    def outside_server_percent(self) -> float:
        return _percent(self.outside_server_matches, self.classified_ranked_matches)

    @property
    def outside_partner_match_count(self) -> int:
        return sum(int(partner[1] or 0) for partner in self.outside_partners)


@dataclass(frozen=True)
class DataQualityMetrics:
    """Counts that make the report's assumptions and gaps explicit."""

    voice_sessions: int
    unmatched_disconnects: int
    open_sessions_at_window_end: int
    suspicious_voice_sessions: int
    ranked_rows_without_voice_context: int
    rollback_ranked_rows_excluded: int


@dataclass(frozen=True)
class WindowReportData:
    """Collected deterministic data for one report window."""

    window: ReportWindow
    total_voice_hours: float
    active_users: int
    ranked_match_rows: int
    distinct_ranked_matches: int
    data_quality: DataQualityMetrics
    top_users: list[UserWindowMetrics]


@dataclass(frozen=True)
class MonthlyReportData:
    """All deterministic report data."""

    report_month: str
    generated_at: datetime
    windows: list[WindowReportData]


@dataclass(frozen=True)
class VoiceSession:
    """A paired voice session clipped to a report window."""

    user_id: int
    channel_id: int
    start: datetime
    end: datetime

    @property
    def seconds(self) -> float:
        return max(0.0, (self.end - self.start).total_seconds())


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _as_utc_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def get_monthly_report_windows(reference_day: Optional[date] = None) -> tuple[str, list[ReportWindow]]:
    """
    Return the four monthly report windows for the first day of the current report run.

    The report month is always the previous complete calendar month.
    """
    if reference_day is None:
        reference_day = datetime.now(timezone.utc).date()
    current_month_start = _month_start(reference_day)
    previous_month_start = _add_months(current_month_start, -1)
    previous_three_months_start = _add_months(current_month_start, -3)
    ytd_start = date(previous_month_start.year, 1, 1)
    all_data_start = _fetch_all_data_start_date() or previous_month_start
    end_exclusive = _as_utc_start(current_month_start)
    report_month = previous_month_start.strftime("%Y-%m")
    return (
        report_month,
        [
            ReportWindow(
                key="previous_month",
                title="Previous Month",
                start=_as_utc_start(previous_month_start),
                end_exclusive=end_exclusive,
            ),
            ReportWindow(
                key="previous_three_months",
                title="Previous 3 Complete Months",
                start=_as_utc_start(previous_three_months_start),
                end_exclusive=end_exclusive,
            ),
            ReportWindow(
                key="year_to_date",
                title="Year to Date",
                start=_as_utc_start(ytd_start),
                end_exclusive=end_exclusive,
            ),
            ReportWindow(
                key="all_data",
                title="All Tracked Data",
                start=_as_utc_start(all_data_start),
                end_exclusive=end_exclusive,
            ),
        ],
    )


def _fetch_all_data_start_date() -> Optional[date]:
    row = (
        database_manager.get_cursor()
        .execute(
            """
        SELECT MIN(ts)
        FROM (
            SELECT MIN(timestamp) AS ts FROM user_activity
            UNION ALL
            SELECT MIN(match_timestamp) AS ts FROM user_full_match_info
        )
        WHERE ts IS NOT NULL;
        """
        )
        .fetchone()
    )
    if row is None or row[0] is None:
        return None
    return datetime.fromisoformat(str(row[0]).replace(" ", "T")).date()


def _execute(query: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
    return database_manager.get_cursor().execute(query, params).fetchall()


def _clean_text(value: Any) -> str:
    """Normalize stylized Discord names into PDF-friendly text."""
    normalized = unicodedata.normalize("NFKD", str(value))
    return "".join(ch for ch in normalized if ch.isprintable())


def _percent(part: int | float, whole: int | float) -> float:
    if whole <= 0:
        return 0.0
    return float(part) * 100.0 / float(whole)


def _format_percent(part: int | float, whole: int | float, digits: int = 0) -> str:
    return f"{_percent(part, whole):.{digits}f}%"


def _window_params(window: ReportWindow) -> dict[str, str]:
    return {"start": window.start.isoformat(), "end": window.end_exclusive.isoformat()}


def _merged_voice_intervals_by_user(sessions: list[VoiceSession]) -> dict[int, list[tuple[datetime, datetime]]]:
    """Merge each user's voice sessions into non-overlapping, sorted intervals."""
    intervals_by_user: dict[int, list[tuple[datetime, datetime]]] = defaultdict(list)
    for session in sessions:
        intervals_by_user[session.user_id].append((session.start, session.end))
    merged_by_user: dict[int, list[tuple[datetime, datetime]]] = {}
    for user_id, intervals in intervals_by_user.items():
        intervals.sort()
        merged: list[tuple[datetime, datetime]] = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        merged_by_user[user_id] = merged
    return merged_by_user


def _is_during_voice_session(intervals: list[tuple[datetime, datetime]], timestamp: datetime) -> bool:
    """Check whether a timestamp falls inside one of the user's merged voice intervals."""
    index = bisect.bisect_right(intervals, timestamp, key=lambda interval: interval[0]) - 1
    return index >= 0 and intervals[index][1] >= timestamp


def _fetch_window_ranked_rows(window: ReportWindow) -> list[tuple[int, datetime, bool]]:
    """Fetch (user_id, match_timestamp, has_win) for ranked, non-rollback rows in the window."""
    return [
        (int(row[0]), _parse_db_datetime(str(row[1])), int(row[2] or 0) == 1)
        for row in _execute(
            """
            SELECT user_id, match_timestamp, has_win
            FROM user_full_match_info
            WHERE julianday(match_timestamp) >= julianday(:start)
              AND julianday(match_timestamp) < julianday(:end)
              AND LOWER(session_type) = 'ranked'
              AND is_rollback = 0;
            """,
            _window_params(window),
        )
    ]


def _fetch_active_user_count(window: ReportWindow) -> int:
    row = (
        database_manager.get_cursor()
        .execute(
            """
        SELECT COUNT(DISTINCT user_id)
        FROM user_activity
        WHERE julianday(timestamp) >= julianday(:start)
          AND julianday(timestamp) < julianday(:end);
        """,
            _window_params(window),
        )
        .fetchone()
    )
    return int(row[0] or 0)


def _fetch_ranked_match_counts(window: ReportWindow) -> tuple[int, int]:
    row = (
        database_manager.get_cursor()
        .execute(
            """
        SELECT COUNT(id), COUNT(DISTINCT match_uuid)
        FROM user_full_match_info
        WHERE julianday(match_timestamp) >= julianday(:start)
          AND julianday(match_timestamp) < julianday(:end)
          AND LOWER(session_type) = 'ranked'
          AND is_rollback = 0;
        """,
            _window_params(window),
        )
        .fetchone()
    )
    return int(row[0] or 0), int(row[1] or 0)


def _parse_db_datetime(raw: str) -> datetime:
    parsed = datetime.fromisoformat(str(raw).replace(" ", "T"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _fetch_voice_sessions(window: ReportWindow) -> list[VoiceSession]:
    rows = _execute(
        """
        SELECT user_id, channel_id, event, timestamp
        FROM user_activity
        WHERE julianday(timestamp) < julianday(:end)
        ORDER BY user_id, channel_id, julianday(timestamp), id;
        """,
        _window_params(window),
    )
    open_sessions: dict[tuple[int, int], datetime] = {}
    sessions: list[VoiceSession] = []
    for user_id_raw, channel_id_raw, event, timestamp_raw in rows:
        user_id = int(user_id_raw)
        channel_id = int(channel_id_raw)
        timestamp = _parse_db_datetime(str(timestamp_raw))
        key = (user_id, channel_id)
        if event == "connect":
            open_sessions[key] = timestamp
            continue
        if event != "disconnect" or key not in open_sessions:
            continue
        start = open_sessions.pop(key)
        end = timestamp
        if end <= window.start or start >= window.end_exclusive:
            continue
        overlap_start = max(start, window.start)
        overlap_end = min(end, window.end_exclusive)
        if overlap_end > overlap_start:
            sessions.append(VoiceSession(user_id=user_id, channel_id=channel_id, start=overlap_start, end=overlap_end))
    return sessions


def _fetch_data_quality_metrics(
    window: ReportWindow, sessions: Optional[list[VoiceSession]] = None
) -> DataQualityMetrics:
    if sessions is None:
        sessions = _fetch_voice_sessions(window)

    rows = _execute(
        """
        SELECT user_id, channel_id, event, timestamp
        FROM user_activity
        WHERE julianday(timestamp) < julianday(:end)
        ORDER BY user_id, channel_id, julianday(timestamp), id;
        """,
        _window_params(window),
    )
    open_sessions: dict[tuple[int, int], datetime] = {}
    unmatched_disconnects = 0
    for user_id_raw, channel_id_raw, event, timestamp_raw in rows:
        key = (int(user_id_raw), int(channel_id_raw))
        timestamp = _parse_db_datetime(str(timestamp_raw))
        if event == "connect":
            open_sessions[key] = timestamp
            continue
        if event != "disconnect":
            continue
        if key not in open_sessions:
            if window.start <= timestamp < window.end_exclusive:
                unmatched_disconnects += 1
            continue
        open_sessions.pop(key)

    open_sessions_at_window_end = sum(1 for opened_at in open_sessions.values() if opened_at < window.end_exclusive)
    suspicious_voice_sessions = sum(1 for session in sessions if session.seconds > 12 * 3600)
    intervals_by_user = _merged_voice_intervals_by_user(sessions)
    ranked_rows_without_voice_context = sum(
        1
        for user_id, match_timestamp, _ in _fetch_window_ranked_rows(window)
        if not _is_during_voice_session(intervals_by_user.get(user_id, []), match_timestamp)
    )
    rollback_ranked_rows_excluded = int(
        _execute(
            """
            SELECT COUNT(*)
            FROM user_full_match_info
            WHERE julianday(match_timestamp) >= julianday(:start)
              AND julianday(match_timestamp) < julianday(:end)
              AND LOWER(session_type) = 'ranked'
              AND is_rollback = 1;
            """,
            _window_params(window),
        )[0][0]
        or 0
    )
    return DataQualityMetrics(
        voice_sessions=len(sessions),
        unmatched_disconnects=unmatched_disconnects,
        open_sessions_at_window_end=open_sessions_at_window_end,
        suspicious_voice_sessions=suspicious_voice_sessions,
        ranked_rows_without_voice_context=ranked_rows_without_voice_context,
        rollback_ranked_rows_excluded=rollback_ranked_rows_excluded,
    )


def _fetch_ranked_counts_by_user(window: ReportWindow) -> dict[int, int]:
    return {
        int(row[0]): int(row[1] or 0)
        for row in _execute(
            """
            SELECT user_id, COUNT(id)
            FROM user_full_match_info
            WHERE julianday(match_timestamp) >= julianday(:start)
              AND julianday(match_timestamp) < julianday(:end)
              AND LOWER(session_type) = 'ranked'
              AND is_rollback = 0
            GROUP BY user_id;
            """,
            _window_params(window),
        )
    }


def _fetch_user_display_names() -> dict[int, str]:
    return {int(row[0]): _clean_text(row[1]) for row in _execute("SELECT id, display_name FROM user_info;", {})}


def _top_active_users_from_metrics(
    voice_seconds_by_user: dict[int, float],
    ranked_counts_by_user: dict[int, int],
    display_names: dict[int, str],
    top_n: int,
) -> list[tuple[int, str, float, int]]:
    rows = [
        (
            user_id,
            display_names.get(user_id, str(user_id)),
            seconds,
            ranked_counts_by_user.get(user_id, 0),
        )
        for user_id, seconds in voice_seconds_by_user.items()
        if seconds > 0
    ]
    rows.sort(key=lambda row: (-row[2], -row[3], row[1].lower()))
    return rows[:top_n]


def _compute_pair_overlap_hours(
    sessions: list[VoiceSession], display_names: dict[int, str]
) -> list[tuple[str, str, float]]:
    """Compute same-channel overlap hours for user pairs."""
    sessions_by_channel: dict[int, list[VoiceSession]] = defaultdict(list)
    for session in sessions:
        sessions_by_channel[session.channel_id].append(session)

    pair_seconds: dict[tuple[int, int], float] = defaultdict(float)
    for channel_sessions in sessions_by_channel.values():
        channel_sessions.sort(key=lambda item: item.start)
        for index, left in enumerate(channel_sessions):
            for right in channel_sessions[index + 1 :]:
                if right.start >= left.end:
                    break
                if left.user_id == right.user_id:
                    continue
                overlap = (min(left.end, right.end) - max(left.start, right.start)).total_seconds()
                if overlap <= 0:
                    continue
                pair = (min(left.user_id, right.user_id), max(left.user_id, right.user_id))
                pair_seconds[pair] += overlap

    rows = [
        (display_names.get(user_a, str(user_a)), display_names.get(user_b, str(user_b)), seconds / 3600.0)
        for (user_a, user_b), seconds in pair_seconds.items()
    ]
    rows.sort(key=lambda row: row[2], reverse=True)
    return rows


def _fetch_unique_users_per_day(window: ReportWindow) -> list[tuple[str, int]]:
    return [
        (str(row[0]), int(row[1]))
        for row in _execute(
            """
            SELECT date(timestamp), COUNT(DISTINCT user_id)
            FROM user_activity
            WHERE julianday(timestamp) >= julianday(:start)
              AND julianday(timestamp) < julianday(:end)
            GROUP BY date(timestamp)
            ORDER BY date(timestamp);
            """,
            _window_params(window),
        )
    ]


def _fetch_last_activity_by_user(
    window: ReportWindow, display_names: dict[int, str], limit: int = 30
) -> list[tuple[str, str]]:
    rows = _execute(
        """
        SELECT user_info.id, user_info.display_name, MAX(user_activity.timestamp) AS last_seen
        FROM user_info
        LEFT JOIN user_activity ON user_activity.user_id = user_info.id
        GROUP BY user_info.id, user_info.display_name
        HAVING last_seen IS NOT NULL AND julianday(last_seen) < julianday(:end)
        ORDER BY julianday(last_seen) ASC
        LIMIT :limit;
        """,
        {"end": window.end_exclusive.isoformat(), "limit": limit},
    )
    return [(display_names.get(int(row[0]), _clean_text(row[1])), str(row[2])) for row in rows]


def _voice_hours_by_month_and_user(
    sessions: list[VoiceSession], top_user_ids: list[int], display_names: dict[int, str]
) -> tuple[list[str], dict[str, list[float]]]:
    months = sorted({session.start.strftime("%Y-%m") for session in sessions})
    values: dict[str, list[float]] = {
        display_names.get(user_id, str(user_id)): [0.0 for _ in months] for user_id in top_user_ids
    }
    month_index = {month: index for index, month in enumerate(months)}
    for session in sessions:
        if session.user_id not in top_user_ids:
            continue
        name = display_names.get(session.user_id, str(session.user_id))
        values[name][month_index[session.start.strftime("%Y-%m")]] += session.seconds / 3600.0
    return months, values


def _weekday_minutes_by_user(
    sessions: list[VoiceSession], top_user_ids: list[int], display_names: dict[int, str]
) -> tuple[list[str], np.ndarray]:
    matrix = np.zeros((len(top_user_ids), 7))
    user_index = {user_id: index for index, user_id in enumerate(top_user_ids)}
    for session in sessions:
        if session.user_id not in user_index:
            continue
        matrix[user_index[session.user_id], session.start.weekday()] += session.seconds / 60.0
    return [display_names.get(user_id, str(user_id)) for user_id in top_user_ids], matrix


def _weekly_voice_hours_by_user(
    sessions: list[VoiceSession], top_user_ids: list[int], display_names: dict[int, str]
) -> tuple[list[str], dict[str, list[float]]]:
    weeks = sorted(
        {f"{session.start.isocalendar().year}-W{session.start.isocalendar().week:02d}" for session in sessions}
    )
    values: dict[str, list[float]] = {
        display_names.get(user_id, str(user_id)): [0.0 for _ in weeks] for user_id in top_user_ids
    }
    week_index = {week: index for index, week in enumerate(weeks)}
    for session in sessions:
        if session.user_id not in top_user_ids:
            continue
        week = f"{session.start.isocalendar().year}-W{session.start.isocalendar().week:02d}"
        values[display_names.get(session.user_id, str(session.user_id))][week_index[week]] += session.seconds / 3600.0
    return weeks, values


def _fetch_match_server_rate_rows(
    window: ReportWindow, sessions: list[VoiceSession], limit: int = 60
) -> list[tuple[str, int, int, float, float, float]]:
    """Per-user ranked totals with in-server/outside split and win rates for the window."""
    intervals_by_user = _merged_voice_intervals_by_user(sessions)
    totals: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # total, wins, in_server, in_server_wins
    for user_id, match_timestamp, has_win in _fetch_window_ranked_rows(window):
        counters = totals[user_id]
        counters[0] += 1
        counters[1] += 1 if has_win else 0
        if _is_during_voice_session(intervals_by_user.get(user_id, []), match_timestamp):
            counters[2] += 1
            counters[3] += 1 if has_win else 0
    display_names = _fetch_user_display_names()
    rows = [
        (
            display_names.get(user_id, str(user_id)),
            total,
            in_server,
            round(_percent(in_server_wins, in_server), 2),
            round(_percent(wins - in_server_wins, total - in_server), 2),
            round(_percent(in_server, total), 2),
        )
        for user_id, (total, wins, in_server, in_server_wins) in totals.items()
    ]
    rows.sort(key=lambda row: (-row[5], -row[1]))
    return rows[:limit]


def collect_monthly_report_data(
    reference_day: Optional[date] = None,
    top_n: int = REPORT_TOP_USERS,
    window_keys: Optional[Iterable[str]] = None,
) -> MonthlyReportData:
    """Collect deterministic data used by the monthly report."""
    report_month, windows = get_monthly_report_windows(reference_day)
    if window_keys is not None:
        allowed_keys = set(window_keys)
        windows = [window for window in windows if window.key in allowed_keys]
    window_data: list[WindowReportData] = []
    for window in windows:
        sessions = _fetch_voice_sessions(window)
        voice_seconds_by_user: dict[int, float] = {}
        for session in sessions:
            voice_seconds_by_user[session.user_id] = voice_seconds_by_user.get(session.user_id, 0.0) + session.seconds
        ranked_counts_by_user = _fetch_ranked_counts_by_user(window)
        display_names = _fetch_user_display_names()
        top_users: list[UserWindowMetrics] = []
        for user_id, display_name, voice_seconds, ranked_matches in _top_active_users_from_metrics(
            voice_seconds_by_user,
            ranked_counts_by_user,
            display_names,
            top_n,
        ):
            split_rows = data_access_fetch_user_ranked_match_server_split_by_week(
                user_id, window.start, window.end_exclusive
            )
            in_server = sum(int(row[1] or 0) for row in split_rows)
            outside = sum(int(row[2] or 0) for row in split_rows)
            partners = data_access_fetch_user_outside_ranked_match_partners(
                user_id, window.start, window.end_exclusive, REPORT_PARTNER_TOP
            )
            partners = [(_clean_text(row[0]), row[1], row[2], row[3]) for row in partners]
            top_users.append(
                UserWindowMetrics(
                    user_id=user_id,
                    display_name=display_name,
                    voice_hours=voice_seconds / 3600.0,
                    ranked_matches=ranked_matches,
                    in_server_matches=in_server,
                    outside_server_matches=outside,
                    outside_partners=partners,
                )
            )
        ranked_rows, distinct_ranked = _fetch_ranked_match_counts(window)
        window_data.append(
            WindowReportData(
                window=window,
                total_voice_hours=sum(voice_seconds_by_user.values()) / 3600.0,
                active_users=_fetch_active_user_count(window),
                ranked_match_rows=ranked_rows,
                distinct_ranked_matches=distinct_ranked,
                data_quality=_fetch_data_quality_metrics(window, sessions),
                top_users=top_users,
            )
        )
    return MonthlyReportData(
        report_month=report_month,
        generated_at=datetime.now(timezone.utc),
        windows=window_data,
    )


class _ReportCanvas:
    """Wraps PdfPages with page numbering, section context, and TOC collection."""

    def __init__(self, pdf: PdfPages, report_month: str, total_pages: Optional[int] = None) -> None:
        self.pdf = pdf
        self.report_month = report_month
        self.total_pages = total_pages
        self.page_number = 0
        self.section_title = ""
        self.toc_entries: list[style.TocEntry] = []

    def begin_section(self, title: str) -> None:
        """Set the section name shown in the header band of subsequent pages."""
        self.section_title = title

    def add_toc_entry(self, title: str, level: int = 0) -> None:
        """Record a TOC entry pointing at the next page to be saved."""
        self.toc_entries.append(style.TocEntry(title=title, level=level, page_number=self.page_number + 1))

    def save_content_page(self, fig: Figure, page_title: str, subtitle: str = "") -> None:
        """Apply the page chrome, write the page, and close the figure."""
        self.page_number += 1
        style.apply_page_chrome(
            fig,
            page_title=page_title,
            section_title=self.section_title,
            page_number=self.page_number,
            report_month=self.report_month,
            total_pages=self.total_pages,
            subtitle=subtitle,
        )
        self.pdf.savefig(fig)
        plt.close(fig)

    def save_full_bleed_page(self, fig: Figure) -> None:
        """Write a chrome-free page such as the cover or a section divider."""
        self.page_number += 1
        self.pdf.savefig(fig)
        plt.close(fig)


def _draw_text_line(ax: Any, y: float, line: str) -> float:
    """Draw one styled report text line and return the next baseline position."""
    if line == "":
        return y - 0.020
    if line.startswith("- "):
        ax.text(0.012, y, "▪", fontsize=8, va="top", color=style.COLOR_ORANGE)
        ax.text(0.032, y, line[2:], fontsize=9, va="top", color=style.COLOR_TEXT)
        return y - 0.034
    if line.startswith("  "):
        ax.text(0.032, y, line.strip(), fontsize=8.5, va="top", color=style.COLOR_MUTED)
        return y - 0.032
    if line.endswith(":"):
        ax.text(0.0, y, line, fontsize=10.5, va="top", color=style.COLOR_NAVY, fontweight="bold")
        return y - 0.042
    ax.text(0.0, y, line, fontsize=9, va="top", color=style.COLOR_TEXT)
    return y - 0.034


def _save_text_page(canvas: _ReportCanvas, title: str, lines: Iterable[str], subtitle: str = "") -> None:
    wrapped_lines: list[str] = []
    for line in lines:
        if line == "":
            wrapped_lines.append("")
            continue
        text = str(line)
        indent = "  " if text.startswith(("- ", "  ")) else ""
        wrapped_lines.extend(textwrap.wrap(text, width=116, subsequent_indent=indent) or [""])

    page_index = 1
    line_index = 0
    while line_index < len(wrapped_lines) or page_index == 1:
        page_title = title if page_index == 1 else f"{title} (continued)"
        fig = style.new_page_figure()
        ax = style.blank_axes(fig)
        y = 0.98
        while line_index < len(wrapped_lines) and y > 0.02:
            y = _draw_text_line(ax, y, wrapped_lines[line_index])
            line_index += 1
        canvas.save_content_page(fig, page_title, subtitle)
        page_index += 1
        if line_index >= len(wrapped_lines):
            break


def _save_table_page(
    canvas: _ReportCanvas,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    subtitle: str = "",
) -> None:
    fig = style.new_page_figure()
    ax = style.blank_axes(fig)
    if not rows:
        style.draw_empty_message(ax)
    else:
        style.style_table(ax, columns, rows)
    canvas.save_content_page(fig, title, subtitle)


def _save_bar_page(
    canvas: _ReportCanvas,
    title: str,
    labels: list[str],
    values: list[float],
    xlabel: str,
    subtitle: str = "",
    value_fmt: str = "{:.0f}",
) -> None:
    fig = style.new_page_figure()
    ax = style.content_axes(fig, (0.24, 0.12, 0.70, 0.74))
    if not labels:
        style.draw_empty_message(ax)
    else:
        sorted_rows = sorted(zip(labels, values), key=lambda row: row[1], reverse=True)
        labels = [row[0] for row in sorted_rows]
        values = [row[1] for row in sorted_rows]
        y_pos = np.arange(len(labels))
        ax.barh(y_pos, values, color=style.COLOR_SERIES_PRIMARY, height=0.62)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=7.5 if len(labels) <= 25 else 6.0)
        ax.set_xlabel(xlabel)
        ax.invert_yaxis()
        style.style_axes(ax, grid_axis="x")
        style.label_bar_values(ax, list(y_pos), values, value_fmt)
    canvas.save_content_page(fig, title, subtitle)


def _save_server_split_page(canvas: _ReportCanvas, data: WindowReportData) -> None:
    sorted_users = sorted(
        data.top_users,
        key=lambda user: (user.in_server_matches + user.outside_server_matches, user.ranked_matches),
        reverse=True,
    )
    users = [user.display_name for user in sorted_users]
    in_server = [user.in_server_matches for user in sorted_users]
    outside = [user.outside_server_matches for user in sorted_users]
    fig = style.new_page_figure()
    ax = style.content_axes(fig, (0.24, 0.12, 0.70, 0.74))
    if not users:
        style.draw_empty_message(ax)
    else:
        y_pos = np.arange(len(users))
        ax.barh(y_pos, in_server, label="In Server Voice", color=style.COLOR_IN_SERVER, height=0.62)
        ax.barh(y_pos, outside, left=in_server, label="Outside Server Voice", color=style.COLOR_OUTSIDE, height=0.62)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(users, fontsize=7.5)
        ax.set_xlabel("Ranked Match Rows")
        ax.legend(fontsize=8, frameon=False, loc="lower right")
        ax.invert_yaxis()
        style.style_axes(ax, grid_axis="x")
    canvas.save_content_page(fig, "Ranked Matches: In Server vs Outside", data.window.label())


def _save_network_page(
    canvas: _ReportCanvas,
    title: str,
    pair_rows: list[tuple[str, str, float]],
    subtitle: str,
    dim_3d: bool = False,
) -> None:
    graph: "nx.Graph[str]" = nx.Graph()
    for user_a, user_b, hours in pair_rows[:80]:
        if hours <= 0:
            continue
        graph.add_edge(user_a, user_b, weight=hours)
    if graph.number_of_edges() == 0:
        _save_text_page(canvas, title, ["No relationship data available for this window."], subtitle)
        return
    fig = style.new_page_figure()
    edge_weights = {(u, v): float(data.get("weight", 0.0)) for u, v, data in graph.edges(data=True)}
    max_weight = max(edge_weights.values()) if edge_weights else 1.0
    if dim_3d:
        ax3d: Any = fig.add_axes(style.CONTENT_RECT, projection="3d")
        pos = nx.spring_layout(graph, dim=3, seed=42, weight="weight")
        for user_a, user_b in graph.edges():
            xs = [pos[user_a][0], pos[user_b][0]]
            ys = [pos[user_a][1], pos[user_b][1]]
            zs = [pos[user_a][2], pos[user_b][2]]
            ax3d.plot(
                xs,
                ys,
                zs,
                color=style.COLOR_NETWORK_EDGE,
                alpha=0.35,
                linewidth=0.5 + 3 * edge_weights[(user_a, user_b)] / max_weight,
            )
        for node, coords in pos.items():
            ax3d.scatter(coords[0], coords[1], coords[2], s=45, color=style.COLOR_SERIES_PRIMARY)
            ax3d.text(coords[0], coords[1], coords[2], node[:14], fontsize=7, color=style.COLOR_TEXT)
        ax3d.set_axis_off()
    else:
        ax = style.content_axes(fig)
        pos = nx.spring_layout(graph, seed=42, weight="weight")
        nx.draw_networkx_edges(
            graph,
            pos,
            ax=ax,
            width=[0.4 + 4 * edge_weights[(u, v)] / max_weight for u, v in graph.edges()],  # type: ignore[arg-type]
            alpha=0.35,
            edge_color=style.COLOR_NETWORK_EDGE,
        )
        nx.draw_networkx_nodes(graph, pos, ax=ax, node_size=140, node_color=style.COLOR_SERIES_PRIMARY)
        nx.draw_networkx_labels(graph, pos, ax=ax, font_size=7, font_color=style.COLOR_TEXT)
        ax.axis("off")
    canvas.save_content_page(fig, title, subtitle)


def _save_pair_bar_page(
    canvas: _ReportCanvas, title: str, pair_rows: list[tuple[str, str, float]], subtitle: str
) -> None:
    labels = [f"{user_a} - {user_b}" for user_a, user_b, _ in pair_rows[:50]]
    values = [hours for _, _, hours in pair_rows[:50]]
    _save_bar_page(canvas, title, labels, values, "Hours Together", subtitle, value_fmt="{:.1f}")


def _save_unique_users_page(canvas: _ReportCanvas, data: WindowReportData, rows: list[tuple[str, int]]) -> None:
    fig = style.new_page_figure()
    ax = style.content_axes(fig, style.CONTENT_RECT_ROTATED_XLABELS)
    if not rows:
        style.draw_empty_message(ax)
    else:
        labels = [row[0] for row in rows]
        values = [row[1] for row in rows]
        ax.bar(labels, values, color=style.COLOR_SERIES_PRIMARY, width=0.72)
        ax.set_ylabel("Unique Users")
        ax.set_xlabel("Date")
        style.style_axes(ax, grid_axis="y")
        ax.tick_params(axis="x", labelrotation=70, labelsize=6)
    canvas.save_content_page(fig, "Unique Users Per Day", data.window.label())


def _save_weekday_matrix_page(
    canvas: _ReportCanvas,
    title: str,
    sessions: list[VoiceSession],
    top_user_ids: list[int],
    display_names: dict[int, str],
    subtitle: str,
) -> None:
    users, matrix = _weekday_minutes_by_user(sessions, top_user_ids, display_names)
    fig = style.new_page_figure()
    ax = style.content_axes(fig, (0.22, 0.12, 0.68, 0.74))
    if not users:
        style.draw_empty_message(ax)
    else:
        image = ax.imshow(matrix, cmap=style.SEQUENTIAL_CMAP, aspect="auto")
        ax.set_xticks(np.arange(7))
        ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        ax.set_yticks(np.arange(len(users)))
        ax.set_yticklabels(users, fontsize=7)
        ax.set_xlabel("Weekday")
        style.style_axes(ax, grid_axis=None)
        style.style_colorbar(fig.colorbar(image, ax=ax), "Voice Minutes")
    canvas.save_content_page(fig, title, subtitle)


def _save_monthly_voice_gradient_page(
    canvas: _ReportCanvas,
    title: str,
    sessions: list[VoiceSession],
    top_user_ids: list[int],
    display_names: dict[int, str],
    subtitle: str,
) -> None:
    months, values = _voice_hours_by_month_and_user(sessions, top_user_ids, display_names)
    users = list(values.keys())
    matrix = np.array([values[user] for user in users]) if users and months else np.array([])
    fig = style.new_page_figure()
    ax = style.content_axes(fig, (0.22, 0.12, 0.68, 0.74))
    if matrix.size == 0:
        style.draw_empty_message(ax)
    else:
        image = ax.imshow(matrix, cmap=style.SEQUENTIAL_CMAP, aspect="auto")
        ax.set_xticks(np.arange(len(months)))
        ax.set_xticklabels(months, rotation=45, ha="right", fontsize=7)
        ax.set_yticks(np.arange(len(users)))
        ax.set_yticklabels(users, fontsize=7)
        style.style_axes(ax, grid_axis=None)
        style.style_colorbar(fig.colorbar(image, ax=ax), "Voice Hours")
    canvas.save_content_page(fig, title, subtitle)


def _save_weekly_timeline_page(
    canvas: _ReportCanvas,
    title: str,
    sessions: list[VoiceSession],
    top_user_ids: list[int],
    display_names: dict[int, str],
    subtitle: str,
) -> None:
    weeks, values = _weekly_voice_hours_by_user(sessions, top_user_ids[: len(style.CHART_PALETTE)], display_names)
    fig = style.new_page_figure()
    ax = style.content_axes(fig, (0.07, 0.18, 0.70, 0.68))
    if not weeks:
        style.draw_empty_message(ax)
    else:
        for index, (user, series) in enumerate(values.items()):
            ax.plot(
                weeks,
                series,
                marker="o",
                markersize=3.5,
                linewidth=1.8,
                label=user,
                color=style.CHART_PALETTE[index],
            )
        ax.set_ylabel("Voice Hours")
        ax.set_xlabel("Week")
        ax.legend(fontsize=7.5, loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
        style.style_axes(ax, grid_axis="y")
        ax.tick_params(axis="x", labelrotation=55, labelsize=7)
    canvas.save_content_page(fig, title, subtitle)


def _save_total_monthly_voice_page(
    canvas: _ReportCanvas, title: str, sessions: list[VoiceSession], subtitle: str
) -> None:
    totals: dict[str, float] = defaultdict(float)
    for session in sessions:
        totals[session.start.strftime("%Y-%m")] += session.seconds / 3600.0
    labels = sorted(totals)
    values = [totals[label] for label in labels]
    _save_bar_page(canvas, title, labels, values, "Total Voice Hours", subtitle, value_fmt="{:.1f}")


def _save_rate_playing_server_page(
    canvas: _ReportCanvas, data: WindowReportData, rows: list[tuple[str, int, int, float, float, float]]
) -> None:
    _save_bar_page(
        canvas,
        "Rate Playing Ranked In Server",
        [row[0] for row in rows],
        [row[5] for row in rows],
        "% Ranked Matches In Server Voice",
        data.window.label(),
    )


def _save_win_rate_in_out_page(
    canvas: _ReportCanvas, data: WindowReportData, rows: list[tuple[str, int, int, float, float, float]]
) -> None:
    rows = sorted(rows, key=lambda row: row[3], reverse=True)
    fig = style.new_page_figure()
    ax = style.content_axes(fig, (0.24, 0.12, 0.70, 0.74))
    if not rows:
        style.draw_empty_message(ax)
    else:
        labels = [row[0] for row in rows[:40]]
        in_rates = [row[3] for row in rows[:40]]
        out_rates = [row[4] for row in rows[:40]]
        y_pos = np.arange(len(labels))
        width = 0.38
        ax.barh(y_pos - width / 2, in_rates, height=width, color=style.COLOR_IN_SERVER, label="In Server")
        ax.barh(y_pos + width / 2, out_rates, height=width, color=style.COLOR_OUTSIDE, label="Outside")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_xlabel("Win Rate %")
        ax.legend(fontsize=8, frameon=False, loc="lower right")
        ax.invert_yaxis()
        style.style_axes(ax, grid_axis="x")
    canvas.save_content_page(fig, "Win Rate: In Server vs Outside", data.window.label())


def _save_user_circular_page(canvas: _ReportCanvas, data: WindowReportData, user: UserWindowMetrics) -> None:
    fig = style.new_page_figure()
    donut_ax = fig.add_axes((0.05, 0.18, 0.42, 0.62))
    donut_ax.set_aspect("equal")
    server_values = [user.in_server_matches, user.outside_server_matches]
    if sum(server_values) == 0:
        style.draw_empty_message(donut_ax, "No ranked matches")
    else:
        pie_parts = donut_ax.pie(
            server_values,
            labels=["In Server", "Outside"],
            autopct="%1.0f%%",
            colors=[style.COLOR_IN_SERVER, style.COLOR_OUTSIDE],
            startangle=90,
            wedgeprops={"width": 0.45, "edgecolor": "white", "linewidth": 2},
        )
        for text in pie_parts[1]:
            text.set_color(style.COLOR_TEXT)
            text.set_fontsize(9)
        for autotext in pie_parts[2] if len(pie_parts) > 2 else []:
            autotext.set_color("white")
            autotext.set_fontweight("bold")
            autotext.set_fontsize(9)
        donut_ax.text(
            0,
            0.06,
            str(user.classified_ranked_matches),
            ha="center",
            va="center",
            fontsize=22,
            fontweight="bold",
            color=style.COLOR_NAVY,
        )
        donut_ax.text(0, -0.16, "classified rows", ha="center", va="center", fontsize=7.5, color=style.COLOR_MUTED)

    text_ax = style.blank_axes(fig, (0.52, 0.12, 0.43, 0.72))
    warning = (
        f"Sample warning: fewer than {LOW_SAMPLE_RANKED_ROWS} classified ranked rows."
        if user.classified_ranked_matches < LOW_SAMPLE_RANKED_ROWS
        else "Sample size is above the report warning threshold."
    )
    partner_line = (
        f"Outside partner signals: {user.outside_partner_match_count} inferred same-team matches."
        if user.outside_partner_match_count > 0
        else "Outside partner signals: none. Solo outside matches do not create partner rows."
    )
    metric_lines = [
        "Window Metrics:",
        f"- Voice hours: {user.voice_hours:.1f}",
        f"- Ranked match rows: {user.ranked_matches}",
        f"- Classified ranked rows: {user.classified_ranked_matches}",
        f"- In-server ranked: {user.in_server_matches} ({user.in_server_percent:.0f}%)",
        f"- Outside-server ranked: {user.outside_server_matches} ({user.outside_server_percent:.0f}%)",
        f"- Voice hours per ranked row: {user.voice_hours / max(user.ranked_matches, 1):.2f}",
        "",
        warning,
        partner_line,
    ]
    y = 0.96
    for line in metric_lines:
        y = _draw_text_line(text_ax, y, line) - 0.016
    canvas.save_content_page(fig, f"{user.display_name} — Ranked Voice Split", data.window.label())


def _save_user_timeline_page(
    canvas: _ReportCanvas, data: WindowReportData, user: UserWindowMetrics, sessions: list[VoiceSession]
) -> None:
    weeks: dict[str, float] = defaultdict(float)
    for session in sessions:
        if session.user_id != user.user_id:
            continue
        week = f"{session.start.isocalendar().year}-W{session.start.isocalendar().week:02d}"
        weeks[week] += session.seconds / 3600.0
    fig = style.new_page_figure()
    ax = style.content_axes(fig, style.CONTENT_RECT_ROTATED_XLABELS)
    if not weeks:
        style.draw_empty_message(ax, "No voice timeline data available for this user.")
    else:
        labels = sorted(weeks)
        values = [weeks[label] for label in labels]
        ax.plot(labels, values, marker="o", markersize=3.5, linewidth=1.8, color=style.COLOR_SERIES_PRIMARY)
        ax.set_ylabel("Voice Hours")
        ax.set_xlabel("Week")
        style.style_axes(ax, grid_axis="y")
        ax.tick_params(axis="x", labelrotation=55, labelsize=7)
    canvas.save_content_page(fig, f"{user.display_name} — Weekly Voice Timeline", data.window.label())


def _executive_summary_cards(report: MonthlyReportData) -> list[tuple[str, str]]:
    """Headline numbers for the primary window, shown as stat cards."""
    if not report.windows:
        return []
    previous_month = report.windows[0]
    total_classified = sum(user.classified_ranked_matches for user in previous_month.top_users)
    total_outside = sum(user.outside_server_matches for user in previous_month.top_users)
    return [
        (str(previous_month.active_users), "Active Users"),
        (f"{previous_month.total_voice_hours:.0f}", "Voice Hours"),
        (str(previous_month.ranked_match_rows), "Ranked Match Rows"),
        (str(previous_month.distinct_ranked_matches), "Distinct Ranked Matches"),
        (_format_percent(total_outside, total_classified), "Outside-Server Share"),
    ]


def _executive_summary_lines(report: MonthlyReportData) -> list[str]:
    if not report.windows:
        return ["No report windows were selected."]
    previous_month = report.windows[0]
    total_classified = sum(user.classified_ranked_matches for user in previous_month.top_users)
    total_outside = sum(user.outside_server_matches for user in previous_month.top_users)
    outside_leaders = sorted(
        previous_month.top_users,
        key=lambda user: (user.outside_server_percent, user.outside_server_matches, user.voice_hours),
        reverse=True,
    )
    partner_leaders = sorted(
        [user for user in previous_month.top_users if user.outside_partner_match_count > 0],
        key=lambda user: user.outside_partner_match_count,
        reverse=True,
    )
    lines = [
        f"Primary window: {previous_month.window.title} ({previous_month.window.label()})",
        f"Top-user outside-server ranked share: {_format_percent(total_outside, total_classified)} ({total_outside}/{total_classified} classified rows)",
        "",
        "Highest outside-server ranked share among top active users:",
    ]
    lines.extend(
        f"- {user.display_name}: {user.outside_server_percent:.0f}% outside ({user.outside_server_matches}/{user.classified_ranked_matches})"
        for user in outside_leaders[:5]
        if user.classified_ranked_matches > 0
    )
    if not any(user.classified_ranked_matches > 0 for user in outside_leaders[:5]):
        lines.append("- No classified ranked rows for the selected top users.")
    lines.extend(["", "Strongest outside-server same-team partner signals:"])
    lines.extend(
        f"- {user.display_name}: {user.outside_partner_match_count} inferred same-team outside matches"
        for user in partner_leaders[:5]
    )
    if not partner_leaders:
        lines.append("- No inferred same-team outside partners among top active users.")
    return lines


def _save_executive_summary_page(canvas: _ReportCanvas, report: MonthlyReportData) -> None:
    """Render the executive summary with headline stat cards above the detail lines."""
    fig = style.new_page_figure()
    style.draw_stat_cards(fig, _executive_summary_cards(report), y=0.71, height=0.13)
    ax = style.blank_axes(fig)
    y = 0.74
    for line in _executive_summary_lines(report):
        y = _draw_text_line(ax, y, line)
    canvas.save_content_page(fig, "Executive Summary", f"Report month {report.report_month}")


def _deterministic_action_lines(report: MonthlyReportData) -> list[str]:
    if not report.windows:
        return ["No report windows were selected."]
    previous_month = report.windows[0]
    lines: list[str] = []
    outside_candidates = [
        user
        for user in previous_month.top_users
        if user.classified_ranked_matches >= LOW_SAMPLE_RANKED_ROWS and user.outside_server_percent >= 50.0
    ]
    outside_candidates.sort(key=lambda user: (user.outside_server_percent, user.outside_server_matches), reverse=True)
    if outside_candidates:
        lines.append("Invite high outside-server ranked players back into server voice:")
        lines.extend(
            f"- {user.display_name}: {user.outside_server_percent:.0f}% outside ({user.outside_server_matches}/{user.classified_ranked_matches})"
            for user in outside_candidates[:8]
        )
    else:
        lines.append("No top active user crossed the high outside-server threshold for this period.")

    partner_candidates = sorted(
        [user for user in previous_month.top_users if user.outside_partner_match_count >= 3],
        key=lambda user: user.outside_partner_match_count,
        reverse=True,
    )
    lines.extend(["", "Follow up on outside-server groups that could be converted into server activity:"])
    if partner_candidates:
        lines.extend(
            f"- {user.display_name}: {user.outside_partner_match_count} inferred same-team outside matches"
            for user in partner_candidates[:8]
        )
    else:
        lines.append("- No repeated outside-server partner cluster exceeded the follow-up threshold.")

    quality = previous_month.data_quality
    if quality.ranked_rows_without_voice_context > 0 or quality.suspicious_voice_sessions > 0:
        lines.extend(
            [
                "",
                "Review data quality before making strict user-level decisions:",
                f"- Ranked rows without voice context: {quality.ranked_rows_without_voice_context}",
                f"- Suspicious voice sessions over 12h: {quality.suspicious_voice_sessions}",
            ]
        )
    return lines


def _data_quality_lines(report: MonthlyReportData) -> list[str]:
    lines = [
        "Methodology:",
        "- Ranked rows include ranked matches with rollback rows excluded.",
        "- In-server ranked rows require a voice connect/disconnect interval covering the match timestamp.",
        "- Outside-server partners are inferred only when another user has the same match id and same result.",
        "- Solo outside matches do not create partner rows.",
        "- Date windows use inclusive start and exclusive end boundaries.",
        "",
        "Data quality by window:",
    ]
    for data in report.windows:
        quality = data.data_quality
        lines.extend(
            [
                f"- {data.window.title}:",
                f"  Voice sessions: {quality.voice_sessions}",
                f"  Unmatched disconnects in window: {quality.unmatched_disconnects}",
                f"  Open sessions at window end: {quality.open_sessions_at_window_end}",
                f"  Suspicious voice sessions over 12h: {quality.suspicious_voice_sessions}",
                f"  Ranked rows without voice context: {quality.ranked_rows_without_voice_context}",
                f"  Rollback ranked rows excluded: {quality.rollback_ranked_rows_excluded}",
            ]
        )
    return lines


def _ai_prompt(report: MonthlyReportData) -> str:
    sections: list[str] = []
    for data in report.windows:
        top_users = "; ".join(
            f"{user.display_name}: {user.voice_hours:.1f}h voice, {user.ranked_matches} ranked, "
            f"{user.in_server_matches} in-server, {user.outside_server_matches} outside"
            for user in data.top_users[:10]
        )
        outside_leaders = "; ".join(
            f"{user.display_name}: {sum(partner[1] for partner in user.outside_partners)} same-team outside partner matches"
            for user in data.top_users[:10]
            if user.outside_partners
        )
        sections.append(
            f"{data.window.title}\n"
            f"Active users: {data.active_users}\n"
            f"Voice hours: {data.total_voice_hours:.1f}\n"
            f"Ranked match rows: {data.ranked_match_rows}\n"
            f"Distinct ranked matches: {data.distinct_ranked_matches}\n"
            f"Ranked rows without voice context: {data.data_quality.ranked_rows_without_voice_context}\n"
            f"Suspicious voice sessions over 12h: {data.data_quality.suspicious_voice_sessions}\n"
            f"Top active users: {top_users or 'none'}\n"
            f"Outside-server same-team partner signals: {outside_leaders or 'none'}"
        )
    actions = "\n".join(_deterministic_action_lines(report))
    return (
        "You are writing the conclusion for a Discord Siege community monthly analytics PDF. "
        "Use only the deterministic facts below. Do not invent data. "
        "Write concise sections: Key Findings, Risks, Opportunities, Recommended Actions. "
        "Actionable items should be specific moderator/community actions.\n\n"
        + "\n\n".join(sections)
        + "\n\nDeterministic action candidates:\n"
        + actions
    )


def generate_ai_conclusion(report: MonthlyReportData) -> str:
    """Generate the final report conclusion using AI. Returns fallback text on failure."""
    try:
        result = BotAISingleton().ask_ai(_ai_prompt(report), use_gpt=True)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print_error_log(f"generate_ai_conclusion: {e}")
        result = None
    if result is None or result.strip() == "":
        return (
            "AI conclusion unavailable.\n\n"
            "Deterministic highlights are included in the report tables and charts. Review users with high outside-server "
            "ranked volume, low recent activity, and repeated same-team outside partnerships for follow-up."
        )
    return result.strip()


async def generate_ai_conclusion_async(report: MonthlyReportData) -> str:
    """Generate the final report conclusion using AI from async bot tasks."""
    try:
        result = await BotAISingleton().ask_ai_async(_ai_prompt(report), timeout=240.0, use_gpt=True)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print_error_log(f"generate_ai_conclusion_async: {e}")
        result = None
    if result is None or result.strip() == "":
        return (
            "AI conclusion unavailable.\n\n"
            "Deterministic highlights are included in the report tables and charts. Review users with high outside-server "
            "ranked volume, low recent activity, and repeated same-team outside partnerships for follow-up."
        )
    return result.strip()


@dataclass(frozen=True)
class _WindowRenderInputs:
    """Prefetched data for rendering one window, shared by both render passes."""

    sessions: list[VoiceSession]
    display_names: dict[int, str]
    pair_rows: list[tuple[str, str, float]]
    inactive_rows: list[tuple[str, str]]
    rate_rows: list[tuple[str, int, int, float, float, float]]
    unique_users_rows: list[tuple[str, int]]


def _collect_window_render_inputs(data: WindowReportData) -> _WindowRenderInputs:
    sessions = _fetch_voice_sessions(data.window)
    display_names = _fetch_user_display_names()
    return _WindowRenderInputs(
        sessions=sessions,
        display_names=display_names,
        pair_rows=_compute_pair_overlap_hours(sessions, display_names),
        inactive_rows=_fetch_last_activity_by_user(data.window, display_names),
        rate_rows=_fetch_match_server_rate_rows(data.window, sessions),
        unique_users_rows=_fetch_unique_users_per_day(data.window),
    )


def _month_display(report_month: str) -> str:
    return datetime.strptime(report_month, "%Y-%m").strftime("%B %Y")


def _save_user_detail_page(canvas: _ReportCanvas, data: WindowReportData, user: UserWindowMetrics) -> None:
    partner_text = (
        "\n".join(
            f"- {partner[0]}: {partner[1]} matches, {partner[3]:.0f}% selected-user win rate"
            for partner in user.outside_partners
        )
        if user.outside_partners
        else "No same-team outside-server partners found."
    )
    _save_text_page(
        canvas,
        f"{user.display_name} — Details",
        [
            f"- Voice hours: {user.voice_hours:.1f}",
            f"- Ranked match rows: {user.ranked_matches}",
            f"- In-server ranked match rows: {user.in_server_matches}",
            f"- Outside-server ranked match rows: {user.outside_server_matches}",
            f"- In-server percentage: {user.in_server_percent:.0f}%",
            f"- Outside-server percentage: {user.outside_server_percent:.0f}%",
            f"- Voice hours per ranked match row: {user.voice_hours / max(user.ranked_matches, 1):.2f}",
            (
                f"- Sample warning: fewer than {LOW_SAMPLE_RANKED_ROWS} classified ranked rows."
                if user.classified_ranked_matches < LOW_SAMPLE_RANKED_ROWS
                else "- Sample size is above the report warning threshold."
            ),
            "",
            "Deterministic conclusion:",
            (
                f"{user.display_name} had {user.classified_ranked_matches} classified ranked rows. "
                f"The split was {user.in_server_matches} in-server and {user.outside_server_matches} outside-server, "
                f"with {user.voice_hours:.1f} voice hours in this report window."
            ),
            "",
            "Top same-team outside-server partners:",
            partner_text,
        ],
        data.window.label(),
    )


def _render_window_pages(canvas: _ReportCanvas, data: WindowReportData, inputs: _WindowRenderInputs) -> None:
    subtitle = data.window.label()
    top_user_ids = [user.user_id for user in data.top_users]
    canvas.add_toc_entry("Window Summary", 1)
    _save_table_page(
        canvas,
        "Window Summary",
        ["Metric", "Value"],
        [
            ["Active users", data.active_users],
            ["Total voice hours", f"{data.total_voice_hours:.1f}"],
            ["Ranked match rows", data.ranked_match_rows],
            ["Distinct ranked matches", data.distinct_ranked_matches],
            ["Voice sessions", data.data_quality.voice_sessions],
            ["Ranked rows without voice context", data.data_quality.ranked_rows_without_voice_context],
            ["Rollback ranked rows excluded", data.data_quality.rollback_ranked_rows_excluded],
            ["Suspicious voice sessions over 12h", data.data_quality.suspicious_voice_sessions],
        ],
        subtitle,
    )
    canvas.add_toc_entry("Community Network (2D)", 1)
    _save_network_page(canvas, "Community Network (2D)", inputs.pair_rows, subtitle, dim_3d=False)
    canvas.add_toc_entry("Community Network (3D)", 1)
    _save_network_page(canvas, "Community Network (3D)", inputs.pair_rows, subtitle, dim_3d=True)
    canvas.add_toc_entry("Duo Relationship Time", 1)
    _save_pair_bar_page(canvas, "Duo Relationship Time", inputs.pair_rows, subtitle)
    canvas.add_toc_entry("Top Voice Time", 1)
    _save_bar_page(
        canvas,
        f"Top {len(data.top_users)} Voice Time",
        [user.display_name for user in data.top_users],
        [user.voice_hours for user in data.top_users],
        "Voice Hours",
        subtitle,
        value_fmt="{:.1f}",
    )
    canvas.add_toc_entry("Inactive Users", 1)
    _save_table_page(
        canvas,
        "Inactive Users",
        ["User", "Last Seen"],
        [[row[0], row[1]] for row in inputs.inactive_rows],
        subtitle,
    )
    canvas.add_toc_entry("Voice Minutes by Weekday", 1)
    _save_weekday_matrix_page(
        canvas, "Voice Minutes by Weekday", inputs.sessions, top_user_ids, inputs.display_names, subtitle
    )
    canvas.add_toc_entry("Voice Hours by Month", 1)
    _save_monthly_voice_gradient_page(
        canvas, "Voice Hours by Month", inputs.sessions, top_user_ids, inputs.display_names, subtitle
    )
    canvas.add_toc_entry("Weekly Voice Timeline", 1)
    _save_weekly_timeline_page(
        canvas, "Weekly Voice Timeline (Top 8)", inputs.sessions, top_user_ids, inputs.display_names, subtitle
    )
    canvas.add_toc_entry("Monthly Voice Time", 1)
    _save_total_monthly_voice_page(canvas, "Monthly Voice Time", inputs.sessions, subtitle)
    canvas.add_toc_entry("Top Ranked Match Rows", 1)
    _save_bar_page(
        canvas,
        f"Top {len(data.top_users)} Ranked Match Rows",
        [user.display_name for user in data.top_users],
        [float(user.ranked_matches) for user in data.top_users],
        "Ranked Match Rows",
        subtitle,
    )
    canvas.add_toc_entry("Rate Playing Ranked In Server", 1)
    _save_rate_playing_server_page(canvas, data, inputs.rate_rows)
    canvas.add_toc_entry("Win Rate: In Server vs Outside", 1)
    _save_win_rate_in_out_page(canvas, data, inputs.rate_rows)
    canvas.add_toc_entry("Unique Users Per Day", 1)
    _save_unique_users_page(canvas, data, inputs.unique_users_rows)
    canvas.add_toc_entry("Ranked Matches: In Server vs Outside", 1)
    _save_server_split_page(canvas, data)
    canvas.add_toc_entry("Top Users", 1)
    _save_table_page(
        canvas,
        "Top Users",
        ["User", "Voice h", "Ranked", "In server", "Outside", "Outside %"],
        [
            [
                user.display_name,
                f"{user.voice_hours:.1f}",
                user.ranked_matches,
                user.in_server_matches,
                user.outside_server_matches,
                f"{user.outside_server_percent:.0f}%",
            ]
            for user in data.top_users
        ],
        subtitle,
    )
    if data.top_users:
        canvas.add_toc_entry("Player Profiles", 1)
    for user in data.top_users:
        _save_user_timeline_page(canvas, data, user, inputs.sessions)
        _save_user_circular_page(canvas, data, user)
        _save_user_detail_page(canvas, data, user)


def _render_report_pages(
    canvas: _ReportCanvas,
    report: MonthlyReportData,
    conclusion: str,
    window_inputs: dict[str, _WindowRenderInputs],
) -> None:
    """Emit every body page (everything after the cover and TOC) in order."""
    month_subtitle = f"Report month {report.report_month}"
    canvas.begin_section("Overview")
    canvas.add_toc_entry("Executive Summary", 0)
    _save_executive_summary_page(canvas, report)
    canvas.add_toc_entry("Deterministic Action Items", 0)
    _save_text_page(canvas, "Deterministic Action Items", _deterministic_action_lines(report), month_subtitle)
    canvas.add_toc_entry("Data Quality and Methodology", 0)
    _save_text_page(canvas, "Data Quality and Methodology", _data_quality_lines(report), month_subtitle)
    for index, data in enumerate(report.windows, start=1):
        canvas.begin_section(data.window.title)
        canvas.add_toc_entry(f"Section {index:02d} — {data.window.title}", 0)
        canvas.save_full_bleed_page(
            style.draw_section_divider(
                section_number=index,
                title=data.window.title,
                date_range=data.window.label(),
                bullets=[
                    "Window summary and data quality",
                    "Community relationship networks",
                    "Voice activity trends and heatmaps",
                    "Ranked in-server vs outside analysis",
                    "Win-rate comparisons",
                    f"Player profiles for the top {len(data.top_users)} active members",
                ],
            )
        )
        _render_window_pages(canvas, data, window_inputs[data.window.key])
    canvas.begin_section("Conclusion")
    canvas.add_toc_entry("AI Conclusion and Action Items", 0)
    _save_text_page(canvas, "AI Conclusion and Action Items", conclusion.splitlines(), month_subtitle)


def render_monthly_report_pdf(
    report: MonthlyReportData,
    conclusion: str,
    output_dir: Path | str = "reports/monthly",
) -> Path:
    """Render collected report data to a themed PDF and return the output path.

    Rendering runs twice: a first pass into an in-memory buffer collects the table
    of contents entries and page count, then the final pass writes the real file
    with the cover, an accurate TOC, and page-total footers.
    """
    output_base = Path(output_dir) / report.report_month
    output_base.mkdir(parents=True, exist_ok=True)
    output_path = output_base / f"gametime_report_{report.report_month}.pdf"
    window_inputs = {data.window.key: _collect_window_render_inputs(data) for data in report.windows}

    with PdfPages(io.BytesIO()) as probe_pdf:
        probe = _ReportCanvas(probe_pdf, report.report_month)
        _render_report_pages(probe, report, conclusion, window_inputs)
    front_matter_pages = 1 + style.toc_page_count(len(probe.toc_entries))
    toc_entries = [entry.shifted(front_matter_pages) for entry in probe.toc_entries]
    total_pages = front_matter_pages + probe.page_number

    with PdfPages(output_path) as pdf:
        canvas = _ReportCanvas(pdf, report.report_month, total_pages=total_pages)
        canvas.save_full_bleed_page(
            style.draw_cover_page(
                month_display=_month_display(report.report_month),
                report_month=report.report_month,
                generated_display=report.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
                stats=_executive_summary_cards(report)[:4],
            )
        )
        canvas.begin_section("Contents")
        for page_start in range(0, len(toc_entries), style.TOC_ROWS_PER_PAGE):
            fig = style.new_page_figure()
            style.draw_toc_entries(fig, toc_entries[page_start : page_start + style.TOC_ROWS_PER_PAGE])
            canvas.save_content_page(fig, "Table of Contents", f"Report month {report.report_month}")
        _render_report_pages(canvas, report, conclusion, window_inputs)
    return output_path


def generate_monthly_report(
    reference_day: Optional[date] = None,
    output_dir: Path | str = "reports/monthly",
    top_n: int = REPORT_TOP_USERS,
    include_ai: bool = True,
    window_keys: Optional[Iterable[str]] = None,
) -> Path:
    """Collect data, optionally generate AI conclusion, and render the monthly report PDF."""
    report = collect_monthly_report_data(reference_day, top_n, window_keys)
    conclusion = generate_ai_conclusion(report) if include_ai else "AI conclusion disabled for this run."
    return render_monthly_report_pdf(report, conclusion, output_dir)


async def generate_monthly_report_async(
    reference_day: Optional[date] = None,
    output_dir: Path | str = "reports/monthly",
    top_n: int = REPORT_TOP_USERS,
    window_keys: Optional[Iterable[str]] = None,
) -> Path:
    """Async report generation for bot tasks."""
    report = await asyncio.to_thread(collect_monthly_report_data, reference_day, top_n, window_keys)
    conclusion = await generate_ai_conclusion_async(report)
    return await asyncio.to_thread(render_monthly_report_pdf, report, conclusion, output_dir)


async def send_monthly_analytics_report_guild(guild: discord.Guild, reference_day: Optional[date] = None) -> None:
    """Generate and send the monthly analytics report for one guild when due."""
    if reference_day is None:
        reference_day = datetime.now(timezone.utc).date()
    if reference_day.day != 1:
        return
    report_month, _ = get_monthly_report_windows(reference_day)
    if await data_access_get_monthly_analytics_report_sent(guild.id, report_month):
        print_log(f"send_monthly_analytics_report_guild: Report {report_month} already sent for {guild.name}")
        return
    channel_id = await data_access_get_analytics_report_text_channel_id(guild.id)
    if channel_id is None:
        print_warning_log(
            f"send_monthly_analytics_report_guild: Analytics report channel not set for {guild.name}. Skipping."
        )
        return
    channel = await data_access_get_channel(channel_id)
    if channel is None:
        print_error_log(f"send_monthly_analytics_report_guild: Channel {channel_id} not found for {guild.name}")
        return
    output_path = await generate_monthly_report_async(reference_day)
    await channel.send(
        content=f"Monthly analytics report for {report_month}",
        file=discord.File(str(output_path), filename=output_path.name),
    )
    data_access_set_monthly_analytics_report_sent(guild.id, report_month)
