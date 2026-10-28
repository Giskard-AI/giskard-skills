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

## Multi-turn check

The connection test sends one request. For a multi-turn target, also check that two requests continue one conversation on the target's side. With `interactions`, `generate_completion` makes Hub build the request from the registered bindings, as in an evaluation or scan. Pass only the new turn in `input`. Hub adds the earlier context.

```python
import secrets


def check_multi_turn(hub, agent_id, make_input, read_reply):
    word = f"blue-{secrets.token_hex(3)}"
    first = make_input(f"Please remember the code word {word}. Reply with OK.")
    ask = make_input("What is the code word I gave you?")
    r1 = hub.agents.generate_completion(agent_id, input=first)
    r2 = hub.agents.generate_completion(agent_id, input=ask, interactions=[(first, r1.output)])
    r3 = hub.agents.generate_completion(agent_id, input=ask)  # A new conversation.
    for r in (r1, r2, r3):
        if r.error:
            raise RuntimeError(r.error)
    knows = [word.lower() in read_reply(r.output).lower() for r in (r2, r3)]
    return {"continued": knows[0], "isolated": not knows[1], "outputs": [r1.output, r2.output, r3.output]}
```

For Chat, use `make_input = lambda text: {"messages": [{"role": "user", "content": text}]}` and `read_reply = lambda out: out["response"]["content"]`. For Structured, use the target's input and answer fields. With MCP, call `generate_agent_completion` with the same `input` and `interactions` arguments.

The check passes when turn 2 uses the code word and the new conversation does not. If the wrapper returns a target conversation ID, it must be the same in turns 1 and 2 and different in the new conversation. If the target refuses unrelated requests, change `word` and the two messages to a fact the target accepts, such as the user's name, and read the outputs yourself. When the outputs are unclear, look at the wrapper or target logs to see what the target received.

| Result | Likely cause | Fix |
| --- | --- | --- |
| Turn 2 does not know the fact, and the target received only the newest message | `[]` bindings, or the wrapper drops earlier `messages` | Use the aggregate binding and convert the whole list |
| Turn 2 does not know the fact, and the target conversation ID changed | The target stores the history, but each request starts a new conversation | Use the forward binding. Return the ID in `metadata` and read it from the next request |
| Turn 2 has no forwarded ID | `source` or `target` does not match the wrapper's output or input path | Correct the paths |
| The target receives earlier turns twice | The wrapper replays Hub's history into a stored conversation | Send only the newest message |
| The new conversation knows the fact | The wrapper or target shares state between conversations | Key state by the forwarded ID, and start a new conversation when the ID is absent |
| Turn 2 refuses or ignores the fact, but the target received it in the same conversation | Model behavior, not the wiring | Keep the bindings and use a different fact |

Fix the wrapper or the bindings of the same agent, for example `hub.agents.update(agent_id, auto_bindings=[...])` (MCP: `update_agent`). A partial update keeps the other fields. Then run the check again.

## Without Python: Hub MCP

If the environment has no Python 3.10+, use the Giskard Hub MCP server instead of the SDK. If the coding assistant has no Hub MCP tools yet, add the server to its MCP configuration. `GISKARD_HUB_BASE_URL` includes the scheme, for example `https://hub.example.com`:

```json
{
  "mcpServers": {
    "Giskard Hub": {
      "url": "${GISKARD_HUB_BASE_URL}/_api/mcp/",
      "headers": {
        "X-API-Key": "${GISKARD_HUB_API_KEY}"
      }
    }
  }
}
```

Adapt the file location, server type field, and environment-variable syntax to the client. Reference the variables, and make sure the client starts with them set. Never write the literal Hub key into a tracked file. Some clients load new servers only after a reload or restart, so ask the user to do this when the tools do not appear. Set up MCP in step 1, before you start the wrapper or a tunnel, because a restart can stop running processes.

The tools take the same arguments as the SDK methods, except `headers`:

| SDK | MCP tool |
| --- | --- |
| `hub.projects.list()` / `hub.projects.retrieve(project_id)` | `list_projects` / `retrieve_project` |
| `hub.agents.create` / `hub.agents.update` | `create_agent` / `update_agent` |
| `hub.agents.test_connection` | `test_agent_connection` |
| `hub.agents.generate_completion` | `generate_agent_completion` |
| `hub.agents.list(project_id=...)` | `list_agents` |

MCP `headers` is a list of name/value pairs: `[{"name": "X-API-Key", "value": "<wrapper key>"}]`. The wrapper key is a tool argument, so it is visible in the session. Do not repeat it in replies to the user. The rules below apply to MCP results too.

## Interpret and retry

Inspect `result` before reporting success. SDK versions may return a dictionary or a model; identify the actual success/response and execution-error fields. **The connection-test result is not necessarily the wrapper's raw output:** do not blindly validate its whole envelope against `output_schema` or assume an unfamiliar shape means the endpoint failed. Inspect the installed SDK's contract if needed. An empty or unrecognized result is not proof of success either.

On failure, surface the relevant error with secrets redacted, fix that specific issue, and re-test the saved agent ID. Do not hide every failure behind a generic "invalid body" message. After an ambiguous create timeout, reconcile with `hub.agents.list(project_id=...)` before creating again. `test_connection` needs `url` and `project_id` even with `agent_id`; it accepts `input_schema`, not `output_schema`.

A local DNS failure for the tunnel URL need not block registration: the SDK calls Hub, which calls the wrapper from its own network. Attempt the Hub test before adding DNS workarounds or more client-side probes.

Apart from the multi-turn check, use `hub.agents.generate_completion(agent_id, input=...)` only for a requested playground check or to investigate a specific response or context issue. Inspect its `error` and `output`.
