"""Pure tests for the optional TribeMarkets match-market integration."""

from datetime import datetime, timezone

from deps.tribemarkets import (
    MATCH_MARKET_CATEGORY,
    MATCH_MARKET_TAGS,
    MatchMarket,
    TribeMarketsSettings,
    build_market_description,
    build_market_title,
    format_result_summary,
    infer_map_name,
    score_reached_close_threshold,
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

    title = build_market_title(started_at, "Villa")
    description = build_market_description(
        member_names=["Alice", "Bob"],
        started_at=started_at,
        map_name="Villa",
    )

    assert title == "2026-08-13 20:30 UTC · Villa — Will the squad win?"
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
        vote_closed=True,
        result_submitted=True,
        settlement_complete=True,
        vote_message_id=42,
    )

    assert MatchMarket.from_dict(market.as_dict()) == market


def test_settings_default_to_disabled_without_an_api_key(monkeypatch):
    monkeypatch.delenv("TRIBEMARKETS_API_KEY", raising=False)
    monkeypatch.delenv("TRIBEMARKETS_TRIBE_ID", raising=False)
    monkeypatch.delenv("TRIBEMARKETS_TRIBE_SLUG", raising=False)

    settings = TribeMarketsSettings.from_environment()

    assert settings.tribe_slug == "circus-maximus"
    assert settings.close_score == 2
    assert not settings.enabled


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
