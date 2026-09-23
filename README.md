# Giskard Skills
Agent skills to streamline adoption and usage of Giskard products — compatible with any coding agent, including Claude Code, Cursor, and others.

## Prerequisites

- A coding agent that supports skills or plugins.
- Node.js with `npx` for the `npx skills add` installation commands below.
- The runtime and dependencies for the skills you use:

| Skill | Runtime and dependencies | Service access |
| --- | --- | --- |
| `scenario-generator` | Python 3.12+; `pip install "giskard[openai]"`, or the `anthropic`, `google`, `azure`, or `litellm` extra. Add the `scan` extra for automatic vulnerability scans. | The target agent and the configured model provider for generation, simulation, and LLM judges. |
| `rag-evaluator` | Python 3.12+; `pip install "giskard[openai,scan]"`, substituting your provider extra as needed. | The target RAG agent, any documents or retriever used in the evaluation, and the configured generation, judge, and embedding providers. |
| `hub-agent-setup` | Python 3.10+; `giskard-hub`, plus dependencies needed to wrap your agent. For a local agent, `cloudflared` or an already configured `ngrok` installation. | A Giskard Hub project and an agent that can be exposed through an authenticated HTTPS endpoint. |
| `giskard-to-collibra` | Python 3.10+; `pip install -r integrations/giskard-to-collibra/requirements.txt` (`giskard-hub>=3.1.1` and `requests`). | Giskard Hub scan access and a Collibra instance with AI Governance and permission to import assets and write metrics to the chosen domain. |

Run dependency installation from the repository root in a Python virtual environment. The bare `giskard-checks` package does not include a model provider SDK.

For LiteLLM, install `giskard[litellm]` (or `giskard[litellm,scan]` for scans) and explicitly configure `LiteLLMGenerator` with your provider's credentials. See the [generator configuration examples](oss/checks/scenario-generator/references/api-reference.md#picking-a-judge-model).

## Available Skills

<table>
  <thead>
    <tr>
      <th width="20%">Skill</th>
      <th width="40%">Install Command</th>
      <th width="40%">When to Use</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>hub-agent-setup</td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill hub-agent-setup</code></td>
      <td>Use when a user wants to connect a local or remote agent to Giskard Hub. Creates an authenticated HTTPS endpoint with complete, non-streaming Chat or Structured responses, deploys it remotely or opens a local tunnel, and uses the Hub SDK connection test to guide any fixes.</td>
    </tr>
    <tr>
      <td>scenario-generator</td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill scenario-generator</code></td>
      <td>Use when a user describes their AI agent and wants to create adversarial test scenarios, red-team their AI, generate evaluation suites, or build checks using the <code>giskard.checks</code> library. Triggers on phrases like "create scenarios", "test my agent", "evaluate my chatbot", "red-team my AI", or "generate checks".</td>
    </tr>
    <tr>
      <td>rag-evaluator</td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill rag-evaluator</code></td>
      <td>Use when a user wants to evaluate a RAG (Retrieval-Augmented Generation) system or a Q&amp;A bot grounded in documents. Covers groundedness, answer relevance, retrieval quality, hallucination, citation accuracy, and out-of-scope refusal. Triggers on phrases like "evaluate my RAG", "test my retrieval", "check groundedness", "build a RAG eval suite", or "test if my agent hallucinates". Quality-focused; for adversarial / red-teaming use <code>scenario-generator</code> instead.</td>
    </tr>
    <tr>
      <td>giskard-to-collibra</td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill giskard-to-collibra</code></td>
      <td>Use when a user wants to export, push, or sync Giskard Hub scan results into Collibra AI Governance. Creates or updates the AI Agent asset hierarchy in Collibra (re-runs are idempotent) and pushes per-probe pass/fail metrics to the Quality tab. Triggers on phrases like "export my scan to Collibra", "push results to Collibra", or "send the latest scan of this project to Collibra". Requires a Collibra instance with AI Governance.</td>
    </tr>
  </tbody>
</table>

## Install as a Claude Code Plugin

This repository can also be used as a [Claude Code plugin](https://code.claude.com/docs/en/plugins). Clone the repo and start Claude with the `--plugin-dir` flag pointing at it:

```bash
claude --plugin-dir ./giskard-skills
```

Once Claude Code is running, use the `/giskard-skills` command to list the available skills.

## Credentials and configuration

Configure credentials only for the skills and providers you use. Keep secrets in environment variables, a secret store, or a git-ignored `.env` file; never include them in source code or logs.

| Integration | Configuration |
| --- | --- |
| Giskard Hub | `GISKARD_HUB_BASE_URL` for your Hub instance and `GISKARD_HUB_API_KEY` for SDK access. Hub setup also needs a project name or ID. |
| Agent wrapper | `AGENT_WRAPPER_API_KEY`, generated separately from the Hub key. Hub receives this key as the registered agent's authentication header so it can call the wrapper. The Hub API key is never sent to the wrapper. |
| Collibra | `COLLIBRA_URL`, `COLLIBRA_USER`, `COLLIBRA_PASSWORD`, and `COLLIBRA_DOMAIN_ID`, in addition to the Hub configuration. See [env.example](integrations/giskard-to-collibra/env.example). The export script loads `.env` from the working directory and its script directory; existing environment variables take precedence. |
| Model providers | The configured provider's credentials, such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`. The `azure_ai/...` model prefix uses `AZURE_AI_API_KEY` and `AZURE_AI_ENDPOINT`; `azure/...` uses `AZURE_API_KEY` and `AZURE_API_BASE`. |

Configure embedding models separately when using a provider other than OpenAI. The evaluation examples default to `text-embedding-3-small`; an unprefixed embedding model name routes to OpenAI. Set `GISKARD_CHECKS_DEFAULT_EMBEDDING_MODEL` to an appropriate provider-prefixed model ID when needed.

## Network access and data flows

Depending on the skill, data is shared with:

| Destination | Data and operations |
| --- | --- |
| Giskard Hub (`GISKARD_HUB_BASE_URL`) | Registers agent metadata, schemas, endpoint, and wrapper credentials; reads projects and scan results. |
| Your agent's endpoint | Receives test inputs and returns responses during connection tests and evaluations. |
| Collibra (`COLLIBRA_URL`, HTTPS) | Receives agent/probe metadata, endpoint URLs, scan IDs/dates, and pass/fail metrics to create or update governance assets. |
| Configured model and embedding providers | Receive descriptions, prompts, agent outputs, judging criteria, and supplied document text for generation and evaluation. |
| Cloudflare Tunnel or ngrok (optional) | Carries Hub requests and agent responses through a public HTTPS URL protected by the wrapper's API key. |

Installation uses GitHub, package registries, and optional tunnel CLI downloads. Collibra exports also save metadata locally in `import_agents.json`; evaluations may save reports. Your coding agent and target agent retain their own service connections and data-handling settings.

## Usage costs

Scenario generation, simulated conversations, LLM judges, embeddings, automatic scans, and calls to your target agent can incur model-provider or agent-service charges. Costs depend on the selected models, document volume, scenario count, conversation turns, and reruns. Hub, Collibra, deployment, and tunnel services are subject to your existing service plans. Installing the skills does not include service access or API credits.

## License

This repository is licensed under [Apache-2.0](LICENSE).
