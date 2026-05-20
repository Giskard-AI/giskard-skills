# Eval lifecycle: guardrails, CI, and production

General patterns for where checks run and how suites evolve. Adapt names and thresholds to your stack; examples use placeholder roles (`validate_request`, `run_suite`).

## Guardrails vs evaluators

| | Guardrails | Evaluators (`giskard.checks` suites) |
|---|------------|--------------------------------------|
| **When** | Inline on request/response path | After response (CI, batch, sampled production) |
| **Latency** | Milliseconds to low tens of ms | Seconds acceptable (LLM judges async) |
| **Style** | Deterministic: regex, schema, SQL validator, blocklists | Deterministic + optional LLM judges |
| **On failure** | Block, redact, refuse, or retry | Report pass/fail; do not silently “fix” user-visible output |
| **False positives** | Production incidents | Wasted reviewer time |

**Examples (adapt labels to your agent):**

- **Guardrail**: `validate_sql(text)` rejects `DELETE` before execution; PII regex on input.
- **Evaluator**: `FnCheck` that `queries[]` is non-empty on data questions; `Groundedness` on retrieved chunks.

The same *logic* can exist in both layers only when latency and false-positive tolerance allow it. Do not put slow LLM-as-judge checks on the hot path unless product requirements explicitly allow it.

## CI/CD vs production monitoring

| | CI / regression suite | Production sampling |
|---|----------------------|---------------------|
| **Data** | Small curated set (often 50–200 scenarios) | Live traces, no gold answer |
| **Checks** | Favor `FnCheck`, `Equals`, `RegexMatching` | More LLM judges acceptable if async |
| **Goal** | Block regressions on known failures | Discover new failure modes |
| **Cost** | Run on every PR — keep lean | Sample rate + budget caps |

**Feedback loop:** Production error analysis → new failure mode → minimal repro scenario → add to CI suite. Without this loop, CI drifts away from real user pain.

**Sampling production traces:** see [`error-analysis.md`](./error-analysis.md#trace-sampling) — outliers, stratified sampling, priority queues.

## Persisting results

```python
from pathlib import Path

result = await suite.run(target=your_agent)
result.print_report()
Path("eval_results.json").write_text(result.model_dump_json(indent=2))
```

### JUnit export (CI dashboards)

```python
from pathlib import Path

result = await suite.run(target=your_agent)
Path("eval_results.xml").write_text(result.to_junit_xml())
# or: result.to_junit_xml("eval_results.xml")
```

Use JSON for pass-rate diffs over time; JUnit for CI test report UIs. See [Run Tests with pytest](https://docs.giskard.ai/oss/checks/how-to/run-tests-with-pytest) — also [`giskard-how-to.md`](./giskard-how-to.md).

Optional demo agents may ship pytest wrappers (see each skill's `example-agent/`).

After the first suite run, follow [`iterative-eval-loop.md`](./iterative-eval-loop.md) — tune checks and add stress cases until the suite is informative (quality scenarios should not all pass on first iteration unless you are still expanding coverage).

## Generic metrics as exploration only

Off-the-shelf scores (“helpfulness”, “coherence”, ROUGE/BERTScore on free-form answers) are poor **primary** gates for product evals. They may help **find traces to review** (sort outliers), not replace domain-specific binary checks.

For RAG **retrieval**, IR-style metrics (recall@k, MRR) on labeled query–document pairs remain useful — see `rag-evaluator/references/retrieval-metrics.md`.

## Prompt and scenario versioning

Treat prompts and scenario definitions as **versioned artifacts** (git alongside application code). When a failure mode is fixed, update or add scenarios in the same change when possible so regressions are caught on the next run.

## See also

- [`error-analysis.md`](./error-analysis.md) — how to choose what to automate
- [`error-analysis.md`](./error-analysis.md#trace-sampling) — production sampling strategies
- [`giskard-how-to.md`](./giskard-how-to.md) — official how-to index (pytest, Spy, CI/CD)
- [Giskard checks reference](https://docs.giskard.ai/oss/checks/reference/checks)
