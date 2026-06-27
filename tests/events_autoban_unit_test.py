"""Unit tests for event autoban behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from cogs import events
from cogs.events import AUTOBAN_USER_IDS, MyEventsCog


async def test_on_member_join_autobans_listed_user(monkeypatch) -> None:
    """A listed joining user is banned before the welcome-message flow."""
    monkeypatch.setattr(events, "data_access_get_new_user_text_channel_id", AsyncMock())
    member = Mock()
    member.id = 1177820750636400711
    member.bot = False
    member.display_name = "Autoban User"
    member.guild = SimpleNamespace(id=123, name="Test Guild", ban=AsyncMock())

    cog = MyEventsCog(Mock())

    await cog.on_member_join(member)

    member.guild.ban.assert_awaited_once_with(member, reason="User is on the bot autoban list.")
    events.data_access_get_new_user_text_channel_id.assert_not_awaited()


def test_autoban_list_contains_requested_user_id() -> None:
    """The requested Discord user ID is configured for autoban."""
    assert 1177820750636400711 in AUTOBAN_USER_IDS
