# Giskard Checks API Reference (RAG-focused)

Subset of the `giskard.checks` API most relevant to RAG evaluation. For the complete API see the giskard-checks README. For attack-pattern coverage and adversarial scenarios, see the `scenario-generator` skill.

## Imports

```python
# Core
from giskard.checks import (
    Scenario, Suite, Step,
    Trace, Interact, Interaction, InteractionSpec,
    Check, CheckResult, CheckStatus,
    Metric,
)

# Built-in checks (rule-based, semantic)
from giskard.checks import (
    Equals, NotEquals, LesserThan, GreaterThan, LesserThanEquals, GreaterEquals,
    FnCheck, from_fn,
    StringMatching, RegexMatching,
    SemanticSimilarity,
    AllOf, AnyOf, Not,
)

# LLM-based checks
from giskard.checks import (
    LLMJudge, Conformity, Groundedness, AnswerRelevance,
    BaseLLMCheck, LLMCheckResult,
)

# Generator config
from giskard.checks import set_default_generator, get_default_generator
from giskard.agents.generators import Generator
```

## Target (System Under Test)

The `target` is the user's RAG agent callable. Pass it to `suite.run(target=...)` so `.interact()` only specifies inputs.

```python
def my_rag_agent(inputs: str) -> str:
    return "answer"

# Or returning structured output for dynamic groundedness:
def my_rag_agent(inputs: str) -> dict:
    return {"answer": "...", "context": ["chunk1", "chunk2"]}

result = await suite.run(target=my_rag_agent)
```

**Required parameter names** (giskard injects by name):
- `inputs`: the resolved input from `.interact(inputs=...)`
- `trace`: optional, the full conversation history
- Other parameter names will NOT be injected. Don't use `query`, `question`, etc.

**Sync or async** both work: `def my_agent(inputs)` or `async def my_agent(inputs)`.

## Scenario

```python
scenario = (
    Scenario("scenario_name")
    .interact(inputs="What is the capital of France?")
    .check(...)
    .check(...)
)
```

- `Scenario(name)`: name is required and shown in the report
- `.interact(inputs=...)`: pass a string, callable, generator, or `UserSimulator`. Multiple `.interact()` calls = multi-turn.
- `.check(check_instance)`: chain as many as needed; stops at first failure within the same step

NEVER pass `inputs`, `checks`, or `description` as `Scenario(...)` constructor kwargs; they are silently ignored.

## Suite

```python
suite = Suite(name="my_suite")
suite.append(scenario)
suite.append(another_scenario)

result = await suite.run(target=my_agent)
result.print_report()
print(f"Pass rate: {result.pass_rate * 100:.1f}%")
```

`SuiteResult` has:
- `pass_rate: float`: fraction of scenarios that passed
- `results: list[ScenarioResult]`: per-scenario detail
- `print_report()`: pretty-print to console
- `model_dump_json()`: serialize to JSON for CI / persistence

## Groundedness (LLM-based)

Validates that the answer is supported by the provided context. **The most important RAG check.**

```python
# Static context (same for every run of this scenario)
Groundedness(
    name="grounded",
    context=["chunk 1 from KB", "chunk 2 from KB"],
    answer_key="trace.last.outputs",
)

# Dynamic context from the agent's output
Groundedness(
    name="grounded",
    context_key="trace.last.outputs.context",
    answer_key="trace.last.outputs.answer",
)

# Dynamic context from interaction metadata
# Default! `context_key` defaults to "trace.last.metadata.context"
Groundedness(name="grounded")
# Then in your scenario:
.interact(
    inputs="What is X?",
    metadata={"context": ["retrieved chunk"]},
)
```

Fields:
- `context: str | list[str] | None`: static context; if set, takes priority over `context_key`
- `context_key: str`: JSONPath; default `"trace.last.metadata.context"`
- `answer: str | None`: static answer; usually unused for live SUTs
- `answer_key: str`: JSONPath; default `"trace.last.outputs"`

## AnswerRelevance (LLM-based)

Validates that the answer addresses the question. Multi-turn aware: only the *current* turn is scored, but prior turns are passed as history so the judge understands intent.

```python
AnswerRelevance(
    name="relevant",
    # Defaults are usually correct:
    # question_key="trace.last.inputs",
    # answer_key="trace.last.outputs",
    context="This is a chatbot that answers questions about our internal HR policies.",
)
```

Fields:
- `question_key: str`: default `"trace.last.inputs"`
- `answer_key: str`: default `"trace.last.outputs"`
- `context: str | None`: domain description; helps the judge calibrate "relevant" to the agent's scope. NOT extracted from the trace.

## Conformity (LLM-based)

Validates the answer against a plain-text rule. Use for behavioral expectations: "must cite", "must decline if uncertain", "must respond in English".

```python
Conformity(
    name="declines_when_unsupported",
    rule="When the agent does not have information to answer, it must explicitly decline rather than guessing. Confident answers without supporting context fail this check.",
)
```

Fields:
- `rule: str`: plain text. NOT a Jinja2 template. Receives the full Trace automatically.

## LLMJudge (LLM-based)

Custom LLM judgment with a Jinja2 prompt. Use when no built-in check fits.

```python
LLMJudge(
    name="answer_matches_gold",
    prompt="""
Compare the agent's answer to the gold answer. Pass if they convey the same factual information, even if worded differently.

Question: {{ trace.last.inputs }}
Agent answer: {{ trace.last.outputs }}
Gold answer: The capital of France is Paris.

Return passed=true if the agent's answer conveys "Paris is the capital of France"; passed=false otherwise.
""",
)
```

Fields:
- `prompt: str`: Jinja2 template; render with full trace context

## Built-in (rule-based) Checks

```python
# Keyword presence/absence
StringMatching(keyword="Paris", text_key="trace.last.outputs", expected=True)
StringMatching(keyword="medical advice", text_key="trace.last.outputs", expected=False)

# Regex
RegexMatching(pattern=r"\[\d+\]", text_key="trace.last.outputs")  # checks for citation markers

# Equality / comparison
Equals(expected_value="Paris", key="trace.last.outputs")
LesserThan(threshold=500, key="trace.last.outputs.length")

# Custom function: receives Trace, NOT the output string
FnCheck(
    name="answer_non_empty",
    fn=lambda trace: len(trace.last.outputs) > 0,
)

# Composition
AllOf(name="all_pass", checks=[check1, check2])
AnyOf(name="grounded_or_refused", checks=[grounded_check, refusal_check])
Not(name="not_empty", check=empty_check)
```

## SemanticSimilarity

Embedding-based similarity to a reference string.

```python
SemanticSimilarity(
    name="matches_gold",
    reference="The capital of France is Paris.",
    text_key="trace.last.outputs",
    threshold=0.85,
)
```

## Multi-turn scenarios

```python
scenario = (
    Scenario("multi_turn_rag")
    .interact(inputs="What is the company's vacation policy?")
    .check(Groundedness(name="grounded_1", context=[...]))
    .interact(inputs="And how does it work for new hires?")  # follow-up
    .check(Groundedness(name="grounded_2", context=[...]))
    .check(AnswerRelevance(name="relevant_2"))
)
```

Each `.interact()` is a turn. Checks placed after a turn evaluate that turn's interaction. `trace.interactions[i]` accesses turn `i`.

## Configuring the LLM generator

LLM-backed checks (`Groundedness`, `AnswerRelevance`, `Conformity`, `LLMJudge`) need a generator.

```python
# Global default (recommended)
set_default_generator(Generator(model="openai/gpt-4o-mini"))

# Per-check override
Groundedness(
    name="grounded",
    generator=Generator(model="openai/gpt-4o"),  # use a stronger judge for one check
    context=[...],
)
```

For best speed/cost: use a small fast model for evals (`gpt-4o-mini`, `gemini-2.0-flash`, `claude-haiku-4-5`). Judging is cheaper than generating, and the judge does not need to be the same model as the agent.

## Persistence (CI-friendly)

```python
from pathlib import Path

result = await suite.run(target=my_agent)
result.print_report()
Path("rag_results.json").write_text(result.model_dump_json(indent=2))
```

For pytest / CI integration: `giskard.checks.export.junit` provides JUnit XML export, useful for surfacing per-check pass/fail in CI dashboards.

## Common Pitfalls

- **Empty Suite passes instantly**: `Scenario("name", checks=[...])` is silently ignored; use `.check(...)` instead.
- **Agent isn't called**: parameter is named `query` instead of `inputs`; only `inputs` and `trace` are injected.
- **Groundedness always passes / always fails**: forgot `set_default_generator(...)`, or `context` and `context_key` both set with `context` empty.
- **`AnswerRelevance` returns "relevant" for off-topic answers**: pass a `context="..."` describing the agent's domain so the judge has scope to ground its decision.
- **`FnCheck` errors on `trace.last.outputs`**: `fn` receives a Trace object, not a string. Use `lambda trace: ... trace.last.outputs ...`, not `lambda outputs: ...`.
