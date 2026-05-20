# Checks catalog (RAG)

> Shared layer stack: [`../../references/checks-catalog-core.md`](../../references/checks-catalog-core.md)

Which [built-in Giskard checks](https://docs.giskard.ai/oss/checks/reference/checks) to use for retrieval-augmented agents. Prefer **deterministic** checks before LLM judges. Always pair in-domain scenarios with [`tool-usage.md`](./tool-usage.md) (retrieval `FnCheck` before `Groundedness` alone).

**Always set `name=`** on every check. Full API notes: [`api-reference.md`](./api-reference.md).

---

## Recommended stack (by layer)

| Layer | Checks | Typical use |
|-------|--------|-------------|
| 1 — Tool usage | `FnCheck` | `sources`, `context`, or `tool_calls` non-empty |
| 2 — Retrieval quality | `FnCheck`, `Equals`, `GreaterEquals` | Recall@k, cited ID in KB — see [`retrieval-metrics.md`](./retrieval-metrics.md) |
| 3 — Format / policy | `StringMatching`, `RegexMatching`, `Not` | Citation markers `[1]`, refusal phrases, forbidden topics |
| 4 — Gold Q&A | `SemanticSimilarity`, `Equals` | Curated test set with reference answers |
| 5 — Grounding | `Groundedness` | Answer supported by retrieved context |
| 6 — Relevance & behavior | `AnswerRelevance`, `Conformity`, `LLMJudge` | Scope, tone, cite policy, multi-hop nuance |

---

## Rule-based checks

### `FnCheck`

Primary tool for retrieval trace, citation ID validation, and custom Recall@k.

```python
FnCheck(
    name="retrieval_tool_used",
    fn=lambda trace: bool(
        (trace.last.outputs or {}).get("sources")
        or (trace.last.outputs or {}).get("context")
    ),
)
```

Use for: non-empty retrieval, doc IDs in KB, multi-turn "at least one turn retrieved".

**Trace-pattern checks** for phased or chained `UserSimulator`: non-retrieval before retrieval on data turns — [`../../references/multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md). Index-based per-turn checks only for static `.interact()` chains.

### `StringMatching` / `RegexMatching`

```python
RegexMatching(name="has_citation_marker", pattern=r"\[\d+\]", text_key='trace.last.outputs["answer"]')
StringMatching(name="declines_phrase", keyword="don't have", text_key='trace.last.outputs["answer"]')
Not(name="no_medical_advice", check=StringMatching(keyword="diagnosis", text_key='trace.last.outputs["answer"]'))
```

Use for: citation format, disclaimer text, quick refusal sanity. **Not** a substitute for retrieval `FnCheck` — citations can be invented.

### `Equals` / comparison checks

```python
Equals(name="exact_doc_id", expected_value="policy-refund-2024", key='trace.last.outputs["sources"][0]')
LesserThan(name="latency_ok_ms", expected_value=3000, key="trace.last.metadata.latency_ms")
```

Use for: structured outputs, SLA metadata, chunk count caps.

### `SemanticSimilarity`

```python
SemanticSimilarity(
    name="matches_reference",
    reference_text_key="trace.last.metadata.reference_answer",
    actual_answer_key='trace.last.outputs["answer"]',
    threshold=0.65,
)
```

Attach gold via `.interact(..., metadata={"reference_answer": "..."})` or static `reference_text=`. Calibrate threshold down from default `0.95`.

Generic string-similarity scores (ROUGE/BERTScore-style) are weak primary gates for product answers. Use `SemanticSimilarity` for **gold Q&A paraphrase**; use IR metrics in [`retrieval-metrics.md`](./retrieval-metrics.md) for retrieval; use `Groundedness` for faithfulness to context.

### Composition: `AllOf`, `AnyOf`, `Not`

```python
AnyOf(
    name="grounded_or_declined",
    checks=[
        Groundedness(name="grounded", context_key='trace.last.outputs["context"]', answer_key='trace.last.outputs["answer"]'),
        Conformity(name="declined", rule="Agent explicitly says it cannot answer from the knowledge base."),
    ],
)
```

Standard pattern for **out-of-scope**: grounded OR polite decline — not `Groundedness` alone.

---

## LLM-based checks

Require `set_default_generator(Generator(...))`.

| Check | Use for RAG | Avoid for |
|-------|-------------|-----------|
| `Groundedness` | Core — answer supported by context | Out-of-scope (no valid context) |
| `AnswerRelevance` | Question answered in domain scope | Proving retrieval ran |
| `Conformity` | Behavioral rules ("must cite", tone) | Sole proxy for retrieval |
| `LLMJudge` | Citation–claim alignment, fabrication hunts, multi-turn quality | Exact keyword/refusal (use `StringMatching` / `FnCheck`) |
| `BaseLLMCheck` | Reusable domain-specific judge | One-off criteria (use `LLMJudge`) |

Calibrate judges before CI gating — [`../../references/judge-calibration.md`](../../references/judge-calibration.md).

---

## Check pairing by scenario type

| Scenario | Minimum checks |
|----------|----------------|
| In-domain factual | `FnCheck` retrieval → `Groundedness` → optional `AnswerRelevance` |
| Out-of-scope | `Conformity` or `StringMatching` decline — **no** required retrieval |
| Gold Q&A row | `FnCheck` retrieval → `SemanticSimilarity` or `Equals` → optional `Groundedness` |
| Must cite sources | `RegexMatching` + `FnCheck` IDs in KB + `LLMJudge` alignment |
| Paraphrase robustness | `UserSimulator` persona → `SemanticSimilarity` or `LLMJudge` consistency across turns |

---

## What not to use as a substitute for tool checks

| Anti-pattern | Prefer |
|--------------|--------|
| `Groundedness(context=[static chunks])` only | `FnCheck` on agent retrieval + dynamic `context_key` |
| `Conformity("must cite")` only | `RegexMatching` + retrieval `FnCheck` |
| `LLMJudge` for recall@k | `FnCheck` or `GreaterEquals` on metric — see retrieval-metrics |

---

## Pass rate and suite design

If the suite passes everything, add harder tuples/personas or stress directions from error analysis. Prefer growing coverage from observed failures, not inflating pass rates. Run [`../../references/iterative-eval-loop.md`](../../references/iterative-eval-loop.md) after every suite — classify agent vs check scope (especially `trace.last` on multi-turn refusal) before hardening.

## See also

- [`../../references/error-analysis.md`](../../references/error-analysis.md) — taxonomy before new scenarios
- [`../../references/eval-lifecycle.md`](../../references/eval-lifecycle.md) — CI vs production
- [`tool-usage.md`](./tool-usage.md) — retrieval tool `FnCheck` patterns
- [`eval-dimensions.md`](./eval-dimensions.md) — dimension catalog
- [`api-reference.md`](./api-reference.md) — imports, pitfalls, `UserSimulator`
- [`examples.md`](./examples.md) — citation layers, gold Q&A
- [Official checks API](https://docs.giskard.ai/oss/checks/reference/checks)
