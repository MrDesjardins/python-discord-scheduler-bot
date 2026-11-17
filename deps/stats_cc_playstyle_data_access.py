"""Persistence for playstyle rounds derived from stats.cc match telemetry."""

from collections.abc import Iterable
from typing import Any

from deps.models import UserFullMatchStats
from deps.system_database import database_manager


def _upsert_rows(cursor: Any, rows: list[tuple[str, int, str, int]]) -> None:
    cursor.executemany(
        """
        INSERT OR REPLACE INTO user_match_playstyle_rounds (
            match_uuid, user_id, playstyle_key, rounds_played
        ) VALUES (?, ?, ?, ?)
        """,
        rows,
    )


def upsert_stats_cc_playstyle_rounds(matches: Iterable[UserFullMatchStats], cursor: Any = None) -> None:
    """Store per-match playstyle rounds without double-counting repeated API history."""
    rows = [
        (match.match_uuid, match.user_id, playstyle, rounds)
        for match in matches
        for playstyle, rounds in match.playstyle_rounds.items()
        if rounds > 0
    ]
    if not rows:
        return

    if cursor is not None:
        _upsert_rows(cursor, rows)
        return

    with database_manager.data_access_transaction() as cursor:
        _upsert_rows(cursor, rows)
