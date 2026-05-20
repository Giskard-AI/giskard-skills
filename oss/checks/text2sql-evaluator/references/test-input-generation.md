# Test input generation (text-to-SQL)

> Shared workflow (dimensions → tuples → questions, static vs personas): [`../../references/test-input-generation-core.md`](../../references/test-input-generation-core.md)

Structured ways to build **user questions** for analytics agents when the user has no golden set yet. Prefer **real production questions** when available.

## SQL-specific dimensions

Define axes that describe how **users** ask, not how SQL is written:

| Example dimension | Example values (yours will differ) |
|-------------------|-----------------------------------|
| `metric_type` | count, sum, average, ranking |
| `ambiguity` | precise, vague ("active"), comparative |
| `time_scope` | all-time, last month, point-in-time |
| `persona_role` | executive, analyst, operator |

Follow the core tuple workflow, then map each tuple to a **scenario direction** in [`scenario-directions.md`](./scenario-directions.md) before writing `Scenario` code.

## Anchoring on schema + metrics

Text-to-SQL evals anchor on **DDL / schema summary** and **fixed seed data**, not KB chunks:

- Tuple → question should be answerable (or honestly unanswerable) given the user's schema
- When seed DB is fixed, derive gold `FnCheck`s from known counts/sums
- Skip Tier 3 directions when schema lacks required tables — note gaps in the report

## Personas vs static prompts

See core doc for the default ~40/40/20 mix. SQL-specific guidance:

- **Static** — gold metrics, `validate_sql` CI, minimal repro after error analysis
- **Personas** — vague metrics, wrong-table first, exec/analyst handoffs — [`simulate-users.md`](./simulate-users.md)

## KB-style generation (RAG)

If the user also has document grounding, see [`../../rag-evaluator/references/test-input-generation.md`](../../rag-evaluator/references/test-input-generation.md) for chunk-anchored Q&A patterns.

## See also

- [`../../references/test-input-generation-core.md`](../../references/test-input-generation-core.md)
- [`scenario-directions.md`](./scenario-directions.md)
- [`eval-dimensions.md`](./eval-dimensions.md)
