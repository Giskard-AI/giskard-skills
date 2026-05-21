# Checks catalog (text-to-SQL)

> Shared layer stack: [`../../references/checks-catalog-core.md`](../../references/checks-catalog-core.md)

Which [built-in Giskard checks](https://docs.giskard.ai/oss/checks/reference/checks) to use for database analytics agents. Prefer **deterministic** checks before LLM judges. Always pair in-domain scenarios with [`tool-usage.md`](./tool-usage.md) (`FnCheck` on `queries[]` before answer judges alone).

**Always set `name=`** on every check. Full API notes: [`api-reference.md`](./api-reference.md).

---

## Recommended stack (by layer)

| Layer | Checks | Typical use |
|-------|--------|-------------|
| 1 — Tool usage | `FnCheck` | `len(queries) > 0`, `blocked: true`, table name in SQL |
| 2 — SQL shape | `RegexMatching`, `FnCheck` + `validate_sql` | `LIMIT`, quoted identifiers, no `DELETE` in executed SQL |
| 3 — Gold answers | `Equals`, `GreaterEquals` / `LesserThan`, `FnCheck` (parse number from `answer`) | Fixed seed DB counts and sums |
| 4 — Wording | `StringMatching`, `Not` + `StringMatching` | Refusal keywords; forbid "run this SQL yourself" |
| 5 — Paraphrase tolerance | `SemanticSimilarity` | Gold Q&A when answer phrasing varies |
| 6 — Subjective / vague metrics | `AnswerRelevance`, `LLMJudge`, `Conformity` | "Active users" assumptions — **not** for safety or exact counts |

---

## Rule-based checks

### `FnCheck`

Primary tool for tool trace, gold metrics, and safety.

```python
FnCheck(
    name="executed_query",
    fn=lambda trace: len((trace.last.outputs or {}).get("queries") or []) > 0,
)
```

Use for: `queries[]` non-empty, `blocked: true`, parsing `"3"` from `answer`, scanning all `trace.interactions` in multi-turn suites.

**Multi-turn safety:** refusal on an early turn then safe SQL on the last turn is valid — scan **all** interactions for refusal/blocked, not `trace.last` only. Pattern: loop `trace.interactions`, check `outputs["queries"]` for `blocked` and `outputs["answer"]` for refusal phrases.

**Trace-pattern checks** (dynamic `UserSimulator` or chained users): e.g. ∃ i<j with empty `queries` on turn i and non-empty on j — see [`../../references/multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md). **Do not** require `non_tool_before_data` when phase 1 is a vague data question (eager SQL is valid). **Index-based** `trace.interactions[0]` only for static per-step `.interact()` chains.

### `RegexMatching`

Inspect SQL strings in `queries[-1].sql` or aggregated query log.

```python
RegexMatching(
    name="select_has_limit",
    pattern=r"\bLIMIT\s+\d+",
    text_key='trace.last.outputs["queries"][0]["sql"]',  # adjust index/path to your shape
)
```

Use for: `LIMIT`, `JOIN`, quoted `"User"`, dialect rules. Prefer over `Conformity` when the pass condition is syntactic.

### `StringMatching`

Fast signals on natural-language `answer`.

```python
StringMatching(name="mentions_user_table", keyword="User", text_key='trace.last.outputs["answer"]')
```

Use for: refusal phrases (`not allowed`, `only select`), listing schema table names. For **absence**, wrap in `Not` — there is no `expected=False` on `StringMatching`.

### `Equals` / `NotEquals`

When the gold value is exact and stable.

```python
Equals(name="user_count", expected_value=3, key='trace.last.outputs["answer"]')  # if answer is bare int/str
GreaterEquals(name="min_revenue_cents", expected_value=17000, key="trace.last.metadata.parsed_revenue")
```

Use `expected_value_key` to compare two trace fields (e.g. answer vs baseline turn).

### `GreaterThan` / `GreaterEquals` / `LesserThan` / `LesserThanEquals`

Numeric thresholds on structured outputs or metadata.

```python
GreaterEquals(name="at_least_one_query", expected_value=1, key='trace.last.outputs["queries"].__len__')  # prefer FnCheck for length
LesserThan(name="latency_ok_ms", expected_value=5000, key="trace.last.metadata.latency_ms")
```

Use for: confidence scores, row counts in metadata, retry limits (`len(queries) <= 3` via `FnCheck` is often clearer).

### `SemanticSimilarity`

Gold natural-language answers when wording varies.

```python
SemanticSimilarity(
    name="matches_gold_answer",
    reference_text="There are 3 users in the database.",
    actual_answer_key='trace.last.outputs["answer"]',
    threshold=0.6,
)
```

Default threshold `0.95` is very strict — calibrate to **0.5–0.7** for paraphrased explanations. Fields are `reference_text` / `reference_text_key`, not `reference=`. Prefer `FnCheck` / `Equals` on parsed numbers when the gold metric is numeric.

### Composition: `AllOf`, `AnyOf`, `Not`

```python
AllOf(
    name="safe_and_blocked",
    checks=[
        FnCheck(name="blocked_flag", fn=lambda t: (t.last.outputs.get("queries") or [{}])[-1].get("blocked")),
        StringMatching(name="refusal_text", keyword="not allowed", text_key='trace.last.outputs["answer"]'),
    ],
)
AnyOf(name="declined_or_blocked", checks=[refusal_fn_check, blocked_fn_check])
```

---

## LLM-based checks

Require `set_default_generator(Generator(...))`. See [checks reference](https://docs.giskard.ai/oss/checks/reference/checks).

| Check | Use for text2sql | Avoid for |
|-------|------------------|-----------|
| `AnswerRelevance` | In-domain questions where SQL/answer shape varies | Exact gold counts (use `FnCheck` / `Equals`) |
| `Conformity` | "Must state what 'active' means" | Refusal wording, DELETE blocked (false fails) |
| `LLMJudge` | Multi-criteria: "number consistent with described SQL" | Anything `FnCheck` can assert on `queries[]` |
| `Groundedness` | Rare — only if agent returns evidence chunks alongside SQL | Default choice for SQL agents |

Custom domain logic: subclass `BaseLLMCheck` only when `LLMJudge` prompts become unwieldy.

---

## What not to use as a substitute for tool checks

| Anti-pattern | Prefer |
|--------------|--------|
| `Conformity("must use the database")` only | `FnCheck` on `queries[]` |
| `LLMJudge("did it query?")` only | `FnCheck(len(queries) > 0)` |
| `Equals` on free-text explanations | `FnCheck` parse number or `SemanticSimilarity` |
| `Groundedness` without SQL trace | `FnCheck` + optional `AnswerRelevance` |

---

## Pass rate and suite design

Persistent **100% pass** often means scenarios are too easy. Add directions from error analysis (ambiguous metrics, wrong-table joins, safety). Run [`../../references/iterative-eval-loop.md`](../../references/iterative-eval-loop.md) after every suite — tune until failures are actionable.

## See also

- [`../../references/error-analysis.md`](../../references/error-analysis.md)
- [`../../references/eval-lifecycle.md`](../../references/eval-lifecycle.md)
- [`workflow-eval.md`](./workflow-eval.md) — multi-step agents
- [`tool-usage.md`](./tool-usage.md) — required SQL tool `FnCheck` patterns
- [`eval-dimensions.md`](./eval-dimensions.md) — dimension → check mapping
- [`examples.md`](./examples.md) — worked scenarios
- `rag-evaluator/references/checks-catalog.md` — parallel catalog for RAG
- [Official checks API](https://docs.giskard.ai/oss/checks/reference/checks)
