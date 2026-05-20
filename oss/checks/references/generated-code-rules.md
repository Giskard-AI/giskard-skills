# Rules for generated code

Subtle violations cause silent failures. Follow these rules in every skill that emits `giskard.checks` code.

## Imports and setup

- ALWAYS use `from giskard.checks import ...` for all check classes; they are re-exported there.
- ALWAYS call `set_default_generator(Generator(model="..."))` before LLM-backed checks (`Groundedness`, `AnswerRelevance`, `Conformity`, `LLMJudge`, `UserSimulator`). Without it, those checks fail at runtime.
- Install: `uv pip install --prerelease=allow 'giskard-checks>=1.0.2b3'` (Python 3.12+).

## Scenario and Suite API

- ALWAYS use the fluent builder: `Scenario("name").interact(...).check(...)`.
- NEVER pass `inputs`, `checks`, `description`, or `user` as constructor kwargs to `Scenario(...)` — they are silently ignored, producing empty scenarios that pass instantly.
- ALWAYS wrap scenarios in a `Suite`. Even one scenario goes in a `Suite` for `pass_rate`, `print_report()`, and consistent results.
- ALWAYS pass the SUT as `target=` to `suite.run(target=your_agent)`, NOT as `outputs=` in each `.interact()`.

## System under test (SUT)

- ALWAYS define injectable parameter names: `def your_agent(inputs): ...` or `def your_agent(inputs, trace): ...`. Names like `query` are NOT injected.
- ALWAYS add type hints matching the user's actual return type (`str` vs `dict`).
- For async SDKs that manage their own event loop: use `async def your_agent(inputs):` and await inside. Sync wrappers that call `asyncio.run()` deadlock when giskard already holds the loop — use `arun`, `ainvoke`, `aquery`, etc.

## Check conventions

- ALWAYS pass `name=` to every check. Unnamed checks show as "None" in reports.
- `FnCheck(fn=...)` receives a **`Trace`**, not the output string. Use `lambda trace: ... trace.last.outputs ...`.
- `Conformity(rule=...)` — plain text only, NOT Jinja2.
- `LLMJudge(prompt=...)` — Jinja2 template; use `{{ trace.last.inputs }}`, `{{ trace.last.outputs }}`.
- `Groundedness` with static context: pass `context=[...]` directly.
- `Groundedness` with dynamic context: pass `context_key="trace.last.outputs.context"` (or equivalent). Do NOT also pass `context=` — they conflict and `context=` wins.
- Use `trace.last.outputs` / `trace.last.inputs` for the latest turn; `trace.interactions[i]` only for static per-step chains.

## Multi-turn scenarios

- **Multi-turn API**: chain `.interact().check().interact().check()` on one `Scenario` (shared trace) — [tutorial](https://docs.giskard.ai/oss/checks/tutorials/multi-turn), [`multi-turn-scenarios.md`](./multi-turn-scenarios.md). Add a check after **each** `.interact()`, not only at the end.
- Default suite mix: ~40% static, ~40% phased/chained `UserSimulator`, ~20% safety dialogue. Do not emit static-only suites unless the user asked.
- **Phased**: one `.interact(inputs=sim)` with `max_steps` 4–8 and phase instructions in `persona=`.
- **Chained roles**: `.interact(inputs=sim_a).interact(inputs=sim_b)` with **`max_steps=1`** per simulator unless that role needs a mini-dialogue.
- On persona scenarios, add a length floor, e.g. `FnCheck(name="multi_turn", fn=lambda t: len(t.interactions) >= 3)`.
- Prefer **trace-pattern** `FnCheck`s when turn order varies; avoid fixed `trace.interactions[0]` for dynamic simulators.
- **Safety / refusal** in dialogue: scan all `trace.interactions` — never only `trace.last` (agent may refuse early then run safe SQL later).
- Never default to static `"Hello"` warm-up + simulator on turn 2.

## Output persistence

- Scripts: persist `SuiteResult` to JSON after `print_report()` (e.g. `Path("results.json").write_text(result.model_dump_json(indent=2))`).
- Notebooks: `print(result)` after `print_report()` for rich display.
- Add `# REPLACE: ...` wherever the user must customize.

## Domain-specific (evaluators)

- **RAG**: In-domain scenarios MUST include retrieval tool-usage `FnCheck` before `Groundedness` alone — see `rag-evaluator/references/tool-usage.md`.
- **Text-to-SQL**: In-domain data questions MUST include SQL tool-usage `FnCheck` on `queries[]` before answer judges — see `text2sql-evaluator/references/tool-usage.md`.
- **Text-to-SQL**: Test `validate_sql` deterministically in addition to agent scenarios.

## See also

- [`api-reference-core.md`](./api-reference-core.md) — imports, target wiring, trace keys
- [`multi-turn-scenarios.md`](./multi-turn-scenarios.md) — per-turn users, trace-pattern checks
