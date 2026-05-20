"""Database schema introspection for agent prompts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.sql_tools import ensure_database


def fetch_schema_text(db_path: Path | None = None) -> str:
    """Build a markdown schema summary for the system prompt.

    Args:
        db_path: Optional database path override.

    Returns:
        Formatted schema description including tables and foreign keys.
    """
    path = ensure_database(db_path)
    with sqlite3.connect(path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        lines = ["## Database schema", ""]
        for (table_name,) in tables:
            columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            lines.append(f'### Table: "{table_name}"')
            lines.append("Columns:")
            for col in columns:
                cid, name, col_type, notnull, default, pk = col
                flags: list[str] = [col_type]
                if pk:
                    flags.append("PK")
                if not notnull:
                    flags.append("nullable")
                lines.append(f'  - "{name}" ({", ".join(flags)})')
            lines.append("")
        fk_lines: list[str] = []
        for (table_name,) in tables:
            for fk in conn.execute(f'PRAGMA foreign_key_list("{table_name}")'):
                fk_lines.append(
                    f'  - "{table_name}"."{fk[3]}" → "{fk[2]}"."{fk[4]}"'
                )
        if fk_lines:
            lines.append("### Foreign keys")
            lines.extend(fk_lines)
            lines.append("")
    return "\n".join(lines)


def default_system_prompt(db_path: Path | None = None) -> str:
    """Return the system prompt for the reference analytics agent.

    Args:
        db_path: Optional database path override.

    Returns:
        System prompt string including embedded schema.
    """
    schema = fetch_schema_text(db_path)
    return f"""You are a data analytics agent that answers questions by querying a SQLite database.

## Rules

1. Always use the execute_query tool for factual questions. Never invent counts or rows.
2. Only read-only SELECT queries are allowed. If a query is blocked, explain the error briefly.
3. Double-quote table and column names (e.g. "User", "firstName").
4. Include LIMIT on non-aggregate SELECT queries.
5. Do not give the user SQL to run elsewhere when a query fails.
6. For ambiguous metrics (active, real users, revenue), state the filter or definition you applied
   (e.g. `"isActive" = 1`, excluding test accounts, completed orders only) in the same answer as the number.

{schema}
"""
