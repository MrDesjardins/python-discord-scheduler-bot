"""Delayed TribeMarkets match reconciliation.

Stats.cc is the fastest signal, but it is optional software.  R6 Tracker's
match history is the durable fallback: after a player leaves voice, the normal
queued fetch returns the match UUID, map, and win/loss result.  This module
keeps the matching algorithm pure and the SQLite persistence deliberately
small so the Discord event loop never has to guess from presence text.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from deps.models import UserFullMatchStats
from deps.system_database import database_manager


RECONCILIATION_WINDOW = timedelta(hours=6)
RECONCILIATION_RETENTION = timedelta(days=2)


@dataclass(frozen=True)
class ReconciledMatch:
    """A match confidently associated with a pending Discord market."""

    match_uuid: str
    map_name: str
    won: bool
    started_at: datetime
    participant_count: int
    score: str | None


@dataclass(frozen=True)
class PendingMarket:
    """Restart-safe state needed to finish one market later."""

    market_id: str
    guild_id: int
    voice_channel_id: int
    text_channel_id: int
    vote_message_id: int | None
    member_ids: tuple[int, ...]
    member_names: tuple[str, ...]
    market: dict[str, Any]
    started_at: datetime
    match_uuid: str | None
    map_name: str | None
    resolution_source: str | None
    status: str
    attempts: int


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def reconcile_match(
    *,
    started_at: datetime,
    member_ids: Iterable[int],
    matches_by_member: Mapping[int, Iterable[UserFullMatchStats]],
) -> ReconciledMatch | None:
    """Find the best shared ranked match without relying on Stats.cc.

    A UUID shared by multiple squad members is stronger evidence than a single
    nearby match.  One participant is accepted as a fallback because a squad
    may contain only one configured Tracker account.  Conflicting results for
    the same UUID are rejected rather than settling a market incorrectly.
    """

    expected_ids = {int(member_id) for member_id in member_ids}
    candidates: dict[str, list[UserFullMatchStats]] = defaultdict(list)
    start = _utc(started_at)
    for member_id in expected_ids:
        for match in matches_by_member.get(member_id, ()):
            match_uuid = str(getattr(match, "match_uuid", "")).strip()
            match_time = getattr(match, "match_timestamp", None)
            session_type = str(getattr(match, "session_type", "")).lower()
            if not match_uuid or not isinstance(match_time, datetime) or "ranked" not in session_type:
                continue
            match_time = _utc(match_time)
            if match_time < start - timedelta(minutes=10) or match_time > start + RECONCILIATION_WINDOW:
                continue
            candidates[match_uuid].append(match)

    ranked: list[tuple[int, float, str, list[UserFullMatchStats]]] = []
    for match_uuid, records in candidates.items():
        # A member can occur more than once in a malformed API response; it
        # must not inflate confidence.
        by_member = {record.user_id: record for record in records}
        results = {bool(record.has_win) for record in by_member.values()}
        if len(results) != 1:
            continue
        nearest = min(abs((_utc(record.match_timestamp) - start).total_seconds()) for record in by_member.values())
        ranked.append((len(by_member), nearest, match_uuid, list(by_member.values())))
    if not ranked:
        return None

    participant_count, _, match_uuid, records = max(ranked, key=lambda item: (item[0], -item[1], item[2]))
    representative = min(records, key=lambda record: abs((_utc(record.match_timestamp) - start).total_seconds()))
    score = None
    rounds_won = getattr(representative, "round_won_count", None)
    rounds_lost = getattr(representative, "round_lost_count", None)
    if isinstance(rounds_won, int) and isinstance(rounds_lost, int) and rounds_won + rounds_lost > 0:
        score = f"{rounds_won}-{rounds_lost}"
    return ReconciledMatch(
        match_uuid=match_uuid,
        map_name=str(getattr(representative, "map_name", "Unknown") or "Unknown"),
        won=bool(representative.has_win),
        started_at=_utc(representative.match_timestamp),
        participant_count=participant_count,
        score=score,
    )


def save_pending_market(
    *,
    market: dict[str, Any],
    guild_id: int,
    voice_channel_id: int,
    text_channel_id: int,
    vote_message_id: int | None,
    member_ids: Iterable[int],
    member_names: Iterable[str],
    started_at: datetime,
) -> None:
    """Insert or refresh a pending market; safe to call after every Discord edit."""

    now = datetime.now(timezone.utc)
    market_id = str(market["market_id"])
    with database_manager.data_access_transaction() as cursor:
        cursor.execute(
            """
            INSERT INTO tribemarkets_pending_match (
                market_id, guild_id, voice_channel_id, text_channel_id,
                vote_message_id, member_ids_json, member_names_json,
                market_json, started_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(market_id) DO UPDATE SET
                vote_message_id=excluded.vote_message_id,
                member_ids_json=excluded.member_ids_json,
                member_names_json=excluded.member_names_json,
                market_json=excluded.market_json,
                updated_at=excluded.updated_at
            """,
            (
                market_id,
                guild_id,
                voice_channel_id,
                text_channel_id,
                vote_message_id,
                json.dumps([int(value) for value in member_ids]),
                json.dumps([str(value) for value in member_names]),
                json.dumps(market),
                _utc(started_at).isoformat(),
                now.isoformat(),
            ),
        )


def list_pending_markets(*, now: datetime | None = None) -> list[PendingMarket]:
    """Return unresolved markets inside the retry retention window."""

    cutoff = _utc(now or datetime.now(timezone.utc)) - RECONCILIATION_RETENTION
    rows = (
        database_manager.get_cursor()
        .execute(
            """
        SELECT market_id, guild_id, voice_channel_id, text_channel_id,
               vote_message_id, member_ids_json, member_names_json,
               market_json, started_at, match_uuid, map_name,
               resolution_source, status, attempts
        FROM tribemarkets_pending_match
        WHERE status != 'resolved' AND started_at >= ?
        ORDER BY started_at ASC
        """,
            (cutoff.isoformat(),),
        )
        .fetchall()
    )
    return [
        PendingMarket(
            market_id=str(row[0]),
            guild_id=int(row[1]),
            voice_channel_id=int(row[2]),
            text_channel_id=int(row[3]),
            vote_message_id=int(row[4]) if row[4] is not None else None,
            member_ids=tuple(int(value) for value in json.loads(row[5])),
            member_names=tuple(str(value) for value in json.loads(row[6])),
            market=dict(json.loads(row[7])),
            started_at=_utc(datetime.fromisoformat(row[8])),
            match_uuid=str(row[9]) if row[9] is not None else None,
            map_name=str(row[10]) if row[10] is not None else None,
            resolution_source=str(row[11]) if row[11] is not None else None,
            status=str(row[12]),
            attempts=int(row[13]),
        )
        for row in rows
    ]


def mark_reconciled_market(
    market_id: str,
    *,
    match_uuid: str | None,
    map_name: str,
    resolution_source: str,
    status: str,
    market: dict[str, Any] | None = None,
) -> None:
    """Persist the evidence before making the external API mutation."""

    with database_manager.data_access_transaction() as cursor:
        cursor.execute(
            """
            UPDATE tribemarkets_pending_match
            SET match_uuid=?, map_name=?, resolution_source=?, status=?,
                market_json=COALESCE(?, market_json), attempts=attempts+1,
                last_attempt_at=?, updated_at=?
            WHERE market_id=?
            """,
            (
                match_uuid,
                map_name,
                resolution_source,
                status,
                json.dumps(market) if market is not None else None,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                market_id,
            ),
        )


def mark_attempted_market(market_id: str) -> None:
    """Record a failed/no-result attempt without losing the pending market."""

    with database_manager.data_access_transaction() as cursor:
        cursor.execute(
            """
            UPDATE tribemarkets_pending_match
            SET attempts=attempts+1, last_attempt_at=?, updated_at=?
            WHERE market_id=?
            """,
            (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), market_id),
        )


def mark_market_resolved(market_id: str) -> None:
    """Make reconciliation completion durable and idempotent."""

    with database_manager.data_access_transaction() as cursor:
        cursor.execute(
            """
            UPDATE tribemarkets_pending_match
            SET status='resolved', resolved_at=?, updated_at=?
            WHERE market_id=?
            """,
            (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), market_id),
        )
