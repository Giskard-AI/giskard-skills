# Checks catalog (core)

Shared layer stack for quality evaluators. Domain-specific rows and examples:

- RAG: [`rag-evaluator/references/checks-catalog.md`](../rag-evaluator/references/checks-catalog.md)
- Text-to-SQL: [`text2sql-evaluator/references/checks-catalog.md`](../text2sql-evaluator/references/checks-catalog.md)

Prefer **deterministic** checks before LLM judges. **Always set `name=`** on every check.

## Recommended stack (by layer)

| Layer | Checks | Role |
|-------|--------|------|
| 1 — Tool usage | `FnCheck` | Prove the agent used its tool (retrieval or SQL) |
| 2 — Domain metrics | `FnCheck`, `Equals`, `GreaterEquals`, `RegexMatching` | Gold answers, IR metrics, SQL shape |
| 3 — Format / policy | `StringMatching`, `RegexMatching`, `Not` | Citations, refusals, forbidden topics |
| 4 — Gold Q&A | `SemanticSimilarity`, `Equals` | Curated test set paraphrase |
| 5 — Grounding / relevance | `Groundedness`, `AnswerRelevance` | Faithfulness and on-topic answers |
| 6 — Behavior | `Conformity`, `LLMJudge` | Vague policy, tone — not primary safety gates |

Calibrate LLM judges before CI gating — [`judge-calibration.md`](./judge-calibration.md).

## Check selection principles

1. **Tool trace first** on in-domain questions — before `Groundedness` or `AnswerRelevance` alone.
2. **FnCheck over Conformity** for safety, counts, refusals, and SQL/retrieval shape.
3. **SemanticSimilarity** for gold Q&A paraphrase — not ROUGE/BERTScore as primary gates.
4. **Composition**: `AllOf`, `AnyOf`, `Not` for "grounded OR declined" patterns.

## FnCheck basics

```python
FnCheck(
    name="meaningful_name",
    fn=lambda trace: ...,  # receives Trace, not raw output
)
```

Use **trace-pattern** checks when turn order varies — see [`multi-turn-scenarios.md`](./multi-turn-scenarios.md).

## Composition example

```python
AnyOf(
    name="grounded_or_declined",
    checks=[
        Groundedness(name="grounded", context=[...]),
        Conformity(name="declined", rule="Agent must decline when information is not available."),
    ],
)
```

## See also

- [`generated-code-rules.md`](./generated-code-rules.md)
- [`judge-calibration.md`](./judge-calibration.md) — TPR/TNR before promoting judges to CI
- [`api-reference-core.md`](./api-reference-core.md)
- [Official checks reference](https://docs.giskard.ai/oss/checks/reference/checks)
