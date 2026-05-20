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

Data analytics agents via SQL tools. **`giskard.checks` only.**

`suite.run(target=...)`. Prefer `{"answer", "queries"}`. **`FnCheck` on `queries[]`** before answer judges — [`references/tool-usage.md`](references/tool-usage.md).

## Required: shared evaluator shell

Read [`../references/evaluator-skill-shell.md`](../references/evaluator-skill-shell.md) first (workflow, [`error-analysis.md`](../references/error-analysis.md), [`generated-code-rules.md`](../references/generated-code-rules.md), [`giskard-how-to.md`](../references/giskard-how-to.md), [`iterative-eval-loop.md`](../references/iterative-eval-loop.md), install via `uv pip install`).

## Domain workflow

### Step 3: Dimensions

[`references/eval-dimensions.md`](references/eval-dimensions.md): tool usage, answer quality, safety (`validate_sql`), conformity.

Directions and tiers: [`references/scenario-directions.md`](references/scenario-directions.md).

### Step 4: Inputs

Mix and personas: [`references/simulate-users.md`](references/simulate-users.md). Co-design: [`../references/iterative-eval-loop.md`](../references/iterative-eval-loop.md).

### Step 5: Checks

[`references/checks-catalog.md`](references/checks-catalog.md) — `FnCheck` / `validate_sql` for safety and gold; `LLMJudge` on full transcript for vague metrics.

### Step 8: Iterative loop (with user)

[`../references/iterative-eval-loop.md`](../references/iterative-eval-loop.md) — review **latest traces** and **scenario setup** with the user; propose nuance before coding. See shell Step 8.

## Evaluation nuances

[`references/sql-safety.md`](references/sql-safety.md) for **guardrail** / `validate_sql` patterns. Portable pitfalls:

- DELETE blocked or refused; LIMIT on non-aggregate SELECT
- Empty `queries[]` OK when schema is only in the prompt — judge `answer`
- Gold counts: parse `answer` on fixed seeds
- Multi-turn: scan all `trace.interactions`, not only `trace.last`

CI: deterministic guardrail tests, then safety scenarios, then full suite — [`../references/eval-lifecycle.md`](../references/eval-lifecycle.md).

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
| Flaky judges | Evaluation nuances; `FnCheck` |
| Schema in prompt | Empty `queries` may be valid |

[`evals/evals.json`](evals/evals.json)
