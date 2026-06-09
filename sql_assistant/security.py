"""
security.py — SQL Safety & Validation Layer
─────────────────────────────────────────────
Validates generated SQL queries before execution.
Only allows safe read-only SELECT / WITH (CTE) statements.
"""

import re
import logging
from dataclasses import dataclass
from typing import Tuple

logger = logging.getLogger(__name__)

# ── Blocked keywords (case-insensitive word-boundary match) ──────────────────
BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "EXEC", "EXECUTE", "MERGE", "GRANT", "REVOKE",
    "BULK", "OPENROWSET", "OPENQUERY", "RESTORE", "BACKUP",
    "SHUTDOWN", "KILL", "WAITFOR", "XP_", "SP_",
]

# ── Allowed statement starters ───────────────────────────────────────────────
ALLOWED_STARTERS = ["SELECT", "WITH"]


@dataclass
class ValidationResult:
    is_safe: bool
    message: str
    cleaned_query: str = ""


def _strip_comments(sql: str) -> str:
    """Remove SQL comments (-- and /* */ style)."""
    # Remove block comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Remove line comments
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _normalize(sql: str) -> str:
    """Collapse whitespace."""
    return " ".join(sql.split())


def validate_sql(sql: str) -> ValidationResult:
    """
    Full validation pipeline for a generated SQL query.

    Returns a ValidationResult with:
        is_safe      — True if the query can be executed
        message      — Human-readable verdict / error
        cleaned_query — Stripped & normalised query (only populated if safe)
    """
    if not sql or not sql.strip():
        return ValidationResult(False, "Empty query received.")

    # 1. Strip comments so they can't be used to hide keywords
    stripped = _strip_comments(sql)
    normalised = _normalize(stripped)

    # 2. Reject multiple statements (semi-colon separated)
    statements = [s.strip() for s in normalised.split(";") if s.strip()]
    if len(statements) > 1:
        logger.warning("Multiple statements detected — blocked.")
        return ValidationResult(
            False,
            "❌ Multiple SQL statements are not allowed for security reasons.",
        )

    query = statements[0]

    # 3. Check it starts with an allowed keyword
    first_token = query.split()[0].upper() if query.split() else ""
    if first_token not in ALLOWED_STARTERS:
        logger.warning("Query starts with disallowed keyword: %s", first_token)
        return ValidationResult(
            False,
            f"❌ Only SELECT and WITH (CTE) queries are allowed. "
            f"Your query starts with **{first_token}**.",
        )

    # 4. Scan for blocked keywords as whole words
    upper_query = query.upper()
    for kw in BLOCKED_KEYWORDS:
        # Use word-boundary regex for exact word match
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, upper_query):
            logger.warning("Blocked keyword found: %s", kw)
            return ValidationResult(
                False,
                f"❌ Blocked keyword detected: **{kw}**. "
                "Only read-only SELECT queries are permitted.",
            )

    logger.info("SQL validation passed.")
    return ValidationResult(True, "✅ Query is safe to execute.", query)


def sanitize_identifier(name: str) -> str:
    """
    Sanitize a table/column name to prevent injection
    when building dynamic SQL strings.
    """
    # Allow only alphanumeric, underscore, and dot (schema.table)
    clean = re.sub(r"[^\w.]", "", name)
    return clean
