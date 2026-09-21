---
name: agent-to-hub
description: Connect a local or remote AI agent to Giskard Hub through an authenticated, non-streaming HTTPS endpoint. Use when a user asks to connect, integrate, or register their agent with the Hub. Build a minimal wrapper, deploy or tunnel it, and use the Hub SDK connection test to guide any fixes.
license: Apache-2.0
metadata:
  author: Giskard
  version: 1.0.0
  category: integration
  tags: [giskard, hub, agent, integration, https, tunnel]
---

# Agent to Hub

Get to the first Hub connection attempt quickly: build the smallest adapter, expose it over HTTPS, register it, and use Hub's connection test to guide fixes. Use the target's stack and the coding agent's available tools. Supporting paths are relative to this skill directory.

Do not create a test suite, run broad audits or extra review passes, refactor unrelated code, or write extensive documentation before the first Hub attempt. Honor required project checks without turning this connection task into a general hardening exercise.

## 1. Gather the essentials

Locate the target's callable/API, input/output shape, streaming behavior, and conversation state. Infer its name, description, and supported languages. Ask only for missing connection details:

- **Hub URL**.
- **Hub API key**: link to [Finding your API key](https://docs.giskard.ai/hub/sdk/quickstart#finding-your-api-key); accept secure input or an already configured environment variable.
- **Hub project name or ID**.

As soon as credentials are available, instantiate `HubClient` and resolve the project with `hub.projects.list()` or `hub.projects.retrieve(project_id)`. This checks Hub access early. Ask about ambiguous matches; do not choose the first project implicitly.

Use `GISKARD_HUB_BASE_URL` and `GISKARD_HUB_API_KEY` for the SDK. Generate a separate cryptographically random `AGENT_WRAPPER_API_KEY` for the wrapper. Keep secrets in the environment, an explicitly loaded and git-ignored `.env`, or a secret store; never in code, URLs, or logs. Never send the Hub key to the wrapper.

## 2. Build the minimal adapter

Use [wrapper-contracts.md](references/wrapper-contracts.md) for Chat/Structured schemas and multi-turn bindings, following the [Hub contract](https://docs.giskard.ai/hub/ui/setup/agents). For Chat, publish the canonical schemas verbatim; keep stricter runtime validation separate. Reuse existing dependencies where practical.

- Implement a JSON `POST` route, e.g. `/giskard/invoke`, around the actual target, with matching input/output schemas.
- Require `X-API-Key` or equivalent authentication before invoking the target. Refuse startup with an empty configured key; use constant-time comparison and reject missing/wrong keys with `401` or `403`.
- Return one complete `application/json` response. **Never stream to Hub.** Prefer a non-streaming call; otherwise consume the target's stream to completion and assemble the final answer/object. Preserve history or per-conversation state where supported.
- Use a finite timeout and return sanitized errors on failure, without partial answers or secrets.

Start the wrapper and make **one cheap request with an invalid key** to confirm rejection before exposing it. This does not invoke the model. Proceed without additional local inference, stream simulations, history tests, or a generated test suite.

## 3. Expose an HTTPS endpoint

**The URL registered with Hub must use `https://` with certificate verification enabled.** TLS can terminate at the tunnel or reverse proxy; `http://127.0.0.1` is only the private loopback hop. It is not the Hub endpoint and does not need a self-signed certificate.

For an easily editable remote target, create and deploy the wrapper on that host using its existing deployment and HTTPS ingress. Otherwise run a separate adapter; a local adapter needs a tunnel.

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

Use Python 3.10+ and the **`giskard-hub` SDK**; see [hub-sdk.md](references/hub-sdk.md) for the short example and authoritative docs.

1. Call `hub.agents.create` with `project_id`, `name`, `description`, full HTTPS `url`, authentication `headers`, `supported_languages`, `input_schema`, `output_schema`, and `auto_bindings`. Use history/state bindings for multi-turn targets and `[]` for independent calls. If the user supplied an existing Hub agent, update that record instead.
2. Retain the returned ID and **immediately call `hub.agents.test_connection`** with that ID, URL, project, headers, and input schema. Hub makes the request to the wrapper; local DNS trouble reaching the tunnel does not establish that Hub cannot reach it.
3. Inspect the actual result and error details. If it fails, fix the reported URL, credentials, adapter, schema, or network issue and re-test the same registration. Do not recreate agents or perform speculative refactoring. Stop with a concrete blocker if credentials, permissions, or connectivity cannot be obtained.

The default verification is this Hub connection test. Use `generate_completion`, history tests, or focused regression tests only when requested or needed to investigate a specific failure. Keep authentication and TLS verification enabled throughout.

## 5. Finish

Once Hub verifies the connection, tell the user it works and provide the HTTPS endpoint, agent ID, project, and brief run/stop instructions. Keep a local wrapper and tunnel alive; explain their temporary lifetime. If the tunnel URL changes, update the same Hub agent and re-test. Do not continue into extra testing or documentation by default.
