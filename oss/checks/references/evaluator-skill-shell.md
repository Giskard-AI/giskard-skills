# Evaluator skill shell (RAG + text-to-SQL)

Shared workflow, references, install, and output format for **quality evaluator** skills. Each skill's `SKILL.md` adds trace contract and domain steps (3–5, 7).

Evaluations use `suite.run(target=user_agent)`. Use bundled `example-agent/` only when the user wants a local demo — setup in that skill's `example-agent/COVERAGE.md`.

Adversarial coverage: **`scenario-generator`**.

## Relationship to other skills

| Need | Skill |
|------|--------|
| RAG quality | `rag-evaluator` |
| SQL / analytics quality | `text2sql-evaluator` |
| Adversarial / red team | `scenario-generator` |

## Shared reference index

| Topic | Path |
|-------|------|
| Information gathering | [`information-gathering.md`](./information-gathering.md) |
| Generated code rules | [`generated-code-rules.md`](./generated-code-rules.md) |
| Error analysis | [`error-analysis.md`](./error-analysis.md) |
| Eval lifecycle | [`eval-lifecycle.md`](./eval-lifecycle.md) |
| Official how-to | [`giskard-how-to.md`](./giskard-how-to.md) |
| Multi-turn | [`multi-turn-scenarios.md`](./multi-turn-scenarios.md) |
| Iterative eval loop | [`iterative-eval-loop.md`](./iterative-eval-loop.md) |
| Check layers (core) | [`checks-catalog-core.md`](./checks-catalog-core.md) |
| Test inputs (core) | [`test-input-generation-core.md`](./test-input-generation-core.md) |
| API (core) | [`api-reference-core.md`](./api-reference-core.md) |

Domain refs: see **Domain reference index** in the active skill's `SKILL.md`.

## Check ordering (invariant)

1. Tool trace — `FnCheck` (retrieval fields or `queries[]`)
2. Gold / shape — `FnCheck`, `Equals`, `RegexMatching`
3. Judges — `Groundedness`, `AnswerRelevance`, `Conformity`, `LLMJudge` ([`judge-calibration.md`](./judge-calibration.md) before CI gates)

Prefer **`FnCheck` over `Conformity`** for safety, refusals, counts, and tool shape.

## Standard workflow

### Step 0: Gather context

[`information-gathering.md`](./information-gathering.md) (skill addendum) + [`iterative-eval-loop.md`](./iterative-eval-loop.md) before personas. [`error-analysis.md`](./error-analysis.md#trace-sampling) when production traces exist.

### Step 1: Error analysis

[`error-analysis.md`](./error-analysis.md) — automate recurring failures only.

### Step 2: Install

```bash
uv pip install --prerelease=allow 'giskard-checks>=1.0.2b3'
```

### Steps 3–5: Domain

See active skill `SKILL.md`.

### Step 6: Pick checks

[`checks-catalog-core.md`](./checks-catalog-core.md) + skill `references/checks-catalog.md`. [`generated-code-rules.md`](./generated-code-rules.md).

### Step 7: Output code

Notebook cells in `.ipynb` context; else one runnable script. Persist results; wrap SUT with `inputs`.

### Step 8: Iterative loop (with user + traces)

**Do not run solo.** Follow [`iterative-eval-loop.md`](./iterative-eval-loop.md):

1. **Run** suite; persist JSON from **this** run  
2. **Review traces** — `trace.interactions` for failed and passed personas  
3. **Audit scenario setup** — persona text, `max_steps`, rubrics in code  
4. **Classify** failures with the user (agent vs simulator drift vs judge)  
5. **Propose** trace-backed changes; **ask** before implementing  
6. **Re-run**

Also sample production traces when available — [`error-analysis.md`](./error-analysis.md#trace-sampling).

## Output format

1. **Questions for you** — gaps in roles, metrics, trace interpretation  
2. **Trace-backed proposals** — 2–4 scenario/setup changes citing latest run ([`iterative-eval-loop.md`](./iterative-eval-loop.md))  
3. Brief diagnosis — inputs, coverage, gaps  
4. Test data  
5. Complete code  
6. Per-scenario one-liner  
7. **Iterative loop outcome** — pass rate, trace observations, setup changes, next proposals  
8. Next steps — explicit ask: which proposals to implement  

Persona mix and pass-rate targets: skill `references/simulate-users.md` and [`iterative-eval-loop.md`](./iterative-eval-loop.md).

## Optional `example-agent/`

Local demo only. Run commands and file layout live in **`example-agent/COVERAGE.md`** for that skill.

## Troubleshooting (shared)

| Issue | Action |
|-------|--------|
| Red team | `scenario-generator` |
| Import errors | `from giskard.checks import ...` |
| Flaky judges | `FnCheck` first; [`judge-calibration.md`](./judge-calibration.md) |
