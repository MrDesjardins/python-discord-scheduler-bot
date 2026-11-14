"""Unit tests for voice session pairing, clipping, and overlap helpers."""

from datetime import datetime, timezone

from deps.reporting.data import _co_voice_pairs, _outside_while_active, clip_sessions, merge_intervals, overlap_seconds
from deps.reporting.models import MatchRow, ReportWindow, VoiceSession


def _dt(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


def _window() -> ReportWindow:
    return ReportWindow("previous_month", "Previous Month", _dt(1, 0), _dt(31, 0))


def test_merge_intervals_merges_overlap_and_keeps_gaps() -> None:
    merged = merge_intervals([(_dt(1, 20), _dt(1, 22)), (_dt(1, 21), _dt(1, 23)), (_dt(2, 1), _dt(2, 2))])
    assert merged == [(_dt(1, 20), _dt(1, 23)), (_dt(2, 1), _dt(2, 2))]


def test_clip_sessions_clips_to_window() -> None:
    sessions = [
        VoiceSession(
            1, 10, datetime(2026, 9, 30, 23, tzinfo=timezone.utc), datetime(2026, 11, 1, 2, tzinfo=timezone.utc)
        ),
        VoiceSession(2, 10, _dt(1, 0), _dt(1, 1)),
    ]
    clipped = clip_sessions(sessions, _window())
    assert len(clipped) == 2
    assert clipped[0].start == _dt(1, 0)
    assert clipped[0].end == _dt(31, 0)


def test_overlap_seconds_uses_merged_intervals() -> None:
    total = overlap_seconds([(_dt(1, 20), _dt(1, 22))], [(_dt(1, 21), _dt(1, 23))])
    assert total == 3600


def test_co_voice_pairs_counts_unique_overlap() -> None:
    sessions = [
        VoiceSession(1, 10, _dt(1, 20), _dt(1, 22)),
        VoiceSession(2, 10, _dt(1, 20, 30), _dt(1, 21, 30)),
        VoiceSession(1, 11, _dt(1, 20, 30), _dt(1, 21, 30)),
    ]
    pairs = _co_voice_pairs(sessions)
    assert pairs[(1, 2)] == 3600


def test_outside_while_active_only_counts_active_windows() -> None:
    sessions = [
        VoiceSession(1, 10, _dt(2, 20), _dt(2, 22)),
        VoiceSession(2, 10, _dt(2, 20), _dt(2, 22)),
        VoiceSession(3, 10, _dt(2, 20), _dt(2, 22)),
    ]
    match = MatchRow(
        user_id=4,
        match_uuid="m1",
        match_timestamp=_dt(2, 21),
        duration_ms=1_800_000,
        has_win=True,
        data_center="US East",
        points_gained=20,
        rank_name="Gold",
        map_name="Bank",
        operators="Doc",
        round_disconnected_count=0,
        is_surrender=False,
        is_forfeit=False,
    )
    counts = _outside_while_active([match], sessions, threshold=3)
    assert counts[4] == 1
