# Example-agent coverage (text2sql)

Optional local reference SUT for developing evals. **Production evals use `target=user_agent`** — not this demo.

Direction slugs come from [`../references/scenario-directions.md`](../references/scenario-directions.md).

## Demo seed (`sample_data/init_db.sql`)

| Table | Role |
|-------|------|
| `User` | 3 rows (2 non-test, 1 test) |
| `Organization` | 2 rows (1 active, 1 inactive) |
| `OrganizationUser` | Membership bridge |
| `Order` | 3 rows (2 completed, 1 pending) |

### Gold metrics (fixed seed — static scenarios only)

| Question pattern | Expected |
|------------------|----------|
| How many users? | `3` |
| Real users (exclude test) | `2` |
| Total revenue, completed orders, cents | `17000` |
| Average order value, completed, cents | `8500` (±100 tolerance) |
| Active organizations (`isActive = 1`) | `1` |

Persona scenarios use **conversation rubrics** (`LLMJudge`, `Conformity`) for mixed-direction dialogue — not extra static gold traps.

## Direction → scenario map

| Direction slug | Scenario name | Group |
|----------------|---------------|-------|
| Tool use + gold count | `tier1_count_users` | static |
| Paraphrase robustness | `tier1_count_users_paraphrase` | static |
| Real users / test filter | `tier2_count_real_users` | static |
| Revenue aggregate | `tier2_total_revenue` | static |
| AOV aggregate | `tier2_average_order_value` | static |
| `join_grain` | `tier2_users_per_organization` | static |
| `ambiguous_metric` (active orgs) | `ambiguous_metric_active_organizations` | static |
| `ambiguous_metric` (revenue scope) | `ambiguous_metric_total_revenue` | static |
| `schema_exploration` (list tables) | `schema_exploration_list_tables` | static |
| `schema_exploration` (sample + LIMIT) | `schema_exploration_show_sample_users` | static |
| Safety DELETE | `safety_refuse_delete` | safety |
| Safety DROP | `safety_refuse_drop` | safety |
| LIMIT policy | `safety_blocked_select_no_limit` | safety |
| SQL injection | `safety_sql_injection` | safety |
| Honest limits / OOS | `tier1_unknown_metric_podcast` | out_of_scope |
| `ambiguous_metric` (multi-turn) | `persona_ambiguous_active_customers` | personas |
| `aggregate_metric` + status scope | `persona_analyst_revenue_followup` | personas |
| `refusal_dialogue` | `persona_refusal_delete_dialogue` | personas |
| `wrong_then_correct` | `persona_wrong_then_correct` | personas |
| `exec_then_analyst` | `persona_exec_then_analyst_revenue` | personas |
| Mixed finance audit | `persona_finance_metric_audit` | personas |
| `join_grain` + test users | `persona_adoption_across_orgs` | personas |
| `support_then_engineer` | `persona_support_then_engineer` | personas |
| `offtopic_then_data` | `persona_offtopic_then_revenue` | personas |

**Deferred (Tier 3):** retention, workflows, release impact — no matching tables in seed.

## Iterative tuning (last step)

After `run_suite.py`, follow [`../../references/iterative-eval-loop.md`](../../references/iterative-eval-loop.md):

| Layer | Use for |
|-------|---------|
| `FnCheck` | Tool use, safety (full trace), crisp single-turn gold |
| `Conformity` | Short policy rules on static turns |
| `llm_judge_conversation` | Multi-turn ambiguous metrics, handoffs, mixed directions |

**Loop iteration 3 (trace-backed):** Full suite 20/23 (87.0%) after prompt + persona caps — failures: static `defines_active` (agent prose gap; SQL filter OK), `persona_wrong_then_correct` (agent contradicted turn-4 count on turn 5), `persona_support_then_engineer` (judge calibrated to accept correcting 3 vs 2 non-test users). Added `ambiguous_metric_total_revenue`; capped simulator drift.

Target: safety 100%; quality often 70–95% with **actionable** failures.

## How to run

```bash
cd example-agent && cp .env.example .env && uv sync --extra dev
./scripts/run_eval.sh                    # guardrails + full suite
uv run python run_suite.py --safety-only # 4 safety scenarios
uv run python run_suite.py --personas-only # 9 persona scenarios
uv run python run_suite.py --no-personas # static + safety + OOS
uv run pytest eval/test_sql_guardrails.py eval/test_check_helpers.py -q  # no API key
uv run pytest eval/test_suite_pytest.py -q   # needs OPENAI_API_KEY
```

## Files

| Path | Role |
|------|------|
| `eval/scenarios.py` | `build_suite()` |
| `eval/check_helpers.py` | `FnCheck` factories + `llm_judge_conversation` |
| `eval/test_sql_guardrails.py` | `validate_sql` unit tests |
| `eval/test_suite_pytest.py` | Async pytest + JUnit export |
| `src/agent.py` | `analytics_agent(inputs) -> dict` |
