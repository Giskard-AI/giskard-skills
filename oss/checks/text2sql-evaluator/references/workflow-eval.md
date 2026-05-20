# Workflow evaluation (text-to-SQL)

> Shared pattern: [`../../references/workflow-eval-core.md`](../../references/workflow-eval-core.md) — E2E first, transition matrix, grow scenarios from hotspots.

SQL-specific step examples below. Map generic step names to your agent's `queries[]` or metadata.

## SQL step examples

Typical multi-step flow: plan → generate SQL → execute → summarize.

### Phase 1 — End-to-end

```python
Scenario("e2e_metric_question")
.interact(inputs="<user question about a metric>")
.check(FnCheck(name="sql_tool_used", fn=lambda t: _has_queries(t)))
.check(FnCheck(name="answer_plausible", fn=lambda t: _matches_policy(t)))
```

Define `_matches_policy` from your error-analysis taxonomy (numeric tolerance, refusal keywords, etc.).

### Phase 2 — Step-level diagnostics

Instrument **labeled steps** in `queries[]` or metadata:

```python
{"step": "plan_sql", "sql": "...", "success": True}
{"step": "execute_sql", "sql": "...", "success": False, "error": "..."}
```

| Step concern | Check idea |
|--------------|------------|
| Tool chosen | `FnCheck`: execute tool invoked, not LLM-only path |
| SQL shape | `RegexMatching` or shared `validate_sql()` |
| Execution | `FnCheck`: `success: true` for allowed SELECTs |
| Answer vs result | `FnCheck` or calibrated `LLMJudge` |

## Transition matrix (SQL steps)

Replace step labels with yours — e.g. `plan` → `generate_sql` → `execute` → `answer`:

| Last OK ↓ / First fail → | `plan` | `generate_sql` | `execute` | `answer` |
|--------------------------|--------|----------------|-----------|----------|
| _(start)_ | | 3 | 1 | |
| `plan` | | 5 | 2 | |
| `generate_sql` | | | 12 | 1 |
| `execute` | | | | 4 |

Build from production or eval traces during error analysis.

## Efficiency and retries

- `FnCheck`: query count ≤ N unless exploration is required
- `FnCheck`: no repeated identical failed SQL without changed prompt

## See also

- [`tool-usage.md`](./tool-usage.md) — `queries[]` contract
- [`../../references/workflow-eval-core.md`](../../references/workflow-eval-core.md)
- [`../../references/error-analysis.md`](../../references/error-analysis.md)
- [`../../references/eval-lifecycle.md`](../../references/eval-lifecycle.md)
