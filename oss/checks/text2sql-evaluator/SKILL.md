---
name: text2sql-evaluator
description: >-
  Builds giskard.checks evaluation suites for text-to-SQL and data analytics agents.
  Triggers on "text2sql evaluator", "evaluate my SQL agent", "SQL agent eval",
  "data analytics agent", "evaluate my analytics chatbot".
  Use scenario-generator for adversarial red-teaming.
license: Apache-2.0
metadata:
  author: Giskard
  version: 1.0.0
  category: ai-testing
  tags: [giskard, checks, sql, text-to-sql, text2sql, evaluation, analytics]
---

# Giskard Text-to-SQL Evaluator

Evals for **data analytics agents** that answer business questions via SQL (`executeQuery`-style tools).

Uses **`giskard.checks` only**. **SQL tool usage is mandatory** for data questions — `FnCheck` on `queries[]` before answer judges. See [`references/tool-usage.md`](references/tool-usage.md).

Evaluations target the **user's agent** via `suite.run(target=...)`. Optional bundled demo: `example-agent/`.

## Relationship to other skills

| Need | Skill |
|------|--------|
| SQL/data analytics **quality** | **This skill** |
| RAG over **documents** | `rag-evaluator` |
| **Adversarial** attacks | `scenario-generator` |

Many production agents need this skill + `scenario-generator`.

## Reference docs

| Topic | Path |
|-------|------|
| Information gathering | [`../references/information-gathering.md`](../references/information-gathering.md) + text2sql addendum |
| Generated code rules | [`../references/generated-code-rules.md`](../references/generated-code-rules.md) |
| Error analysis, CI lifecycle | [`../references/error-analysis.md`](../references/error-analysis.md), [`../references/eval-lifecycle.md`](../references/eval-lifecycle.md) |
| Trace sampling | [`../references/trace-sampling.md`](../references/trace-sampling.md) |
| Official how-to index | [`../references/giskard-how-to.md`](../references/giskard-how-to.md) |
| Multi-turn mechanics | [`../references/multi-turn-scenarios.md`](../references/multi-turn-scenarios.md) |
| Personas | [`references/simulate-users.md`](references/simulate-users.md) |
| Check layers (core) | [`../references/checks-catalog-core.md`](../references/checks-catalog-core.md) |
| Test inputs (core) | [`../references/test-input-generation-core.md`](../references/test-input-generation-core.md) |
| Check layers (SQL) | [`references/checks-catalog.md`](references/checks-catalog.md) |
| API (core) | [`../references/api-reference-core.md`](../references/api-reference-core.md) |
| API (SQL subset) | [`references/api-reference.md`](references/api-reference.md) |
| SQL safety | [`references/sql-safety.md`](references/sql-safety.md) |
| Dimensions, directions, inputs, workflow, examples | `references/eval-dimensions.md`, `scenario-directions.md`, `test-input-generation.md`, `workflow-eval.md`, `examples.md` |
| Bundled demo agent | `example-agent/` |

## Workflow

### Step 0: Gather context

Read [`../references/information-gathering.md`](../references/information-gathering.md) (text2sql addendum). Require agent description, interface, and DB access model.

Sample production traces when available — [`../references/trace-sampling.md`](../references/trace-sampling.md).

### Step 1: Error analysis

Read [`../references/error-analysis.md`](../references/error-analysis.md).

### Step 2: Install

```bash
uv pip install --prerelease=allow 'giskard-checks>=1.0.2b3'
```

### Step 3: Map inputs → dimensions

Minimum coverage ([`references/eval-dimensions.md`](references/eval-dimensions.md)):

1. SQL tool usage — `FnCheck` on `queries[]`
2. Answer quality — gold metrics when possible
3. SQL safety — `validate_sql` + agent behavior
4. Conformity — no "run DELETE yourself"; no memory answers when tools exist

Directions: [`references/scenario-directions.md`](references/scenario-directions.md) — Tier 1 always; Tier 2 when schema supports; Tier 3 only with events/sessions tables.

### Step 4: Source inputs

~40% static gold/guardrails, ~40% phased/chained personas, ~20% safety dialogue — [`../references/multi-turn-scenarios.md`](../references/multi-turn-scenarios.md), [`references/simulate-users.md`](references/simulate-users.md), [`references/test-input-generation.md`](references/test-input-generation.md).

### Step 5: Pick checks (cheap → expensive)

See [`references/checks-catalog.md`](references/checks-catalog.md), [`references/sql-safety.md`](references/sql-safety.md), [`../references/generated-code-rules.md`](../references/generated-code-rules.md).

1. `validate_sql` unit tests (no API key)
2. `FnCheck` on `queries[]` and `answer` text
3. Gold parses from fixed seed DB
4. `SemanticSimilarity` for paraphrase
5. LLM judges sparingly — not for safety or exact counts

Multi-step agents: [`references/workflow-eval.md`](references/workflow-eval.md).

### Step 6: Output code

Notebook cells if `.ipynb` context; else runnable script. SUT returns `{"answer", "queries"}` when possible.

## Evaluation nuances

Prefer **`FnCheck` over `Conformity`** for safety, refusals, and schema lists — judges false-fail on valid behavior.

- **Destructive requests**: no successful DELETE in `queries[]`; or `blocked: true`; or refusal keywords in `answer`
- **Schema-in-prompt**: "What tables exist?" may pass with empty `queries` if DDL is in system prompt — check `answer` content
- **LIMIT policy**: fail on successful non-aggregate SELECT without `LIMIT`, not on recovery narration
- **Gold metrics**: parse integers from `answer` on fixed seeds

CI order: `validate_sql` tests → `--safety-only` scenarios → full quality suite.

## Optional reference implementation (`example-agent/`)

```bash
cd example-agent && cp .env.example .env && uv sync
./scripts/deploy.sh
./scripts/run_eval.sh
uv run python run_suite.py --safety-only
```

| File | Role |
|------|------|
| `src/sql_tools.py` | `validate_sql`, `execute_query` |
| `src/agent.py` | `analytics_agent(inputs) -> dict` |
| `eval/scenarios.py` | Scenario definitions + `build_suite()` |
| `eval/test_sql_guardrails.py` | Deterministic guardrails (no API key) |

Point users here only when they want a local demo SUT.

## Output format

1. **Brief diagnosis** — Tier 1/2/3 covered and skipped
2. **Personas** — list or "static-only"
3. **Scenario plan** — direction → prompt/persona → check type
4. **Complete code**
5. **Per-scenario one-liner**
6. **Next steps**

## Troubleshooting

| Issue | Action |
|-------|--------|
| TypeScript agent | Python/HTTP adapter returning `answer` + `queries[]` |
| No DB credentials | Sanitized snapshot or optional `example-agent/` |
| Flaky judges | See Evaluation nuances; use `FnCheck` |
| Metadata without query | Valid when schema preloaded |
| Red team / injection | `scenario-generator` |

Skill quality rubrics: [`evals/evals.json`](evals/evals.json).
