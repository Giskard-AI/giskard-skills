# Architecture: `oss/checks/` skills

Giskard agent skills for building `giskard.checks` evaluation suites. Discovered via [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json) (`"skills": ["./oss/checks/"]`).

## Layer diagram

```
shared refs (oss/checks/references/)
    ↓ linked from
domain refs (oss/checks/<skill>/references/)
    ↓ linked from
SKILL.md (entry point; quality evaluators ~80–100 lines + evaluator-skill-shell.md)
    ↓ optional
example-agent/ (reference SUT + pytest wrappers)
```

## Skill anatomy

```
oss/checks/<skill-name>/
├── SKILL.md              # Entry point — slim; quality evaluators link evaluator-skill-shell.md
├── references/           # Domain docs loaded on demand
├── evals/evals.json      # Skill quality rubrics + static assertions
└── example-agent/        # Optional runnable reference SUT (rag, text2sql)
```

Shared cross-skill references live in [`references/`](references/) — not duplicated inside each skill.

## Skills

| Skill | Role | [Agent Skills docs](https://docs.giskard.ai/oss/agent-skills) |
|-------|------|---------------------------------------------------------------|
| `rag-evaluator` | RAG quality: retrieval FnCheck, groundedness, refusal | Listed |
| `text2sql-evaluator` | SQL analytics quality: `queries[]`, guardrails, gold metrics | **Not yet listed** — use repo; coordinate docs PR |
| `scenario-generator` | Adversarial red-teaming | Listed |

One skill per agent archetype. Do not add duplicate folders (e.g. `sql-analytics-evaluator`) that mirror text2sql.

## Shared references

| File | Purpose |
|------|---------|
| `error-analysis.md` | Trace sampling, open/axial coding, failure taxonomy before expanding suites |
| `eval-lifecycle.md` | Guardrails vs evaluators, CI vs production, JUnit export |
| `judge-calibration.md` | TPR/TNR for LLM judges before CI gating |
| `workflow-eval-core.md` | E2E → step diagnostics → transition matrix (generic) |
| `giskard-how-to.md` | Index to [official how-to guides](https://docs.giskard.ai/oss/checks/how-to) |
| `multi-turn-scenarios.md` | Per-turn users, trace-pattern checks |
| `information-gathering.md` | Required context + domain addenda |
| `generated-code-rules.md` | Scenario/Suite API invariants |
| `checks-catalog-core.md` | Layer stack (tool → deterministic → judges) |
| `api-reference-core.md` | Imports, target=, trace keys |
| `test-input-generation-core.md` | Dimensions → tuples → questions; static vs `UserSimulator` |
| `doc-authoring.md` | Layer rules, placeholders, what stays in example-agent |
| `iterative-eval-loop.md` | Run → trace review → co-design with user → harden |
| `evaluator-skill-shell.md` | Shared workflow, refs, install, output format for rag + text2sql SKILL.md |

Domain files keep parallel names between RAG and text2sql (`tool-usage.md`, `checks-catalog.md`, `workflow-eval.md`, …) with a link to the core doc at the top.

## Documentation layers

Skill content is split so agents can build evals for **any** user agent without assuming the bundled demo.

| Layer | Path | Must contain | Must not contain |
|-------|------|--------------|------------------|
| Shared | [`references/`](references/) | Methodology, check ordering, lifecycle | Table names, doc IDs, `example-agent/` paths |
| Domain | `<skill>/references/` | Trace contract, direction slugs, portable `FnCheck` patterns | Demo gold values, `scenarios.py` mapping |
| Demo | `<skill>/example-agent/` | Seed data, scenario names, [`COVERAGE.md`](text2sql-evaluator/example-agent/COVERAGE.md) | — |

Rules:

1. **Shared refs** — agent-agnostic; see [`references/doc-authoring.md`](references/doc-authoring.md).
2. **Domain refs** — RAG vs text2sql differ by trace shape (`sources` vs `queries[]`), not by demo layout.
3. **Example-agent** — optional local SUT; production evals always use `target=user_agent`.
4. **SKILL.md** — may link to `example-agent/` as optional demo; directions live in domain refs.
5. **Parallel filenames** between RAG and text2sql stay; content follows the same section template.

## Conventions

### SKILL.md size

Put long tables, code templates, and rules in `references/`. SKILL.md = role, domain workflow deltas, domain ref index, domain troubleshooting.

**Quality evaluators** (`rag-evaluator`, `text2sql-evaluator`) must link [`evaluator-skill-shell.md`](references/evaluator-skill-shell.md) for shared workflow, reference index, install, output format, and iterative loop. Keep domain-only steps in each SKILL.md.

Each evaluator SKILL.md must also link to: `error-analysis.md`, `generated-code-rules.md`, `giskard-how-to.md`, `iterative-eval-loop.md` (one-line links in SKILL.md or via the shell section).

### Check ordering (invariant)

1. Deterministic tool trace (`FnCheck` on retrieval or `queries[]`)
2. Gold metrics / SQL shape / IR metrics
3. LLM judges (`Groundedness`, `AnswerRelevance`, `Conformity`)

### Cross-skill links

- Quality evaluators → `scenario-generator` for adversarial work
- `scenario-generator` → quality evaluators for baselines
- Use relative paths: `../references/...`, `references/...`

### Install command

Standard across skills:

```bash
uv pip install --prerelease=allow 'giskard-checks>=1.0.2b3'
```

Example agents use `uv sync` in `example-agent/`.

### example-agent pattern

Reference SUT for local eval development only. Production evals use `target=user_agent`.

| Component | Purpose |
|-----------|---------|
| `COVERAGE.md` | Direction → scenario map, demo seed gold values, how to run |
| `src/` | Agent + tools/retriever |
| `eval/scenarios.py` | `build_suite()` |
| `eval/test_*_guardrails.py` | Deterministic tests, no API key |
| `eval/test_suite_pytest.py` | Async pytest wrapper + JUnit export |
| `run_suite.py` | CLI runner |
| `scripts/run_eval.sh` | Guardrails + suite |

## Skill quality evals

Each skill ships `evals/evals.json`:

- `prompt` / `expected_output` — human review rubrics
- `assertions` — optional static `file_contains` / `file_exists` checks on skill files (for local regression when maintaining skills)

When editing skills, keep SKILL.md links to required shared refs, domain `scenario-directions.md` free of `example-agent/` paths, and `COVERAGE.md` present wherever `example-agent/` exists.

## Adding a fourth skill

1. Create `oss/checks/<name>/SKILL.md` with YAML frontmatter (`name`, `description`, triggers)
2. Add domain `references/`; link shared refs from `oss/checks/references/`
3. Add `evals/evals.json` with assertions
4. Optional `example-agent/` if a runnable SUT helps users learn the trace contract
5. Do not bloat SKILL.md — extend shared refs when content applies to multiple skills
