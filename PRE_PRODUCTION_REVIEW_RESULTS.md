# Pre-Production Review Results (2026-06-02)

Review of staged changes: rank-system overhaul, LFG role pings, `modresetrank`, Chrome version detection.

## Automated checks

| Check | Result |
|-------|--------|
| `make lint-black` | Pass |
| `make lint-pylint` | Pass (9.66/10, existing test warnings only) |
| `make lint-mypy` | Pass (after adding mypy overrides for new rank command test modules) |
| `make unit-test` | **420 passed** (after fixing `test_set_member_role_from_rank_*` mock) |
| `make integration-test` | **103 passed, 4 failed** (see below) |
| `python -c "import bot"` | Pass |

### Integration test failures (environment / live API)

- `tests/browser_integration_test.py::test_highest_rank_emerald`, `test_highest_rank_gold`
- `tests/data_access_integration_test.py::test_data_access_get_r6tracker_max_rank_test_emerald_period`, `test_data_access_get_r6tracker_max_rank_test_gold`

Failures tied to live R6 Tracker responses (e.g. `KeyError: 'data'`, empty/error JSON). Not introduced by rank-role logic; run again on prod-like network or accept as flaky live tests.

## Fixes applied during review

1. **`tests/functions_unit_test.py`** — Patch `resolve_rank_role_name` so rank mocks are not mapped to `Unranked` via real `siege_ranks`.
2. **`cogs/mod_basic.py` `modresetrank`** — Exclude `guild.default_role` and managed roles from `member.edit(roles=...)`.
3. **`cogs/mod_basic.py` `modresetrank`** — Removed `@commands.has_permissions(administrator=True)` so Mod role can use the command (matches `_is_admin_or_mod`).
4. **`tests/mod_basic_unit_test.py`** — Added test for default/managed role exclusion; `guild.default_role` on mocks.
5. **`pyproject.toml`** — Mypy `ignore_errors` for `tests.user_rank_commands_unit_test` and `tests.mod_basic_unit_test` (callback mock patterns).

## Go / No-Go checklist

| Item | Status | Notes |
|------|--------|-------|
| Black, pylint, mypy clean | **Go** | |
| Unit tests pass | **Go** | 420/420 |
| Integration tests | **Caution** | 4 live-browser/API failures |
| App imports | **Go** | |
| Prod guild has `Unranked` role + emoji | **Manual** | Required before deploy; bot maps all no-rank to `Unranked` |
| `modresetrank` safe on real members | **Go** | Code fixed for @everyone / managed roles |
| Daily refresh browser load | **Caution** | See risk section |
| LFG role pings intentional | **Go** | Rank-band pings; `@here` removed on manual `/lfg` |
| Current-season rank parsing | **Go** | Uses `metadata.currentSeason`; fixture → `Unranked` when season missing |

## Deployment prerequisites (manual)

1. Every production guild must have a Discord role named **`Unranked`**.
2. Guild emoji named **`Unranked`** (loaded on `on_ready` into `bot.guild_emoji`).
3. Rank roles used in LFG pings should be **mentionable** (or bot has permission to mention them).

## Risk summary

### High — daily `refresh_current_rank_roles_cross_guilds`

- Called from `daily_saving_active_user_matches_task` in `cogs/tasks.py`.
- Each active user triggers `_download_current_season_rank_sync` → **new Chrome session per user**.
- With N active users, expect N browser startups per day; circuit breaker opens after 5 failures (300s timeout).
- **Recommendation:** Batch rank fetches in one `BrowserContextManager` session or add caching before heavy prod load.

### Medium — early-season mass `Unranked`

- All rank sync paths use **current season** rank, not max rank.
- Users with no ranked games in `metadata.currentSeason` get **Unranked** (intended after season reset).

### Low — `get_active_user_info_with_connected_voice`

- Shared helper used by rank refresh; duplicate pattern with inline logic in `persist_siege_matches_cross_guilds` is intentional DRY, not dead code.

### Low — `force_fetch` on `data_access_get_r6tracker_current_season_rank`

- Parameter unused (cache disabled); no functional bug.

## Rank behavior validation

- `parse_json_current_season_rank` on `tests/tests_assets/nosleep_rb6_new_season_profile.json` → `('Unranked', 0)` when `currentSeason` has no segment.
- LFG: Unranked-only voice → pings `<@&Unranked>` only; Bronze → Bronze + Copper (no Unranked).
