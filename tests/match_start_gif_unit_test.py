"""Unit tests for the match-start GIF: every dependency is mocked, nothing hits the database or network."""

import io
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

import deps.match_start_gif as gif
from deps.analytic_models import UserMapStats
from deps.siege import StatsCcRankedMatchEndResult


def _member(user_id: int, name: str) -> Any:
    return SimpleNamespace(id=user_id, display_name=name, bot=False)


async def _fake_avatar(member: SimpleNamespace, size: int = 100) -> Image.Image:
    return Image.new("RGB", (size, size), "#7289DA")


@pytest.fixture
def patched_data():
    """Replace every data source of the GIF with canned values."""
    map_stats = UserMapStats(matches=10, wins=6, top_operators=[("Ash", 12), ("Mira", 8)])
    with (
        patch.object(gif, "download_avatar", _fake_avatar),
        patch.object(gif, "get_user_rank_siege", lambda member: "Gold"),
        patch.object(gif, "download_custom_emoji", AsyncMock(return_value=Image.new("RGBA", (48, 48), "#FFD700"))),
        patch.object(gif, "data_access_fetch_users_operators", return_value=[]),
        patch.object(gif, "build_player_value_lookup", return_value={}),
        patch.object(gif, "data_access_fetch_team_stats", return_value=(20, 0.55)),
        patch.object(gif, "data_access_fetch_user_map_stats", return_value=map_stats) as fetch_map_stats,
        patch.object(gif, "data_access_fetch_user_full_user_info", return_value=None),
        patch.object(gif, "data_access_fetch_total_hours", return_value=12),
        patch.object(gif, "data_access_fetch_recent_results", return_value=[True, False, True]),
        patch.object(gif, "fetch_user_info_by_user_id", AsyncMock(return_value=None)),
    ):
        yield SimpleNamespace(fetch_map_stats=fetch_map_stats)


def _frames(gif_bytes: bytes) -> list[Image.Image]:
    image = cast(Any, Image.open(io.BytesIO(gif_bytes)))
    frames = []
    for index in range(image.n_frames):
        image.seek(index)
        frames.append(image.convert("RGB"))
    return frames


@pytest.mark.asyncio
async def test_gif_without_map_has_intro_and_one_frame_per_player(patched_data) -> None:
    members = [_member(1, "A"), _member(2, "B")]

    result = await gif.generate_match_start_gif(members, 1, {})

    assert result is not None
    frames = _frames(result)
    assert len(frames) == 3
    assert {frame.size for frame in frames} == {(gif.FRAME_WIDTH, gif.FRAME_HEIGHT)}
    patched_data.fetch_map_stats.assert_not_called()


@pytest.mark.asyncio
async def test_gif_with_known_map_adds_map_frame_and_fetches_stats_per_member(patched_data) -> None:
    members = [_member(1, "A"), _member(2, "B")]

    result = await gif.generate_match_start_gif(members, 1, {}, map_name="Villa")

    assert result is not None
    assert len(_frames(result)) == 4
    assert patched_data.fetch_map_stats.call_count == 2
    patched_data.fetch_map_stats.assert_any_call(1, "Villa", gif.MAP_TOP_OPERATORS)


@pytest.mark.asyncio
async def test_gif_takes_map_from_match_result_and_appends_result_frame(patched_data) -> None:
    members = [_member(1, "A")]
    match_result = StatsCcRankedMatchEndResult(won=True, our_score=2, their_score=1, map_name="Villa")

    result = await gif.generate_match_start_gif(members, 1, {}, match_result=match_result)

    assert result is not None
    # intro + map + player + result
    assert len(_frames(result)) == 4


@pytest.mark.asyncio
async def test_gif_skips_map_frame_when_map_has_no_artwork(patched_data) -> None:
    result = await gif.generate_match_start_gif([_member(1, "A")], 1, {}, map_name="Not A Real Map")

    assert result is not None
    assert len(_frames(result)) == 2


@pytest.mark.asyncio
async def test_gif_survives_map_stats_failure(patched_data) -> None:
    patched_data.fetch_map_stats.side_effect = RuntimeError("db down")

    result = await gif.generate_match_start_gif([_member(1, "A")], 1, {}, map_name="Villa")

    assert result is not None
    assert len(_frames(result)) == 3


@pytest.mark.asyncio
async def test_gif_without_members_returns_none() -> None:
    assert await gif.generate_match_start_gif([], 1, {}) is None


def test_format_operators_and_record() -> None:
    assert gif._format_operators([("Ash", 14), ("Mira", 9)]) == "Ash 14  Mira 9"
    assert gif._format_map_record(UserMapStats(matches=12, wins=7, top_operators=[])) == "58% win | 12 games"


@pytest.mark.parametrize("win_rate, color", [(60, gif.COLOR_WIN), (50, "white"), (30, gif.COLOR_LOSS)])
def test_win_rate_color(win_rate: float, color: str) -> None:
    assert gif._win_rate_color(win_rate) == color


@pytest.mark.asyncio
@pytest.mark.parametrize("map_name", ["Villa", None, "Not A Real Map"])
async def test_static_summary_renders_with_and_without_map_artwork(patched_data, map_name: str | None) -> None:
    members = [_member(1, "A"), _member(2, "B")]
    result = StatsCcRankedMatchEndResult(
        won=True, our_score=4, their_score=1, map_name=map_name, is_match_complete=True
    )

    png = await gif.generate_match_end_static_summary(members, result)

    assert png is not None
    assert Image.open(io.BytesIO(png)).size == (gif.FRAME_WIDTH, gif.BANNER_HEIGHT + gif.SUMMARY_SQUAD_HEIGHT)


@pytest.mark.asyncio
async def test_static_summary_without_members_returns_none() -> None:
    result = StatsCcRankedMatchEndResult(won=True, our_score=4, their_score=1, is_match_complete=True)

    assert await gif.generate_match_end_static_summary([], result) is None


@pytest.mark.asyncio
async def test_rank_icon_is_the_guild_emoji_of_the_members_rank(patched_data) -> None:
    icon = await gif._download_rank_icon({"Gold": 123, "Unranked": 9}, _member(1, "A"))

    assert icon is not None
    gif.download_custom_emoji.assert_awaited_once_with("123", gif.RANK_ICON_SIZE)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_rank_icon_is_none_when_the_guild_has_no_rank_emoji(patched_data) -> None:
    assert await gif._download_rank_icon({}, _member(1, "A")) is None
