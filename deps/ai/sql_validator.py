"""
Catalog-aware validation and normalization for model-generated SQL.

The validator is deliberately conservative: it repairs safe casing mistakes, rejects
statements that cannot mean what the user asked, and returns actionable feedback so
the model can regenerate instead of silently returning zero rows.
"""

from __future__ import annotations

import re
from typing import Iterable, Set

from deps.ai import data_catalog

KNOWN_SESSION_TYPES = {"ranked", "standard"}

DANGEROUS_KEYWORDS = re.compile(
    r"\b(pragma|attach|detach|insert|update|delete|drop|alter|create|truncate|vacuum|reindex)\b",
    re.IGNORECASE,
)
REPLACE_INTO = re.compile(r"\breplace\s+into\b", re.IGNORECASE)
TABLE_REF = re.compile(r"(?is)\b(?:from|join)\s+([`\"\[]?[A-Za-z_][\w.]*[`\"\]]?)")
CTE_NAME = re.compile(r"(?is)(?:\bwith\b|,)\s*([A-Za-z_]\w*)\s+as\s*\(")
# Capture an optional table alias (e.g. ``m.session_type``) and an optional existing
# LOWER(...) wrapper so normalization never produces invalid SQL like ``m.LOWER(...)``.
SESSION_EQUALS = re.compile(r"(?i)(?:lower\s*\(\s*)?(\w+\.)?session_type\s*\)?\s*=\s*'([^']+)'")
OPERATOR_NAME_EQUALS = re.compile(r"(?i)(?:lower\s*\(\s*)?(\w+\.)?operator_name\s*\)?\s*=\s*'([^']+)'")
BARE_OPERATOR_EQUALS = re.compile(r"(?is)\boperators\b\s*\)?\s*=\s*'[^']*'")
BARE_OPERATOR_IN = re.compile(r"(?is)\boperators\b\s*\)?\s+in\s*\(")
BARE_OPERATOR_LIKE = re.compile(r"(?is)\boperators\b\s*\)?\s+like\s+'[^']*'")


def clean_sql(sql: str) -> str:
    """Strip Markdown fences and surrounding whitespace."""
    return sql.strip().replace("```sql", "").replace("```", "").strip()


def _strip_identifier(identifier: str) -> str:
    return identifier.strip().strip('`"[]').split(".")[-1].strip('`"[]')


def extract_table_refs(sql: str) -> Set[str]:
    """All table names in FROM/JOIN clauses, excluding CTE names defined in the query."""
    refs = {_strip_identifier(match) for match in TABLE_REF.findall(sql)}
    cte_names = {match.casefold() for match in CTE_NAME.findall(sql)}
    return {ref for ref in refs if ref.casefold() not in cte_names}


def validate_read_only(sql: str) -> None:
    """Reject anything that is not a single read-only statement."""
    lowered = sql.casefold()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("AI generated a non-read-only SQL statement")
    if ";" in sql.rstrip(";"):
        raise ValueError("AI generated multiple SQL statements")
    if DANGEROUS_KEYWORDS.search(sql) or REPLACE_INTO.search(sql):
        raise ValueError("AI generated a SQL statement with a write or admin keyword")
    if lowered.startswith("with") and re.search(r"\b(insert|update|delete|replace)\b", lowered):
        raise ValueError("WITH queries may only contain a final SELECT")


def validate_table_allowlist(sql: str) -> None:
    """Reject tables outside the stats allowlist (archive/cache/market tables are private)."""
    refs = extract_table_refs(sql)
    unknown = sorted(ref for ref in refs if ref not in data_catalog.STATS_TABLE_ALLOWLIST)
    if unknown:
        raise ValueError("SQL references tables outside the allowed stats tables: " + ", ".join(unknown))


def normalize_casing(sql: str) -> str:
    """Repair the common casing traps instead of failing the user on them."""
    normalized = SESSION_EQUALS.sub(
        lambda match: f"LOWER({match.group(1) or ''}session_type) = '{match.group(2).casefold()}'",
        sql,
    )
    normalized = OPERATOR_NAME_EQUALS.sub(
        lambda match: f"LOWER({match.group(1) or ''}operator_name) = '{match.group(2).casefold()}'",
        normalized,
    )
    return normalized


def validate_categoricals(sql: str) -> None:
    """Reject a session_type literal the database does not contain."""
    for match in SESSION_EQUALS.finditer(sql):
        value = match.group(2).casefold()
        if value not in KNOWN_SESSION_TYPES:
            raise ValueError(
                f"Unknown session_type value {match.group(2)!r}. "
                "Use 'ranked' or 'standard' (compare with LOWER(session_type))."
            )


def validate_operator_filter(sql: str) -> None:
    """Require the delimiter-safe comma-list filter for the operators column."""
    if BARE_OPERATOR_EQUALS.search(sql) or BARE_OPERATOR_IN.search(sql):
        raise ValueError(
            "operators is a comma-separated list; filter it with "
            "',' || LOWER(operators) || ',' LIKE '%,<operator>,' instead of = or IN"
        )
    if BARE_OPERATOR_LIKE.search(sql):
        raise ValueError(
            "Filter operators with ',' || LOWER(operators) || ',' LIKE '%,<operator>,' "
            "so a partial name cannot match"
        )


def _is_aggregate(sql: str) -> bool:
    return bool(
        re.search(r"\b(count|sum|avg|min|max)\s*\(", sql, re.IGNORECASE)
        or re.search(r"\bgroup\s+by\b", sql, re.IGNORECASE)
    )


def validate_identity_rules(
    sql: str,
    resolved_users: Iterable,
    require_canonical_identity: bool,
    require_kd_semantics: bool,
) -> None:
    """Keep the existing identity and K/D guarantees."""
    lowered = sql.casefold()
    if require_canonical_identity:
        if "user_info" not in lowered:
            raise ValueError("Leaderboard/partner SQL must join user_info for canonical names")
        if "ubisoft_username_active" not in lowered and "ubisoft_username_max" not in lowered:
            raise ValueError("SQL must select a canonical Ubisoft username")
        if "display_name" in lowered:
            raise ValueError("SQL must not use Discord display_name as the answer identity")
    if require_kd_semantics and "999999" in lowered:
        raise ValueError("K/D SQL must not use an artificial zero-death K/D value")
    for user in resolved_users:
        display_name = (user.display_name or "").casefold()
        if display_name and re.search(rf"ubisoft_username\s*=\s*['\"]{re.escape(display_name)}['\"]", lowered):
            raise ValueError(f"AI used Discord display name {user.display_name!r} as a Ubisoft username")
        if ("user_full_match_info" in lowered or "user_info" in lowered) and str(user.id) not in sql:
            raise ValueError(f"AI query did not use resolved user_id {user.id} for {user.display_name!r}")


def validate_rollback_rule(sql: str, require_canonical_identity: bool) -> None:
    """
    Leaderboard aggregates over historical matches must exclude rollbacks.

    Scoped to canonical/leaderboard queries so a simple player lookup like
    ``SELECT * ... WHERE user_id = 1`` keeps working.
    """
    if not require_canonical_identity:
        return
    lowered = sql.casefold()
    if "user_full_match_info" not in lowered or not _is_aggregate(sql):
        return
    if "is_rollback" not in lowered:
        raise ValueError(
            "Aggregate/leaderboard SQL over user_full_match_info must exclude is_rollback rows " "with is_rollback = 0"
        )


def ensure_limit(sql: str, require_canonical_identity: bool) -> str:
    """Add a default LIMIT to leaderboard queries that forgot one."""
    if not require_canonical_identity:
        return sql
    if re.search(r"\blimit\b", sql, re.IGNORECASE):
        return sql
    return sql.rstrip(";").rstrip() + " LIMIT 50"


def validate_and_normalize(
    sql: str,
    resolved_users: Iterable,
    require_canonical_identity: bool = False,
    require_kd_semantics: bool = False,
) -> str:
    """Clean, repair safe issues, then reject unsafe or unsupported SQL."""
    cleaned = clean_sql(sql)
    validate_read_only(cleaned)
    validate_table_allowlist(cleaned)
    cleaned = normalize_casing(cleaned)
    validate_categoricals(cleaned)
    validate_operator_filter(cleaned)
    validate_identity_rules(cleaned, resolved_users, require_canonical_identity, require_kd_semantics)
    validate_rollback_rule(cleaned, require_canonical_identity)
    cleaned = ensure_limit(cleaned, require_canonical_identity)
    return cleaned
