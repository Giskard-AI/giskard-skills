# Simulate users with personas (text-to-SQL)

Source realistic **questions** with Giskard [`UserSimulator`](https://docs.giskard.ai/oss/checks/how-to/simulate-users). Pair static scenarios with gold metrics, guardrail baselines, and fast CI.

**Design-time input planning** (dimensions, tuples, static gold cases): [`../../references/test-input-generation-core.md`](../../references/test-input-generation-core.md).

**Multi-turn mechanics** (chained users per step, trace-pattern checks): [`../../references/multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md).

## Assigning users per turn

Each `.interact()` step can use a **different** `UserSimulator`, static string, or trace-aware callable — see [`../../references/multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md#different-personas-inputs-and-targets-per-step).

Different users can drive **different `.interact()` steps** in one scenario:

| Pattern | Example |
|---------|---------|
| **Chained simulators** | `.interact(inputs=exec_sim).interact(inputs=analyst_sim)` — `max_steps=1` per sim for role handoff |
| **Phased single simulator** | One `UserSimulator` with phase list in `persona=` — `max_steps` 4–8 |
| **Trace-aware callable** | `.interact(inputs=lambda trace: ...)` |

Avoid static `"Hi"` warm-up turns; use a persona phase instead.

## When to ask the user

- "Who asks questions — BI analysts, executives, support?"
- "Do threads involve handoffs (exec then analyst) or one user refining their ask?"

If unknown, infer 3–5 personas from the agent description.

## Setup

```python
from giskard.checks import UserSimulator, set_default_generator
from giskard.agents.generators import Generator

set_default_generator(Generator(model="openai/gpt-4o-mini"))
```

## Objective archetypes (use when direction fits)

Map from [`scenario-directions.md`](./scenario-directions.md) — do not attach every archetype to every scenario.

| ID | Use when direction is… | Persona elicits (dynamic wording) | Typical checks |
|----|------------------------|-----------------------------------|----------------|
| `aggregate_metric` | Revenue, counts, AOV | Filters + SUM/COUNT; business language | `fn_gold_count` if seed known; tool on data turns |
| `join_grain` | Users per org, per-team metrics | Multi-table question; no SQL from user | tool + JOIN/bridge in SQL |
| `ambiguous_metric` | "Active", "real" users | Vague then clarify in dialogue | tool + `Conformity` on assumptions |
| `schema_exploration` | What tables exist | Discovery questions | answer or tool per schema-in-prompt rules |
| `refusal_dialogue` | Safety directions | Destructive ask in conversation | full-trace: no successful DELETE; refusal/blocked on **any** turn — not `trace.last` only |

## Conversation-shape archetypes (phased single simulator)

One `UserSimulator`; phases are instructions, not fixed strings.

| ID | Phases (simulator chooses words) | Trace-pattern checks |
|----|----------------------------------|----------------------|
| `wrong_then_correct` | Wrong table/metric first; after agent reply, ask the real question | non-tool before data tool |
| `offtopic_then_data` | Social or unrelated opener; then analytics question | non-tool before data tool |
| `vague_then_specific` | Vague KPI; drill down after answer | `multi_turn`; tool when specifics appear |
| `task_then_close` | Business question; short thanks without new data ask | tool early; later turns may have no new query |
| `pressure_then_accept` | Push back on refusal (safety only) | destructive blocked throughout |

### Example: phased `wrong_then_correct`

```python
wrong_then_correct = UserSimulator(
    persona="""
    You are a newcomer to the company's data chatbot.
    Phase 1: Ask about "customers" or "accounts" in a vague way that might map to the wrong table.
    Phase 2: After the agent responds, ask clearly how many users are in the database (excluding test accounts if relevant).
    Do not write SQL. Stop when you have a clear user count or the agent explains limits.
    """,
    max_steps=6,
)

Scenario("wrong_then_correct_entity_count").interact(inputs=wrong_then_correct)
```

## Multi-user archetypes (chained `.interact()`)

Distinct `UserSimulator` per step; **`max_steps=1`** each unless that role needs a mini-dialogue.

| ID | Handoff | Steps |
|----|---------|-------|
| `exec_then_analyst` | Executive vague metric → analyst precise follow-up | exec_sim → analyst_sim |
| `support_then_engineer` | Support reports symptom → engineer asks for SQL-backed count | support_sim → engineer_sim |

### Example: chained `exec_then_analyst`

```python
exec_sim = UserSimulator(
    persona="""
    You are a busy executive. Ask vaguely about revenue or performance in one short message.
    Do not name SQL tables. Do not ask follow-ups.
    """,
    max_steps=1,
)

analyst_sim = UserSimulator(
    persona="""
    You are a BI analyst continuing the same thread.
    Ask for total revenue from completed orders in cents, precisely.
    One message only unless the agent's answer is unclear.
    """,
    max_steps=1,
)

(
    Scenario("exec_then_analyst_revenue")
    .interact(inputs=exec_sim, metadata={"persona_id": "exec"})
    .interact(inputs=analyst_sim, metadata={"persona_id": "analyst"})
    .check(fn_any_interaction_executed_query())
)
```

## Wire into scenarios (single simulator)

```python
from giskard.checks import Scenario, FnCheck, UserSimulator

exec_persona = UserSimulator(
    persona="""
    You are a busy executive using a data chatbot.
    - Ask how many active customers there are (vague; do not name SQL tables)
    - If the agent gives a number without defining "active", ask what that means
    - Stop when you have a clear count and definition
    """,
    max_steps=6,
)

Scenario("active_customers_exec_persona").interact(inputs=exec_persona)
```

Use `suite.run(target=your_agent)` — do not pass `outputs=` in `.interact()` when using `target` at run time.

## Assert on `goal_reached` (optional)

```python
from giskard.checks.generators.user import UserSimulatorOutput

def _goal_reached(trace) -> bool:
    sim_out = (trace.last.metadata or {}).get("simulator_output")
    if isinstance(sim_out, UserSimulatorOutput):
        return sim_out.goal_reached
    return True

FnCheck(name="simulator_goal_reached", fn=lambda trace: _goal_reached(trace))
```

## Suite mix (default)

Canonical mix and multi-turn check patterns: [`../../references/multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md#default-suite-composition).

| Share | Type | Purpose |
|-------|------|---------|
| ~40% | Static `inputs="..."` | Gold metrics, guardrails, fast CI |
| ~40% | Phased or chained personas | Realistic phrasing, handoffs, ambiguity, mixed directions |
| ~20% | Safety dialogue personas | Destructive intent via conversation |

Persona scenarios: `fn_multi_turn(min_turns=3)` (or equivalent), trace-pattern tool/safety `FnCheck`s, **`llm_judge_conversation`** / **`Conformity`** rubrics — not SQL substring traps on simulator finals.

Do not ship a first suite that is only single-turn static strings unless the user explicitly asked.

## When a persona scenario fails

See [`../../references/error-analysis.md`](../../references/error-analysis.md): first upstream failure, single-turn repro, N−1 prefix replay.

Run the loop **with the user** — [`../../references/iterative-eval-loop.md`](../../references/iterative-eval-loop.md):

1. Open **latest** traces from `eval/results.json` (turn #, user text, agent answer, `queries[]`)
2. Audit **scenario setup** — persona phases, `max_steps`, rubric bullets in `eval/scenarios.py`
3. Classify: agent bug | simulator drift | judge miscalibration | suite too easy
4. **Propose** trace-backed changes; **ask** before editing scenarios or agent

Do not harden with SQL substring checks or unbounded simulator turns without user confirmation.

## See also

- [`multi-turn-scenarios.md`](../../references/multi-turn-scenarios.md) — per-turn users, trace-pattern checks
- [`scenario-directions.md`](./scenario-directions.md) — which directions to cover
- [`tool-usage.md`](./tool-usage.md) — `FnCheck` on `queries[]`
- [`api-reference.md`](./api-reference.md) — `UserSimulator` fields
