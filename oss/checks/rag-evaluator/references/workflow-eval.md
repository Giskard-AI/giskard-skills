# Workflow evaluation (RAG)

> Shared pattern: [`../../references/workflow-eval-core.md`](../../references/workflow-eval-core.md) — E2E first, transition matrix, grow scenarios from hotspots.

RAG-specific step examples below. Map generic step names to your `tool_calls[]` or logging.

## RAG step examples

Typical flow: retrieve → rerank → generate → cite (or agentic search loops).

### Phase 1 — End-to-end

```python
Scenario("e2e_policy_question")
.interact(inputs="<user question>")
.check(FnCheck(name="retrieval_used", fn=_retrieval_ran))
.check(Groundedness(name="grounded", context_key='trace.last.outputs["context"]', answer_key='trace.last.outputs["answer"]'))
```

### Phase 2 — Step-level (when instrumented)

If traces include step metadata (e.g. `tool_calls[]` with `step: retrieve | rerank | generate`):

| Step concern | Check idea |
|--------------|------------|
| Retrieve invoked | `FnCheck` before judging answer |
| Rerank / filter | `FnCheck` on intermediate doc lists |
| Generation | `Groundedness` on chunks the model actually saw |
| Citation | `RegexMatching` + doc ID validation |

## Transition matrix (RAG steps)

Example cells (replace with your step labels):

| Last OK ↓ / First fail → | `retrieve` | `rerank` | `generate` | `cite` |
|--------------------------|------------|----------|------------|--------|
| _(start)_ | | 2 | | |
| `retrieve` | | 4 | 1 | |
| `rerank` | | | 6 | |
| `generate` | | | | 3 |

Build from error analysis — not hypothetical flows.

## Multi-turn RAG

- Annotate **first failure** in `trace.interactions`
- Simplify to **one-turn** repro when the bug is not context-dependent
- **N−1 prefix replay** for realistic follow-ups — see [`simulate-users.md`](./simulate-users.md)

## See also

- [`tool-usage.md`](./tool-usage.md) — retrieval trace contract
- [`retrieval-metrics.md`](./retrieval-metrics.md) — IR metrics on labelled retrieval steps
- [`../../references/workflow-eval-core.md`](../../references/workflow-eval-core.md)
- [`../../references/error-analysis.md`](../../references/error-analysis.md)
