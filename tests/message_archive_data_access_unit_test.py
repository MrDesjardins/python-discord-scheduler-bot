"""Tests for Discord message archive persistence."""

import os
import sqlite3

import pytest

import json

from deps.message_archive_data_access import (
    MAX_SPOOL_ATTEMPTS,
    archive_deleted_message_payload,
    archive_message_edit,
    archive_message_payload,
    archive_message_payloads,
    delete_spooled_message_archive_jobs,
    fetch_spooled_message_archive_jobs,
    mark_message_deleted,
    mark_spooled_message_archive_jobs_failed,
    open_archive_connection,
    spool_message_archive_jobs,
)
from deps.system_database import DATABASE_NAME_TEST, database_manager


def _payload(message_id: int = 123, content: str = "hello") -> dict:
    return {
        "message_id": message_id,
        "guild_id": 456,
        "channel_id": 789,
        "channel_name": "general",
        "channel_type": "TextChannel",
        "author_id": 111,
        "author_name": "user#0001",
        "author_display_name": "user",
        "author_is_bot": False,
        "content": content,
        "clean_content": content,
        "created_at": "2026-01-01T00:00:00+00:00",
        "edited_at": None,
        "deleted_at": None,
        "is_deleted": False,
        "message_type": "default",
        "jump_url": "https://discord.com/channels/456/789/123",
        "reference_message_id": None,
        "attachments_json": "[]",
        "embeds_json": "[]",
        "mentions_json": "[]",
        "role_mentions_json": "[]",
        "reactions_json": "[]",
        "pinned": False,
        "source": "test",
    }


def setup_function() -> None:
    os.environ.pop("MESSAGE_ARCHIVE_DATABASE", None)
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()


def test_archive_message_payload_upserts_message_and_records_events() -> None:
    archive_message_payload(_payload(content="first"), event_type="create")
    archive_message_payload(_payload(content="edited"), event_type="edit")

    row = (
        database_manager.get_cursor()
        .execute("SELECT content, is_deleted FROM archived_message WHERE message_id = 123")
        .fetchone()
    )
    event_count = (
        database_manager.get_cursor()
        .execute("SELECT COUNT(*) FROM archived_message_event WHERE message_id = 123")
        .fetchone()[0]
    )

    assert row == ("edited", 0)
    assert event_count == 2


def test_mark_message_deleted_keeps_content_and_marks_deleted() -> None:
    archive_message_payload(_payload(content="evidence"), event_type="create")
    mark_message_deleted(123, 789, 456)

    row = (
        database_manager.get_cursor()
        .execute("SELECT content, is_deleted, deleted_at FROM archived_message WHERE message_id = 123")
        .fetchone()
    )
    delete_event = (
        database_manager.get_cursor()
        .execute(
            """
        SELECT content_before
        FROM archived_message_event
        WHERE message_id = 123 AND event_type = 'delete'
        """
        )
        .fetchone()
    )

    assert row[0] == "evidence"
    assert row[1] == 1
    assert row[2] is not None
    assert delete_event == ("evidence",)


def test_archive_message_payloads_writes_batch_and_events() -> None:
    archived_count = archive_message_payloads(
        [
            _payload(message_id=1, content="one"),
            _payload(message_id=2, content="two"),
            _payload(message_id=3, content="three"),
        ],
        event_type="backfill",
    )

    message_count = database_manager.get_cursor().execute("SELECT COUNT(*) FROM archived_message").fetchone()[0]
    event_count = database_manager.get_cursor().execute("SELECT COUNT(*) FROM archived_message_event").fetchone()[0]

    assert archived_count == 3
    assert message_count == 3
    assert event_count == 3


def test_backfill_events_are_idempotent_when_backfill_runs_again() -> None:
    archive_message_payloads([_payload(message_id=1, content="one")], event_type="backfill")
    archive_message_payloads([_payload(message_id=1, content="one updated")], event_type="backfill")

    row = database_manager.get_cursor().execute("SELECT content FROM archived_message WHERE message_id = 1").fetchone()
    backfill_event_count = (
        database_manager.get_cursor()
        .execute("SELECT COUNT(*) FROM archived_message_event WHERE message_id = 1 AND event_type = 'backfill'")
        .fetchone()[0]
    )

    assert row == ("one updated",)
    assert backfill_event_count == 1


def test_archive_connection_can_target_explicit_database_without_global_manager(tmp_path) -> None:
    archive_db = tmp_path / "archive.db"

    with open_archive_connection(str(archive_db)) as conn:
        archive_message_payload(_payload(message_id=987, content="isolated"), event_type="create", conn=conn)

    with sqlite3.connect(archive_db) as conn:
        row = conn.execute("SELECT content FROM archived_message WHERE message_id = 987").fetchone()

    assert row == ("isolated",)


def test_spooled_archive_jobs_can_be_fetched_marked_and_deleted() -> None:
    job = ("create", _payload(message_id=321, content="queued evidence"))

    spooled_count = spool_message_archive_jobs([job], "unit_test")
    spooled_jobs = fetch_spooled_message_archive_jobs()

    assert spooled_count == 1
    assert len(spooled_jobs) == 1
    spool_id, fetched_job = spooled_jobs[0]
    assert fetched_job == job

    mark_spooled_message_archive_jobs_failed([spool_id], "retry failed")
    row = (
        database_manager.get_cursor()
        .execute("SELECT attempts, last_error FROM archived_message_job_spool WHERE id = ?", (spool_id,))
        .fetchone()
    )

    assert row == (1, "retry failed")
    assert delete_spooled_message_archive_jobs([spool_id]) == 1
    assert fetch_spooled_message_archive_jobs() == []


def test_spooled_archive_jobs_are_retried_and_removed() -> None:
    from cogs.events import MyEventsCog

    job = ("create", _payload(message_id=654, content="retried evidence"))

    spool_message_archive_jobs([job], "unit_test")
    processed_count = MyEventsCog._process_spooled_message_archive_jobs_sync()

    row = (
        database_manager.get_cursor().execute("SELECT content FROM archived_message WHERE message_id = 654").fetchone()
    )

    assert processed_count == 1
    assert row == ("retried evidence",)
    assert fetch_spooled_message_archive_jobs() == []


def test_archive_payload_failure_raises_and_rolls_back() -> None:
    payload = _payload(message_id=999, content="will rollback")
    bad_payload = _payload(message_id=1000, content="bad")
    del bad_payload["author_id"]

    with pytest.raises((KeyError, sqlite3.Error)):
        archive_message_payloads([payload, bad_payload], event_type="create")

    message_count = database_manager.get_cursor().execute("SELECT COUNT(*) FROM archived_message").fetchone()[0]

    assert message_count == 0


def test_archive_message_edit_records_single_before_after_event() -> None:
    before_payload = _payload(content="before")
    after_payload = _payload(content="after")

    archive_message_payload(before_payload, event_type="create")
    archive_message_edit(before_payload, after_payload)

    row = (
        database_manager.get_cursor().execute("SELECT content FROM archived_message WHERE message_id = 123").fetchone()
    )
    edit_events = (
        database_manager.get_cursor()
        .execute(
            """
        SELECT content_before, content_after
        FROM archived_message_event
        WHERE message_id = 123 AND event_type = 'edit'
        """
        )
        .fetchall()
    )

    assert row == ("after",)
    assert edit_events == [("before", "after")]


def test_mark_message_deleted_is_idempotent() -> None:
    archive_message_payload(_payload(content="evidence"), event_type="create")
    mark_message_deleted(123, 789, 456)
    mark_message_deleted(123, 789, 456)

    delete_event_count = (
        database_manager.get_cursor()
        .execute("SELECT COUNT(*) FROM archived_message_event WHERE message_id = 123 AND event_type = 'delete'")
        .fetchone()[0]
    )

    assert delete_event_count == 1


def test_archive_deleted_message_payload_preserves_content_and_is_idempotent() -> None:
    payload = _payload(content="cached evidence")

    archive_deleted_message_payload(payload)
    archive_deleted_message_payload(payload)

    row = (
        database_manager.get_cursor()
        .execute("SELECT content, is_deleted FROM archived_message WHERE message_id = 123")
        .fetchone()
    )
    delete_event_count = (
        database_manager.get_cursor()
        .execute("SELECT COUNT(*) FROM archived_message_event WHERE message_id = 123 AND event_type = 'delete'")
        .fetchone()[0]
    )

    assert row == ("cached evidence", 1)
    assert delete_event_count == 1


def test_spooled_job_is_dead_lettered_after_max_attempts(tmp_path, monkeypatch) -> None:
    dead_letter_path = tmp_path / "dead_letter.jsonl"
    monkeypatch.setenv("MESSAGE_ARCHIVE_FAILED_JOB_LOG", str(dead_letter_path))

    job = ("create", _payload(message_id=777, content="poison"))
    spool_message_archive_jobs([job], "unit_test")
    spool_id = fetch_spooled_message_archive_jobs()[0][0]

    # The final failed attempt reaches MAX_SPOOL_ATTEMPTS and dead-letters the job.
    for _ in range(MAX_SPOOL_ATTEMPTS):
        mark_spooled_message_archive_jobs_failed([spool_id], "retry failed")

    remaining = (
        database_manager.get_cursor()
        .execute("SELECT COUNT(*) FROM archived_message_job_spool WHERE id = ?", (spool_id,))
        .fetchone()[0]
    )
    dead_letter_lines = dead_letter_path.read_text(encoding="utf-8").strip().splitlines()
    dead_letter_record = json.loads(dead_letter_lines[-1])

    assert remaining == 0
    assert fetch_spooled_message_archive_jobs() == []
    assert dead_letter_record["job_kind"] == "create"
    assert dead_letter_record["payload"]["message_id"] == 777
    assert "max_attempts_exceeded" in dead_letter_record["reason"]
