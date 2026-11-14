# AI Data Access Improvement Plan

Status: implemented (phases 1-5)
Scope: making the Discord bot answer stats/database questions reliably.
Current models: Gemini `gemini-3.8-flash` (primary), OpenAI `gpt-5.6-terra` / `gpt-5.6-luna` (fallback).
See section 7 for the files and verification attached to this implementation.

## 1. Problem statement

The failure mode is not "the model cannot write SQL". It is that the model is asked to
write SQL against a database it has only been shown as a flat list of column names.

Concrete example that failed:

> "Give me the top 10 people playing Doc operator in this server in term of round played
> in 2026 for ranked"

The bot asked for a clarification, then claimed it could not access 2026 data.

Root causes, in order of impact:

1. **No time grounding.** The SQL and planner prompts never state today's date or the
   actual data coverage. With today at 2026-11-14 and data up to 2026-07 in the local
   database, "2026" reads to the model as the future.
2. **No semantics.** The prompt lists fields but not what a row represents, which column
   is the time axis, which tables are lifetime snapshots, or which values are legal.
3. **Casing traps.** `user_full_match_info.session_type` stores `'Ranked'`; `operator_stats`
   stores `operator_name='doc'` and `session_type='ranked'`. SQLite text `=` is
   case-sensitive, so plausible SQL returns zero rows and triggers the clarification path.
4. **Schema gaps.** `operator_stats` is never shown to the model, even though it is the only
   table with exact per-operator `rounds_played`.
5. **Dishonest recovery.** The clarifying-question prompt tells the model to ask for a
   "past date range", so it invents a limitation instead of reporting what is actually
   available.
6. **Data-model limits are undocumented.** `round_played_count` is per match, not per
   operator; `operators` is the set used during the whole match. "Rounds on Doc" is
   therefore approximate from `user_full_match_info` and exact only (lifetime) via
   `operator_stats`.

## 2. Goals / non-goals

Goals:

- Give the model a precise, maintained semantic description of every stats table.
- Always inject the current date and the real data coverage.
- Reject or auto-correct SQL that uses wrong casing, wrong table, or unsafe semantics.
- Turn "0 rows" into a diagnosis (which filter removed the data) instead of a guess.
- Add deterministic fast paths for the highest-traffic question classes.
- Make regressions measurable with an offline eval suite.

Non-goals:

- Replacing the SQL path with a full BI/tool-calling framework in one step.
- Exposing moderation archive, cache, or market tables to the LLM (privacy/security).
- Reworking the player-value or match-ingestion algorithms.

## 3. Core design: a semantic data catalog

Create `deps/ai/data_catalog.py` as the single source of truth. Both the planner prompt
and the SQL prompt are rendered from it. The catalog is code, not prose in a prompt
string, so it can be tested and drift-checked.

### 3.1 Types

```python
@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type: str
    description: str
    category: str | None = None      # e.g. "session_type", "operator_name"
    nullable: bool = False

@dataclass(frozen=True)
class TableSpec:
    name: str
    domain: str                      # matches | activity | tournaments | bets | player_value
    purpose: str                     # one sentence, what the table is for
    grain: str                       # "one row per user per match"
    time_column: str | None          # the only column usable for time filtering
    time_semantics: str              # historical | lifetime snapshot | event log | computed snapshot
    keys: str                        # primary/unique keys and join keys
    joins: tuple[str, ...]           # canonical join paths
    categoricals: dict[str, tuple[str, ...]]  # column -> legal values as stored
    gotchas: tuple[str, ...]         # casing, rollback, CSV, coverage, etc.
    default_filters: tuple[str, ...]
    columns: tuple[ColumnSpec, ...]
```

The catalog must also expose:

- `STATS_TABLE_ALLOWLIST`: only tables the LLM may query. Excludes `archived_message*`,
  `cache`, `tribemarkets_pending_match`, `user_weights`, `user_following`,
  `custom_game_user_subscription`.
- `canonical_identity_sql()`: the one approved way to render a player name.
- `coverage()`: cached `(min_timestamp, max_timestamp)` from `user_full_match_info`.
- `render(domains, question)`: compact prompt text for only the relevant domains.

### 3.2 The actual table catalog (what goes in the prompt)

This is the content the model should receive. Keep each entry short; details go in
`gotchas` and column descriptions.

| Table | Purpose | Grain | Time axis | Semantics |
|---|---|---|---|---|
| `user_info` | Identity spine: Discord user ↔ Ubisoft accounts | one row per Discord user | none | current profile |
| `user_full_match_info` | Historical per-match stats recorded by the bot | one row per user per match | `match_timestamp` (UTC ISO) | historical, append-only |
| `user_full_stats_info` | R6 Tracker lifetime profile snapshot | one row per user (currently 128 users) | none | point-in-time snapshot |
| `operator_stats` | R6 Tracker lifetime per-operator snapshot | one row per user/operator/session/gamemode | none (`last_updated` only) | point-in-time snapshot |
| `user_activity` | Voice channel connect/disconnect event log | one row per event | `timestamp` | event log |
| `user_player_value` | Nightly computed team-balancing value | one row per user/algorithm | `computed_at`, `last_match_timestamp` | computed snapshot |
| `tournament*` | Tournaments, registrations, bracket games, teams | varies | `start_date`/`timestamp` | operational |
| `bet_*` | Betting odds, user bets, ledger | varies | `time_bet_placed`/`timestamp` | operational |

Per-table details to encode:

**`user_info`**
- `id` = Discord user id, the join key to every other stats table.
- `display_name` = Discord name (never the answer identity).
- Canonical player name = `COALESCE(ubisoft_username_active, ubisoft_username_max)`.
- `r6_tracker_active_id` is the R6 Tracker UUID.
- Gotcha: do not filter matches by `ubisoft_username` strings; join on `user_id`.
- Coverage: 236 users.

**`user_full_match_info`**
- The only table with a real time axis. Use it for "in 2026", "last month", etc.
- `match_timestamp` is an ISO-8601 UTC string with offset, e.g.
  `2025-01-20T04:55:53.063000+00:00`. Compare with ISO date strings; use
  `DATE(match_timestamp)` for grouping by day.
- `session_type` stores `'Ranked'` (capital R). Compare with `LOWER(session_type)='ranked'`.
- `operators` is a comma-separated list of operator names as displayed, e.g.
  `Capitão,Buck,Alibi,Valkyrie,Doc`. Filter with
  `',' || operators || ',' LIKE '%,Doc,%'` (or `LOWER(...)` for case-insensitive).
- `round_played_count` is the number of rounds in that match, i.e. match-level, not
  per operator. Summing it for matches containing Doc overcounts "rounds on Doc".
- `is_rollback` must be excluded from aggregates (`is_rollback = 0`) unless the question
  is specifically about rollbacks. `is_surrender` / `is_forfeit` are optional flags.
- `has_win` is 0/1.
- `kd_ratio`, `head_shot_percentage`, `kills_per_round`, etc. are precomputed per match.
- A match with N tracked users produces N rows sharing `match_uuid`.
- Coverage (local DB): 2024-06-22 → 2026-07-18, 36,742 rows, all `Ranked`.

**`user_full_stats_info`**
- R6 Tracker lifetime totals, not the bot's own history and not date-filterable.
- Split columns: `rank_*`, `arcade_*`, `quickmatch_*` for per-playlist lifetime stats.
- Only 128 rows for 236 users: do not assume coverage for a given player.
- Use for "all-time stats" questions; never for "in 2026".

**`operator_stats`**
- The only table with exact per-operator `rounds_played`, `matches_played`, `kills`,
  `deaths`, `kd_ratio`.
- `operator_name` is lowercase (`doc`, `ash`, ...).
- `session_type='ranked'`, `gamemode='pvp_ranked'` in the current data.
- No date dimension: `last_updated` is the snapshot time, not a match time. Therefore
  "rounds on Doc in 2026" cannot be answered exactly from this table; it is a lifetime
  snapshot. Document this in the prompt so the model states the limitation correctly
  instead of inventing one.

**`user_activity`**
- `event` is `'connect'` or `'disconnect'`.
- Voice time is computed by pairing events per user (and channel/guild), not by summing
  durations in a single row.
- Filter by `guild_id` when the question is about "this server".
- `timestamp` is the event time.

**`user_player_value`**
- `algorithm` selects the scoring variant; `value` is the team-balancing value and
  `rating` the derived rating. `match_count`, `last_match_timestamp`, `computed_at`
  describe freshness.
- Use for "player value"/"team balancing" questions, not for raw match stats.

**Tournament and bet tables**
- `tournament`: one row per tournament; dates in `registration_date`, `start_date`, `end_date`.
- `user_tournament`: registrations (user ↔ tournament).
- `tournament_game`: bracket games (`user1_id`, `user2_id`, `user_winner_id`, `score`, `map`, `timestamp`).
- `tournament_team_members`: team rosters.
- `bet_user_tournament`: tournament-level bets.
- `bet_game`: per-game odds and distribution state.
- `bet_user_game`: individual game bets.
- `bet_ledger_entry`: ledger movements.
- Gotcha: bet odds are probabilities in `[0,1]`; `bet_distributed` is a flag.

### 3.3 Prompt rendering

Replace `_domain_schema_text` with a renderer that emits, per domain:

```
TODAY: 2026-11-14 (UTC)
DATA COVERAGE: matches from 2024-06-22 to 2026-07-18 (UTC)

TABLE user_full_match_info
  purpose: historical per-match stats recorded by the bot
  grain: one row per user per match
  use time column: match_timestamp (ISO-8601 UTC)
  join: user_full_match_info.user_id = user_info.id
  legal values: session_type ∈ {'Ranked'}
  gotchas:
    - exclude is_rollback = 0 for aggregates
    - operators is a comma list; use ',' || operators || ',' LIKE '%,Doc,%'
    - round_played_count is per match, not per operator
  columns: ...
```

Keep the whole rendered prompt under a budget (e.g. 6k chars). Render only domains the
planner selected, plus `user_info` always.

### 3.4 Validation hardening

Extend `validate_generated_sql` (or extract `deps/ai/sql_validator.py`):

- Parse table references and reject anything outside `STATS_TABLE_ALLOWLIST`.
- Reject unknown columns using the catalog.
- For categorical columns, reject literals outside the known set (case-insensitive match
  is allowed, but the emitted SQL should use `LOWER(...)` or the canonical value).
- If `operators` is used with `=`, `IN`, or a bare `LIKE '%...%'`, require the
  delimiter-safe form and warn/repair.
- If `session_type` is filtered with `=` and a lowercase literal, rewrite to
  `LOWER(session_type)=...`.
- For aggregate/leaderboard queries, require `is_rollback = 0`.
- Require a `LIMIT` on leaderboard queries.
- Reject `PRAGMA`, `ATTACH`, `DETACH`, and multiple statements (already partially done).
- Add a lightweight row-count guard: run `SELECT COUNT(*) FROM (query)` (or `EXPLAIN`)
  and refuse unbounded full-table dumps.

### 3.5 Zero-row diagnosis

When an executed SQL returns no rows, do not immediately ask a generic question. Run a
deterministic ladder:

1. Re-run the query with each optional filter removed, one at a time
   (date range, `session_type`, operator/CSV filter, user filter).
2. Record which filter caused the empty result and what the count is without it.
3. Optionally run a coverage probe for the relevant tables.
4. Pass those facts to the model:
   "0 rows for Doc + Ranked + 2026-01-01..2026-12-31. Without the date filter: 318 matches.
   Without the operator filter: 36,742 matches. Coverage ends 2026-07-18."
5. The model then either answers, narrows the range honestly, or asks a targeted question.

Remove the current misleading instruction in `generate_clarifying_question` that asks for
a "past date range". Replace it with "use the coverage facts above; never claim a year is
unavailable unless coverage proves it".

### 3.6 Deterministic recipes (fast paths)

For the most common intents, bypass free-form SQL and call typed functions. Each recipe
declares its own SQL and returns canonical columns. Start with:

- Top operators by rounds/matches, with optional date range and session type.
  - Date-scoped: approximate from `user_full_match_info` (document the caveat).
  - Lifetime: exact from `operator_stats`.
- Leaderboards: matches played, win rate, K/D, team kills, aces/clutches, voice time.
  Existing helpers live in `analytic_ranking_data_access` / `analytic_leaderboard_data_access`.
- Player profile: totals, ranks, recent form, top operators.

The planner classifies into a recipe when possible; free-form SQL remains the fallback for
long-tail questions. This removes a whole class of casing/schema errors and cuts cost
(two LLM calls become one).

### 3.7 Evaluation harness

Add `tests/data/ai_sql_eval_cases.py` plus a runner:

- Cases: `(question, expected_intent, expected_sql_invariants, expected_answer_invariants)`.
- Seed a small deterministic SQLite fixture using the existing test DB helpers.
- Metrics: intent accuracy, SQL executes, row-set matches, answer contains expected
  canonical names, no invented names, no false "unavailable" claims.
- Must include the Doc example and a few casing traps (`ranked` vs `Ranked`,
  `doc` vs `Doc`).
- Run in CI; fail on regressions.

### 3.8 Schema-drift guard

A test enumerates `sqlite_master` tables and `PRAGMA table_info` and asserts:

- Every allowlisted table exists in `DataCatalog`.
- Every allowlisted column is described.
- Every catalog column exists in the live schema.
- Every categorical value found in the DB is listed (or explicitly marked as open-ended).

This keeps the catalog honest as migrations land.

## 4. Phased rollout

### Phase 1 — Grounding (small, immediate)
- Inject today's UTC date and coverage into planner + SQL prompts.
- Fix the clarifying-question prompt.
- Make `_domain_schema_text` include `operator_stats` and the casing rules.

Acceptance: the Doc question produces a valid query (or an honest, specific answer) on
the local DB; no "2026 is unavailable" response.

### Phase 2 — Catalog (the main investment)
- Add `deps/ai/data_catalog.py` with TableSpec/ColumnSpec.
- Render prompts from the catalog; delete hand-written schema strings.
- Add schema-drift test.

Acceptance: one source of truth; prompts include purpose/grain/time/categoricals/gotchas.

### Phase 3 — Validator + zero-row diagnosis
- Add catalog-aware validation and auto-repair for casing/CSV/rollback.
- Add the filter-ladder diagnosis and feed facts to the clarifier.

Acceptance: no zero-row query reaches the user without a diagnosis; traps are auto-fixed
or rejected with actionable feedback.

### Phase 4 — Recipes
- Implement typed recipes for top operators and core leaderboards.
- Route planner output to recipes first, SQL fallback second.

Acceptance: the top ~10 question classes never depend on free-form SQL; cost and latency drop.

### Phase 5 — Eval + observability
- Add the eval suite and CI gate.
- Log plan, SQL, row count, validation outcome, and provider per request.

Acceptance: visible accuracy trend; regressions caught before deploy.

## 5. File-level change map

| File | Change |
|---|---|
| `deps/ai/data_catalog.py` | New: TableSpec/ColumnSpec, allowlist, coverage, renderer |
| `deps/ai/sql_validator.py` | New (or extend `ai_functions`): catalog-aware validation/repair |
| `deps/ai/zero_row_diagnostics.py` | New: filter ladder + facts |
| `deps/ai/recipes.py` | New: typed metric queries |
| `deps/ai/ai_functions.py` | Use catalog in `build_query_plan_prompt`, `ask_ai_sql_for_stats`; fix clarifier |
| `deps/analytic_constants.py` | May become redundant; keep as column selectors or generate from catalog |
| `deps/data_access.py` | Add a bounded query helper for diagnostics |
| `tests/...` | Catalog drift test, eval cases, casing regressions |

## 6. Risks and mitigations

- **Catalog drift** → drift test fails CI on any schema change.
- **Prompt growth / cost** → render only selected domains, cap prompt chars, recipes
  reduce two LLM calls to one for common asks.
- **Data-model honesty** → the catalog states snapshots vs history; the model must say
  "lifetime only" for `operator_stats` rather than inventing a limitation.
- **SQL injection / unsafe reads** → keep read-only allowlist, statement checks, table
  allowlist, and bounded queries.
- **Provider changes** → keep Gemini/OpenAI fallback; provider is recorded in the audit log.

## 7. Implementation notes

What shipped:

| Area | File |
|---|---|
| Semantic table catalog, coverage, prompt rendering | `deps/ai/data_catalog.py` |
| Read-only, catalog-aware SQL validation and casing repair | `deps/ai/sql_validator.py` |
| Empty-result filter diagnosis | `deps/ai/zero_row_diagnostics.py` |
| Deterministic operator/leaderboard recipes | `deps/ai/recipes.py` |
| Prompt wiring, recipe routing, clarifier fix, logs | `deps/ai/ai_functions.py` |
| Catalog drift, validator, recipe, diagnosis, prompt tests | `tests/ai_data_access_unit_test.py` |

Behaviour changes:

- Planner and SQL prompts now carry `Today is YYYY-MM-DD (UTC)` and the real match
  coverage from `user_full_match_info`.
- SQL prompts render table purpose, grain, time semantics, joins, legal values, traps,
  key columns, and the full column list from the catalog.
- `session_type` and `operator_name` literals are normalized to `LOWER(...)` so the
  `'Ranked'`/`'ranked'` and `'Doc'`/`'doc'` traps cannot silently return zero rows.
- Bare `operators = ...` / `operators LIKE ...` filters are rejected with actionable
  feedback; `',' || LOWER(operators) || ',' LIKE '%,<op>,%'` is required.
- Leaderboard aggregates over `user_full_match_info` must exclude `is_rollback`.
- A zero-row result triggers a filter-removal diagnosis, which is fed back into the
  retry prompt and into the clarifying question.
- The clarifying prompt no longer asks for a "past date range" and is grounded in
  coverage facts.
- Clear question shapes use deterministic recipes first: operator rounds (lifetime and
  date-scoped), match leaderboards (matches, wins, win rate, K/D, team kills, aces,
  clutches, first kills/deaths), and voice time.
- The Doc question now returns a real top-10 leaderboard from the local database
  instead of a false "2026 is unavailable" answer.
- The new test file matches the existing CI gate (`make unit-test-coverage` runs
  `tests/*_unit_test.py`; mypy covers `deps`, `cogs`, and `tests`).

Known limitation (documented in the prompt and recipe note):

- `operator_stats.rounds_played` is exact per operator but is a lifetime snapshot with
  no date dimension. Date-scoped operator questions use
  `user_full_match_info.round_played_count`, which counts the full rounds of each match
  in which the operator appears, so the result is an upper-bound estimate.

Verification:

```bash
.venv/bin/python -m pytest tests/ai_context_unit_test.py tests/ai_data_access_unit_test.py \
  tests/ai_functions_integration_test.py tests/ai_summary_timing_regression_test.py -q
.venv/bin/python -m mypy deps/ai/ai_functions.py deps/ai/data_catalog.py \
  deps/ai/sql_validator.py deps/ai/zero_row_diagnostics.py deps/ai/recipes.py
```
