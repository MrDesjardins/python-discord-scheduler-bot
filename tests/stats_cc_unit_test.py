"""Recorded API contract and failure behavior for the experimental provider."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from deps.browser import download_full_matches
from deps.data_access_data_class import UserInfo
from deps.models import UserQueueForStats
from deps.stats_cc import StatsCCClient, StatsCCUnavailable, parse_match


@pytest.fixture
def recorded():
    return json.loads(Path("tests/tests_assets/stats_cc_match.json").read_text(encoding="utf-8"))


@pytest.fixture
def user(recorded):
    return UserInfo(
        123, "Player", "noSleep_rb6", "noSleep_rb6", recorded["match"]["player_summary"]["profile_id"], "UTC", 0
    )


def test_recorded_match_matches_existing_tracker_fields(recorded, user):
    match = parse_match(recorded["match"], recorded["detail"], recorded["config"], user)
    assert match.match_uuid == "3c3ed8fb-789b-4eee-a420-16c61bc48dbb"
    assert match.match_timestamp == datetime(2026, 11, 2, 6, 21, 52, 376000, tzinfo=timezone.utc)
    assert match.match_duration_ms == 2287048
    assert (match.map_name, match.data_center, match.rank_name) == ("Outback", "US East", "PLATINUM II")
    assert (match.kill_count, match.death_count, match.assist_count, match.head_shot_count) == (1, 8, 2, 1)
    assert (match.round_played_count, match.round_won_count, match.has_win) == (9, 5, True)
    assert (match.rank_points, match.points_gained, match.rank_previous) == (3388, 28, 3360)
    assert set(match.operators.split(",")) == {"Fuze", "Valkyrie", "Azami", "Kapkan", "Ace", "Alibi"}
    assert match.kill_1_count == 1
    assert match.kd_ratio == 0.12


def test_zero_deaths_and_unranked_placement(recorded, user):
    recorded["match"]["player_summary"]["deaths"] = 0
    recorded["match"]["ranked_session"] = {"rank": "v7-unranked", "rank_points": 0}
    match = parse_match(recorded["match"], recorded["detail"], recorded["config"], user)
    assert match.kd_ratio == 1
    assert (match.rank_name, match.rank_previous, match.points_gained) == ("Unknown", 0, 0)


@pytest.mark.parametrize("change", ["profile", "detail", "canceled", "rounds"])
def test_incomplete_or_wrong_match_is_rejected(recorded, user, change):
    if change == "profile":
        recorded["match"]["player_summary"]["profile_id"] = "other"
    elif change == "detail":
        recorded["detail"]["id"] = "other"
    elif change == "canceled":
        recorded["match"]["end_reason"] = "canceled"
    else:
        recorded["detail"]["rounds"] = []
    with pytest.raises(StatsCCUnavailable):
        parse_match(recorded["match"], recorded["detail"], recorded["config"], user)


def test_empty_history_is_unavailable_not_inactivity(user):
    with StatsCCClient() as client, patch.object(client, "_get", return_value=[]):
        with pytest.raises(StatsCCUnavailable):
            client.download_matches(user)


def test_malformed_history_is_unavailable(user, recorded):
    with StatsCCClient() as client, patch.object(client, "_get", side_effect=[[None], recorded["config"]]):
        with pytest.raises(StatsCCUnavailable):
            client.download_matches(user)


def test_shared_match_details_are_fetched_once(recorded, user):
    with (
        StatsCCClient() as client,
        patch.object(
            client,
            "_get",
            side_effect=[[recorded["match"]], recorded["config"], recorded["detail"], [recorded["match"]]],
        ) as get,
    ):
        assert len(client.download_matches(user)) == 1
        assert len(client.download_matches(user)) == 1
        assert get.call_count == 4


def test_http_block_has_no_retry():
    with StatsCCClient() as client, patch.object(client.session, "get") as get, patch("deps.stats_cc.time.sleep"):
        get.return_value.raise_for_status.side_effect = requests.HTTPError("429")
        with pytest.raises(StatsCCUnavailable):
            client._get("config")
        with pytest.raises(StatsCCUnavailable):
            client._get("another-player")
        get.assert_called_once()


def test_download_translates_recorded_responses(recorded, user):
    with (
        StatsCCClient() as client,
        patch.object(client, "_get", side_effect=[[recorded["match"]], recorded["config"], recorded["detail"]]),
    ):
        assert len(client.download_matches(user)) == 1


def test_opt_in_uses_statscc_without_opening_browser(recorded, user, monkeypatch):
    monkeypatch.setenv("MATCH_STATS_PROVIDER", "statscc")
    queue = UserQueueForStats(user, 1, datetime.now(timezone.utc))
    match = parse_match(recorded["match"], recorded["detail"], recorded["config"], user)
    with patch("deps.browser.StatsCCClient") as client, patch("deps.browser.BrowserContextManager") as browser:
        client.return_value.__enter__.return_value.download_matches.return_value = [match]
        result = download_full_matches([queue])
    browser.assert_not_called()
    assert result[0].match_stats == [match]


def test_opt_in_falls_back_for_missing_telemetry(user, monkeypatch):
    monkeypatch.setenv("MATCH_STATS_PROVIDER", "statscc")
    queue = UserQueueForStats(user, 1, datetime.now(timezone.utc))
    with patch("deps.browser.StatsCCClient") as client, patch("deps.browser.BrowserContextManager") as browser:
        client.return_value.__enter__.return_value.download_matches.side_effect = StatsCCUnavailable("No telemetry")
        browser.return_value.__enter__.return_value.download_full_matches.return_value = []
        result = download_full_matches([queue])
    browser.return_value.__enter__.return_value.download_full_matches.assert_called_once_with(queue)
    assert len(result) == 1
