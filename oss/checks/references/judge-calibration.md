# LLM judge calibration

Use LLM-backed checks (`Groundedness`, `AnswerRelevance`, `Conformity`, `LLMJudge`) **after** deterministic checks. This doc covers **how to trust** a judge before gating CI.

Do **not** use generic off-the-shelf scores ("helpfulness", ROUGE, BERTScore) as primary CI gates — see [`eval-lifecycle.md`](./eval-lifecycle.md).

## Scoped binary judges

Prefer **pass/fail** judges with a narrow rule:

| Check | Best for |
|-------|----------|
| `Groundedness` | Answer supported by provided context |
| `AnswerRelevance` | Answer addresses the question |
| `Conformity` | Plain-text behavioral rule (not Jinja2) |
| `LLMJudge` | Custom criteria via Jinja2 template |

Split fuzzy quality into **multiple binary sub-checks** (tool used, grounded, refused when OOS) instead of one Likert score.

## Critique-shadowing loop

1. Domain expert labels **pass/fail** on 50–100 traces (open coding first — see [`error-analysis.md`](./error-analysis.md))
2. Run the judge on the same traces
3. Measure **TPR** (true positive rate) and **TNR** (true negative rate) on a held-out set
4. Iterate judge prompt/rule until alignment is acceptable for your use case
5. Only then promote the judge to CI gating

Ground-truth labels for judge validation must be **hand-validated** — do not let an LLM label the calibration set.

## Model choice

Using the **same model** for the agent and the judge is usually fine — the judge performs a different task. Switch models only when TPR/TNR stay poor after prompt iteration.

Start with a capable fast-tier judge model; optimize cost after alignment is stable.

## When to use which check

| Need | Prefer |
|------|--------|
| Faithfulness to retrieved context | `Groundedness` with dynamic `context_key` |
| Refusal / policy compliance | `Conformity` with explicit decline rule |
| Numeric gold on fixed seed | `FnCheck` — not a judge |
| SQL safety / tool trace | `FnCheck`, `RegexMatching` — not a judge |
| Subjective nuance after rules fail | `LLMJudge` with calibrated template |

## See also

- [`checks-catalog-core.md`](./checks-catalog-core.md) — layer ordering (deterministic before judges)
- [Giskard checks reference](https://docs.giskard.ai/oss/checks/reference/checks)
