# Mapping reference

Use this reference to explain a converted suite, or to fix the converter when a tool changes its format.

## Target format

The converter writes one Giskard OSS `SuiteResult` per tool. It uses these classes from `giskard.checks`:

| Level | Class | What the converter puts in it |
| --- | --- | --- |
| Suite | `SuiteResult` | All the scenarios of one tool. `duration_ms` is the run time if the tool records it, else 0. |
| Scenario | `ScenarioResult` | One test unit of the tool, such as one garak attempt generation or one PyRIT attack. It has one step and the tags. |
| Step | `TestCaseResult` | The check results, and `last_interaction_index` set to the last interaction. |
| Check | `CheckResult` | One verdict. `details["check_name"]` names it. `message` holds the reason. `metrics` holds the numeric scores. |
| Trace | `Trace` | `interactions` holds the conversation. `annotations` holds the source identifiers and the tool metadata. |
| Interaction | `Interaction` | `inputs` is `{"messages": [{"role": "user", "content": <text sent to the target>}]}`. `outputs` is `{"response": {"role": "assistant", "content": <reply>}}`. `metadata` holds per-turn data. |

The output file is `SuiteResult.to_hub_format()`. Load it again with `SuiteResult.model_validate_json(...)`. After a reload, `final_trace` is a plain dict.

## Rules

- Statuses follow Giskard. PASS means the target resisted or the assertion passed. FAIL means a vulnerability or a failed assertion. ERROR means the tool could not reach a verdict because of an error. SKIP means the tool gave no score.
- Never let a tool error become a FAIL. A FAIL must always mean that the tool saw the target fail.
- Tags use `key:value`, so `SuiteResult.group_by(key)` works. Every scenario has `tool:<tool>`.
- Keep every source field that can help a reviewer. Put per-turn data in the interaction metadata, and everything else in the annotations. The `compact` helper removes empty values.
- Pair turns with `pair_turns`. It makes one interaction per user turn and its reply, and it returns the system prompts separately. Put the system prompts in the annotations.
- `make_scenario` writes each interaction in the Hub Chat format. The Hub UI shows chat bubbles only for this format, and the Hub SDK cannot read plain-string interactions back. Content that is not text becomes JSON text, because Chat content is a string.

## What Giskard Hub keeps

`hub.evaluations.upload` makes one Hub result per scenario. The Hub keeps the tags, the trace annotations, each interaction (inputs, outputs, metadata), and each check (status, message, details, metrics). It adds each metric to the check details under the metric name. It takes the check name from `details["check_name"]`.

The Hub does not keep `scenario_name`, `duration_ms`, or `recommendation`. For this reason, the converter copies the scenario name into the annotations. Do not use the detail keys `check_kind`, `check_spec`, `inputs`, or `target`, because the Hub reads them for its own checks.

## garak

| Item | Mapping |
| --- | --- |
| Input | `<prefix>.report.jsonl`. The script reads it line by line. |
| Scenario | One per attempt and generation. Each attempt appears twice (status 1, then status 2), so the script keeps the line with the highest status for each `uuid`. |
| Interactions | The turns of `conversations[i]`, or `messages[i]` before garak 0.13. In garak 0.9 and older, `prompt` and `outputs[i]` are plain strings. |
| Checks | One per detector in `detector_results`. A score at or above the threshold (default 0.5) is a FAIL. A `None` score is a SKIP. An attempt with no detector results gets one SKIP check. |
| Tags | `probe:<probe>`, the probe tags from `plugin_cache` or the digest (`owasp:llm01`, `avid-effect:...`, `quality:...`, and others), and `intent:<code>`. |
| Annotations | garak version, run ID, target, start time, attempt UUID and sequence, goal, intent, probe description, tier, severity, triggers, attempt notes, system prompt, and reverse translation. |

## promptfoo

| Item | Mapping |
| --- | --- |
| Input | The `-o` JSON `OutputFile`, the JSONL lines, or the `{"data": ...}` share wrapper. Results version 2 and 3 both work. |
| Scenario | One per result row. A row is one test for one provider, prompt, and repeat. |
| Interactions | `response.metadata.messages` for multi-turn strategies. Otherwise one interaction from `redteamFinalPrompt`, `response.prompt`, or `prompt.raw`, with `response.output`. Latency, tokens, cost, and guardrails go into the metadata of the last interaction. |
| Checks | One per item of `gradingResult.componentResults`, named by the assertion metric or type. A test with a `threshold` gets one overall check, because promptfoo combines the assertions. `failureReason` 2 is an ERROR. The `error` field alone does not mean an error, because promptfoo also fills it for failed assertions. |
| Tags | `plugin`, `strategy` (`basic` when absent), `severity`, `harm-category`, `provider`, `metric`, and the config tags. |
| Annotations | Eval ID, promptfoo version, description, vars, test metadata, success, score, failure reason, red-team history, and response metadata. |

## DeepTeam

| Item | Mapping |
| --- | --- |
| Input | The JSON from `RiskAssessment.save()`. Keys can be snake_case or camelCase. |
| Scenario | One per item of `test_cases`. |
| Interactions | `turns` for multi-turn attacks. Otherwise `input` and `actual_output`. |
| Checks | One check named `<vulnerability>/<vulnerability_type>`. `error` is an ERROR. A `None` score is a SKIP. A score above 0 is a PASS, and 0 is a FAIL. |
| Tags | `vulnerability`, `vulnerability-type`, `attack-method`, and `risk-category`. |
| Annotations | Reason, CVSS score, costs, metadata, and the other non-empty fields. The `overview` counts are not used, because DeepTeam computes some of them incorrectly. |

## PyRIT

| Item | Mapping |
| --- | --- |
| Input | The SQLite memory database `pyrit.db`, which has the most data. Also `export_conversations` JSON (PyRIT 0.14 and older), `AttackResult` JSON dumps, and `ScenarioResult` JSON dumps. DuckDB (PyRIT 0.9 and older) and Azure SQL need a JSON export. |
| Scenario | One per row of `AttackResultEntries`. Without attack results, one per conversation that has scores. |
| Interactions | The pieces of `conversation_id`, grouped by `sequence`. `inputs` is the converted value that the target received. The original value, the converters, the errors, and the scores of each piece go into the metadata. |
| Checks | One check named after the objective scorer. The `outcome` gives the status. `success` (objective achieved) is a FAIL, `failure` is a PASS, `error` is an ERROR, and `undetermined` is a SKIP. Without attack results, each score is a check, and `true` or a float at or above 0.5 is a FAIL. |
| Tags | `attack`, `scenario`, `attack-group`, `harm-category`, and the memory labels. |
| Annotations | Objective, attack result ID, conversation ID, target, converters, labels, turns, timing, the adversarial chat transcript, and the PyRIT scenario. |

The database opens read-only. Rows that no attack result references, such as scorer conversations, are not converted.

## Size limits

The converter keeps the whole suite in memory. These measurements come from large copies of real files:

| Tool | Input | Scenarios | Time | Peak memory | Output |
| --- | --- | --- | --- | --- | --- |
| garak | 99 MB `report.jsonl` | 22,000 | 5 s | 1.0 GB | 105 MB |
| promptfoo | 291 MB red-team JSON | 8,000 | 6 s | 1.9 GB | 222 MB |
| DeepTeam | 48 MB JSON | 8,000 | 2 s | 0.8 GB | 71 MB |
| PyRIT | 125 MB `pyrit.db` | 5,000 | 5 s | 0.8 GB | 71 MB |

The garak report is read line by line. The other JSON inputs are loaded at once. The PyRIT database is read with one query per 500 IDs, because its columns have no index and the database opens read-only.

The upload command splits each suite into parts of at most 8 MB, and each part becomes one evaluation. It does not retry a failed upload, because a retry can create a duplicate evaluation.

## Change the converter

The script has one function for each tool, `convert_<tool>(path, opts)`. It returns `(scenarios, duration_ms)` and is registered in `CONVERTERS`. Build scenarios only with `make_scenario` and checks only with `make_check`. These helpers create real `giskard.checks` objects, so an invalid result fails at once.

To support a new format version, change only the code of that tool: `convert_<tool>` and its `_<tool>_` helpers. Read a few records of the file to learn the new keys. Keep the rules above, and keep the old format working. Add a small fixture for the new format to the test file, then run `python test_third_party_to_giskard.py <path to the changed script>`. Work on copies in the working directory, not on the installed skill.
