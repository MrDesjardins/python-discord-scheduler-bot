"""Tests for delayed TribeMarkets match identification."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from deps.tribemarkets_reconciliation import reconcile_match
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
        "title": "2026-08-18 03:03 UTC · Map pending — Will the squad win?",
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

    assert calls == [
        "title:2026-08-18 03:03 UTC · Oregon — Will the squad win?",
        "close",
        "resolve:r6_tracker:match-async",
        "summary",
        "discord-edit",
        "matched",
        "resolved",
    ]


async def _resolved_message(message):
    return message
