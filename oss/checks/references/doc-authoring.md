# Documentation authoring conventions

Rules for writing and editing skill reference files under `oss/checks/`.

## Three layers

| Layer | Path | Content |
|-------|------|---------|
| Shared | `oss/checks/references/` | Methodology only — error analysis, lifecycle, multi-turn, judge calibration, **iterative eval loop** |
| Domain | `oss/checks/<skill>/references/` | Trace contract, failure modes, portable code with placeholders |
| Demo | `oss/checks/<skill>/example-agent/` | Seed data, scenario names, CLI flags, direction → scenario map in `COVERAGE.md` |

Do **not** put demo paths, fixed gold values, or concrete scenario names from `example-agent/` in domain refs.

## Placeholder vocabulary

| Domain | Trace keys | Placeholders |
|--------|------------|--------------|
| text2sql | `answer`, `queries[]` | `<entity_table>`, `<fact_table>`, `<bridge_table>`, `<status_column>`, `<flag_column>` |
| RAG | `answer`, `sources` / `context` / `tool_calls` | `<doc_id>`, `<topic>`, `<kb_chunk>` |

Use angle-bracket placeholders in prose and code comments. In Python examples, use `# REPLACE:` for user-specific values.

## Gold metrics

Write: "When the user provides a fixed seed DB, derive expected integers once and use gold `FnCheck` on parsed `answer`."

Do **not** embed demo seed values in domain refs — put them in `example-agent/COVERAGE.md` only.

## Scenario naming

Domain docs use **direction slugs** (`ambiguous_metric`, `join_grain`, `factual_lookup`, `oos_probe`).

Demo `Scenario("...")` names live in `example-agent/COVERAGE.md`, not in `scenario-directions.md`.

## Linking to example-agent

- **`examples.md`**: one footer line — "Runnable reference implementation: `example-agent/` (optional)."
- **`SKILL.md`**: at most one line pointing to `example-agent/COVERAGE.md` — no demo bash blocks or file tables in SKILL or shell.
- **Domain refs**: no links to `example-agent/eval/scenarios.py` or `init_db.sql`.

## Parallel filenames (RAG ↔ text2sql)

Keep matching names: `tool-usage.md`, `scenario-directions.md`, `checks-catalog.md`, `workflow-eval.md`, `simulate-users.md`, `examples.md`.

Structure each `scenario-directions.md` as: trace contract → how to use → tiers → proven patterns → coverage report → **iterative eval loop** pointer.

## Evaluator SKILL.md shell

`rag-evaluator` and `text2sql-evaluator` share [`evaluator-skill-shell.md`](./evaluator-skill-shell.md). Put duplicated workflow tables, install, shared ref index, standard output format, and iterative loop there — not in both SKILL.md files.

Each evaluator `SKILL.md` must link the shell and contain only: trace contract, domain workflow steps (3–5, 7 pointers to domain refs), domain ref index, domain troubleshooting. No duplicate co-design steps, 40/40/20 mix tables, pass-rate targets, or iterative-loop prose — those live in shared/domain refs.

## Iterative eval loop (required in every evaluator skill)

Via [`evaluator-skill-shell.md`](./evaluator-skill-shell.md) Step 8 — **with the user**, grounded in **latest traces** and **scenario setup**:

1. Link shell, [`iterative-eval-loop.md`](./iterative-eval-loop.md), [`error-analysis.md`](./error-analysis.md)
2. Loop: run → review traces → audit personas/checks → propose → ask → implement → re-run
3. Output format leads with questions + trace-backed proposals (shell)

Domain refs (`scenario-directions.md`, `checks-catalog.md`, `simulate-users.md`) should point to the shared loop doc — not duplicate the full procedure.

## See also

- [`ARCHITECTURE.md`](../ARCHITECTURE.md) — repo layout and documentation layers
