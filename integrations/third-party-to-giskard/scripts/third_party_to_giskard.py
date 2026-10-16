#!/usr/bin/env python3
"""Convert garak, promptfoo, DeepTeam, and PyRIT results into Giskard OSS SuiteResults.

The script only reads existing result files. It never runs the third-party tools.
Each convert command handles one tool and writes one SuiteResult JSON file, the payload of
SuiteResult.to_hub_format(). The upload command sends those files to Giskard Hub.

Polarity follows Giskard: PASS means the target resisted, FAIL means the tool found
a vulnerability or a failed assertion, ERROR means the tool could not evaluate, and
SKIP means the tool reached no verdict.
"""

import argparse
import json
import os
import re
import sys
import traceback
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOLS = ("garak", "promptfoo", "deepteam", "pyrit")
USER_ROLES = {"user", "human"}
SYSTEM_ROLES = {"system", "developer"}


# ---------------------------------------------------------------- shared helpers


def compact(value: Any) -> Any:
    """Drop None, empty strings, and empty containers from nested dicts."""
    if isinstance(value, dict):
        out = {k: compact(v) for k, v in value.items()}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    return value


def number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ms_between(start: Any, end: Any) -> int:
    try:
        delta = datetime.fromisoformat(str(end)) - datetime.fromisoformat(str(start))
    except ValueError:
        return 0
    return max(int(delta.total_seconds() * 1000), 0)


def system_prompt(system: list[Any]) -> Any:
    """Return the only system prompt, or the list when there are several."""
    return system[0] if len(system) == 1 else system


def is_sqlite(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(16) == b"SQLite format 3\x00"


def connect_ro(path: Path) -> Any:
    """Open a SQLite database read-only, with rows as sqlite3.Row. Close it with contextlib.closing."""
    import sqlite3

    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def parse_time(value: Any) -> datetime | None:
    """Parse an ISO timestamp ('T' or space separator). Aware times become naive UTC."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def pair_turns(turns: list[tuple[Any, Any, dict]]) -> tuple[list[tuple], list[Any]]:
    """Pair each user turn with the reply that follows it.

    ``turns`` holds ``(role, content, metadata)``. Returns ``(interactions, system)``
    where interactions are ``(inputs, outputs, metadata)`` and system holds the
    system prompts. A reply without a user turn gets ``None`` inputs, and a
    trailing user turn without a reply gets ``None`` outputs.
    """
    pairs: list[tuple] = []
    system: list[Any] = []
    pending: tuple[Any, dict] | None = None
    for role, content, meta in turns:
        role = (role or "").lower()
        if role in SYSTEM_ROLES:
            system.append(content)
        elif role in USER_ROLES:
            if pending is not None:
                pairs.append((pending[0], None, compact({"input": pending[1]})))
            pending = (content, meta)
        else:
            inputs, in_meta = pending if pending is not None else (None, {})
            pairs.append((inputs, content, compact({"input": in_meta, "output": meta, "role": role if role != "assistant" else None})))
            pending = None
    if pending is not None:
        pairs.append((pending[0], None, compact({"input": pending[1]})))
    return pairs, system


def make_check(status: str, name: str, message: Any = None, details: dict | None = None, metrics: dict | None = None):
    from giskard.checks import CheckResult, CheckStatus, Metric

    values = {k: number(v) for k, v in (metrics or {}).items()}
    return CheckResult(
        status=CheckStatus(status),
        message=str(message) if message not in (None, "") else None,
        details={"check_name": name, **compact(details or {})},
        metrics=[Metric(name=k, value=v) for k, v in values.items() if v is not None],
    )


def hub_interaction(inputs: Any, outputs: Any, metadata: dict | None) -> Any:
    """Build an Interaction in a Hub format.

    A dict is the body of a Structured agent and stays an object. Other content uses the Hub Chat
    format: the Hub UI shows chat bubbles only for it, and the Hub SDK cannot read back plain-string
    interactions. Lists and other non-text content become JSON text, because Chat content is a string.
    """
    from giskard.checks import Interaction

    def text(value: Any) -> str:
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)

    if not isinstance(inputs, dict):
        inputs = {"messages": [] if inputs is None else [{"role": "user", "content": text(inputs)}]}
    if outputs is not None and not isinstance(outputs, dict):
        outputs = {"response": {"role": "assistant", "content": text(outputs)}}
    return Interaction(inputs=inputs, outputs=outputs, metadata=metadata or {})


def make_scenario(tool: str, name: str, interactions: list[tuple], checks: list, tags: list[Any], annotations: dict, duration_ms: int = 0):
    from giskard.checks import ScenarioResult, TestCaseResult, Trace

    trace = Trace(
        interactions=[hub_interaction(i, o, m) for i, o, m in interactions],
        annotations=compact({"source_tool": tool, "scenario_name": name, **annotations}),
    )
    step = TestCaseResult(
        results=checks,
        duration_ms=duration_ms,
        last_interaction_index=len(interactions) - 1 if interactions else None,
    )
    tags = [f"tool:{tool}", *(str(t) for t in tags if t not in (None, ""))]
    return ScenarioResult(
        scenario_name=name,
        steps=[step],
        final_trace=trace,
        duration_ms=duration_ms,
        tags=list(dict.fromkeys(tags)),
    )


# ---------------------------------------------------------------- garak


def _garak_text(message: Any) -> Any:
    return message.get("text") if isinstance(message, dict) else message


def _garak_meta(message: Any) -> dict:
    if not isinstance(message, dict):
        return {}
    return compact({k: message.get(k) for k in ("lang", "data_path", "data_type", "data_checksum", "notes")})


def _garak_interactions(attempt: dict, conversation: Any, output: Any) -> tuple[list[tuple], list[Any]]:
    turns = conversation.get("turns") if isinstance(conversation, dict) else conversation
    if isinstance(turns, list) and turns:  # 0.13+ Conversation, or 0.9.0.16-0.12 messages
        return pair_turns([(t.get("role"), _garak_text(t.get("content")), _garak_meta(t.get("content"))) for t in turns])
    prompt = attempt.get("prompt")  # <= 0.9.0.9 plain strings, or a missing conversation
    prompt_turns = prompt.get("turns") if isinstance(prompt, dict) else None
    if prompt_turns:
        turns = [(t.get("role"), _garak_text(t.get("content")), _garak_meta(t.get("content"))) for t in prompt_turns]
        return pair_turns(turns + [("assistant", _garak_text(output), _garak_meta(output))])
    return [(_garak_text(prompt), _garak_text(output), compact({"output": _garak_meta(output)}))], []


def convert_garak(path: Path, opts: argparse.Namespace) -> tuple[list, int]:
    threshold = opts.garak_threshold
    setup: dict = {}
    init: dict = {}
    completion: dict = {}
    digest: dict = {}
    probes_meta: dict = {}
    detectors_meta: dict = {}
    attempts: dict[str, dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            kind = entry.get("entry_type")
            if kind == "attempt":
                # Each attempt is logged twice: status 1 after generation, status 2 after detection.
                previous = attempts.get(entry.get("uuid"))
                if previous is None or (entry.get("status") or 0) >= (previous.get("status") or 0):
                    attempts[entry.get("uuid")] = entry
            elif kind in ("start_run setup", "start_run args config"):
                setup = entry
            elif kind == "init":
                init = entry
            elif kind == "completion":
                completion = entry
            elif kind == "digest":
                digest = entry
            elif kind == "plugin_cache":
                cache = entry.get("plugin_cache") or {}
                probes_meta.update(cache.get("probes") or {})
                detectors_meta.update(cache.get("detectors") or {})

    digest_probes = {
        probe: value["_summary"]
        for group in (digest.get("eval") or {}).values()
        if isinstance(group, dict)
        for probe, value in group.items()
        if isinstance(value, dict) and isinstance(value.get("_summary"), dict) and probe != "_summary"
    }
    target = " ".join(
        str(v)
        for v in (
            setup.get("plugins.target_type") or setup.get("plugins.model_type"),
            setup.get("plugins.target_name") or setup.get("plugins.model_name"),
        )
        if v
    )
    run = {
        "garak_version": init.get("garak_version") or setup.get("_config.version"),
        "garak_run_id": init.get("run") or setup.get("transient.run_id"),
        "target": target,
        "run_started_at": init.get("start_time"),
        "generations": setup.get("run.generations"),
        "eval_threshold": threshold,
    }

    scenarios = []
    for index, attempt in enumerate(attempts.values(), start=1):
        probe = attempt.get("probe_classname") or "unknown"
        probe_meta = probes_meta.get(f"probes.{probe}") or {}
        summary = digest_probes.get(probe) or {}
        tags = [f"probe:{probe}", *(probe_meta.get("tags") or summary.get("probe_tags") or [])]
        if attempt.get("intent"):
            tags.append(f"intent:{attempt['intent']}")
        conversations = attempt.get("conversations") or attempt.get("messages") or []
        outputs = attempt.get("outputs") or []
        reverse = attempt.get("reverse_translation_outputs") or []
        detector_results = attempt.get("detector_results") or {}
        notes = attempt.get("notes") or {}
        generations = max(len(outputs), len(conversations), 1)
        seq = attempt.get("seq")

        for gen in range(generations):
            output = outputs[gen] if gen < len(outputs) else None
            conversation = conversations[gen] if gen < len(conversations) else None
            interactions, system = _garak_interactions(attempt, conversation, output)
            checks = []
            for detector, scores in detector_results.items():
                score = scores[gen] if isinstance(scores, list) and gen < len(scores) else None
                meta = detectors_meta.get(f"detectors.{detector}") or {}
                details = {
                    "detector": detector,
                    "score": score,
                    "eval_threshold": threshold,
                    "detector_description": meta.get("description"),
                    "detector_doc_uri": meta.get("doc_uri"),
                }
                value = number(score)
                if value is None:
                    checks.append(make_check("skip", detector, "Detector returned no score.", details))
                elif value >= threshold:  # garak passes only when score < threshold
                    message = f"{meta.get('hit_desc') or 'Detector hit'} (score {value:g}, threshold {threshold:g})"
                    checks.append(make_check("fail", detector, message, details, {detector: value}))
                else:
                    message = f"{meta.get('pass_desc') or 'Detector passed'} (score {value:g}, threshold {threshold:g})"
                    checks.append(make_check("pass", detector, message, details, {detector: value}))
            if not checks:
                checks.append(make_check("skip", "garak", f"Attempt has no detector results (status {attempt.get('status')}).", {"attempt_status": attempt.get("status")}))

            name = f"{probe} #{seq + 1 if isinstance(seq, int) else index}" + (f" · generation {gen + 1}" if generations > 1 else "")
            annotations = {
                **run,
                "source_file": path.name,
                "garak_attempt_uuid": attempt.get("uuid"),
                "garak_seq": seq,
                "generation": gen + 1 if generations > 1 else None,
                "goal": attempt.get("goal") or probe_meta.get("goal"),
                "intent": attempt.get("intent"),
                "probe_description": probe_meta.get("description") or summary.get("probe_descr"),
                "probe_doc_uri": probe_meta.get("doc_uri"),
                "probe_tier": probe_meta.get("tier") or summary.get("probe_tier"),
                "probe_severity": summary.get("probe_severity"),
                "probe_params": attempt.get("probe_params"),
                "targets": attempt.get("targets"),
                "triggers": notes.get("triggers"),
                "attempt_notes": {k: v for k, v in notes.items() if k != "triggers"},
                "system_prompt": system_prompt(system),
                "reverse_translation_output": _garak_text(reverse[gen]) if gen < len(reverse) else None,
            }
            scenarios.append(make_scenario("garak", name, interactions, checks, tags, annotations))

    return scenarios, ms_between(init.get("start_time"), completion.get("end_time"))


# ---------------------------------------------------------------- promptfoo

_PROMPTFOO_FAILURE_REASONS = {0: "NONE", 1: "ASSERT", 2: "ERROR"}
_PROMPTFOO_BULKY_KEYS = {"messages", "redteamHistory", "redteamTreeHistory"}


def _promptfoo_component(component: dict, test_meta: dict) -> Any:
    assertion = component.get("assertion") or {}
    name = assertion.get("metric") or assertion.get("type") or "assertion"
    grader_meta = {k: v for k, v in (component.get("metadata") or {}).items() if test_meta.get(k) != v}
    status = "error" if grader_meta.get("graderError") else "pass" if component.get("pass") else "fail"
    details = {
        "assertion_type": assertion.get("type"),
        "assertion_value": assertion.get("value"),
        "metric": assertion.get("metric"),
        "weight": assertion.get("weight"),
        "assertion_threshold": assertion.get("threshold"),
        "score": component.get("score"),
        "named_scores": component.get("namedScores"),
        "grader_metadata": grader_meta,
        "nested_results": component.get("componentResults"),
        "comment": component.get("comment"),
    }
    return make_check(status, name, component.get("reason"), details, {name: component.get("score")})


def _promptfoo_checks(record: dict, test_meta: dict) -> list:
    grading = record.get("gradingResult") or {}
    reason = record.get("failureReason")
    errored = reason == 2 or (reason is None and not record.get("success") and not grading and record.get("error"))
    if errored:  # provider or grading error: no verdict
        return [make_check("error", "promptfoo", record.get("error") or "Provider or grading error.", {"failure_reason": "ERROR"})]
    components = grading.get("componentResults") or []
    threshold = (record.get("testCase") or {}).get("threshold")
    agrees = all(c.get("pass") for c in components) == bool(record.get("success"))
    if components and threshold is None and agrees:
        return [_promptfoo_component(c, test_meta) for c in components]
    # A test threshold or weighted assertions aggregate the components, so keep promptfoo's overall verdict.
    details = {
        "score": record.get("score"),
        "test_threshold": threshold,
        "component_results": [compact(_promptfoo_component(c, test_meta).model_dump(mode="json")) for c in components],
    }
    status = "pass" if record.get("success") else "fail"
    return [make_check(status, "promptfoo", grading.get("reason") or record.get("error"), details, {"score": record.get("score")})]


def _promptfoo_turn(message: dict) -> tuple:
    """Return (role, content, metadata). Fields such as tool_calls or tool_call_id go into the metadata."""
    extra = {k: v for k, v in message.items() if k not in ("role", "content")}
    if message.get("content") is None and extra:  # an assistant message with only tool calls: show the calls
        return message.get("role"), json.dumps(extra, ensure_ascii=False, default=str), {}
    return message.get("role"), message.get("content"), extra


def _promptfoo_interactions(record: dict) -> tuple[list[tuple], list[Any]]:
    response = record.get("response") or {}
    meta = response.get("metadata") or {}
    output = response.get("output")
    messages = meta.get("messages")
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except json.JSONDecodeError:
            messages = None
    if isinstance(messages, list) and messages:  # multi-turn strategies (crescendo, goat, hydra...)
        return pair_turns([_promptfoo_turn(m) for m in messages if isinstance(m, dict)])
    prompt = meta.get("redteamFinalPrompt") or response.get("prompt") or (record.get("prompt") or {}).get("raw")
    if isinstance(prompt, list):  # chat prompt as [{role, content}]
        return pair_turns([_promptfoo_turn(m) for m in prompt if isinstance(m, dict)] + [("assistant", output, {})])
    test_vars = record.get("vars") or (record.get("testCase") or {}).get("vars")
    if isinstance(output, dict) and isinstance(test_vars, dict) and test_vars:
        # Structured agent: the provider returned an object, and the vars fill its request body.
        return [(test_vars, output, {})], []
    return [(prompt, output, {})], []


def _promptfoo_db(path: Path, opts: argparse.Namespace) -> list[dict]:
    """Rebuild one `promptfoo export` document per run of a promptfoo.db.

    ponytail: runs saved before results version 4 keep their rows in evals.results and are skipped.
    """
    json_columns = {"config", "results", "test_case", "prompt", "provider", "response", "grading_result", "named_scores", "metadata"}
    with closing(connect_ro(path)) as con:
        return _promptfoo_db_runs(con, json_columns, opts)


def _promptfoo_db_runs(con: Any, json_columns: set, opts: argparse.Namespace) -> list[dict]:
    def rows(sql: str, *params: Any) -> list[dict]:
        # snake_case columns become the camelCase keys of the export: test_case -> testCase.
        return [
            {re.sub(r"_([a-z])", lambda m: m[1].upper(), k): json.loads(v) if k in json_columns and isinstance(v, str) else v for k, v in dict(r).items()}
            for r in con.execute(sql, params)
        ]

    runs = []
    for ev in rows("SELECT * FROM evals ORDER BY created_at"):
        if opts.promptfoo_eval_id and ev["id"] not in opts.promptfoo_eval_id:
            continue
        results = rows("SELECT * FROM eval_results WHERE eval_id = ? ORDER BY test_idx, prompt_idx", ev["id"])
        if results:
            runs.append({"evalId": ev["id"], "config": ev["config"], "results": {"stats": ev["results"], "results": results}})
    return runs


def convert_promptfoo(path: Path, opts: argparse.Namespace) -> tuple[list, int]:
    scenarios: list = []
    duration_ms = 0
    for raw in _promptfoo_db(path, opts) if is_sqlite(path) else [load_json(path)]:
        converted, duration = _promptfoo_run(raw, path)
        scenarios += converted
        duration_ms += duration
    return scenarios, duration_ms


def _promptfoo_run(raw: Any, path: Path) -> tuple[list, int]:
    if isinstance(raw, list):  # -o results.jsonl: one EvaluateResult per line
        data: dict = {"results": {"results": raw}}
    else:
        data = raw["data"] if isinstance(raw.get("data"), dict) else raw  # shared-eval wrapper
    summary = data.get("results") or {}
    records = summary.get("results") or []
    config = data.get("config") or {}
    meta = data.get("metadata") or {}
    run = {
        "promptfoo_eval_id": data.get("evalId"),
        "promptfoo_version": meta.get("promptfooVersion"),
        "eval_description": config.get("description"),
        "eval_created_at": summary.get("timestamp") or meta.get("evaluationCreatedAt"),
        "eval_author": meta.get("author") or data.get("author"),
        "redteam_purpose": (config.get("redteam") or {}).get("purpose"),
    }
    config_tags = [f"{k}:{v}" for k, v in (config.get("tags") or {}).items()] if isinstance(config.get("tags"), dict) else []

    def provider_name(record: dict) -> Any:
        provider = record.get("provider") or {}
        return (provider.get("label") or provider.get("id")) if isinstance(provider, dict) else provider

    def prompt_label(record: dict) -> Any:
        return (record.get("prompt") or {}).get("label")

    # The same test runs once per provider x prompt column. Name the column only when there are several.
    multi_provider = len({str(provider_name(r)) for r in records}) > 1
    multi_prompt = len({str(prompt_label(r)) for r in records}) > 1
    scenarios = []
    for index, record in enumerate(records, start=1):
        test = record.get("testCase") or {}
        response = record.get("response") or {}
        response_meta = response.get("metadata") or {}
        test_meta = {
            k: v
            for k, v in {**(record.get("metadata") or {}), **(test.get("metadata") or {})}.items()
            if not k.startswith("_") and k not in response_meta
        }
        plugin, strategy = test_meta.get("pluginId"), test_meta.get("strategyId")
        description = test.get("description") or record.get("description")
        test_idx = record.get("testIdx")
        number_label = f"#{test_idx + 1}" if isinstance(test_idx, int) else f"#{index}"
        if plugin:
            name = f"{plugin} · {strategy or 'basic'} {number_label}"
        else:
            name = description or f"test {number_label}"
        if multi_provider:
            name += f" · {provider_name(record)}"
        if multi_prompt:
            name += f" · prompt {(record.get('promptIdx') or 0) + 1}"
        if isinstance(record.get("repeatIndex"), int):
            name += f" · repeat {record['repeatIndex'] + 1}"

        interactions, system = _promptfoo_interactions(record)
        if interactions:
            inputs, outputs, last_meta = interactions[-1]
            interactions[-1] = (inputs, outputs, compact({
                **last_meta,
                "latency_ms": record.get("latencyMs") or response.get("latencyMs"),
                "token_usage": record.get("tokenUsage") or response.get("tokenUsage"),
                "cost": record.get("cost") or response.get("cost"),
                "cached": response.get("cached"),
                "finish_reason": response.get("finishReason"),
                "is_refusal": response.get("isRefusal"),
                "guardrails": response.get("guardrails"),
                "session_id": response.get("sessionId"),
            }))

        tags = [
            *config_tags,
            f"eval-id:{data['evalId']}" if data.get("evalId") else None,
            f"plugin:{plugin}" if plugin else None,
            f"strategy:{strategy or 'basic'}" if plugin else None,
            f"severity:{test_meta['severity']}" if test_meta.get("severity") else None,
            f"harm-category:{test_meta['harmCategory']}" if test_meta.get("harmCategory") else None,
            f"provider:{provider_name(record)}" if provider_name(record) else None,
            *(f"metric:{m}" for m in (record.get("namedScores") or {})),
        ]
        annotations = {
            **run,
            "source_file": path.name,
            "result_id": record.get("id"),
            "test_idx": test_idx,
            "prompt_idx": record.get("promptIdx"),
            "repeat_index": record.get("repeatIndex"),
            "test_description": description,
            "provider": record.get("provider"),
            "test_provider": test.get("provider"),
            "prompt_label": prompt_label(record),
            "prompt_template_output": (record.get("prompt") or {}).get("raw"),
            "vars": record.get("vars") or test.get("vars"),
            "test_metadata": test_meta,
            "success": record.get("success"),
            "score": record.get("score"),
            "failure_reason": _PROMPTFOO_FAILURE_REASONS.get(record.get("failureReason")),
            "named_scores": record.get("namedScores"),
            "grader_comment": (record.get("gradingResult") or {}).get("comment"),
            "system_prompt": system_prompt(system),
            "redteam_history": response_meta.get("redteamHistory"),
            "redteam_tree_history": response_meta.get("redteamTreeHistory"),
            "response_metadata": {k: v for k, v in response_meta.items() if k not in _PROMPTFOO_BULKY_KEYS},
        }
        checks = _promptfoo_checks(record, test_meta)
        scenarios.append(make_scenario("promptfoo", name, interactions, checks, tags, annotations))

    duration = number((summary.get("stats") or {}).get("durationMs")) or 0
    return scenarios, int(duration)


# ---------------------------------------------------------------- DeepTeam


def convert_deepteam(path: Path, opts: argparse.Namespace) -> tuple[list, int]:
    data = load_json(path)
    overview = data.get("overview") or {}
    scenarios = []
    for index, case in enumerate(data.get("test_cases") or data.get("testCases") or [], start=1):

        def field(*keys: str) -> Any:  # deepteam mixes snake_case and camelCase across versions
            return next((case[k] for k in keys if case.get(k) is not None), None)

        vulnerability = field("vulnerability")
        vulnerability_type = field("vulnerability_type", "vulnerabilityType")
        attack = field("attack_method", "attackMethod")
        risk = field("risk_category", "riskCategory")
        output = field("actual_output", "actualOutput")
        turns = case.get("turns") or []
        if turns:
            interactions, system = pair_turns(
                [(t.get("role"), t.get("content"), {k: v for k, v in t.items() if k not in ("role", "content")}) for t in turns]
            )
        else:
            system = []
            interactions = [(case.get("input"), output, {})] if case.get("input") is not None or output is not None else []

        check_name = f"{vulnerability}/{vulnerability_type}" if vulnerability and vulnerability_type else vulnerability or "deepteam"
        score = number(case.get("score"))
        details = {
            "vulnerability": vulnerability,
            "vulnerability_type": vulnerability_type,
            "attack_method": attack,
            "risk_category": risk,
            "score": case.get("score"),
            "cvss_score": case.get("cvss_score"),
        }
        if case.get("error"):
            check = make_check("error", check_name, case["error"], details)
        elif score is None:
            check = make_check("skip", check_name, case.get("reason") or "DeepTeam returned no score.", details)
        else:  # deepteam: score 1 means the target resisted, a case passes when score > 0
            check = make_check("pass" if score > 0 else "fail", check_name, case.get("reason"), details, {check_name: score})

        used = {"vulnerability", "vulnerability_type", "vulnerabilityType", "attack_method", "attackMethod", "risk_category",
                "riskCategory", "actual_output", "actualOutput", "turns", "score", "reason", "error"}
        extra = {k: v for k, v in case.items() if k not in used and (k != "input" or turns)}
        name = check_name + (f" · {attack}" if attack else "") + f" #{index}"
        tags = [
            f"vulnerability:{vulnerability}" if vulnerability else None,
            f"vulnerability-type:{vulnerability_type}" if vulnerability_type else None,
            f"attack-method:{attack}" if attack else None,
            f"risk-category:{risk}" if risk else None,
        ]
        annotations = {
            "source_file": path.name,
            "test_case_index": index,
            "reason": case.get("reason"),
            "system_prompt": system_prompt(system),
            "run_cvss_score": overview.get("cvss_score", overview.get("cvssScore")),
            **extra,
        }
        scenarios.append(make_scenario("deepteam", name, interactions, [check], tags, annotations))

    return scenarios, int((number(overview.get("run_duration", overview.get("runDuration"))) or 0) * 1000)


# ---------------------------------------------------------------- PyRIT

# AttackOutcome "success" means the attack objective was achieved, so the target is vulnerable.
_PYRIT_OUTCOMES = {"success": "fail", "failure": "pass", "error": "error", "undetermined": "skip"}
_PYRIT_JSON_COLUMNS = {
    "labels", "prompt_metadata", "targeted_harm_categories", "converter_identifiers", "prompt_target_identifier",
    "attack_identifier", "orchestrator_identifier", "atomic_attack_identifier", "attack_metadata", "pruned_conversation_ids",
    "adversarial_chat_conversation_ids", "attribution_data", "retry_events_json", "score_category", "score_metadata",
    "scorer_class_identifier", "scorable", "target_identifier", "scenario_identifier", "objective_target_identifier",
    "objective_scorer_identifier", "display_group_map_json", "scenario_metadata", "attack_results_json", "scenario_init_data",
}


def _pyrit_class(identifier: Any) -> str | None:
    return (identifier.get("class_name") or identifier.get("__type__")) if isinstance(identifier, dict) else None


def _pyrit_attack_node(identifier: Any) -> dict:
    """Return the attack identifier. In 1.x it is nested in the atomic attack identifier."""
    node = identifier if isinstance(identifier, dict) else {}
    for key in ("attack_technique", "attack"):
        node = (node.get("children") or {}).get(key) or node
    return node


def _pyrit_score(score: dict | None) -> dict:
    if not score:
        return {}
    return compact({
        "value": score.get("score_value"),
        "type": score.get("score_type"),
        "category": score.get("score_category"),
        "rationale": score.get("score_rationale"),
        "description": score.get("score_value_description"),
        "scorer": _pyrit_class(score.get("scorer_class_identifier")),
        "objective": score.get("objective") or score.get("task"),
        "status": score.get("status"),
        "metadata": score.get("score_metadata"),
    })


def _pyrit_scorer_name(score: dict, fallback: Any = None) -> str | None:
    """Name a check after its scorer and category, so two judges of the same class stay separate metrics."""
    name = _pyrit_class(score.get("scorer_class_identifier")) or fallback
    category = score.get("score_category")
    category = ", ".join(map(str, category)) if isinstance(category, list) else category
    return f"{name} ({category})" if name and category else name


def _pyrit_score_value(score: dict) -> float | None:
    value = str(score.get("score_value")).strip().lower()
    return {"true": 1.0, "false": 0.0}.get(value, number(score.get("score_value")))


def _pyrit_piece_meta(piece: dict, scores: list) -> dict:
    converted = piece.get("converted_value")
    return compact({
        "piece_id": piece.get("id"),
        "original_value": piece.get("original_value") if piece.get("original_value") != converted else None,
        "original_value_data_type": piece.get("original_value_data_type") if piece.get("original_value_data_type") != "text" else None,
        "converted_value_data_type": piece.get("converted_value_data_type") if piece.get("converted_value_data_type") != "text" else None,
        "converters": [_pyrit_class(c) for c in piece.get("converter_identifiers") or []],
        "response_error": piece.get("response_error") if piece.get("response_error") not in (None, "none") else None,
        "prompt_metadata": piece.get("prompt_metadata"),
        "scores": [_pyrit_score(s) for s in scores],
    })


def _pyrit_interactions(pieces: list[dict], scores_by_piece: dict) -> tuple[list[tuple], list[Any]]:
    """Group pieces into messages by sequence, then pair user and assistant messages."""
    messages: dict[Any, list[dict]] = defaultdict(list)
    for piece in sorted(pieces, key=lambda p: (p.get("sequence") or 0, str(p.get("timestamp")))):
        messages[piece.get("sequence")].append(piece)
    turns = []
    for group in messages.values():
        values = [p.get("converted_value") if p.get("converted_value") is not None else p.get("original_value") for p in group]
        metas = [_pyrit_piece_meta(p, p.get("scores") or scores_by_piece.get(p.get("original_prompt_id") or p.get("id"), [])) for p in group]
        if len(group) == 1 and group[0].get("converted_value_data_type", "text") == "text":
            content, meta = values[0], metas[0]
        else:  # multimodal message: keep each piece with its data type
            content = [{"type": p.get("converted_value_data_type"), "value": v} for p, v in zip(group, values)]
            meta = {"pieces": metas}
        role = group[0].get("role")
        turns.append(("assistant" if role == "simulated_assistant" else role, content, meta))
    return pair_turns(turns)


def _pyrit_after_since(timestamp: Any, since: str) -> bool:
    start, at = parse_time(since), parse_time(timestamp)
    if start is None or at is None:  # unparsable: fall back to comparing text
        return str(timestamp or "") >= since
    return at >= start


def _pyrit_keep(result: dict, labels: dict, scenario_id: Any, opts: argparse.Namespace) -> bool:
    return (
        all(str(labels.get(k)) == v for k, v in opts.pyrit_labels.items())
        and (not opts.pyrit_scenario_id or scenario_id in opts.pyrit_scenario_id)
        and (not opts.pyrit_conversation_id or result.get("conversation_id") in opts.pyrit_conversation_id)
        and (not opts.pyrit_since or _pyrit_after_since(result.get("timestamp"), opts.pyrit_since))
    )


def _pyrit_attack_scenario(result: dict, pieces: list[dict], scores_by_piece: dict, context: dict, path: Path) -> Any:
    outcome = str(result.get("outcome") or "undetermined").lower()
    attack_node = _pyrit_attack_node(result.get("atomic_attack_identifier") or result.get("attack_identifier"))
    attack_children = attack_node.get("children") or {}
    attack = _pyrit_class(attack_node)
    last_score = result.get("last_score") or {}
    check_name = _pyrit_scorer_name(last_score, _pyrit_class(attack_children.get("objective_scorer"))) or "objective"
    first = pieces[0] if pieces else {}
    labels = result.get("labels") or first.get("labels") or {}
    harm = result.get("targeted_harm_categories") or first.get("targeted_harm_categories") or last_score.get("score_category") or []
    target = context.get("target") or attack_children.get("objective_target") or first.get("prompt_target_identifier") or {}

    details = {
        "outcome": outcome,
        "outcome_reason": result.get("outcome_reason"),
        "objective": result.get("objective"),
        "objective_score": _pyrit_score(last_score),
        "error_message": result.get("error_message"),
        "error_type": result.get("error_type"),
        "error_traceback": result.get("error_traceback"),
    }
    message = result.get("outcome_reason") or last_score.get("score_rationale") or result.get("error_message") or f"Attack outcome: {outcome}."
    metric = _pyrit_score_value(last_score) if last_score else None
    check = make_check(_PYRIT_OUTCOMES.get(outcome, "skip"), check_name, message, details, {check_name: metric})

    interactions, system = _pyrit_interactions(pieces, scores_by_piece)
    objective = str(result.get("objective") or "")
    name = f"{attack or 'attack'} · {objective[:80]}{'...' if len(objective) > 80 else ''}"
    tags = [
        f"attack:{attack}" if attack else None,
        f"scenario:{context['pyrit_scenario_name']}" if context.get("pyrit_scenario_name") else None,
        f"attack-group:{context['attack_group']}" if context.get("attack_group") else None,
        *(f"harm-category:{h}" for h in (harm if isinstance(harm, list) else [harm])),
        *(f"{k}:{v}" for k, v in labels.items()),
    ]
    annotations = {
        "source_file": path.name,
        "objective": result.get("objective"),
        "attack_result_id": result.get("attack_result_id") or result.get("id"),
        "conversation_id": result.get("conversation_id"),
        "attack": attack,
        "converters": [_pyrit_class(c) for c in attack_children.get("request_converters") or []],
        "target": compact({k: target.get(k) for k in ("class_name", "__type__", "model_name", "underlying_model_name", "endpoint")}) if isinstance(target, dict) else target,
        "labels": labels,
        "targeted_harm_categories": harm,
        "executed_turns": result.get("executed_turns"),
        "execution_time_ms": result.get("execution_time_ms"),
        "timestamp": result.get("timestamp"),
        "pyrit_version": result.get("pyrit_version") or attack_node.get("pyrit_version"),
        "attack_metadata": result.get("attack_metadata") or result.get("metadata"),
        "total_retries": result.get("total_retries"),
        "system_prompt": system_prompt(system),
        "related_conversations": result.get("related_conversations"),
        "pruned_conversation_ids": result.get("pruned_conversation_ids"),
        **{k: v for k, v in context.items() if k != "target"},
    }
    duration = int(number(result.get("execution_time_ms")) or 0)
    return make_scenario("pyrit", name, interactions, [check], tags, annotations, duration)


def _pyrit_conversation_scenarios(pieces_by_conv: dict[str, list[dict]], scores_by_piece: dict, path: Path, opts: argparse.Namespace) -> list:
    """Fallback without attack results: one scenario per scored conversation, one check per score."""
    scenarios = []
    for conversation_id, pieces in pieces_by_conv.items():
        first = pieces[0]
        labels = first.get("labels") or {}
        if not _pyrit_keep({"conversation_id": conversation_id, "timestamp": first.get("timestamp")}, labels, None, opts):
            continue
        scores = [s for p in pieces for s in (p.get("scores") or scores_by_piece.get(p.get("original_prompt_id") or p.get("id"), []))]
        if not scores and not opts.pyrit_all_conversations:
            continue  # adversarial-chat and scorer conversations carry no score
        checks = []
        for score in scores:
            value = _pyrit_score_value(score)
            name = _pyrit_scorer_name(score) or "score"
            if value is None:
                status = "skip"
            elif score.get("score_type") == "true_false":
                status = "pass" if (value == 1.0) == opts.pyrit_true_is_safe else "fail"
            else:
                status = "fail" if value >= opts.pyrit_float_threshold else "pass"
            message = score.get("score_rationale") or score.get("score_value_description") or f"Score {score.get('score_value')} ({score.get('score_type')})."
            checks.append(make_check(status, name, message, _pyrit_score(score), {name: value}))
        if not checks:
            checks.append(make_check("skip", "pyrit", "The conversation has no score."))
        interactions, system = _pyrit_interactions(pieces, scores_by_piece)
        attack = _pyrit_class(first.get("attack_identifier") or first.get("orchestrator_identifier"))
        harm = first.get("targeted_harm_categories") or []
        harm = harm if isinstance(harm, list) else [harm]
        tags = [f"attack:{attack}" if attack else None, *(f"harm-category:{h}" for h in harm), *(f"{k}:{v}" for k, v in labels.items())]
        annotations = {
            "source_file": path.name,
            "conversation_id": conversation_id,
            "attack": attack,
            "attack_instance_id": (first.get("orchestrator_identifier") or {}).get("id"),
            "target": first.get("prompt_target_identifier"),
            "labels": labels,
            "targeted_harm_categories": harm,
            "timestamp": first.get("timestamp"),
            "pyrit_version": first.get("pyrit_version"),
            "system_prompt": system_prompt(system),
            "verdict_source": "scores (no attack outcome in this input)",
        }
        name = f"{attack or 'conversation'} · {conversation_id}"
        scenarios.append(make_scenario("pyrit", name, interactions, checks, tags, annotations))
    return scenarios


def _pyrit_rows(con: Any, sql: str, params: Any = ()) -> list[dict]:
    rows = []
    for row in con.execute(sql, params):
        item = dict(row)
        for key in item.keys() & _PYRIT_JSON_COLUMNS:
            if isinstance(item[key], str):
                try:
                    item[key] = json.loads(item[key])  # SQLAlchemy stores JSON null as the text 'null'
                except json.JSONDecodeError:
                    pass
        rows.append(item)
    return rows


def _pyrit_db(path: Path, opts: argparse.Namespace) -> list:
    # Read-only: opening an old DB with a newer PyRIT would migrate it in place.
    with closing(connect_ro(path)) as con:
        return _pyrit_db_scenarios(con, path, opts)


def _pyrit_db_scenarios(con: Any, path: Path, opts: argparse.Namespace) -> list:
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "PromptMemoryEntries" not in tables:
        raise ValueError(f"{path} is a SQLite file but not a PyRIT memory database.")

    def grouped(table: str, column: str, values: Any, order: str = "") -> dict:
        """Fetch rows whose column is in values, grouped by that column.

        One IN query per 500 values: the columns have no index and the DB is read-only,
        so one query per conversation would scan the table once per attack.
        """
        found: dict = defaultdict(list)
        values = list(dict.fromkeys(v for v in values if v))
        for start in range(0, len(values), 500):
            chunk = values[start:start + 500]
            sql = f"SELECT * FROM {table} WHERE {column} IN ({','.join('?' * len(chunk))}) {order}"
            for row in _pyrit_rows(con, sql, chunk):
                found[row[column]].append(row)
        return found

    def scores_for(pieces: Any) -> dict:
        return grouped("ScoreEntries", "prompt_request_response_id", (p.get("original_prompt_id") or p["id"] for p in pieces), "ORDER BY timestamp")

    results = _pyrit_rows(con, "SELECT * FROM AttackResultEntries ORDER BY timestamp") if "AttackResultEntries" in tables else []
    if not results:  # PyRIT < 0.10 style data: no attack outcomes
        pieces_by_conv: dict[str, list[dict]] = defaultdict(list)
        all_pieces = _pyrit_rows(con, "SELECT * FROM PromptMemoryEntries ORDER BY conversation_id, sequence, timestamp")
        for piece in all_pieces:
            pieces_by_conv[piece["conversation_id"]].append(piece)
        return _pyrit_conversation_scenarios(pieces_by_conv, scores_for(all_pieces), path, opts)

    scenario_rows = {s["id"]: s for s in _pyrit_rows(con, "SELECT * FROM ScenarioResultEntries")} if "ScenarioResultEntries" in tables else {}
    by_conversation = {}  # 0.10 to 0.14: attack_results_json maps atomic attack names to conversation IDs
    for row in scenario_rows.values():
        for atomic, conversation_ids in (row.get("attack_results_json") or {}).items():
            for conversation_id in conversation_ids or []:
                by_conversation[conversation_id] = (row, atomic)
    targets = {}
    if "Conversations" in tables:
        targets = {r["conversation_id"]: r.get("target_identifier") for r in _pyrit_rows(con, "SELECT conversation_id, target_identifier FROM Conversations")}
    conversation_ids = [r.get("conversation_id") for r in results]
    conversation_ids += [c for r in results for c in r.get("adversarial_chat_conversation_ids") or []]
    pieces_by_conv = grouped("PromptMemoryEntries", "conversation_id", conversation_ids, "ORDER BY sequence, timestamp")
    scores_by_piece = scores_for(p for c in conversation_ids for p in pieces_by_conv.get(c, []))
    scores_by_id = {k: v[0] for k, v in grouped("ScoreEntries", "id", (r.get("last_score_id") for r in results)).items()}

    scenarios = []
    for result in results:
        scenario_row, atomic = scenario_rows.get(result.get("attribution_parent_id")), (result.get("attribution_data") or {}).get("parent_collection")
        if scenario_row is None and result.get("conversation_id") in by_conversation:
            scenario_row, atomic = by_conversation[result["conversation_id"]]
        pieces = pieces_by_conv.get(result.get("conversation_id"), [])
        labels = result.get("labels") or (pieces[0].get("labels") if pieces else None) or {}
        if not _pyrit_keep(result, labels, (scenario_row or {}).get("id"), opts):
            continue
        result = {**result, "last_score": scores_by_id.get(result.get("last_score_id"))}
        adversarial = [
            {"role": p.get("role"), "content": p.get("converted_value")}
            for conversation_id in result.get("adversarial_chat_conversation_ids") or []
            for p in pieces_by_conv.get(conversation_id, [])
        ]
        context = compact({
            "target": targets.get(result.get("conversation_id")),
            "pyrit_scenario_id": (scenario_row or {}).get("id"),
            "pyrit_scenario_name": (scenario_row or {}).get("scenario_name"),
            "pyrit_scenario_description": (scenario_row or {}).get("scenario_description"),
            "pyrit_scenario_version": (scenario_row or {}).get("scenario_version"),
            "atomic_attack": atomic,
            "attack_group": ((scenario_row or {}).get("display_group_map_json") or {}).get(atomic),
            # Roles are reversed in the adversarial chat: the attacker speaks as "assistant".
            "adversarial_chat": adversarial,
        })
        scenarios.append(_pyrit_attack_scenario(result, pieces, scores_by_piece, context, path))
    return scenarios


def convert_pyrit(path: Path, opts: argparse.Namespace) -> tuple[list, int]:
    with path.open("rb") as handle:
        head = handle.read(16)
    if head[8:12] == b"DUCK":
        raise ValueError(
            "This is a PyRIT DuckDB memory (PyRIT 0.9 and older), which the standard library cannot read. "
            "Ask the user to export it with memory.export_conversations(file_path=..., export_type='json') in that PyRIT version."
        )
    if head.startswith(b"SQLite format 3\x00"):
        scenarios = _pyrit_db(path, opts)
    else:
        data = load_json(path)
        items = data if isinstance(data, list) else [data]
        first = next((x for x in items if isinstance(x, dict)), {})
        scenarios = []
        if "attack_results" in first:  # ScenarioResult dump
            for scenario in items:
                group_map = scenario.get("display_group_map") or {}
                for atomic, results in (scenario.get("attack_results") or {}).items():
                    for result in results:
                        context = compact({
                            "target": scenario.get("objective_target_identifier"),
                            "pyrit_scenario_id": scenario.get("id"),
                            "pyrit_scenario_name": scenario.get("scenario_name"),
                            "pyrit_scenario_description": scenario.get("scenario_description"),
                            "pyrit_scenario_version": scenario.get("scenario_version"),
                            "atomic_attack": atomic,
                            "attack_group": group_map.get(atomic),
                        })
                        if _pyrit_keep(result, result.get("labels") or {}, scenario.get("id"), opts):
                            pieces = [result["last_response"]] if result.get("last_response") else []
                            scenarios.append(_pyrit_attack_scenario(result, pieces, {}, context, path))
        elif "outcome" in first:  # AttackResult dumps: only the last response is available
            for result in items:
                if _pyrit_keep(result, result.get("labels") or {}, result.get("attribution_parent_id"), opts):
                    pieces = [result["last_response"]] if result.get("last_response") else []
                    scenarios.append(_pyrit_attack_scenario(result, pieces, {}, {}, path))
        elif "conversation_id" in first:  # export_conversations or MessagePiece dumps
            pieces_by_conv: dict[str, list[dict]] = defaultdict(list)
            for piece in items:
                pieces_by_conv[piece["conversation_id"]].append(piece)
            scenarios = _pyrit_conversation_scenarios(pieces_by_conv, {}, path, opts)
            if not scenarios and not opts.pyrit_all_conversations:
                raise ValueError(
                    f"{path} holds PyRIT conversations without scores or attack outcomes, so there is no verdict. "
                    "Convert the PyRIT memory database (pyrit.db) instead, or pass --pyrit-all-conversations to keep them as SKIP."
                )
    return scenarios, sum(s.duration_ms for s in scenarios)


# ---------------------------------------------------------------- CLI

CONVERTERS = {"garak": convert_garak, "promptfoo": convert_promptfoo, "deepteam": convert_deepteam, "pyrit": convert_pyrit}


def load_json(path: Path) -> Any:
    """Parse a JSON file, or a JSONL file into a list. ponytail: loads the whole file in memory."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".jsonl":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def emit(data: Any) -> None:
    """Print the single JSON document that each command writes to stdout."""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def cmd_convert(opts: argparse.Namespace) -> None:
    from giskard.checks import SuiteResult

    opts.pyrit_labels = dict(item.split("=", 1) for item in opts.pyrit_label or [])
    scenarios: list = []
    duration_ms = 0
    inputs = []
    for raw in opts.files:
        path = Path(raw)
        if not path.is_file():
            raise FileNotFoundError(f"Input file not found: {path}")
        try:
            converted, duration = CONVERTERS[opts.tool](path, opts)
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError, TypeError, KeyError) as exc:
            raise ValueError(f"{path} is not a supported {opts.tool} result file ({type(exc).__name__}: {exc}).") from exc
        if not converted:
            raise ValueError(f"No {opts.tool} results found in {path}. Check --tool and the file.")
        scenarios.extend(converted)
        duration_ms += duration
        inputs.append({"file": str(path), "scenarios": len(converted)})
        print(f"{path}: {len(converted)} scenarios", file=sys.stderr)

    # Make scenario names unique. Runs repeat the same tests, and PyRIT names cut objectives at 80 characters.
    taken = {s.scenario_name for s in scenarios}
    counts, seen = Counter(s.scenario_name for s in scenarios), Counter()
    for i, s in enumerate(scenarios):
        if counts[s.scenario_name] > 1:
            name = s.scenario_name
            while name in taken:
                seen[s.scenario_name] += 1
                name = f"{s.scenario_name} ({seen[s.scenario_name]})"
            taken.add(name)
            s.final_trace.annotations["scenario_name"] = name
            scenarios[i] = s.model_copy(update={"scenario_name": name})

    result = SuiteResult(results=scenarios, duration_ms=duration_ms)
    output = Path(opts.output or f"giskard_results/{opts.tool}_suite_result.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.to_hub_format(), ensure_ascii=False, indent=1), encoding="utf-8")

    summary = {
        "tool": opts.tool,
        "output": str(output),
        "inputs": inputs,
        "scenarios": len(scenarios),
        "passed": result.passed_count,
        "failed": result.failed_count,
        "errored": result.errored_count,
        "skipped": result.skipped_count,
        "pass_rate": result.pass_rate,
        "duration_ms": duration_ms,
        "tag_keys": sorted({tag.partition(":")[0] for s in scenarios for tag in s.tags}),
    }
    for key in opts.group_by or []:
        groups = result.group_by(key).groups
        summary[f"by_{key}"] = {
            str(name): stats.model_dump(include={"passed", "failed", "errored", "skipped", "pass_rate"})
            for name, stats in groups.items()
        }
    emit(summary)


def _hub(env_file: str, max_retries: int = 2):
    from giskard_hub import HubClient

    # Existing environment variables win over the env file.
    path = Path(env_file)
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))
    missing = [k for k in ("GISKARD_HUB_BASE_URL", "GISKARD_HUB_API_KEY") if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"{', '.join(missing)} not set. Set them in the environment or in {path}.")
    return HubClient(max_retries=max_retries)  # reads GISKARD_HUB_BASE_URL and GISKARD_HUB_API_KEY


def cmd_projects(opts: argparse.Namespace) -> None:
    with _hub(opts.env_file) as hub:
        emit([{"id": p.id, "name": p.name, "description": getattr(p, "description", None)} for p in hub.projects.list()])


def cmd_agents(opts: argparse.Namespace) -> None:
    with _hub(opts.env_file) as hub:
        emit([{"id": a.id, "name": a.name, "description": getattr(a, "description", None)} for a in hub.agents.list(project_id=opts.project_id)])


def split_payload(payload: dict, max_bytes: int) -> list[dict]:
    """Split a SuiteResult payload into parts whose scenarios stay under max_bytes of JSON.

    Used with --max-upload-mb when a Hub rejects a large upload. Each part becomes its own evaluation.
    """
    parts: list[list] = [[]]
    size = 0
    for scenario in payload["results"]:
        scenario_bytes = len(json.dumps(scenario, ensure_ascii=False, default=str).encode())
        if parts[-1] and size + scenario_bytes > max_bytes:
            parts.append([])
            size = 0
        parts[-1].append(scenario)
        size += scenario_bytes
    return [{**payload, "results": part} for part in parts]


def cmd_upload(opts: argparse.Namespace) -> None:
    if opts.name and len(opts.files) > 1:
        raise ValueError("--name works with a single file only. Upload the files one at a time to name each evaluation.")
    payloads = []
    for raw in opts.files:
        payload = json.loads(Path(raw).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError(f"{raw} is not a SuiteResult JSON file written by the convert command.")
        payloads.append((raw, payload))

    uploaded: list[dict] = []
    # No retries: an upload creates an evaluation, so a retry after a timeout can create a duplicate.
    with _hub(opts.env_file, max_retries=0) as hub:
        ui_base = os.environ["GISKARD_HUB_BASE_URL"].rstrip("/").removesuffix("/_api")
        for raw, payload in payloads:
            scenarios = payload["results"]
            tool = next((s.get("final_trace", {}).get("annotations", {}).get("source_tool") for s in scenarios[:1]), None)
            base_name = opts.name or f"{tool or 'third-party'} results ({datetime.now():%Y-%m-%d %H:%M})"
            parts = split_payload(payload, int(opts.max_upload_mb * 1_000_000)) if opts.max_upload_mb else [payload]
            for index, part in enumerate(parts, start=1):
                name = base_name if len(parts) == 1 else f"{base_name} (part {index}/{len(parts)})"
                try:
                    evaluation = hub.evaluations.upload(
                        project_id=opts.project_id,
                        payload=part,
                        agent_id=opts.agent_id,
                        name=name,
                        auto_classify_failures=opts.auto_classify_failures,
                    )
                except Exception as exc:
                    done = ", ".join(f"{u['name']} ({u['evaluation_id']})" for u in uploaded) or "none"
                    raise RuntimeError(
                        f"Upload of '{name}' from {raw} failed: {exc}. Already uploaded: {done}. "
                        "The file may be too big for this Hub. If so, upload it again with --max-upload-mb to split it."
                    ) from exc
                uploaded.append({
                    "file": raw,
                    "tool": tool,
                    "part": f"{index}/{len(parts)}",
                    "evaluation_id": evaluation.id,
                    "name": name,
                    "scenarios": len(part["results"]),
                    "url": f"{ui_base}/p/{opts.project_id}/evaluations/{evaluation.id}",
                })
                print(f"{raw}: uploaded '{name}' as evaluation {evaluation.id}", file=sys.stderr)
    emit({"project_id": opts.project_id, "agent_id": opts.agent_id, "evaluations": uploaded})

EPILOG = """
Every command prints one JSON document on stdout. Progress goes to stderr.
On failure, the command prints {"error": "..."} on stdout and exits with code 1.

examples:
  %(prog)s convert --tool garak run1.report.jsonl run2.report.jsonl
  %(prog)s convert --tool promptfoo results.json --group-by plugin --group-by severity
  %(prog)s convert --tool promptfoo ~/.promptfoo/promptfoo.db --group-by eval-id
  %(prog)s convert --tool deepteam deepteam-results/20260101_120000.json --output out/deepteam.json
  %(prog)s convert --tool pyrit ~/.local/share/dbdata/pyrit.db --pyrit-label op_name=nightly --group-by attack
  %(prog)s projects
  %(prog)s agents <project_id>
  %(prog)s upload giskard_results/garak_suite_result.json --project-id <project_id> --agent-id <agent_id>
"""


def _key_value(text: str) -> str:
    if "=" not in text:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {text!r}")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    convert = sub.add_parser(
        "convert",
        help="Convert the result files of one tool into one SuiteResult JSON file.",
        description="Convert the result files of one tool into one SuiteResult JSON file (the payload of SuiteResult.to_hub_format()).",
    )
    convert.add_argument("files", nargs="+", help="Result files of the tool. Several files merge into one suite.")
    convert.add_argument("--tool", required=True, choices=TOOLS, help="The tool that produced the files.")
    convert.add_argument("--output", help="Output JSON path. Default: giskard_results/<tool>_suite_result.json.")
    convert.add_argument("--group-by", action="append", metavar="TAG_KEY", help="Add pass/fail counts per value of this tag key to the summary. Repeatable.")
    convert.add_argument("--garak-threshold", type=float, default=0.5, help="garak eval_threshold of the run. A detector score >= threshold is a FAIL. garak does not record it. Default: 0.5.")
    convert.add_argument("--promptfoo-eval-id", action="append", metavar="ID", help="With a promptfoo.db, keep only this eval (run) ID. Repeatable. Default: every run that has results.")
    pyrit = convert.add_argument_group("PyRIT options")
    pyrit.add_argument("--pyrit-label", action="append", metavar="KEY=VALUE", type=_key_value, help="Keep only attacks or conversations with this memory label (e.g. op_name=nightly). Repeatable, all must match.")
    pyrit.add_argument("--pyrit-scenario-id", action="append", metavar="ID", help="Keep only attacks of this ScenarioResult ID. Repeatable.")
    pyrit.add_argument("--pyrit-conversation-id", action="append", metavar="ID", help="Keep only this conversation ID. Repeatable.")
    pyrit.add_argument("--pyrit-since", metavar="TIMESTAMP", help="Keep only attacks at or after this timestamp, e.g. '2026-10-14' or '2026-10-14 08:00:00'.")
    pyrit.add_argument("--pyrit-all-conversations", action="store_true", help="Without attack results, also keep conversations that have no score.")
    pyrit.add_argument("--pyrit-true-is-safe", action="store_true", help="Without attack results, read true_false score 'true' as safe (e.g. a refusal scorer). Default: 'true' means the objective was achieved (FAIL).")
    pyrit.add_argument("--pyrit-float-threshold", type=float, default=0.5, help="Without attack results, a float_scale score >= threshold is a FAIL. Default: 0.5.")
    convert.set_defaults(func=cmd_convert)

    for name, help_text in (("projects", "List Hub projects as JSON."), ("agents", "List the agents of a Hub project as JSON."), ("upload", "Upload SuiteResult JSON files to Hub, one evaluation per file.")):
        command = sub.add_parser(name, help=help_text, description=help_text)
        command.add_argument("--env-file", default=".env", help="File with GISKARD_HUB_BASE_URL and GISKARD_HUB_API_KEY. Environment variables win. Default: .env.")
        if name == "agents":
            command.add_argument("project_id")
        if name == "upload":
            command.add_argument("files", nargs="+", help="Files written by the convert command.")
            command.add_argument("--project-id", required=True)
            command.add_argument("--agent-id", help="Optional Hub agent to link the evaluations to.")
            command.add_argument("--name", help="Evaluation name, for a single file. Default: '<tool> results (<date>)'.")
            command.add_argument("--auto-classify-failures", action="store_true", help="Ask the Hub to classify the failure category of each failed scenario.")
            command.add_argument("--max-upload-mb", type=float, help="Split each file into several evaluations of at most this size. Use it when the Hub rejects a large upload. By default, each file is uploaded in one request.")
        command.set_defaults(func={"projects": cmd_projects, "agents": cmd_agents, "upload": cmd_upload}[name])

    opts = parser.parse_args()
    try:
        opts.func(opts)
    except Exception as exc:  # noqa: BLE001 -- the calling agent reads one JSON error instead of a traceback
        frames = traceback.extract_tb((exc.__cause__ or exc).__traceback__)
        own = [f for f in frames if f.filename == __file__] or frames
        emit({"error": f"{type(exc).__name__}: {exc}", "location": f"{own[-1].name}, line {own[-1].lineno}" if own else None})
        sys.exit(1)


if __name__ == "__main__":
    main()
