"""SQL validation and execution for the reference analytics agent."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "analytics.db"
INIT_SQL_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "init_db.sql"


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of SQL static validation."""

    valid: bool
    error: str | None = None


@dataclass(frozen=True)
class QueryResult:
    """Outcome of executing a validated query."""

    success: bool
    sql: str
    rows: list[dict[str, Any]] | None = None
    row_count: int | None = None
    fields: list[str] | None = None
    error: str | None = None
    blocked: bool = False


def validate_sql(sql: str) -> ValidationResult:
    """Validate that SQL is a safe read-only analytics query.

    Args:
        sql: Raw SQL string from the agent or a test case.

    Returns:
        ValidationResult with valid=True when the query may run.

    Example:
        >>> validate_sql('SELECT COUNT(*) FROM "User"').valid
        True
        >>> validate_sql('DELETE FROM "User"').valid
        False
    """
    normalized = sql.strip().lower()
    if not normalized.startswith("select") and not normalized.startswith("with"):
        return ValidationResult(valid=False, error="Only SELECT queries are allowed")

    dangerous_keywords = [
        "insert",
        "update",
        "delete",
        "drop",
        "truncate",
        "alter",
        "create",
        "replace",
        "grant",
        "revoke",
        "attach",
        "detach",
    ]
    for keyword in dangerous_keywords:
        if re.search(rf"\b{keyword}\b", normalized):
            return ValidationResult(
                valid=False,
                error=f"Forbidden keyword detected: {keyword.upper()}",
            )

    dangerous_functions = ["pg_sleep", "readfile", "writefile"]
    for func in dangerous_functions:
        if re.search(rf"\b{func}\s*\(", normalized):
            return ValidationResult(
                valid=False,
                error=f"Forbidden function detected: {func}",
            )

    without_trailing = normalized.rstrip().rstrip(";")
    if ";" in without_trailing:
        return ValidationResult(valid=False, error="Multiple SQL statements are not allowed")

    is_aggregate = re.search(r"\b(count|sum|avg|min|max|group\s+by)\b", normalized)
    has_limit = re.search(r"\blimit\s+\d+", normalized)
    if not is_aggregate and not has_limit:
        return ValidationResult(
            valid=False,
            error="Non-aggregate queries must include a LIMIT clause for safety.",
        )

    return ValidationResult(valid=True)


def ensure_database(db_path: Path | None = None) -> Path:
    """Create the SQLite database from seed SQL if missing.

    Args:
        db_path: Optional override for database file location.

    Returns:
        Path to the SQLite database file.
    """
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    script = INIT_SQL_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(path) as conn:
        conn.executescript(script)
    return path


def execute_query(sql: str, db_path: Path | None = None) -> QueryResult:
    """Validate and run a SELECT query against the sample database.

    Args:
        sql: SQL to execute.
        db_path: Optional database path override.

    Returns:
        QueryResult with rows on success or error metadata on failure.
    """
    validation = validate_sql(sql)
    if not validation.valid:
        return QueryResult(
            success=False,
            sql=sql,
            error=validation.error,
            blocked=True,
        )

    path = ensure_database(db_path)
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            rows = [dict(row) for row in cursor.fetchall()]
            fields = [description[0] for description in cursor.description or []]
            return QueryResult(
                success=True,
                sql=sql,
                rows=rows,
                row_count=len(rows),
                fields=fields,
            )
    except sqlite3.Error as exc:
        return QueryResult(success=False, sql=sql, error=str(exc))


EXECUTE_QUERY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_query",
        "description": (
            "Execute a read-only SQL query on the analytics SQLite database. "
            'Only SELECT is allowed. Quote table and column names with double quotes '
            '(e.g. SELECT * FROM "User" LIMIT 10). Non-aggregate queries must include LIMIT.'
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The SQL query to execute"},
            },
            "required": ["sql"],
        },
    },
}
