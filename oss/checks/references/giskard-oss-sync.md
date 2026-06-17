# Giskard OSS sync (source of truth)

Skills in this repo document the **giskard-checks** and **giskard-scan** Python APIs shipped from [Giskard-AI/giskard-oss](https://github.com/Giskard-AI/giskard-oss). When the library changes, update skills here — do not treat skill text as authoritative over the repo.

## Packages and paths

| Package | PyPI name | Public exports | Skill consumers |
|---------|-----------|----------------|-----------------|
| Checks | `giskard-checks` | `libs/giskard-checks/src/giskard/checks/__init__.py` | `rag-evaluator`, `scenario-generator` |
| Scan | `giskard-scan` | `libs/giskard-scan/src/giskard/scan/__init__.py` | future scan/red-team skill |
| Agents | `giskard-agents` | `Generator`, prompts | all LLM-backed checks |

Official user docs: [docs.giskard.ai/oss/checks](https://docs.giskard.ai/oss/checks), [docs.giskard.ai/oss/solutions/scan-vulnerabilities](https://docs.giskard.ai/oss/solutions/scan-vulnerabilities).

## How to verify skills are current

1. **Fetch latest main** from giskard-oss (`git fetch origin main`).
2. **Run the CI sync checker** (also runs in GitHub Actions on skill changes):

   ```bash
   git clone --depth 1 https://github.com/Giskard-AI/giskard-oss.git /tmp/giskard-oss
   python scripts/check_giskard_oss_sync.py --giskard-oss-path /tmp/giskard-oss
   python -m pytest scripts/test_check_giskard_oss_sync.py -q
   ```

   Compares `giskard.checks.__all__` to `from giskard.checks import (...)` blocks in all `references/api-reference.md` files. Fails on missing or stale symbols.
3. **Diff public exports** — read `giskard/checks/__init__.py` `__all__` and compare to both skills' `references/api-reference.md` import blocks.
4. **Spot-check judge signatures** — `Groundedness`, `AnswerRelevance`, `Conformity`, `LLMJudge`, `Toxicity` under `libs/giskard-checks/src/giskard/checks/judges/`.
5. **Spot-check Scenario/Suite** — `libs/giskard-checks/src/giskard/checks/core/scenario.py`, `scenarios/suite.py`, `core/result.py` (`print_report`, `group_by`, `to_junit_xml`).
6. **Run skill evals** after API doc changes (`oss/checks/*/evals/evals.json`).

Record the oss commit you verified against in PR descriptions (e.g. `giskard-oss@b73fff0` — last skills sync).

## API additions since early skills (verify still present)

These exist in current giskard-oss but were missing from initial skill docs:

### Judges and builtins

- `Toxicity` — LLM judge for hate/harassment/threats/self-harm/sexual/violence categories. Prefer over custom safety `FnCheck` keyword lists.
- `JsonValid` — schema validation on extracted trace fields.
- `RegoPolicy` — optional Rego policy checks (`regorus` extra).

### Scenario / suite reporting

- `Scenario.with_tags(["Category:Refusal", "flaky"])` — flat `Key:Value` or bare labels.
- `result.print_report(group_by="Category")` — grouped pass-rate table after standard report.
- `result.group_by("Category")` → `GroupedSuiteResult` with per-bucket stats.
- `Scenario.multiple_runs` / `run(multiple_runs=N)` — runs the scenario up to N times with a **fresh trace each time**; each run must pass for the next to run. **Not** retry-until-success. Distinct from the eval hardening loop in `eval-iteration-loop.md` (which is about refining scenarios/checks between suite runs).

### Debugging

- `WithSpy` — patches a target callable and records call metadata on the interaction trace (tool-call debugging). Example: `references/advanced-checks-examples.md`.

### Structured validation

- `JsonValid` — JSON / JSON Schema validation at a trace key.
- `RegoPolicy` — inline Rego policies (`pip install 'giskard-checks[regorus]'`). Example: `references/advanced-checks-examples.md`.

### Scan (red team)

```python
from giskard.scan import vulnerability_scan, generate_suite

# One-liner automated vulnerability scan (preferred for "red-team my agent")
result = await vulnerability_scan(target=my_agent, description="...", languages=["en"])
result.print_report(group_by="threat-type")
```

Scan generators (`AdversarialScenarioGenerator`, `CrescendoAttackScenarioGenerator`, `GOATAttackScenarioGenerator`, `PromptInjectionScenarioGenerator`) produce `giskard.checks.Scenario` objects — same `Suite.run(target=...)` path as hand-written scenarios.

## Defaults that trip up generated code

| Check | Default key | Skill guidance |
|-------|-------------|----------------|
| `Groundedness.context_key` | `trace.last.metadata.context` | Use when context is on `.interact(metadata={"context": [...]})`. Use `trace.last.outputs.context` when the SUT returns a dict. |
| `Groundedness.answer_key` | `trace.last.outputs` | Override to `trace.last.outputs.answer` for structured outputs. |
| `AnswerRelevance.context` | `None` | Pass domain string (not from trace) so multi-turn judges know scope. |
| `SemanticSimilarity.threshold` | `0.95` | Calibrate down (0.5–0.7) for natural-language gold answers. |

## Install pins (current oss main)

- `pip install giskard-checks` — library version tracks oss releases (e.g. `1.0.2b4` on main at last sync).
- `pip install giskard-scan` — for automated vulnerability scans (`1.0.0b2` on main at last sync).

Skills should say `pip install giskard-checks` (and `giskard-scan` when documenting scan flows), not pin prerelease versions unless reproducing a specific bug.

## When oss adds a new check

1. Add it to the relevant skill's `references/api-reference.md` import block and a short usage snippet.
2. Update `check-selection.md` if it changes the preferred check order.
3. Add one example scenario if the check is commonly needed.
4. Extend skill evals if agents keep missing the new check.
