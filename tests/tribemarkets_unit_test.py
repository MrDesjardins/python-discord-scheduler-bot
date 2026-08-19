"""Pure tests for the optional TribeMarkets match-market integration."""

from datetime import datetime, timezone

import pytest

from deps.tribemarkets import (
    MATCH_MARKET_CATEGORY,
    MATCH_MARKET_TAGS,
    MatchMarket,
    TribeMarketsSettings,
    build_market_description,
    build_market_title,
    format_vote_closed_message,
    format_vote_open_message,
    format_result_summary,
    infer_map_name,
    score_reached_close_threshold,
    TribeMarketsClient,
)


def test_score_reached_close_threshold_for_first_to_two_scores():
    assert score_reached_close_threshold(2, 0)
    assert score_reached_close_threshold(1, 2)
    assert score_reached_close_threshold(3, 1)
    assert not score_reached_close_threshold(1, 1)
    assert not score_reached_close_threshold(0, 1)


def test_infer_map_name_from_stats_cc_details():
    assert infer_map_name("Ranked on Villa") == "Villa"
    assert infer_map_name("Match Ending: Ranked on Oregon") == "Oregon"
    assert infer_map_name("Casual on Villa") is None
    assert infer_map_name(None) is None


def test_market_copy_contains_match_context_and_binary_instruction():
    started_at = datetime(2026, 8, 13, 20, 30, tzinfo=timezone.utc)

    title = build_market_title(started_at, "Villa", ["Alice", "Bob"])
    description = build_market_description(
        member_names=["Alice", "Bob"],
        started_at=started_at,
        map_name="Villa",
    )

    assert title == "2026-08-13 20:30 UTC · Villa - Alice, Bob"
    assert build_market_title(started_at, None, ["Alice", "Bob"]) == (
        "2026-08-13 20:30 UTC · Alice, Bob"
    )
    assert "Squad: Alice, Bob" in description
    assert "Map: Villa" in description
    assert "Vote Yes" in description
    assert "vote No" in description


def test_match_market_round_trips_cache_state():
    market = MatchMarket(
        community_id="tribe-id",
        market_id="market-id",
        yes_outcome_id="yes-id",
        no_outcome_id="no-id",
        share_url="https://tribemarkets.com/app/tribes/circus-maximus/markets/market-id",
        external_event_id="discord-ranked:1:2:3",
        title="Will the squad win?",
        opens_at="2026-08-13T20:30:00+00:00",
        closes_at="2026-08-14T00:30:00+00:00",
        vote_closed=True,
        result_submitted=True,
        settlement_complete=True,
        vote_message_id=42,
    )

    assert MatchMarket.from_dict(market.as_dict()) == market


def test_format_vote_open_message_shows_context_above_buttons():
    market = MatchMarket(
        community_id="tribe-id",
        market_id="market-id",
        yes_outcome_id="yes-id",
        no_outcome_id="no-id",
        share_url="https://example.com/market-id",
        external_event_id="discord-ranked:1:2:3",
        title="Will the squad win?",
        closes_at="2026-08-14T00:30:00+00:00",
    )

    assert format_vote_open_message(market) == (
        "🗳️ **Will the squad win?**\n"
        "🟢 **Market open** · closes <t:1786667400:R>\n"
        "Vote **Yes** if the squad wins; vote **No** if it loses."
    )


def test_settings_default_to_disabled_without_an_api_key(monkeypatch):
    monkeypatch.delenv("TRIBEMARKETS_API_KEY", raising=False)
    monkeypatch.delenv("TRIBEMARKETS_TRIBE_ID", raising=False)
    monkeypatch.delenv("TRIBEMARKETS_TRIBE_SLUG", raising=False)

    settings = TribeMarketsSettings.from_environment()

    assert settings.tribe_slug == "circus-maximus"
    assert settings.close_score == 2
    assert settings.default_stake == "10"
    assert settings.settlement_rule == "sponsored_parimutuel"
    assert settings.sponsor_liquidity == "100"
    assert not settings.enabled


def test_signed_validation_default_challenge_window_matches_api_requirement(monkeypatch):
    """An omitted challenge setting must remain valid for the API."""
    monkeypatch.setenv("TRIBEMARKETS_API_KEY", "test-key")
    monkeypatch.setenv("TRIBEMARKETS_TRIBE_ID", "tribe-id")
    monkeypatch.setenv("TRIBEMARKETS_VALIDATION_MODE", "signed_bot_with_challenge")
    monkeypatch.setenv("TRIBEMARKETS_VALIDATION_PROVIDER_ID", "provider")
    monkeypatch.delenv("TRIBEMARKETS_VALIDATION_CHALLENGE_MINUTES", raising=False)

    assert TribeMarketsSettings.from_environment().challenge_minutes == 120


def test_match_markets_use_siege_category_and_ranked_match_tags():
    assert MATCH_MARKET_CATEGORY == "Siege"
    assert MATCH_MARKET_TAGS == ("Match", "Ranked")


def test_result_summary_formats_match_recap_and_small_prediction_breakdown():
    summary = {
        "market": {
            "status": "resolved",
            "winning_outcome": {"code": "YES", "label": "Yes"},
            "evidence": {"final_score": "2-0"},
        },
        "pool": {
            "total_staked": "60.00",
            "currency_code": "credits",
        },
        "participants": {
            "eligible_count": 2,
            "correct_count": 1,
            "incorrect_count": 1,
        },
        "top_winners": [
            {
                "display_name": "Alice",
                "outcome_code": "YES",
                "profit": "40.00",
                "payout": "50.00",
            }
        ],
        "top_losers": [
            {
                "display_name": "Bob",
                "outcome_code": "NO",
                "profit": "-10.00",
                "payout": "0.00",
            }
        ],
    }

    content = format_result_summary(summary, "https://tribemarkets.com/market/abc")

    assert "Winning prediction: **Yes**" in content
    assert "Final score: **2-0**" in content
    assert "Correct predictions: 1/2" in content
    assert "Highest earner: **Alice** (+40.00 profit)" in content
    assert "Biggest loss: **Bob** (-10.00)" in content
    assert "Alice — YES: +40.00 profit (50.00 payout)" in content
    assert content.endswith("🔗 View market: https://tribemarkets.com/market/abc")


def test_result_summary_marks_void_market_as_refunded():
    content = format_result_summary(
        {"market": {"status": "voided"}, "terminal_reason": "winning outcome had no stakes"},
        "https://tribemarkets.com/market/voided",
    )

    assert "Market **winning outcome had no stakes**" in content
    assert "all stakes were refunded" in content
    assert content.endswith("🔗 View market: https://tribemarkets.com/market/voided")


def test_vote_closed_message_includes_yes_and_no_counts():
    content = format_vote_closed_message(
        {"vote_counts": {"YES": 10, "NO": 2}},
        "2-1",
        "https://tribemarkets.com/market/abc",
    )

    assert "Voting closed at 2-1" in content
    assert "10 Yes" in content
    assert "2 No" in content


@pytest.mark.asyncio
async def test_update_market_title_uses_patch_and_updates_local_state(monkeypatch):
    market = MatchMarket(
        community_id="tribe-id",
        market_id="market-id",
        yes_outcome_id="yes-id",
        no_outcome_id="no-id",
        share_url="https://example.com/market-id",
        external_event_id="discord-ranked:1:2:3",
        title="Map pending",
    )
    client = TribeMarketsClient(
        TribeMarketsSettings(
            api_url="https://example.com/v1",
            api_key="key",
            tribe_slug="circus-maximus",
            tribe_id="tribe-id",
            validation_provider_id=None,
            validation_mode="manual",
            share_link_hours=168,
            close_score=2,
            challenge_minutes=120,
            default_stake="10",
            settlement_rule="sponsored_parimutuel",
            sponsor_liquidity="100",
        )
    )
    calls = []

    async def fake_request(method, path, *, json_body=None, headers=None):
        calls.append((method, path, json_body))
        return {}

    monkeypatch.setattr(client, "_request", fake_request)

    assert await client.update_market_title(market, title="2026-08-18 03:03 UTC · Villa - Alice")
    assert calls == [
        (
            "PATCH",
            "/communities/tribe-id/markets/market-id",
            {"title": "2026-08-18 03:03 UTC · Villa - Alice"},
        )
    ]
    assert market.title == "2026-08-18 03:03 UTC · Villa - Alice"


@pytest.mark.asyncio
async def test_submit_result_can_use_r6_tracker_evidence(monkeypatch):
    market = MatchMarket(
        community_id="tribe-id",
        market_id="market-id",
        yes_outcome_id="yes-id",
        no_outcome_id="no-id",
        share_url="https://example.com/market-id",
        external_event_id="discord-ranked:1:2:3",
    )
    client = TribeMarketsClient(
        TribeMarketsSettings(
            api_url="https://example.com/v1",
            api_key="key",
            tribe_slug="circus-maximus",
            tribe_id="tribe-id",
            validation_provider_id=None,
            validation_mode="manual",
            share_link_hours=168,
            close_score=2,
            challenge_minutes=120,
            default_stake="10",
            settlement_rule="sponsored_parimutuel",
            sponsor_liquidity="100",
        )
    )
    captured = {}

    async def fake_request(method, path, *, json_body=None, headers=None):
        captured.update(method=method, path=path, json_body=json_body)
        return {}

    monkeypatch.setattr(client, "_request", fake_request)

    assert await client.submit_result(
        market,
        won=False,
        score="2-4",
        map_name="Villa",
        member_names=["Alice"],
        occurred_at=datetime(2026, 8, 18, 3, 10, tzinfo=timezone.utc),
        resolution_source="r6_tracker",
        match_uuid="match-uuid",
    )
    assert captured["path"] == "/communities/tribe-id/markets/market-id/resolve"
    assert captured["json_body"]["resolution_source"] == "r6_tracker"
    assert captured["json_body"]["evidence"]["match_uuid"] == "match-uuid"
    assert captured["json_body"]["evidence"]["source"] == "r6_tracker"
