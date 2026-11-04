"""Unit tests for the DM asking the bot owner to solve a tracker.gg challenge"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deps import tracker_block_alert, tracker_pacing
from ui.tracker_block_view import TrackerBlockView


@pytest.fixture(autouse=True)
def reset_pacing_state(monkeypatch):
    """Each test starts with no block and no alert sent yet"""
    monkeypatch.setattr(tracker_pacing, "_blocked_until", 0.0)
    monkeypatch.setattr(tracker_pacing, "_attention_requested", False)
    monkeypatch.setattr(tracker_pacing, "_last_attention_at", float("-inf"))


def _bot_with_owner() -> tuple[MagicMock, AsyncMock]:
    owner = AsyncMock()
    bot = MagicMock()
    bot.application_info = AsyncMock(return_value=MagicMock(owner=owner))
    return bot, owner


def test_message_gives_the_command_and_the_cooldown():
    message = tracker_block_alert.build_tracker_block_message(1800.0)

    assert "another 30 min" in message
    assert "ssh -Y " in message
    assert f"cd {tracker_block_alert.REPOSITORY_ROOT} && ENV=dev" in message
    assert "deployment/validate_tracker_cloudflare.py" in message


def test_message_without_cooldown_does_not_claim_a_pause():
    assert "paused" not in tracker_block_alert.build_tracker_block_message(0.0)


async def test_nothing_is_sent_without_a_request():
    bot, owner = _bot_with_owner()

    await tracker_block_alert.send_tracker_block_alert(bot)

    owner.send.assert_not_called()


async def test_request_dms_the_owner_once_with_the_button():
    bot, owner = _bot_with_owner()
    tracker_pacing.request_tracker_attention()

    await tracker_block_alert.send_tracker_block_alert(bot)
    await tracker_block_alert.send_tracker_block_alert(bot)

    owner.send.assert_called_once()
    assert isinstance(owner.send.call_args.kwargs["view"], TrackerBlockView)


async def test_failed_dm_is_requested_again():
    bot, owner = _bot_with_owner()
    owner.send.side_effect = RuntimeError("DMs closed")
    tracker_pacing.request_tracker_attention()

    with patch("deps.tracker_block_alert.print_error_log"):
        await tracker_block_alert.send_tracker_block_alert(bot)

    assert tracker_pacing._attention_requested is True  # pylint: disable=protected-access


async def test_solved_button_ends_the_cooldown_and_disables_itself():
    tracker_pacing._blocked_until = tracker_pacing.time.monotonic() + 3600  # pylint: disable=protected-access
    view = TrackerBlockView()
    button = view.children[0]
    interaction = MagicMock()
    interaction.response.edit_message = AsyncMock()
    interaction.followup.send = AsyncMock()

    await button.callback(interaction)

    assert tracker_pacing.tracker_block_remaining_seconds() == 0
    assert button.disabled is True
    interaction.response.edit_message.assert_awaited_once_with(view=view)
    interaction.followup.send.assert_awaited_once()
