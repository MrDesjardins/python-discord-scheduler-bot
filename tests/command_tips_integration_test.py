"""Verify lesson progress survives rereads through the persistent database cache."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from deps.values import COMMAND_CUSTOM_GAME_MAKE_TEAM

from deps.command_tips import send_daily_command_tip
from deps.cache import ALWAYS_TTL, get_cache, set_cache
from deps.data_access import data_access_set_main_text_channel_id
from deps.system_database import database_manager


@pytest.mark.asyncio
async def test_persistent_rotation_and_daily_deduplication(tmp_path):
    original_name = database_manager.get_database_name()
    database_manager.set_database_name(str(tmp_path / "command_tips.db"))
    database_manager.init_database()
    try:
        guild = MagicMock(id=123)
        channel = guild.get_channel.return_value
        channel.send = AsyncMock()
        data_access_set_main_text_channel_id(guild.id, 456)
        set_cache(False, "DailyCommandTip:123", {"date": "2000-01-01", "next_index": 23}, ALWAYS_TTL)
        await send_daily_command_tip(guild)
        assert (await get_cache(False, "DailyCommandTip:123"))["next_index"] == 0
        await send_daily_command_tip(guild)
        channel.send.assert_awaited_once()
        assert f"/{COMMAND_CUSTOM_GAME_MAKE_TEAM}" in channel.send.call_args.kwargs["embed"].description
    finally:
        database_manager.set_database_name(original_name)
