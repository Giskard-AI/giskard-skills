# Giskard Checks API reference (core)

Shared API surface for all skills. Domain-specific notes:

- RAG: [`rag-evaluator/references/api-reference.md`](../rag-evaluator/references/api-reference.md)
- Text-to-SQL: [`text2sql-evaluator/references/api-reference.md`](../text2sql-evaluator/references/api-reference.md)
- Adversarial: [`scenario-generator/references/api-reference.md`](../scenario-generator/references/api-reference.md)

Full docs: [Checks reference](https://docs.giskard.ai/oss/checks/reference/checks).

## Imports

```python
from giskard.checks import (
    Scenario, Suite, UserSimulator,
    FnCheck, StringMatching, RegexMatching,
    Equals, GreaterEquals, LesserThan, SemanticSimilarity,
    Groundedness, AnswerRelevance, Conformity, LLMJudge,
    AllOf, AnyOf, Not,
    set_default_generator,
)
from giskard.agents.generators import Generator

set_default_generator(Generator(model="openai/gpt-4o-mini"))
```

## Target (system under test)

Pass the user's agent to `suite.run(target=...)` — not as `outputs=` in each `.interact()`.

```python
def your_agent(inputs: str) -> str | dict:
    ...

result = await suite.run(target=your_agent)
```

**Injectable parameter names only:** `inputs`, optional `trace`. Names like `query` are NOT injected.

For async SDKs: `async def your_agent(inputs):` and await inside.

## Scenario and Suite

```python
scenario = (
    Scenario("name")  # never pass inputs/checks as constructor kwargs
    .interact(inputs="...")
    .check(FnCheck(name="...", fn=lambda trace: ...))
)

suite = Suite(name="my_suite")
suite.append(scenario)
result = await suite.run(target=your_agent)
result.print_report()
```

**Multi-turn** = multiple `.interact()` steps on one shared `trace`. Put `.check()` **after each** `.interact()` so failures name the turn — see [Multi-Turn Scenarios](https://docs.giskard.ai/oss/checks/tutorials/multi-turn) and [`multi-turn-scenarios.md`](./multi-turn-scenarios.md).

```python
Scenario("two_step")
.interact(inputs="First message.")
.check(FnCheck(name="step1_ok", fn=lambda trace: ...))
.interact(inputs="Follow-up.")
.check(FnCheck(name="step2_ok", fn=lambda trace: ...))
```

## Trace keys

| Key | Use |
|-----|-----|
| `trace.last.outputs` | Latest agent output |
| `trace.last.inputs` | Latest user input |
| `trace.interactions[i]` | Specific turn (static chains only) |
| `trace.last.metadata` | Latency, persona tags, reference answers |

For dict outputs: `trace.last.outputs["answer"]`, `trace.last.outputs["queries"]`, etc.

## UserSimulator

```python
sim = UserSimulator(
    persona="...",
    goal="...",
    max_steps=4,
)
Scenario("multi_turn").interact(inputs=sim).check(...)
```

- `max_steps=1` per simulator when chaining distinct roles across `.interact()` steps.
- Higher `max_steps` for phased dialogue within one `.interact()`.
- **Different persona per step**: `.interact(inputs=sim_a).interact(inputs=sim_b)` — each step can use a different `UserSimulator`, static string, or `lambda trace: ...` ([`multi-turn-scenarios.md`](./multi-turn-scenarios.md)).
- **One `target` per scenario run** — all dynamic steps share `suite.run(target=...)`; compare agents with separate scenarios or runs, not per-`.interact()` targets.

## Check quick reference

| Check | Template? | Notes |
|-------|-----------|-------|
| `FnCheck` | — | Receives `Trace` |
| `Conformity` | Plain text rule | Not Jinja2 |
| `LLMJudge` | Jinja2 prompt | `{{ trace.last.inputs }}`, `{{ trace.last.outputs }}` |
| `Groundedness` | — | Static `context=[...]` OR dynamic `context_key=...` |
| `AnswerRelevance` | — | Defaults to last inputs/outputs |

## See also

- [`generated-code-rules.md`](./generated-code-rules.md)
- [`checks-catalog-core.md`](./checks-catalog-core.md)
- [`multi-turn-scenarios.md`](./multi-turn-scenarios.md)
