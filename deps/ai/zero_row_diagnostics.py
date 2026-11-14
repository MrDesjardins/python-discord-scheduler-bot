"""
Diagnose a statistics query that returned no rows.

When a generated query returns nothing, the old recovery path asked a generic
clarifying question and the model often invented a reason ("I cannot access 2026
yet"). This module locates which WHERE predicate removed the data and reports the
result to the model, so it can correct the query or state a real limitation.

The parser is intentionally small: it handles the flat SELECT ... FROM ... WHERE
shapes the bot generates. Anything else falls back to a coverage fact only.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from deps.ai import data_catalog

_WHERE_END = re.compile(r"\b(group\s+by|order\s+by|limit|having|window)\b", re.IGNORECASE)
_FROM_END = re.compile(r"\b(where|group\s+by|order\s+by|limit|having|window)\b", re.IGNORECASE)


def _split_top_level_and(where_clause: str) -> List[str]:
    """Split a WHERE clause on AND at paren depth zero, ignoring quoted strings."""
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    quote: Optional[str] = None
    index = 0
    while index < len(where_clause):
        char = where_clause[index]
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            index += 1
            continue
        if char == "(":
            depth += 1
            current.append(char)
            index += 1
            continue
        if char == ")":
            depth = max(0, depth - 1)
            current.append(char)
            index += 1
            continue
        if depth == 0:
            match = re.match(r"(?i)\band\b", where_clause[index:])
            if match:
                parts.append("".join(current).strip())
                current = []
                index += len(match.group(0))
                continue
        current.append(char)
        index += 1
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return [part for part in parts if part]


def _extract_from_and_where(sql: str) -> Optional[Tuple[str, str]]:
    """Return (from_clause, where_clause) for a flat query, or None."""
    from_match = re.search(r"(?is)\bfrom\b", sql)
    if not from_match:
        return None
    after_from = sql[from_match.end() :]
    boundary = _FROM_END.search(after_from)
    if boundary and boundary.group(1).casefold().startswith("where"):
        from_clause = after_from[: boundary.start()]
        where_start = from_match.end() + boundary.end()
        after_where = sql[where_start:]
        end = _WHERE_END.search(after_where)
        where_clause = after_where[: end.start()] if end else after_where
        return from_clause.strip(), where_clause.strip().rstrip(";")
    if boundary:
        return after_from[: boundary.start()].strip(), ""
    return after_from.strip().rstrip(";"), ""


def _run_count(query: str) -> Optional[int]:
    """Run one bounded COUNT query; return None when it cannot be executed."""
    try:
        if not re.match(r"(?is)^\s*select\b", query):
            return None
        from deps.system_database import database_manager

        row = database_manager.get_cursor().execute(query).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return None


def _coverage_line() -> str:
    earliest, latest = data_catalog.get_coverage()
    if earliest and latest:
        return f"Recorded match coverage: {str(earliest)[:10]} to {str(latest)[:10]} (UTC)."
    return "Recorded match coverage is unavailable."


def diagnose_zero_rows(sql: str) -> str:
    """
    Build a factual diagnosis for an empty result set.

    The returned string is safe to put in a prompt: it contains only row counts and
    the predicates that were removed, never user data.
    """
    cleaned = sql.strip().replace("```sql", "").replace("```", "").strip().rstrip(";")
    coverage = _coverage_line()
    if not re.match(r"(?is)^\s*(select|with)\b", cleaned):
        return coverage
    # Nested SELECTs (subqueries/CTEs) have more than one FROM/WHERE scope. The
    # predicate ladder below only understands a flat query, so do not guess.
    if len(re.findall(r"(?i)\bselect\b", cleaned)) > 1:
        return coverage + " No filter-level diagnosis is available for this query shape."

    extracted = _extract_from_and_where(cleaned)
    if extracted is None:
        return coverage + " No filter-level diagnosis is available for this query shape."

    from_clause, where_clause = extracted
    if not from_clause:
        return coverage

    predicates = _split_top_level_and(where_clause) if where_clause else []
    full_count = _run_count(f"SELECT COUNT(*) FROM {from_clause}" + (f" WHERE {where_clause}" if where_clause else ""))
    if full_count is None:
        return coverage + " Could not re-run the query to diagnose the empty result."

    lines = [f"The previous query returned {full_count} rows.", coverage]
    if predicates:
        lines.append("Rows with one filter removed (to identify which filter hid the data):")
        for index, predicate in enumerate(predicates):
            remaining = predicates[:index] + predicates[index + 1 :]
            query = f"SELECT COUNT(*) FROM {from_clause}"
            if remaining:
                query += " WHERE " + " AND ".join(remaining)
            count = _run_count(query)
            if count is not None:
                lines.append(f"- without `{predicate}`: {count} rows")
    else:
        lines.append("The query had no WHERE filters, so the table itself is empty for this shape.")
    return "\n".join(lines)
