# SQL safety and guardrails (text-to-SQL)

How to validate SQL **before execution** (guardrails) and how to assert safe behavior in **eval suites** (evaluators). Adapt rules to your engine and policy.

## Guardrails (inline, deterministic)

Run on every proposed SQL string **before** the database executes it:

- Blocked keywords or statement types (`DELETE`, `DROP`, `UPDATE`, … per your policy)
- Required `LIMIT` on non-aggregate `SELECT`
- Dialect rules (quoted identifiers, schema prefixes, forbidden functions)
- Injection patterns (`;` stacking, comment tricks) when applicable

Implement as a pure function (e.g. `validate_sql(sql) -> ValidationResult`) unit-tested without an LLM. Keep latency in the low milliseconds.

## Evaluators (suite-level)

After the agent runs, inspect `queries[]` in the trace:

- `FnCheck`: no **successful** destructive SQL in executed queries
- `FnCheck`: `blocked: true` or refusal language in `answer` when user requests unsafe operations
- `RegexMatching` on SQL strings for `LIMIT`, allowed tables, etc.

Prefer **`FnCheck` over `Conformity`** for refusal wording — judges often false-fail on valid refusals.

## Scenario directions

Map to Tier 1 safety directions in [`scenario-directions.md`](./scenario-directions.md). Pair guardrail unit tests with at least one end-to-end agent scenario per blocked operation class.

## See also

- [`eval-dimensions.md`](./eval-dimensions.md) §3 — dimension summary
- [`../references/eval-lifecycle.md`](../references/eval-lifecycle.md) — guardrails vs evaluators
- [`tool-usage.md`](./tool-usage.md) — `queries[]` trace contract
- Ship deterministic validator tests in CI (pytest); optional demo in `example-agent/`
