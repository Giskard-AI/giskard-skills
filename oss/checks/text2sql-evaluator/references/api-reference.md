# Giskard Checks API reference (text-to-SQL)

> Shared API surface: [`../../references/api-reference-core.md`](../../references/api-reference-core.md)

Text-to-SQL-specific notes below. For when to use each check, see [`checks-catalog.md`](./checks-catalog.md). Full docs: [Checks reference](https://docs.giskard.ai/oss/checks/reference/checks). Adversarial: `scenario-generator` skill.

## Imports

```python
from giskard.checks import (
    Scenario, Suite, UserSimulator,
    FnCheck, RegexMatching, StringMatching,
    Equals, GreaterEquals, LesserThan, SemanticSimilarity,
    AnswerRelevance, Conformity, LLMJudge,
    AllOf, AnyOf, Not,
    set_default_generator,
)
from giskard.agents.generators import Generator
```

## Target (system under test)

```python
def your_agent(inputs: str) -> dict:
    """Preferred shape for tool-usage evals."""
    return {"answer": "...", "queries": [{"sql": "...", "success": True, "blocked": False}]}

await suite.run(target=your_agent)
```

Injectable parameters: **`inputs`**, optional **`trace`**. Names like `query` are not injected.

## Checks used most often

### FnCheck on `queries[]`

```python
FnCheck(
    name="executed_query",
    fn=lambda trace: len((trace.last.outputs or {}).get("queries") or []) > 0,
)
```

`fn` receives a **`Trace`**, not the output string.

### AnswerRelevance

```python
AnswerRelevance(
    name="relevant",
    context="Analytics assistant over <describe database scope>.",
)
```

### RegexMatching on SQL

Point `text_key` at your SQL field inside `trace.last.outputs` (adjust path to your schema).

### LLMJudge

Jinja2 `prompt` with `{{ trace.last.inputs }}`, `{{ trace.last.outputs }}` — use when `FnCheck` cannot encode the rule.

### Conformity

Plain-text `rule=` — not Jinja2. Use sparingly for subjective policies; not for exact counts or refusals.

## UserSimulator

See [`simulate-users.md`](./simulate-users.md). Requires `set_default_generator(...)`.

## Multi-turn

Each `.interact()` is a turn. Checks after a turn evaluate that turn. Inspect `trace.interactions[i]` for per-turn `FnCheck`s.

## Persistence

```python
Path("results.json").write_text(result.model_dump_json(indent=2))
```

## Common pitfalls

- `Scenario("x", checks=[...])` is ignored — use `.check(...)`.
- `StringMatching(expected=False)` is silently ignored — use `Not(StringMatching(...))`.
- `SemanticSimilarity(reference=...)` wrong field names — use `reference_text=` and `actual_answer_key=`.
- Async SDK: use `async def your_agent(inputs)` if sync wrapper deadlocks inside giskard's loop.

## See also

- [`tool-usage.md`](./tool-usage.md) — `queries[]` contract
- [`sql-safety.md`](./sql-safety.md) — guardrails vs suite checks
- `scenario-generator/references/api-reference.md` — full shared API + adversarial patterns
