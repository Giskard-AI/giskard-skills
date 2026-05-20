# Error analysis (start here)

Eval suites should come from **observed failures**, not imagined ones. Before adding scenarios or LLM judges, review real traces from your agent (production samples, internal dogfood, or a small pilot run).

The workflow below is adapted for `giskard.checks` without prescribing a specific product domain.

## Trace sampling

Before writing scenarios, **find traces likely to contain failures**. Random review is inefficient when most traces pass.

### When to sample

- After meaningful changes: prompt, model, schema, retrieval config, new features
- **100+ fresh traces** per major review cycle
- **10–20 traces weekly** between cycles — focus on outliers
- Always after incidents, user-complaint spikes, or metric drift

### Sampling strategies

#### 1. Random baseline

Review a random sample of 20–50 traces. If few issues appear, the suite may be too easy — add stress prompts that probe prompt constraints.

#### 2. Priority queues

Prioritize traces from:

- Negative user feedback, support tickets, escalations
- Guardrail or CI check failures
- Existing eval failures (use evals as a screen, then error-analyze)

#### 3. Outlier sorting

Sort by metadata and review extremes:

| Signal | RAG | Text-to-SQL |
|--------|-----|-------------|
| Latency | High `metadata.latency_ms` | Same |
| Response length | Very long/short `answer` | Same |
| Tool usage | 0 vs many retrieval calls | 0 vs many `queries[]` |
| Retrievals | Unusually large `sources` / `context` | N/A |

Review both high and low outliers — generic metrics are **exploration signals**, not quality gates (see [`eval-lifecycle.md`](./eval-lifecycle.md)).

#### 4. Stratified sampling

Group by dimensions that matter for your product:

- User type, feature flag, query category, locale
- Sample proportionally; **oversample small groups** for edge cases

#### 5. Embedding clustering (optional)

Cluster query embeddings to surface natural groupings. Sample from each cluster; oversample rare clusters. Use for exploration — not as a pass/fail metric.

### Production vs CI

| Context | Sampling goal |
|---------|---------------|
| **Production** | Discover new failure modes; feed CI suite |
| **CI** | Regression on known failures; small curated set |

See [`eval-lifecycle.md`](./eval-lifecycle.md) for the guardrails ↔ evaluators feedback loop.

## Notebook-first MVP

Before building CI infra, review traces in a **notebook** or script:

1. Call the agent on 20–50 sampled inputs
2. Open-code failures in plain language
3. Prototype one `Scenario` + `FnCheck` per recurring mode
4. Promote stable cases to a versioned suite — see [`giskard-how-to.md`](./giskard-how-to.md)

This matches the [Giskard Checks quickstart](https://docs.giskard.ai/oss/checks) arc: explore → automate regressions.

## Minimum viable review

1. Collect **20–50 traces** after a meaningful change (prompt, model, schema, retrieval config).
2. One **domain expert** (or PM who owns user outcomes) reviews them — a single “benevolent dictator” beats five shallow annotators for most teams.
3. Note issues in plain language (open coding). Prefer the **first upstream failure** per trace; downstream failures often cascade.
4. Group notes into a **failure taxonomy** (axial coding). Count frequency per category.
5. Automate only categories that **persist** after cheap fixes (prompt clarity, guardrails, schema in system message).

Target **~100 traces** before treating a taxonomy as stable. If ~20 consecutive traces add no new category, you can pause — but review at least 100 once when bootstrapping.

## Re-run cadence

| Trigger | Scope |
|---------|--------|
| Major change (prompt, model, schema, retrieval) | **100+** fresh traces |
| Between major cycles | **10–20** weekly outliers — see [Trace sampling](#trace-sampling) |
| Incidents, complaint spikes, metric drift | Full priority-queue review |

## PM + engineer collaboration

- **Engineers** spot tool/retrieval/SQL bugs, trace shape issues, guardrail gaps
- **PMs / domain owners** spot outcome failures users care about

Still use one **benevolent dictator** for pass/fail labels when automating checks — consensus labels dilute signal on small teams.

## Open coding → axial coding

| Phase | What you do | Output |
|-------|-------------|--------|
| Open coding | Read trace; write what went wrong in user-visible terms | Raw notes per trace |
| Axial coding | Merge similar notes into named failure modes | Taxonomy + counts |

Ask outcome questions, not implementation trivia: “Was the refund policy correct?” not “Did `retrieve()` return 200?”

### LLM assist boundaries

| OK | Not OK |
|----|--------|
| Suggest axial groupings after **30+** open-coded traces | Skip initial open coding |
| Draft scenario text from a named failure mode | Let an LLM label the calibration set for judges |
| Summarize trace batches for review prep | Auto-promote checks without human pass/fail labels |

Always validate LLM-suggested clusters yourself — see [`judge-calibration.md`](./judge-calibration.md) before gating CI on judges.

## What to automate (cost-aware)

| Failure signal | Prefer first | Escalate to LLM judge when |
|----------------|--------------|----------------------------|
| Tool never called | `FnCheck` on trace | Never — use trace assertions |
| Wrong SQL shape / blocked destructive SQL | `RegexMatching`, unit tests on validator | Subjective “reasonable SQL” only |
| Answer contradicts retrieved context | `Groundedness` with dynamic `context_key` | Judge misaligned with human labels |
| Vague metric (“active users”) | `Conformity` / `LLMJudge` on stated assumptions | Cheap rules cannot encode policy |

**Do not** build an automated check for every taxonomy row. Fix prompt/guardrail gaps first; automate regressions for failures that recur.

**Eval-driven development** (writing evals before shipping features) is usually a poor default. Exception: hard constraints you already know (`never expose raw PII`, `read-only SQL only`).

## Binary pass/fail

Use **pass/fail** checks in `giskard.checks`, not 1–5 Likert scales. Track progress with multiple binary sub-checks (tool used, grounded, refused when OOS) instead of one fuzzy score.

## Pass rate sanity

- **~100% pass** on a stress suite often means tests are too easy — add harder directions, personas, or edge cases. Run the [**iterative eval loop**](./iterative-eval-loop.md) after every suite run.
- A moderate pass rate with **actionable failures** is healthier than green dashboards that hide regressions.

## Multi-turn and agent traces

- Annotate the **first independent failure** in the trace; fix upstream before tuning downstream checks.
- **Different users per turn**: chain `.interact()` with different `UserSimulator` instances or phased personas — see [`multi-turn-scenarios.md`](./multi-turn-scenarios.md) and per-skill `simulate-users.md`.
- **Simplify to single-turn** when possible: if a failure reproduces with one user message, use a static `inputs="..."` scenario instead of a long persona.
- **Prefix replay (N−1 turns)**: feed the first N−1 turns from a real conversation, then let the agent respond once — often more realistic than fully synthetic multi-turn dialogue.
- For long sessions, use **trace-pattern** checks (e.g. non-tool turn before data turn) when turn order varies; use index-based `trace.interactions[i]` only for static per-step inputs.

## Balanced abstention set

When calibration matters (“know what it doesn’t know”), include roughly balanced:

- **Answerable** — context or DB supports a verifiable answer (expect answer + correct tool use).
- **Unanswerable / out-of-scope** — false premises, missing data, or policy decline (expect refusal, not fabrication).

Binary pass = correct behavior for that class (answered vs declined), not a middle score.

## After error analysis → giskard suite

1. Each high-frequency failure mode → one or more `Scenario`s (static prompt and/or `UserSimulator` persona).
2. Map modes to checks via skill `checks-catalog.md` (deterministic before LLM).
3. Promote stable cases into CI — see [`eval-lifecycle.md`](./eval-lifecycle.md).

## See also

- [`eval-lifecycle.md`](./eval-lifecycle.md) — guardrails vs evaluators, CI vs production
- [`test-input-generation-core.md`](./test-input-generation-core.md) — dimensions → tuples → questions; per-skill `test-input-generation.md` for RAG/SQL anchors
- [`workflow-eval-core.md`](./workflow-eval-core.md) — multi-step agent failures (E2E → transition matrix)
- [`multi-turn-scenarios.md`](./multi-turn-scenarios.md) — per-turn user assignment, trace-pattern checks
- [`iterative-eval-loop.md`](./iterative-eval-loop.md) — post-suite trace review with the user
- `rag-evaluator` / `text2sql-evaluator` → `simulate-users.md` — persona archetypes (evaluator-specific)
- `rag-evaluator` → `retrieval-metrics.md` — IR metrics (RAG-only)
- `text2sql-evaluator` → `sql-safety.md` — SQL guardrails (text2sql-only)
