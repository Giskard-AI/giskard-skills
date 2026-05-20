# Example-agent coverage (RAG)

Optional local reference SUT for developing evals. **Production evals use `target=user_agent`** — not this demo.

Direction slugs come from [`../references/scenario-directions.md`](../references/scenario-directions.md).

## Demo KB (`sample_kb/`)

| Doc ID | Topic |
|--------|-------|
| `refund-policy` | Refund window (30 days, annual plans) |
| `pricing` | Starter plan ($49/mo) |
| `deployment` | GCP-only production |
| `data-retention` | Query logs retained 90 days |
| `getting-started` | Onboarding steps |

## Direction → scenario map

| Direction slug | Scenario name | Group |
|----------------|---------------|-------|
| `factual_lookup` (in-domain) | `refund_policy_in_scope` | in_scope |
| `factual_lookup` | `deployment_gcp` | in_scope |
| `factual_lookup` | `pricing_starter` | in_scope |
| `factual_lookup` | `data_retention_logs` | in_scope |
| Recall@k (labelled) | `retrieval_refund_policy_labelled` | retrieval_labelled |
| `oos_probe` (wrong platform) | `out_of_scope_aws_deploy` | out_of_scope |
| `oos_probe` (off-topic) | `out_of_scope_weather` | out_of_scope |

### Labelled retrieval scenario

- Query: refund window for annual subscriptions
- Expected doc in top-3: `refund-policy`

## How to run

```bash
cd example-agent && cp .env.example .env && uv sync
./scripts/run_eval.sh
uv run python run_suite.py --in-scope-only
uv run python run_suite.py --oos-only
uv run pytest eval/test_retrieval_guardrails.py -q   # no API key
uv run pytest eval/test_suite_pytest.py -q         # needs OPENAI_API_KEY
```

## Files

| Path | Role |
|------|------|
| `eval/scenarios.py` | `build_suite()` |
| `eval/test_retrieval_guardrails.py` | Keyword retriever unit tests |
| `eval/test_suite_pytest.py` | Async pytest + JUnit export |
| `src/agent.py` | `rag_agent(inputs) -> dict` |
| `src/retriever.py` | Keyword retriever over `sample_kb/` |

## Trace contract

```python
{"answer": str, "context": list[str], "sources": list[dict], "tool_calls": list[dict]}
```

See [`../references/tool-usage.md`](../references/tool-usage.md).
