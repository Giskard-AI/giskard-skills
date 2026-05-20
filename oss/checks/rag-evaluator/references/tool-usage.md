# Correct retrieval tool usage (RAG evals)

**Every in-domain RAG scenario should verify the agent actually used retrieval** (or an equivalent search tool), not only that the final answer looks good. Answers can pass `Groundedness` with static context you attach in the test while the **production agent** still hallucinates from memory.

## What to check

| Failure | What it looks like | Why it matters |
|---------|------------------|----------------|
| **No retrieval** | `sources` / `context` / `tool_calls` empty on factual questions | Agent answers from parametric memory |
| **Wrong tool** | Search never called; only LLM or web tool used | Eval does not test your RAG stack |
| **Retrieve but ignore** | Chunks returned but answer contradicts them | Generation bug, not retrieval |
| **Out-of-scope over-retrieve** | Heavy retrieval then confident wrong answer | Should decline or say not in KB |

**Order of checks**: (1) tool was invoked → (2) retrieval quality (if labels exist) → (3) `Groundedness` / answer quality.

## Ask the user for tool surface

Before writing scenarios:

- Tool names (`retrieve`, `search`, `vector_search`, …)
- Return shape: `{"answer", "sources", "context", "citations", "tool_calls", …}`
- Whether retrieval is **inside** the agent or a separate `retrieve(query)` you can call in tests

If the agent returns only a string, ask them to wrap it so evals can see retrieval:

```python
def rag_agent(inputs: str) -> dict:
    result = pipeline(inputs)
    return {
        "answer": result.answer,
        "sources": result.source_ids,
        "context": result.chunks,
        "tool_calls": result.tool_log,
    }
```

## Deterministic `FnCheck` patterns

Adapt keys to the user's output shape.

```python
def _out(trace) -> dict:
    o = trace.last.outputs
    return o if isinstance(o, dict) else {}

retrieval_ran = FnCheck(
    name="retrieval_tool_used",
    fn=lambda trace: (
        len(_out(trace).get("sources") or []) > 0
        or len(_out(trace).get("context") or []) > 0
        or len(_out(trace).get("tool_calls") or []) > 0
    ),
)
```

**In-domain factual questions** — require retrieval:

```python
Scenario("policy_question")
.interact(inputs="What is the refund window?")
.check(retrieval_ran)
.check(Groundedness(context_key="trace.last.outputs.context", answer_key="trace.last.outputs.answer"))
```

**Out-of-scope** — do **not** require retrieval; use `Conformity` on decline (see `eval-dimensions.md` §3).

## Separate retriever callable

When `retrieve(query)` is exposed, you can test retrieval **without** the full agent:

```python
def test_recall_at_k():
    docs = retrieve("refund policy")
    ids = {d.id for d in docs}
    assert "expected-chunk-id" in ids
```

Still add end-to-end scenarios that assert the **agent** called retrieval in production wiring.

## Dynamic multi-turn (personas and handoffs)

Phased or **chained** `UserSimulator` per `.interact()` step: chitchat/off-topic turns may skip retrieval; factual turns must retrieve. Prefer trace-pattern checks over `trace.interactions[0]` when turn order varies — [`../../references/multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md).

## With `UserSimulator` personas

Personas should ask **domain questions** that require KB lookup, not meta questions about the system.

```python
UserSimulator(
    persona="""
    You are an employee asking HR policy questions.
    - Ask about parental leave, then a follow-up on eligibility
    - Use natural language; do not mention "documents" or "retrieval"
    - Stop when both questions are answered or the agent declines clearly
    """,
    max_steps=6,
)
```

Add `FnCheck` that **at least one turn** invoked retrieval (inspect all `trace.interactions`, not only `trace.last`).

## Multi-turn: check every factual turn

```python
FnCheck(
    name="retrieval_on_factual_turns",
    fn=lambda trace: all(
        len((i.outputs or {}).get("context") or []) > 0
        or "don't know" in str((i.outputs or {}).get("answer", "")).lower()
        for i in trace.interactions
        if _is_factual_turn(i)
    ),
)
```

Define `_is_factual_turn` from your test design, or require retrieval on `trace.last` only for single-turn suites.

## What not to do

- Pass RAG evals with **only** `Groundedness(context=[static chunks])` and no tool check — that tests the judge + chunks, not the agent pipeline.
- Use `Conformity("must cite sources")` as the only proxy for retrieval — citations can be invented.
- Skip tool checks on black-box agents without asking for a thin wrapper exposing `sources` / `context`.

## See also

- [`checks-catalog.md`](./checks-catalog.md) — full built-in check picker ([official reference](https://docs.giskard.ai/oss/checks/reference/checks))
- [`eval-dimensions.md`](./eval-dimensions.md) — dimension 0 (tool usage) and 4 (retrieval quality)
- [`simulate-users`](https://docs.giskard.ai/oss/checks/how-to/simulate-users) — persona-driven questions
- `text2sql-evaluator/references/tool-usage.md` — same pattern for SQL tools
