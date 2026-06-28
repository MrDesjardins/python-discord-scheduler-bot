"""Unit tests for event autoban behavior."""

import asyncio
from contextlib import suppress
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from cogs import events
from cogs.events import AUTOBAN_USER_IDS, MyEventsCog


async def test_on_member_join_autobans_listed_user(monkeypatch) -> None:
    """A listed joining user is banned before the welcome-message flow."""
    mock_new_user_text_channel = AsyncMock()
    monkeypatch.setattr(events, "data_access_get_new_user_text_channel_id", mock_new_user_text_channel)
    member = Mock()
    member.id = 1177820750636400711
    member.bot = False
    member.display_name = "Autoban User"
    member.guild = SimpleNamespace(id=123, name="Test Guild", ban=AsyncMock())

    cog = MyEventsCog(Mock())

    await cog.on_member_join(member)

    member.guild.ban.assert_awaited_once_with(member, reason="User is on the bot autoban list.")
    mock_new_user_text_channel.assert_not_awaited()


def test_autoban_list_contains_requested_user_id() -> None:
    """The requested Discord user ID is configured for autoban."""
    assert 1177820750636400711 in AUTOBAN_USER_IDS


async def test_message_archive_enqueue_spools_when_queue_is_full(monkeypatch) -> None:
    """Full archive queue spills jobs to durable storage instead of waiting indefinitely."""
    cog = MyEventsCog(Mock())
    cog.message_archive_queue = asyncio.Queue(maxsize=1)
    cog.message_archive_queue.put_nowait(("create", {"message_id": 1}))
    worker_task = Mock()
    worker_task.done.return_value = False
    cog.message_archive_worker_task = worker_task
    spooled_calls = []

    def fake_spool(jobs, reason):
        spooled_calls.append((jobs, reason))
        return len(jobs)

    monkeypatch.setattr(events, "spool_message_archive_jobs", fake_spool)

    await cog._enqueue_message_archive_job(("create", {"message_id": 2}))

    assert cog.message_archive_queue.qsize() == 1
    assert spooled_calls == [([("create", {"message_id": 2})], "queue_full")]


async def test_message_archive_worker_spools_failed_batches(monkeypatch) -> None:
    """Worker persistence failures are converted into durable spool jobs."""
    cog = MyEventsCog(Mock())
    await cog.message_archive_queue.put(("create", {"message_id": 1}))
    spooled_calls = []

    def fail_process(jobs):
        raise RuntimeError("database locked")

    def fake_spool(jobs, reason):
        spooled_calls.append((jobs, reason))
        return len(jobs)

    monkeypatch.setattr(MyEventsCog, "_process_message_archive_jobs_sync", staticmethod(fail_process))
    monkeypatch.setattr(MyEventsCog, "_process_spooled_message_archive_jobs_sync", staticmethod(lambda: 0))
    monkeypatch.setattr(events, "spool_message_archive_jobs", fake_spool)

    task = asyncio.create_task(cog._message_archive_worker())
    await asyncio.wait_for(cog.message_archive_queue.join(), timeout=1)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert spooled_calls == [([("create", {"message_id": 1})], "worker_failed: database locked")]
