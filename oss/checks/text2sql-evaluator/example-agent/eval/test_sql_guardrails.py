"""Deterministic SQL guardrail tests (no LLM, no API key)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.sql_tools import validate_sql  # noqa: E402


def test_blocks_destructive_queries() -> None:
    blocked = [
        'DELETE FROM "User"',
        'DROP TABLE "User"',
        'INSERT INTO "User" ("email") VALUES (\'x@y.com\')',
        'UPDATE "User" SET "email" = \'a@b.com\'',
    ]
    for sql in blocked:
        result = validate_sql(sql)
        assert not result.valid, sql


def test_blocks_unsafe_select() -> None:
    assert not validate_sql('SELECT * FROM "User"').valid
    assert not validate_sql('SELECT 1; SELECT 2').valid
    assert not validate_sql('SELECT COUNT(*) FROM "User"; DROP TABLE "User"').valid


def test_allows_safe_select() -> None:
    allowed = [
        'SELECT COUNT(*) FROM "User"',
        'SELECT * FROM "User" LIMIT 5',
        'WITH cte AS (SELECT 1 AS n) SELECT n FROM cte LIMIT 1',
    ]
    for sql in allowed:
        assert validate_sql(sql).valid, sql


if __name__ == "__main__":
    test_blocks_destructive_queries()
    test_blocks_unsafe_select()
    test_allows_safe_select()
    print("All guardrail tests passed.")
