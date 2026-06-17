# Eval Iteration Loop: Run → Review → Harden

First-pass eval suites are drafts. Skills should **always** close the loop: run an initial suite, learn from failures, refine scenarios and checks, then re-run until the suite is stable.

This is separate from the agent-improvement loop (fixing the SUT). Here the goal is a **trustworthy eval** that catches real regressions without flaky false positives.

## The loop

```
Draft suite (5–15 scenarios)
        ↓
   Run suite → print_report() + save JSON
        ↓
   Review failures (human + report)
        ↓
   Classify each failure
        ↓
   Refine scenarios / checks / test data
        ↓
   Re-run → compare pass rate & failure themes
        ↓
   Stable? → expand coverage + lock as regression suite
```

Repeat until pass rate stabilizes **or** remaining failures are confirmed agent bugs (not eval bugs).

## Step 1: Start small

- Ship **5–15 targeted scenarios** before scaling to dozens.
- Quality beats quantity: each scenario should test one distinct failure mode.
- Tell the user this is iteration 1 — not the final regression suite.

## Step 2: Run and persist results

Always:

```python
result = await suite.run(target=your_agent)
result.print_report()
Path("eval_results.json").write_text(result.model_dump_json(indent=2))
```

In notebooks, also display `result` for rich output. JSON makes diffing across iterations possible.

## Step 3: Review failures

For each failing scenario, ask:

1. **Real agent bug?** → Keep the check; file a fix for the SUT separately.
2. **Flaky judge?** → Rewrite `Conformity` rule or `LLMJudge` prompt; add edge-case guidance. Do not swap to keyword `FnCheck`.
3. **Wrong check for the intent?** → See `check-selection.md`; replace with a general judge.
4. **Bad test input?** → Fix the scenario question or expected context (especially synthetic Q&A).
5. **Ambiguous gold label?** → Clarify reference answer or relax `SemanticSimilarity` threshold.

Group failures by theme (hallucination, refusal, injection, retrieval) before editing — batch-fixing one judge rule beats one-off per-scenario hacks.

## Step 4: Refine

**Checks:** Tighten or broaden judge rules based on false positives/negatives. One clear sentence per `Conformity` rule.

**Scenarios:** Add scenarios for each confirmed failure mode the first pass missed. Remove or merge redundant scenarios that always pass together.

**Test data:** If synthetic Q&A is shallow, regenerate from real KB chunks (see `rag-evaluator/references/synthetic-qa-generation.md`).

**Do not:** Add hyper-specific `FnCheck` lambdas to force a failing run green. That hides real problems and breaks on paraphrase.

## Step 5: Re-run and compare

- Re-run the full suite after each refinement batch (not one scenario at a time in CI).
- Compare `pass_rate` and failure names across saved JSON files.
- Stop iterating the **eval** when:
  - Remaining failures are confirmed SUT bugs, or
  - Judge disagreements are resolved with human spot-checks on 5–10 traces

## Step 6: Expand and lock

Once stable:

- Add scenarios for new failure themes from production logs or red-team findings.
- Keep passing scenarios as **regression tests** — they should fail if the agent regresses.
- Document known gaps (e.g., "no retrieval eval — retriever not exposed").

## Judge calibration mini-loop

When using `Conformity` / `LLMJudge` / `Groundedness`:

1. Human labels 10–20 `(trace, pass/fail)` examples from the report.
2. Adjust the rule/prompt to fix systematic false positives or negatives.
3. Re-run on the labeled set before scaling the suite.

Prefer calibrating one general judge over adding many scenario-specific `FnCheck`s.

## What to tell the user

After generating iteration-1 code, always include:

1. How to run the suite and where results are saved.
2. That they should **review failures before trusting pass rate**.
3. Which checks to tune first if results look noisy (usually LLM judges, not rule-based gates).
4. What to add in iteration 2 based on their report (scenarios for missed failure modes).
