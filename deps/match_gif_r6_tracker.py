"""Find the R6 Tracker match behind a match-start GIF.

stats.cc is optional software: when nobody in the squad runs it, R6 Tracker's match history is the only
way to put a final score on the "Match starting... Good luck!" message. This module only does the pure
matching; fetching and the Discord edit live in ``bot_common_actions``.

R6 Tracker's match ``timestamp`` is when the match ENDED (prod, 2026-10-31: GIF posted 06:42, Kanal match
stamped 07:18:59 with a 37-minute duration). Matching on that end time would credit the previous match,
which ended minutes before the next GIF, to the wrong message. The match start is therefore estimated as
``timestamp - duration`` and must be close to the moment the GIF was posted.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping, Optional

from deps.models import UserFullMatchStats
from deps.siege import StatsCcRankedMatchEndResult

# Prod (2026-10-31/11-01, 11 GIFs): R6 Tracker's start is 45-80 s before the GIF post. Back-to-back matches
# start at least ~15 min apart, so this window cannot reach the previous or next match.
MATCH_START_TOLERANCE = timedelta(minutes=10)


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _estimated_match_start(match: UserFullMatchStats) -> Optional[datetime]:
    """Match start derived from R6 Tracker's end ``timestamp`` minus the duration, if both are usable."""
    duration_ms = int(match.match_duration_ms or 0)
    if not isinstance(match.match_timestamp, datetime) or duration_ms <= 0:
        return None
    return _utc(match.match_timestamp) - timedelta(milliseconds=duration_ms)


def _candidate_start_distance(match: UserFullMatchStats, gif_started_at: datetime) -> Optional[float]:
    """Seconds between the match start and the GIF post, or None when the match cannot be this GIF's."""
    if match.is_rollback or not match.match_uuid or "ranked" not in str(match.session_type or "").lower():
        return None
    estimated_start = _estimated_match_start(match)
    if estimated_start is None or abs(estimated_start - gif_started_at) > MATCH_START_TOLERANCE:
        return None
    return abs((estimated_start - gif_started_at).total_seconds())


def find_r6_tracker_match_for_gif(
    gif_started_at: datetime,
    member_ids: Iterable[int],
    matches_by_member: Mapping[int, Iterable[UserFullMatchStats]],
) -> Optional[UserFullMatchStats]:
    """The ranked match the GIF's squad started when the GIF was posted, or None if not (yet) known.

    Prefers the match shared by the most squad members, then the start closest to the GIF. A match whose
    members disagree on the outcome is ignored rather than showing a wrong score.
    """
    started_at = _utc(gif_started_at)
    by_uuid: dict[str, dict[int, tuple[UserFullMatchStats, float]]] = defaultdict(dict)
    for member_id in member_ids:
        for match in matches_by_member.get(int(member_id), ()):
            distance = _candidate_start_distance(match, started_at)
            if distance is not None:
                by_uuid[match.match_uuid][match.user_id] = (match, distance)

    ranked: list[tuple[int, float, UserFullMatchStats]] = []
    for records in by_uuid.values():
        if len({bool(match.has_win) for match, _ in records.values()}) != 1:
            continue
        representative, distance = next(iter(records.values()))
        ranked.append((len(records), -distance, representative))
    if not ranked:
        return None
    return max(ranked, key=lambda item: (item[0], item[1]))[2]


def match_end_result_from_r6_tracker(match: UserFullMatchStats) -> StatsCcRankedMatchEndResult:
    """Present an R6 Tracker match like a final stats.cc result so the GIF summary renders it the same way."""
    our_score = int(match.round_won_count or 0)
    their_score = int(match.round_lost_count or 0)
    if our_score + their_score == 0:
        # No round counts: still show who won rather than nothing.
        our_score, their_score = (1, 0) if match.has_win else (0, 1)
    return StatsCcRankedMatchEndResult(
        won=bool(match.has_win),
        our_score=our_score,
        their_score=their_score,
        map_name=match.map_name or None,
        is_tie=False,
        is_match_complete=True,
    )
