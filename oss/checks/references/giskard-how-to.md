# Giskard Checks how-to index

Map skill workflows to [official Giskard how-to guides](https://docs.giskard.ai/oss/checks/how-to). Load the guide instead of re-deriving API details.

| Skill task | Official guide |
|------------|----------------|
| First suite / quickstart | [Quickstart](https://docs.giskard.ai/oss/checks) |
| Run suites in CI | [Run Tests with pytest](https://docs.giskard.ai/oss/checks/how-to/run-tests-with-pytest), [CI/CD Integration](https://docs.giskard.ai/oss/checks/how-to/ci-cd-integration) |
| Chained multi-turn (`.interact().check().interact()`) | [Multi-Turn Scenarios](https://docs.giskard.ai/oss/checks/tutorials/multi-turn) |
| Multi-turn personas | [Simulate Users](https://docs.giskard.ai/oss/checks/how-to/simulate-users) |
| Debug failing scenarios | [Debug with Spy](https://docs.giskard.ai/oss/checks/how-to/debug-with-spy) |
| Dict / structured agent outputs | [Testing Structured Outputs](https://docs.giskard.ai/oss/checks/how-to/testing-structured-outputs) |
| Large suite runs | [Batch Evaluation](https://docs.giskard.ai/oss/checks/how-to/batch-evaluation) |
| Custom `FnCheck` / trace logic | [Custom Checks](https://docs.giskard.ai/oss/checks/how-to/custom-checks), [Custom trace types](https://docs.giskard.ai/oss/checks/how-to/custom-trace-types) |
| Stateful multi-step | [Stateful Checks](https://docs.giskard.ai/oss/checks/how-to/stateful-checks) |

## Checks reference

- [Built-in checks API](https://docs.giskard.ai/oss/checks/reference/checks)
- [What are Giskard Checks?](https://docs.giskard.ai/oss/checks) — async evaluators, serializable results, multi-turn traces

## Agent skills (this repo)

| Skill | Docs site | Repo |
|-------|-----------|------|
| `scenario-generator` | [Agent Skills](https://docs.giskard.ai/oss/agent-skills) | `oss/checks/scenario-generator/` |
| `rag-evaluator` | [Agent Skills](https://docs.giskard.ai/oss/agent-skills) | `oss/checks/rag-evaluator/` |
| `text2sql-evaluator` | *(not yet on docs site — use repo)* | `oss/checks/text2sql-evaluator/` |

## See also

- [`api-reference-core.md`](./api-reference-core.md) — imports, `target=`, trace keys
- [`eval-lifecycle.md`](./eval-lifecycle.md) — guardrails vs evaluators, JUnit export
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) — skill layout and shared refs
