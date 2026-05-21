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
  version: 1.1.0
  category: ai-testing
  tags: [giskard, checks, sql, text-to-sql, text2sql, evaluation, analytics]
---

# Giskard Text-to-SQL Evaluator

Quality evals: wrong counts, unsafe SQL, empty tool trace, out-of-scope handling.

`suite.run(target=...)`. Return shape: prefer `{"answer", "queries"}`.

**In-domain:** `FnCheck` on `queries[]` before answer judges — [`references/tool-usage.md`](references/tool-usage.md).

## Required: shared evaluator shell

Read [`../references/evaluator-skill-shell.md`](../references/evaluator-skill-shell.md) first (workflow, [`error-analysis.md`](../references/error-analysis.md), [`generated-code-rules.md`](../references/generated-code-rules.md), [`giskard-how-to.md`](../references/giskard-how-to.md), [`iterative-eval-loop.md`](../references/iterative-eval-loop.md), install via `uv pip install`).

## Domain workflow

### Step 3: Dimensions

[`references/eval-dimensions.md`](references/eval-dimensions.md) + directions in [`references/scenario-directions.md`](references/scenario-directions.md).

| User has | Coverage |
|----------|----------|
| Agent only | Relevance, conformity, refusal |
| Agent + schema in prompt | + metadata answers (empty `queries` may be OK) |
| Agent + seed DB | + gold `FnCheck`, `validate_sql` guardrails |
| Agent + labelled Q&A | Gold `SemanticSimilarity` / `Equals` |

### Step 4: Tool usage

In-domain: `FnCheck` on `queries[]` → SQL shape / [`references/sql-safety.md`](references/sql-safety.md) → `AnswerRelevance` / gold.

Out-of-scope: **decline** (`Conformity`), not required query.

### Step 5: Inputs

Default **multi-turn** mix (~40% static / ~40% `UserSimulator` / ~20% dialogue safety) — shell Step 5b, [`../references/multi-turn-scenarios.md`](../references/multi-turn-scenarios.md), [`references/simulate-users.md`](references/simulate-users.md). Static strings for gold metrics and guardrails only; personas for follow-ups and handoffs. [`references/test-input-generation.md`](references/test-input-generation.md).

### Step 7: Patterns

Trace keys and gold `FnCheck` wiring: [`references/api-reference.md`](references/api-reference.md), [`references/examples.md`](references/examples.md). Safety: `validate_sql` + `FnCheck` on `queries[]`, not `Conformity` alone. **notebook** / `.ipynb`: [`../references/generated-code-rules.md`](../references/generated-code-rules.md).

## Domain references

| File | Purpose |
|------|---------|
| [`eval-dimensions.md`](references/eval-dimensions.md) | Dimensions |
| [`scenario-directions.md`](references/scenario-directions.md) | Directions, tiers |
| [`test-input-generation.md`](references/test-input-generation.md) | Input tuples |
| [`tool-usage.md`](references/tool-usage.md) | `queries[]` `FnCheck` |
| [`sql-safety.md`](references/sql-safety.md) | `validate_sql`, guardrails |
| [`checks-catalog.md`](references/checks-catalog.md) | Check layers |
| [`api-reference.md`](references/api-reference.md) | API |
| [`workflow-eval.md`](references/workflow-eval.md) | Workflow eval |
| [`simulate-users.md`](references/simulate-users.md) | Personas |
| [`examples.md`](references/examples.md) | Worked code |

Optional demo: `example-agent/` + `COVERAGE.md` (see shell).

## Troubleshooting (text-to-SQL)

| Issue | Action |
|-------|--------|
| TypeScript agent | Adapter returning `answer` + `queries[]` |
| No DB | Sanitized snapshot or `example-agent/` |
| Schema in prompt | Empty `queries` may be valid — judge `answer` |
| Flaky judges | `FnCheck` first; [`references/sql-safety.md`](references/sql-safety.md) |
| Guardrails only | `validate_sql` unit tests — see `sql-safety.md` |

[`evals/evals.json`](evals/evals.json)
