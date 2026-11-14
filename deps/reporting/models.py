"""Data structures shared by the analytics report pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class ReportWindow:
    """One report window with an exclusive end."""

    key: str
    title: str
    start: datetime
    end_exclusive: datetime

    @property
    def label(self) -> str:
        return f"{self.start.date().isoformat()} to {self.end_exclusive.date().isoformat()} (exclusive)"

    @property
    def days(self) -> int:
        return max(1, (self.end_exclusive - self.start).days)


@dataclass(frozen=True)
class UserInfo:
    """Identity and settings for one Discord user."""

    user_id: int
    display_name: str
    ubisoft_name: str
    time_zone: str
    max_mmr: int


@dataclass(frozen=True)
class VoiceSession:
    """A paired voice session, clipped to a report window."""

    user_id: int
    channel_id: int
    start: datetime
    end: datetime

    @property
    def seconds(self) -> float:
        return max(0.0, (self.end - self.start).total_seconds())


@dataclass(frozen=True)
class MatchRow:
    """One tracked user's row in a ranked match."""

    user_id: int
    match_uuid: str
    match_timestamp: datetime
    duration_ms: int
    has_win: bool
    data_center: str
    points_gained: int
    rank_name: str
    map_name: str
    operators: str
    round_disconnected_count: int
    is_surrender: bool
    is_forfeit: bool

    @property
    def seconds(self) -> float:
        return max(0.0, float(self.duration_ms) / 1000.0)

    @property
    def start(self) -> datetime:
        return self.match_timestamp - _seconds_delta(self.seconds)


def _seconds_delta(seconds: float):
    from datetime import timedelta

    return timedelta(seconds=seconds)


@dataclass
class DataQuality:
    """Counts that make data limitations explicit."""

    unmatched_disconnects: int = 0
    open_sessions_at_end: int = 0
    long_sessions: int = 0
    rollback_rows_excluded: int = 0
    missing_duration_rows: int = 0
    missing_timezone_users: int = 0
    missing_ubisoft_users: int = 0
    voice_only_users: int = 0
    match_only_users: int = 0
    duplicate_display_names: int = 0
    snapshot_max_activity: Optional[datetime] = None
    snapshot_max_match: Optional[datetime] = None
    stale_days: int = 0


@dataclass
class UserMetrics:
    """Per-user metrics for one window."""

    user_id: int
    display_name: str
    ubisoft_name: str
    time_zone: str
    max_mmr: int
    voice_seconds: float = 0.0
    session_count: int = 0
    session_minutes: list[float] = field(default_factory=list)
    match_rows: int = 0
    distinct_matches: int = 0
    match_seconds: float = 0.0
    in_rows: int = 0
    out_rows: int = 0
    in_seconds: float = 0.0
    out_seconds: float = 0.0
    in_wins: int = 0
    out_wins: int = 0
    in_rank_delta: int = 0
    out_rank_delta: int = 0
    outside_while_active: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    last_voice: Optional[datetime] = None
    last_match: Optional[datetime] = None
    weekday_hour_voice: dict[tuple[int, int], float] = field(default_factory=dict)
    weekday_hour_matches: dict[tuple[int, int], int] = field(default_factory=dict)
    top_voice_partners: list[tuple[str, float]] = field(default_factory=list)
    top_match_partners: list[tuple[str, int]] = field(default_factory=list)
    top_outside_partners: list[tuple[str, int]] = field(default_factory=list)
    classification: str = "inactive"
    flags: list[str] = field(default_factory=list)
    prior_28d_voice_seconds: float = 0.0
    current_14d_voice_seconds: float = 0.0
    weekly_voice_seconds: list[float] = field(default_factory=list)
    messages: int = 0

    @property
    def voice_hours(self) -> float:
        return self.voice_seconds / 3600.0

    @property
    def match_hours(self) -> float:
        return self.match_seconds / 3600.0

    @property
    def in_hours(self) -> float:
        return self.in_seconds / 3600.0

    @property
    def out_hours(self) -> float:
        return self.out_seconds / 3600.0

    @property
    def median_session_minutes(self) -> float:
        if not self.session_minutes:
            return 0.0
        values = sorted(self.session_minutes)
        return values[len(values) // 2]

    @property
    def in_percent(self) -> float:
        return _percent(self.in_rows, self.match_rows)

    @property
    def out_percent(self) -> float:
        return _percent(self.out_rows, self.match_rows)

    @property
    def in_win_rate(self) -> float:
        return _percent(self.in_wins, self.in_rows)

    @property
    def out_win_rate(self) -> float:
        return _percent(self.out_wins, self.out_rows)

    @property
    def match_per_voice_hour(self) -> float:
        return self.match_rows / self.voice_hours if self.voice_hours > 0 else 0.0


def _percent(part: int, whole: int) -> float:
    return (float(part) * 100.0 / float(whole)) if whole else 0.0


@dataclass
class PairRelationship:
    """Aggregated relationship between two users."""

    user_a: int
    user_b: int
    co_voice_seconds: float = 0.0
    co_matches: int = 0
    co_wins: int = 0

    @property
    def score(self) -> float:
        return self.co_voice_seconds / 3600.0 + self.co_matches * 0.25


@dataclass
class WindowMetrics:
    """All deterministic metrics for one report window."""

    window: ReportWindow
    users: list[UserMetrics]
    data_quality: DataQuality
    total_voice_seconds: float = 0.0
    session_count: int = 0
    match_rows: int = 0
    distinct_matches: int = 0
    match_seconds: float = 0.0
    in_rows: int = 0
    out_rows: int = 0
    in_seconds: float = 0.0
    out_seconds: float = 0.0
    voice_users: int = 0
    match_users: int = 0
    any_users: int = 0
    new_users: int = 0
    returning_users: int = 0
    churned_users: int = 0
    peak_concurrent: int = 0
    peak_concurrent_at: Optional[datetime] = None
    avg_concurrent: float = 0.0
    unique_users_per_day: list[tuple[date, int]] = field(default_factory=list)
    messages: int = 0
    message_users: int = 0
    weekday_hour_voice: dict[tuple[int, int], float] = field(default_factory=dict)
    weekday_hour_matches: dict[tuple[int, int], int] = field(default_factory=dict)
    weekly_voice: list[tuple[date, float]] = field(default_factory=list)
    weekly_matches: list[tuple[date, int]] = field(default_factory=list)
    monthly_voice: list[tuple[str, float]] = field(default_factory=list)
    monthly_matches: list[tuple[str, int]] = field(default_factory=list)
    session_length_counts: dict[str, int] = field(default_factory=dict)
    in_data_centers: dict[str, int] = field(default_factory=dict)
    out_data_centers: dict[str, int] = field(default_factory=dict)
    pairs: list[PairRelationship] = field(default_factory=list)

    @property
    def total_voice_hours(self) -> float:
        return self.total_voice_seconds / 3600.0

    @property
    def match_hours(self) -> float:
        return self.match_seconds / 3600.0

    @property
    def in_percent(self) -> float:
        return _percent(self.in_rows, self.match_rows)

    @property
    def out_percent(self) -> float:
        return _percent(self.out_rows, self.match_rows)

    @property
    def median_session_minutes(self) -> float:
        values = sorted(m for u in self.users for m in u.session_minutes)
        return values[len(values) // 2] if values else 0.0

    @property
    def outside_while_active_count(self) -> int:
        return sum(user.outside_while_active for user in self.users)

    def user(self, user_id: int) -> Optional[UserMetrics]:
        return next((u for u in self.users if u.user_id == user_id), None)


@dataclass
class ActionItem:
    """One evidence-backed admin action."""

    action_id: str
    priority: str
    category: str
    user_ids: tuple[int, ...]
    headline: str
    evidence: tuple[str, ...]
    why_it_matters: str
    suggested_action: str
    message: str
    confidence: str
    caveats: tuple[str, ...] = ()
    impact: int = 0

    @property
    def score(self) -> int:
        priority_score = {"P0": 300, "P1": 200, "P2": 100}.get(self.priority, 0)
        return priority_score + self.impact + min(len(self.evidence), 5) * 5


@dataclass
class NetworkNode:
    user_id: int
    label: str
    voice_hours: float
    classification: str
    degree: int = 0
    betweenness: float = 0.0
    community: int = 0


@dataclass
class NetworkEdge:
    user_a: int
    user_b: int
    label_a: str
    label_b: str
    co_voice_hours: float
    co_matches: int
    score: float


@dataclass
class ReportData:
    """Everything the renderer needs, with no database access."""

    report_month: str
    reference_date: date
    generated_at: datetime
    database_path: str
    windows: list[WindowMetrics]
    primary: WindowMetrics
    actions: list[ActionItem]
    narrative: str
    narrative_source: str
    narrative_facts: dict[str, str]
    users: dict[int, UserInfo]
    network_nodes: list[NetworkNode] = field(default_factory=list)
    network_edges: list[NetworkEdge] = field(default_factory=list)
    time_zone_distribution: dict[str, int] = field(default_factory=dict)
