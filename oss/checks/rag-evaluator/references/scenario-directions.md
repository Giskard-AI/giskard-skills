# Scenario directions (RAG)

Guide for **which test scenarios to build**, **why they matter**, and **what inputs they need**. Use when designing a `giskard.checks` suite for a document-grounded agent — not as a copy-paste prompt list.

## Trace contract

In-domain evals assume the agent exposes retrieval in its return shape when possible:

```python
{
    "answer": str,
    "sources": [...],      # and/or
    "context": [...],      # and/or
    "tool_calls": [...],
}
```

See [`tool-usage.md`](./tool-usage.md). Adapt doc IDs and field names to the user's agent.

## How to use this guide

0. Run [**error analysis**](../../references/error-analysis.md) on traces first — pick directions from observed failure modes.
1. Confirm KB coverage (corpus sample, topic list, or user-provided chunks).
2. Pick **Tier 1** directions for every deployment — include **at least 2–4 persona scenarios** (phased or chained `UserSimulator`) in the first suite, not static-only single turns.
3. Add **Tier 2** when retrieval is exposed or labels exist.
4. Add **Tier 3** for citations, multi-hop, or multi-turn stress.
5. Prefer **deterministic checks first**, LLM judges second.
6. **Personas** via [`simulate-users.md`](./simulate-users.md) — phased or chained users per turn; static strings for gold Q&A and OOS only. See [`../../references/multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md).
7. **Retrieval tool usage** on every in-domain factual question — [`tool-usage.md`](./tool-usage.md) before `Groundedness` alone.
8. After each run, apply [`../../references/iterative-eval-loop.md`](../../references/iterative-eval-loop.md) — ~100% quality pass often means the suite is too easy.

### Optional persona (when direction fits)

| Direction | Objective | Shape / multi-user |
|-----------|-----------|-------------------|
| In-domain factual | `factual_lookup` | — |
| Paraphrase / follow-up | — | `vague_then_specific`, `paraphrase_same_fact` |
| Multi-hop | `multi_hop_synthesis` | — |
| OOS adjacent topic | `oos_probe` | `offtopic_then_data`, `wrong_topic_then_correct` |
| Citation required | `citation_focus` | `employee_then_manager` |

Label each `Scenario("direction_slug")` so reports stay readable.

---

## Tier 1 — Baseline (every RAG agent)

### Grounding and retrieval

| Direction | Failure mode | Checks (order) |
|-----------|--------------|----------------|
| In-domain factual | Answers without retrieving | `FnCheck` retrieval → `Groundedness` |
| Out-of-scope | Hallucination on missing topics | Decline `Conformity` / `StringMatching` — **no** required retrieval |
| Paraphrase same fact | Brittle to wording | Same checks; optional `UserSimulator` |
| Empty / nonsense query | Garbage out | `AnswerRelevance` or decline |

### Abstention balance

Include both **answerable** (context supports answer) and **unanswerable** (false premise, missing doc, adjacent-but-uncovered topic) cases — see [`eval-dimensions.md`](./eval-dimensions.md).

---

## Tier 2 — When retrieval is measurable

| Direction | Needs | Checks |
|-----------|-------|--------|
| Wrong chunk retrieved | Query–doc labels or synthetic pairs | IR metrics — [`retrieval-metrics.md`](./retrieval-metrics.md) |
| Recall@k regression | Labelled relevant doc IDs | `FnCheck` on doc ID set |
| Retriever exposed separately | `retrieve(query)` callable | Retriever-only tests + E2E |

Tune **retrieval before generation judges** when labels exist.

---

## Tier 3 — Product-specific depth

| Direction | Notes |
|-----------|--------|
| Multi-hop synthesis | 2+ chunks required — [`test-input-generation.md`](./test-input-generation.md) |
| Citation format | `RegexMatching` + ID-in-KB `FnCheck` + optional `LLMJudge` alignment |
| Multi-turn follow-up | Prior turn context — [`workflow-eval.md`](./workflow-eval.md) |
| Policy / tone rules | `Conformity` on cite, language, disclaimers |

Skip Tier 3 directions until Tier 1 is green on a representative sample.

---

## Test input dimensions

When scaling beyond hand-written questions, use **dimensions → tuples → natural language** — see [`../../references/test-input-generation-core.md`](../../references/test-input-generation-core.md) and [`test-input-generation.md`](./test-input-generation.md). Map each tuple to a direction above.

---

## Proven check patterns

| Situation | Prefer | Avoid |
|-----------|--------|-------|
| Retrieval ran | `FnCheck` on `sources` / `context` / `tool_calls` | `Conformity("must cite")` only |
| Faithfulness | `Groundedness` with dynamic `context_key` | Static `context=` while agent skips retrieval |
| Refusal | `StringMatching` / `FnCheck` on decline phrases | `Groundedness` on OOS questions |
| Gold answer wording | `SemanticSimilarity` (calibrated threshold) | ROUGE/BERTScore as primary gate |

---

## Coverage report

For each direction **included** or **skipped**, tell the user:

- **Included**: failure mode targeted.
- **Skipped**: missing KB, labels, or retriever access.

After each run, follow [`../../references/iterative-eval-loop.md`](../../references/iterative-eval-loop.md).

---

## See also

- [`eval-dimensions.md`](./eval-dimensions.md) — full dimension catalog
- [`../../references/doc-authoring.md`](../../references/doc-authoring.md) — placeholder conventions; demo details in optional `example-agent/COVERAGE.md`
- `text2sql-evaluator/references/scenario-directions.md` — parallel structure for SQL agents
