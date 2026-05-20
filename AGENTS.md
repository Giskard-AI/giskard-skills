## Learned User Preferences

- Author and extend evaluator skills with Giskard OSS `giskard.checks` only; do not mention LangWatch or third-party observability frameworks in skill content.
- For RAG and text-to-SQL evaluators, verify correct tool usage (`FnCheck` on retrieval `sources`/`context`/`tool_calls` or SQL `queries[]`) before answer-quality judges (`Groundedness`, `AnswerRelevance`, `Conformity`).
- Prefer deterministic checks (`FnCheck`, `RegexMatching`, `Equals`, `StringMatching`) before LLM judges for tool use, SQL shape, gold metrics, and refusals.
- Use `UserSimulator` with dynamic per-turn personas for realistic multi-turn evals; mix with static prompts for gold metrics and guardrails.
- Keep skill and reference docs agent-agnostic; put demo paths, gold values, and concrete scenario names only in `example-agent/COVERAGE.md`.
- Prefer general, adaptable examples and references in skills—not bindings to the bundled example agents.
- End eval work with the iterative loop: expect some failures, co-design scenarios with the user (questions and persona/check proposals), then harden for realistic difficulty—not impossible superspecific checks.
- Keep evaluator-specific persona patterns in each skill's `simulate-users.md`, not in `scenario-generator` SKILL.md.
- Unify duplicated evaluator workflow in a shared shell reference; keep separate `rag-evaluator` and `text2sql-evaluator` skills for trigger discovery.
- Use `uv` for Python dependencies and execution in example agents and eval scripts.
- Do not update README or create git commits unless explicitly asked.

## Learned Workspace Facts

- `giskard-skills` packages Cursor agent skills under `oss/checks/` for evaluating AI agents with Giskard OSS checks.
- Primary evaluator skills: `rag-evaluator` (document RAG), `text2sql-evaluator` (SQL analytics agents), `scenario-generator` (adversarial red-teaming).
- `text2sql-evaluator` is the canonical SQL evaluator; do not add duplicate folders (e.g. `sql-analytics-evaluator`, `data-analytics-evaluator`).
- Both `rag-evaluator` and `text2sql-evaluator` ship `example-agent/` (reference SUT, `uv sync`, `giskard-checks>=1.0.2b3`, Python 3.12+).
- Documentation uses three layers: shared `oss/checks/references/`, domain `<skill>/references/`, demo `example-agent/`—see `oss/checks/ARCHITECTURE.md`.
- RAG and text2sql evaluator skills share parallel `references/` filenames (`eval-dimensions.md`, `scenario-directions.md`, `test-input-generation.md`, `simulate-users.md`, etc.); RAG adds `retrieval-metrics.md`, text2sql adds `sql-safety.md`.
- Shared refs include `iterative-eval-loop.md` (with user co-design) and `doc-authoring.md` for end-of-eval hardening and authoring rules.
- `rag-evaluator` expects structured outputs exposing retrieval trace (`sources`, `context`, or `tool_calls`) for tool-usage checks.
- `text2sql-evaluator` expects agent return shape `{"answer", "queries"}` for SQL tool-usage checks.
- Quality evaluators pair with `scenario-generator` for security and adversarial coverage.
