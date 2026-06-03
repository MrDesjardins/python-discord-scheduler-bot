"""Unit tests for rank-account commands using current-season rank role sync."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from cogs.mod_onbehalf import ModeratorOnUserBehalf
from cogs.user_features import UserFeatures
from deps.data_access_data_class import UserInfo
from ui.setup_user_profile_view import SetupUserProfileModal


def _interaction(member: Mock, guild: Mock) -> Mock:
    interaction = Mock(spec=discord.Interaction)
    interaction.user = member
    interaction.guild = guild
    interaction.guild_id = guild.id
    interaction.response = Mock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()
    return interaction


async def test_set_active_user_account_syncs_current_season_rank_for_active_account() -> None:
    """Changing active account immediately syncs rank role from that active account."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = UserFeatures(bot)
    guild = Mock(spec=discord.Guild)
    guild.id = 123
    member = Mock(spec=discord.Member)
    member.id = 456
    interaction = _interaction(member, guild)

    with (
        patch("cogs.user_features.data_access_set_ubisoft_username_active") as mock_set_active,
        patch("cogs.user_features.fetch_current_season_rank_for_account", new_callable=AsyncMock) as mock_fetch,
        patch("cogs.user_features.set_member_role_from_current_rank", new_callable=AsyncMock) as mock_set_role,
    ):
        mock_fetch.return_value = ("Emerald", 3839)
        mock_set_role.return_value = True
        await cog.set_active_user_account.callback(cog, interaction, "active_ubi")

    mock_set_active.assert_called_once_with(member.id, "active_ubi")
    mock_fetch.assert_awaited_once_with("active_ubi")
    mock_set_role.assert_awaited_once_with(guild, member, "Emerald")
    interaction.followup.send.assert_awaited_once()


async def test_set_max_user_account_syncs_current_season_rank_for_saved_active_account() -> None:
    """Changing max account preserves active account as the current-season role source."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = UserFeatures(bot)
    guild = Mock(spec=discord.Guild)
    guild.id = 123
    member = Mock(spec=discord.Member)
    member.id = 456
    interaction = _interaction(member, guild)
    view = Mock()
    view.result = True
    view.wait = AsyncMock()
    user_info = UserInfo(
        id=member.id,
        display_name="Player",
        ubisoft_username_max="old_max",
        ubisoft_username_active="active_ubi",
        r6_tracker_active_id=None,
        time_zone="US/Eastern",
        max_mmr=3200,
    )

    with (
        patch("cogs.user_features.ConfirmCancelView", return_value=view),
        patch("cogs.user_features.data_access_get_member", new_callable=AsyncMock, return_value=member),
        patch("cogs.user_features.data_access_set_ubisoft_username_max") as mock_set_max,
        patch("cogs.user_features.fetch_user_info_by_user_id", new_callable=AsyncMock, return_value=user_info),
        patch("cogs.user_features.fetch_current_and_max_rank_for_accounts", new_callable=AsyncMock) as mock_fetch,
        patch("cogs.user_features.set_member_role_from_current_rank", new_callable=AsyncMock) as mock_set_role,
        patch("cogs.user_features.data_access_set_max_mmr") as mock_set_mmr,
    ):
        mock_fetch.return_value = ("Emerald", 3839, "Diamond", 4343)
        mock_set_role.return_value = True
        await cog.set_max_user_account.callback(cog, interaction, "max_ubi")

    mock_set_max.assert_called_once_with(member.id, "max_ubi")
    mock_fetch.assert_awaited_once_with("max_ubi", "active_ubi")
    mock_set_role.assert_awaited_once_with(guild, member, "Emerald")
    mock_set_mmr.assert_called_once_with(member.id, 4343)


async def test_setup_profile_syncs_current_season_rank_for_active_account() -> None:
    """Setup profile assigns rank using the active account, not the max account."""
    guild = Mock(spec=discord.Guild)
    guild.id = 123
    member = Mock(spec=discord.Member)
    member.id = 456
    member.display_name = "Player"
    bot = Mock()
    bot.guild_emoji = {guild.id: {"Emerald": "1", "Copper": "2"}}
    view = SimpleNamespace(
        bot=bot,
        guild=guild,
        member=member,
        max_rank_account=None,
        active_account=None,
        user_timezone="US/Eastern",
    )
    modal = object.__new__(SetupUserProfileModal)
    modal.view = view
    modal.max_rank_account_input = SimpleNamespace(value="max_ubi")
    modal.active_account_input = SimpleNamespace(value="active_ubi")
    interaction = _interaction(member, guild)

    with (
        patch(
            "ui.setup_user_profile_view.fetch_current_and_max_rank_for_accounts", new_callable=AsyncMock
        ) as mock_fetch,
        patch("ui.setup_user_profile_view.upsert_user_info") as mock_upsert,
        patch("ui.setup_user_profile_view.set_member_role_from_current_rank", new_callable=AsyncMock) as mock_set_role,
        patch(
            "ui.setup_user_profile_view.data_access_get_gaming_session_text_channel_id", new_callable=AsyncMock
        ) as mock_channel,
    ):
        mock_fetch.return_value = ("Emerald", 3839, "Diamond", 4343)
        mock_set_role.return_value = True
        mock_channel.return_value = 789
        await modal.on_submit(interaction)

    mock_fetch.assert_awaited_once_with("max_ubi", "active_ubi")
    mock_upsert.assert_called_once_with(member.id, "Player", "max_ubi", "active_ubi", None, "US/Eastern", 4343)
    mock_set_role.assert_awaited_once_with(guild, member, "Emerald")


async def test_moderator_set_active_account_syncs_current_season_rank() -> None:
    """Moderator-side active-account changes should refresh the current-season role immediately."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = ModeratorOnUserBehalf(bot)
    guild = Mock(spec=discord.Guild)
    guild.id = 123
    member = Mock(spec=discord.Member)
    member.id = 456
    interaction = _interaction(member, guild)

    with (
        patch("cogs.mod_onbehalf.data_access_set_ubisoft_username_active") as mock_set_active,
        patch("cogs.mod_onbehalf.sync_member_current_rank_role", new_callable=AsyncMock) as mock_sync,
    ):
        mock_sync.return_value = ("Emerald", 3839)
        await cog.set_user_ubisoft_active_account_for_other_user.callback(cog, interaction, member, "active_ubi")

    mock_set_active.assert_called_once_with(member.id, "active_ubi")
    mock_sync.assert_awaited_once_with(guild, member, "active_ubi")


async def test_moderator_set_max_account_syncs_current_season_rank_for_active_account() -> None:
    """Moderator-side max-account changes should refresh the current-season role from the saved active account."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = ModeratorOnUserBehalf(bot)
    guild = Mock(spec=discord.Guild)
    guild.id = 123
    member = Mock(spec=discord.Member)
    member.id = 456
    interaction = _interaction(member, guild)
    user_info = UserInfo(
        id=member.id,
        display_name="Player",
        ubisoft_username_max="old_max",
        ubisoft_username_active="active_ubi",
        r6_tracker_active_id=None,
        time_zone="US/Eastern",
        max_mmr=3200,
    )

    with (
        patch("cogs.mod_onbehalf.data_access_set_ubisoft_username_max") as mock_set_max,
        patch("cogs.mod_onbehalf.fetch_user_info_by_user_id", new_callable=AsyncMock, return_value=user_info),
        patch("cogs.mod_onbehalf.sync_member_current_rank_role", new_callable=AsyncMock) as mock_sync,
    ):
        mock_sync.return_value = ("Emerald", 3839)
        await cog.set_user_ubisoft_max_rank_for_other_user.callback(cog, interaction, member, "max_ubi")

    mock_set_max.assert_called_once_with(member.id, "max_ubi")
    mock_sync.assert_awaited_once_with(guild, member, "active_ubi")
