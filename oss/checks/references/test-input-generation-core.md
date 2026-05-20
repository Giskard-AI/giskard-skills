# Test input generation (core)

**Design-time** workflow for building eval inputs — what questions belong in the suite, often with gold labels. Domain-specific anchors and prompts:

- RAG (KB chunks, synthetic Q&A): [`rag-evaluator/references/test-input-generation.md`](../rag-evaluator/references/test-input-generation.md)
- Text-to-SQL (schema, metrics): [`text2sql-evaluator/references/test-input-generation.md`](../text2sql-evaluator/references/test-input-generation.md)

**Not the same as** per-skill `simulate-users.md` (RAG or text2sql) — that covers **runtime** `UserSimulator` dialogue. Use both: static/synthetic cases from here, realism from personas.

**Failure-hypothesis-first:** use the app, recruit users, or review traces ([`error-analysis.md`](./error-analysis.md)) before defining dimensions. Dimensions should reflect **observed failure modes**, not a pre-built query-type matrix.

## Dimensions and tuples

Avoid `"give me 20 test questions"` with no structure — outputs stay generic.

1. **Define dimensions** — axes of variation for **how users ask**, not implementation details. Rename for your product.

| Agent type | Example dimensions |
|------------|-------------------|
| RAG / docs Q&A | `topic_area`, `query_complexity`, `in_scope` |
| Text-to-SQL | `metric_type`, `ambiguity`, `time_scope`, `persona_role` |
| Support bot | `issue_type`, `user_mood`, `prior_context` |

2. **Hand-write ~20 tuples** — one value per dimension, e.g. `(billing, frustrated, follow_up)` or `(count, vague, all_time, executive)`.

3. **Scale tuples** — two approaches:

| Approach | Pros | Cons |
|----------|------|------|
| **Cross-product** of dimension values | Systematic coverage | Combinatorial explosion; many unrealistic tuples |
| **Direct LLM tuple generation** (same structure, sampled rows) | More realistic phrasing | May miss rare corners unless you seed with hand-written tuples |

Default: hand-write ~20 tuples, then ask an LLM to generate **more tuples** (not full questions yet). Filter unrealistic rows before converting to NL questions.

4. **Convert tuples to questions** (separate LLM call when using a generator):
   - One natural-language **question** per tuple (and optional gold label).

5. **Map each tuple** to a scenario direction in the skill's `scenario-directions.md` before writing `Scenario` code.

6. **Run questions through the real agent**; collect traces; sample ~100 for [`error-analysis.md`](./error-analysis.md).

Fix obvious product gaps (missing prompt rules, guardrails) before generating data for them.

## Static inputs vs UserSimulator

| Mechanism | When | Output |
|-----------|------|--------|
| **Static** `inputs="..."` | Gold metrics, CI repro, chunk-anchored Q&A with known labels | Fixed string per scenario |
| **Tuple → static** | Coverage matrix from dimensions | One NL question per tuple, wired once |
| **`UserSimulator`** | Vagueness, follow-ups, handoffs, phrasing variance | Dynamic messages at run time — see per-skill `simulate-users.md` |

Default static vs persona mix: see per-skill `simulate-users.md` (unless the user specifies otherwise).

## When NOT to generate synthetically

Prefer existing inputs when the user has:

- A curated golden test set
- Real production logs (even unlabelled)
- FAQs or support ticket samples

Real user questions beat synthetic ones for realism. Synthetic generation is the fallback when nothing else is available.

If the user has *some* real questions but not enough: use real questions for relevance/refusal coverage; add synthetic cases where you need **known anchors** (KB chunks for groundedness, fixed seed DB for gold `FnCheck`s).

## When synthetic data misleads

Synthetic tuples help **coverage** but can miss domain nuance. Treat outputs as hypotheses until validated on real traces. Be cautious when:

- Domain requires tacit expert knowledge (legal, medical, internal policy)
- Low-resource languages or dialects
- High-stakes decisions where false confidence is costly
- Domains you cannot validate (no expert reviewer)
- Underrepresented user groups or edge workflows

Prefer real logs + targeted synthetic anchors over large generic synthetic sets.

## Diverse query types

Eval strategy should **emerge from error analysis**, not a pre-built query-type matrix. Add tuple dimensions when a failure mode repeats — do not enumerate every conceivable question type upfront.

## See also

- [`error-analysis.md`](./error-analysis.md) — review traces before expanding the suite
- [`multi-turn-scenarios.md`](./multi-turn-scenarios.md) — per-turn users when static chains are not enough
- Per-skill `scenario-directions.md` — which failure modes each tuple should target
