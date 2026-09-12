"""Unit tests for the daily AI summary rich rendering (banner + embeds)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from deps.ai.ai_functions import DailySummarySections
from deps.ai.daily_summary_visual import (
    COLOR_LOSS,
    COLOR_NEUTRAL,
    COLOR_WIN,
    MAX_EMBEDS_PER_MESSAGE,
    build_daily_recap_banner,
    build_daily_summary_embeds,
    compute_user_win_loss,
)
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats


def create_mock_user(user_id: int, display_name: str) -> UserInfo:
    return UserInfo(
        id=user_id,
        display_name=display_name,
        ubisoft_username_max=f"ubi_{user_id}",
        ubisoft_username_active=f"ubi_{user_id}",
        r6_tracker_active_id=f"uuid-{user_id}",
        time_zone="US/Eastern",
        max_mmr=3500,
    )


def create_mock_match(user_id: int, match_uuid: str, has_win: bool) -> UserFullMatchStats:
    return UserFullMatchStats(
        id=1,
        match_uuid=match_uuid,
        user_id=user_id,
        match_timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
        match_duration_ms=600000,
        data_center="US East",
        session_type="ranked",
        map_name="Clubhouse",
        is_surrender=False,
        is_forfeit=False,
        is_rollback=False,
        r6_tracker_user_uuid=f"uuid-{user_id}",
        ubisoft_username=f"ubi_{user_id}",
        operators="Ash,Jager",
        round_played_count=9,
        round_won_count=5,
        round_lost_count=4,
        round_disconnected_count=0,
        kill_count=9,
        death_count=5,
        assist_count=2,
        head_shot_count=3,
        tk_count=0,
        ace_count=0,
        first_kill_count=1,
        first_death_count=0,
        clutches_win_count=1,
        clutches_loss_count=0,
        clutches_win_count_1v1=1,
        clutches_win_count_1v2=0,
        clutches_win_count_1v3=0,
        clutches_win_count_1v4=0,
        clutches_win_count_1v5=0,
        clutches_lost_count_1v1=0,
        clutches_lost_count_1v2=0,
        clutches_lost_count_1v3=0,
        clutches_lost_count_1v4=0,
        clutches_lost_count_1v5=0,
        kill_1_count=4,
        kill_2_count=2,
        kill_3_count=1,
        kill_4_count=0,
        kill_5_count=0,
        rank_points=3500,
        rank_name="Diamond",
        points_gained=25,
        rank_previous=3475,
        kd_ratio=1.8,
        head_shot_percentage=0.43,
        kills_per_round=0.78,
        deaths_per_round=0.56,
        assists_per_round=0.22,
        has_win=has_win,
    )


def test_compute_user_win_loss_counts_wins_and_losses():
    matches = [
        create_mock_match(1, "m1", has_win=True),
        create_mock_match(1, "m2", has_win=True),
        create_mock_match(1, "m3", has_win=False),
    ]

    wins, losses = compute_user_win_loss(matches)

    assert (wins, losses) == (2, 1)


def test_build_daily_summary_embeds_colors_by_win_loss_and_sets_footer():
    user_winner = create_mock_user(1, "Winner")
    user_loser = create_mock_user(2, "Loser")
    sections = DailySummarySections(
        fallback_text=None,
        sections=[(user_winner, "Winner had a great day."), (user_loser, "Loser had a rough day.")],
        users=[user_winner, user_loser],
        matches_by_user_id={
            1: [create_mock_match(1, "m1", has_win=True), create_mock_match(1, "m2", has_win=True)],
            2: [create_mock_match(2, "m3", has_win=False), create_mock_match(2, "m4", has_win=True)],
        },
    )
    guild = SimpleNamespace(get_member=lambda user_id: None)

    batches = build_daily_summary_embeds(sections, guild)

    assert len(batches) == 1
    embeds = batches[0]
    assert len(embeds) == 2
    assert embeds[0].color.value == COLOR_WIN
    assert embeds[0].footer.text == "2W - 0L"
    assert embeds[1].color.value == COLOR_NEUTRAL
    assert embeds[1].footer.text == "1W - 1L"


def test_build_daily_summary_embeds_batches_over_ten_users():
    users_with_text = [(create_mock_user(i, f"Player{i}"), f"Player{i} played well.") for i in range(1, 13)]
    sections = DailySummarySections(
        fallback_text=None,
        sections=users_with_text,
        users=[user for user, _ in users_with_text],
        matches_by_user_id={},
    )
    guild = SimpleNamespace(get_member=lambda user_id: None)

    batches = build_daily_summary_embeds(sections, guild)

    assert len(batches) == 2
    assert len(batches[0]) == MAX_EMBEDS_PER_MESSAGE
    assert len(batches[1]) == 2


def test_build_daily_summary_embeds_loss_color():
    user = create_mock_user(1, "Loser")
    sections = DailySummarySections(
        fallback_text=None,
        sections=[(user, "Had a rough night.")],
        users=[user],
        matches_by_user_id={1: [create_mock_match(1, "m1", has_win=False), create_mock_match(1, "m2", has_win=False)]},
    )
    guild = SimpleNamespace(get_member=lambda user_id: None)

    batches = build_daily_summary_embeds(sections, guild)

    assert batches[0][0].color.value == COLOR_LOSS


@pytest.mark.asyncio
async def test_build_daily_recap_banner_returns_none_for_no_users():
    guild = SimpleNamespace(get_member=lambda user_id: None)

    result = await build_daily_recap_banner(guild, [])

    assert result is None


@pytest.mark.asyncio
async def test_build_daily_recap_banner_renders_png_for_users():
    guild = SimpleNamespace(get_member=lambda user_id: None)
    users = [create_mock_user(1, "Fridge"), create_mock_user(2, "Obey")]

    async def fake_avatar(member):
        return Image.new("RGB", (100, 100), "#3A3F44")

    with (
        patch("deps.ai.daily_summary_visual.download_avatar", side_effect=fake_avatar),
        patch("deps.ai.daily_summary_visual.build_player_value_lookup", return_value={1: (4200, 92, 63.2)}),
    ):
        result = await build_daily_recap_banner(guild, users)

    assert result is not None
    assert result[:8] == b"\x89PNG\r\n\x1a\n"
