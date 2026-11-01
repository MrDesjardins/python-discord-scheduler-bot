"""Tests for finishing match-start GIFs from R6 Tracker, independently of TribeMarkets."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from deps import bot_common_actions
from deps.match_gif_r6_tracker import find_r6_tracker_match_for_gif, match_end_result_from_r6_tracker
from deps.models import UserQueueForStats, UserWithUserMatchInfo

GIF_STARTED_AT = datetime(2026, 10, 31, 6, 42, 39, tzinfo=timezone.utc)


def tracker_match(
    *,
    user_id: int = 1,
    uuid: str = "match-1",
    started_at: datetime = GIF_STARTED_AT - timedelta(minutes=1),
    duration_minutes: int = 36,
    won: bool = True,
    rounds: tuple[int, int] = (5, 3),
    session_type: str = "Ranked",
    is_rollback: bool = False,
    map_name: str = "Kanal",
):
    """An R6 Tracker match; like the real API, ``match_timestamp`` is when the match ENDED."""
    return SimpleNamespace(
        user_id=user_id,
        match_uuid=uuid,
        match_timestamp=started_at + timedelta(minutes=duration_minutes),
        match_duration_ms=duration_minutes * 60_000,
        session_type=session_type,
        is_rollback=is_rollback,
        has_win=won,
        map_name=map_name,
        round_won_count=rounds[0],
        round_lost_count=rounds[1],
    )


def awaiting_record(**overrides):
    record = {
        "guild_id": 10,
        "voice_channel_id": 20,
        "text_channel_id": 30,
        "message_id": 999,
        "member_ids": [1, 2],
        "started_at": GIF_STARTED_AT.isoformat(),
    }
    record.update(overrides)
    return record


def test_matches_the_match_that_started_with_the_gif():
    match = tracker_match()
    assert find_r6_tracker_match_for_gif(GIF_STARTED_AT, [1], {1: [match]}) is match


def test_previous_match_ending_just_before_the_gif_is_not_credited_to_it():
    """Back-to-back matches: the previous one's END time is right before the GIF, its START is not."""
    previous = tracker_match(uuid="previous", started_at=GIF_STARTED_AT - timedelta(minutes=38), duration_minutes=36)
    assert find_r6_tracker_match_for_gif(GIF_STARTED_AT, [1], {1: [previous]}) is None


def test_ignores_unranked_rollback_and_far_matches():
    matches = [
        tracker_match(uuid="standard", session_type="Standard"),
        tracker_match(uuid="rollback", is_rollback=True),
        tracker_match(uuid="later", started_at=GIF_STARTED_AT + timedelta(minutes=40)),
        tracker_match(uuid="no-duration", duration_minutes=0),
    ]
    assert find_r6_tracker_match_for_gif(GIF_STARTED_AT, [1], {1: matches}) is None


def test_prefers_match_shared_by_more_squad_members():
    closest_solo = tracker_match(user_id=1, uuid="solo", started_at=GIF_STARTED_AT)
    shared = [
        tracker_match(user_id=uid, uuid="shared", started_at=GIF_STARTED_AT - timedelta(minutes=4)) for uid in (1, 2)
    ]
    found = find_r6_tracker_match_for_gif(GIF_STARTED_AT, [1, 2], {1: [closest_solo, shared[0]], 2: [shared[1]]})
    assert found is not None and found.match_uuid == "shared"


def test_rejects_match_whose_members_disagree_on_outcome():
    matches = {1: [tracker_match(user_id=1, won=True)], 2: [tracker_match(user_id=2, won=False)]}
    assert find_r6_tracker_match_for_gif(GIF_STARTED_AT, [1, 2], matches) is None


def test_match_end_result_uses_rounds_and_falls_back_to_outcome():
    result = match_end_result_from_r6_tracker(tracker_match(won=False, rounds=(2, 4)))
    assert (result.won, result.our_score, result.their_score, result.map_name) == (False, 2, 4, "Kanal")
    assert result.is_match_complete
    no_rounds = match_end_result_from_r6_tracker(tracker_match(won=True, rounds=(0, 0)))
    assert (no_rounds.our_score, no_rounds.their_score) == (1, 0)


def _guild_with_member():
    member = MagicMock(spec=discord.Member)
    member.id = 1
    member.display_name = "PlayerOne"
    guild = MagicMock(spec=discord.Guild)
    guild.get_member = MagicMock(side_effect=lambda uid: member if uid == 1 else None)
    return guild


@pytest.mark.asyncio
async def test_finish_edits_gif_with_final_score_and_clears_records():
    message = MagicMock()
    message.edit = AsyncMock()
    record = awaiting_record()
    with (
        patch.object(bot_common_actions, "data_access_get_guild", AsyncMock(return_value=_guild_with_member())),
        patch.object(bot_common_actions, "generate_match_end_static_summary", AsyncMock(return_value=b"PNG")),
        patch.object(bot_common_actions, "data_access_get_message", AsyncMock(return_value=message)),
        patch.object(bot_common_actions, "data_access_get_match_gif_awaiting_result", AsyncMock(return_value=record)),
        patch.object(
            bot_common_actions,
            "data_access_get_pending_match_start_gif_message",
            AsyncMock(return_value={"message_id": 999}),
        ),
        patch.object(bot_common_actions, "data_access_clear_match_gif_awaiting_result") as clear_awaiting,
        patch.object(bot_common_actions, "data_access_clear_pending_match_start_gif_message") as clear_pending,
    ):
        await bot_common_actions._finish_match_gif_from_r6_tracker(record, tracker_match())

    content = message.edit.await_args.kwargs["content"]
    assert "Good luck!" in content and "**Won 5-3**" in content and "Kanal" in content
    assert message.edit.await_args.kwargs["attachments"][0].filename == "match_result.png"
    clear_awaiting.assert_called_once_with(999)
    clear_pending.assert_called_once_with(10, 20)


@pytest.mark.asyncio
async def test_finish_keeps_newer_match_pending_slot():
    """The voice channel slot already belongs to the squad's next match: leave it alone."""
    message = MagicMock()
    message.edit = AsyncMock()
    record = awaiting_record()
    with (
        patch.object(bot_common_actions, "data_access_get_guild", AsyncMock(return_value=_guild_with_member())),
        patch.object(bot_common_actions, "generate_match_end_static_summary", AsyncMock(return_value=b"PNG")),
        patch.object(bot_common_actions, "data_access_get_message", AsyncMock(return_value=message)),
        patch.object(bot_common_actions, "data_access_get_match_gif_awaiting_result", AsyncMock(return_value=record)),
        patch.object(
            bot_common_actions,
            "data_access_get_pending_match_start_gif_message",
            AsyncMock(return_value={"message_id": 1234}),
        ),
        patch.object(bot_common_actions, "data_access_clear_match_gif_awaiting_result"),
        patch.object(bot_common_actions, "data_access_clear_pending_match_start_gif_message") as clear_pending,
    ):
        await bot_common_actions._finish_match_gif_from_r6_tracker(record, tracker_match())

    message.edit.assert_awaited_once()
    clear_pending.assert_not_called()


@pytest.mark.asyncio
async def test_finish_loses_race_to_stats_cc():
    """stats.cc finished the message while the PNG was rendering: its result stands."""
    message = MagicMock()
    message.edit = AsyncMock()
    with (
        patch.object(bot_common_actions, "data_access_get_guild", AsyncMock(return_value=_guild_with_member())),
        patch.object(bot_common_actions, "generate_match_end_static_summary", AsyncMock(return_value=b"PNG")),
        patch.object(bot_common_actions, "data_access_get_message", AsyncMock(return_value=message)),
        patch.object(bot_common_actions, "data_access_get_match_gif_awaiting_result", AsyncMock(return_value=None)),
    ):
        await bot_common_actions._finish_match_gif_from_r6_tracker(awaiting_record(), tracker_match())

    message.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_finish_drops_record_when_message_was_deleted():
    message = MagicMock()
    message.edit = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "gone"))
    record = awaiting_record()
    with (
        patch.object(bot_common_actions, "data_access_get_guild", AsyncMock(return_value=_guild_with_member())),
        patch.object(bot_common_actions, "generate_match_end_static_summary", AsyncMock(return_value=b"PNG")),
        patch.object(bot_common_actions, "data_access_get_message", AsyncMock(return_value=message)),
        patch.object(bot_common_actions, "data_access_get_match_gif_awaiting_result", AsyncMock(return_value=record)),
        patch.object(bot_common_actions, "data_access_clear_match_gif_awaiting_result") as clear_awaiting,
    ):
        await bot_common_actions._finish_match_gif_from_r6_tracker(record, tracker_match())

    clear_awaiting.assert_called_once_with(999)


@pytest.mark.asyncio
async def test_leave_voice_batch_finishes_gif_without_extra_fetch_and_without_tribemarkets(monkeypatch):
    monkeypatch.setattr(bot_common_actions, "TRIBEMARKETS_ENABLED", False)
    fetched = UserWithUserMatchInfo(UserQueueForStats(SimpleNamespace(id=1), 10, GIF_STARTED_AT), [tracker_match()])
    with (
        patch.object(
            bot_common_actions, "data_access_list_match_gifs_awaiting_result", return_value=[awaiting_record()]
        ),
        patch.object(bot_common_actions, "download_full_matches_async", AsyncMock()) as download,
        patch.object(bot_common_actions, "_finish_match_gif_from_r6_tracker", AsyncMock()) as finish,
    ):
        await bot_common_actions.finish_match_gifs_from_r6_tracker([fetched])

    download.assert_not_awaited()
    assert finish.await_args.args[1].match_uuid == "match-1"


@pytest.mark.asyncio
async def test_periodic_poll_fetches_one_member_per_old_enough_gif():
    now = datetime.now(timezone.utc)
    old = awaiting_record(message_id=1, started_at=(now - timedelta(minutes=30)).isoformat())
    young = awaiting_record(message_id=2, member_ids=[3], started_at=(now - timedelta(minutes=5)).isoformat())
    user_info = SimpleNamespace(id=1, ubisoft_username_active="PlayerOne")
    with (
        patch.object(bot_common_actions, "data_access_list_match_gifs_awaiting_result", return_value=[old, young]),
        patch.object(
            bot_common_actions, "data_access_get_pending_match_start_gif_message", AsyncMock(return_value=None)
        ),
        patch.object(bot_common_actions, "fetch_user_info_by_user_id", AsyncMock(return_value=user_info)) as lookup,
        patch.object(bot_common_actions, "data_access_set_match_gif_awaiting_result") as save_attempt,
        patch.object(bot_common_actions, "download_full_matches_async", AsyncMock(return_value=[])) as download,
    ):
        await bot_common_actions.finish_match_gifs_from_r6_tracker()

    lookup.assert_awaited_once_with(1)
    queued = download.await_args.args[0]
    assert [entry.user_info.id for entry in queued] == [1]
    assert save_attempt.call_args.args[0]["attempts"] == 1


@pytest.mark.asyncio
async def test_periodic_poll_rotates_to_next_member_after_an_attempt():
    now = datetime.now(timezone.utc)
    record = awaiting_record(attempts=1, started_at=(now - timedelta(minutes=30)).isoformat())
    user_info = SimpleNamespace(id=2, ubisoft_username_active="PlayerTwo")
    with (
        patch.object(bot_common_actions, "data_access_list_match_gifs_awaiting_result", return_value=[record]),
        patch.object(
            bot_common_actions, "data_access_get_pending_match_start_gif_message", AsyncMock(return_value=None)
        ),
        patch.object(bot_common_actions, "fetch_user_info_by_user_id", AsyncMock(return_value=user_info)) as lookup,
        patch.object(bot_common_actions, "data_access_set_match_gif_awaiting_result"),
        patch.object(bot_common_actions, "download_full_matches_async", AsyncMock(return_value=[])),
    ):
        await bot_common_actions.finish_match_gifs_from_r6_tracker()

    lookup.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_periodic_poll_leaves_live_stats_cc_match_to_stats_cc():
    now = datetime.now(timezone.utc)
    record = awaiting_record(started_at=(now - timedelta(minutes=30)).isoformat())
    live_slot = {"message_id": 999, "last_result_key": "live:LEADING:3-2:Kanal"}
    with (
        patch.object(bot_common_actions, "data_access_list_match_gifs_awaiting_result", return_value=[record]),
        patch.object(
            bot_common_actions, "data_access_get_pending_match_start_gif_message", AsyncMock(return_value=live_slot)
        ),
        patch.object(bot_common_actions, "download_full_matches_async", AsyncMock()) as download,
    ):
        await bot_common_actions.finish_match_gifs_from_r6_tracker()

    download.assert_not_awaited()
