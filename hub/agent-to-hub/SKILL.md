---
name: agent-to-hub
description: Connect an existing local or remote AI agent to Giskard Hub. Use when a user asks to connect, integrate, or register their agent with the Hub. Builds an authenticated, non-streaming HTTP wrapper, deploys it or exposes it through a local tunnel, registers it with the Hub SDK, and verifies the connection.
license: Apache-2.0
metadata:
  author: Giskard
  version: 1.0.0
  category: integration
  tags: [giskard, hub, agent, integration, http, tunnel]
---

# Agent to Hub

Complete the connection, from working wrapper code to a successful Hub connection test. Use the target's language, framework, deployment setup, and the coding agent's available tools; no particular editor, agent host, or cloud provider is required. Supporting paths are relative to this skill directory.

## Gather the connection details

Inspect the target's entry point or remote API, input/output types, credentials, streaming behavior, and conversation state. Determine where it runs and whether its remote source and deployment are readily accessible. Infer the agent's name, purpose, and supported languages from the project; ask about material gaps instead of inventing capabilities.

Ask the user for these values, requesting only those not already supplied:

- **Hub URL**: the base URL of their Giskard Hub instance.
- **Hub API key**: link to [Finding your API key](https://docs.giskard.ai/hub/sdk/quickstart#finding-your-api-key). Let them provide it through a secure input mechanism or set `GISKARD_HUB_API_KEY` in the execution environment and confirm it is ready.
- **Hub project name or project ID**: resolve a name using `hub.projects.list()`; ask if the match is ambiguous. Verify an ID with `hub.projects.retrieve(project_id)`. Do not select the first project or create a new one implicitly.

Use `GISKARD_HUB_BASE_URL` and `GISKARD_HUB_API_KEY` for SDK authentication. Generate a **separate** cryptographically random wrapper key, such as 32 random bytes encoded for an HTTP header, and store it as `AGENT_WRAPPER_API_KEY` in the wrapper's environment or secret store. Keep the Hub key, wrapper key, target's own credentials, and any tunnel token distinct. Never commit or print secrets, include them in URLs, or dump SDK agent objects that contain headers. An environment file must be excluded from version control and loaded explicitly by the relevant process.

Continue inspecting and implementing the wrapper while waiting for Hub details; registration requires all three values.

For a local wrapper, explain **before opening a tunnel**:

> I’ll open a public HTTPS connection to your local wrapper so Giskard Hub can reach it. The wrapper will require an API key and reject requests with a missing or invalid key. The connection stays available only while the wrapper and tunnel are running.

This is an upfront disclosure, not a separate confirmation gate. Proceed within the user's authorization and the environment's execution permissions.

## Build the HTTP wrapper

Read [wrapper-contracts.md](references/wrapper-contracts.md) and the current [Hub agent contract](https://docs.giskard.ai/hub/ui/setup/agents). Implement an actual adapter around the discovered target, including dependencies and startup configuration. Do not leave a stub for the user to fill in.

- Expose a JSON `POST` route, for example `/giskard/invoke`. Choose **Chat** for message conversations or **Structured** for custom JSON inputs and outputs. Define explicit input and output JSON Schemas that match the implemented bodies.
- Require `X-API-Key` on every invocation (or an existing equally strong authentication mechanism). Refuse to start if the configured key is absent or empty. Compare secrets using the runtime's constant-time comparison facility; missing or wrong keys must return `401` or `403` **before invoking the target**. Keep authentication enabled during testing and deployment.
- Validate the request, adapt it to the target, and return only a complete JSON result with `Content-Type: application/json`. Reject invalid bodies with an appropriate `4xx`; return sanitized `5xx` errors for upstream failures. Do not expose credentials or stack traces.
- **Never return a streaming response.** Prefer the target's non-streaming API when available. Otherwise consume its stream through successful completion, assemble the final answer or object, then serialize one Hub-compatible response. Do not forward SSE, NDJSON, WebSocket frames, generator responses, or token events to Hub.
- Preserve real multi-turn behavior: pass history to stateless targets or propagate per-conversation state to stateful targets. Do not share a global session across Hub conversations or silently discard earlier messages. Configure the matching `auto_bindings` at registration.
- Set finite upstream/overall timeouts and response-size limits appropriate to the target. If generation times out, disconnects before completion, or exceeds a limit, close the upstream stream and return an error, never partial success. Ensure the deployment and tunnel timeouts can accommodate a full buffered response.

Test the generated adapter before exposing it: missing and incorrect keys reject without running the target; an authenticated request returns schema-valid JSON; a delayed multi-chunk target produces the full answer only after completion; an interrupted stream fails without a partial answer. For multi-turn targets, test a dependent second turn and an independent conversation to verify context and isolation. Use representative native events when testing a streaming adapter.

## Make the wrapper reachable

### Remote target that is easy to edit

When the remote target has accessible source and an established deployment path, **create and deploy the wrapper on that remote host** using its existing service, container, or application deployment. Configure the wrapper key in the remote secret environment, install its dependencies, deploy the adapter, and verify the actual HTTPS route. Account for reverse-proxy routing and request timeouts. Use the existing deployment mechanism rather than assuming SSH, a particular cloud, or a new infrastructure stack.

If access is missing, request the specific source/deployment access needed and finish any independent implementation work. When the remote target cannot reasonably be edited, build a separate adapter that calls its API; if this adapter runs locally, follow the local tunnel procedure below. Keep the target's native credentials server-side.

### Local target and wrapper, or any local adapter

After the disclosure and local authentication tests, start the wrapper on a dedicated loopback port (for example `127.0.0.1:8080`) and **open** a Cloudflare quick tunnel or ngrok tunnel. Expose only the wrapper service, not an unrelated development server or the unauthenticated native agent API.

Prefer an already configured provider. Otherwise [Cloudflare quick tunnels](https://developers.cloudflare.com/tunnel/get-started/#quick-tunnels-development) work without a Cloudflare account. Install the appropriate official CLI if needed and allowed, then run:

```sh
cloudflared tunnel --url http://127.0.0.1:8080
```

Read the actual HTTPS `trycloudflare.com` URL from the process output. Quick tunnels are for development, have no uptime guarantee, and do not support SSE; the wrapper must still buffer any upstream stream.

Alternatively, use [ngrok](https://ngrok.com/) and its [local endpoint quickstart](https://ngrok.com/docs/share-localhost/quickstart). Configure the user's ngrok account token securely if needed, then run:

```sh
ngrok http 8080
```

Use the reported HTTPS forwarding URL. Avoid browser-login gates that prevent Hub's HTTP requests from reaching the authenticated wrapper. Provider account authentication does not replace the wrapper's API key.

Run the wrapper and tunnel in persistent process sessions supported by the environment. Record their process/session identifiers, log locations, and concrete restart/stop commands without secrets. Keep both running for subsequent Hub use; do not kill them when the connection test ends. If the environment cannot keep processes alive, explain that limitation and arrange a user-managed session before claiming the endpoint is ready.

### Verify the deployed route

Append the invocation path to the real remote or tunnel URL, e.g. `https://assigned-host/giskard/invoke`. Send requests to **that exact URL** with no key, a wrong key, and the correct key. Require authentication failures for the first two and a complete schema-valid response for the third. A working local port, tunnel startup message, health route, HTML page, or login redirect is not sufficient evidence. Never register `localhost`, a fabricated domain, or just the tunnel root when the wrapper uses a subpath.

## Register and test through Hub

Read [hub-sdk.md](references/hub-sdk.md). Use Python 3.10+ and the **`giskard-hub` SDK**, installing it in the project's environment or a dedicated virtual environment. The wrapper itself can use any language. Consult the [SDK introduction](https://docs.giskard.ai/hub/sdk), [agent guide](https://docs.giskard.ai/hub/sdk/guides/agents-and-knowledge-bases), and [API reference](https://docs.giskard.ai/hub/sdk/reference) for the installed version.

Once the real endpoint is reachable and the project is resolved:

1. Instantiate `HubClient` with the user's Hub URL and Hub API key.
2. Call `hub.agents.create` with `project_id`, `name`, meaningful `description`, full `url`, authentication `headers`, actual `supported_languages`, `input_schema`, `output_schema`, and explicit `auto_bindings`. Use aggregate history or forwarded state for multi-turn support and `[]` for independent calls.
3. Save the returned agent ID without secrets. After creation, call `hub.agents.test_connection` with `agent_id`, `url`, `project_id`, the same authentication `headers`, and `input_schema`. Inspect errors and validate the returned payload; an HTTP success or a created record alone does not mean the connection works.
4. Optionally use `hub.agents.generate_completion` for a short, harmless playground-style check. Use a second turn with `interactions` when verifying Hub's multi-turn bindings, and check the returned `error` and `output` rather than assuming success.

If a test fails, diagnose the wrapper, authentication, schema, URL, or binding issue, fix it, and re-test the existing registration. Do not create duplicate agents on each retry. After an ambiguous create timeout, list agents in the selected project and reconcile the name/URL before retrying. If a required credential, permission, or network route is unavailable, state the exact blocker and the next action; do not claim completion or retry indefinitely. Do not weaken authentication to make a test pass.

## Finish

Only tell the user everything works after endpoint authentication checks, schema checks, and the **post-create Hub connection test** succeed, along with any additional checks you ran. Report the agent name and ID, selected project, endpoint, contract mode, and verification outcome. Include where the wrapper and registration code live and how to run them.

For a tunnel, explain that this is a temporary public connection protected by the wrapper key; keep the processes alive and give their stop/restart instructions. If the public URL changes, update the same agent with `hub.agents.update(agent_id, url=new_url)` and run `test_connection` again. Do not claim an unfinished deployment or failing check is working.
