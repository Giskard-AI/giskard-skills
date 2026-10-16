# Mapping reference

Use this reference to explain a converted suite, or to fix the converter when a tool changes its format.

## Inputs and counts

| Tool | Where to find the file | Notes | The tool's own counts |
| --- | --- | --- | --- |
| garak | `~/.local/share/garak/garak_runs/` | Use the `report.jsonl`, not the hitlog or the HTML report. garak does not record a custom `eval_threshold`, so pass `--garak-threshold`. | The `eval` lines, per probe and detector. |
| promptfoo | The `-o` path, `promptfoo export eval latest -o results.json`, or `~/.promptfoo/promptfoo.db` | CSV, HTML, XML, and YAML outputs are not supported. The database keeps every run. Use `--promptfoo-eval-id`. | `results.stats`, or the `success` and `failure_reason` columns of `eval_results` |
| DeepTeam | The folder given to `save()` or `-o` | Results that exist only in Confident AI cannot be converted. | The `test_cases` list. The `overview` counts are not reliable. |
| PyRIT | `dbdata/pyrit.db` in the user data folder or the PyRIT repository | The database keeps every run. Use the `--pyrit-*` filters. DuckDB and Azure SQL need an `export_conversations` JSON file. | The `outcome` column of `AttackResultEntries`. |

## Target format

The converter writes one Giskard OSS `SuiteResult` per tool. It uses these classes from `giskard.checks`:

| Level | Class | What the converter puts in it |
| --- | --- | --- |
| Suite | `SuiteResult` | All the scenarios of one tool. `duration_ms` is the run time if the tool records it, else 0. |
| Scenario | `ScenarioResult` | One test unit of the tool, such as one garak attempt generation or one PyRIT attack. It has one step and the tags. |
| Step | `TestCaseResult` | The check results, and `last_interaction_index` set to the last interaction. |
| Check | `CheckResult` | One verdict. `details["check_name"]` names it. `message` holds the reason. `metrics` holds the numeric scores. |
| Trace | `Trace` | `interactions` holds the conversation. `annotations` holds the source identifiers and the tool metadata. |
| Interaction | `Interaction` | Chat format: `inputs` is `{"messages": [{"role": "user", "content": <text sent to the target>}]}` and `outputs` is `{"response": {"role": "assistant", "content": <reply>}}`. Structured format: `inputs` and `outputs` are the objects of a Structured agent. `metadata` holds per-turn data. |

The output file is `SuiteResult.to_hub_format()`. Load it again with `SuiteResult.model_validate_json(...)`. After a reload, `final_trace` is a plain dict.

## Rules

- Statuses follow Giskard. PASS means the target resisted or the assertion passed. FAIL means a vulnerability or a failed assertion. ERROR means the tool could not reach a verdict because of an error. SKIP means the tool gave no score.
- Never let a tool error become a FAIL. A FAIL must always mean that the tool saw the target fail.
- Tags use `key:value`, so `SuiteResult.group_by(key)` works. Every scenario has `tool:<tool>`.
- Scenario names are unique in a suite. The `convert` command adds ` (1)`, ` (2)`, and so on to names that repeat, for example the same test in several runs.
- Check names are unique in a scenario. `make_scenario` adds ` #1`, ` #2`, and so on to check names that repeat, such as two `contains` assertions or one PyRIT score per turn, and renames their metrics the same way.
- Problems that do not stop the conversion, such as an incomplete last line, go into the `warnings` list of the summary.
- Keep every source field that can help a reviewer. Put per-turn data in the interaction metadata, and everything else in the annotations. The `compact` helper removes empty values.
- Pair turns with `pair_turns`. It makes one interaction per user turn and its reply, and it returns the system prompts separately. Put the system prompts in the annotations.
- `make_scenario` keeps a dict input or output as an object, in the Hub Structured format. It writes all other content in the Hub Chat format. The Hub UI shows chat bubbles only for Chat, and the Hub SDK cannot read plain-string interactions back. Lists and other content that is not text become JSON text, because Chat content is a string. Give a dict only when the tool recorded the object that the target received or returned.

## What Giskard Hub keeps

`hub.evaluations.upload` makes one Hub result per scenario. The Hub keeps the tags, the trace annotations, each interaction (inputs, outputs, metadata), and each check (status, message, details, metrics). It adds each metric to the check details under the metric name. It takes the check name from `details["check_name"]`.

The Hub does not keep `scenario_name`, `duration_ms`, or `recommendation`. For this reason, the converter copies the scenario name into the annotations. Do not use the detail keys `check_kind`, `check_spec`, `inputs`, or `target`, because the Hub reads them for its own checks.

## garak

| Item | Mapping |
| --- | --- |
| Input | `<prefix>.report.jsonl`. The script reads it line by line. An interrupted run can end with an incomplete line. The script skips that last line and adds a warning. A broken line before the end fails the conversion. |
| Scenario | One per attempt and generation. Each attempt appears twice (status 1, then status 2), so the script keeps the line with the highest status for each `uuid`. |
| Interactions | The turns of `conversations[i]`, or `messages[i]` before garak 0.13. In garak 0.9 and older, `prompt` and `outputs[i]` are plain strings. |
| Checks | One per detector in `detector_results`. A score at or above the threshold (default 0.5) is a FAIL. A `None` score is a SKIP. An attempt with no detector results gets one SKIP check. |
| Tags | `probe:<probe>`, the probe tags from `plugin_cache` or the digest (`owasp:llm01`, `avid-effect:...`, `quality:...`, and others), and `intent:<code>`. |
| Annotations | garak version, run ID, target, start time, attempt UUID and sequence, goal, intent, probe description, tier, severity, triggers, attempt notes, system prompt, and reverse translation. |

## promptfoo

| Item | Mapping |
| --- | --- |
| Input | The `-o` JSON `OutputFile`, the JSONL lines, or the `{"data": ...}` share wrapper. Results version 2 and 3 both work. The SQLite database `promptfoo.db` also works. It opens read-only, and each row of `evals` with rows in `eval_results` becomes one run. Runs saved before results version 4 are skipped with a warning, because their rows are in `evals.results`. Export them to JSON to convert them. Rows without any of `success`, `gradingResult`, `response`, `testCase`, or `failureReason` are not promptfoo results and are ignored, so a file of another tool gives no scenarios. |
| Scenario | One per result row. A row is one test for one provider, prompt, and repeat. With several prompts, the name numbers the distinct prompt labels, because `promptIdx` counts the prompt and provider columns. |
| Interactions | `response.metadata.messages` for multi-turn strategies. Otherwise one interaction from `redteamFinalPrompt`, `response.prompt`, or `prompt.raw`, with `response.output`. A chat prompt saved as JSON text (a list of `role` and `content` messages) becomes turns, and its system message goes into the annotations. When `response.output` is an object and the test has `vars`, the interaction is Structured: `inputs` is the `vars`, which fill the request body, and `outputs` is the object. Message fields such as `tool_calls` and `tool_call_id` go into the metadata. A message with only tool calls shows the calls as JSON text. Latency, tokens, cost, and guardrails go into the metadata of the last interaction. |
| Checks | One per item of `gradingResult.componentResults`, named by the assertion metric or type. A test with a `threshold` gets one overall check, because promptfoo combines the assertions. `failureReason` 2 is an ERROR. The `error` field alone does not mean an error, because promptfoo also fills it for failed assertions. |
| Tags | `eval-id`, `plugin`, `strategy` (`basic` when absent), `severity`, `harm-category`, `provider`, `metric`, and the config tags. |
| Annotations | Eval ID, promptfoo version, description, vars, test metadata, success, score, failure reason, red-team history, and response metadata. |

## DeepTeam

| Item | Mapping |
| --- | --- |
| Input | The JSON from `RiskAssessment.save()`. DeepTeam 0.2.1 and older write `riskCategory`, `attackMethod`, and `actualOutput`. Newer versions write DeepTeam's own fields in snake_case and the fields inherited from deepeval in camelCase, such as `toolsCalled` and `retrievalContext`. The list is always `test_cases`. |
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
| Checks | One check named after the objective scorer. The `outcome` gives the status. `success` (objective achieved) is a FAIL, `failure` is a PASS, `error` is an ERROR, and `undetermined` is a SKIP. Without attack results, each score is a check, and `true` or a float at or above 0.5 is a FAIL. A conversation without scores whose pieces have a `response_error` other than `none` gets one ERROR check. |
| Tags | `attack`, `scenario`, `attack-group`, `harm-category`, and the memory labels. When the attack result has no attack identifier, as for errors in PyRIT 0.14, the attack comes from the pieces. |
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

The garak report is read line by line. The other JSON inputs are loaded at once. The PyRIT database is read with one query per table, with all the IDs in one JSON array parameter, because its columns have no index and the database opens read-only.

The upload command sends each suite in one request. Hubs have different size limits, and an oversized request can fail with a generic server error. With `--max-upload-mb`, the command splits each suite into parts of at most that size, and each part becomes one evaluation. In a test, an 18 MB suite uploaded as three 8 MB parts, and a single 105 MB request failed. The command does not retry a failed upload, because a retry can create a duplicate evaluation.

## Change the converter

The script has one function for each tool, `convert_<tool>(path, opts)`. It returns `(scenarios, duration_ms)` and is registered in `CONVERTERS`. Build scenarios only with `make_scenario` and checks only with `make_check`. These helpers create real `giskard.checks` objects, so an invalid result fails at once.

To support a new format version, change only the code of that tool: `convert_<tool>` and its `_<tool>_` helpers. Read a few records of the file to learn the new keys. Keep the rules above, and keep the old format working. Add a small fixture for the new format to the test file, then run `python test_third_party_to_giskard.py <path to the changed script>`. Work on copies in the working directory, not on the installed skill.
