# Test input generation (text-to-SQL)

Structured ways to build **user questions** for analytics agents when the user has no golden set yet. Prefer **real production questions** when available.

## Dimensions and tuples

Define axes that describe how **users** ask, not how SQL is written:

| Example dimension | Example values (yours will differ) |
|-------------------|-----------------------------------|
| `metric_type` | count, sum, average, ranking |
| `ambiguity` | precise, vague ("active"), comparative |
| `time_scope` | all-time, last month, point-in-time |
| `persona_role` | executive, analyst, operator |

1. Hand-write **~20 tuples** (one value per dimension).
2. Optionally scale tuples with an LLM in a **separate** step from natural-language generation.
3. Convert each tuple to a realistic **question** (no SQL from the user).
4. Run questions through the **real agent**; collect traces for [`../../references/error-analysis.md`](../../references/error-analysis.md).

Map each tuple to a **scenario direction** in [`scenario-directions.md`](./scenario-directions.md) before writing `Scenario` code.

## Personas vs static prompts

- **Static** `inputs="..."` — gold metrics, CI speed, minimal repro after error analysis.
- **`UserSimulator` personas** — vagueness, follow-ups, phrasing variance — see [`simulate-users.md`](./simulate-users.md).

Default mix (unless user opts out): ~40% static, ~40% quality personas, ~20% safety-oriented dialogue.

## KB-style generation (RAG)

If the user also has document grounding, see [`../../rag-evaluator/references/test-input-generation.md`](../../rag-evaluator/references/test-input-generation.md) for chunk-anchored Q&A patterns. Text-to-SQL evals usually anchor on **schema + metrics**, not chunks.

## See also

- [`scenario-directions.md`](./scenario-directions.md) — which failure modes to target
- [`eval-dimensions.md`](./eval-dimensions.md) — checks per dimension
