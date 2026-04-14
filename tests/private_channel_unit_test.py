"""
Unit tests for the private channel feature.
No database, no Discord — mocked dependencies only.
"""

import pytest
from unittest.mock import call
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from deps.values import PRIVATE_CHANNEL_MIN_HOURS
from types import SimpleNamespace


def _perms(view_channel: bool, connect: bool):
    return SimpleNamespace(view_channel=view_channel, connect=connect)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.add_command = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 99999
    return bot


@pytest.fixture
def mock_guild():
    guild = MagicMock(spec=discord.Guild)
    guild.id = 111111111
    guild.name = "Test Guild"
    guild.default_role = MagicMock(spec=discord.Role)
    guild.me = MagicMock(spec=discord.Member)
    guild.me.id = 99999
    return guild


@pytest.fixture
def mock_creator(mock_guild):
    member = MagicMock(spec=discord.Member)
    member.id = 222222222
    member.display_name = "TestUser"
    member.bot = False
    member.guild = mock_guild
    member.voice = None
    member.move_to = AsyncMock()
    return member


@pytest.fixture
def mock_category():
    category = MagicMock()
    category.__class__ = discord.CategoryChannel  # Make isinstance() pass
    category.id = 444444444
    category.name = "Private Channels"
    return category


@pytest.fixture
def mock_private_channel():
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 555555555
    channel.name = "TestUser's private vc"
    channel.members = []
    channel.delete = AsyncMock()
    return channel


@pytest.fixture
def mock_interaction(mock_guild, mock_creator):
    interaction = MagicMock()
    interaction.guild = mock_guild
    interaction.user = mock_creator
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


# ---------------------------------------------------------------------------
# Tests: create_private_channel command
# ---------------------------------------------------------------------------


class TestCreatePrivateChannelCommand:
    @pytest.mark.asyncio
    async def test_rejected_when_under_min_hours(self, mock_bot, mock_interaction):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)

        with patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS - 1):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert str(PRIVATE_CHANNEL_MIN_HOURS) in msg
        assert str(PRIVATE_CHANNEL_MIN_HOURS - 1) in msg

    @pytest.mark.asyncio
    async def test_rejected_when_no_hours_recorded(self, mock_bot, mock_interaction):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)

        with patch("cogs.user_features.data_access_fetch_total_hours", return_value=None):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert str(PRIVATE_CHANNEL_MIN_HOURS) in msg

    @pytest.mark.asyncio
    async def test_rejected_when_category_not_configured(self, mock_bot, mock_interaction):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=None,
            ),
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "category" in msg.lower()

    @pytest.mark.asyncio
    async def test_rejected_when_category_not_found_in_guild(self, mock_bot, mock_interaction, mock_guild):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = None

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=444444444,
            ),
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "no longer exists" in msg

    @pytest.mark.asyncio
    async def test_multiple_channels_allowed_simultaneously(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_category, mock_private_channel
    ):
        """Creating a channel succeeds even when other private channels already exist."""
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = mock_category
        mock_guild.get_member.return_value = mock_creator
        mock_guild.create_voice_channel = AsyncMock(return_value=mock_private_channel)

        existing = {999: (12345, True)}

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=mock_category.id,
            ),
            patch("cogs.user_features.data_access_set_guild_active_private_channel", new_callable=AsyncMock),
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_guild.create_voice_channel.assert_called_once()

    @pytest.mark.asyncio
    async def test_channel_name_uses_display_name(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_category, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)
        mock_creator.display_name = "Alice"
        mock_guild.get_channel.return_value = mock_category
        mock_guild.get_member.return_value = mock_creator
        mock_guild.create_voice_channel = AsyncMock(return_value=mock_private_channel)

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=mock_category.id,
            ),
            patch("cogs.user_features.data_access_set_guild_active_private_channel", new_callable=AsyncMock),
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        call_kwargs = mock_guild.create_voice_channel.call_args.kwargs
        assert call_kwargs["name"] == "Alice's private vc"

    @pytest.mark.asyncio
    async def test_permission_overwrites_are_correct(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_category, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = mock_category
        mock_guild.get_member.return_value = mock_creator
        mock_guild.create_voice_channel = AsyncMock(return_value=mock_private_channel)
        mock_private_channel.edit = AsyncMock()
        mock_private_channel.set_permissions = AsyncMock()
        mock_private_channel.permissions_for = MagicMock(side_effect=[_perms(False, False), _perms(True, True)])
        mock_category.channels = [mock_private_channel]

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=mock_category.id,
            ),
            patch("cogs.user_features.data_access_set_guild_active_private_channel", new_callable=AsyncMock),
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        # Channel is created without overwrites (to avoid permission-check 403 during creation).
        call_kwargs = mock_guild.create_voice_channel.call_args.kwargs
        assert "overwrites" not in call_kwargs or call_kwargs.get("overwrites") is None

        # Permissions are set separately after creation:
        # - deny everyone connect/move first
        # - then allow creator connect/view as final overwrite
        mock_private_channel.set_permissions.assert_has_calls(
            [
                call(mock_guild.default_role, connect=False, move_members=False),
                call(mock_creator, view_channel=True, connect=True, move_members=False),
            ]
        )

    @pytest.mark.asyncio
    async def test_channel_placed_at_bottom_of_category(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_category, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)

        existing_ch1 = MagicMock()
        existing_ch1.id = 11
        existing_ch1.position = 5
        existing_ch2 = MagicMock()
        existing_ch2.id = 22
        existing_ch2.position = 7

        mock_private_channel.edit = AsyncMock()
        mock_category.channels = [existing_ch1, existing_ch2, mock_private_channel]
        mock_guild.get_channel.return_value = mock_category
        mock_guild.get_member.return_value = mock_creator
        mock_guild.create_voice_channel = AsyncMock(return_value=mock_private_channel)

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=mock_category.id,
            ),
            patch("cogs.user_features.data_access_set_guild_active_private_channel", new_callable=AsyncMock),
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_private_channel.edit.assert_called_once_with(position=8)  # max(5, 7) + 1

    @pytest.mark.asyncio
    async def test_creator_moved_into_channel_when_in_voice(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_category, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)
        mock_creator.voice = MagicMock()
        mock_creator.voice.channel = MagicMock(spec=discord.VoiceChannel)
        mock_guild.get_channel.return_value = mock_category
        mock_guild.get_member.return_value = mock_creator
        mock_guild.create_voice_channel = AsyncMock(return_value=mock_private_channel)

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=mock_category.id,
            ),
            patch("cogs.user_features.data_access_set_guild_active_private_channel", new_callable=AsyncMock),
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_creator.move_to.assert_called_once_with(mock_private_channel)

    @pytest.mark.asyncio
    async def test_creator_not_moved_when_not_in_voice(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_category, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)
        mock_creator.voice = None
        mock_guild.get_channel.return_value = mock_category
        mock_guild.get_member.return_value = mock_creator
        mock_guild.create_voice_channel = AsyncMock(return_value=mock_private_channel)

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=mock_category.id,
            ),
            patch("cogs.user_features.data_access_set_guild_active_private_channel", new_callable=AsyncMock),
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_creator.move_to.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_sends_confirmation_message(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_category, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = mock_category
        mock_guild.get_member.return_value = mock_creator
        mock_guild.create_voice_channel = AsyncMock(return_value=mock_private_channel)

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=mock_category.id,
            ),
            patch("cogs.user_features.data_access_set_guild_active_private_channel", new_callable=AsyncMock),
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert str(mock_private_channel.id) in msg

    @pytest.mark.asyncio
    async def test_creation_canceled_when_creator_access_cannot_be_granted(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_category, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = mock_category
        mock_guild.get_member.return_value = mock_creator
        mock_guild.create_voice_channel = AsyncMock(return_value=mock_private_channel)
        mock_private_channel.delete = AsyncMock()

        with (
            patch("cogs.user_features.data_access_fetch_total_hours", return_value=PRIVATE_CHANNEL_MIN_HOURS + 1),
            patch(
                "cogs.user_features.data_access_get_guild_private_channel_category_id",
                return_value=mock_category.id,
            ),
            patch.object(cog, "_grant_private_channel_connect", new=AsyncMock(return_value=False)),
            patch(
                "cogs.user_features.data_access_set_guild_active_private_channel", new_callable=AsyncMock
            ) as mock_set,
        ):
            await cog.create_private_channel.callback(cog, mock_interaction)

        mock_private_channel.delete.assert_called_once()
        mock_set.assert_not_called()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "canceled creation" in msg


class TestPrivateChannelInviteCommand:
    @pytest.mark.asyncio
    async def test_invite_grants_access_and_sends_dm(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        target_user = MagicMock(spec=discord.Member)
        target_user.id = 333333333
        target_user.display_name = "InvitedUser"
        target_user.send = AsyncMock()

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = mock_private_channel
        mock_private_channel.set_permissions = AsyncMock()
        mock_private_channel.permissions_for = MagicMock(side_effect=[_perms(False, False), _perms(True, True)])

        with patch(
            "cogs.user_features.data_access_get_guild_active_private_channels",
            new=AsyncMock(return_value={mock_private_channel.id: (mock_creator.id, True)}),
        ):
            await cog.invite_to_private_channel.callback(cog, mock_interaction, target_user)

        mock_private_channel.set_permissions.assert_called_once_with(
            target_user, view_channel=True, connect=True, move_members=False
        )
        target_user.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "has been invited" in msg

    @pytest.mark.asyncio
    async def test_invite_reports_when_dm_closed(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        target_user = MagicMock(spec=discord.Member)
        target_user.id = 333333333
        target_user.display_name = "InvitedUser"
        target_user.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "DM blocked"))

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = mock_private_channel
        mock_private_channel.set_permissions = AsyncMock()
        mock_private_channel.permissions_for = MagicMock(side_effect=[_perms(False, False), _perms(True, True)])

        with patch(
            "cogs.user_features.data_access_get_guild_active_private_channels",
            new=AsyncMock(return_value={mock_private_channel.id: (mock_creator.id, True)}),
        ):
            await cog.invite_to_private_channel.callback(cog, mock_interaction, target_user)

        mock_private_channel.set_permissions.assert_called_once_with(
            target_user, view_channel=True, connect=True, move_members=False
        )
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "couldn't DM them" in msg

    @pytest.mark.asyncio
    async def test_invite_reports_when_access_cannot_be_granted(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        target_user = MagicMock(spec=discord.Member)
        target_user.id = 333333333
        target_user.display_name = "InvitedUser"
        target_user.send = AsyncMock()

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = mock_private_channel
        mock_private_channel.set_permissions = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Forbidden"))
        mock_guild.me.top_role.position = 1
        target_user.roles = [mock_guild.default_role]

        with patch(
            "cogs.user_features.data_access_get_guild_active_private_channels",
            new=AsyncMock(return_value={mock_private_channel.id: (mock_creator.id, True)}),
        ):
            await cog.invite_to_private_channel.callback(cog, mock_interaction, target_user)

        target_user.send.assert_not_called()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "couldn't grant that member access" in msg.lower()

    @pytest.mark.asyncio
    async def test_invite_fetches_channel_when_not_in_cache(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        target_user = MagicMock(spec=discord.Member)
        target_user.id = 333333333
        target_user.display_name = "InvitedUser"
        target_user.send = AsyncMock()

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = None
        mock_guild.fetch_channel = AsyncMock(return_value=mock_private_channel)
        mock_private_channel.set_permissions = AsyncMock()
        mock_private_channel.permissions_for = MagicMock(side_effect=[_perms(False, False), _perms(True, True)])

        with patch(
            "cogs.user_features.data_access_get_guild_active_private_channels",
            new=AsyncMock(return_value={mock_private_channel.id: (mock_creator.id, True)}),
        ):
            await cog.invite_to_private_channel.callback(cog, mock_interaction, target_user)

        mock_guild.fetch_channel.assert_any_call(mock_private_channel.id)
        mock_private_channel.set_permissions.assert_called_once_with(
            target_user, view_channel=True, connect=True, move_members=False
        )
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "has been invited" in msg

    @pytest.mark.asyncio
    async def test_invite_skips_stale_channel_and_uses_next_valid(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        stale_channel_id = 111111111
        valid_channel_id = mock_private_channel.id
        target_user = MagicMock(spec=discord.Member)
        target_user.id = 333333333
        target_user.display_name = "InvitedUser"
        target_user.send = AsyncMock()

        cog = UserFeatures(mock_bot)
        mock_private_channel.set_permissions = AsyncMock()
        mock_private_channel.permissions_for = MagicMock(side_effect=[_perms(False, False), _perms(True, True)])
        mock_guild.get_channel.side_effect = lambda channel_id: (
            None if channel_id == stale_channel_id else mock_private_channel
        )
        mock_guild.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Not found"))

        with (
            patch(
                "cogs.user_features.data_access_get_guild_active_private_channels",
                new=AsyncMock(
                    return_value={
                        stale_channel_id: (mock_creator.id, True),
                        valid_channel_id: (mock_creator.id, True),
                    }
                ),
            ),
            patch(
                "cogs.user_features.data_access_remove_guild_active_private_channel",
                new=AsyncMock(),
            ) as mock_remove,
        ):
            await cog.invite_to_private_channel.callback(cog, mock_interaction, target_user)

        mock_remove.assert_called_once_with(mock_guild.id, stale_channel_id)
        mock_private_channel.set_permissions.assert_called_once_with(
            target_user, view_channel=True, connect=True, move_members=False
        )
        target_user.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "has been invited" in msg

    @pytest.mark.asyncio
    async def test_invite_succeeds_when_target_already_has_access(
        self, mock_bot, mock_interaction, mock_guild, mock_creator, mock_private_channel
    ):
        from cogs.user_features import UserFeatures

        target_user = MagicMock(spec=discord.Member)
        target_user.id = 333333333
        target_user.display_name = "InvitedUser"
        target_user.send = AsyncMock()

        perms = MagicMock()
        perms.view_channel = True
        perms.connect = True

        cog = UserFeatures(mock_bot)
        mock_guild.get_channel.return_value = mock_private_channel
        mock_private_channel.set_permissions = AsyncMock()
        mock_private_channel.permissions_for.return_value = perms

        with patch(
            "cogs.user_features.data_access_get_guild_active_private_channels",
            new=AsyncMock(return_value={mock_private_channel.id: (mock_creator.id, True)}),
        ):
            await cog.invite_to_private_channel.callback(cog, mock_interaction, target_user)

        mock_private_channel.set_permissions.assert_not_called()
        target_user.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "has been invited" in msg


# ---------------------------------------------------------------------------
# Tests: private channel auto-deletion in on_voice_state_update
# ---------------------------------------------------------------------------


class TestPrivateChannelAutoDeletion:
    @pytest.fixture
    def mock_bot(self):
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 99999
        return bot

    def _make_member(self, guild, user_id=222):
        member = MagicMock(spec=discord.Member)
        member.id = user_id
        member.display_name = "TestUser"
        member.bot = False
        member.guild = guild
        return member

    def _make_guild(self, guild_id=111111111):
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.name = "Test Guild"
        return guild

    @pytest.mark.asyncio
    async def test_channel_deleted_when_last_user_leaves(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = []
        private_channel.delete = AsyncMock()

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = private_channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = None

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity"),
            patch("cogs.events.send_session_stats_to_queue", new_callable=AsyncMock),
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, True)},
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock) as mock_remove,
        ):
            await cog.on_voice_state_update(member, before, after)

        private_channel.delete.assert_called_once()
        mock_remove.assert_called_once_with(guild.id, private_channel.id)

    @pytest.mark.asyncio
    async def test_channel_not_deleted_when_bot_lacks_permissions(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        guild.me = MagicMock(spec=discord.Member)
        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = []
        private_channel.delete = AsyncMock()
        private_channel.permissions_for.return_value = SimpleNamespace(view_channel=False, manage_channels=False)

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = private_channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = None

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity"),
            patch("cogs.events.send_session_stats_to_queue", new_callable=AsyncMock),
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, True)},
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock) as mock_remove,
        ):
            await cog.on_voice_state_update(member, before, after)

        private_channel.delete.assert_not_called()
        mock_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_stale_entry_removed_after_repeated_missing_access(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        guild.me = MagicMock(spec=discord.Member)
        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = []
        private_channel.delete = AsyncMock()
        private_channel.permissions_for.return_value = SimpleNamespace(view_channel=False, manage_channels=False)

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = private_channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = None

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity"),
            patch("cogs.events.send_session_stats_to_queue", new_callable=AsyncMock),
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, True)},
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock) as mock_remove,
        ):
            await cog.on_voice_state_update(member, before, after)
            await cog.on_voice_state_update(member, before, after)
            await cog.on_voice_state_update(member, before, after)

        private_channel.delete.assert_not_called()
        mock_remove.assert_called_once_with(guild.id, private_channel.id)

    @pytest.mark.asyncio
    async def test_channel_not_deleted_when_still_has_members(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        remaining = MagicMock(spec=discord.Member)
        remaining.bot = False
        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = [remaining]
        private_channel.delete = AsyncMock()

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = private_channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = None

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity"),
            patch("cogs.events.send_session_stats_to_queue", new_callable=AsyncMock),
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, True)},
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock) as mock_remove,
        ):
            await cog.on_voice_state_update(member, before, after)

        private_channel.delete.assert_not_called()
        mock_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_regular_channel_not_deleted_when_empty(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        regular_channel = MagicMock(spec=discord.VoiceChannel)
        regular_channel.id = 333333333
        regular_channel.members = []
        regular_channel.delete = AsyncMock()

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = regular_channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = None

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity"),
            patch("cogs.events.send_session_stats_to_queue", new_callable=AsyncMock),
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            # Active private channel is a different channel
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={999999999: (12345, True)},
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock) as mock_remove,
        ):
            await cog.on_voice_state_update(member, before, after)

        regular_channel.delete.assert_not_called()
        mock_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_deleted_when_user_switches_away_and_channel_empty(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = []
        private_channel.delete = AsyncMock()

        other_channel = MagicMock(spec=discord.VoiceChannel)
        other_channel.id = 666666666
        other_channel.members = []

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = private_channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = other_channel

        cog = MyEventsCog(mock_bot)

        mock_cursor = MagicMock()
        mock_transaction = MagicMock()
        mock_transaction.__enter__ = MagicMock(return_value=mock_cursor)
        mock_transaction.__exit__ = MagicMock(return_value=None)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[other_channel.id]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.database_manager") as mock_db,
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch("cogs.events.data_access_update_voice_user_list", new_callable=AsyncMock),
            patch("cogs.events.get_any_siege_activity", return_value=None),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, True)},
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock) as mock_remove,
        ):
            mock_db.data_access_transaction.return_value = mock_transaction
            await cog.on_voice_state_update(member, before, after)

        private_channel.delete.assert_called_once()
        mock_remove.assert_called_once_with(guild.id, private_channel.id)

    @pytest.mark.asyncio
    async def test_no_deletion_when_no_active_private_channel(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        channel = MagicMock(spec=discord.VoiceChannel)
        channel.id = 555555555
        channel.members = []
        channel.delete = AsyncMock()

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = None

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity"),
            patch("cogs.events.send_session_stats_to_queue", new_callable=AsyncMock),
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={},
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock) as mock_remove,
        ):
            await cog.on_voice_state_update(member, before, after)

        channel.delete.assert_not_called()
        mock_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_two_private_channels_only_empty_one_deleted(self, mock_bot):
        """When two private channels exist and only one becomes empty, only that one is deleted."""
        from cogs.events import MyEventsCog

        guild = self._make_guild()

        empty_private = MagicMock(spec=discord.VoiceChannel)
        empty_private.id = 555555555
        empty_private.members = []
        empty_private.delete = AsyncMock()

        busy_private = MagicMock(spec=discord.VoiceChannel)
        busy_private.id = 666666666
        busy_private.members = [MagicMock()]
        busy_private.delete = AsyncMock()

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = empty_private
        after = MagicMock(spec=discord.VoiceState)
        after.channel = None

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity"),
            patch("cogs.events.send_session_stats_to_queue", new_callable=AsyncMock),
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={
                    empty_private.id: (12345, True),
                    busy_private.id: (67890, True),
                },
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock) as mock_remove,
        ):
            await cog.on_voice_state_update(member, before, after)

        empty_private.delete.assert_called_once()
        busy_private.delete.assert_not_called()
        mock_remove.assert_called_once_with(guild.id, empty_private.id)

    @pytest.mark.asyncio
    async def test_channel_deleted_when_before_members_contains_only_leaving_member(self, mock_bot):
        """Delete channel even if Discord still reports the leaving member in before.channel.members."""
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        member = self._make_member(guild, user_id=222)

        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = [member]  # stale state snapshot
        private_channel.delete = AsyncMock()

        before = MagicMock(spec=discord.VoiceState)
        before.channel = private_channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = None

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity"),
            patch("cogs.events.send_session_stats_to_queue", new_callable=AsyncMock),
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, True)},
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock) as mock_remove,
        ):
            await cog.on_voice_state_update(member, before, after)

        private_channel.delete.assert_called_once()
        mock_remove.assert_called_once_with(guild.id, private_channel.id)


# ---------------------------------------------------------------------------
# Tests: activity tracking (only voice_channel_ids + tracked private channels)
# ---------------------------------------------------------------------------


class TestPrivateChannelTracking:
    @pytest.fixture
    def mock_bot(self):
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 99999
        return bot

    def _make_guild(self, guild_id=111111111):
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.name = "Test Guild"
        return guild

    def _make_member(self, guild, user_id=222):
        member = MagicMock(spec=discord.Member)
        member.id = user_id
        member.display_name = "TestUser"
        member.bot = False
        member.guild = guild
        return member

    @pytest.mark.asyncio
    async def test_join_untracked_private_channel_skips_insert(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = [MagicMock()]

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = None
        after = MagicMock(spec=discord.VoiceState)
        after.channel = private_channel

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity") as mock_insert,
            patch("cogs.events.data_access_update_voice_user_list", new_callable=AsyncMock),
            patch("cogs.events.get_any_siege_activity", return_value=None),
            patch("cogs.events.send_private_notification_following_user", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, False)},  # track=False
            ),
        ):
            await cog.on_voice_state_update(member, before, after)

        mock_insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_join_tracked_private_channel_inserts_activity(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = [MagicMock()]

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = None
        after = MagicMock(spec=discord.VoiceState)
        after.channel = private_channel

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity") as mock_insert,
            patch("cogs.events.data_access_update_voice_user_list", new_callable=AsyncMock),
            patch("cogs.events.get_any_siege_activity", return_value=None),
            patch("cogs.events.send_private_notification_following_user", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, True)},  # track=True
            ),
        ):
            await cog.on_voice_state_update(member, before, after)

        mock_insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_join_non_configured_non_private_channel_skips_insert(self, mock_bot):
        """Channels that are neither in voice_channel_ids nor private channels are not tracked."""
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        random_channel = MagicMock(spec=discord.VoiceChannel)
        random_channel.id = 888888888  # not in voice_channel_ids, not a private channel
        random_channel.members = [MagicMock()]

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = None
        after = MagicMock(spec=discord.VoiceState)
        after.channel = random_channel

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity") as mock_insert,
            patch("cogs.events.data_access_update_voice_user_list", new_callable=AsyncMock),
            patch("cogs.events.get_any_siege_activity", return_value=None),
            patch("cogs.events.send_private_notification_following_user", new_callable=AsyncMock),
            patch("cogs.events.data_access_get_guild_active_private_channels", return_value={}),
        ):
            await cog.on_voice_state_update(member, before, after)

        mock_insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_leave_untracked_private_channel_skips_insert(self, mock_bot):
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = []

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = private_channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = None

        cog = MyEventsCog(mock_bot)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[111]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.insert_user_activity") as mock_insert,
            patch("cogs.events.send_session_stats_to_queue", new_callable=AsyncMock),
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, False)},  # track=False
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock),
        ):
            await cog.on_voice_state_update(member, before, after)

        mock_insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_from_untracked_private_to_tracked_logs_only_connect(self, mock_bot):
        """Moving from untracked private → tracked channel logs only the CONNECT, no full move transaction."""
        from cogs.events import MyEventsCog

        guild = self._make_guild()
        private_channel = MagicMock(spec=discord.VoiceChannel)
        private_channel.id = 555555555
        private_channel.members = []
        private_channel.delete = AsyncMock()

        other_channel = MagicMock(spec=discord.VoiceChannel)
        other_channel.id = 666666666
        other_channel.members = []

        member = self._make_member(guild)
        before = MagicMock(spec=discord.VoiceState)
        before.channel = private_channel
        after = MagicMock(spec=discord.VoiceState)
        after.channel = other_channel

        cog = MyEventsCog(mock_bot)

        mock_cursor = MagicMock()
        mock_transaction = MagicMock()
        mock_transaction.__enter__ = MagicMock(return_value=mock_cursor)
        mock_transaction.__exit__ = MagicMock(return_value=None)

        with (
            patch("cogs.events.data_access_get_guild_voice_channel_ids", return_value=[other_channel.id]),
            patch("cogs.events.data_access_get_guild_schedule_text_channel_id", return_value=333),
            patch("cogs.events.database_manager") as mock_db,
            patch("cogs.events.insert_user_activity") as mock_insert,
            patch("cogs.events.data_access_remove_voice_user_list", new_callable=AsyncMock),
            patch("cogs.events.data_access_update_voice_user_list", new_callable=AsyncMock),
            patch("cogs.events.get_any_siege_activity", return_value=None),
            patch(
                "cogs.events.data_access_get_guild_active_private_channels",
                return_value={private_channel.id: (12345, False)},  # track=False
            ),
            patch("cogs.events.data_access_remove_guild_active_private_channel", new_callable=AsyncMock),
        ):
            mock_db.data_access_transaction.return_value = mock_transaction
            await cog.on_voice_state_update(member, before, after)

        # Full move transaction must NOT have been called
        mock_db.data_access_transaction.assert_not_called()
