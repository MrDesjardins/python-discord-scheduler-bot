"""SQLite persistence for Discord message moderation archives."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import discord

ARCHIVE_DATABASE_ENV = "MESSAGE_ARCHIVE_DATABASE"
ARCHIVE_FAILED_JOB_LOG_ENV = "MESSAGE_ARCHIVE_FAILED_JOB_LOG"
DEFAULT_ARCHIVE_FAILED_JOB_LOG = "message_archive_failed_jobs.jsonl"
# Durable spool jobs that keep failing are dead-lettered to the JSONL log after this many attempts.
MAX_SPOOL_ATTEMPTS = 20

# The archive schema is created with IF NOT EXISTS, so it only needs to run once per database
# path per process. Caching avoids re-running the full DDL script (and a DROP INDEX) on every
# connection, which the worker opens per batch and on every idle poll.
_SCHEMA_INITIALIZED_PATHS: set[str] = set()
_SCHEMA_INIT_LOCK = threading.Lock()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _message_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def serialize_discord_message(message: discord.Message, source: str = "gateway") -> dict[str, Any]:
    """Convert a Discord message into stable database fields."""
    guild = message.guild
    channel = message.channel
    author = message.author
    return {
        "message_id": message.id,
        "guild_id": guild.id if guild is not None else None,
        "channel_id": channel.id,
        "channel_name": getattr(channel, "name", None),
        "channel_type": type(channel).__name__,
        "author_id": author.id,
        "author_name": str(author),
        "author_display_name": getattr(author, "display_name", None),
        "author_is_bot": bool(author.bot),
        "content": message.content or "",
        "clean_content": message.clean_content or "",
        "created_at": _message_datetime(message.created_at),
        "edited_at": _message_datetime(message.edited_at),
        "deleted_at": None,
        "is_deleted": False,
        "message_type": str(message.type),
        "jump_url": message.jump_url,
        "reference_message_id": message.reference.message_id if message.reference else None,
        "attachments_json": _json_dump(
            [
                {
                    "id": attachment.id,
                    "filename": attachment.filename,
                    "url": attachment.url,
                    "content_type": attachment.content_type,
                    "size": attachment.size,
                }
                for attachment in message.attachments
            ]
        ),
        "embeds_json": _json_dump([embed.to_dict() for embed in message.embeds]),
        "mentions_json": _json_dump([user.id for user in message.mentions]),
        "role_mentions_json": _json_dump([role.id for role in message.role_mentions]),
        "reactions_json": _json_dump(
            [
                {
                    "emoji": str(reaction.emoji),
                    "count": reaction.count,
                }
                for reaction in message.reactions
            ]
        ),
        "pinned": bool(message.pinned),
        "source": source,
    }


def _default_database_path() -> str:
    env_database = os.getenv(ARCHIVE_DATABASE_ENV)
    if env_database:
        return env_database

    # Import lazily so tools that pass an explicit archive DB do not initialize
    # the production database as a side effect.
    from deps.system_database import database_manager

    return database_manager.get_database_name()


def _database_path(database_path: str | None = None) -> str:
    return database_path or _default_database_path()


def _init_archive_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS archived_message (
            message_id INTEGER PRIMARY KEY,
            guild_id INTEGER NULL,
            channel_id INTEGER NOT NULL,
            channel_name TEXT NULL,
            channel_type TEXT NULL,
            author_id INTEGER NOT NULL,
            author_name TEXT NOT NULL,
            author_display_name TEXT NULL,
            author_is_bot BOOLEAN NOT NULL DEFAULT 0,
            content TEXT NOT NULL DEFAULT '',
            clean_content TEXT NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL,
            edited_at DATETIME NULL,
            deleted_at DATETIME NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT 0,
            message_type TEXT NULL,
            jump_url TEXT NULL,
            reference_message_id INTEGER NULL,
            attachments_json TEXT NOT NULL DEFAULT '[]',
            embeds_json TEXT NOT NULL DEFAULT '[]',
            mentions_json TEXT NOT NULL DEFAULT '[]',
            role_mentions_json TEXT NOT NULL DEFAULT '[]',
            reactions_json TEXT NOT NULL DEFAULT '[]',
            pinned BOOLEAN NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'gateway',
            persisted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS archived_message_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            guild_id INTEGER NULL,
            channel_id INTEGER NOT NULL,
            event_type TEXT NOT NULL CHECK(event_type IN ('create', 'edit', 'delete', 'backfill')),
            event_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            content_before TEXT NULL,
            content_after TEXT NULL,
            source TEXT NOT NULL DEFAULT 'gateway',
            FOREIGN KEY(message_id) REFERENCES archived_message(message_id)
        );

        CREATE INDEX IF NOT EXISTS idx_archived_message_author
        ON archived_message(guild_id, author_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_archived_message_channel_time
        ON archived_message(guild_id, channel_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_archived_message_deleted_partial
        ON archived_message(guild_id, deleted_at DESC)
        WHERE is_deleted = 1;

        CREATE INDEX IF NOT EXISTS idx_archived_message_event_message
        ON archived_message_event(message_id, event_at DESC);

        CREATE TABLE IF NOT EXISTS archived_message_job_spool (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_kind TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_error TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_archived_message_job_spool_attempts
        ON archived_message_job_spool(attempts, created_at);
        """
    )
    conn.execute("DROP INDEX IF EXISTS idx_archived_message_deleted;")
    conn.commit()


def _ensure_archive_schema(conn: sqlite3.Connection, resolved_path: str) -> None:
    """Run the schema DDL at most once per database path per process."""
    # An in-memory database is a fresh, private schema for every connection, so it must
    # always be initialized and can never be cached.
    if resolved_path == ":memory:":
        _init_archive_schema(conn)
        return
    if resolved_path in _SCHEMA_INITIALIZED_PATHS:
        return
    with _SCHEMA_INIT_LOCK:
        if resolved_path in _SCHEMA_INITIALIZED_PATHS:
            return
        _init_archive_schema(conn)
        _SCHEMA_INITIALIZED_PATHS.add(resolved_path)


@contextmanager
def open_archive_connection(database_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """Open an isolated SQLite connection for archive writes."""
    resolved_path = _database_path(database_path)
    if resolved_path != ":memory:":
        Path(resolved_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(resolved_path, timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.row_factory = sqlite3.Row
        _ensure_archive_schema(conn, resolved_path)
        yield conn
    finally:
        conn.close()


@contextmanager
def _transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Cursor]:
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield cursor
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        cursor.close()


def _failed_job_log_path() -> str:
    return os.getenv(ARCHIVE_FAILED_JOB_LOG_ENV, DEFAULT_ARCHIVE_FAILED_JOB_LOG)


def _archive_job_to_row(job: tuple[str, Any]) -> tuple[str, str]:
    kind, payload = job
    return kind, _json_dump(payload)


def _archive_job_from_row(row: sqlite3.Row) -> tuple[int, tuple[str, Any]]:
    return int(row["id"]), (str(row["job_kind"]), json.loads(row["payload_json"]))


def _append_archive_jobs_to_file(jobs: list[tuple[str, Any]], reason: str | None) -> None:
    path = Path(_failed_job_log_path())
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as file:
        for job in jobs:
            kind, payload_json = _archive_job_to_row(job)
            file.write(
                _json_dump(
                    {
                        "created_at": now,
                        "job_kind": kind,
                        "payload": json.loads(payload_json),
                        "reason": reason,
                    }
                )
                + "\n"
            )


def spool_message_archive_jobs(
    jobs: list[tuple[str, Any]],
    reason: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Persist archive jobs for later retry, falling back to JSONL if SQLite is unavailable."""
    if not jobs:
        return 0

    try:
        if conn is not None:
            with _transaction(conn) as cursor:
                _spool_message_archive_jobs_in_transaction(cursor, jobs, reason)
            return len(jobs)

        with open_archive_connection() as archive_conn:
            return spool_message_archive_jobs(jobs, reason=reason, conn=archive_conn)
    except Exception:
        _append_archive_jobs_to_file(jobs, reason)
        return len(jobs)


def _spool_message_archive_jobs_in_transaction(
    cursor: sqlite3.Cursor,
    jobs: list[tuple[str, Any]],
    reason: str | None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for job in jobs:
        kind, payload_json = _archive_job_to_row(job)
        rows.append(
            {
                "job_kind": kind,
                "payload_json": payload_json,
                "updated_at": now,
                "last_error": reason,
            }
        )
    cursor.executemany(
        """
        INSERT INTO archived_message_job_spool (
            job_kind,
            payload_json,
            updated_at,
            last_error
        )
        VALUES (
            :job_kind,
            :payload_json,
            :updated_at,
            :last_error
        )
        """,
        rows,
    )


def fetch_spooled_message_archive_jobs(
    limit: int = 100,
    max_attempts: int = MAX_SPOOL_ATTEMPTS,
    conn: sqlite3.Connection | None = None,
) -> list[tuple[int, tuple[str, Any]]]:
    """Fetch durable archive jobs that are still eligible for retry."""
    if conn is not None:
        rows = conn.execute(
            """
            SELECT id, job_kind, payload_json
            FROM archived_message_job_spool
            WHERE attempts < :max_attempts
            ORDER BY id
            LIMIT :limit
            """,
            {"max_attempts": max_attempts, "limit": limit},
        ).fetchall()
        return [_archive_job_from_row(row) for row in rows]

    with open_archive_connection() as archive_conn:
        return fetch_spooled_message_archive_jobs(limit=limit, max_attempts=max_attempts, conn=archive_conn)


def delete_spooled_message_archive_jobs(ids: list[int], conn: sqlite3.Connection | None = None) -> int:
    """Delete durable archive jobs after they are successfully persisted."""
    if not ids:
        return 0
    if conn is not None:
        placeholders = ",".join("?" for _ in ids)
        with _transaction(conn) as cursor:
            cursor.execute(f"DELETE FROM archived_message_job_spool WHERE id IN ({placeholders})", ids)
        return len(ids)

    with open_archive_connection() as archive_conn:
        return delete_spooled_message_archive_jobs(ids, conn=archive_conn)


def _dead_letter_exhausted_spool_jobs(cursor: sqlite3.Cursor, ids: list[int], error: str) -> None:
    """Move spool jobs that exhausted their retries to the JSONL log and delete them."""
    placeholders = ",".join("?" for _ in ids)
    exhausted = cursor.execute(
        f"""
        SELECT id, job_kind, payload_json
        FROM archived_message_job_spool
        WHERE id IN ({placeholders}) AND attempts >= ?
        """,
        [*ids, MAX_SPOOL_ATTEMPTS],
    ).fetchall()
    if not exhausted:
        return
    dead_jobs = [_archive_job_from_row(row)[1] for row in exhausted]
    _append_archive_jobs_to_file(dead_jobs, f"max_attempts_exceeded: {error}")
    dead_ids = [int(row["id"]) for row in exhausted]
    dead_placeholders = ",".join("?" for _ in dead_ids)
    cursor.execute(f"DELETE FROM archived_message_job_spool WHERE id IN ({dead_placeholders})", dead_ids)


def mark_spooled_message_archive_jobs_failed(
    ids: list[int],
    error: str,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Increment attempts for durable archive jobs that failed retry, dead-lettering exhausted ones."""
    if not ids:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    if conn is not None:
        placeholders = ",".join("?" for _ in ids)
        with _transaction(conn) as cursor:
            cursor.execute(
                f"""
                UPDATE archived_message_job_spool
                SET attempts = attempts + 1,
                    updated_at = ?,
                    last_error = ?
                WHERE id IN ({placeholders})
                """,
                [now, error, *ids],
            )
            _dead_letter_exhausted_spool_jobs(cursor, ids, error)
        return len(ids)

    with open_archive_connection() as archive_conn:
        return mark_spooled_message_archive_jobs_failed(ids, error, conn=archive_conn)


def _insert_message_event(
    cursor: sqlite3.Cursor,
    message_id: int,
    guild_id: int | None,
    channel_id: int,
    event_type: str,
    content_before: str | None,
    content_after: str | None,
    source: str,
) -> None:
    cursor.execute(
        """
        INSERT INTO archived_message_event (
            message_id,
            guild_id,
            channel_id,
            event_type,
            event_at,
            content_before,
            content_after,
            source
        )
        VALUES (
            :message_id,
            :guild_id,
            :channel_id,
            :event_type,
            :event_at,
            :content_before,
            :content_after,
            :source
        )
        """,
        {
            "message_id": message_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "event_type": event_type,
            "event_at": datetime.now(timezone.utc).isoformat(),
            "content_before": content_before,
            "content_after": content_after,
            "source": source,
        },
    )


def _upsert_message_payload(cursor: sqlite3.Cursor, payload: dict[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO archived_message (
            message_id,
            guild_id,
            channel_id,
            channel_name,
            channel_type,
            author_id,
            author_name,
            author_display_name,
            author_is_bot,
            content,
            clean_content,
            created_at,
            edited_at,
            deleted_at,
            is_deleted,
            message_type,
            jump_url,
            reference_message_id,
            attachments_json,
            embeds_json,
            mentions_json,
            role_mentions_json,
            reactions_json,
            pinned,
            source,
            updated_at
        )
        VALUES (
            :message_id,
            :guild_id,
            :channel_id,
            :channel_name,
            :channel_type,
            :author_id,
            :author_name,
            :author_display_name,
            :author_is_bot,
            :content,
            :clean_content,
            :created_at,
            :edited_at,
            :deleted_at,
            :is_deleted,
            :message_type,
            :jump_url,
            :reference_message_id,
            :attachments_json,
            :embeds_json,
            :mentions_json,
            :role_mentions_json,
            :reactions_json,
            :pinned,
            :source,
            :updated_at
        )
        ON CONFLICT(message_id) DO UPDATE SET
            guild_id = excluded.guild_id,
            channel_id = excluded.channel_id,
            channel_name = excluded.channel_name,
            channel_type = excluded.channel_type,
            author_id = excluded.author_id,
            author_name = excluded.author_name,
            author_display_name = excluded.author_display_name,
            author_is_bot = excluded.author_is_bot,
            content = excluded.content,
            clean_content = excluded.clean_content,
            edited_at = excluded.edited_at,
            deleted_at = COALESCE(archived_message.deleted_at, excluded.deleted_at),
            is_deleted = CASE WHEN archived_message.is_deleted = 1 THEN 1 ELSE excluded.is_deleted END,
            message_type = excluded.message_type,
            jump_url = excluded.jump_url,
            reference_message_id = excluded.reference_message_id,
            attachments_json = excluded.attachments_json,
            embeds_json = excluded.embeds_json,
            mentions_json = excluded.mentions_json,
            role_mentions_json = excluded.role_mentions_json,
            reactions_json = excluded.reactions_json,
            pinned = excluded.pinned,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        {
            **payload,
            "author_is_bot": int(payload["author_is_bot"]),
            "is_deleted": int(payload["is_deleted"]),
            "pinned": int(payload["pinned"]),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _has_existing_backfill_event(cursor: sqlite3.Cursor, message_id: int) -> bool:
    row = cursor.execute(
        """
        SELECT 1
        FROM archived_message_event
        WHERE message_id = :message_id AND event_type = 'backfill'
        LIMIT 1
        """,
        {"message_id": message_id},
    ).fetchone()
    return row is not None


def _archive_message_payload_in_transaction(cursor: sqlite3.Cursor, payload: dict[str, Any], event_type: str) -> None:
    existing = cursor.execute(
        "SELECT content FROM archived_message WHERE message_id = :message_id",
        {"message_id": payload["message_id"]},
    ).fetchone()
    content_before = existing[0] if existing is not None else None

    _upsert_message_payload(cursor, payload)

    if event_type == "backfill" and _has_existing_backfill_event(cursor, payload["message_id"]):
        return

    _insert_message_event(
        cursor,
        payload["message_id"],
        payload["guild_id"],
        payload["channel_id"],
        event_type,
        content_before,
        payload["content"],
        payload["source"],
    )


def archive_message_payload(
    payload: dict[str, Any],
    event_type: str = "create",
    conn: sqlite3.Connection | None = None,
) -> int:
    """Upsert a serialized message payload and append an archive event."""
    if conn is not None:
        with _transaction(conn) as cursor:
            _archive_message_payload_in_transaction(cursor, payload, event_type)
        return 1

    with open_archive_connection() as archive_conn:
        return archive_message_payload(payload, event_type=event_type, conn=archive_conn)


def archive_message_payloads(
    payloads: list[dict[str, Any]],
    event_type: str = "backfill",
    conn: sqlite3.Connection | None = None,
) -> int:
    """Archive a batch of serialized message payloads."""
    if not payloads:
        return 0
    if conn is not None:
        with _transaction(conn) as cursor:
            for payload in payloads:
                _archive_message_payload_in_transaction(cursor, payload, event_type)
        return len(payloads)

    with open_archive_connection() as archive_conn:
        return archive_message_payloads(payloads, event_type=event_type, conn=archive_conn)


def archive_discord_message(message: discord.Message, event_type: str = "create", source: str = "gateway") -> int:
    """Archive a Discord message object."""
    return archive_message_payload(serialize_discord_message(message, source), event_type=event_type)


def archive_message_edit(
    before_payload: dict[str, Any],
    after_payload: dict[str, Any],
    conn: sqlite3.Connection | None = None,
) -> int:
    """Archive a message edit as one event with before and after content."""
    if conn is not None:
        with _transaction(conn) as cursor:
            _upsert_message_payload(cursor, after_payload)
            _insert_message_event(
                cursor,
                after_payload["message_id"],
                after_payload["guild_id"],
                after_payload["channel_id"],
                "edit",
                before_payload["content"],
                after_payload["content"],
                after_payload["source"],
            )
        return 1

    with open_archive_connection() as archive_conn:
        return archive_message_edit(before_payload, after_payload, conn=archive_conn)


def archive_deleted_message_payload(
    payload: dict[str, Any],
    deleted_at: datetime | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Archive cached delete content and mark the message deleted in one transaction."""
    deleted_at = deleted_at or datetime.now(timezone.utc)
    if conn is not None:
        with _transaction(conn) as cursor:
            _upsert_message_payload(cursor, payload)
            _mark_message_deleted_in_transaction(
                cursor,
                payload["message_id"],
                payload["channel_id"],
                payload["guild_id"],
                deleted_at,
                payload["source"],
            )
        return 1

    with open_archive_connection() as archive_conn:
        return archive_deleted_message_payload(payload, deleted_at=deleted_at, conn=archive_conn)


def _mark_message_deleted_in_transaction(
    cursor: sqlite3.Cursor,
    message_id: int,
    channel_id: int,
    guild_id: int | None,
    deleted_at: datetime,
    source: str,
) -> None:
    existing = cursor.execute(
        "SELECT content, is_deleted FROM archived_message WHERE message_id = :message_id",
        {"message_id": message_id},
    ).fetchone()
    if existing is None:
        cursor.execute(
            """
            INSERT INTO archived_message (
                message_id,
                guild_id,
                channel_id,
                author_id,
                author_name,
                content,
                clean_content,
                created_at,
                deleted_at,
                is_deleted,
                source,
                updated_at
            )
            VALUES (
                :message_id,
                :guild_id,
                :channel_id,
                0,
                'unknown',
                '',
                '',
                :created_at,
                :deleted_at,
                1,
                :source,
                :updated_at
            )
            """,
            {
                "message_id": message_id,
                "guild_id": guild_id,
                "channel_id": channel_id,
                "created_at": deleted_at.isoformat(),
                "deleted_at": deleted_at.isoformat(),
                "source": source,
                "updated_at": deleted_at.isoformat(),
            },
        )
        content_before = None
    else:
        content_before = existing[0]
        if existing[1] == 1:
            return
        cursor.execute(
            """
            UPDATE archived_message
            SET deleted_at = :deleted_at,
                is_deleted = 1,
                updated_at = :updated_at
            WHERE message_id = :message_id
            """,
            {
                "message_id": message_id,
                "deleted_at": deleted_at.isoformat(),
                "updated_at": deleted_at.isoformat(),
            },
        )

    _insert_message_event(
        cursor,
        message_id,
        guild_id,
        channel_id,
        "delete",
        content_before,
        None,
        source,
    )


def mark_message_deleted(
    message_id: int,
    channel_id: int,
    guild_id: int | None,
    deleted_at: datetime | None = None,
    source: str = "gateway",
    conn: sqlite3.Connection | None = None,
) -> int:
    """Mark an archived message as deleted, retaining any previously captured content."""
    deleted_at = deleted_at or datetime.now(timezone.utc)
    if conn is not None:
        with _transaction(conn) as cursor:
            _mark_message_deleted_in_transaction(cursor, message_id, channel_id, guild_id, deleted_at, source)
        return 1

    with open_archive_connection() as archive_conn:
        return mark_message_deleted(
            message_id, channel_id, guild_id, deleted_at=deleted_at, source=source, conn=archive_conn
        )
