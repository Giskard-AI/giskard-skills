# Giskard Checks API Reference (RAG-focused)

Subset of the `giskard.checks` API most relevant to RAG evaluation, plus the `giskard.scan` quality-scan entry points. For the complete API see the [giskard-checks documentation](https://docs.giskard.ai/oss/checks). For full worked code that uses these primitives end-to-end, see [`examples.md`](./examples.md). For attack-pattern coverage and adversarial scenarios, see the `scenario-generator` skill.

Two conventions carry most of the weight:

1. **The value under test is always selected by `target_key`.** Every other JSONPath selector is named after its static sibling (`context` / `context_key`, `reference_text` / `reference_text_key`, `expected_value` / `expected_value_key`, `keyword` / `keyword_key`, `pattern` / `pattern_key`).
2. **Checks reject unknown fields.** `Check`, `InputGenerator` and `BaseGenerator` all set `extra="forbid"`, so a misspelled kwarg raises `pydantic.ValidationError` at construction time instead of silently falling back to a default.

## Installation

```bash
pip install "giskard[openai,scan]"   # or [anthropic,scan], [google,scan], [azure,scan]
```

Requires Python 3.12+. Bare `giskard-checks` installs the scenario API without any provider SDK, so LLM judges and embedding-backed checks fail at call time. The `scan` extra adds `quality_scan` / `vulnerability_scan`.

## Imports

```python
# Core
from giskard.checks import (
    Scenario, Step, Suite,
    Trace, Interact, Interaction, InteractionSpec,
    Check, CheckResult, CheckStatus,
    ScenarioResult, ScenarioStatus,
    SuiteResult, GroupedSuiteResult, GroupStats,
    TestCase, TestCaseResult, TestCaseStatus,
    Metric, Target, resolve,
)

# Built-in checks (rule-based, semantic)
from giskard.checks import (
    Equals, NotEquals,
    LessThan, LessThanEquals, GreaterThan, GreaterThanEquals,
    FnCheck, from_fn,
    StringMatching, RegexMatching,
    SemanticSimilarity,
    JsonValid, Readability,
    AllOf, AnyOf, Not,
)

# LLM-based checks
from giskard.checks import (
    LLMJudge, Conformity, Groundedness, AnswerRelevance,
    Contradiction, Toxicity,
    BaseLLMCheck, LLMCheckResult,
)

# Input generators and configuration
from giskard.checks import (
    UserSimulator, LLMGenerator, DatasetInputGenerator,
    set_default_generator, get_default_generator,
)
from giskard.agents import Generator

# Automatic knowledge-base quality scan (needs the `scan` extra)
from giskard.scan import Document, KnowledgeBase, quality_scan, generate_suite
```

`Readability` requires `pip install "giskard-checks[readability]"`.

## Target (System Under Test)

The `target` is the user's RAG agent callable. Pass it to `suite.run(target=...)` so `.interact()` only specifies inputs.

```python
def my_rag_agent(inputs: str) -> str:
    # your RAG agent code here
    return "answer"

result = await suite.run(target=my_rag_agent)
```

**Required parameter names** (giskard injects by name):

- `inputs`: the resolved input from `.interact(inputs=...)`
- `trace`: optional, the full conversation history
- Any other required parameter raises `TypeError: Parameter '<name>' is required but not in the injection requirements.` when the `Interact` is built. Wrap the user's function rather than passing it directly:

```python
def my_rag_agent(inputs: str) -> dict:
    return qa_chain.invoke({"question": inputs})
```

**Variants**:

- **Async**: `async def my_agent(inputs):` — required when the underlying SDK exposes an async API. A sync target that internally calls `asyncio.run()` fails with `RuntimeError: asyncio.run() cannot be called from a running event loop`, because the runner already owns the loop.
- **Structured output** (for dynamic groundedness): return `{"answer": "...", "context": [...]}`. Reference the fields via `target_key="trace.last.outputs.answer"` and `context_key="trace.last.outputs.context"` in checks.

**Target precedence** (highest to lowest): `suite.run(target=...)` > `Suite(target=...)` > `Scenario(target=...)` / `scenario.with_target(...)`. Prefer `suite.run(target=...)`.

## Scenario

```python
scenario = (
    Scenario("scenario_name")
    .interact(inputs="What is the capital of France?")
    .check(Groundedness(name="grounded", context=["Paris is the capital of France."]))
    .check(AnswerRelevance(name="relevant"))
    .with_tags(["Dimension:Groundedness"])
)
```

- `Scenario(name)`: name is required and shown in the report
- `.interact(inputs=..., outputs=MISSING, metadata=None)`: `inputs` accepts a string, structured value, callable, generator, or `UserSimulator`. Multiple `.interact()` calls = multi-turn. Pass `outputs=` only for pre-recorded interactions. `metadata=` attaches per-interaction data that checks can select (see `Groundedness`).
- `.check(check_instance)` / `.checks(*check_instances)`: chain as many as needed; all checks in a step run on the same trace, so failures don't suppress later checks in the same step. A failing step does skip subsequent steps (steps are split by `.interact()` boundaries), which surface as SKIP.
- `.with_tags([...])`: flat `"Key:Value"` labels used by `SuiteResult.group_by()` and `print_report(group_by=...)`. For RAG evals, tagging by dimension (`"Dimension:Groundedness"`, `"Dimension:OutOfScope"`, ...) turns one aggregate pass rate into a per-dimension breakdown.
- `.with_annotations({...})`: scenario-level data readable as `trace.annotations` and selectable as `trace.annotations.key`.
- `multiple_runs=N` (constructor): re-execute the whole scenario up to N times with a fresh trace each time, stopping at the first non-passing run. Useful for exposing non-determinism on a specific question.

NEVER pass `inputs`, `checks`, or `description` as `Scenario(...)` constructor kwargs. Unlike checks, `Scenario` tolerates unknown keys and silently drops them, so this produces an empty scenario that passes instantly.

## Suite

```python
suite = Suite(name="my_suite")
suite.append(scenario)
suite.append(another_scenario)

result = await suite.run(target=my_agent, parallel=True)
result.print_report(group_by="Dimension")
```

`Suite.run(...)` parameters:

- `target`: overrides suite-level and scenario-level targets
- `return_exception=False`: `True` records input-generation failures as ERROR results instead of raising
- `parallel=False`: `True` runs scenarios concurrently while preserving result order. Use it for any suite with more than a handful of LLM-judged scenarios.
- `max_concurrency=None`: cap concurrent scenarios when `parallel=True`; `None` starts everything at once, so provider rate limits become the effective cap
- `verbose=True`: `False` suppresses the live rich progress bar (use in CI)

`SuiteResult` has:

- `pass_rate: float | None`: passed / (total − skipped). **`None`** when nothing was evaluated (empty suite, or all scenarios skipped) — guard before formatting.
- `passed_count`, `failed_count`, `errored_count`, `skipped_count`: `int`
- `results: list[ScenarioResult]`: per-scenario detail
- `failures_and_errors: list[ScenarioResult]`: only failed/errored scenarios
- `recommendation: str | None`: Markdown guidance, populated by `quality_scan`
- `print_report(console=None, group_by=None)`: pretty-print; `group_by="Dimension"` appends a per-tag-value pass-rate table
- `group_by("Dimension") -> GroupedSuiteResult`: per-group `GroupStats` (`passed`, `failed`, `errored`, `skipped`, `total`, `non_skipped`, `pass_rate`)
- `to_junit_xml()` / `to_junit_xml("results.xml")`: JUnit XML for CI dashboards
- `to_hub_format()`: JSON-serializable Giskard Hub payload
- `model_dump_json(indent=2)`: full serialization for CI artifacts

```python
if result.pass_rate is None:
    print("No scenarios evaluated")
else:
    print(f"Pass rate: {result.pass_rate:.1%}")
```

`ScenarioResult` exposes `scenario_name`, `status`, `passed` / `failed` / `errored` / `skipped`, `final_trace` (**not** `trace`), `steps`, `tags`, `duration_ms`, `runs_executed`, `failures_and_errors`.

## Statuses: PASS, FAIL, ERROR, SKIP

All status enums have four states. ERROR and SKIP mean *no verdict was reached*:

- **ERROR** — the check could not run: a key resolved to nothing, an unsupported comparison, an exception in the target
- **SKIP** — the check or step was deliberately not evaluated, typically because an earlier step in the scenario failed

Rollups use priority ERROR > FAIL > all-SKIP > PASS, so PASS mixed with SKIP still rolls up to PASS; only an all-SKIP collection becomes SKIP. Skipped scenarios are excluded from the `pass_rate` denominator. Branch on `status` (or the explicit `failed` / `errored` / `skipped` properties) rather than on `not passed`.

## Built-in LLM-based Checks

All accept an optional `generator=` for a per-check model override, plus `name` and `description`. Always pass `name`.

Every LLM check returns an `LLMCheckResult` with a **required, non-blank `reason`** and a required `passed`. Custom `LLMJudge` prompts must ask for a justification, or the judge call fails validation.

### Groundedness

Validates that the answer is supported by the provided context. **The most important RAG check.**

```python
Groundedness(
    name="grounded",
    context=["chunk 1 from KB", "chunk 2 from KB"],
)
```

Fields:

- `context: str | list[str]`: static context; when set, takes priority over `context_key`
- `context_key: str`: JSONPath; default `"trace.last.metadata.context"`
- `answer: str`: static answer; usually unused for live SUTs
- `target_key: str`: JSONPath to the answer; default `"trace.last.outputs"`

**Variants**:

- **Dynamic context from agent output** (SUT returns a dict): omit `context=` and set `context_key="trace.last.outputs.context"`, `target_key="trace.last.outputs.answer"`.
- **Dynamic context from interaction metadata**: omit `context=` and attach via `.interact(inputs=..., metadata={"context": [...]})` — matches the default `context_key`.

If either key resolves to nothing, the check returns ERROR without spending a judge call. A list value is joined with newlines before it reaches the prompt, so passing `context=[...]` is safe and readable.

### Contradiction

Same inputs as `Groundedness` (`answer` / `target_key`, `context` / `context_key`), but a permissive criterion: omissions and unsupported additions are tolerated, and only statements that **directly conflict** with the context fail.

```python
Contradiction(
    name="does_not_contradict_sources",
    context=["Refunds are available within 30 days of purchase."],
)
```

Use it when the agent is expected to add world knowledge on top of retrieval and strict groundedness would flag legitimate elaboration. Pairing `Groundedness` (strict, informational) with `Contradiction` (permissive, gating) is a good way to keep a CI gate stable while still tracking drift.

### AnswerRelevance

Validates that the answer addresses the question. Multi-turn aware: only the _current_ turn is scored, but prior turns are passed as history so the judge understands intent.

```python
AnswerRelevance(
    name="relevant",
    # Defaults are usually correct:
    # question_key="trace.last.inputs",
    # target_key="trace.last.outputs",
    context="This is a chatbot that answers questions about our internal HR policies.",
)
```

Fields:

- `question: str` / `question_key: str`: static question, or JSONPath (default `"trace.last.inputs"`)
- `answer: str` / `target_key: str`: static answer, or JSONPath (default `"trace.last.outputs"`)
- `context: str`: domain description; helps the judge calibrate "relevant" to the agent's scope. NOT extracted from the trace.
- `include_history: bool`: default `True`. Set to `False` to score the current turn in isolation, dropping the conversation-history section from the prompt.

Unresolvable `question_key` / `target_key` return ERROR rather than silently substituting a question inferred from history.

### Conformity

Validates the answer against a plain-text rule. Use for behavioral expectations: "must cite", "must decline if uncertain", "must respond in English".

```python
Conformity(
    name="declines_when_unsupported",
    rule="When the agent does not have information to answer, it must explicitly decline rather than guessing. Confident answers without supporting context fail this check.",
)
```

Fields:

- `rule: str`: plain text. NOT a Jinja2 template. Receives the full Trace automatically, so it can judge multi-turn behavior.

### LLMJudge

Custom LLM judgment with a Jinja2 prompt. Use when no built-in check fits.

```python
LLMJudge(
    name="answer_matches_gold",
    prompt="""
Compare the agent's answer to the gold answer. Pass if they convey the same factual information, even if worded differently.

Question: {{ trace.last.inputs }}
Agent answer: {{ trace.last.outputs }}
Gold answer: The capital of France is Paris.

Return passed=true if the agent's answer conveys "Paris is the capital of France"; passed=false otherwise. Include a one-sentence reason.
""",
)
```

Fields:

- `prompt: str`: Jinja2 template; rendered with the full trace context
- `prompt_path: str`: alternative to `prompt` — a registered template reference such as `"my_project::checks/gold.j2"`. Exactly one of the two is required.

### Toxicity

Built-in safety judge across `hate_speech`, `harassment`, `threats`, `self_harm`, `sexual_content`, `violence`. Mostly the `scenario-generator` skill's territory, but useful in a RAG suite when the corpus itself contains sensitive material and you want to confirm the agent does not amplify it.

```python
Toxicity(name="output_not_toxic", categories=["hate_speech", "harassment"])
```

It passes when the output is clean, so do not wrap it in `Not`.

## Built-in (rule-based) Checks

```python
# Keyword presence: passes if `keyword` is found in the resolved text.
StringMatching(name="cites_paris", keyword="Paris", target_key="trace.last.outputs")

# Case-insensitive matching
StringMatching(name="mentions_refund", keyword="refund", case_sensitive=False)

# Keyword absence: StringMatching only asserts presence, so wrap it in Not.
Not(name="no_medical_advice", check=StringMatching(keyword="medical advice", target_key="trace.last.outputs"))

# Regex (PyPI `regex` module, with a matching timeout)
RegexMatching(name="has_citation", pattern=r"\[\d+\]", target_key="trace.last.outputs")

# Equality / comparison. `target_key` selects the actual value; `expected_value`
# (or `expected_value_key`) supplies the expected one. Exactly one is required.
Equals(name="is_paris", expected_value="Paris", target_key="trace.last.outputs")
LessThan(name="answer_is_short", expected_value=500, target_key="trace.last.outputs.length")

# Collection matching: apply the comparison across a list-valued key
GreaterThan(
    name="all_scores_confident",
    expected_value=0.7,
    target_key="trace.last.outputs.scores",
    match="all",   # "any" | "all" | "none"
)

# Structured output validity, optionally against a JSON Schema
JsonValid(
    name="envelope_is_valid_json",
    target_key="trace.last.outputs",
    schema={"type": "object", "required": ["answer", "sources"]},
)

# Custom function: receives Trace, NOT the output string
FnCheck(
    name="answer_non_empty",
    fn=lambda trace: len(str(trace.last.outputs)) > 0,
)

# Composition
AllOf(name="all_pass", checks=[check1, check2])
AnyOf(name="grounded_or_refused", checks=[grounded_check, refusal_check])
Not(name="not_empty", check=empty_check)
```

The comparison checks are `Equals`, `NotEquals`, `LessThan`, `LessThanEquals`, `GreaterThan` and `GreaterThanEquals`. An unsupported comparison between the two values (e.g. `str < int`) returns ERROR, not FAIL.

## SemanticSimilarity

Embedding-based similarity to a reference string.

```python
SemanticSimilarity(
    name="matches_gold",
    reference_text="The capital of France is Paris.",
    target_key="trace.last.outputs",   # adjust to ".answer" if SUT returns dict
    threshold=0.5,                      # default is 0.95 which is very strict
)
```

Fields:

- `reference_text: str`: static gold; when set, takes priority over `reference_text_key`.
- `reference_text_key: str`: JSONPath; default `"trace.last.metadata.reference_text"`. Use this if you attach the reference into the interaction metadata at `.interact()` time.
- `target_key: str`: JSONPath; default `"trace.last.outputs"`. Set to `"trace.last.outputs.answer"` when the SUT returns a dict.
- `threshold: float`: default `0.95` (very strict; calibrate downward to 0.5-0.7 for natural-language answers, where phrasing varies but meaning is preserved).
- `embedding_model`: optional; defaults to `text-embedding-3-small` (override globally via `GISKARD_CHECKS_DEFAULT_EMBEDDING_MODEL`).

Keep both selectors single-valued: a wildcard or multi-match path resolves to a list, and the check FAILs with a message telling you to narrow the key.

## UserSimulator

LLM-powered persona that drives `.interact()` dynamically across multiple turns. Use it when a static `inputs="..."` string is too rigid — e.g., to test paraphrase robustness, multi-turn follow-up clarifications, or how the agent handles users who don't know exactly what to ask.

```python
from giskard.checks import UserSimulator

curious_user = UserSimulator(
    persona="""
    You are an employee looking up the company's parental leave policy.
    - Start with a vague question ("what's the leave policy?")
    - Based on the agent's reply, ask a more specific follow-up
    - If anything is unclear, ask for clarification once
    - Stop once you have a concrete answer about parental leave specifically
    """,
    max_steps=4,
)

scenario = (
    Scenario("parental_leave_followup")
    .interact(inputs=curious_user)
    .check(Groundedness(name="grounded", context=POLICY_CHUNKS))
    .check(AnswerRelevance(name="relevant"))
)
```

Fields:

- `persona: str`: free-text description of the user. Detailed, goal-oriented personas work best. Include background, what the user is trying to accomplish, and a stop condition.
- `context: str | None`: optional extra situational detail for the persona.
- `max_steps: int`: max conversation turns (default `3`). Bump up for personas that need clarification rounds. `max_turns` is not a field and raises a `ValidationError`.
- `max_retries: int`: per-turn retries when the model refuses (default `2`).

**RAG-quality persona ideas**:

- **Paraphraser**: asks the same factual question multiple ways to test consistency.
- **Curious follow-up asker**: starts vague, drills in based on the agent's response.
- **Out-of-scope wanderer**: asks one in-scope question, then drifts to topics the KB doesn't cover — tests refusal quality.
- **Confused/imprecise user**: uses wrong terminology or partial information; tests the agent's ability to clarify before answering.

For **adversarial personas** (manipulation, prompt-injection, jailbreaks) use the `scenario-generator` skill instead.

Related generators: `LLMGenerator(prompt=... | prompt_path=..., max_steps=...)` when you want to supply the whole driving prompt, and `DatasetInputGenerator(prompt="...")` to replay a fixed question verbatim (it also adapts the prompt into a structured target schema when the SUT does not take plain strings).

## Multi-turn scenarios

```python
scenario = (
    Scenario("multi_turn_rag")
    .interact(inputs="What is the company's vacation policy?")
    .check(Groundedness(name="grounded_1", context=POLICY_CHUNKS))
    .interact(inputs="And how does it work for new hires?")  # follow-up
    .check(Groundedness(name="grounded_2", context=POLICY_CHUNKS))
    .check(AnswerRelevance(name="relevant_2"))
)
```

Each `.interact()` is a turn. Checks placed after a turn evaluate that turn's interaction. `trace.interactions[i]` accesses turn `i`. A failing turn stops the scenario, so later turns report SKIP — expected, and the reason to read `status` rather than `not passed`.

To make a follow-up depend on the previous answer, pass a trace-aware callable:

```python
.interact(inputs=lambda trace: f"You said {trace.last.outputs}. Where is that documented?")
```

## JSONPath keys

Every selector must start with `trace.`; anything else raises a `ValidationError` at construction time.

- `trace.last.outputs` — most recent output (most common)
- `trace.last.inputs` — most recent question
- `trace.last.outputs.answer` / `trace.last.outputs.context` — fields of a structured output
- `trace.last.metadata.context` — data attached via `.interact(..., metadata={...})`
- `trace.interactions[0].outputs` — first turn's answer
- `trace.annotations.key` — scenario-level annotation

A path matching nothing resolves to `NoMatch`, which checks report as ERROR. A wildcard or multi-match path resolves to a list.

## Configuring the LLM generator

LLM-backed checks (`Groundedness`, `Contradiction`, `AnswerRelevance`, `Conformity`, `LLMJudge`, `Toxicity`) and `UserSimulator` need a generator.

```python
from giskard.agents import Generator
from giskard.checks import set_default_generator

set_default_generator(Generator(model="openai/gpt-5.6-terra"))
```

Always name the judge model explicitly. `set_default_generator` is technically optional, but the built-in fallback is `openai/gpt-4o-mini` — a legacy model no longer in OpenAI's recommended lineup — so omitting the call silently pins every judge to a stale model.

### Picking a judge model

Judging is much cheaper than generation, and the judge does not need to be the same model as the agent, so a mid-tier model is the right default. Reserve a frontier model for the checks whose verdict you actually argue about — typically `Groundedness` on the scenarios that gate a release.

| Role | OpenAI | Anthropic | Google |
|---|---|---|---|
| Default judge | `openai/gpt-5.6-terra` | `anthropic/claude-sonnet-5` | `google/gemini-3.7-flash` |
| Cheap, high-volume | `openai/gpt-5.6-luna` | `anthropic/claude-haiku-4-5` | `google/gemini-3.5-flash-lite` |
| Frontier, for critical checks | `openai/gpt-5.6-sol` | `anthropic/claude-opus-5` | `google/gemini-3.1-pro-preview` |

Model line-ups turn over every few months, so confirm against the provider's current model list before pinning one in a long-lived suite. Prefer a pinned ID over a `-latest` alias: an alias that silently changes underneath you turns judge drift into unexplained suite churn. Note that Gemini's Pro tier is preview-stage, which carries a shorter deprecation notice period than stable models.

Changing the judge model re-baselines the suite. Expect a handful of borderline verdicts to flip, and re-run the whole suite rather than comparing a new judge's results against an old report.

**Model strings are `provider/model`, routed through `giskard-llm`'s native providers.** Supported prefixes: `openai`, `google`, `gemini`, `anthropic`, `azure`, `azure_ai`. A bare model name defaults to `openai`. An unregistered prefix fails with `ValueError: Provider '<x>' is not configured and not in the registry.` Through `Generator` and the checks, that `ValueError` arrives as the cause of a `WorkflowError` (or as an ERROR check result), with the message intact in the exception chain.

For anything else:

```python
# OpenAI-compatible endpoint (vLLM, Ollama, OpenRouter, ...)
import giskard.llm

giskard.llm.configure("local", provider="openai", base_url="http://localhost:11434/v1", api_key="ollama")
set_default_generator(Generator(model="local/gpt-oss-20b"))

# Or go through LiteLLM: pip install "giskard[litellm]"
from giskard.agents.generators import LiteLLMGenerator

set_default_generator(LiteLLMGenerator(model="bedrock/anthropic.claude-sonnet-5"))
```

**Variants**:

- **Per-check override**: pass `generator=Generator(model="openai/gpt-5.6-sol")` to a single check to use a stronger judge there (e.g., for `Groundedness` on critical scenarios).

**Environment variables** (prefix `GISKARD_CHECKS_`, also read from a project `.env`):

- `GISKARD_CHECKS_DEFAULT_MODEL` — judge model used when no generator is set (defaults to the legacy `openai/gpt-4o-mini`; set this or call `set_default_generator`)
- `GISKARD_CHECKS_DEFAULT_EMBEDDING_MODEL` — default embedder (`text-embedding-3-small`, still current; `text-embedding-3-large` is the more capable option). A bare name routes to OpenAI, so prefix it on other providers (`azure_ai/text-embedding-3-small`)
- `GISKARD_CHECKS_MAX_REPORTED_FAILURES` — cap failures shown in suite reports
- `GISKARD_CHECKS_DISABLE_RICH_PRETTY` — disable rich REPL pretty-printing

## Persistence (CI-friendly)

```python
from pathlib import Path

result = await suite.run(target=my_agent, parallel=True, verbose=False)
result.print_report(group_by="Dimension")
Path("rag_results.json").write_text(result.model_dump_json(indent=2))
result.to_junit_xml("rag_results.xml")     # per-scenario pass/fail in CI dashboards
```

`SuiteResult.to_junit_xml()` supersedes reaching into `giskard.checks.export.junit` directly (that module still exists and backs the method).

## Automatic knowledge-base quality scan

`giskard.scan.quality_scan` generates a knowledge-base quality suite from your documents, runs it, prints a grouped report with a recommendation, and returns a `SuiteResult`.

```python
from giskard.scan import KnowledgeBase, quality_scan

result = await quality_scan(
    target=my_rag_agent,
    description="An assistant that answers questions about our internal HR policies.",
    languages=["en"],                    # BCP-47 codes the agent must handle
    knowledge_base=KnowledgeBase.from_texts(KB_CHUNKS),  # or a plain list[str]
    max_scenarios=30,                    # total cap across generators
    seed=42,                             # reproducible generation
    group_by="component",                # tag key for the printed table
    parallel=True,
    max_concurrency=None,
    return_exception=False,
    target_mode="multiturn",             # "singleturn" skips multi-turn-only generators
)
```

Generators behind it: `HallucinationScenarioGenerator`, `SycophancyScenarioGenerator`, `SplitQuestionsScenarioGenerator`, `MultiTopicScenarioGenerator`, `OutOfScopeScenarioGenerator`.

Omitting `knowledge_base` (or passing an empty one) emits a `RuntimeWarning` and skips the knowledge-base scenarios, which is nearly everything the quality scan does — so always supply documents.

### KnowledgeBase

```python
from giskard.scan import Document, KnowledgeBase

kb = KnowledgeBase.from_texts(["chunk 1", "chunk 2"])
kb = KnowledgeBase(documents=(Document(content="chunk 1", tags=["policy"]),))

neighbours = await kb.closest_documents_to_text("parental leave", max_documents=3)
```

The document collection is frozen, embeddings are computed lazily in one batch on first nearest-neighbour lookup, and at least one non-empty document is required. `from_texts` takes a list of strings, so convert a DataFrame column to a list first. A bare `str` is not rejected. It is iterated character by character and silently becomes one document per character, so always wrap a single text in a list (`from_texts([text])`).

### Composing your own generated suite

```python
from giskard.scan import HallucinationScenarioGenerator, OutOfScopeScenarioGenerator, generate_suite

suite = await generate_suite(
    description="An assistant that answers questions about our internal HR policies.",
    languages=["en"],
    generators=[HallucinationScenarioGenerator(), OutOfScopeScenarioGenerator()],
    max_scenarios=20,
    seed=42,
    knowledge_base=kb,
)
result = await suite.run(target=my_rag_agent, parallel=True)
```

Because the result is an ordinary `Suite` / `SuiteResult`, a generated suite and a hand-written one can be reported side by side, or their scenarios merged into one suite.

## Common Pitfalls

- **`ValidationError: Extra inputs are not permitted`**: the check has no such field. If it was meant to select a value from the trace, it is `target_key`; otherwise look the field up above.
- **Empty Suite passes instantly**: `Scenario("name", checks=[...])` silently drops the kwarg. Use `.check(...)`.
- **Agent isn't called / `TypeError: Parameter 'query' is required but not in the injection requirements`**: only `inputs` and `trace` are injected. Wrap the user's function.
- **`RuntimeError: asyncio.run() cannot be called from a running event loop`**: a sync SUT calls `asyncio.run()` internally. Make the SUT `async def` and `await` the SDK's async API (`arun`, `ainvoke`, `aquery`, ...).
- **`TypeError: unsupported format string passed to NoneType`** on the pass rate: `pass_rate` is `None` for an empty or fully skipped suite. Guard it.
- **`Groundedness` reports ERROR**: `context_key` or `target_key` resolved to nothing. The default `context_key` is `trace.last.metadata.context`, not the agent's output — set it explicitly when the chunks come back in the answer payload.
- **`Groundedness` always passes / always fails**: `context` (static) shadows `context_key`; the static value always wins. Pass only one.
- **`AnswerRelevance` returns "relevant" for off-topic answers**: pass `context="..."` describing the agent's domain so the judge has scope to ground its decision.
- **`ValidationError: path must start with 'trace.'`**: every JSONPath selector is rooted at `trace.`.
- **`FnCheck` errors on `trace.last.outputs`**: `fn` receives a Trace object, not a string. Use `lambda trace: ... trace.last.outputs ...`, not `lambda outputs: ...`.
- **`SemanticSimilarity` complains the value must be a single value**: the key resolved to a list (a wildcard or multi-match path). Narrow the selector.
- **`SemanticSimilarity` fails everything**: default threshold is 0.95 (very strict); calibrate to 0.5-0.7 for natural-language answers.
- **`StringMatching` cannot assert absence on its own**: wrap it in `Not(...)`.
- **LLM judge fails validation on `reason`**: `LLMCheckResult.reason` is required and non-blank; ask for it in the prompt.
- **`scen.trace.last.outputs` raises AttributeError in post-suite aggregation**: `ScenarioResult` exposes the trace as `final_trace`, not `trace`.
- **`ValueError: Provider 'ollama' is not configured and not in the registry`** (often wrapped in a `WorkflowError`, so check the exception cause): only the native providers are routed by default. Use `giskard.llm.configure(...)` or `LiteLLMGenerator`.
- **Later turns of a multi-turn scenario report SKIP**: an earlier step failed, so the rest never ran. Skipped scenarios are excluded from the pass-rate denominator.
