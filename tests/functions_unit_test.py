"""Test Functions"""

from datetime import datetime, timezone
from unittest.mock import call, patch, Mock, AsyncMock
import discord
import pytest
from deps.functions_model import get_empty_votes, get_supported_time_time_label
from deps.functions import (
    get_last_schedule_message,
    get_rotated_number_from_current_day,
    get_sha,
    get_time_choices,
    get_url_user_profile_main,
    get_url_user_profile_overview,
    get_url_user_ranked_matches,
    get_url_api_ranked_matches,
    most_common,
)
from deps.models import TimeLabel
from deps.data_access_data_class import UserInfo
import deps.functions
import deps.bot_common_actions
from deps.mybot import MyBot
from deps.values import MSG_UNIQUE_STRING
import deps.siege


def test_most_common_no_tie():
    """Return the most frequent element"""
    list1 = [1, 2, 2]
    result = most_common(list1)
    assert result == 2


def test_most_common_tie():
    """Return the first most common"""
    list1 = [2, 2, 3, 3]
    result = most_common(list1)
    assert result == 2


def test_get_empty_votes():
    """Return an object with empty list of user for each time"""
    result = get_empty_votes()
    assert result == {
        "1pm": [],
        "2pm": [],
        "3pm": [],
        "4pm": [],
        "5pm": [],
        "6pm": [],
        "7pm": [],
        "8pm": [],
        "9pm": [],
        "10pm": [],
        "11pm": [],
        "12am": [],
        "1am": [],
        "2am": [],
        "3am": [],
    }


def test_get_supported_time_time_label():
    """Return a list of TimeLabel objects that represent the supported times"""
    result = get_supported_time_time_label()
    assert result == [
        TimeLabel("1pm", "3pm", "1pm Eastern Time"),
        TimeLabel("2pm", "3pm", "2pm Eastern Time"),
        TimeLabel("3pm", "3pm", "3pm Eastern Time"),
        TimeLabel("4pm", "4pm", "4pm Eastern Time"),
        TimeLabel("5pm", "5pm", "5pm Eastern Time"),
        TimeLabel("6pm", "6pm", "6pm Eastern Time"),
        TimeLabel("7pm", "7pm", "7pm Eastern Time"),
        TimeLabel("8pm", "8pm", "8pm Eastern Time"),
        TimeLabel("9pm", "9pm", "9pm Eastern Time"),
        TimeLabel("10pm", "10pm", "10pm Eastern Time"),
        TimeLabel("11pm", "11pm", "11pm Eastern Time"),
        TimeLabel("12am", "12am", "12am Eastern Time"),
        TimeLabel("1am", "1am", "1am Eastern Time"),
        TimeLabel("2am", "2am", "2am Eastern Time"),
        TimeLabel("3am", "2am", "3am Eastern Time"),
    ]


def test_get_sha():
    """Test to see if we can access the subprocess of git"""
    sha = get_sha()
    assert len(sha) > 8


def test_profile_url():
    """Test the URL for the user profile"""
    url = get_url_user_profile_main("user1")
    assert url == "https://r6.tracker.network/r6siege/profile/uplay/user1"


def test_profile_overview_url():
    """Test the URL for the user profile overview"""
    url = get_url_user_profile_overview("user1")
    assert url == "https://r6.tracker.network/r6siege/profile/uplay/user1/overview"


def test_get_url_user_ranked_matches():
    """Test the URL for the user rank page"""
    url = get_url_user_ranked_matches("user1")
    assert url == "https://r6.tracker.network/r6siege/profile/uplay/user1/matches?playlist=ranked"


def test_get_url_user_ranked_matches_api():
    """Test the URL for the user rank API"""
    url = get_url_api_ranked_matches("user1")
    assert url == "https://api.tracker.gg/api/v2/r6siege/standard/matches/uplay/user1?gamemode=pvp_ranked"


def test_get_url_user_ranked_matches_api_with_name_with_dot():
    """Test the URL for the user rank API"""
    url = get_url_api_ranked_matches("GuyHero.")
    assert url == "https://api.tracker.gg/api/v2/r6siege/standard/matches/uplay/GuyHero.?gamemode=pvp_ranked"


def test_choices_items():
    """Assert the number of choices for time"""
    choices = get_time_choices()
    assert len(choices) == 15
    assert choices[0].value == "1pm"
    assert choices[0].name == "1pm"
    assert choices[14].value == "3am"
    assert choices[14].name == "3am"


@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
def test_get_rotated_number_from_current_day_1(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 1, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(1)
    assert result == 0
    result = get_rotated_number_from_current_day(5)
    assert result == 0
    result = get_rotated_number_from_current_day(12)
    assert result == 0


@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
def test_get_rotated_number_from_current_day_2(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 10, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(1)
    assert result == 0
    result = get_rotated_number_from_current_day(5)
    assert result == 4
    result = get_rotated_number_from_current_day(6)
    assert result == 3
    result = get_rotated_number_from_current_day(12)
    assert result == 9


@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
def test_get_rotated_number_from_current_day_3(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 1, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(3)
    assert result == 0
    mock_get_now_eastern.return_value = datetime(2024, 1, 2, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(3)
    assert result == 1
    mock_get_now_eastern.return_value = datetime(2024, 1, 3, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(3)
    assert result == 2
    mock_get_now_eastern.return_value = datetime(2024, 1, 4, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(3)
    assert result == 0


async def test_get_last_schedule_message_no_channel():
    """Test how the number rotates based on the current day"""
    bot = Mock(spec=MyBot)
    result = await get_last_schedule_message(
        bot,
        None,
    )
    assert result is None


@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
async def test_get_last_schedule_message_no_last_message(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 1, 10, 0, 0, 6318, timezone.utc)
    bot = Mock(spec=MyBot)
    channel = Mock(spec=discord.TextChannel)

    # Mock an empty async iterable for history
    async def async_iter():
        for _ in []:
            yield _

    channel.history = Mock(return_value=async_iter())  # Ensure it returns an async iterable

    result = await get_last_schedule_message(bot, channel)
    assert result is None


@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
async def test_get_last_schedule_message_with_last_message_but_not_bot(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 1, 10, 0, 0, 6318, timezone.utc)
    bot = Mock(spec=MyBot)
    channel = Mock(spec=discord.TextChannel)

    # Mock an empty async iterable for history
    async def async_iter():
        for _ in [Mock(spec=discord.Message, author=Mock(spec=discord.User, bot=False))]:
            yield _

    channel.history = Mock(return_value=async_iter())  # Ensure it returns an async iterable

    result = await get_last_schedule_message(bot, channel)
    assert result is None


@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
async def test_get_last_schedule_message_with_last_message_is_bot_with_not_right_msg_format(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 1, 10, 0, 0, 6318, timezone.utc)
    bot = Mock(spec=MyBot)
    bot.user = Mock(spec=discord.User)
    channel = Mock(spec=discord.TextChannel)

    # Mock an empty async iterable for history
    msg1 = Mock(spec=discord.Message, author=Mock(spec=discord.User, bot=True))
    msg1.author = bot.user
    msg1.embeds = []
    msg1.content = "Not the right message format"

    async def async_iter():
        for _ in [msg1]:
            yield _

    channel.history = Mock(return_value=async_iter())  # Ensure it returns an async iterable

    result = await get_last_schedule_message(bot, channel)
    assert result is None


@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
async def test_get_last_schedule_message_with_last_message_is_bot_with_right_msg_format(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 1, 10, 0, 0, 6318, timezone.utc)
    bot = Mock(spec=MyBot)
    bot.user = Mock(spec=discord.User)
    channel = Mock(spec=discord.TextChannel)

    # Mock an empty async iterable for history
    msg1 = Mock(spec=discord.Message, author=Mock(spec=discord.User, bot=True))
    msg1.author = bot.user
    msg1.embeds = []
    msg1.content = f"{MSG_UNIQUE_STRING} And more"

    async def async_iter():
        for _ in [msg1]:
            yield _

    channel.history = Mock(return_value=async_iter())  # Ensure it returns an async iterable

    result = await get_last_schedule_message(bot, channel)
    assert result is msg1


async def test_set_member_role_from_rank_with_role_to_remove_remove_all_possibles_rank_then_add():
    """
    The test ensures that the function
    1) Adds the new role
    2) Removes the other managed rank roles
    Tag: #good_test, #good_practice
    """
    # Arrange
    guild = Mock(spec=discord.Guild)
    member = Mock(spec=discord.Member)
    role_1 = Mock(spec=discord.Role, name="rank1")  # Create a new role for rank1
    role_2 = Mock(spec=discord.Role, name="rank2")  # Create a new role for rank2
    member.roles = [role_1, role_2]
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()

    def mock_discord_get(roles, name):
        """Return different roles based on name lookup."""
        if name == "rank1":
            return role_1
        elif name == "rank2":
            return role_2
        return None

    discord.utils.get = Mock(side_effect=mock_discord_get)
    # Act
    with (
        patch("deps.functions.siege_ranks", ["rank1", "rank2"]),
        patch("deps.functions.resolve_rank_role_name", side_effect=lambda rank: rank),
    ):
        await deps.functions.set_member_role_from_rank(guild, member, "rank2")
        # Assert
        member.add_roles.assert_called_once_with(role_2, reason="Bot assigned role based on rank from R6 Tracker")
        member.remove_roles.assert_called_once_with(
            role_1, reason="Bot removed prior rank roles before assigning rank2."
        )


async def test_set_member_role_from_rank_missing_target_role_preserves_existing_roles():
    """If the target role is missing, the function should fail before mutating roles."""
    guild = Mock(spec=discord.Guild)
    member = Mock(spec=discord.Member)
    role_1 = Mock(spec=discord.Role, name="rank1")
    member.roles = [role_1]
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()

    def mock_discord_get(roles, name):
        if name == "rank1":
            return role_1
        return None

    discord.utils.get = Mock(side_effect=mock_discord_get)
    with patch("deps.functions.siege_ranks", ["rank1", "rank2"]):
        with pytest.raises(ValueError):
            await deps.functions.set_member_role_from_rank(guild, member, "rank2")

    member.add_roles.assert_not_called()
    member.remove_roles.assert_not_called()


async def test_sync_member_current_rank_role_uses_current_rank():
    """Current-season rank sync assigns the fetched current rank role."""
    guild = Mock(spec=discord.Guild)
    member = Mock(spec=discord.Member)
    member.display_name = "Player"

    with (
        patch(
            "deps.bot_common_actions.data_access_get_r6tracker_current_season_rank",
            new_callable=AsyncMock,
            return_value=("Unranked", 0),
        ) as mock_fetch,
        patch("deps.bot_common_actions.set_member_role_from_rank", new_callable=AsyncMock) as mock_set_role,
    ):
        result = await deps.bot_common_actions.sync_member_current_rank_role(guild, member, "active_ubi")

    assert result == ("Unranked", 0)
    mock_fetch.assert_awaited_once_with("active_ubi", True)
    mock_set_role.assert_awaited_once_with(guild, member, "Unranked")


def _user_info(user_id: int, display_name: str, active_account: str | None = "ubi") -> UserInfo:
    return UserInfo(user_id, display_name, None, active_account, None, "UTC", 0)


async def test_refresh_current_rank_roles_guild_scope_only_updates_target_guild():
    """Guild-scoped rank refresh only changes members in the requested guild."""
    bot = Mock(spec=MyBot)
    target_guild = Mock(spec=discord.Guild)
    target_guild.id = 1
    target_guild.name = "Target"
    other_guild = Mock(spec=discord.Guild)
    other_guild.id = 2
    other_guild.name = "Other"
    bot.guilds = [target_guild, other_guild]

    member = Mock(spec=discord.Member)
    member.id = 123
    member.display_name = "Player"
    member.mention = "<@123>"
    member.roles = []
    target_guild.get_member.return_value = member
    other_guild.get_member.return_value = member

    begin_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2026, 1, 2, tzinfo=timezone.utc)

    with (
        patch("deps.bot_common_actions.get_active_user_info", return_value=[_user_info(123, "Player")]),
        patch(
            "deps.bot_common_actions.fetch_current_season_rank_for_account",
            new_callable=AsyncMock,
            return_value=("Gold", 0),
        ),
        patch(
            "deps.bot_common_actions.set_member_role_from_current_rank", new_callable=AsyncMock, return_value=True
        ) as mock_set_role,
        patch("deps.bot_common_actions.post_rank_change_notifications", new_callable=AsyncMock) as mock_notify,
    ):
        summary = await deps.bot_common_actions.refresh_current_rank_roles_cross_guilds(
            begin_time,
            end_time,
            bot,
            guild=target_guild,
            include_connected_voice=False,
        )

    assert summary.candidates == 1
    assert summary.updated == 1
    target_guild.get_member.assert_called_once_with(123)
    other_guild.get_member.assert_not_called()
    mock_set_role.assert_awaited_once_with(target_guild, member, "Gold")
    mock_notify.assert_awaited_once_with(bot, summary)


async def test_refresh_current_rank_roles_db_only_excludes_connected_voice_users():
    """include_connected_voice=False does not add users who are only currently in voice."""
    bot = Mock(spec=MyBot)
    guild = Mock(spec=discord.Guild)
    guild.id = 1
    guild.name = "Guild"
    bot.guilds = [guild]

    db_member = Mock(spec=discord.Member)
    db_member.id = 123
    db_member.display_name = "DbPlayer"
    db_member.mention = "<@123>"
    db_member.roles = []

    def get_member(user_id: int):
        return db_member if user_id == 123 else None

    guild.get_member.side_effect = get_member
    begin_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2026, 1, 2, tzinfo=timezone.utc)

    with (
        patch("deps.bot_common_actions.get_active_user_info", return_value=[_user_info(123, "DbPlayer")]),
        patch(
            "deps.bot_common_actions.get_currently_connected_user_ids", new_callable=AsyncMock, return_value={123, 456}
        ) as mock_connected,
        patch("deps.bot_common_actions.fetch_user_info_by_user_id", new_callable=AsyncMock) as mock_fetch_user,
        patch(
            "deps.bot_common_actions.fetch_current_season_rank_for_account",
            new_callable=AsyncMock,
            return_value=("Gold", 0),
        ),
        patch(
            "deps.bot_common_actions.set_member_role_from_current_rank", new_callable=AsyncMock, return_value=True
        ) as mock_set_role,
        patch("deps.bot_common_actions.post_rank_change_notifications", new_callable=AsyncMock) as mock_notify,
    ):
        summary = await deps.bot_common_actions.refresh_current_rank_roles_cross_guilds(
            begin_time,
            end_time,
            bot,
            include_connected_voice=False,
        )

    assert summary.candidates == 1
    assert summary.updated == 1
    mock_connected.assert_not_called()
    mock_fetch_user.assert_not_called()
    mock_set_role.assert_awaited_once_with(guild, db_member, "Gold")
    mock_notify.assert_awaited_once_with(bot, summary)


async def test_post_rank_change_notifications_posts_to_main_siege_channel():
    """Rank changes are announced in the configured main Siege channel used by automatic LFG."""
    bot = Mock(spec=MyBot)
    bot.guild_emoji = {123: {"Silver": "111", "Gold": "222", "Unranked": "333"}}
    channel = Mock(spec=discord.TextChannel)
    channel.send = AsyncMock()
    summary = deps.bot_common_actions.RankRefreshSummary(
        changes=[
            deps.bot_common_actions.RankRoleChange(
                guild_id=123,
                guild_name="Guild",
                user_id=456,
                display_name="Player",
                member_mention="<@456>",
                old_rank="Silver",
                new_rank="Gold",
            )
        ]
    )

    with (
        patch("deps.bot_common_actions.data_access_get_main_text_channel_id", new_callable=AsyncMock, return_value=789),
        patch("deps.bot_common_actions.data_access_get_channel", new_callable=AsyncMock, return_value=channel),
    ):
        await deps.bot_common_actions.post_rank_change_notifications(bot, summary)

    channel.send.assert_awaited_once()
    message = channel.send.await_args.args[0]
    assert "Rank changes from active player refresh" in message
    assert "<@456>: <:Silver:111> Silver -> <:Gold:222> Gold" in message
