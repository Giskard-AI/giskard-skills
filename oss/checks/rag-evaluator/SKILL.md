---
name: rag-evaluator
description: >-
  Builds giskard.checks evaluation suites for RAG and document-grounded agents.
  Triggers on "evaluate my RAG", "test retrieval", "check groundedness", "RAG eval".
  Use scenario-generator for adversarial red-teaming.
license: Apache-2.0
metadata:
  author: Giskard
  version: 1.1.0
  category: ai-testing
  tags: [giskard, checks, rag, evaluation, groundedness, retrieval]
---

# Giskard RAG Evaluator

Quality evals: hallucination, ungrounded answers, poor retrieval, out-of-scope handling.

`suite.run(target=...)`. Return shape: `str` or dict with `answer` / `sources` / `context` / `tool_calls`.

**In-domain:** `FnCheck` on retrieval before `Groundedness` alone — [`references/tool-usage.md`](references/tool-usage.md).

## Required: shared evaluator shell

Read [`../references/evaluator-skill-shell.md`](../references/evaluator-skill-shell.md) first (workflow, [`error-analysis.md`](../references/error-analysis.md), [`generated-code-rules.md`](../references/generated-code-rules.md), [`giskard-how-to.md`](../references/giskard-how-to.md), [`iterative-eval-loop.md`](../references/iterative-eval-loop.md), install via `uv pip install`).

## Domain workflow

### Step 3: Dimensions

[`references/eval-dimensions.md`](references/eval-dimensions.md) + directions in [`references/scenario-directions.md`](references/scenario-directions.md).

| User has | Coverage |
|----------|----------|
| Agent only | Relevance, conformity, refusal, paraphrase |
| Agent + KB | + groundedness, synthetic Q&A |
| Agent + retriever | + dynamic groundedness, recall@k |
| Agent + Q&A set | Gold `SemanticSimilarity` / judges |

### Step 4: Tool usage

In-domain: `FnCheck` → IR metrics if labelled ([`references/retrieval-metrics.md`](references/retrieval-metrics.md)) → `Groundedness` / `AnswerRelevance`.

Out-of-scope: **decline** (`Conformity`), not retrieval.

### Step 5: Inputs

Default **multi-turn** mix (~40% static / ~40% `UserSimulator` / ~20% dialogue safety) — shell Step 5b, [`../references/multi-turn-scenarios.md`](../references/multi-turn-scenarios.md), [`references/simulate-users.md`](references/simulate-users.md). Static strings for gold/OOS only; personas for follow-ups and handoffs. [`references/test-input-generation.md`](references/test-input-generation.md).

### Step 7: Patterns

Trace keys and `Groundedness` wiring: [`references/api-reference.md`](references/api-reference.md), [`references/examples.md`](references/examples.md). OOS: `Conformity`, not `Groundedness`. **notebook** / `.ipynb`: [`../references/generated-code-rules.md`](../references/generated-code-rules.md).

## Domain references

| File | Purpose |
|------|---------|
| [`eval-dimensions.md`](references/eval-dimensions.md) | Dimensions |
| [`scenario-directions.md`](references/scenario-directions.md) | Directions, tiers |
| [`test-input-generation.md`](references/test-input-generation.md) | Synthetic Q&A |
| [`tool-usage.md`](references/tool-usage.md) | Retrieval `FnCheck` |
| [`retrieval-metrics.md`](references/retrieval-metrics.md) | Recall@k |
| [`checks-catalog.md`](references/checks-catalog.md) | Check layers |
| [`api-reference.md`](references/api-reference.md) | API, `context_key` |
| [`workflow-eval.md`](references/workflow-eval.md) | Workflow eval |
| [`simulate-users.md`](references/simulate-users.md) | Personas |
| [`examples.md`](references/examples.md) | Worked code |

Optional demo: `example-agent/` + `COVERAGE.md` (see shell).

## Troubleshooting (RAG)

| Issue | Action |
|-------|--------|
| No KB | Relevance, refusal, paraphrase; honest **groundedness gap** |
| String output | Pre-retrieve `context=` or dict + `context_key` |
| RAGAS-style | `Groundedness`, `AnswerRelevance`, retrieval `FnCheck` |

[`evals/evals.json`](evals/evals.json)
