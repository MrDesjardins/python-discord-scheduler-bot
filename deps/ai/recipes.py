"""
Deterministic SQL recipes for the most common stats questions.

These bypass free-form SQL generation for question shapes where the correct query is
known. That removes a class of casing/schema mistakes and avoids an extra planner call.

The recipes intentionally cover only clear, high-traffic shapes (operator leaderboards
and core leaderboards). Everything else keeps using the catalog-driven SQL path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple

from deps.operator_mapping import ATTACKER_OPERATORS, DEFENDER_OPERATORS

_OPERATORS = tuple(sorted(ATTACKER_OPERATORS | DEFENDER_OPERATORS, key=len, reverse=True))

# Names whose database spelling differs from the ASCII token used in questions.
_OPERATOR_ALIASES = {
    "capitao": "Capitão",
    "jager": "Jäger",
    "nokk": "Nøkk",
    "nomad": "Nomad",
}

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

DateRange = Tuple[date, date]


@dataclass(frozen=True)
class RecipeResult:
    """A deterministic SQL answer plus whether the metric is exact."""

    name: str
    sql: str
    exact: bool
    note: str = ""


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _add_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def _parse_limit(message: str) -> int:
    match = re.search(r"\b(?:top|limit)\s+(\d{1,3})\b", message)
    if not match:
        return 10
    return max(1, min(100, int(match.group(1))))


def _parse_date_range(message: str, today: date) -> Optional[DateRange]:
    """Parse the common date shapes; return [start, end) or None for lifetime."""
    iso_range = re.search(
        r"(\d{4}-\d{1,2}-\d{1,2})\s*(?:to|until|through|-)\s*(\d{4}-\d{1,2}-\d{1,2})",
        message,
    )
    if iso_range:
        start = date.fromisoformat(iso_range.group(1))
        end = date.fromisoformat(iso_range.group(2)) + timedelta(days=1)
        return (start, end)

    year_match = re.search(r"\b(20\d{2})\b", message)
    if year_match:
        year = int(year_match.group(1))
        return (date(year, 1, 1), date(year + 1, 1, 1))

    month_match = re.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})\b",
        message,
    )
    if month_match:
        month = _MONTHS[month_match.group(1)]
        year = int(month_match.group(2))
        start = date(year, month, 1)
        return (start, _add_month(start))

    relative = re.search(r"\blast\s+(\d{1,2})\s+(day|week|month)s?\b", message)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        if unit == "day":
            delta = timedelta(days=amount)
        elif unit == "week":
            delta = timedelta(weeks=amount)
        else:
            delta = timedelta(days=30 * amount)
        return (today - delta, today + timedelta(days=1))

    if re.search(r"\bthis\s+month\b", message):
        return (date(today.year, today.month, 1), today + timedelta(days=1))
    if re.search(r"\blast\s+month\b", message):
        start = date(today.year, today.month, 1)
        previous_end = start
        previous_start = date(start.year - 1, 12, 1) if start.month == 1 else date(start.year, start.month - 1, 1)
        return (previous_start, previous_end)
    if re.search(r"\bthis\s+year\b", message):
        return (date(today.year, 1, 1), today + timedelta(days=1))
    if re.search(r"\blast\s+year\b", message):
        return (date(today.year - 1, 1, 1), date(today.year, 1, 1))
    return None


def _parse_session(message: str) -> Optional[str]:
    if re.search(r"\branked\b", message):
        return "Ranked"
    if re.search(r"\b(standard|casual|quick\s*match|quickmatch)\b", message):
        return "Standard"
    return None


def _find_operator(question: str) -> Optional[str]:
    folded = question.casefold()
    for name in _OPERATORS:
        if re.search(rf"(?<!\w){re.escape(name.casefold())}(?!\w)", folded):
            return _OPERATOR_ALIASES.get(name.casefold(), name)
    return None


def _looks_like_leaderboard(message: str) -> bool:
    return bool(re.search(r"\b(top|leaderboard|most|best|ranking|ranked\s+list)\b", message))


def _parse_metric(message: str) -> Optional[str]:
    if re.search(r"\bvoice\b|\bvc\b|time\s+(?:in|on)\s+voice|hours?\s+(?:in|on)\s+voice", message):
        return "voice_time"
    if re.search(r"\b(win\s*rate|winrate|win\s*percentage)\b", message):
        return "win_rate"
    if re.search(r"(?<!\w)k\s*/?\s*d(?!\w)|kill.?.?death\s*ratio", message):
        return "kd"
    if re.search(r"\bteam\s*kills?\b|\btk\b", message):
        return "team_kills"
    if re.search(r"\baces?\b", message):
        return "aces"
    if re.search(r"\bclutch", message):
        return "clutches_won"
    if re.search(r"\bfirst\s*kills?\b", message):
        return "first_kills"
    if re.search(r"\bfirst\s*deaths?\b", message):
        return "first_deaths"
    if re.search(r"\b(matches|games)\s+played\b|\bmost\s+(matches|games)\b", message):
        return "matches_played"
    if re.search(r"\bwins?\b", message):
        return "wins"
    return None


def _date_filter(column: str, date_range: Optional[DateRange]) -> str:
    if not date_range:
        return ""
    start, end = date_range
    return f" AND {column} >= '{start.isoformat()}' AND {column} < '{end.isoformat()}'"


def _session_filter(column: str, session: Optional[str]) -> str:
    if not session:
        return ""
    return f" AND LOWER({column}) = '{session.casefold()}'"


def _operator_match_sql(operator: str) -> str:
    return f"',' || LOWER(m.operators) || ',' LIKE '%,{operator.casefold()},%'"


def _operator_sql(operator: str, date_range: Optional[DateRange], session: Optional[str], limit: int) -> RecipeResult:
    if date_range is None and session in (None, "Ranked"):
        # Exact lifetime totals come from the per-operator snapshot.
        sql = (
            "SELECT COALESCE(ui.ubisoft_username_active, ui.ubisoft_username_max) AS player, "
            "SUM(o.rounds_played) AS rounds, SUM(o.matches_played) AS matches "
            "FROM operator_stats o "
            "JOIN user_info ui ON ui.id = o.user_id "
            f"WHERE LOWER(o.operator_name) = '{operator.casefold()}' "
            "AND LOWER(o.session_type) = 'ranked' AND o.gamemode = 'pvp_ranked' "
            "GROUP BY o.user_id ORDER BY rounds DESC "
            f"LIMIT {limit}"
        )
        return RecipeResult(
            name="operator_lifetime",
            sql=sql,
            exact=True,
            note=(
                "These are exact lifetime per-operator totals from the R6 Tracker snapshot; "
                "the snapshot has no date dimension."
            ),
        )

    where = f"m.is_rollback = 0 AND {_operator_match_sql(operator)}"
    where += _date_filter("m.match_timestamp", date_range)
    where += _session_filter("m.session_type", session)
    sql = (
        "SELECT COALESCE(ui.ubisoft_username_active, ui.ubisoft_username_max) AS player, "
        "SUM(m.round_played_count) AS rounds_in_matches_with_operator, COUNT(*) AS matches "
        "FROM user_full_match_info m "
        "JOIN user_info ui ON ui.id = m.user_id "
        f"WHERE {where} "
        "GROUP BY m.user_id ORDER BY rounds_in_matches_with_operator DESC "
        f"LIMIT {limit}"
    )
    return RecipeResult(
        name="operator_date_scoped",
        sql=sql,
        exact=False,
        note=(
            "Per-operator rounds are not stored per date in this table. This counts the full "
            "rounds of each match in which the operator appears, so it is an upper-bound estimate."
        ),
    )


def _voice_time_sql(date_range: Optional[DateRange], guild_id: Optional[int], limit: int) -> RecipeResult:
    guild_filter = f" AND c.guild_id = {int(guild_id)}" if guild_id is not None else ""
    date_filter = _date_filter("c.timestamp", date_range)
    sql = (
        "SELECT COALESCE(ui.ubisoft_username_active, ui.ubisoft_username_max) AS player, "
        "ROUND(SUM((julianday(d.timestamp) - julianday(c.timestamp)) * 86400.0), 0) AS voice_seconds "
        "FROM user_activity c "
        "JOIN user_activity d ON d.user_id = c.user_id AND d.channel_id = c.channel_id "
        "AND d.guild_id = c.guild_id AND d.event = 'disconnect' AND d.timestamp = ("
        "SELECT MIN(d2.timestamp) FROM user_activity d2 "
        "WHERE d2.user_id = c.user_id AND d2.channel_id = c.channel_id "
        "AND d2.guild_id = c.guild_id "
        "AND d2.event = 'disconnect' AND d2.timestamp > c.timestamp) "
        "JOIN user_info ui ON ui.id = c.user_id "
        f"WHERE c.event = 'connect'{guild_filter}{date_filter} "
        "GROUP BY c.user_id ORDER BY voice_seconds DESC "
        f"LIMIT {limit}"
    )
    return RecipeResult(
        name="leaderboard_voice_time",
        sql=sql,
        exact=False,
        note=(
            "Voice time is paired from connect/disconnect events; a connect without a "
            "matching disconnect is not counted."
        ),
    )


def _leaderboard_sql(metric: str, date_range: Optional[DateRange], session: Optional[str], limit: int) -> RecipeResult:
    expressions = {
        "matches_played": "COUNT(*)",
        "wins": "SUM(m.has_win)",
        "win_rate": "ROUND(100.0 * SUM(m.has_win) / COUNT(*), 1)",
        "kd": "ROUND(SUM(m.kill_count) * 1.0 / NULLIF(SUM(m.death_count), 0), 2)",
        "team_kills": "SUM(m.tk_count)",
        "aces": "SUM(m.ace_count)",
        "clutches_won": "SUM(m.clutches_win_count)",
        "first_kills": "SUM(m.first_kill_count)",
        "first_deaths": "SUM(m.first_death_count)",
    }
    expression = expressions[metric]
    where = "m.is_rollback = 0"
    where += _date_filter("m.match_timestamp", date_range)
    where += _session_filter("m.session_type", session)
    having = " HAVING SUM(m.death_count) > 0" if metric == "kd" else ""
    sql = (
        "SELECT COALESCE(ui.ubisoft_username_active, ui.ubisoft_username_max) AS player, "
        f"{expression} AS {metric} "
        "FROM user_full_match_info m "
        "JOIN user_info ui ON ui.id = m.user_id "
        f"WHERE {where} GROUP BY m.user_id{having} ORDER BY {metric} DESC "
        f"LIMIT {limit}"
    )
    return RecipeResult(
        name=f"leaderboard_{metric}",
        sql=sql,
        exact=True,
        note="Aggregate over recorded matches, excluding rollbacks.",
    )


def try_build_recipe(
    question: str,
    requester_id: int,
    resolved_users: Optional[list] = None,
    today: Optional[date] = None,
    guild_id: Optional[int] = None,
) -> Optional[RecipeResult]:
    """
    Return a deterministic recipe for a clearly recognized question shape, else None.

    ``resolved_users`` disables recipes: when the user explicitly mentions players, the
    identity constraints are better handled by the normal planner/SQL path.
    """
    if resolved_users:
        return None
    message = question.casefold()
    today = today or _today()
    limit = _parse_limit(message)
    date_range = _parse_date_range(message, today)
    session = _parse_session(message)

    # Only global leaderboard phrasing uses the operator recipe. A personal question
    # ("how many rounds did I play as Doc?") must go through the normal SQL path so the
    # requester's user_id and the date range are honored.
    operator = _find_operator(question)
    if operator is not None and _looks_like_leaderboard(message):
        return _operator_sql(operator, date_range, session, limit)

    metric = _parse_metric(message)
    if metric is not None and _looks_like_leaderboard(message):
        if metric == "voice_time":
            return _voice_time_sql(date_range, guild_id, limit)
        return _leaderboard_sql(metric, date_range, session, limit)

    return None
