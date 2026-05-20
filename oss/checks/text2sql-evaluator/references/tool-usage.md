# Correct SQL tool usage (text-to-SQL evals)

**Every in-domain data scenario should verify the agent actually used the SQL / analytics tool** (e.g. `execute_query`, `run_sql`), not only that the final answer looks good. Models often hallucinate counts without querying.

## What to check

| Failure | Signal | Check |
|---------|--------|--------|
| **No query** | `queries` empty on "how many users?" | `FnCheck(len(queries) > 0)` |
| **Wrong tool** | Answer without SQL tool in trace | Same + ask user for tool log in output |
| **Unsafe SQL succeeded** | `success: true` on DELETE | `FnCheck` on `queries[]` |
| **Schema-only answer** | Table list from prompt, no query | OK for metadata questions only — see below |

**Order of checks**: (1) correct tool invoked → (2) SQL shape / guardrails → (3) answer relevance or gold metric.

## Require structured tool trace

Ask the user to return:

```python
{"answer": str, "queries": [{"sql": str, "success": bool, "blocked": bool, ...}]}
```

If the user has no `queries[]` in the return shape, ask them to wrap the agent before shipping evals. Without a tool log, usage checks devolve into `Conformity` ("must use database") — weak signal.

## Deterministic patterns (preferred)

```python
def _queries(trace) -> list:
    return list((trace.last.outputs or {}).get("queries") or [])

executed = FnCheck(name="executed_query", fn=lambda t: len(_queries(t)) > 0)

used_entity_table = FnCheck(
    name="queried_entity_table",
    fn=lambda t: any('"<EntityTable>"' in str(q.get("sql", "")) for q in _queries(t)),
)
```

Replace `<EntityTable>` with the user's table name (e.g. `"User"`, `customers`).

Combine with gold `FnCheck` on parsed numbers in `answer` when the user provides a fixed seed DB.

## Exceptions (document in scenario plan)

| Question type | Tool required? |
|---------------|----------------|
| Counts, sums, filters, samples | **Yes** |
| "What tables exist?" with schema in system prompt | **No** — check `answer` lists real tables |
| Out-of-scope (not in DB) | May query then decline; or decline without query |
| Destructive intent | Tool may return `blocked: true` — check no successful destructive SQL |

## Dynamic multi-turn (personas and handoffs)

- **Phased single simulator**: one `.interact(inputs=sim)` — chitchat or wrong ask may have empty `queries[]`; data phases must query. Use trace-pattern checks, not fixed turn index — see [`../../references/multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md).
- **Chained simulators**: different `UserSimulator` per `.interact()` step (`max_steps=1` per role). Tool required on analyst/data steps; optional empty `queries[]` on executive vague opener if no metric yet.
- **Per-step `.check()`** after a step when only that role must invoke SQL.

## With `UserSimulator` personas

Personas must drive **data questions**, not SQL syntax lessons.

```python
UserSimulator(
    persona="""
    You are an executive who asks vague analytics questions.
    - Ask how many active customers exist; push for a definition if unclear
    - Do not write SQL yourself
    - Stop when you have a number and what "active" means
    """,
    max_steps=6,
)
```

Assert `len(queries) > 0` on the **last** turn or on **any** turn with a factual answer:

```python
FnCheck(
    name="queried_on_data_question",
    fn=lambda trace: any(
        len((i.outputs or {}).get("queries") or []) > 0
        for i in trace.interactions
    ),
)
```

## See also

- [`checks-catalog.md`](./checks-catalog.md) — `RegexMatching`, `Equals`, `SemanticSimilarity`, composition
- [`eval-dimensions.md`](./eval-dimensions.md) §1 Tool use
- [`scenario-directions.md`](./scenario-directions.md) — Proven check patterns
- `rag-evaluator/references/tool-usage.md` — retrieval tool parity
