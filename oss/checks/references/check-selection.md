# Check Selection: Prefer General Judges Over Custom FnCheck

Agents using giskard skills often reach for `FnCheck` (or `from_fn`) first. That produces brittle, overfit evals. **Default to the built-in judges** — they encode evaluation patterns that generalize across agents and phrasing.

## Decision order

When choosing a check for a scenario, walk this list top to bottom and stop at the first fit:

| Priority | Check | Use when |
|----------|-------|----------|
| 1 | `Groundedness` | Answer must be supported by provided context / retrieved chunks |
| 2 | `AnswerRelevance` | Answer must address the question (with optional `context=` domain hint) |
| 3 | `Conformity` | A clear behavioral rule applies (refusal, safety boundary, tone, no prompt leak) |
| 4 | `SemanticSimilarity` | Compare to a reference answer in meaning |
| 5 | `StringMatching` / `RegexMatching` | Exact keyword, citation marker, or format pattern (cheap sanity) |
| 6 | `LLMJudge` | Multi-criteria judgment Conformity cannot express in one rule, or need structured pass/fail reasoning |
| 7 | `FnCheck` | **Only** deterministic programmatic assertions (see below) |

## When FnCheck is appropriate

Use `FnCheck` only when the assertion is **objective and structural** — no language understanding required:

- Retrieval metrics with labelled doc IDs (`recall@k`, `precision@k`, `mrr`, `ndcg`) — see `rag-evaluator/references/retrieval-metrics.md`
- Parsed IDs from structured output (cited doc exists in KB set, tool name in allowlist)
- Numeric thresholds on trace metadata (latency, token count, number of tool calls)
- Non-empty / minimum length as a **cheap gate before** a judge, not as the sole quality check

## When FnCheck is a smell (use a judge instead)

| Smell | Prefer instead |
|-------|----------------|
| Keyword lists for refusal / safety ("don't", "cannot", "sorry") | `Conformity(rule="...")` |
| Keyword blocklists for sensitive terms | `Conformity` or `LLMJudge` |
| Heuristic "response length < N means refusal" | `Conformity(rule="must decline explicitly")` |
| Domain keyword detection for on/off topic | `Conformity(rule="must stay within domain X")` or `AnswerRelevance(context=...)` |
| Custom logic for "did it hallucinate?" | `Groundedness` or `LLMJudge` with fabrication prompt |
| Custom logic for "is answer correct?" | `SemanticSimilarity` + `LLMJudge` against gold |

**Why:** Keyword `FnCheck` passes on lucky phrasing and fails on valid paraphrases. Judges evaluate intent; they survive wording changes and are easier for users to read and tune.

## Layering (defense in depth)

Stack cheap checks before expensive judges — but each layer should use the **right tool**:

```python
.check(StringMatching(keyword="[", name="has_citation_marker"))  # format sanity
.check(Conformity(rule="Every factual claim must cite a source from the provided context.", name="cites_sources"))
.check(Groundedness(context=chunks, name="grounded_in_context"))
```

Avoid duplicating the same intent in `FnCheck` and `Conformity`. If you wrote a Conformity rule, you rarely need a parallel keyword FnCheck.

## Composing judges

- **Out-of-scope**: `Conformity` for refusal — not `Groundedness` (no valid context to ground in)
- **Either grounded OR polite decline**: `AnyOf(Groundedness(...), Conformity(rule="must decline when unsupported"))`
- **Strict multi-step agent**: `AllOf(AnswerRelevance(...), Conformity(...), Groundedness(...))`

## Calibrating judges

When a judge misfires, **rewrite the rule or prompt** — do not replace it with a keyword FnCheck. See `eval-iteration-loop.md` for the review → refine → re-run cycle.
