# Giskard Skills

Agent skills for building and running **evaluations with [Giskard Checks](https://github.com/Giskard-AI/giskard)** (`giskard.checks`). Works with Cursor, Claude Code, and other agents that support skills.

All skills in this repo generate **`giskard.checks` suites** — `Scenario`, `Suite`, and built-in checks (`Conformity`, `FnCheck`, `Groundedness`, etc.). No proprietary eval platform required.

## Prerequisites

- Node.js with `npx` (to install skills)
- Python 3.12+ and `giskard-checks` (when running generated eval code)

```bash
uv pip install --prerelease=allow 'giskard-checks>=1.0.2b3'
```

## Choosing a skill

| Your agent | Skill | Focus |
|------------|-------|--------|
| Chatbot / assistant — jailbreaks, leakage, abuse | `scenario-generator` | Adversarial red-teaming |
| Q&A over documents (RAG, knowledge base) | `rag-evaluator` | Retrieval tool usage, groundedness, refusal |
| Natural language → SQL (text-to-SQL, analytics chatbots) | `text2sql-evaluator` | SQL tool usage (`queries[]`), safety, gold metrics |

Many production systems need **more than one** — e.g. `text2sql-evaluator` for quality and safety baselines, plus `scenario-generator` for attack scenarios.

## Available skills

<table>
  <thead>
    <tr>
      <th width="18%">Skill</th>
      <th width="38%">Install</th>
      <th width="44%">When to use</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>scenario-generator</code></td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill scenario-generator</code></td>
      <td>Adversarial test scenarios and red-teaming for any LLM agent. Use for prompt injection, jailbreaks, data leakage, off-topic abuse, and creative failure-mode discovery. Triggers: "create scenarios", "test my agent", "red-team my AI", "generate checks".</td>
    </tr>
    <tr>
      <td><code>rag-evaluator</code></td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill rag-evaluator</code></td>
      <td>RAG / document Q&A. Always checks <strong>retrieval tool usage</strong> (<code>sources</code>, <code>context</code>, <code>tool_calls</code>) before answer-only judges. Groundedness, retrieval quality, citations, refusal. Triggers: "evaluate my RAG", "test my retrieval". Pair with <code>scenario-generator</code> for security.</td>
    </tr>
    <tr>
      <td><code>text2sql-evaluator</code></td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill text2sql-evaluator</code></td>
      <td>Text-to-SQL agents. Always checks <strong>SQL tool usage</strong> (<code>queries[]</code>) on data questions. <code>UserSimulator</code> personas + static prompts. <code>validate_sql</code>, gold counts. Example-agent (10 scenarios). Triggers: "text2sql evaluator", "evaluate my SQL agent". Pair with <code>scenario-generator</code> for abuse.</td>
    </tr>
  </tbody>
</table>

Skill sources live under `oss/checks/<skill-name>/` (each has a `SKILL.md` and `references/`).

## Example: run the text-to-SQL reference agent

The `text2sql-evaluator` skill ships a local SQLite demo agent and giskard suite:

```bash
cd oss/checks/text2sql-evaluator/example-agent
cp .env.example .env   # set OPENAI_API_KEY
uv sync

# Chat with the agent
uv run python -m src.cli

# Deterministic SQL guardrails (no API key)
uv run python eval/test_sql_guardrails.py

# Full giskard eval suite
uv run python run_suite.py
uv run python run_suite.py --safety-only   # faster subset
```

Eval design nuances (validated on the example agent):

- **Safety** → `FnCheck` on `queries[]`, not `Conformity` on exact apology text
- **Table list** → check `answer` content; empty `queries` OK if schema is in the system prompt
- **LIMIT blocks** → pass when the agent retries with `LIMIT`; check successful SQL only
- **Gold metrics** on demo seed: 3 users, 2 non-test, 17000 cents completed revenue

Shared under `oss/checks/references/`: **error-analysis.md** (includes trace sampling), **eval-lifecycle.md**, **iterative-eval-loop.md** (includes user co-design).

Both **rag-evaluator** and **text2sql-evaluator** use the same reference filenames: `eval-dimensions.md`, `tool-usage.md`, `checks-catalog.md`, `scenario-directions.md`, `simulate-users.md`, `test-input-generation.md`, `workflow-eval.md`, `api-reference.md`, `examples.md`. Shared under `oss/checks/references/`: `error-analysis.md`, `eval-lifecycle.md`, `multi-turn-scenarios.md` (per-turn user assignment, trace-pattern checks). Domain-specific: `retrieval-metrics.md` (RAG), `sql-safety.md` (text2sql). See the alignment table in each skill’s `SKILL.md`.

## Install as a Claude Code plugin

This repository is also a [Claude Code plugin](https://code.claude.com/docs/en/plugins). Clone it and start Claude with `--plugin-dir`:

```bash
claude --plugin-dir ./giskard-skills
```

Use `/giskard-skills` in Claude Code to list available skills.
