# Giskard Hub local vs SaaS

**Short answer:** Hub is self-hostable, but not from this repo or the `giskard-hub` PyPI package alone. There is no documented public “one command” install on docs.giskard.ai; enterprise/on-prem uses the `Giskard-AI/llm-hub` **local-install** tarball or internal **Docker Compose** dev stack.

## What is what

| Artifact | Role |
| --- | --- |
| `pip install giskard-hub` | **Client SDK** only (`HubClient`, MCP at `/_api/mcp/`). Not a Hub server. |
| `Giskard-AI/llm-hub` | **Hub server** (UI, API, workers, scans, evaluations). |
| `giskard hub start` + `giskardai/giskard:latest:7860` | **Legacy** OSS UI from old `giskard` package — **not** current enterprise Hub. |

Public docs: [Hub SDK quickstart](https://docs.giskard.ai/hub/sdk/quickstart) lists prerequisites as “cloud **or self-hosted**” Hub + API key from the UI; [Hub UI](https://docs.giskard.ai/hub/ui) points on-premise installs to **Contact us**.

## Self-hosted paths (documented in `llm-hub`, not on docs.giskard.ai)

### A. Docker Compose dev (engineers)

- **Requires:** Docker, Docker Compose, `make`.
- **Steps:** clone `llm-hub` → `make setup` → configure `.env` LLM profiles → `make reset_data` → `make up`.
- **URLs:** e.g. `https://app.llm.localhost`, API `/_api/docs`.

### B. Local-install package (on-prem / tarball)

- **Requires:** Python 3.12+, Node 18+, PostgreSQL **with pgvector**; optional Docker only for DB in tests.
- **Steps:** extract `local-llm-hub.tar.gz` → `cp env.example .env` → set DB password, `GISKARD_HUB_TENANT_SECRETS_KEY`, LLM profiles → `sh start.sh`.
- **Ports:** frontend `APP_URL` (default `http://localhost:3000`), backend `http://localhost:8000/_api`.
- **Auth:** `GISKARD_HUB_ENABLE_AUTH=false` (no Keycloak in package).
- **SDK smoke test** uses `GISKARD_HUB_BASE_URL=http://localhost:8000/_api` and default `GISKARD_HUB_API_KEY=fake-api-key-for-testing` (Bearer) — still **a** Hub API key, not “no credentials”.
- **Package source:** `make package` in `llm-hub`; not published to PyPI.

## Pointing hub-agent-setup at local Hub

Once a Hub instance is running:

```bash
export GISKARD_HUB_BASE_URL="http://localhost:8000"   # or https://your-tenant-host; SDK appends /_api
export GISKARD_HUB_API_KEY="<from UI user badge, or local-install test key>"
# Multi-tenant / Docker internal host only:
# export GISKARD_HUB_TENANT_HOST="app.llm.localhost"
```

Follow this skill for the **agent wrapper**: Hub still POSTs to a **verified HTTPS** agent URL (tunnel or deployed ingress) with `AGENT_WRAPPER_API_KEY`. Local Hub on the same machine does not remove the wrapper/tunnel requirement for remote evaluations unless the agent is reachable from the Hub network over HTTPS.

**OSS-only checks:** You can run `giskard.checks` suites locally without Hub, or upload finished runs with `hub.evaluations.upload()` — registration, connection tests, and remote evaluations still need a running Hub.

## Minimal SaaS path for full Hub QA

1. Obtain **Hub URL**, **API key** (UI → user badge), and **project** from your Giskard tenant (dev/staging or production).
2. Set `GISKARD_HUB_BASE_URL`, `GISKARD_HUB_API_KEY`; run `hub.projects.list()` or Hub MCP `list_projects`.
3. Implement the agent wrapper per hub-agent-setup (including tool mocks for triggered agents when needed); expose **`https://`** endpoint (`AGENT_WRAPPER_API_KEY`); tunnel with `cloudflared` if the agent is local.
4. `hub.agents.create` + `hub.agents.test_connection`; then run evaluations and scans in the UI or SDK.

For a dedicated on-prem VM, request the **local-install tarball** or Helm chart from Giskard rather than inferring images from the legacy `giskardai/giskard` container.
