# Hub registration and verification

Read after implementing the wrapper. Sources: [SDK setup](https://docs.giskard.ai/hub/sdk), [agent operations](https://docs.giskard.ai/hub/sdk/guides/agents-and-knowledge-bases), and [API reference](https://docs.giskard.ai/hub/sdk/reference). Check installed signatures if documentation and the package differ; use current `input=` and JSON Schemas rather than legacy agent integration APIs.

## Prepare the configuration

Use Python 3.10+ in the project's environment or a dedicated virtual environment. Install `giskard-hub`; the validation example also uses `jsonschema`:

```sh
python -m pip install giskard-hub jsonschema
```

The Hub URL and API key belong in `HubClient(base_url=..., api_key=...)`, commonly read from `GISKARD_HUB_BASE_URL` and `GISKARD_HUB_API_KEY`. The **wrapper** key belongs in the agent's `headers={"X-API-Key": ...}` so Hub sends it to the wrapper. Never put the Hub key in those headers or forward the incoming wrapper key to the native target.

Resolve the user's chosen project using `hub.projects.retrieve(project_id)` or `hub.projects.list()` for a name. Record the resolved ID. Gather actual language codes, such as `en` or `fr`, and a description of the agent's purpose, users, and boundaries; these inform Hub's generated tests. Do not infer arbitrary languages from the underlying model's theoretical capabilities.

Create a non-secret `hub-agent.json` containing `project_id`, `name`, `description`, the complete invocation `url`, `supported_languages`, and the exact `input_schema`, `output_schema`, and `auto_bindings` dictionaries/lists from the implemented wrapper. Do not put credentials in this file. The SDK derives the contract from the schemas; do not invent a `mode="chat"` or `mode="structured"` create argument.

## First registration

Adapt this into a runnable registration script in the target project. Run it from the directory containing the completed `hub-agent.json`, after public/remote authentication and response tests pass. Supply `AGENT_WRAPPER_API_KEY` securely to this process as well as to the wrapper.

```python
import json
import os
from pathlib import Path

from giskard_hub import HubClient
from jsonschema import validate

config = json.loads(Path("hub-agent.json").read_text())
id_file = Path("hub-agent-id.txt")
if id_file.exists():
    raise RuntimeError("An agent ID is already saved; resume verification of that agent.")

wrapper_key = os.environ["AGENT_WRAPPER_API_KEY"]
if not wrapper_key:
    raise ValueError("AGENT_WRAPPER_API_KEY must not be empty")
headers = {"X-API-Key": wrapper_key}

hub = HubClient(
    base_url=os.environ["GISKARD_HUB_BASE_URL"],
    api_key=os.environ["GISKARD_HUB_API_KEY"],
    max_retries=0,  # Reconcile an ambiguous create failure before retrying.
)

try:
    agent = hub.agents.create(
        project_id=config["project_id"],
        name=config["name"],
        description=config["description"],
        url=config["url"],
        headers=headers,
        supported_languages=config["supported_languages"],
        input_schema=config["input_schema"],
        output_schema=config["output_schema"],
        auto_bindings=config["auto_bindings"],
    )
    id_file.write_text(agent.id + "\n")

    result = hub.agents.test_connection(
        agent_id=agent.id,
        url=config["url"],
        project_id=config["project_id"],
        headers=headers,
        input_schema=config["input_schema"],
    )
    # SDK versions may return a raw dict or an AgentOutput model.
    payload = result if isinstance(result, dict) else result.model_dump(exclude_none=True)
    if payload.get("error") is not None:
        raise RuntimeError("Hub connection test reported an error; inspect it with secrets redacted.")
    validate(instance=payload, schema=config["output_schema"])
    print(f"Hub connection test passed for agent {agent.id}")
finally:
    hub.close()
```

`test_connection` uses keyword arguments for `url` and `project_id` even when `agent_id` is supplied. It accepts `input_schema` to generate a suitable request; do not pass an unsupported `output_schema` argument. Validate the actual returned output against that schema yourself. The installed SDK may return the raw Structured body, so do not assume `result.response` or a `success` attribute exists. If the installed version uses a documented response envelope, extract its payload before validation; never skip schema validation to conceal a mismatch.

Treat SDK exceptions, non-null execution errors, malformed responses, and schema mismatches as failures. Inspect diagnostic errors without printing credentials or the entire `Agent` object. A failed test after creation leaves the agent registered: retain its ID, repair the integration, and re-run the test for that ID. On an ambiguous create outcome, query `hub.agents.list(project_id=...)` and reconcile before another create.

## Optional playground check

Reopen a `HubClient` with the same credentials and use the saved ID. For Chat, a small check that also exercises Hub's history bindings is:

```python
first_input = {"messages": [{"role": "user", "content": "Remember the word juniper."}]}
first = hub.agents.generate_completion(agent_id, input=first_input)
if first.error is not None:
    raise RuntimeError("First completion failed; inspect the sanitized error.")
validate(instance=first.output, schema=config["output_schema"])

second_input = {"messages": [{"role": "user", "content": "Which word did I ask you to remember?"}]}
second = hub.agents.generate_completion(
    agent_id,
    input=second_input,
    interactions=[(first_input, first.output)],
)
if second.error is not None:
    raise RuntimeError("Second completion failed; inspect the sanitized error.")
validate(instance=second.output, schema=config["output_schema"])
```

Inspect the second response for preserved context; schema validity alone does not establish memory. Choose an in-domain prompt if the target would reject this example. Use only the new turn in `second_input` when supplying prior `interactions`, so aggregate bindings do not duplicate history. For a stateful agent, check that the same thread/session is forwarded and a separate conversation gets a fresh one.

For Structured agents, pass a small valid custom object as `input` and validate `completion.output` against its output schema. Use prior input/output pairs only when the registered bindings support multi-turn behavior. A one-turn playground call is sufficient for independent agents. Do not run scans, evaluations, or a long conversation as part of this connectivity check.

If a tunnel restarts with a different public URL, update the saved agent with `hub.agents.update(agent_id, url=new_url)`, then repeat the authentication checks and `test_connection` with the new URL. Keep the registration and local configuration consistent.
