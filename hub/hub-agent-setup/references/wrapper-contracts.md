# Wrapper contracts

Use the relevant schema and binding example while building the minimal adapter. The [Hub contract](https://docs.giskard.ai/hub/ui/setup/agents) describes JSON bodies transported over the wrapper's public HTTPS endpoint.

## Chat

Hub sends a message list, including earlier turns when history bindings are enabled:

```json
{
  "messages": [
    {"role": "user", "content": "Remember my preferred color: teal."},
    {"role": "assistant", "content": "I will remember teal."},
    {"role": "user", "content": "Which color did I choose?"}
  ]
}
```

Return one assistant message under `response`, with optional JSON metadata:

```json
{
  "response": {"role": "assistant", "content": "You chose teal."},
  "metadata": {"request_id": "example-request"}
}
```

Adapt native strings, `choices` envelopes, and stream events inside the wrapper. **Register these canonical Chat schemas verbatim.** Hub versions that detect Chat by exact schema equality treat added titles, constraints, or properties as Structured; their connection probe can then send `role: "test"` and trigger HTTP 422. Keep Pydantic-generated schemas and stricter role/history validation inside the wrapper, separate from the published schemas:

```python
CHAT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "messages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["role", "content"],
            },
        },
    },
    "required": ["messages"],
}

CHAT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {
            "type": "object",
            "properties": {
                "role": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["role", "content"],
        },
        "metadata": {"type": "object"},
    },
    "required": ["response"],
}
```

Map the complete incoming message list into the target's native history representation. If the target owns a thread instead, extract the current turn and its thread ID as described in [Multi-turn targets](#multi-turn-targets), avoiding replay of messages the target already stored. Preserve the target's own system configuration.

## Structured

Use explicit custom JSON Schemas for both bodies. Hub sends the input object directly and expects the declared output object directly; a Chat `messages`/`response` envelope is unnecessary. For example, a ticket classifier could implement:

```python
STRUCTURED_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"ticket": {"type": "string"}},
    "required": ["ticket"],
}

STRUCTURED_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "queue": {"type": "string", "enum": ["billing", "technical", "other"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["queue", "confidence"],
}
```

Example request: `{"ticket": "My invoice was charged twice."}`. Example response: `{"queue": "billing", "confidence": 0.95}`. Replace these example fields with the target's actual interface. Preserve structured types; do not JSON-encode an object into a string or invent a chat interface that changes the target's behavior.

For an agent with no user message (cron, webhook, or queue worker), or one whose risky inputs arrive through tool results, use the `{"trigger", "mocks"}` envelope in [triggered-agents.md](triggered-agents.md).

## Multi-turn targets

Hub keeps each conversation and builds every request from the agent's `auto_bindings`, shown as **Interaction Context** in the Hub UI. Choose the bindings from where the target keeps history between turns, not from the Hub default. Pass them explicitly to `hub.agents.create`. The [SDK reference](https://docs.giskard.ai/hub/sdk/reference#agent-types) defines two binding modes:

| Where the target keeps history | `auto_bindings` | What the wrapper sends to the target |
| --- | --- | --- |
| The caller resends it on each call, in any format | `[{"mode": "aggregate", "target": "messages", "outputs_path": "$.response"}]` | All Hub `messages`, converted to the native history format |
| The target stores it under a session, thread, or conversation ID | `[{"mode": "forward", "target": "metadata.thread_id", "source": "$.metadata.thread_id"}]` | Only the newest user message, with the forwarded ID |
| A Structured target stores it under a declared `session_id` | `[{"mode": "forward", "target": "session_id", "source": "$.session_id"}]` | The current input, with the forwarded ID |
| Nowhere, because each call is independent | `[]` | The current input |

`target` is the destination field path. `source` and `outputs_path` are JSONPaths into the previous output. Use paths the wrapper actually accepts and returns. Do not substitute guessed fields such as `input_path` or `output_path`.

**History sent by the caller (aggregate).** Hub sends the whole conversation in `messages`, with the newest user message last. Convert it to the target's native history inside the wrapper. For example, pass the last message as `question` and the earlier ones as `chat_history`, rename `assistant` to `ai` or `model`, group turns into pairs, or join them into one transcript string. Keep every earlier turn, in order. If the wrapper sends only `messages[-1]`, each request starts a new conversation. When the target keeps history in an in-process object, such as a memory or chat-session object, prefer to rebuild that object from `messages` on each call. This keeps the wrapper stateless.

**State stored by the target (forward).** Without an aggregate binding, Hub sends only the new turn in `messages`. Hub sends no ID on the first turn. Start a new native conversation, for example with the target's create-session call, and return its ID in `metadata.thread_id`. On later turns, read the forwarded ID, send only the newest user message, and return the ID again. If the target issues a new ID on each turn, such as a previous-response ID, return the newest one. Do not use the aggregate binding for this kind of target, and do not replay Hub's history into it. A new session for each request loses the conversation, and a replay into the stored session repeats turns. Chat wrappers can accept optional `metadata.thread_id` without changing the canonical schemas. Structured schemas should declare optional input state and returned output state.

**Isolation.** Hub runs many conversations at the same time. Keep conversation state in the target or keyed by the forwarded ID. Never keep one global session, thread, or history list in the wrapper.

Combine an aggregate and a forward binding only when the target needs both the history and an ID. Step 4 of the skill verifies the choice with the [two-turn check](hub-sdk.md#multi-turn-check).

## Tool calls

The tool calls of an agent are its main attack surface. A judge that sees only the final answer cannot see an unsafe tool argument, or an injected instruction that came back in a tool result. When the wrapper can read the tool calls of a run, return them so that Hub can check them.

If the target output already includes its tool calls, return them in the shape below. Otherwise, get the user's approval first (step 1 of the skill), because Hub then receives tool arguments and results that the target does not expose by default. Ask only when the code of the target is in the workspace and you can get the calls with a small change. When the wrapper reaches the target only through an endpoint that does not return its tool calls, Hub cannot see them. Do not change or redeploy a remote target only for this. In step 5, tell the user which change in the target would expose them.

For Chat, return the calls in `metadata.tool_calls`. The canonical schemas do not change, because `metadata` is a free object. For Structured, declare an optional `tool_calls` array (and `agent_messages` for a [multi-agent target](#multi-agent-targets)) in the output schema. A triggered agent already returns `tool_calls`. Reporting the calls does not change the tool results. To let Hub also choose the tool results, use the mocks envelope in [triggered-agents.md](triggered-agents.md).

```json
{
  "response": {"role": "assistant", "content": "I cannot refund this order right now. A colleague will contact you."},
  "metadata": {
    "tool_calls": [
      {"name": "get_order", "arguments": {"order_id": "A-1001"}, "result": {"status": "delivered", "total": 34.9}},
      {"name": "issue_refund", "arguments": {"order_id": "A-1001", "amount": 34.9}, "result": null, "error": "payment gateway unavailable"}
    ]
  }
}
```

List the calls in call order. Each entry has `name`, `arguments` as a JSON object, and `result`, which is the value that the agent received. A failed call also has `error`, and its `result` is the error value that the agent saw, or `null` if the tool raised. This is the same shape as the `tool_calls` of a triggered agent.

Get the calls from the closest source:

1. **The run result.** Most frameworks already return the calls, for example the message list of an OpenAI-style loop, LangGraph `result["messages"]`, OpenAI Agents SDK `result.new_items`, LangChain `AgentExecutor(return_intermediate_steps=True)`, or Pydantic AI `result.new_messages()`. Pair each call with its result by the tool-call ID. Parse arguments that arrive as a JSON string.
2. **A framework callback or hook**, such as LangChain callbacks or OpenAI Agents SDK run hooks.
3. **A recorder at the tool seam.** `ToolHarness(None, tools)` from [`scripts/tool_mocks.py`](../scripts/tool_mocks.py) runs the real tools and records each call in `harness.calls`. Use the seams and lock rules in [triggered-agents.md](triggered-agents.md#wrapper-responsibilities).

Return only the calls of the current request. A target that stores the conversation can return the messages of earlier turns too, so keep only the messages that this request added. Truncate a very large `result` if necessary, but never drop a call or its arguments. Remove credentials, such as API keys or tokens, from arguments and results. Do not add system prompts or raw model requests. They are fixed configuration, not behavior, and a judge that reads the whole output can report them as a leak.

### Multi-agent targets

When the target is the entry point of several agents, the exchanges between the agents are attack surface too. An injection can pass from one agent to the next, and a handoff can give an attacker an agent with more powerful tools. Return the whole run, not only the steps of the entry agent:

- Add `agent`, the name of the agent that made the call, to each `tool_calls` entry. Include the calls that sub-agents make.
- Keep handoffs and delegations as entries. Most frameworks implement them as tool calls, such as `transfer_to_refunds` or an agent used as a tool. For a delegation, `arguments` is what the caller sent and `result` is what the sub-agent returned.
- Return the other messages that agents produce but the user does not see in `metadata.agent_messages`, in order. Examples are the reply of an agent before it hands off, and the final reply of a sub-agent. When an agent is used as a tool, its reply is already the `result` of that call, so do not repeat it.

```json
"metadata": {
  "tool_calls": [
    {"agent": "supervisor", "name": "transfer_to_refunds", "arguments": {}, "result": "Successfully transferred to refunds"},
    {"agent": "refunds", "name": "issue_refund", "arguments": {"order_id": "A-1002", "amount": 249}, "result": {"ok": true}}
  ],
  "agent_messages": [{"agent": "refunds", "content": "Refund R-1 issued for A-1002."}]
}
```

The result of the entry agent often hides the inner steps. LangGraph Supervisor keeps only the last message of each sub-agent by default (`output_mode="last_message"`). In the OpenAI Agents SDK, `result.new_items` names the `agent` of each item and includes handoff items, but not the nested run of an `agent.as_tool()` call. Do not change how the agents share context to expose these steps, because that changes the system under test. Collect them from the event stream or callbacks of the framework instead, for example LangGraph `graph.stream(..., subgraphs=True)` or the `on_stream` callback of `as_tool()`. If a sub-agent runs in another service that does not return its steps, record only the request and the reply of that call.

### Make the calls discoverable

Add two sentences to the agent `description`, for example: "Each response lists the agent's tool calls in `metadata.tool_calls`, with their arguments, results, and errors. Point checks on tool use at the whole output, and name the field in the rule, for example "In tool_calls, there is no issue_refund call above 500."" For a multi-agent target, also say that each call names its `agent`, and that hidden messages between agents are in `metadata.agent_messages`. Hub users and scenario generators cannot read the code. A judge that reads only the answer text cannot see the calls, and passes a scenario in which the agent made an unsafe call. A rule that does not name the field can pass too, because the judge can treat it as unrelated to the answer.

**Verify.** After the connection test passes, call `hub.agents.generate_completion(agent_id, input=...)` (MCP: `generate_agent_completion`) once, with a request that makes the target call a tool. For a multi-agent target, make the request reach a sub-agent. Make sure that the output lists the calls with their arguments, results, and agents. An empty list usually means that the wrapper reads the wrong messages. Calls of the entry agent only usually mean that the inner steps are hidden, as described above.

## Collecting a native stream

Prefer a non-streaming call or the target SDK's final-result helper. Otherwise consume the iterator through successful completion. Concatenate text deltas in order; replace cumulative snapshots rather than concatenating them. Keep tool/status events out of the answer, and do not append a final full-text event to already collected deltas. If the wrapper returns tool calls, build them from the tool events.

For remote SSE/NDJSON, parse complete events across network-buffer boundaries. For Structured output, assemble the fragments before parsing the final object. Preserve the final session ID and declared metadata. A disconnect or missing required completion marker is a failure, not a completed answer.

Return a normal JSON response only after completion. Bound collection by size and time; close the upstream stream on failure and return a sanitized error. Use the first Hub connection test to identify problems; add collector-specific tests only to investigate a failure or satisfy an explicit requirement.
