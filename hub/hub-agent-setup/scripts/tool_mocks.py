"""Resolve the `mocks` part of a `{"inputs": ..., "mocks": {...}}` request.

Copy this file next to the wrapper. It uses only the standard library.
See references/triggered-agents.md for the request format and how to wire it.

Each tool maps to an ordered list of rules (a single rule object is accepted
as shorthand). The first rule whose `when` matches the call arguments wins:

    {"returns": <value>}                          # static
    {"when": {"invoice_id": "INV-2"}, "returns": <value>}   # conditional
    {"sequence": [{"returns": <a>}, {"error": {...}}]}      # per call, last repeats
    {"error": {"message": "ERP timeout", "type": "TimeoutError"}}

A call that matches no rule, or a tool absent from `mocks`, runs the agent's
default fake.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping
from typing import Any

_OUTCOME_KEYS = ("returns", "error")
_RULE_KEYS = ("returns", "error", "sequence")


class ToolMockError(RuntimeError):
    """Raised inside the tool layer when an `error` mock is selected."""

    def __init__(self, message: str, error_type: str | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type


def _check_outcome(item: Any, where: str, keys: tuple[str, ...]) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"{where} must be an object")
    present = [k for k in keys if k in item]
    if len(present) != 1:
        raise ValueError(f"{where} needs exactly one of {', '.join(keys)}")
    if "error" in item:
        error = item["error"]
        if not isinstance(error, dict) or not isinstance(error.get("message"), str):
            raise ValueError(f"{where}.error needs a string `message`")


def _json_safe(value: Any) -> Any:
    """Detached, JSON-typed copy (tuples become lists, unknown objects become str)."""
    return json.loads(json.dumps(value, default=str))


def validate_mocks(mocks: Any, tool_names: set[str]) -> dict[str, list[dict]]:
    """Return mocks normalised to `{tool: [rule, ...]}`; raise ValueError if invalid."""
    if mocks is None:
        return {}
    if not isinstance(mocks, dict):
        raise ValueError("`mocks` must be an object keyed by tool name")
    unknown = sorted(set(mocks) - tool_names)
    if unknown:
        raise ValueError(
            f"unknown tools in `mocks`: {unknown}; mockable tools: {sorted(tool_names)}"
        )
    normalised: dict[str, list[dict]] = {}
    for tool, rules in mocks.items():
        rules = rules if isinstance(rules, list) else [rules]
        normalised[tool] = []
        for i, rule in enumerate(rules):
            where = f"mocks.{tool}[{i}]"
            _check_outcome(rule, where, _RULE_KEYS)
            if "when" in rule:
                if not isinstance(rule["when"], dict):
                    raise ValueError(f"{where}.when must be an object of argument values")
                # Normalise once here; call arguments are normalised the same way.
                rule = {**rule, "when": _json_safe(rule["when"])}
            if "sequence" in rule:
                seq = rule["sequence"]
                if not isinstance(seq, list) or not seq:
                    raise ValueError(f"{where}.sequence must be a non-empty list")
                for j, item in enumerate(seq):
                    _check_outcome(item, f"{where}.sequence[{j}]", _OUTCOME_KEYS)
            normalised[tool].append(rule)
    return normalised


class ToolHarness:
    """Per-request tool layer: applies mocks, falls back to fakes, records calls.

    Create one instance per request. `tools` maps every tool name the agent can
    call to the default fake implementation, called as `fn(**arguments)`.
    With `raise_errors=False`, an `error` mock or a call to an unknown tool
    returns `{"error": message}` as the tool result instead of raising, for
    agents that crash on exceptions.
    """

    def __init__(
        self,
        mocks: Any,
        tools: Mapping[str, Callable[..., Any]],
        *,
        raise_errors: bool = True,
    ) -> None:
        self.tools = dict(tools)
        self.rules = validate_mocks(mocks, set(self.tools))
        self.raise_errors = raise_errors
        self.calls: list[dict[str, Any]] = []
        self._sequence_positions: dict[tuple[str, int], int] = {}

    def _select(self, name: str, args: dict[str, Any]) -> dict | None:
        for index, rule in enumerate(self.rules.get(name, [])):
            when = rule.get("when", {})
            if any(k not in args or args[k] != v for k, v in when.items()):
                continue
            if "sequence" not in rule:
                return rule
            position = self._sequence_positions.get((name, index), 0)
            self._sequence_positions[(name, index)] = position + 1
            return rule["sequence"][min(position, len(rule["sequence"]) - 1)]
        return None

    def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        args = args or {}
        record: dict[str, Any] = {"name": name, "arguments": _json_safe(args)}
        self.calls.append(record)
        outcome = self._select(name, record["arguments"])
        record["mocked"] = outcome is not None
        if outcome is None:
            if name not in self.tools:
                return self._fail(record, f"unknown tool {name}", KeyError(name))
            try:
                result = self.tools[name](**args)
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                raise
        elif "error" in outcome:
            error = outcome["error"]
            return self._fail(
                record, error["message"], ToolMockError(error["message"], error.get("type"))
            )
        else:
            result = copy.deepcopy(outcome["returns"])  # the agent may mutate it
        record["result"] = _json_safe(result)
        return result

    def _fail(self, record: dict[str, Any], message: str, exc: Exception) -> Any:
        record["error"] = message
        if self.raise_errors:
            raise exc
        return {"error": message}

    def wrap(self, name: str) -> Callable[..., Any]:
        """Return a drop-in callable for one tool, for DI or monkeypatching."""

        def tool(**kwargs: Any) -> Any:
            return self.call(name, kwargs)

        tool.__name__ = name
        return tool


def rules_schema(parameters: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """JSON Schema for one tool's rule (or rule list); `when` lists the tool's parameters."""
    when: dict[str, Any] = {"type": "object"}
    if parameters and parameters.get("properties"):
        when["properties"] = dict(parameters["properties"])
    error = {
        "type": "object",
        "properties": {"message": {"type": "string"}, "type": {"type": "string"}},
        "required": ["message"],
    }
    outcome = {"type": "object", "properties": {"returns": {}, "error": error}}
    rule = {
        "type": "object",
        "properties": {
            "when": when,
            "returns": {},
            "error": error,
            "sequence": {"type": "array", "items": outcome, "minItems": 1},
        },
    }
    # A single rule object is accepted as shorthand for a one-item list.
    return {"anyOf": [rule, {"type": "array", "items": rule}]}


def build_input_schema(
    tool_specs: Mapping[str, Mapping[str, Any]],
    inputs_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured input schema `{inputs, mocks}` with one `mocks` property per tool.

    `tool_specs` maps tool name to `{"description": str, "parameters": <JSON Schema>}`,
    for example taken from the agent's OpenAI-style tool definitions.
    """
    mock_properties = {}
    for name, spec in tool_specs.items():
        schema = rules_schema(spec.get("parameters"))
        schema["description"] = spec.get("description", "")
        mock_properties[name] = schema
    return {
        "type": "object",
        "properties": {
            "inputs": dict(inputs_schema or {"type": "string"}),
            "mocks": {"type": "object", "properties": mock_properties},
        },
        "required": ["inputs"],
    }
