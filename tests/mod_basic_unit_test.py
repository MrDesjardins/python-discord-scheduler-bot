"""Tests for basic moderator commands."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from cogs.mod_basic import ModBasic


def _interaction(guild: Mock, member: Mock) -> Mock:
    interaction = Mock(spec=discord.Interaction)
    interaction.guild = guild
    interaction.user = member
    interaction.response = Mock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()
    return interaction


async def test_reset_rank_roles_uses_single_member_edit_and_preserves_other_roles() -> None:
    """Reset rank should update each member in one edit and keep non-rank roles."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = ModBasic(bot)

    guild = Mock(spec=discord.Guild)
    guild.name = "Guild"
    guild.id = 123
    guild.default_role = SimpleNamespace(name="@everyone", managed=False)
    guild.roles = [
        SimpleNamespace(name="Mod"),
        SimpleNamespace(name="Support"),
        SimpleNamespace(name="Diamond"),
        SimpleNamespace(name="Unranked"),
    ]

    member = SimpleNamespace(
        id=456,
        display_name="Player",
        bot=False,
        roles=[guild.roles[1], guild.roles[2]],
        edit=AsyncMock(),
    )

    already_unranked = SimpleNamespace(
        id=457,
        display_name="Idle",
        bot=False,
        roles=[guild.roles[1], guild.roles[3]],
        edit=AsyncMock(),
    )

    guild.members = [member, already_unranked]

    async def async_members():
        yield member
        yield already_unranked

    guild.fetch_members = Mock(return_value=async_members())

    interaction = _interaction(
        guild,
        SimpleNamespace(display_name="Admin", id=1, guild_permissions=SimpleNamespace(administrator=True), roles=[]),
    )

    with patch("cogs.mod_basic.discord.Member", SimpleNamespace):
        await cog.reset_rank_roles.callback(cog, interaction)

    member.edit.assert_awaited_once()
    assert member.edit.await_args.kwargs["roles"] == [guild.roles[1], guild.roles[3]]
    already_unranked.edit.assert_not_called()
    interaction.followup.send.assert_awaited_once()


async def test_reset_rank_roles_excludes_default_and_managed_roles_from_edit() -> None:
    """Reset rank must not pass @everyone or managed roles into member.edit(roles=...)."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = ModBasic(bot)

    guild = Mock(spec=discord.Guild)
    guild.name = "Guild"
    guild.id = 123
    everyone = SimpleNamespace(name="@everyone", managed=True)
    guild.default_role = everyone
    booster = SimpleNamespace(name="Server Booster", managed=True)
    support = SimpleNamespace(name="Support", managed=False)
    diamond = SimpleNamespace(name="Diamond", managed=False)
    unranked = SimpleNamespace(name="Unranked", managed=False)
    guild.roles = [everyone, booster, support, diamond, unranked]

    member = SimpleNamespace(
        id=456,
        display_name="Player",
        bot=False,
        roles=[everyone, booster, support, diamond],
        edit=AsyncMock(),
    )

    guild.members = [member]

    async def async_members():
        yield member

    guild.fetch_members = Mock(return_value=async_members())

    interaction = _interaction(
        guild,
        SimpleNamespace(display_name="Admin", id=1, guild_permissions=SimpleNamespace(administrator=True), roles=[]),
    )

    with patch("cogs.mod_basic.discord.Member", SimpleNamespace):
        await cog.reset_rank_roles.callback(cog, interaction)

    edited_roles = member.edit.await_args.kwargs["roles"]
    assert support in edited_roles
    assert unranked in edited_roles
    assert diamond not in edited_roles
    assert everyone not in edited_roles
    assert booster not in edited_roles


async def test_reset_rank_roles_does_not_edit_bots() -> None:
    """Reset rank should only call member.edit on human accounts."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = ModBasic(bot)

    guild = Mock(spec=discord.Guild)
    guild.name = "Guild"
    guild.id = 123
    guild.default_role = SimpleNamespace(name="@everyone", managed=False)
    guild.roles = [
        SimpleNamespace(name="Diamond"),
        SimpleNamespace(name="Unranked"),
    ]

    human = SimpleNamespace(
        id=1,
        display_name="Player",
        bot=False,
        roles=[guild.roles[0]],
        edit=AsyncMock(),
    )
    other_bot = SimpleNamespace(
        id=2,
        display_name="HelperBot",
        bot=True,
        roles=[guild.roles[0]],
        edit=AsyncMock(),
    )

    guild.members = [human, other_bot]

    async def async_members():
        yield human
        yield other_bot

    guild.fetch_members = Mock(return_value=async_members())

    interaction = _interaction(
        guild,
        SimpleNamespace(display_name="Admin", id=99, guild_permissions=SimpleNamespace(administrator=True), roles=[]),
    )

    with patch("cogs.mod_basic.discord.Member", SimpleNamespace):
        await cog.reset_rank_roles.callback(cog, interaction)

    human.edit.assert_awaited_once()
    other_bot.edit.assert_not_called()
    followup_message = interaction.followup.send.await_args.args[0]
    assert "Ignored 1 bot(s)" in followup_message
