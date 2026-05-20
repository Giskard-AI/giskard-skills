"""Unit tests for eval.check_helpers (no API key)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.check_helpers import (  # noqa: E402
    non_tool_before_data_query,
    parse_first_integer,
)


def _interaction(queries: list[dict] | None) -> Any:
    return SimpleNamespace(outputs={"queries": queries or []})


def _trace(interactions: list[Any]) -> Any:
    return SimpleNamespace(interactions=interactions)


def test_parse_first_integer_plain() -> None:
    assert parse_first_integer("There are 3 users.") == 3


def test_parse_first_integer_with_commas() -> None:
    assert parse_first_integer("Total revenue is 17,000 cents.") == 17000


def test_parse_first_integer_none() -> None:
    assert parse_first_integer("no numbers here") is None


def test_non_tool_before_data_query_true() -> None:
    trace = _trace(
        [
            _interaction([]),
            _interaction([{"sql": "SELECT 1", "success": True}]),
        ]
    )
    assert non_tool_before_data_query(trace) is True


def test_non_tool_before_data_query_false_when_first_has_query() -> None:
    trace = _trace(
        [
            _interaction([{"sql": "SELECT 1", "success": True}]),
            _interaction([]),
        ]
    )
    assert non_tool_before_data_query(trace) is False


def test_non_tool_before_data_query_false_all_empty() -> None:
    trace = _trace([_interaction([]), _interaction([])])
    assert non_tool_before_data_query(trace) is False
