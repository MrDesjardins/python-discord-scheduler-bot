# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python Discord bot for a Rainbow Six Siege gaming community with features including:
- Daily scheduling system for tracking when users plan to play
- Tournament system (single elimination, 1v1 to 5v5) with betting
- Automated statistics tracking via R6 Tracker API integration
- AI-powered conversation and summaries (Gemini/OpenAI)
- Analytics and visualizations of user activity and relationships
- Custom 10-man game mode with map selection and team balancing
- Follow/notification system for voice channel activity

## Development Commands

### Running the Bot
```bash
# Development
source .venv/bin/activate
python3 bot.py  # or ./bot.py

# Uses BOT_TOKEN_DEV when ENV=dev, BOT_TOKEN when ENV=prod
```

### Testing
```bash
# Run all tests
make test

# Unit tests only
make unit-test

# Integration tests only
make integration-test

# Coverage report (opens in browser on WSL)
make unit-test-coverage-web
make integration-test-coverage-web

# Coverage for CI
make unit-test-coverage
make integration-test-coverage
```

### Linting
```bash
# Run all linters
make lint

# Individual linters
make lint-pylint   # Code quality checks
make lint-black    # Code formatting (auto-fixes)
make lint-mypy     # Type checking
```

### Admin Console
```bash
python3 botadmin.py  # Interactive menu for server management and visualizations
```

### Deployment
```bash
deployment/update.sh  # Pull latest code, install deps, restart service on production
```

## Architecture

### Core Structure

**Bot Initialization (bot.py → deps/mybot.py → deps/bot_singleton.py)**
- Entry point uses `BotSingleton` pattern to ensure single bot instance
- `MyBot` extends `discord.ext.commands.Bot` with custom intents and emoji caching
- Cogs are auto-loaded from `cogs/` directory via `setup_hook()`

**Command Organization (cogs/)**
- `events.py`: Core event handlers (on_ready, voice state changes, messages, presence updates)
- `user_*.py`: User-facing commands (schedule, tournament, betting, features, custom games)
- `mod_*.py`: Moderator/admin commands (channels, analytics, tournament management)
- `tasks.py`: Scheduled background tasks (daily messages, stats posting, cache cleanup)
- `tournament_tasks.py`: Tournament-specific scheduled tasks

**Business Logic (deps/)**
- `bot_common_actions.py`: Shared Discord actions (send messages, move users, LFG, stats)
- `functions*.py`: Utility functions (date handling, R6 tracker parsing, schedule logic, statistics)
- `*_data_access.py`: Database access layers for different domains
- `analytic_*.py`: Analytics data access, processing, and visualization
- `ai/`: AI integration for conversational features
- `tournaments/`: Complete tournament system (data, functions, UI, visualization)
- `bet/`: Betting system for tournaments
- `custom_match/`: 10-man custom game logic

### Data Layer

**Caching Strategy (deps/cache.py)**
- Two-tier system: in-memory (`TTLCache`) and persistent file-based cache
- Memory cache: Fast access with automatic expiry, used for Discord objects and frequent lookups
- File cache: Survives restarts, used for configuration and long-term data
- All access through `get_cache()`, `set_cache()`, `remove_cache()` functions
- Cache keys defined in `deps/data_access.py` (e.g., `KEY_DAILY_MSG`, `KEY_GUILD_VOICE_CHANNELS`)

**Database (deps/system_database.py, user_activity.db)**
- SQLite with WAL mode for better write performance
- Stores: user activity (voice join/leave), match statistics, tournament data, betting records
- `DatabaseManager` class handles connections and migrations
- Separate test database (`user_activity_test.db`) for testing

**Data Access Pattern**
```
Cog Command → bot_common_actions → data_access → cache → database/API
                                 ↓
                         business functions → models
```

### Key Integration Points

**R6 Tracker API (deps/functions_r6_tracker.py, deps/browser.py)**
- Fetches match statistics and player profiles
- Uses Selenium with undetected Chrome driver to bypass protections
- Web scraping handled via `BrowserContextManager` for proper resource cleanup
- Match data parsed and stored in `UserFullMatchStats` model

**Discord Activity Monitoring (cogs/events.py)**
- Tracks Rainbow Six Siege activity states (menu, warming up, playing ranked, etc.)
- Generates automatic LFG messages when players return to menu
- Triggers stats collection when players leave voice channels
- Activity transitions stored in `KEY_GAMING_SESSION_LAST_ACTIVITY` cache

**AI System (deps/ai/)**
- Dual provider support: Gemini (primary) and OpenAI (fallback)
- `BotAISingleton` manages context and conversation history
- Can query database for stats and answer game-related questions
- Daily summaries generated via `ai_bot_functions.py`

### UI Components (ui/)

Discord.py Views for interactive buttons/dropdowns:
- `schedule_*.py`: Schedule selection interfaces
- `tournament_*.py`: Tournament registration and match reporting
- `bet_tournament_selector_*.py`: Betting market selection
- `confirmation_rank_view.py`: Rank verification flow
- `timezone_view.py`: Timezone selection

### Configuration

**Environment Variables (.env)**
```
ENV=dev|prod
BOT_TOKEN=<production token>
BOT_TOKEN_DEV=<development token>
GEMINI_API_KEY=<api key>
OPENAI_API_KEY=<api key>
```

**Per-Guild Settings (cached in data_access)**
- Schedule text channel: Where daily messages are posted
- Voice channels: Which channels to monitor
- Tournament text channel: Where brackets are displayed
- Main text channel: General announcements
- New user text channel: Welcome messages
- Bot voice behavior: Whether bot joins voice to announce schedules

### Testing Conventions

- Unit tests: `tests/*_unit_test.py` - Test individual functions with mocked dependencies
- Integration tests: `tests/*_integration_test.py` - Test with real database interactions
- Use `DATABASE_NAME_TEST` for test database isolation
- Mark non-parallel tests with `@pytest.mark.no_parallel` decorator
- Async tests automatically detected via `pytest-asyncio` plugin

### Important Patterns

**Singleton Pattern**
- `BotSingleton`: Single bot instance across application
- `BotAISingleton`: Single AI context manager
- `DatabaseManager`: Single database connection (instantiated as `database_manager`)

**Error Handling**
- Use `print_log()`, `print_warning_log()`, `print_error_log()` from `deps/log.py`
- Logs go to console and `app.log` file
- Discord exceptions often need try/catch for 404s when testing with prod data in dev

**Model Classes**
- Domain models in `deps/models.py`: `SimpleUser`, `UserFullMatchStats`, `ActivityTransition`, etc.
- Tournament models in `deps/tournaments/tournament_data_class.py`
- Bet models in `deps/bet/bet_data_class.py`
- Use `@dataclasses.dataclass` for simple data structures
- Complex models have `from_db_row()` static methods for database deserialization

**Rate Limiting**
- Custom rate limiter in `deps/ratelimiter.py`
- Browser interactions use `BrowserContextManager` to properly manage Chrome instances

### Data Flow Examples

**Daily Schedule Flow**
1. `tasks.py:send_daily_schedule_guild()` → triggered by scheduled task
2. `bot_common_actions.py:send_daily_question_to_a_guild()` → checks cache, sends message
3. User reactions → `events.py:on_reaction_add()` → cache updated
4. Auto-schedule application → `functions_schedule.py:schedule_check_and_update()` → reactions added to message

**Match Stats Flow**
1. User leaves voice → `events.py:on_voice_state_update()`
2. Queued for stats → `bot_common_actions.py:send_session_stats_to_queue()`
3. Background processing → `tasks.py:process_user_stat_queue()`
4. Fetch R6 data → `functions_r6_tracker.py` + `browser.py` (Selenium)
5. Parse and store → `analytic_data_access.py:insert_user_match_info()`
6. Display results → `functions_stats.py:generate_user_session_statistics()`

**Tournament Flow**
1. Creation → `mod_tournament.py:modcreatetournament()` → `tournament_data_access.py`
2. Registration → `user_tournament.py:registertournament()` → updates bracket
3. Match reporting → `tournament_ui_functions.py:TournamentMatchReportView` → validates scores
4. Bracket update → `tournament_visualizer.py:create_bracket_image()` → posts to channel
5. Bet distribution → `bet/bet_functions.py:distribute_bet_money()` → calculates payouts

### Performance Considerations

- Cache aggressively: Discord API calls are expensive
- Use cache prefixes for bulk invalidation (e.g., `GUILD:{guild_id}:*`)
- WAL mode on SQLite reduces lock contention
- Background tasks process heavy operations (stats fetching, image generation)
- Selenium instances properly cleaned up via context manager
