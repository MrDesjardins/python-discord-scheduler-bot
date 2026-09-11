"""Tests for delayed TribeMarkets match identification."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from deps.tribemarkets_reconciliation import ReconciledMatch, match_uuid_already_assigned, reconcile_match
import deps.tribemarkets_reconciliation as reconciliation
from deps.system_database import DatabaseManager
from deps.models import UserQueueForStats, UserWithUserMatchInfo


START = datetime(2026, 8, 18, 3, 3, tzinfo=timezone.utc)


def match(*, user_id: int, uuid: str, offset_minutes: int = 2, won: bool = True, map_name: str = "Villa"):
    return SimpleNamespace(
        user_id=user_id,
        match_uuid=uuid,
        match_timestamp=START + timedelta(minutes=offset_minutes),
        session_type="ranked",
        has_win=won,
        map_name=map_name,
        round_won_count=4,
        round_lost_count=2,
        round_played_count=6,
        match_duration_ms=600000,
    )


def test_reconcile_prefers_uuid_shared_by_squad_members():
    result = reconcile_match(
        started_at=START,
        member_ids=[1, 2, 3],
        matches_by_member={
            1: [match(user_id=1, uuid="solo"), match(user_id=1, uuid="shared")],
            2: [match(user_id=2, uuid="shared")],
            3: [match(user_id=3, uuid="other", offset_minutes=1)],
        },
    )

    assert result is not None
    assert result.match_uuid == "shared"
    assert result.participant_count == 2
    assert result.map_name == "Villa"
    assert result.won is True
    assert result.score == "4-2"


def test_reconcile_accepts_one_configured_tracker_member():
    result = reconcile_match(
        started_at=START,
        member_ids=[1, 2],
        matches_by_member={1: [match(user_id=1, uuid="one")], 2: []},
    )

    assert result is not None
    assert result.match_uuid == "one"
    assert result.participant_count == 1


def test_reconcile_rejects_non_ranked_or_far_matches():
    non_ranked = match(user_id=1, uuid="casual")
    non_ranked.session_type = "standard"
    far = match(user_id=2, uuid="far", offset_minutes=400)

    assert (
        reconcile_match(
            started_at=START,
            member_ids=[1, 2],
            matches_by_member={1: [non_ranked], 2: [far]},
        )
        is None
    )


def test_reconcile_defers_a_market_that_is_too_new():
    result = reconcile_match(
        started_at=START,
        member_ids=[1, 2],
        matches_by_member={
            1: [match(user_id=1, uuid="new")],
            2: [match(user_id=2, uuid="new")],
        },
        now=START + timedelta(minutes=2),
    )

    assert result is None


def test_reconcile_rejects_future_tracker_records():
    result = reconcile_match(
        started_at=START,
        member_ids=[1, 2],
        matches_by_member={
            1: [match(user_id=1, uuid="future", offset_minutes=30)],
            2: [match(user_id=2, uuid="future", offset_minutes=30)],
        },
        now=START + timedelta(minutes=20),
    )

    assert result is None


def test_reconcile_delays_single_participant_fallback():
    result = reconcile_match(
        started_at=START,
        member_ids=[1, 2],
        matches_by_member={1: [match(user_id=1, uuid="one")], 2: []},
        now=START + timedelta(minutes=30),
    )

    assert result is None


def test_reconcile_rejects_conflicting_results_for_same_uuid():
    assert (
        reconcile_match(
            started_at=START,
            member_ids=[1, 2],
            matches_by_member={
                1: [match(user_id=1, uuid="same", won=True)],
                2: [match(user_id=2, uuid="same", won=False)],
            },
        )
        is None
    )


def test_pending_market_persistence_survives_round_trip(tmp_path, monkeypatch):
    manager = DatabaseManager(str(tmp_path / "reconciliation.db"))
    monkeypatch.setattr(reconciliation, "database_manager", manager)
    market = {
        "market_id": "market-1",
        "community_id": "tribe-1",
        "yes_outcome_id": "yes",
        "no_outcome_id": "no",
        "share_url": "https://example.test/market-1",
        "external_event_id": "discord-ranked:1:2:3",
    }

    reconciliation.save_pending_market(
        market=market,
        guild_id=10,
        voice_channel_id=20,
        text_channel_id=30,
        vote_message_id=40,
        member_ids=[1, 2],
        member_names=["Alice", "Bob"],
        started_at=START,
    )

    pending = reconciliation.list_pending_markets(now=START + timedelta(hours=1))
    assert len(pending) == 1
    assert pending[0].market_id == "market-1"
    assert pending[0].member_ids == (1, 2)
    assert pending[0].started_at == START

    reconciliation.mark_reconciled_market(
        "market-1",
        match_uuid="match-1",
        map_name="Villa",
        resolution_source="r6_tracker",
        status="matched",
    )
    assert match_uuid_already_assigned("match-1", exclude_market_id="market-2") is True
    assert match_uuid_already_assigned("match-1", exclude_market_id="market-1") is False
    reconciliation.mark_market_resolved("market-1")
    assert reconciliation.list_pending_markets(now=START + timedelta(hours=1)) == []


def test_pending_market_persistence_expires_after_retry_retention(tmp_path, monkeypatch):
    manager = DatabaseManager(str(tmp_path / "expired.db"))
    monkeypatch.setattr(reconciliation, "database_manager", manager)
    reconciliation.save_pending_market(
        market={"market_id": "old", "community_id": "tribe"},
        guild_id=1,
        voice_channel_id=2,
        text_channel_id=3,
        vote_message_id=None,
        member_ids=[1],
        member_names=["Alice"],
        started_at=START,
    )

    assert reconciliation.list_pending_markets(now=START + timedelta(days=3)) == []


@pytest.mark.asyncio
async def test_async_reconciliation_resolves_from_fetched_history(monkeypatch):
    from deps import bot_common_actions

    market = {
        "market_id": "market-async",
        "community_id": "tribe",
        "yes_outcome_id": "yes",
        "no_outcome_id": "no",
        "share_url": "https://example.test/market-async",
        "external_event_id": "discord-ranked:1:2:3",
        "title": "2026-08-18 03:03 UTC · Alice",
        "vote_message_id": 40,
    }
    pending = SimpleNamespace(
        market_id="market-async",
        guild_id=10,
        voice_channel_id=20,
        text_channel_id=30,
        vote_message_id=40,
        member_ids=(1,),
        member_names=("Alice",),
        market=market,
        started_at=START,
        resolution_source=None,
    )
    calls: list[str] = []

    class FakeClient:
        async def update_market_title(self, market, *, title):
            calls.append(f"title:{title}")
            return True

        async def close_market(self, market):
            calls.append("close")
            return True

        async def submit_result(self, market, **kwargs):
            calls.append(f"resolve:{kwargs['resolution_source']}:{kwargs['match_uuid']}")
            return True

        async def get_result_summary(self, market):
            calls.append("summary")
            return None

    class FakeMessage:
        async def edit(self, *, content, view):
            calls.append("discord-edit")

    monkeypatch.setattr(bot_common_actions, "list_pending_markets", lambda: [pending])
    monkeypatch.setattr(bot_common_actions, "TribeMarketsClient", FakeClient)
    monkeypatch.setattr(bot_common_actions, "data_access_get_message", lambda *args: _resolved_message(FakeMessage()))
    monkeypatch.setattr(bot_common_actions, "mark_reconciled_market", lambda *args, **kwargs: calls.append("matched"))
    monkeypatch.setattr(bot_common_actions, "mark_market_resolved", lambda *args: calls.append("resolved"))

    fetched = UserWithUserMatchInfo(
        UserQueueForStats(SimpleNamespace(id=1), 10, START),
        [match(user_id=1, uuid="match-async", map_name="Oregon")],
    )
    await bot_common_actions.reconcile_pending_tribemarkets(fetched_users=[fetched])

    # get_result_summary() returns None here (TribeMarkets' 120-minute challenge window is
    # still open), so the market must NOT be marked resolved yet - only "matched" (evidence
    # recorded) - or the settled recap from the later poll-only branch would never post
    # (list_pending_markets excludes anything already marked resolved).
    assert calls == [
        "title:2026-08-18 03:03 UTC · Oregon - Alice",
        "close",
        "resolve:r6_tracker:match-async",
        "summary",
        "discord-edit",
        "matched",
    ]


@pytest.mark.asyncio
async def test_async_reconciliation_settles_a_previously_matched_market(monkeypatch):
    """Once the challenge window closes, a later poll must post the recap and resolve it."""
    from deps import bot_common_actions

    market = {
        "market_id": "market-settle",
        "community_id": "tribe",
        "yes_outcome_id": "yes",
        "no_outcome_id": "no",
        "share_url": "https://example.test/market-settle",
        "external_event_id": "discord-ranked:1:2:3",
        "title": "2026-08-18 03:03 UTC · Oregon - Alice",
        "vote_message_id": 40,
        "result_submitted": True,
    }
    pending = SimpleNamespace(
        market_id="market-settle",
        guild_id=10,
        voice_channel_id=20,
        text_channel_id=30,
        vote_message_id=40,
        member_ids=(1,),
        member_names=("Alice",),
        market=market,
        started_at=START,
        resolution_source="r6_tracker",
        match_uuid="match-async",
        map_name="Oregon",
    )
    calls: list[str] = []

    class FakeClient:
        async def get_result_summary(self, market):
            calls.append("summary")
            return {"won": True, "score": "4-1"}

    class FakeMessage:
        async def edit(self, *, content, view):
            calls.append("discord-edit")

    monkeypatch.setattr(bot_common_actions, "list_pending_markets", lambda: [pending])
    monkeypatch.setattr(bot_common_actions, "TribeMarketsClient", FakeClient)
    monkeypatch.setattr(bot_common_actions, "data_access_get_message", lambda *args: _resolved_message(FakeMessage()))
    monkeypatch.setattr(bot_common_actions, "mark_reconciled_market", lambda *args, **kwargs: calls.append("matched"))
    monkeypatch.setattr(bot_common_actions, "mark_market_resolved", lambda *args: calls.append("resolved"))

    await bot_common_actions.reconcile_pending_tribemarkets(fetched_users=[])

    assert calls == ["summary", "discord-edit", "matched", "resolved"]


async def _resolved_message(message):
    return message


@pytest.mark.asyncio
async def test_update_match_start_gif_message_from_r6_tracker_finishes_stuck_message():
    """When stats.cc never reported a score, the R6 Tracker fallback must still finish the GIF message."""
    from deps.bot_common_actions import _update_match_start_gif_message_from_r6_tracker

    result = ReconciledMatch(
        match_uuid="match-1",
        map_name="Oregon",
        won=True,
        started_at=START,
        participant_count=2,
        score="4-1",
        confidence="high",
    )
    pending_gif = {"text_channel_id": 555, "message_id": 999, "member_ids": [101]}

    member = MagicMock(spec=discord.Member)
    member.id = 101
    member.display_name = "PlayerOne"

    guild = MagicMock(spec=discord.Guild)
    guild.get_member = MagicMock(side_effect=lambda uid: member if uid == 101 else None)

    message = MagicMock()
    message.edit = AsyncMock()

    with (
        patch("deps.bot_common_actions.data_access_get_guild", AsyncMock(return_value=guild)),
        patch(
            "deps.bot_common_actions.data_access_get_pending_match_start_gif_message",
            AsyncMock(return_value=pending_gif),
        ),
        patch(
            "deps.bot_common_actions.generate_match_end_static_summary",
            AsyncMock(return_value=b"PNGBYTES"),
        ) as mock_static,
        patch("deps.bot_common_actions.data_access_get_message", AsyncMock(return_value=message)),
        patch("deps.bot_common_actions.data_access_clear_pending_match_start_gif_message") as mock_clear,
    ):
        await _update_match_start_gif_message_from_r6_tracker(10, 20, (101,), result)

    message.edit.assert_awaited_once()
    mock_static.assert_awaited_once()
    call_kw = message.edit.await_args.kwargs
    assert "**Won 4-1**" in call_kw["content"]
    assert "Oregon" in call_kw["content"]
    att = call_kw["attachments"][0]
    assert att.filename == "match_result.png"
    mock_clear.assert_called_once_with(10, 20)


@pytest.mark.asyncio
async def test_update_match_start_gif_message_from_r6_tracker_does_not_abort_caller_on_error():
    """An unexpected error in the GIF update must not propagate to reconcile_pending_tribemarkets."""
    from deps.bot_common_actions import _update_match_start_gif_message_from_r6_tracker

    result = ReconciledMatch(
        match_uuid="match-1",
        map_name="Oregon",
        won=True,
        started_at=START,
        participant_count=1,
        score="4-1",
        confidence="medium",
    )

    with patch(
        "deps.bot_common_actions.data_access_get_pending_match_start_gif_message",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        # Must not raise: the caller relies on this being independent of the
        # TribeMarkets title/close/submit_result calls that follow it.
        await _update_match_start_gif_message_from_r6_tracker(10, 20, (101,), result)


@pytest.mark.asyncio
async def test_update_match_start_gif_message_loses_race_to_stats_cc():
    """If stats.cc finishes the message while this fallback is running, it must not clobber it."""
    from deps.bot_common_actions import _update_match_start_gif_message_from_r6_tracker

    result = ReconciledMatch(
        match_uuid="match-1",
        map_name="Oregon",
        won=True,
        started_at=START,
        participant_count=1,
        score="4-1",
        confidence="medium",
    )
    not_yet_final = {"text_channel_id": 555, "message_id": 999, "member_ids": [101]}
    now_final = {**not_yet_final, "last_result_key": "final:Won 4-1:4-1:Oregon"}

    member = MagicMock(spec=discord.Member)
    member.id = 101
    member.display_name = "PlayerOne"
    guild = MagicMock(spec=discord.Guild)
    guild.get_member = MagicMock(side_effect=lambda uid: member if uid == 101 else None)

    message = MagicMock()
    message.edit = AsyncMock()

    with (
        patch("deps.bot_common_actions.data_access_get_guild", AsyncMock(return_value=guild)),
        patch(
            "deps.bot_common_actions.data_access_get_pending_match_start_gif_message",
            AsyncMock(side_effect=[not_yet_final, now_final]),
        ),
        patch(
            "deps.bot_common_actions.generate_match_end_static_summary",
            AsyncMock(return_value=b"PNGBYTES"),
        ),
        patch("deps.bot_common_actions.data_access_get_message", AsyncMock(return_value=message)),
        patch("deps.bot_common_actions.data_access_clear_pending_match_start_gif_message") as mock_clear,
    ):
        await _update_match_start_gif_message_from_r6_tracker(10, 20, (101,), result)

    message.edit.assert_not_awaited()
    mock_clear.assert_not_called()


@pytest.mark.asyncio
async def test_update_match_start_gif_message_skips_when_already_finalized():
    """A message stats.cc already finished must not be overwritten by the fallback."""
    from deps.bot_common_actions import _update_match_start_gif_message_from_r6_tracker

    result = ReconciledMatch(
        match_uuid="match-1",
        map_name="Oregon",
        won=True,
        started_at=START,
        participant_count=1,
        score="4-1",
        confidence="medium",
    )
    pending_gif = {
        "text_channel_id": 555,
        "message_id": 999,
        "member_ids": [101],
        "last_result_key": "final:Won 4-1:4-1:Oregon",
    }

    with (
        patch(
            "deps.bot_common_actions.data_access_get_pending_match_start_gif_message",
            AsyncMock(return_value=pending_gif),
        ),
        patch("deps.bot_common_actions.data_access_get_message", AsyncMock()) as mock_get_message,
    ):
        await _update_match_start_gif_message_from_r6_tracker(10, 20, (101,), result)

    mock_get_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_match_start_gif_message_clears_pending_when_no_members_resolve():
    """Nobody in the squad can be resolved in the guild: clear the stale pending record."""
    from deps.bot_common_actions import _update_match_start_gif_message_from_r6_tracker

    result = ReconciledMatch(
        match_uuid="match-1",
        map_name="Oregon",
        won=True,
        started_at=START,
        participant_count=1,
        score="4-1",
        confidence="medium",
    )
    pending_gif = {"text_channel_id": 555, "message_id": 999, "member_ids": [101]}
    guild = MagicMock(spec=discord.Guild)
    guild.get_member = MagicMock(return_value=None)

    with (
        patch("deps.bot_common_actions.data_access_get_guild", AsyncMock(return_value=guild)),
        patch(
            "deps.bot_common_actions.data_access_get_pending_match_start_gif_message",
            AsyncMock(return_value=pending_gif),
        ),
        patch("deps.bot_common_actions.data_access_clear_pending_match_start_gif_message") as mock_clear,
    ):
        await _update_match_start_gif_message_from_r6_tracker(10, 20, (101,), result)

    mock_clear.assert_called_once_with(10, 20)


@pytest.mark.asyncio
async def test_reconcile_pending_tribemarkets_finishes_gif_message_from_r6_tracker(monkeypatch):
    """The R6 Tracker fallback branch must also finish the match-start GIF message."""
    from deps import bot_common_actions

    market = {
        "market_id": "market-gif",
        "community_id": "tribe",
        "yes_outcome_id": "yes",
        "no_outcome_id": "no",
        "share_url": "https://example.test/market-gif",
        "external_event_id": "discord-ranked:1:2:3",
        "title": "2026-08-18 03:03 UTC · Alice",
        "vote_message_id": 40,
    }
    pending = SimpleNamespace(
        market_id="market-gif",
        guild_id=10,
        voice_channel_id=20,
        text_channel_id=30,
        vote_message_id=40,
        member_ids=(1,),
        member_names=("Alice",),
        market=market,
        started_at=START,
        resolution_source=None,
    )

    class FakeClient:
        async def update_market_title(self, market, *, title):
            return True

        async def close_market(self, market):
            return True

        async def submit_result(self, market, **kwargs):
            return True

        async def get_result_summary(self, market):
            return None

    monkeypatch.setattr(bot_common_actions, "list_pending_markets", lambda: [pending])
    monkeypatch.setattr(bot_common_actions, "TribeMarketsClient", FakeClient)
    monkeypatch.setattr(bot_common_actions, "data_access_get_message", lambda *args: _resolved_message(None))
    monkeypatch.setattr(bot_common_actions, "mark_reconciled_market", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot_common_actions, "mark_market_resolved", lambda *args: None)
    mock_finish_gif = AsyncMock()
    monkeypatch.setattr(bot_common_actions, "_update_match_start_gif_message_from_r6_tracker", mock_finish_gif)

    fetched = UserWithUserMatchInfo(
        UserQueueForStats(SimpleNamespace(id=1), 10, START),
        [match(user_id=1, uuid="match-async", map_name="Oregon")],
    )
    await bot_common_actions.reconcile_pending_tribemarkets(fetched_users=[fetched])

    mock_finish_gif.assert_awaited_once()
    call_args = mock_finish_gif.await_args.args
    assert call_args[0] == 10  # guild_id
    assert call_args[1] == 20  # voice_channel_id
    assert call_args[2] == (1,)  # member_ids
    assert call_args[3].match_uuid == "match-async"
