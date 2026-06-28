#!/usr/bin/env python3
"""Merge archived messages/events from a source SQLite DB into a target DB.

Use this to push a locally backfilled message archive into the production
database without touching any other tables. The merge is idempotent:

- ``archived_message`` is keyed by ``message_id`` (PRIMARY KEY), so rows are
  inserted with ``INSERT OR IGNORE`` and re-running never duplicates them.
- ``archived_message_event`` has an autoincrement ``id`` with no unique
  constraint, so we copy every column except ``id`` and guard against
  re-inserting an identical event tuple.

A consistent snapshot of the target (production) DB is written next to it as
``<target>.bak-<UTC timestamp>`` before any rows are merged. Only the two
archive tables are touched; every other table in the target is left untouched.

Stop the bot service before running so the archive worker is not writing to the
target database concurrently.

Example:
    python3 scripts/merge_message_archive.py \
        --source /path/to/local/user_activity.db \
        --target /path/to/prod/user_activity.db
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ARCHIVE_TABLE = "archived_message"
EVENT_TABLE = "archived_message_event"
EVENT_COLUMNS = (
    "message_id",
    "guild_id",
    "channel_id",
    "event_type",
    "event_at",
    "content_before",
    "content_after",
    "source",
)


def _count(conn: sqlite3.Connection, table: str, schema: str = "main") -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]


def backup_database(target: Path) -> Path:
    """Make a consistent snapshot of the target DB using the SQLite backup API.

    The backup API is WAL-safe (unlike a raw file copy, which can miss the -wal
    file), so the snapshot is a complete, restorable database on its own.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = target.with_name(f"{target.name}.bak-{timestamp}")
    source_conn = sqlite3.connect(str(target))
    backup_conn = sqlite3.connect(str(backup_path))
    try:
        source_conn.backup(backup_conn)
    finally:
        backup_conn.close()
        source_conn.close()
    print(f"backup: {backup_path}")
    return backup_path


def merge(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Source DB not found: {source}")
    if not target.exists():
        raise FileNotFoundError(f"Target DB not found: {target}")

    backup_database(target)

    conn = sqlite3.connect(str(target))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("ATTACH DATABASE ? AS src;", (str(source),))

        before_messages = _count(conn, ARCHIVE_TABLE)
        before_events = _count(conn, EVENT_TABLE)
        src_messages = _count(conn, ARCHIVE_TABLE, schema="src")
        src_events = _count(conn, EVENT_TABLE, schema="src")

        with conn:  # single transaction; rolls back on error
            conn.execute(
                f"""
                INSERT OR IGNORE INTO main.{ARCHIVE_TABLE}
                SELECT * FROM src.{ARCHIVE_TABLE};
                """
            )
            columns = ", ".join(EVENT_COLUMNS)
            conn.execute(
                f"""
                INSERT INTO main.{EVENT_TABLE} ({columns})
                SELECT {columns}
                FROM src.{EVENT_TABLE} AS s
                WHERE NOT EXISTS (
                    SELECT 1 FROM main.{EVENT_TABLE} AS m
                    WHERE m.message_id = s.message_id
                      AND m.event_type = s.event_type
                      AND m.event_at = s.event_at
                );
                """
            )

        after_messages = _count(conn, ARCHIVE_TABLE)
        after_events = _count(conn, EVENT_TABLE)
        conn.execute("DETACH DATABASE src;")
    finally:
        conn.close()

    print(f"source: {src_messages} messages, {src_events} events")
    print(f"messages: {before_messages} -> {after_messages} (+{after_messages - before_messages})")
    print(f"events:   {before_events} -> {after_events} (+{after_events - before_events})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, type=Path, help="Local DB holding the backfilled archive.")
    parser.add_argument("--target", required=True, type=Path, help="Production DB to merge into.")
    args = parser.parse_args()

    merge(args.source, args.target)


if __name__ == "__main__":
    main()
