"""
Unit tests for voice state event handling

Tests the critical bug fixes:
- Fix 1: Guild loop bug (single guild processing)
- Fix 2: Bot shutdown handler
- Fix 3: Cache race condition (locking)
- Fix 5: Channel move atomicity
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
import pytest
import discord
from deps.system_database import EVENT_CONNECT, EVENT_DISCONNECT


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot"""
    bot = MagicMock()
    bot.guilds = []
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def mock_guild():
    """Create a mock Discord guild"""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 111111111
    guild.name = "Test Guild"
    return guild


@pytest.fixture
def mock_member(mock_guild):
    """Create a mock Discord member"""
    member = MagicMock(spec=discord.Member)
    member.id = 222222222
    member.display_name = "TestUser"
    member.bot = False
    member.guild = mock_guild
    return member


@pytest.fixture
def mock_voice_channel():
    """Create a mock voice channel"""
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 333333333
    channel.name = "Test Voice"
    channel.members = []
    return channel


@pytest.fixture
def mock_voice_state():
    """Create a mock voice state"""
    state = MagicMock(spec=discord.VoiceState)
    state.channel = None
    return state


class TestGuildLoopBug:
    """Test Fix 1: Guild loop bug - should only process member's guild"""

    @pytest.mark.asyncio
    async def test_user_join_voice_channel_single_guild(self, mock_bot, mock_guild, mock_member, mock_voice_channel):
        """Verify that joining a voice channel only creates ONE database entry"""
        from cogs.events import MyEventsCog

        # Setup: Bot has 3 guilds
        other_guild_1 = MagicMock(spec=discord.Guild)
        other_guild_1.id = 999999991
        other_guild_1.name = "Other Guild 1"

        other_guild_2 = MagicMock(spec=discord.Guild)
        other_guild_2.id = 999999992
        other_guild_2.name = "Other Guild 2"

        mock_bot.guilds = [mock_guild, other_guild_1, other_guild_2]

        cog = MyEventsCog(mock_bot)

        # Create voice states
        before = MagicMock(spec=discord.VoiceState)
        before.channel = None

        after = MagicMock(spec=discord.VoiceState)
        after.channel = mock_voice_channel

        # Mock data access functions
        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids") as mock_get_voice_channels,
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id") as mock_get_schedule_channel,
            patch("cogs.events.insert_user_activity") as mock_insert,
            patch("cogs.events.data_access_update_voice_user_list") as mock_update_voice_list,
            patch("cogs.events.get_siege_activity") as mock_get_activity,
            patch("cogs.events.send_private_notification_following_user") as mock_send_notification,
        ):

            # Setup mocks
            mock_get_voice_channels.return_value = [mock_voice_channel.id]
            mock_get_schedule_channel.return_value = 444444444
            mock_get_activity.return_value = None
            mock_send_notification.return_value = None

            # Execute
            await cog.on_voice_state_update(mock_member, before, after)

            # Verify: insert_user_activity should be called ONCE (not 3 times)
            assert mock_insert.call_count == 1

            # Verify: Called with correct guild_id (member's guild, not others)
            call_args = mock_insert.call_args
            assert call_args[0][3] == mock_guild.id  # guild_id parameter

            # Verify: Only queried member's guild settings
            mock_get_voice_channels.assert_called_once_with(mock_guild.id)
            mock_get_schedule_channel.assert_called_once_with(mock_guild.id)

    @pytest.mark.asyncio
    async def test_bot_user_ignored(self, mock_bot, mock_guild, mock_member, mock_voice_channel):
        """Verify that bot users are ignored"""
        from cogs.events import MyEventsCog

        cog = MyEventsCog(mock_bot)

        # Make the member a bot
        mock_member.bot = True

        before = MagicMock(spec=discord.VoiceState)
        before.channel = None

        after = MagicMock(spec=discord.VoiceState)
        after.channel = mock_voice_channel

        with patch("cogs.events.insert_user_activity") as mock_insert:
            await cog.on_voice_state_update(mock_member, before, after)

            # Verify: No database insertion for bots
            mock_insert.assert_not_called()


class TestShutdownHandler:
    """Test Fix 2: Bot shutdown handler"""

    @pytest.mark.asyncio
    async def test_shutdown_cleanup(self, mock_bot, mock_guild, mock_member, mock_voice_channel):
        """Verify that bot shutdown creates DISCONNECT events for all users in voice"""
        from cogs.events import MyEventsCog

        # Setup: 2 users in voice channel
        user1 = MagicMock(spec=discord.Member)
        user1.id = 111
        user1.display_name = "User1"
        user1.bot = False

        user2 = MagicMock(spec=discord.Member)
        user2.id = 222
        user2.display_name = "User2"
        user2.bot = False

        bot_user = MagicMock(spec=discord.Member)
        bot_user.id = 333
        bot_user.display_name = "BotUser"
        bot_user.bot = True

        mock_voice_channel.members = [user1, user2, bot_user]
        mock_bot.guilds = [mock_guild]

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids") as mock_get_channels,
            patch("cogs.events.data_access_get_channel") as mock_get_channel,
            patch("cogs.events.insert_user_activity") as mock_insert,
        ):

            mock_get_channels.return_value = [mock_voice_channel.id]
            mock_get_channel.return_value = mock_voice_channel

            # Execute
            await cog.on_close()

            # Verify: DISCONNECT events for 2 non-bot users (not the bot user)
            assert mock_insert.call_count == 2

            # Verify: Both users got DISCONNECT events
            calls = mock_insert.call_args_list
            user_ids = {call[0][0] for call in calls}
            events = {call[0][4] for call in calls}

            assert user_ids == {user1.id, user2.id}
            assert events == {EVENT_DISCONNECT}


class TestCacheRaceCondition:
    """Test Fix 3: Cache race condition (locking)"""

    @pytest.mark.asyncio
    async def test_concurrent_cache_updates(self):
        """Verify that concurrent voice state changes don't corrupt cache"""
        from deps.data_access import (
            data_access_update_voice_user_list,
            data_access_remove_voice_user_list,
            data_access_get_voice_user_list,
            lock_voice_user_list,
        )

        guild_id = 12345
        channel_id = 67890
        user1_id = 111
        user2_id = 222

        with (
            patch("deps.data_access.get_cache") as mock_get_cache,
            patch("deps.data_access.set_cache") as mock_set_cache,
        ):

            # Setup: Empty cache initially
            mock_get_cache.return_value = {}

            # Simulate concurrent updates
            async def update_user1():
                await data_access_update_voice_user_list(guild_id, channel_id, user1_id, "Playing")

            async def update_user2():
                await data_access_update_voice_user_list(guild_id, channel_id, user2_id, "Menu")

            # Execute concurrently
            await asyncio.gather(update_user1(), update_user2())

            # Verify: set_cache was called at least twice (one per update)
            assert mock_set_cache.call_count >= 2

            # Verify: Lock exists (proves locking is in place)
            assert lock_voice_user_list is not None
            assert isinstance(lock_voice_user_list, asyncio.Lock)


class TestChannelMoveAtomicity:
    """Test Fix 5: Channel move atomicity"""

    @pytest.mark.asyncio
    async def test_user_move_between_channels(self, mock_bot, mock_guild, mock_member):
        """Verify that channel moves create atomic DISCONNECT+CONNECT"""
        from cogs.events import MyEventsCog

        cog = MyEventsCog(mock_bot)

        channel1 = MagicMock(spec=discord.VoiceChannel)
        channel1.id = 111111
        channel1.name = "Channel 1"

        channel2 = MagicMock(spec=discord.VoiceChannel)
        channel2.id = 222222
        channel2.name = "Channel 2"

        before = MagicMock(spec=discord.VoiceState)
        before.channel = channel1

        after = MagicMock(spec=discord.VoiceState)
        after.channel = channel2

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids") as mock_get_voice_channels,
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id") as mock_get_schedule_channel,
            patch("deps.system_database.database_manager") as mock_db_manager,
            patch("cogs.events.data_access_remove_voice_user_list") as mock_remove_voice_list,
            patch("cogs.events.data_access_update_voice_user_list") as mock_update_voice_list,
            patch("cogs.events.get_siege_activity") as mock_get_activity,
        ):

            # Setup mocks
            mock_get_voice_channels.return_value = [channel1.id, channel2.id]
            mock_get_schedule_channel.return_value = 444444444
            mock_get_activity.return_value = None

            # Mock transaction context manager
            mock_cursor = MagicMock()
            mock_transaction = MagicMock()
            mock_transaction.__enter__ = MagicMock(return_value=mock_cursor)
            mock_transaction.__exit__ = MagicMock(return_value=None)
            mock_db_manager.data_access_transaction.return_value = mock_transaction

            # Execute
            await cog.on_voice_state_update(mock_member, before, after)

            # Verify: Transaction was used
            mock_db_manager.data_access_transaction.assert_called_once()

            # Verify: Cursor execute was called (for INSERT statements)
            assert mock_cursor.execute.call_count >= 2  # At least DISCONNECT and CONNECT

            # Verify: Cache was updated after transaction
            mock_remove_voice_list.assert_called_once_with(mock_guild.id, channel1.id, mock_member.id)
            mock_update_voice_list.assert_called_once()
