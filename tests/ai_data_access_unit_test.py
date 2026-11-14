"""Unit tests for the catalog-driven AI data access path."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from deps.ai import data_catalog, recipes, sql_validator, zero_row_diagnostics
from deps.ai.ai_functions import BotAI
from deps.analytic_data_access import (
    insert_if_nonexistant_full_match_info,
    insert_user_activity,
    upsert_user_info,
)
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats
from deps.operator_stats_data_access import upsert_operator_stats
from deps.system_database import (
    DATABASE_NAME,
    DATABASE_NAME_TEST,
    EVENT_CONNECT,
    EVENT_DISCONNECT,
    database_manager,
)

pytestmark = pytest.mark.no_parallel


@pytest.fixture(autouse=True)
def setup_and_teardown():
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()
    yield
    database_manager.set_database_name(DATABASE_NAME)


def create_user(user_id: int, name: str) -> UserInfo:
    upsert_user_info(user_id, name, f"ubi_{user_id}", f"ubi_{user_id}", f"uuid-{user_id}", "US/Eastern", 3000)
    return UserInfo(user_id, name, f"ubi_{user_id}", f"ubi_{user_id}", f"uuid-{user_id}", "US/Eastern", 3000)


def create_match(
    match_uuid: str,
    user_id: int,
    timestamp: datetime,
    operators: str = "Doc,Ash",
    session_type: str = "Ranked",
    rounds: int = 9,
) -> UserFullMatchStats:
    return UserFullMatchStats(
        id=None,
        match_uuid=match_uuid,
        user_id=user_id,
        match_timestamp=timestamp,
        match_duration_ms=1800000,
        data_center="eus",
        session_type=session_type,
        map_name="Bank",
        is_surrender=False,
        is_forfeit=False,
        is_rollback=False,
        r6_tracker_user_uuid=f"uuid-{user_id}",
        ubisoft_username=f"ubi_{user_id}",
        operators=operators,
        round_played_count=rounds,
        round_won_count=5,
        round_lost_count=4,
        round_disconnected_count=0,
        kill_count=10,
        death_count=8,
        assist_count=3,
        head_shot_count=5,
        tk_count=0,
        ace_count=1,
        first_kill_count=2,
        first_death_count=1,
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
        kill_1_count=3,
        kill_2_count=2,
        kill_3_count=1,
        kill_4_count=1,
        kill_5_count=1,
        rank_points=3500,
        rank_name="Gold I",
        points_gained=50,
        rank_previous=3450,
        kd_ratio=1.25,
        head_shot_percentage=0.50,
        kills_per_round=1.11,
        deaths_per_round=0.89,
        assists_per_round=0.33,
        has_win=True,
    )


def test_catalog_matches_live_schema_and_describes_every_column():
    cursor = database_manager.get_cursor()
    for table_name in sorted(data_catalog.STATS_TABLE_ALLOWLIST):
        schema_columns = [row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()]
        catalog_columns = list(data_catalog.column_names(table_name))
        assert len(schema_columns) == len(catalog_columns), f"catalog drift for {table_name}"
        assert set(schema_columns) == set(catalog_columns), f"catalog drift for {table_name}"
        table = data_catalog.TABLES[table_name]
        for column in table.columns:
            assert column.description.strip(), f"{table_name}.{column.name} has no description"
        for column in table.columns:
            if column.important:
                assert column.name in schema_columns


def test_catalog_excludes_private_and_non_stats_tables():
    for table in ("archived_message", "cache", "tribemarkets_pending_match", "user_weights"):
        assert table not in data_catalog.STATS_TABLE_ALLOWLIST


def test_render_grounding_contains_today_and_coverage():
    user = create_user(1, "Alice")
    insert_if_nonexistant_full_match_info(
        user, [create_match("m1", user.id, datetime(2026, 2, 1, tzinfo=timezone.utc))]
    )

    grounding = data_catalog.render_grounding()

    assert data_catalog.today_utc_iso() in grounding
    assert "2026-02-01" in grounding
    assert "Recorded match data covers" in grounding


def test_render_domain_describes_purpose_grain_time_and_gotchas():
    rendered = data_catalog.render_domain("matches")

    assert "TABLE `user_full_match_info`" in rendered
    assert "grain:" in rendered
    assert "time column: `match_timestamp`" in rendered
    assert "TABLE `operator_stats`" in rendered
    assert "lifetime snapshot" in rendered
    assert "',' || LOWER(operators) || ',' LIKE" in rendered


def test_validator_repairs_session_type_casing():
    sql = sql_validator.validate_and_normalize(
        "SELECT COUNT(*) FROM user_full_match_info WHERE session_type = 'ranked'", []
    )

    assert "LOWER(session_type) = 'ranked'" in sql


def test_validator_repairs_aliased_session_type_without_corrupting_sql():
    sql = sql_validator.validate_and_normalize(
        "SELECT COUNT(*) FROM user_full_match_info m WHERE m.session_type = 'ranked'", []
    )

    assert "LOWER(m.session_type) = 'ranked'" in sql
    assert "m.LOWER" not in sql


def test_validator_rejects_bare_operator_filter():
    with pytest.raises(ValueError, match="comma-separated list"):
        sql_validator.validate_and_normalize("SELECT * FROM user_full_match_info WHERE operators = 'Doc'", [])


def test_validator_rejects_wrapped_bare_operator_like():
    with pytest.raises(ValueError, match="comma-separated list|partial name"):
        sql_validator.validate_and_normalize(
            "SELECT * FROM user_full_match_info WHERE LOWER(operators) LIKE '%doc%'", []
        )


def test_validator_rejects_unknown_table():
    with pytest.raises(ValueError, match="outside the allowed stats tables"):
        sql_validator.validate_and_normalize("SELECT * FROM archived_message", [])


def test_validator_rejects_unknown_session_type():
    with pytest.raises(ValueError, match="Unknown session_type"):
        sql_validator.validate_and_normalize(
            "SELECT COUNT(*) FROM user_full_match_info WHERE session_type = 'casual'", []
        )


def test_validator_requires_rollback_for_leaderboards():
    sql = (
        "SELECT COALESCE(user_info.ubisoft_username_active, user_info.ubisoft_username_max), COUNT(*) "
        "FROM user_full_match_info m JOIN user_info ON user_info.id = m.user_id GROUP BY m.user_id"
    )
    with pytest.raises(ValueError, match="is_rollback"):
        sql_validator.validate_and_normalize(sql, [], require_canonical_identity=True)


def test_operator_recipe_is_date_scoped_and_delimited():
    question = (
        "Give me the top 10 people playing Doc operator in this server in term of round " "played in 2026 for ranked"
    )

    recipe = recipes.try_build_recipe(question, 1)

    assert recipe is not None
    assert recipe.name == "operator_date_scoped"
    assert recipe.exact is False
    assert "LIKE '%,doc,%'" in recipe.sql
    assert "2026-01-01" in recipe.sql and "2027-01-01" in recipe.sql
    assert "LOWER(m.session_type) = 'ranked'" in recipe.sql
    assert "is_rollback = 0" in recipe.sql
    assert "rounds_in_matches_with_operator" in recipe.sql


def test_operator_recipe_returns_ranked_rows():
    user1 = create_user(1, "Alice")
    user2 = create_user(2, "Bob")
    insert_if_nonexistant_full_match_info(
        user1,
        [
            create_match("a1", user1.id, datetime(2026, 2, 1, tzinfo=timezone.utc), rounds=9),
            create_match("a2", user1.id, datetime(2026, 3, 1, tzinfo=timezone.utc), rounds=6),
        ],
    )
    insert_if_nonexistant_full_match_info(
        user2, [create_match("b1", user2.id, datetime(2026, 2, 2, tzinfo=timezone.utc), rounds=4)]
    )
    # Outside the requested year and a different operator: neither may count.
    insert_if_nonexistant_full_match_info(
        user2,
        [
            create_match("b2", user2.id, datetime(2025, 2, 2, tzinfo=timezone.utc), rounds=9),
            create_match("b3", user2.id, datetime(2026, 2, 3, tzinfo=timezone.utc), operators="Ash,Mute"),
        ],
    )

    recipe = recipes.try_build_recipe("top 10 people playing Doc operator in 2026 for ranked", 1)
    assert recipe is not None
    rows = database_manager.get_cursor().execute(recipe.sql).fetchall()

    assert rows[0] == ("ubi_1", 15, 2)
    assert rows[1] == ("ubi_2", 4, 1)
    assert len(rows) == 2


def test_lifetime_operator_recipe_uses_operator_stats():
    user1 = create_user(1, "Alice")
    user2 = create_user(2, "Bob")
    upsert_operator_stats(
        [
            {
                "user_id": user1.id,
                "operator_name": "doc",
                "session_type": "ranked",
                "side": "defender",
                "gamemode": "pvp_ranked",
                "matches_played": 10,
                "matches_won": 6,
                "matches_lost": 4,
                "win_percentage": 60.0,
                "time_played": 7200,
                "rounds_played": 90,
                "rounds_won": 55,
                "rounds_lost": 35,
                "round_win_pct": 61.0,
                "kills": 40,
                "deaths": 30,
                "kd_ratio": 1.33,
                "kills_per_game": 4.0,
                "kills_per_round": 0.44,
            },
            {
                "user_id": user2.id,
                "operator_name": "doc",
                "session_type": "ranked",
                "side": "defender",
                "gamemode": "pvp_ranked",
                "matches_played": 5,
                "matches_won": 2,
                "matches_lost": 3,
                "win_percentage": 40.0,
                "time_played": 3600,
                "rounds_played": 45,
                "rounds_won": 20,
                "rounds_lost": 25,
                "round_win_pct": 44.0,
                "kills": 15,
                "deaths": 20,
                "kd_ratio": 0.75,
                "kills_per_game": 3.0,
                "kills_per_round": 0.33,
            },
        ]
    )

    recipe = recipes.try_build_recipe("who has the most rounds playing doc", 1)
    assert recipe is not None
    assert recipe.name == "operator_lifetime"
    assert recipe.exact is True
    rows = database_manager.get_cursor().execute(recipe.sql).fetchall()

    assert rows[0] == ("ubi_1", 90, 10)
    assert rows[1] == ("ubi_2", 45, 5)


def test_personal_operator_question_is_not_a_leaderboard_recipe():
    assert recipes.try_build_recipe("how many rounds did I play as doc", 1) is None
    assert recipes.try_build_recipe("I played Ash last night, how did I do?", 1) is None


def test_voice_time_recipe_pairs_events_and_scopes_guild():
    user1 = create_user(1, "Alice")
    user2 = create_user(2, "Bob")
    guild = 999
    other_guild = 1000
    start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    insert_user_activity(user1.id, "Alice", 10, guild, EVENT_CONNECT, start)
    insert_user_activity(user1.id, "Alice", 10, guild, EVENT_DISCONNECT, start.replace(hour=12))
    insert_user_activity(user2.id, "Bob", 11, guild, EVENT_CONNECT, start)
    insert_user_activity(user2.id, "Bob", 11, guild, EVENT_DISCONNECT, start.replace(hour=11))
    # This longer session is in another guild and must be excluded by the guild scope.
    insert_user_activity(user2.id, "Bob", 12, other_guild, EVENT_CONNECT, start)
    insert_user_activity(user2.id, "Bob", 12, other_guild, EVENT_DISCONNECT, start.replace(hour=13))

    recipe = recipes.try_build_recipe("who has the most voice time in 2026", 1, guild_id=guild)
    assert recipe is not None
    assert recipe.name == "leaderboard_voice_time"
    rows = database_manager.get_cursor().execute(recipe.sql).fetchall()

    assert rows[0] == ("ubi_1", 7200.0)
    assert rows[1] == ("ubi_2", 3600.0)


def test_operator_word_does_not_resolve_a_user_named_doc():
    create_user(42, "Doc")
    bot_ai = BotAI()

    resolved = bot_ai.resolve_users_in_text("top people playing Doc operator", [])

    assert resolved == []


def test_recipe_is_skipped_for_player_comparisons():
    recipe = recipes.try_build_recipe("who has the best kd between Fridge and Deus", 1, resolved_users=[object()])

    assert recipe is None


@pytest.mark.asyncio
async def test_ask_ai_sql_for_stats_uses_recipe_without_calling_ai():
    # A real user named Doc must not hijack a question about the operator Doc.
    create_user(42, "Doc")
    bot_ai = BotAI()
    question = (
        "Give me the top 10 people playing Doc operator in this server in term of round " "played in 2026 for ranked"
    )

    def explode(*args, **kwargs):
        raise AssertionError("ask_ai must not be called when a recipe matches")

    with patch.object(bot_ai, "ask_ai", side_effect=explode):
        sql = await bot_ai.ask_ai_sql_for_stats(1, question, 1, [])

    assert sql is not None
    assert "LIKE '%,doc,%'" in sql
    assert "is_rollback = 0" in sql
    assert "upper-bound estimate" in bot_ai.last_sql_note


def test_zero_row_diagnosis_identifies_the_date_filter():
    user = create_user(1, "Alice")
    insert_if_nonexistant_full_match_info(
        user, [create_match("m1", user.id, datetime(2025, 2, 1, tzinfo=timezone.utc))]
    )
    sql = (
        "SELECT COALESCE(ui.ubisoft_username_active, ui.ubisoft_username_max) AS player, "
        "SUM(m.round_played_count) AS rounds FROM user_full_match_info m "
        "JOIN user_info ui ON ui.id = m.user_id "
        "WHERE m.is_rollback = 0 AND m.match_timestamp >= '2026-01-01' "
        "AND m.match_timestamp < '2027-01-01' GROUP BY m.user_id"
    )

    diagnosis = zero_row_diagnostics.diagnose_zero_rows(sql)

    assert "returned 0 rows" in diagnosis
    assert "without `m.match_timestamp >= '2026-01-01'`: 1 rows" in diagnosis
    assert "Recorded match coverage" in diagnosis


@pytest.mark.asyncio
async def test_clarifying_prompt_uses_coverage_and_diagnosis():
    bot_ai = BotAI()
    ask = AsyncMock(return_value="Which month in 2026?")

    with patch.object(bot_ai, "ask_ai_async", ask):
        await bot_ai.generate_clarifying_question(
            1, "top Doc in 2026", "context", diagnosis="Without the date filter: 318 rows."
        )

    prompt = ask.await_args.args[0]
    assert data_catalog.today_utc_iso() in prompt
    assert "Without the date filter: 318 rows." in prompt
    assert "past date range" not in prompt.casefold()


@pytest.mark.asyncio
async def test_sql_prompt_includes_grounding_and_catalog_semantics():
    bot_ai = BotAI()
    responses = [
        '{"needs_sql": true, "domain": "matches", "user_ids": []}',
        "SELECT COUNT(*) FROM user_full_match_info",
    ]
    with patch.object(bot_ai, "ask_ai", side_effect=responses) as ask:
        await bot_ai.ask_ai_sql_for_stats(1, "show my match stats", 99, [])

    sql_prompt = ask.call_args_list[1].args[0]
    assert data_catalog.today_utc_iso() in sql_prompt
    assert "TABLE `operator_stats`" in sql_prompt
    assert "grain: one row per tracked user per match" in sql_prompt
    assert "LOWER(session_type) = 'ranked'" in sql_prompt


@pytest.mark.asyncio
async def test_planner_only_path_adds_catalog_schema():
    """A stats question with no keyword or date must still receive the table catalog."""
    bot_ai = BotAI()
    responses = [
        '{"needs_sql": true, "domain": "matches", "user_ids": []}',
        "SELECT 1",
    ]
    with patch.object(bot_ai, "ask_ai", side_effect=responses) as ask:
        result = await bot_ai.ask_ai_sql_for_stats(1, "how do I stack up", 99, [])

    assert result == "SELECT 1"
    sql_prompt = ask.call_args_list[1].args[0]
    assert "TABLE `user_full_match_info`" in sql_prompt
    assert "TABLE `operator_stats`" in sql_prompt
