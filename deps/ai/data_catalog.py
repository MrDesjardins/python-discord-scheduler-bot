"""
Semantic catalog for the stats database used by the AI SQL path.

The catalog is the single source of truth for what each table means. Prompts are
rendered from it instead of being written by hand, and tests assert it stays in
sync with the live schema.

Why this exists: the previous prompt only listed column names. The model could not
tell which table is historical, which is a lifetime snapshot, which column is the
time axis, or which literal casing the database stores. That produced zero-row
queries and false "data is unavailable" answers (see docs/ai-data-access-plan.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional, Tuple


@dataclass(frozen=True)
class ColumnSpec:
    """One column, with the meaning the model needs to use it correctly."""

    name: str
    type: str
    description: str
    important: bool = False


@dataclass(frozen=True)
class TableSpec:
    """One table, with its grain, time semantics, joins, and traps."""

    name: str
    domain: str
    purpose: str
    grain: str
    time_column: Optional[str]
    time_semantics: str
    keys: str
    joins: Tuple[str, ...] = ()
    categoricals: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    gotchas: Tuple[str, ...] = ()
    default_filters: Tuple[str, ...] = ()
    columns: Tuple[ColumnSpec, ...] = ()


def _c(name: str, type_: str, description: str, important: bool = False) -> ColumnSpec:
    return ColumnSpec(name=name, type=type_, description=description, important=important)


USER_INFO = TableSpec(
    name="user_info",
    domain="identity",
    purpose="Identity spine: maps a Discord user id to their Ubisoft accounts and profile settings.",
    grain="one row per Discord user",
    time_column=None,
    time_semantics="current profile (not a history)",
    keys="id (Discord user id) is the join key used by every stats table",
    joins=(),
    gotchas=(
        "display_name is the Discord display name and must never be returned as the player identity.",
        "Canonical player name = COALESCE(ubisoft_username_active, ubisoft_username_max).",
        "Never filter match rows by ubisoft_username strings; join on user_id instead.",
        "Not every user has both Ubisoft names; a user may be missing from match data.",
    ),
    columns=(
        _c("id", "INTEGER", "Discord user id; primary key and join key.", True),
        _c("display_name", "TEXT", "Discord display name; alias only, not the answer identity.", True),
        _c("ubisoft_username_max", "TEXT", "Main Ubisoft account name (fallback canonical).", True),
        _c("ubisoft_username_active", "TEXT", "Currently used Ubisoft account name (preferred canonical).", True),
        _c("r6_tracker_active_id", "TEXT", "R6 Tracker profile UUID used for external lookups."),
        _c("time_zone", "TEXT", "User's configured time zone."),
        _c("max_mmr", "INTEGER", "Highest recorded MMR."),
    ),
)

USER_FULL_MATCH_INFO = TableSpec(
    name="user_full_match_info",
    domain="matches",
    purpose="Historical per-match stats recorded by the bot: the only table with a real match time axis.",
    grain="one row per tracked user per match",
    time_column="match_timestamp",
    time_semantics="historical; append-only; stored as ISO-8601 UTC text with offset",
    keys="id is the row key; match_uuid groups the users in the same match; user_id joins user_info",
    joins=("user_full_match_info.user_id = user_info.id",),
    categoricals={"session_type": ("Ranked", "Standard")},
    gotchas=(
        "Compare session_type with LOWER(session_type) = 'ranked'; the stored value is 'Ranked' and SQLite text = is case-sensitive.",
        "operators is a comma-separated list of display-case names, e.g. 'Capitão,Buck,Alibi,Valkyrie,Doc'.",
        "Filter an operator with ',' || LOWER(operators) || ',' LIKE '%,doc,%'; a bare operators = 'Doc' is wrong.",
        "round_played_count is the number of rounds in the match, not rounds on a specific operator.",
        "Summing round_played_count over matches that contain an operator overcounts that operator's rounds.",
        "Exclude is_rollback = 0 from aggregates unless the question is about rollbacks.",
        "has_win is stored as 0/1.",
        "Use DATE(match_timestamp) to group by day.",
    ),
    default_filters=("is_rollback = 0",),
    columns=(
        _c("id", "INTEGER", "Row key."),
        _c("match_uuid", "TEXT", "Match identifier shared by all tracked users in the match.", True),
        _c("user_id", "INTEGER", "Discord user id; join to user_info.id.", True),
        _c("match_timestamp", "DATETIME", "Match end time, ISO-8601 UTC text with offset. The only time axis.", True),
        _c("match_duration_ms", "INTEGER", "Match duration in milliseconds."),
        _c("data_center", "TEXT", "Match data center."),
        _c("session_type", "TEXT", "Playlist as stored: 'Ranked' or 'Standard'. Use LOWER() to compare.", True),
        _c("map_name", "TEXT", "Map played."),
        _c("is_surrender", "BOOLEAN", "Match ended by surrender (0/1)."),
        _c("is_forfeit", "BOOLEAN", "Match ended by forfeit (0/1)."),
        _c("is_rollback", "BOOLEAN", "Row rolled back by a later correction (0/1); exclude from aggregates.", True),
        _c("r6_tracker_user_uuid", "TEXT", "R6 Tracker profile UUID for this row."),
        _c("ubisoft_username", "TEXT", "Ubisoft name recorded for this match; not a safe identity filter."),
        _c("operators", "TEXT", "Comma-separated operator names used during the match.", True),
        _c("round_played_count", "INTEGER", "Rounds in the match (match-level, not per operator).", True),
        _c("round_won_count", "INTEGER", "Rounds won by the tracked user."),
        _c("round_lost_count", "INTEGER", "Rounds lost by the tracked user."),
        _c("round_disconnected_count", "INTEGER", "Rounds lost to disconnect."),
        _c("kill_count", "INTEGER", "Kills."),
        _c("death_count", "INTEGER", "Deaths."),
        _c("assist_count", "INTEGER", "Assists."),
        _c("head_shot_count", "INTEGER", "Headshot kills."),
        _c("tk_count", "INTEGER", "Team kills."),
        _c("ace_count", "INTEGER", "Aces."),
        _c("first_kill_count", "INTEGER", "First kills."),
        _c("first_death_count", "INTEGER", "First deaths."),
        _c("clutches_win_count", "INTEGER", "Clutches won."),
        _c("clutches_loss_count", "INTEGER", "Clutches lost."),
        _c("clutches_win_count_1v1", "INTEGER", "1v1 clutches won."),
        _c("clutches_win_count_1v2", "INTEGER", "1v2 clutches won."),
        _c("clutches_win_count_1v3", "INTEGER", "1v3 clutches won."),
        _c("clutches_win_count_1v4", "INTEGER", "1v4 clutches won."),
        _c("clutches_win_count_1v5", "INTEGER", "1v5 clutches won."),
        _c("clutches_lost_count_1v1", "INTEGER", "1v1 clutches lost."),
        _c("clutches_lost_count_1v2", "INTEGER", "1v2 clutches lost."),
        _c("clutches_lost_count_1v3", "INTEGER", "1v3 clutches lost."),
        _c("clutches_lost_count_1v4", "INTEGER", "1v4 clutches lost."),
        _c("clutches_lost_count_1v5", "INTEGER", "1v5 clutches lost."),
        _c("kill_1_count", "INTEGER", "Rounds with one kill."),
        _c("kill_2_count", "INTEGER", "Rounds with two kills."),
        _c("kill_3_count", "INTEGER", "Rounds with three kills."),
        _c("kill_4_count", "INTEGER", "Rounds with four kills."),
        _c("kill_5_count", "INTEGER", "Rounds with five kills."),
        _c("rank_points", "INTEGER", "Rank points after the match."),
        _c("rank_name", "TEXT", "Rank name after the match."),
        _c("points_gained", "INTEGER", "Rank points gained or lost."),
        _c("rank_previous", "INTEGER", "Rank points before the match."),
        _c("kd_ratio", "REAL", "Kill/death ratio for the match."),
        _c("head_shot_percentage", "REAL", "Headshot percentage for the match."),
        _c("kills_per_round", "REAL", "Kills per round."),
        _c("deaths_per_round", "REAL", "Deaths per round."),
        _c("assists_per_round", "REAL", "Assists per round."),
        _c("has_win", "BOOLEAN", "Whether the user won (0/1).", True),
    ),
)

USER_FULL_STATS_INFO = TableSpec(
    name="user_full_stats_info",
    domain="matches",
    purpose="R6 Tracker lifetime profile snapshot: all-time totals, not the bot's own match history.",
    grain="one row per user",
    time_column=None,
    time_semantics="point-in-time snapshot; not filterable by date",
    keys="user_id joins user_info; r6_tracker_user_uuid identifies the tracked profile",
    joins=("user_full_stats_info.user_id = user_info.id",),
    gotchas=(
        "Never use this table for 'in 2026' or any date range; it has no time dimension.",
        "Only a subset of users have a snapshot; do not assume every user is present.",
        "Playlist splits are encoded in column prefixes rank_*, arcade_*, quickmatch_*.",
    ),
    columns=(
        _c("id", "INTEGER", "Row key in databases created after the current schema; never rely on it."),
        _c("user_id", "INTEGER", "Discord user id; join to user_info.id.", True),
        _c("r6_tracker_user_uuid", "TEXT", "R6 Tracker profile UUID."),
        _c("total_matches_played", "INTEGER", "All-time matches played.", True),
        _c("total_matches_won", "INTEGER", "All-time matches won."),
        _c("total_matches_lost", "INTEGER", "All-time matches lost."),
        _c("total_matches_abandoned", "INTEGER", "All-time abandoned matches."),
        _c("time_played_seconds", "INTEGER", "All-time time played in seconds.", True),
        _c("total_kills", "INTEGER", "All-time kills."),
        _c("total_deaths", "INTEGER", "All-time deaths."),
        _c("total_attacker_round_wins", "INTEGER", "All-time attacker round wins."),
        _c("total_defender_round_wins", "INTEGER", "All-time defender round wins."),
        _c("total_headshots", "INTEGER", "All-time headshots."),
        _c("total_headshots_missed", "INTEGER", "All-time missed headshots."),
        _c("headshot_percentage", "REAL", "All-time headshot percentage."),
        _c("total_wall_bang", "INTEGER", "All-time wallbangs."),
        _c("total_damage", "INTEGER", "All-time damage."),
        _c("total_assists", "INTEGER", "All-time assists."),
        _c("total_team_kills", "INTEGER", "All-time team kills."),
        _c("attacked_breacher_count", "INTEGER", "Rounds as attack breacher."),
        _c("attacked_breacher_percentage", "REAL", "Attack breacher percentage."),
        _c("attacked_fragger_count", "INTEGER", "Rounds as attack fragger."),
        _c("attacked_fragger_percentage", "REAL", "Attack fragger percentage."),
        _c("attacked_intel_count", "INTEGER", "Rounds as attack intel."),
        _c("attacked_intel_percentage", "REAL", "Attack intel percentage."),
        _c("attacked_roam_count", "INTEGER", "Rounds as attack roamer."),
        _c("attacked_roam_percentage", "REAL", "Attack roamer percentage."),
        _c("attacked_support_count", "INTEGER", "Rounds as attack support."),
        _c("attacked_support_percentage", "REAL", "Attack support percentage."),
        _c("attacked_utility_count", "INTEGER", "Rounds as attack utility."),
        _c("attacked_utility_percentage", "REAL", "Attack utility percentage."),
        _c("defender_debuffer_count", "INTEGER", "Rounds as defender debuffer."),
        _c("defender_debuffer_percentage", "REAL", "Defender debuffer percentage."),
        _c("defender_entry_denier_count", "INTEGER", "Rounds as entry denier."),
        _c("defender_entry_denier_percentage", "REAL", "Entry denier percentage."),
        _c("defender_intel_count", "INTEGER", "Rounds as defender intel."),
        _c("defender_intel_percentage", "REAL", "Defender intel percentage."),
        _c("defender_support_count", "INTEGER", "Rounds as defender support."),
        _c("defender_support_percentage", "REAL", "Defender support percentage."),
        _c("defender_trapper_count", "INTEGER", "Rounds as trapper."),
        _c("defender_trapper_percentage", "REAL", "Trapper percentage."),
        _c("defender_utility_denier_count", "INTEGER", "Rounds as utility denier."),
        _c("defender_utility_denier_percentage", "REAL", "Utility denier percentage."),
        _c("kd_ratio", "REAL", "All-time K/D ratio.", True),
        _c("kill_per_match", "REAL", "All-time kills per match."),
        _c("kill_per_minute", "REAL", "All-time kills per minute."),
        _c("win_percentage", "REAL", "All-time win percentage."),
        _c("rank_match_played", "INTEGER", "Ranked matches played."),
        _c("rank_match_won", "INTEGER", "Ranked matches won."),
        _c("rank_match_lost", "INTEGER", "Ranked matches lost."),
        _c("rank_match_abandoned", "INTEGER", "Ranked matches abandoned."),
        _c("rank_kills_count", "INTEGER", "Ranked kills."),
        _c("rank_deaths_count", "INTEGER", "Ranked deaths."),
        _c("rank_kd_ratio", "REAL", "Ranked K/D ratio."),
        _c("rank_kill_per_match", "REAL", "Ranked kills per match."),
        _c("rank_win_percentage", "REAL", "Ranked win percentage."),
        _c("arcade_match_played", "INTEGER", "Arcade matches played."),
        _c("arcade_match_won", "INTEGER", "Arcade matches won."),
        _c("arcade_match_lost", "INTEGER", "Arcade matches lost."),
        _c("arcade_match_abandoned", "INTEGER", "Arcade matches abandoned."),
        _c("arcade_kills_count", "INTEGER", "Arcade kills."),
        _c("arcade_deaths_count", "INTEGER", "Arcade deaths."),
        _c("arcade_kd_ratio", "REAL", "Arcade K/D ratio."),
        _c("arcade_kill_per_match", "REAL", "Arcade kills per match."),
        _c("arcade_win_percentage", "REAL", "Arcade win percentage."),
        _c("quickmatch_match_played", "INTEGER", "Quickmatch matches played."),
        _c("quickmatch_match_won", "INTEGER", "Quickmatch matches won."),
        _c("quickmatch_match_lost", "INTEGER", "Quickmatch matches lost."),
        _c("quickmatch_match_abandoned", "INTEGER", "Quickmatch matches abandoned."),
        _c("quickmatch_kills_count", "INTEGER", "Quickmatch kills."),
        _c("quickmatch_deaths_count", "INTEGER", "Quickmatch deaths."),
        _c("quickmatch_kd_ratio", "REAL", "Quickmatch K/D ratio."),
        _c("quickmatch_kill_per_match", "REAL", "Quickmatch kills per match."),
        _c("quickmatch_win_percentage", "REAL", "Quickmatch win percentage."),
    ),
)

OPERATOR_STATS = TableSpec(
    name="operator_stats",
    domain="matches",
    purpose="R6 Tracker lifetime per-operator snapshot: the only table with exact per-operator rounds played.",
    grain="one row per user per operator per session_type per gamemode",
    time_column=None,
    time_semantics="point-in-time snapshot; last_updated is the snapshot time, not a match time",
    keys="user_id joins user_info; unique on (user_id, operator_name, session_type, gamemode)",
    joins=("operator_stats.user_id = user_info.id",),
    categoricals={
        "session_type": ("ranked",),
        "gamemode": ("pvp_ranked",),
    },
    gotchas=(
        "operator_name is lowercase; compare with LOWER(operator_name) = 'doc'.",
        "No date dimension: this table cannot answer 'in 2026'. It is a lifetime snapshot.",
        "rounds_played is the exact per-operator rounds over the snapshot lifetime.",
        "Use this table for lifetime operator totals; use user_full_match_info for date-scoped estimates.",
    ),
    columns=(
        _c("id", "INTEGER", "Row key."),
        _c("user_id", "INTEGER", "Discord user id; join to user_info.id.", True),
        _c("operator_name", "TEXT", "Lowercase operator name, e.g. 'doc'.", True),
        _c("session_type", "TEXT", "Playlist as stored, e.g. 'ranked'.", True),
        _c("side", "TEXT", "Attacker or defender side."),
        _c("gamemode", "TEXT", "Game mode, e.g. 'pvp_ranked'.", True),
        _c("matches_played", "INTEGER", "Matches played with this operator."),
        _c("matches_won", "INTEGER", "Matches won with this operator."),
        _c("matches_lost", "INTEGER", "Matches lost with this operator."),
        _c("win_percentage", "REAL", "Win percentage with this operator."),
        _c("time_played", "INTEGER", "Time played with this operator."),
        _c("rounds_played", "INTEGER", "Exact rounds played with this operator over the snapshot.", True),
        _c("rounds_won", "INTEGER", "Rounds won with this operator."),
        _c("rounds_lost", "INTEGER", "Rounds lost with this operator."),
        _c("round_win_pct", "REAL", "Round win percentage."),
        _c("kills", "INTEGER", "Kills with this operator."),
        _c("deaths", "INTEGER", "Deaths with this operator."),
        _c("kd_ratio", "REAL", "K/D ratio with this operator."),
        _c("kills_per_game", "REAL", "Kills per game."),
        _c("kills_per_round", "REAL", "Kills per round."),
        _c("last_updated", "TIMESTAMP", "When this snapshot row was refreshed."),
    ),
)

USER_ACTIVITY = TableSpec(
    name="user_activity",
    domain="activity",
    purpose="Voice channel connect/disconnect event log used to compute voice time.",
    grain="one row per connect or disconnect event",
    time_column="timestamp",
    time_semantics="historical event log",
    keys="user_id joins user_info; channel_id and guild_id scope the event",
    joins=("user_activity.user_id = user_info.id",),
    categoricals={"event": ("connect", "disconnect")},
    gotchas=(
        "Voice time is computed by pairing connect and disconnect events, not by reading one row.",
        "Filter by guild_id for 'this server' questions.",
        "A connect without a matching disconnect must be handled explicitly.",
    ),
    columns=(
        _c("id", "INTEGER", "Row key."),
        _c("user_id", "INTEGER", "Discord user id; join to user_info.id.", True),
        _c("channel_id", "INTEGER", "Voice channel id."),
        _c("guild_id", "INTEGER", "Discord guild id; use to scope to this server.", True),
        _c("event", "TEXT", "'connect' or 'disconnect'.", True),
        _c("timestamp", "DATETIME", "Event time (UTC).", True),
    ),
)

USER_PLAYER_VALUE = TableSpec(
    name="user_player_value",
    domain="matches",
    purpose="Nightly computed team-balancing value and rating per user.",
    grain="one row per user per algorithm",
    time_column="computed_at",
    time_semantics="computed snapshot; last_match_timestamp shows the newest match used",
    keys="(user_id, algorithm) is the primary key; user_id joins user_info",
    joins=("user_player_value.user_id = user_info.id",),
    gotchas=(
        "algorithm selects the scoring variant.",
        "Use for player-value/team-balancing questions, not raw match stats.",
    ),
    columns=(
        _c("user_id", "INTEGER", "Discord user id; join to user_info.id.", True),
        _c("algorithm", "TEXT", "Scoring algorithm variant.", True),
        _c("value", "REAL", "Computed team-balancing value.", True),
        _c("rating", "REAL", "Derived rating."),
        _c("match_count", "INTEGER", "Matches used in the computation."),
        _c("last_match_timestamp", "DATETIME", "Newest match used in the computation."),
        _c("computed_at", "DATETIME", "When the value was computed."),
    ),
)

TOURNAMENT = TableSpec(
    name="tournament",
    domain="tournaments",
    purpose="Tournament definition and schedule.",
    grain="one row per tournament",
    time_column="start_date",
    time_semantics="operational schedule",
    keys="id is referenced by user_tournament, tournament_game, and bet tables",
    categoricals={"bet_odds_generation": ("kill_count",)},
    gotchas=("Dates are tournament dates, not match dates.",),
    columns=(
        _c("id", "INTEGER", "Tournament id.", True),
        _c("guild_id", "INTEGER", "Discord guild that owns the tournament."),
        _c("name", "TEXT", "Tournament name.", True),
        _c("registration_date", "DATETIME", "Registration date."),
        _c("start_date", "DATETIME", "Start date.", True),
        _c("end_date", "DATETIME", "End date."),
        _c("best_of", "INTEGER", "Series length."),
        _c("max_players", "INTEGER", "Maximum players."),
        _c("maps", "TEXT", "Comma-separated map pool."),
        _c("has_started", "BOOLEAN", "Tournament started (0/1)."),
        _c("has_finished", "BOOLEAN", "Tournament finished (0/1)."),
        _c("team_size", "INTEGER", "Players per team."),
        _c("bet_odds_generation", "TEXT", "How betting odds are computed."),
    ),
)

USER_TOURNAMENT = TableSpec(
    name="user_tournament",
    domain="tournaments",
    purpose="Tournament registrations.",
    grain="one row per user registration",
    time_column="registration_date",
    time_semantics="historical registration",
    keys="user_id and tournament_id join user_info and tournament",
    joins=("user_tournament.user_id = user_info.id", "user_tournament.tournament_id = tournament.id"),
    columns=(
        _c("id", "INTEGER", "Row key."),
        _c("user_id", "INTEGER", "Discord user id.", True),
        _c("tournament_id", "INTEGER", "Tournament id.", True),
        _c("registration_date", "DATETIME", "Registration time."),
    ),
)

TOURNAMENT_GAME = TableSpec(
    name="tournament_game",
    domain="tournaments",
    purpose="Bracket games and results.",
    grain="one row per tournament game",
    time_column="timestamp",
    time_semantics="historical game result",
    keys="tournament_id joins tournament; user1_id, user2_id, user_winner_id join user_info",
    joins=("tournament_game.tournament_id = tournament.id",),
    gotchas=("Bracket linkage uses next_game1_id and next_game2_id.",),
    columns=(
        _c("id", "INTEGER", "Game id."),
        _c("tournament_id", "INTEGER", "Tournament id.", True),
        _c("user1_id", "INTEGER", "First player id."),
        _c("user2_id", "INTEGER", "Second player id."),
        _c("user_winner_id", "INTEGER", "Winner player id.", True),
        _c("score", "TEXT", "Series score."),
        _c("map", "TEXT", "Map played."),
        _c("timestamp", "DATETIME", "When the game was recorded."),
        _c("next_game1_id", "INTEGER", "Bracket link for the first slot."),
        _c("next_game2_id", "INTEGER", "Bracket link for the second slot."),
    ),
)

TOURNAMENT_TEAM_MEMBERS = TableSpec(
    name="tournament_team_members",
    domain="tournaments",
    purpose="Tournament team rosters.",
    grain="one row per team member",
    time_column=None,
    time_semantics="roster state",
    keys="tournament_id joins tournament; user_id and user_leader_id join user_info",
    joins=("tournament_team_members.tournament_id = tournament.id",),
    columns=(
        _c("id", "INTEGER", "Row key."),
        _c("user_leader_id", "INTEGER", "Team leader user id."),
        _c("tournament_id", "INTEGER", "Tournament id.", True),
        _c("user_id", "INTEGER", "Team member user id.", True),
    ),
)

BET_USER_TOURNAMENT = TableSpec(
    name="bet_user_tournament",
    domain="bets",
    purpose="Tournament-level bets placed by users.",
    grain="one row per user tournament bet",
    time_column=None,
    time_semantics="bet state",
    keys="user_id and tournament_id join user_info and tournament",
    joins=("bet_user_tournament.user_id = user_info.id", "bet_user_tournament.tournament_id = tournament.id"),
    columns=(
        _c("id", "INTEGER", "Row key."),
        _c("tournament_id", "INTEGER", "Tournament id.", True),
        _c("user_id", "INTEGER", "Bettor user id.", True),
        _c("amount", "INTEGER", "Bet amount.", True),
    ),
)

BET_GAME = TableSpec(
    name="bet_game",
    domain="bets",
    purpose="Per-game betting market odds and distribution state.",
    grain="one row per tournament game market",
    time_column=None,
    time_semantics="market state",
    keys="tournament_game_id joins tournament_game",
    joins=("bet_game.tournament_game_id = tournament_game.id",),
    gotchas=("probabilities are in [0,1]; bet_distributed is a 0/1 flag.",),
    columns=(
        _c("id", "INTEGER", "Row key."),
        _c("tournament_id", "INTEGER", "Tournament id.", True),
        _c("tournament_game_id", "INTEGER", "Tournament game id.", True),
        _c("probability_user_1_win", "REAL", "Win probability for user 1."),
        _c("probability_user_2_win", "REAL", "Win probability for user 2."),
        _c("bet_distributed", "BOOLEAN", "Whether payouts were distributed (0/1)."),
    ),
)

BET_USER_GAME = TableSpec(
    name="bet_user_game",
    domain="bets",
    purpose="Individual bets on a specific tournament game.",
    grain="one row per user game bet",
    time_column="time_bet_placed",
    time_semantics="historical bet",
    keys="user_id joins user_info; bet_game_id joins bet_game",
    joins=("bet_user_game.user_id = user_info.id", "bet_user_game.bet_game_id = bet_game.id"),
    columns=(
        _c("id", "INTEGER", "Row key."),
        _c("tournament_id", "INTEGER", "Tournament id."),
        _c("bet_game_id", "INTEGER", "Bet market id.", True),
        _c("user_id", "INTEGER", "Bettor user id.", True),
        _c("amount", "INTEGER", "Bet amount.", True),
        _c("user_id_bet_placed", "INTEGER", "User the bet is on."),
        _c("time_bet_placed", "DATETIME", "When the bet was placed."),
        _c("probability_user_win_when_bet_placed", "REAL", "Win probability at bet time."),
        _c("bet_distributed", "BOOLEAN", "Whether this bet was paid out (0/1)."),
    ),
)

BET_LEDGER_ENTRY = TableSpec(
    name="bet_ledger_entry",
    domain="bets",
    purpose="Betting ledger movements.",
    grain="one row per ledger movement",
    time_column=None,
    time_semantics="ledger history",
    keys="user_id joins user_info; bet ids join the bet tables",
    joins=("bet_ledger_entry.user_id = user_info.id",),
    columns=(
        _c("id", "INTEGER", "Row key."),
        _c("tournament_id", "INTEGER", "Tournament id."),
        _c("tournament_game_id", "INTEGER", "Tournament game id."),
        _c("bet_game_id", "INTEGER", "Bet market id."),
        _c("bet_user_game_id", "INTEGER", "User game bet id."),
        _c("user_id", "INTEGER", "User id.", True),
        _c("amount", "INTEGER", "Ledger amount (positive or negative).", True),
    ),
)


TABLES: Dict[str, TableSpec] = {
    table.name: table
    for table in (
        USER_INFO,
        USER_FULL_MATCH_INFO,
        USER_FULL_STATS_INFO,
        OPERATOR_STATS,
        USER_ACTIVITY,
        USER_PLAYER_VALUE,
        TOURNAMENT,
        USER_TOURNAMENT,
        TOURNAMENT_GAME,
        TOURNAMENT_TEAM_MEMBERS,
        BET_USER_TOURNAMENT,
        BET_GAME,
        BET_USER_GAME,
        BET_LEDGER_ENTRY,
    )
}

# Tables the LLM may query. Archive, cache, market-state, and subscription tables are
# intentionally excluded: they contain private content or are not stats data.
STATS_TABLE_ALLOWLIST = frozenset(TABLES)

DOMAIN_TABLES: Dict[str, Tuple[str, ...]] = {
    "general": ("user_info", "user_full_match_info", "user_full_stats_info", "operator_stats"),
    "matches": (
        "user_info",
        "user_full_match_info",
        "user_full_stats_info",
        "operator_stats",
        "user_player_value",
    ),
    "activity": ("user_info", "user_activity"),
    "tournaments": (
        "user_info",
        "tournament",
        "user_tournament",
        "tournament_game",
        "tournament_team_members",
        "bet_user_tournament",
        "bet_game",
        "bet_user_game",
        "bet_ledger_entry",
    ),
    "bets": (
        "user_info",
        "tournament",
        "user_tournament",
        "tournament_game",
        "tournament_team_members",
        "bet_user_tournament",
        "bet_game",
        "bet_user_game",
        "bet_ledger_entry",
    ),
}

CANONICAL_NAME_SQL = "COALESCE(user_info.ubisoft_username_active, user_info.ubisoft_username_max)"


def today_utc_iso() -> str:
    """Current UTC date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).date().isoformat()


def get_coverage() -> Tuple[Optional[str], Optional[str]]:
    """
    Earliest and latest recorded match timestamps, or (None, None) when unavailable.

    Kept resilient: coverage is advisory prompt grounding, never a reason to fail a query.
    """
    try:
        from deps.system_database import database_manager

        row = (
            database_manager.get_cursor()
            .execute("SELECT MIN(match_timestamp), MAX(match_timestamp) FROM user_full_match_info")
            .fetchone()
        )
    except Exception:
        return (None, None)
    if not row:
        return (None, None)
    return (row[0], row[1])


def render_grounding() -> str:
    """Date and data-coverage facts that every SQL/planner prompt must carry."""
    today = today_utc_iso()
    earliest, latest = get_coverage()
    lines = [f"Today is {today} (UTC)."]
    if earliest and latest:
        lines.append(f"Recorded match data covers {str(earliest)[:10]} to {str(latest)[:10]} (UTC).")
        lines.append(
            "If a requested period is outside this range, state what is available using these facts. "
            "Never claim a year or date range is unavailable before checking this coverage."
        )
    else:
        lines.append("No recorded match coverage is available right now; do not invent dates.")
    return "\n".join(lines)


def domains_for_plan(planned_domain: str) -> Tuple[str, ...]:
    """Map a planner domain to catalog domain names (which render to tables)."""
    if planned_domain == "general":
        return ("matches", "activity")
    if planned_domain == "bets":
        return ("tournaments",)
    if planned_domain in DOMAIN_TABLES:
        return (planned_domain,)
    return ("matches",)


def tables_for_domains(domains: Iterable[str]) -> Tuple[TableSpec, ...]:
    """Resolve domain names to table specs, preserving first-seen order and de-duplicating."""
    seen: set[str] = set()
    resolved: list[TableSpec] = []
    for domain in domains:
        for table_name in DOMAIN_TABLES.get(domain, ()):
            if table_name in seen or table_name not in TABLES:
                continue
            seen.add(table_name)
            resolved.append(TABLES[table_name])
    return tuple(resolved)


def render_table(table: TableSpec) -> str:
    """Render one table as a compact semantic block for an LLM prompt."""
    lines = [f"TABLE `{table.name}` — {table.purpose}"]
    lines.append(f"  grain: {table.grain}")
    if table.time_column:
        lines.append(f"  time column: `{table.time_column}` ({table.time_semantics})")
    else:
        lines.append(f"  time: none ({table.time_semantics})")
    lines.append(f"  keys: {table.keys}")
    for join in table.joins:
        lines.append(f"  join: {join}")
    for column, values in table.categoricals.items():
        rendered_values = ", ".join(f"'{value}'" for value in values)
        lines.append(f"  legal `{column}` values: {rendered_values}")
    for gotcha in table.gotchas:
        lines.append(f"  - {gotcha}")
    if table.default_filters:
        lines.append(f"  default filters: {'; '.join(table.default_filters)}")
    important_columns = [spec for spec in table.columns if spec.important]
    if important_columns:
        lines.append("  key columns:")
        for important_column in important_columns:
            lines.append(f"    - {important_column.name} ({important_column.type}): {important_column.description}")
    lines.append("  all columns: " + ", ".join(spec.name for spec in table.columns))
    return "\n".join(lines)


def render_domain(domain: str) -> str:
    """Render every table in one domain."""
    return "\n\n".join(render_table(table) for table in tables_for_domains((domain,)))


def render_tables(domains: Iterable[str]) -> str:
    """Render the tables for several domains in one prompt section."""
    return "\n\n".join(render_table(table) for table in tables_for_domains(domains))


def column_names(table_name: str) -> Tuple[str, ...]:
    """Column names the catalog claims for a table."""
    table = TABLES.get(table_name)
    if table is None:
        return ()
    return tuple(column.name for column in table.columns)
