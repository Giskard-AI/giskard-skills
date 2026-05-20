# Simulate users with personas (RAG evals)

Source realistic **questions** with Giskard [`UserSimulator`](https://docs.giskard.ai/oss/checks/how-to/simulate-users). Pair static scenarios with gold Q&A, out-of-scope baselines, and fast CI.

**Design-time input planning** (dimensions, tuples, static gold cases): [`../../references/test-input-generation-core.md`](../../references/test-input-generation-core.md).

**Multi-turn mechanics**: [`../../references/multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md).

## Assigning users per turn

Different users can drive **different `.interact()` steps** in one scenario:

| Pattern | Example |
|---------|---------|
| **Chained simulators** | `.interact(inputs=employee_sim).interact(inputs=manager_sim)` — `max_steps=1` per role |
| **Phased single simulator** | One sim: vague → specific, or wrong topic → correction |
| **Trace-aware callable** | `.interact(inputs=lambda trace: ...)` |

Avoid static `"Hi"` warm-up turns; use a persona phase instead.

## When to ask the user

- "Who asks questions — employees, customers, researchers?"
- "Do threads involve handoffs (employee then manager) or one user refining their ask?"

If unknown, infer 3–5 personas from the agent description.

## Setup

```python
from giskard.checks import UserSimulator, set_default_generator
from giskard.agents.generators import Generator

set_default_generator(Generator(model="openai/gpt-4o-mini"))
```

## Objective archetypes (use when direction fits)

From [`scenario-directions.md`](./scenario-directions.md) — attach only when the direction row applies.

| ID | Use when direction is… | Persona elicits | Typical checks |
|----|------------------------|-----------------|----------------|
| `factual_lookup` | Simple KB question | Direct question in domain terms | retrieval `FnCheck` → `Groundedness` |
| `multi_hop_synthesis` | Needs 2+ chunks | Question requiring combine/compare | retrieval + `Groundedness` |
| `citation_focus` | Must cite sources | Ask for policy with source expectation | retrieval + citation `Conformity` |
| `oos_probe` | Adjacent uncovered topic | In-scope then adjacent missing topic | decline on OOS turn; no required retrieval |

## Conversation-shape archetypes (phased single simulator)

| ID | Phases | Trace-pattern checks |
|----|--------|----------------------|
| `wrong_topic_then_correct` | Mislabeled product/policy → corrected ask | non-retrieval before retrieval on data turn |
| `offtopic_then_data` | Chitchat or unrelated opener → in-domain question | same |
| `vague_then_specific` | Broad → narrow follow-up | `multi_turn`; retrieval on factual turns |
| `paraphrase_same_fact` | Same fact, different wording across turns | `SemanticSimilarity` or consistency judge |

### Example: phased `offtopic_then_data`

```python
offtopic_then_data = UserSimulator(
    persona="""
    You are an employee using the internal knowledge base.
    Phase 1: Open with a brief social or off-topic message (not about company policy).
    Phase 2: Ask a concrete in-domain question about <topic from KB>.
    Do not mention chunks or retrieval. Stop when you have a clear answer.
    """,
    max_steps=5,
)

Scenario("offtopic_then_policy").interact(inputs=offtopic_then_data)
```

## Multi-user archetypes (chained `.interact()`)

| ID | Handoff | Steps |
|----|---------|-------|
| `employee_then_manager` | Employee asks HR question → manager asks compliance follow-up | employee_sim → manager_sim |
| `customer_then_supervisor` | Customer vague complaint → supervisor demands citation | customer_sim → supervisor_sim |

### Example: chained `employee_then_manager`

```python
employee_sim = UserSimulator(
    persona="""
    You are an employee. Ask one question about parental leave in plain language.
    One message only.
    """,
    max_steps=1,
)

manager_sim = UserSimulator(
    persona="""
    You are the employee's manager in the same thread.
    Ask whether parental leave is paid and cite the official policy.
    One message only.
    """,
    max_steps=1,
)

(
    Scenario("employee_then_manager_leave")
    .interact(inputs=employee_sim, metadata={"persona_id": "employee"})
    .interact(inputs=manager_sim, metadata={"persona_id": "manager"})
)
```

## Wire into scenarios (single simulator)

```python
curious_user = UserSimulator(
    persona="""
    You are a user looking up information in the knowledge base.
    - Start with a vague question about <topic>
    - Ask one specific follow-up based on the agent's answer
    - Do not mention "documents", "chunks", or "retrieval"
    - Stop when you have a concrete answer or a clear decline
    """,
    max_steps=5,
)

Scenario("follow_up_persona").interact(inputs=curious_user)
```

Adapt `context_key` / `answer_key` to the user's output shape — see [`tool-usage.md`](./tool-usage.md).

## Suite mix

Unless the user wants static-only: combine static gold/OOS with phased and chained personas for paraphrase, follow-up, and handoffs.

## When a persona scenario fails

See [`../../references/error-analysis.md`](../../references/error-analysis.md).

## See also

- [`multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md)
- [`scenario-directions.md`](./scenario-directions.md)
- [`tool-usage.md`](./tool-usage.md)
- [`api-reference.md`](./api-reference.md)
