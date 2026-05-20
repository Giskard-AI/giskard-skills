# Workflow evaluation (text-to-SQL)

Use when the system is **multi-step**: plan → generate SQL → execute → summarize (or analogous tools). Keep state names **generic** — map them to your agent’s logging fields.

## Two phases

### Phase 1 — End-to-end (black box)

One binary question per task: **did the user get a correct, safe outcome?**

```python
Scenario("e2e_metric_question")
.interact(inputs="<user question about a metric>")
.check(FnCheck(name="sql_tool_used", fn=lambda t: _has_queries(t)))
.check(FnCheck(name="answer_plausible", fn=lambda t: _matches_policy(t)))  # or gold FnCheck / LLMJudge
```

Define `_matches_policy` from your error-analysis taxonomy (numeric tolerance, refusal keywords, etc.).

### Phase 2 — Step-level diagnostics

After E2E failures cluster, instrument **labeled steps** in `queries[]` or metadata, e.g.:

```python
{"step": "plan_sql", "sql": "...", "success": True}
{"step": "execute_sql", "sql": "...", "success": False, "error": "..."}
```

If the agent does not emit steps today, ask the user to add lightweight step tags — evals cannot diagnose transitions without them.

**Per-step checks (examples — rename to match your trace):**

| Step concern | Check idea |
|--------------|------------|
| Tool chosen | `FnCheck`: execute tool invoked, not a generic LLM-only path |
| Parameters / SQL shape | `RegexMatching` or shared `validate_sql()` |
| Execution | `FnCheck`: `success: true` for allowed SELECTs |
| Answer vs result | `FnCheck` or `LLMJudge` with narrow criteria |

## Transition failure matrix

Track **last successful step → first failing step**. Count failures per cell to prioritize engineering work.

Example layout (replace step labels with yours):

| Last OK ↓ / First fail → | `plan` | `generate_sql` | `execute` | `answer` |
|--------------------------|--------|----------------|-----------|----------|
| _(start)_ | | 3 | 1 | |
| `plan` | | 5 | 2 | |
| `generate_sql` | | | 12 | 1 |
| `execute` | | | | 4 |

Build the matrix from production or eval traces during error analysis — not from hypothetical flows.

## Mapping to `giskard.checks`

- **High-frequency transition** (e.g. execute → fail): dedicated `Scenario` with inputs that stress that path; `FnCheck` on the failing step’s output.
- **Rare edge case**: static repro with minimal `inputs` (see [`../../references/error-analysis.md`](../../references/error-analysis.md)).
- **Do not** encode the whole matrix as 50 scenarios upfront — grow the suite as the matrix highlights hotspots.

## Efficiency and retries

Optional `FnCheck`s (adapt thresholds):

- `LesserThan` or `FnCheck`: query count ≤ N unless question requires exploration
- `FnCheck`: no repeated identical failed SQL without changed prompt

## See also

- [`tool-usage.md`](./tool-usage.md) — `queries[]` contract
- [`../../references/error-analysis.md`](../../references/error-analysis.md) — first-failure annotation
- [`../../references/eval-lifecycle.md`](../../references/eval-lifecycle.md) — guardrails on SQL validator vs suite evals
