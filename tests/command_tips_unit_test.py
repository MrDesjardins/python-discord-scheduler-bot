"""Unit coverage for daily lesson delivery and rotation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deps.values import COMMAND_INIT_USER

from deps.command_tips import COMMAND_TIPS, build_command_tip, send_daily_command_tip


@pytest.mark.asyncio
async def test_send_persists_progress_and_suppresses_duplicate():
    guild = MagicMock(id=123)
    channel = guild.get_channel.return_value
    channel.send = AsyncMock()
    state = {}

    def save(_memory, _key, value, _ttl):
        state.update(value)

    with (
        patch("deps.command_tips.data_access_get_main_text_channel_id", AsyncMock(return_value=456)),
        patch("deps.command_tips.get_cache", AsyncMock(return_value=state)),
        patch("deps.command_tips.set_cache", side_effect=save),
    ):
        await send_daily_command_tip(guild)
        await send_daily_command_tip(guild)

    channel.send.assert_awaited_once()
    assert state["next_index"] == 1
    assert f"/{COMMAND_INIT_USER}" in channel.send.call_args.kwargs["embed"].description


@pytest.mark.asyncio
async def test_failed_send_does_not_advance():
    guild = MagicMock(id=123)
    guild.get_channel.return_value.send = AsyncMock(side_effect=RuntimeError("Forbidden"))
    with (
        patch("deps.command_tips.data_access_get_main_text_channel_id", AsyncMock(return_value=456)),
        patch("deps.command_tips.get_cache", AsyncMock(return_value={})),
        patch("deps.command_tips.set_cache") as save,
    ):
        with pytest.raises(RuntimeError):
            await send_daily_command_tip(guild)
        save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("channel_id", [None, 456])
async def test_missing_channel_skips_delivery(channel_id):
    guild = MagicMock(id=123)
    guild.get_channel.return_value = None
    with (
        patch("deps.command_tips.data_access_get_main_text_channel_id", AsyncMock(return_value=channel_id)),
        patch("deps.command_tips.get_cache") as read,
    ):
        await send_daily_command_tip(guild)
        read.assert_not_called()


def test_all_lessons_are_unique_and_rotation_wraps():
    assert len(COMMAND_TIPS) == 24
    assert len({tip[0] for tip in COMMAND_TIPS}) == 24
    for index, (command, description, _) in enumerate(COMMAND_TIPS):
        embed = build_command_tip(index)
        assert f"/{command}" in embed.description
        assert description in embed.description
        assert len(embed) < 6000
    assert build_command_tip(24).to_dict() == build_command_tip(0).to_dict()
