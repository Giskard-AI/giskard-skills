"""Resolve the `mocks` part of a `{"trigger": ..., "mocks": {...}}` request.

Copy this file next to the wrapper. It uses only the standard library.
See references/triggered-agents.md for the request format and how to wire it.

Each tool maps to an ordered list of rules (a single rule object is accepted
as shorthand). The first rule whose `when` matches the call arguments wins:

    {"returns": <value>}                          # static
    {"when": {"invoice_id": "INV-2"}, "returns": <value>}   # conditional
    {"sequence": [{"returns": <a>}, {"error": {...}}]}      # per call, last repeats
    {"error": {"message": "ERP timeout", "type": "TimeoutError"}}

A call that matches no rule, or a tool absent from `mocks`, runs the agent's
default fake. `when` compares JSON values, except that a number and its decimal
string match (`102` == `"102"`, which models often send), and `null` also
matches an omitted argument.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable, Mapping
from typing import Any

_OUTCOME_KEYS = ("returns", "error")
_RULE_KEYS = ("returns", "error", "sequence")
_NUMBER = re.compile(r"-?\d+(\.\d+)?")


class ToolMockError(RuntimeError):
    """Raised inside the tool layer when an `error` mock is selected."""

    def __init__(self, message: str, error_type: str | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type


def _check_outcome(
    item: Any, where: str, keys: tuple[str, ...], allowed: tuple[str, ...]
) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"{where} must be an object")
    # A typo such as `whne` would otherwise turn a conditional rule unconditional.
    extra = sorted(set(item) - set(allowed))
    if extra:
        raise ValueError(f"{where} has unknown keys {extra}; allowed: {list(allowed)}")
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


def _scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and _NUMBER.fullmatch(value):
        return float(value)
    return value


def _matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, (dict, list)) or isinstance(actual, (dict, list)):
        return expected == actual
    a, b = _scalar(expected), _scalar(actual)
    return a == b and type(a) is type(b)  # keeps `true` distinct from `1`


def validate_mocks(
    mocks: Any,
    tool_names: set[str],
    parameters: Mapping[str, set[str]] | None = None,
) -> dict[str, list[dict]]:
    """Return mocks normalised to `{tool: [rule, ...]}`; raise ValueError if invalid.

    With `parameters` (tool name -> argument names), a `when` on an unknown
    argument is rejected instead of silently never matching.
    """
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
            _check_outcome(rule, where, _RULE_KEYS, ("when", *_RULE_KEYS))
            if "when" in rule:
                if not isinstance(rule["when"], dict):
                    raise ValueError(f"{where}.when must be an object of argument values")
                known = parameters.get(tool) if parameters else None
                unknown_args = sorted(set(rule["when"]) - set(known)) if known is not None else []
                if unknown_args:
                    raise ValueError(
                        f"{where}.when has unknown arguments {unknown_args}; "
                        f"{tool} takes {sorted(known)}"
                    )
                # Normalise once here; call arguments are normalised the same way.
                rule = {**rule, "when": _json_safe(rule["when"])}
            if "sequence" in rule:
                seq = rule["sequence"]
                if not isinstance(seq, list) or not seq:
                    raise ValueError(f"{where}.sequence must be a non-empty list")
                for j, item in enumerate(seq):
                    _check_outcome(item, f"{where}.sequence[{j}]", _OUTCOME_KEYS, _OUTCOME_KEYS)
            normalised[tool].append(rule)
    return normalised


class ToolHarness:
    """Per-request tool layer: applies mocks, falls back to fakes, records calls.

    Create one instance per request. `tools` maps every tool name the agent can
    call to the default fake implementation, called as `fn(**arguments)`.
    With `raise_errors=False`, an `error` mock, a call to an unknown tool, or an
    exception from a default fake (for example a missing argument) returns
    `{"error": message}` as the tool result instead of raising, for agents that
    crash on exceptions. Every record has a `result` (`None` when the call
    raised) and failed calls also have `error`.
    """

    def __init__(
        self,
        mocks: Any,
        tools: Mapping[str, Callable[..., Any]],
        *,
        raise_errors: bool = True,
        parameters: Mapping[str, set[str]] | None = None,
    ) -> None:
        self.tools = dict(tools)
        self.rules = validate_mocks(mocks, set(self.tools), parameters)
        self.raise_errors = raise_errors
        self.calls: list[dict[str, Any]] = []
        self._sequence_positions: dict[tuple[str, int], int] = {}

    def _select(self, name: str, args: dict[str, Any]) -> dict | None:
        for index, rule in enumerate(self.rules.get(name, [])):
            when = rule.get("when", {})
            if not all(_matches(v, args.get(k)) for k, v in when.items()):
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
                return self._fail(record, f"{type(exc).__name__}: {exc}", exc)
        elif "error" in outcome:
            error = outcome["error"]
            return self._fail(
                record,
                error["message"],
                ToolMockError(error["message"], error.get("type")),
                error.get("type"),
            )
        else:
            result = copy.deepcopy(outcome["returns"])  # the agent may mutate it
        record["result"] = _json_safe(result)
        return result

    def _fail(
        self, record: dict[str, Any], message: str, exc: Exception, error_type: str | None = None
    ) -> Any:
        record["error"] = message
        record["result"] = None
        if self.raise_errors:
            raise exc
        result = {"error": message, **({"type": error_type} if error_type else {})}
        record["result"] = result
        return result

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
        "additionalProperties": False,
    }

    def exactly_one(keys: list[str]) -> list[dict[str, Any]]:
        return [{"required": [k]} for k in keys]

    outcome = {
        "type": "object",
        "properties": {"returns": {}, "error": error},
        "additionalProperties": False,
        "oneOf": exactly_one(["returns", "error"]),
    }
    rule = {
        "type": "object",
        "properties": {
            "when": when,
            "returns": {},
            "error": error,
            "sequence": {"type": "array", "items": outcome, "minItems": 1},
        },
        "additionalProperties": False,
        "oneOf": exactly_one(["returns", "error", "sequence"]),
    }
    # A single rule object is accepted as shorthand for a one-item list.
    return {"anyOf": [rule, {"type": "array", "items": rule}]}


def build_input_schema(
    tool_specs: Mapping[str, Mapping[str, Any]],
    trigger_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured input schema `{trigger, mocks}` with one `mocks` property per tool.

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
            "trigger": dict(trigger_schema or {"type": "string"}),
            "mocks": {
                "type": "object",
                "properties": mock_properties,
                "additionalProperties": False,
            },
        },
        "required": ["trigger"],
    }
