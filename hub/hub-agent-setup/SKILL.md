---
name: hub-agent-setup
description: Connect a local or remote AI agent to Giskard Hub through an authenticated, non-streaming HTTPS endpoint. Use when a user asks to connect, integrate, or register their agent with the Hub, including triggered (cron, webhook, event) agents with no user input that Hub tests through tool mocks. Build a minimal wrapper, deploy or tunnel it, and use the Hub connection test (SDK or MCP) to guide any fixes.
license: Apache-2.0
metadata:
  author: Giskard
  version: 1.2.0
  category: integration
  tags: [giskard, hub, agent, integration, https, tunnel, cron, tool-mocks]
---

# Hub Agent Setup

Get to the first Hub connection attempt quickly: build the smallest adapter, expose it over HTTPS, register it, and use Hub's connection test to guide fixes. Use the target's stack and the coding agent's available tools. Supporting paths are relative to this skill directory.

Do not create a test suite, run broad audits or extra review passes, refactor unrelated code, or write extensive documentation before the first Hub attempt. The one exception is a triggered agent's mock check (one local request per mock kind, see [triggered-agents.md](references/triggered-agents.md#verify-the-mocks-locally)), which confirms that write tools are neutralized. Honor required project checks without turning this connection task into a general hardening exercise.

## 1. Gather the essentials

Identify the target agent first. A project can contain several agents, for example separate entry points, services, graphs, or chains. If the user did not name the target and more than one candidate exists, list the candidates briefly with their locations and ask which one to register. Never pick one yourself. Continue without asking only when the user named the target or the project contains a single candidate.

Locate the target's callable/API, input/output shape, streaming behavior, conversation state, and whether it is already deployed. Infer its name, description, and supported languages. Ask only for missing connection details:

- **Hub URL**.
- **Hub API key**: link to [Finding your API key](https://docs.giskard.ai/hub/sdk/quickstart#finding-your-api-key); accept secure input or an already configured environment variable.
- **Hub project name or ID**.

If the target has no user message (a cron job, scheduler, webhook, or queue worker that reads state through tools and acts through write tools), it is a **triggered agent**. Follow [triggered-agents.md](references/triggered-agents.md) as well: register it as Structured with a `{"inputs", "mocks"}` envelope and document its mockable tools in the Hub description. For a hybrid chat and cron agent, ask which mode to register, or register both.

Use the `giskard-hub` Python SDK when Python 3.10+ is available. Without Python, connect to the Giskard Hub MCP server and use its tools for the same steps. See [hub-sdk.md](references/hub-sdk.md#without-python-hub-mcp).

As soon as credentials are available, instantiate `HubClient` and resolve the project with `hub.projects.list()` or `hub.projects.retrieve(project_id)` (MCP: `list_projects` or `retrieve_project`). This checks Hub access early. Ask about ambiguous matches; do not choose the first project implicitly.

Use `GISKARD_HUB_BASE_URL` and `GISKARD_HUB_API_KEY` for the SDK. Generate a separate cryptographically random `AGENT_WRAPPER_API_KEY` for the wrapper. Keep secrets in the environment, an explicitly loaded and git-ignored `.env`, or a secret store; never in code, URLs, or logs. Never send the Hub key to the wrapper.

## 2. Build the minimal adapter

Choose the hosting path in step 3 first, because it decides where the wrapper runs.

Use [wrapper-contracts.md](references/wrapper-contracts.md) for Chat/Structured schemas and multi-turn bindings, following the [Hub contract](https://docs.giskard.ai/hub/ui/setup/agents). For Chat, publish the canonical schemas verbatim; keep stricter runtime validation separate. Reuse existing dependencies where practical. If a deployed target already has an authenticated HTTPS endpoint that meets this contract, skip the wrapper and register that endpoint.

- Implement a JSON `POST` route, e.g. `/giskard/invoke`, around the actual target, with matching input/output schemas.
- Require `X-API-Key` or equivalent authentication before invoking the target. Refuse startup with an empty configured key. Inside the target's own app, disable only the wrapper route instead, so the target keeps running. Use constant-time comparison and reject missing/wrong keys with `401` or `403`.
- Return one complete `application/json` response. **Never stream to Hub.** Prefer a non-streaming call; otherwise consume the target's stream to completion and assemble the final answer/object. Preserve history or per-conversation state where supported.
- Use a finite timeout and return sanitized errors on failure, without partial answers or secrets.
- For a triggered agent or a tool-using agent that Hub should test through tool data, accept `mocks`, reset fake world state per request, make every write tool hit a fake or recorder, and return the tool calls and side effects. See [triggered-agents.md](references/triggered-agents.md).

Start the wrapper and make **one cheap request with an invalid key** to confirm rejection before exposing it. For a remote wrapper, you can send this request to the deployed HTTPS URL after the deploy instead. This does not invoke the model. Apart from a triggered agent's mock check, proceed without additional local inference, stream simulations, history tests, or a generated test suite.

## 3. Expose an HTTPS endpoint

**The URL registered with Hub must use `https://` with certificate verification enabled.** TLS can terminate at the tunnel or reverse proxy; `http://127.0.0.1` is only the private loopback hop. It is not the Hub endpoint and does not need a self-signed certificate.

Recommend the remote flow when the target is already deployed and the wrapper is easy to deploy there. Deploy the wrapper with the host's existing deployment and HTTPS ingress. Confirm with the user before you deploy, and ask them to set `AGENT_WRAPPER_API_KEY` on the host first. A deployed endpoint has a stable URL and needs no local processes, so it is more reliable for long evaluations and scans.

A tunnel is the alternative. It is the only option when the target runs only locally. For a deployed target, use a tunnel only when the user prefers it or the wrapper is hard to deploy. Then run a local wrapper that calls the deployed target. Tell the user that the tunnel URL is temporary and that a long run fails if the machine sleeps or a process stops.

For a local wrapper, tell the user **before opening the tunnel**:

> I’ll open a public HTTPS connection to your local wrapper so Giskard Hub can reach it. Requests remain protected by the wrapper's API key. Keep the wrapper and tunnel running while using the agent in Hub.

Then open a [Cloudflare quick tunnel](https://developers.cloudflare.com/tunnel/get-started/#quick-tunnels-development) or an already configured [ngrok](https://ngrok.com/) tunnel. Install the official CLI if needed and permitted. Choose one:

```sh
cloudflared tunnel --url http://127.0.0.1:8080
# Or:
ngrok http 8080
```

Expose only the wrapper service. Append its invocation path to the **actual HTTPS URL** reported by the tunnel. Keep both processes running in persistent sessions and proceed directly to registration; a successful public `curl` from the developer's machine is not a prerequisite.

## 4. Register, test, and fix only what fails

Use Python 3.10+ and the **`giskard-hub` SDK**, or the Hub MCP tools when Python is unavailable. See [hub-sdk.md](references/hub-sdk.md) for the short example, the MCP tool names, and authoritative docs.

1. Call `hub.agents.create` (MCP: `create_agent`) with `project_id`, `name`, `description`, full HTTPS `url`, authentication `headers`, `supported_languages`, `input_schema`, `output_schema`, and `auto_bindings`. Use history/state bindings for multi-turn targets and `[]` for independent calls. If the user supplied an existing Hub agent, update that record instead. For a triggered agent, append the "Mockable tools" section to `description` as shown in [triggered-agents.md](references/triggered-agents.md#make-the-mock-surface-discoverable).
2. Retain the returned ID and **immediately call `hub.agents.test_connection`** (MCP: `test_agent_connection`) with that ID, URL, project, headers, and input schema. Hub makes the request to the wrapper; local DNS trouble reaching the tunnel does not establish that Hub cannot reach it.
3. Inspect the actual result and error details. If it fails, fix the reported URL, credentials, adapter, schema, or network issue and re-test the same registration. Do not recreate agents or perform speculative refactoring. Stop with a concrete blocker if credentials, permissions, or connectivity cannot be obtained.

The default verification is this Hub connection test. Use `generate_completion`, history tests, or focused regression tests only when requested or needed to investigate a specific failure. Keep authentication and TLS verification enabled throughout.

## 5. Finish

Once Hub verifies the connection, tell the user it works and provide the HTTPS endpoint, agent ID, project, and brief run/stop instructions. Keep a local wrapper and tunnel alive; explain their temporary lifetime. If the tunnel URL changes, update the same Hub agent and re-test. Do not continue into extra testing or documentation by default.
