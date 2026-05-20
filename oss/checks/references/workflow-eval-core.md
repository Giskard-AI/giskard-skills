# Workflow evaluation (core)

For **multi-step agents** (RAG pipelines, text-to-SQL chains, tool-using assistants). Domain step examples:

- RAG: [`rag-evaluator/references/workflow-eval.md`](../rag-evaluator/references/workflow-eval.md)
- Text-to-SQL: [`text2sql-evaluator/references/workflow-eval.md`](../text2sql-evaluator/references/workflow-eval.md)
- Adversarial multi-step tool misuse: [`scenario-generator/SKILL.md`](../scenario-generator/SKILL.md)

Start with **black-box success** (did the user get the correct, safe outcome?), then add step-level diagnostics when E2E passes hide partial failures.

## Phase 1 — End-to-end (black box)

One binary question per task: **did the user get the correct, safe outcome?**

Use static `inputs` or a short persona. Checks: tool trace (`FnCheck`) + outcome (`FnCheck`, gold metric, or narrow `LLMJudge`).

Do not build step-level checks until E2E failures cluster in error analysis.

## Phase 2 — Step-level diagnostics

Requires **instrumented traces** — labeled steps in `tool_calls[]`, `queries[]`, or metadata (e.g. `step: retrieve | plan | execute`).

If the agent does not emit steps today, ask the user to add lightweight step tags. Evals cannot diagnose transitions without them.

Per-step checks (rename to match your trace):

| Concern | Check idea |
|---------|------------|
| Tool chosen | `FnCheck`: expected tool invoked |
| Parameters / shape | `RegexMatching`, domain validator |
| Execution | `FnCheck`: success flag or non-empty result |
| Answer vs intermediate | `FnCheck` or calibrated `LLMJudge` |

## Transition failure matrix

Track **last successful step → first failing step**. Count failures per cell during error analysis — not from hypothetical flows.

| Last OK ↓ / First fail → | step A | step B | step C |
|--------------------------|--------|--------|--------|
| _(start)_ | | n | |
| step A | | n | |
| step B | | | n |

**Grow scenarios from matrix hotspots** — do not encode the whole matrix as 50 scenarios upfront.

## Efficiency and retries

Optional `FnCheck`s (adapt thresholds):

- Step or tool call count ≤ N unless the task requires exploration
- No repeated identical failed attempts without changed inputs

## Mapping to giskard.checks

- High-frequency transition → dedicated `Scenario` stressing that path; `FnCheck` on the failing step
- Rare edge case → static repro with minimal `inputs` — see [`error-analysis.md`](./error-analysis.md)
- Multi-turn agentic loops → [`multi-turn-scenarios.md`](./multi-turn-scenarios.md)

## See also

- [`error-analysis.md`](./error-analysis.md) — first-failure annotation
- [`eval-lifecycle.md`](./eval-lifecycle.md) — guardrails vs suite evals
- [`error-analysis.md`](./error-analysis.md#trace-sampling) — find multi-step failures in production
