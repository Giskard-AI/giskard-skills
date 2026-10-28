#!/usr/bin/env python3
"""Offline QA self-test for hub-agent-setup/scripts/tool_mocks.py (PR #22)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hub/hub-agent-setup/scripts"))

from tool_mocks import ToolHarness, ToolMockError, build_input_schema, validate_mocks  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        failures.append(f"{name}: {detail}" if detail else name)


def test_static_and_fallback() -> None:
    harness = ToolHarness(
        {"t": {"returns": 1}},
        {"t": lambda **k: 99, "other": lambda **k: "real"},
    )
    assert harness.call("t", {}) == 1
    assert harness.call("other", {}) == "real"
    assert harness.calls[0]["mocked"] is True
    assert harness.calls[1]["mocked"] is False


def test_when_and_number_string() -> None:
    harness = ToolHarness(
        {"calc": [{"when": {"n": 102}, "returns": "a"}, {"returns": "b"}]},
        {"calc": lambda **k: "default"},
    )
    check("when int", harness.call("calc", {"n": 102}) == "a")
    check("when str", harness.call("calc", {"n": "102"}) == "a")
    check("when miss", harness.call("calc", {"n": 1}) == "b")
    harness2 = ToolHarness(
        {"f": {"when": {"flag": True}, "returns": "yes"}},
        {"f": lambda **k: "no"},
    )
    check("true not 1", harness2.call("f", {"flag": 1}) == "no")


def test_when_null_omitted() -> None:
    harness = ToolHarness(
        {"t": {"when": {"x": None}, "returns": "hit"}},
        {"t": lambda **k: "miss"},
    )
    check("null matches omitted", harness.call("t", {}) == "hit")


def test_sequence_repeats() -> None:
    harness = ToolHarness(
        {"t": {"sequence": [{"returns": 1}, {"returns": 2}]}},
        {"t": lambda **k: 0},
    )
    check("seq1", harness.call("t", {}) == 1)
    check("seq2", harness.call("t", {}) == 2)
    check("seq3 repeat", harness.call("t", {}) == 2)


def test_error_raise_and_return() -> None:
    h_raise = ToolHarness({"t": {"error": {"message": "boom", "type": "E"}}}, {"t": lambda **k: 1})
    try:
        h_raise.call("t", {})
        check("error raises", False, "expected ToolMockError")
    except ToolMockError as exc:
        check("error type", exc.error_type == "E")

    h_ret = ToolHarness(
        {"t": {"error": {"message": "boom"}}},
        {"t": lambda **k: 1},
        raise_errors=False,
    )
    out = h_ret.call("t", {})
    check("error result", out == {"error": "boom"})
    check("record error", "error" in h_ret.calls[0])


def test_unknown_tool_raise_errors_false() -> None:
    h = ToolHarness(None, {"known": lambda **k: 1}, raise_errors=False)
    out = h.call("missing", {})
    check("unknown tool", out == {"error": "unknown tool missing"})


def test_fake_exception_raise_errors_false() -> None:
    h = ToolHarness(None, {"t": lambda **k: (_ for _ in ()).throw(ValueError("bad"))}, raise_errors=False)
    out = h.call("t", {})
    check("fake exc", "error" in out and "ValueError" in out["error"])


def test_deepcopy_mutation() -> None:
    shared = {"items": [1]}
    h = ToolHarness({"t": {"returns": shared}}, {"t": lambda **k: {}})
    r1 = h.call("t", {})
    r1["items"].append(2)
    r2 = h.call("t", {})
    check("deepcopy", r2["items"] == [1])


def test_validate_unknown_tool_and_typo_keys() -> None:
    try:
        validate_mocks({"bad": {"returns": 1}}, {"good"})
        check("unknown tool", False)
    except ValueError as e:
        check("unknown tool msg", "unknown tools" in str(e))

    try:
        validate_mocks({"t": {"whne": {}, "returns": 1}}, {"t"})
        check("typo key", False)
    except ValueError as e:
        check("typo key msg", "unknown keys" in str(e))

    try:
        validate_mocks({"t": {"when": {"x": 1}, "returns": 1}}, {"t"}, parameters={"t": {"y"}})
        check("unknown when arg", False)
    except ValueError as e:
        check("unknown when arg msg", "unknown arguments" in str(e))


def test_build_input_schema() -> None:
    schema = build_input_schema(
        {"get_x": {"description": "read x", "parameters": {"type": "object", "properties": {"id": {"type": "string"}}}}}
    )
    check("inputs required", schema["required"] == ["inputs"])
    check("mocks props", "get_x" in schema["properties"]["mocks"]["properties"])
    check("no extra mocks", schema["properties"]["mocks"]["additionalProperties"] is False)


def main() -> int:
    test_static_and_fallback()
    test_when_and_number_string()
    test_when_null_omitted()
    test_sequence_repeats()
    test_error_raise_and_return()
    test_unknown_tool_raise_errors_false()
    test_fake_exception_raise_errors_false()
    test_deepcopy_mutation()
    test_validate_unknown_tool_and_typo_keys()
    test_build_input_schema()
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("tool_mocks self-test: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
