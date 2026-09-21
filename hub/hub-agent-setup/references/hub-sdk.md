# Hub SDK registration

Use Python 3.10+ and `giskard-hub` in the existing environment or a small virtual environment. Sources: [SDK setup](https://docs.giskard.ai/hub/sdk), [agent guide](https://docs.giskard.ai/hub/sdk/guides/agents-and-knowledge-bases), and [API reference](https://docs.giskard.ai/hub/sdk/reference).

Resolve the user's project and check Hub credentials early with `HubClient` and `hub.projects.list()` or `hub.projects.retrieve(project_id)`. Once the adapter and HTTPS ingress are running, register and test immediately. No separate public reachability script, config file, or test harness is required.

## Minimal example

Build `config` from the user's project and implemented adapter: `project_id`, `name`, `description`, HTTPS `url`, actual `supported_languages`, `input_schema`, `output_schema`, and `auto_bindings`. Keep credentials outside this dictionary. Reuse the returned or previously saved agent ID for subsequent attempts; verify any user-supplied ID belongs to the selected project.

```python
import os
from urllib.parse import urlsplit

from giskard_hub import HubClient


def register_and_test(config, agent_id=None):
    url = urlsplit(config["url"])
    if url.scheme != "https" or not url.hostname:
        raise ValueError("Hub requires a complete HTTPS endpoint URL")
    wrapper_key = os.environ["AGENT_WRAPPER_API_KEY"]
    if not wrapper_key:
        raise ValueError("AGENT_WRAPPER_API_KEY must not be empty")

    params = dict(config)
    project_id = params.pop("project_id")
    params["headers"] = {"X-API-Key": wrapper_key}
    with HubClient(
        base_url=os.environ["GISKARD_HUB_BASE_URL"],
        api_key=os.environ["GISKARD_HUB_API_KEY"],
        max_retries=0,
    ) as hub:
        if agent_id:
            agent = hub.agents.update(agent_id, **params)
        else:
            agent = hub.agents.create(project_id=project_id, **params)
        # Retain this ID even if the following call fails.
        print(f"Hub agent ID: {agent.id}")
        result = hub.agents.test_connection(
            agent_id=agent.id,
            url=params["url"],
            project_id=project_id,
            headers=params["headers"],
            input_schema=params["input_schema"],
        )
        return agent.id, result
```

The Hub key authenticates `HubClient`; only the wrapper key goes in the agent's `headers`. Do not print entire agent objects, which contain credentials.

## Interpret and retry

Inspect `result` before reporting success. SDK versions may return a dictionary or a model; identify the actual success/response and execution-error fields. **The connection-test result is not necessarily the wrapper's raw output:** do not blindly validate its whole envelope against `output_schema` or assume an unfamiliar shape means the endpoint failed. Inspect the installed SDK's contract if needed. An empty or unrecognized result is not proof of success either.

On failure, surface the relevant error with secrets redacted, fix that specific issue, and re-test the saved agent ID. Do not hide every failure behind a generic "invalid body" message. After an ambiguous create timeout, reconcile with `hub.agents.list(project_id=...)` before creating again. `test_connection` needs `url` and `project_id` even with `agent_id`; it accepts `input_schema`, not `output_schema`.

A local DNS failure for the tunnel URL need not block registration: the SDK calls Hub, which calls the wrapper from its own network. Attempt the Hub test before adding DNS workarounds or more client-side probes.

Use `hub.agents.generate_completion(agent_id, input=...)` only for a requested playground check or to investigate a specific response/context issue. Inspect its `error` and `output`. For multi-turn diagnosis, send only the new input plus prior `(input, output)` pairs in `interactions`; do not also duplicate history in the new input.
