---
name: scenario-generator
description: >-
  Generates tailored giskard.checks test scenarios and suites for AI agents.
  Triggers on "create scenarios", "test my agent", "red-team my AI", "generate checks".
  Pair with rag-evaluator or text2sql-evaluator for quality baselines.
license: Apache-2.0
metadata:
  author: Giskard
  version: 1.1.0
  category: ai-testing
  tags: [giskard, checks, scenarios, red-teaming, ai-evaluation]
---

# Giskard Checks Scenario Generator

Adversarial test scenarios for LLM agents using `giskard.checks`. Focus: prompt injection, jailbreaks, data leakage, off-topic abuse, tool misuse.

For **quality baselines** (groundedness, SQL tool use, gold metrics), use `rag-evaluator` or `text2sql-evaluator` first, then add this skill for attack coverage.

## Relationship to other skills

| Need | Skill |
|------|--------|
| **Adversarial** / red-teaming | **This skill** |
| RAG quality (retrieval, groundedness) | `rag-evaluator` |
| SQL/data analytics quality | `text2sql-evaluator` |

Many production agents need a quality evaluator + this skill.

## Reference docs

| Topic | Path |
|-------|------|
| Information gathering | [`../references/information-gathering.md`](../references/information-gathering.md) + scenario-generator addendum |
| Generated code rules | [`../references/generated-code-rules.md`](../references/generated-code-rules.md) |
| Error analysis | [`../references/error-analysis.md`](../references/error-analysis.md) |
| Judge calibration | [`../references/judge-calibration.md`](../references/judge-calibration.md) |
| Workflow eval (core) | [`../references/workflow-eval-core.md`](../references/workflow-eval-core.md) |
| Official how-to index | [`../references/giskard-how-to.md`](../references/giskard-how-to.md) |
| Multi-turn mechanics | [`../references/multi-turn-scenarios.md`](../references/multi-turn-scenarios.md) |
| API (core) | [`../references/api-reference-core.md`](../references/api-reference-core.md) |
| Attack patterns | [`references/attack-patterns.md`](references/attack-patterns.md) |
| API (adversarial) | [`references/api-reference.md`](references/api-reference.md) |
| Worked code (3 canonical) | [`references/examples.md`](references/examples.md) |
| Extended examples | [`references/examples-extended.md`](references/examples-extended.md) |

## Workflow

### Step 0: Gather context

Read [`../references/information-gathering.md`](../references/information-gathering.md). Require agent description, boundaries, fears, and interface before generating code.

Review real failure traces when available — [`../references/error-analysis.md`](../references/error-analysis.md).

### Step 1: Install

```bash
uv pip install --prerelease=allow 'giskard-checks>=1.0.2b3'
```

### Step 2: Map fears → attack surfaces

Consult [`references/attack-patterns.md`](references/attack-patterns.md). Map each fear to concrete vectors (injection, leakage, jailbreak, tool misuse, multi-turn drift).

### Step 3: Design scenarios

Escalate sophistication: direct → indirect → multi-turn → `UserSimulator` personas. See [`../references/multi-turn-scenarios.md`](../references/multi-turn-scenarios.md).

### Step 4: Pick checks (cheap → expensive)

1. `FnCheck`, `StringMatching`, `RegexMatching`, `Equals`
2. `SemanticSimilarity`
3. `Conformity`, `LLMJudge`, `Groundedness`, `AnswerRelevance`
4. `AllOf`, `AnyOf`, `Not`

Follow [`../references/generated-code-rules.md`](../references/generated-code-rules.md).

### Step 5: Output code

Complete runnable script or notebook cells. `Suite` + `suite.run(target=...)`. Persist results to JSON in scripts.

## Output format

1. **Brief analysis** — attack surfaces and approach
2. **Complete Python code** — all scenarios in a `Suite`
3. **Per-scenario intent** — one-line adversarial goal

## Performance notes

- 3–5 scenarios per fear; direct, indirect, and multi-turn variants
- Quality over quantity — distinct failure modes
- Multi-turn attacks that gradually shift context beat single-shot probes

## Troubleshooting

| Issue | Action |
|-------|--------|
| User doesn't know fears | Brainstorm by domain (support, RAG, code, healthcare) |
| Only system prompt provided | Extract boundaries; ask for callable |
| Single scenario requested | Still wrap in `Suite` |
| Import errors | `from giskard.checks import ...` |

Skill quality rubrics: [`evals/evals.json`](evals/evals.json).
