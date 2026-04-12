"""Unit tests for permanent AI context behavior."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from unittest.mock import MagicMock

import pytest

from deps.ai.ai_functions import DAILY_SUMMARY_MAX_CONTEXT_CHARS, BotAI
from deps.data_access import (
    data_access_clear_guild_ai_context,
    data_access_get_guild_ai_context,
    data_access_set_guild_ai_context,
)
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Set up a clean test database for cache-backed context storage."""
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()
    yield
    database_manager.set_database_name(DATABASE_NAME)


def create_mock_user(user_id: int, display_name: str) -> UserInfo:
    """Create a user for AI prompt tests."""
    return UserInfo(
        id=user_id,
        display_name=display_name,
        ubisoft_username_max=f"ubi_{user_id}",
        ubisoft_username_active=f"ubi_{user_id}",
        r6_tracker_active_id=f"uuid-{user_id}",
        time_zone="US/Eastern",
        max_mmr=3500,
    )


def create_mock_match(user_id: int, match_uuid: str) -> UserFullMatchStats:
    """Create a match for AI summary tests."""
    return UserFullMatchStats(
        id=1,
        match_uuid=match_uuid,
        user_id=user_id,
        match_timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
        match_duration_ms=600000,
        data_center="US East",
        session_type="ranked",
        map_name="Clubhouse",
        is_surrender=False,
        is_forfeit=False,
        is_rollback=False,
        r6_tracker_user_uuid=f"uuid-{user_id}",
        ubisoft_username=f"ubi_{user_id}",
        operators="Ash,Jager",
        round_played_count=9,
        round_won_count=5,
        round_lost_count=4,
        round_disconnected_count=0,
        kill_count=9,
        death_count=5,
        assist_count=2,
        head_shot_count=3,
        tk_count=0,
        ace_count=0,
        first_kill_count=1,
        first_death_count=0,
        clutches_win_count=1,
        clutches_loss_count=0,
        clutches_win_count_1v1=1,
        clutches_win_count_1v2=0,
        clutches_win_count_1v3=0,
        clutches_win_count_1v4=0,
        clutches_win_count_1v5=0,
        clutches_lost_count_1v1=0,
        clutches_lost_count_1v2=0,
        clutches_lost_count_1v3=0,
        clutches_lost_count_1v4=0,
        clutches_lost_count_1v5=0,
        kill_1_count=4,
        kill_2_count=2,
        kill_3_count=1,
        kill_4_count=0,
        kill_5_count=0,
        rank_points=3500,
        rank_name="Diamond",
        points_gained=25,
        rank_previous=3475,
        kd_ratio=1.8,
        head_shot_percentage=0.43,
        kills_per_round=0.78,
        deaths_per_round=0.56,
        assists_per_round=0.22,
        has_win=True,
    )


@pytest.mark.asyncio
async def test_guild_ai_context_data_access_round_trip():
    """Guild AI context should persist through the cache-backed store."""
    guild_id = 12345

    data_access_set_guild_ai_context(guild_id, "Always call the Friday stack Team Rocket.")
    stored_value = await data_access_get_guild_ai_context(guild_id)

    assert stored_value == "Always call the Friday stack Team Rocket."

    data_access_clear_guild_ai_context(guild_id)
    cleared_value = await data_access_get_guild_ai_context(guild_id)

    assert cleared_value is None


@pytest.mark.asyncio
async def test_guild_ai_context_preserves_empty_document():
    """An existing but empty AI context document should not be treated as missing."""
    guild_id = 67890

    data_access_set_guild_ai_context(guild_id, "")
    stored_value = await data_access_get_guild_ai_context(guild_id)

    assert stored_value == ""


@pytest.mark.asyncio
async def test_update_guild_ai_context_persists_new_document():
    """Natural-language updates should save the revised full document."""
    guild_id = 54321
    bot_ai = BotAI()
    data_access_set_guild_ai_context(guild_id, "Original knowledge")

    with patch.object(bot_ai, "ask_ai_async", AsyncMock(return_value="Updated knowledge")):
        updated_value = await bot_ai.update_guild_ai_context(guild_id, "Add that ranked night starts at 8pm.")

    assert updated_value == "Updated knowledge"
    assert await data_access_get_guild_ai_context(guild_id) == "Updated knowledge"


@pytest.mark.asyncio
@patch("deps.ai.ai_functions.get_active_user_info")
@patch("deps.ai.ai_functions.data_access_fetch_user_matches_in_time_range")
async def test_generate_message_summary_includes_guild_ai_context(mock_fetch_matches, mock_get_active_users):
    """AI summaries should include the permanent guild context in the prompt."""
    guild_id = 999
    bot_ai = BotAI()
    user = create_mock_user(1, "PlayerOne")
    match = create_mock_match(1, "match-1")

    mock_get_active_users.return_value = [user]
    mock_fetch_matches.return_value = {1: [match]}
    data_access_set_guild_ai_context(guild_id, "Call Friday ranked night 'The Gauntlet'.")

    ask_ai_async = AsyncMock(return_value="Summary text")
    with patch.object(bot_ai, "ask_ai_async", ask_ai_async):
        result = await bot_ai.generate_message_summary_matches_async(guild_id, 24)

    prompt = ask_ai_async.await_args.args[0]
    assert "Call Friday ranked night 'The Gauntlet'." in prompt
    assert "Your goal is to generate a summary of the ranked matches" in prompt
    assert result.endswith("Summary text")


@pytest.mark.asyncio
@patch("deps.ai.ai_functions.get_active_user_info")
@patch("deps.ai.ai_functions.data_access_fetch_user_matches_in_time_range")
async def test_generate_message_summary_caps_large_match_context(mock_fetch_matches, mock_get_active_users):
    """Large daily summaries should stay small enough for the OpenAI fallback."""
    guild_id = 1000
    bot_ai = BotAI()
    users = [create_mock_user(user_id, f"Player{user_id}") for user_id in range(1, 4)]
    matches = []
    for index in range(80):
        user_id = (index % len(users)) + 1
        match = create_mock_match(user_id, f"match-{index}")
        match.kill_count = index % 20
        match.points_gained = index
        matches.append(match)

    mock_get_active_users.return_value = users
    mock_fetch_matches.return_value = {
        user.id: [match for match in matches if match.user_id == user.id] for user in users
    }

    ask_ai_async = AsyncMock(return_value="Summary text")

    def verbose_match_summary(match):
        return f"match_uuid `{match.match_uuid}` for user_id `{match.user_id}`\n" + ("x" * 2000)

    with (
        patch.object(bot_ai, "ask_ai_async", ask_ai_async),
        patch.object(bot_ai, "summarize_full_match", side_effect=verbose_match_summary),
    ):
        result = await bot_ai.generate_message_summary_matches_async(guild_id, 24)

    prompt = ask_ai_async.await_args.args[0]
    assert len(prompt) <= DAILY_SUMMARY_MAX_CONTEXT_CHARS
    assert "lower-priority match records were omitted" in prompt
    assert result.endswith("Summary text")


@pytest.mark.asyncio
async def test_generate_answer_when_mentioning_bot_includes_guild_ai_context():
    """Bot mentions should include permanent guild context in the response prompt."""
    guild_id = 777
    bot_ai = BotAI()
    data_access_set_guild_ai_context(guild_id, "The server owner prefers concise answers.")

    ask_ai_async = AsyncMock(return_value="Reply text")
    with (
        patch.object(bot_ai, "ask_ai_async", ask_ai_async),
        patch.object(bot_ai, "ask_ai_sql_for_stats", AsyncMock(return_value="")),
    ):
        response = await bot_ai.generate_answer_when_mentioning_bot(
            guild_id,
            "Alice said: hello",
            "@bot who is online?",
            [],
            "Alice",
            42,
            "Gold",
        )

    prompt = ask_ai_async.await_args.args[0]
    assert "The server owner prefers concise answers." in prompt
    assert "User question:@bot who is online?" in prompt
    assert response == "Reply text"


@pytest.mark.asyncio
async def test_ask_ai_sql_for_stats_includes_guild_ai_context():
    """SQL generation should also see the permanent guild context."""
    guild_id = 888
    bot_ai = BotAI()
    data_access_set_guild_ai_context(guild_id, "Use player nicknames consistently.")

    with patch.object(bot_ai, "ask_ai", return_value="SELECT 1") as ask_ai:
        response = await bot_ai.ask_ai_sql_for_stats(guild_id, "show my match stats", 99, [])

    prompt = ask_ai.call_args.args[0]
    assert "Use player nicknames consistently." in prompt
    assert "Generate a SQL query" in prompt
    assert response == "SELECT 1"


@pytest.mark.asyncio
async def test_generate_answer_when_mentioning_bot_includes_resolved_mentions():
    """Bot mention answers should use explicit resolved mention identities."""
    guild_id = 909
    bot_ai = BotAI()
    resolved_user = create_mock_user(55, "fridge")

    ask_ai_async = AsyncMock(return_value="Reply text")
    ask_ai_sql_for_stats = AsyncMock(return_value="")
    with (
        patch.object(bot_ai, "ask_ai_async", ask_ai_async),
        patch.object(bot_ai, "ask_ai_sql_for_stats", ask_ai_sql_for_stats),
    ):
        await bot_ai.generate_answer_when_mentioning_bot(
            guild_id,
            "Patrick said: compare @fridge and @Deus",
            "@R6SiegeBot who has the best K/D between @fridge and @Deus",
            [resolved_user],
            "Patrick",
            77,
            "Gold",
        )

    response_prompt = ask_ai_async.await_args.args[0]
    sql_prompt = ask_ai_sql_for_stats.await_args.args[1]
    assert "Resolved mentions:" in response_prompt
    assert "display_name = fridge" in response_prompt
    assert "unless the permanent server knowledge explicitly defines one" in response_prompt
    assert "@R6SiegeBot who has the best K/D between @fridge and @Deus" in sql_prompt


@pytest.mark.asyncio
async def test_ask_ai_sql_for_stats_includes_resolved_mentions():
    """SQL prompts should constrain identity resolution to explicit mentioned users."""
    bot_ai = BotAI()
    resolved_users = [create_mock_user(10, "fridge"), create_mock_user(11, "Deus")]

    with patch.object(bot_ai, "ask_ai", return_value="SELECT 1") as ask_ai:
        await bot_ai.ask_ai_sql_for_stats(1, "who has the better k/d", 99, resolved_users)

    prompt = ask_ai.call_args.args[0]
    assert "Resolved mentioned users:" in prompt
    assert "display_name = fridge" in prompt
    assert "display_name = Deus" in prompt
    assert "restrict to these user ids: 10,11" in prompt


@pytest.mark.asyncio
async def test_resolve_user_mentions_prefers_live_discord_display_name():
    """Resolved mentions should use the live Discord display name over stale stored display names."""
    from cogs.events import MyEventsCog

    message = MagicMock()
    mentioned_user = MagicMock()
    mentioned_user.id = 111
    mentioned_user.display_name = "t1deus"
    mentioned_user.mention = "<@111>"
    message.mentions = [mentioned_user]

    stored_user = UserInfo(
        id=111,
        display_name="Deus",
        ubisoft_username_max="deus_max",
        ubisoft_username_active="deus_active",
        r6_tracker_active_id="uuid-111",
        time_zone="US/Eastern",
        max_mmr=4200,
    )

    with patch("cogs.events.fetch_user_info_by_user_id", AsyncMock(return_value=stored_user)):
        resolved_users = await MyEventsCog._resolve_user_mentions(message, bot_user_id=999)

    assert len(resolved_users) == 1
    assert resolved_users[0].display_name == "t1deus"
    assert resolved_users[0].ubisoft_username_active == "deus_active"
