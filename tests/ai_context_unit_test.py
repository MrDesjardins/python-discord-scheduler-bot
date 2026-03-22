"""Unit tests for permanent AI context behavior."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from deps.ai.ai_functions import BotAI
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
async def test_generate_answer_when_mentioning_bot_includes_guild_ai_context():
    """Bot mentions should include permanent guild context in the response prompt."""
    guild_id = 777
    bot_ai = BotAI()
    data_access_set_guild_ai_context(guild_id, "The server owner prefers concise answers.")

    ask_ai_async = AsyncMock(return_value="Reply text")
    with patch.object(bot_ai, "ask_ai_async", ask_ai_async), patch.object(
        bot_ai, "ask_ai_sql_for_stats", AsyncMock(return_value="")
    ):
        response = await bot_ai.generate_answer_when_mentioning_bot(
            guild_id,
            "Alice said: hello",
            "@bot who is online?",
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
        response = await bot_ai.ask_ai_sql_for_stats(guild_id, "show my match stats", 99)

    prompt = ask_ai.call_args.args[0]
    assert "Use player nicknames consistently." in prompt
    assert "Generate a SQL query" in prompt
    assert response == "SELECT 1"
