"""Profile setup must resolve accounts or reply without saving partial data."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from deps.stats_cc import StatsCCClient, StatsCCUnavailable
from ui.setup_user_profile_view import SetupUserProfileModal

PROFILE_ID = "f67508fb-fd32-414e-8c8c-e1dff7b2eb92"


def test_setup_current_season_and_peak_are_distinct():
    config = {
        "seasons": {"current": {"started_at": "2026-01-01T00:00:00Z"}, "old": {"started_at": "2025-01-01T00:00:00Z"}},
        "ranks": {"gold": {"display": "Gold II"}},
    }
    active = {"id": PROFILE_ID, "ranked_season_records": {"current": {"rank": "gold", "max_rank_points": 2500}}}
    highest = {"ranked_season_records": {"old": {"max_rank_points": 4500}}}
    with StatsCCClient() as client, patch.object(client, "_get", side_effect=[active, highest, config]) as get:
        assert client.setup_profile("Peak", "Active") == (PROFILE_ID, "GOLD II", 4500)
        assert get.call_args_list[0].args == ("profiles/pc/Active",)


def test_no_current_season_record_is_unranked_and_same_account_fetched_once():
    profile = {"id": PROFILE_ID, "ranked_season_records": {"old": {"max_rank_points": 4500}}}
    config = {"seasons": {"current": {"started_at": "2026-01-01T00:00:00Z"}}}
    with StatsCCClient() as client, patch.object(client, "_get", side_effect=[profile, config]) as get:
        assert client.setup_profile("Player", "player") == (PROFILE_ID, "UNRANKED", 4500)
        assert get.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_modal_replies_and_only_saves_resolved_profile(failure):
    view = SimpleNamespace(
        member=SimpleNamespace(id=123, display_name="Player"),
        guild=SimpleNamespace(id=1),
        user_timezone="UTC",
        bot=SimpleNamespace(guild_emoji={}),
    )
    modal = SetupUserProfileModal(view)
    modal.max_rank_account_input._value = " Player "
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock()), followup=SimpleNamespace(send=AsyncMock())
    )
    result = StatsCCUnavailable("blocked") if failure else (PROFILE_ID, "GOLD II", 4500)
    with (
        patch.object(modal, "fetch_profile", side_effect=result if failure else None, return_value=result),
        patch("ui.setup_user_profile_view.upsert_user_info") as save,
        patch(
            "ui.setup_user_profile_view.set_member_role_from_current_rank", new_callable=AsyncMock, return_value=True
        ),
        patch(
            "ui.setup_user_profile_view.data_access_get_gaming_session_text_channel_id",
            new_callable=AsyncMock,
            return_value=42,
        ),
    ):
        await modal.on_submit(interaction)
        interaction.followup.send.assert_awaited_once()
        if failure:
            save.assert_not_called()
            assert "Could not look up" in interaction.followup.send.call_args.args[0]
        else:
            assert save.call_args.args == (123, "Player", "Player", "Player", PROFILE_ID, "UTC", 4500)


@pytest.mark.parametrize("api_key", [None, "test-key"])
def test_profile_http_lookup_supports_anonymous_and_optional_key(monkeypatch, api_key):
    if api_key is None:
        monkeypatch.delenv("STATS_CC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("STATS_CC_API_KEY", api_key)
    profile = {"id": PROFILE_ID, "ranked_season_records": {}}
    config = {"seasons": {"current": {"started_at": "2026-01-01T00:00:00Z"}}}
    with StatsCCClient() as client, patch.object(client.session, "get") as get, patch("deps.stats_cc.time.sleep"):
        get.return_value.json.side_effect = [profile, config]
        assert client.setup_profile("Player", "Player") == (PROFILE_ID, "UNRANKED", 0)
        assert client.session.headers.get("x-api-key") == api_key
        assert get.call_args_list[0].args == ("https://api.stats.cc/siege/v2/profiles/pc/Player",)
        assert get.call_args_list[0].kwargs["timeout"] == 20
