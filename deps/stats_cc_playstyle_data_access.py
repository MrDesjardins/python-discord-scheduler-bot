"""Persistence for playstyle rounds derived from stats.cc match telemetry."""

from collections.abc import Iterable

from deps.models import UserFullMatchStats
from deps.system_database import database_manager


def upsert_stats_cc_playstyle_rounds(matches: Iterable[UserFullMatchStats]) -> None:
    """Store per-match playstyle rounds without double-counting repeated API history."""
    rows = [
        (match.match_uuid, match.user_id, playstyle, rounds)
        for match in matches
        for playstyle, rounds in match.playstyle_rounds.items()
        if rounds > 0
    ]
    if not rows:
        return

    with database_manager.data_access_transaction() as cursor:
        cursor.executemany(
            """
            INSERT OR REPLACE INTO user_match_playstyle_rounds (
                match_uuid, user_id, playstyle_key, rounds_played
            ) VALUES (?, ?, ?, ?)
            """,
            rows,
        )
