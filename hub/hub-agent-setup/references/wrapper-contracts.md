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

Map the complete incoming message list into the target's native history representation. If the target owns a thread instead, extract the current turn and its thread ID as described below, avoiding replay of messages the target already stored. Preserve the target's own system configuration.

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

## Multi-turn bindings

Pass `auto_bindings` explicitly to `hub.agents.create`. The [SDK reference](https://docs.giskard.ai/hub/sdk/reference#agent-types) defines two binding modes:

| Target behavior | `auto_bindings` |
| --- | --- |
| Stateless chat, needs full conversation | `[{"mode": "aggregate", "target": "messages", "outputs_path": "$.response"}]` |
| Owns a thread, accepts `metadata.thread_id` | `[{"mode": "forward", "target": "metadata.thread_id", "source": "$.metadata.thread_id"}]` |
| Structured target accepts a `session_id` | `[{"mode": "forward", "target": "session_id", "source": "$.session_id"}]` |
| Independent calls with no conversation state | `[]` |

`target` is the destination field path; `source` and `outputs_path` are JSONPaths into the previous output. Use paths the wrapper actually accepts and returns. Do not substitute guessed fields such as `input_path` or `output_path`.

For history aggregation, the wrapper consumes Hub's combined history once. For forwarding, accept an absent state field on the first call, create a fresh conversation, and return its identifier on each successful turn. Chat wrappers can accept optional `metadata.thread_id` without changing the canonical schemas; Structured schemas should declare optional input state and returned output state. Use only the current turn with a forwarded session unless the native API also requires history.

## Collecting a native stream

Prefer a non-streaming call or the target SDK's final-result helper. Otherwise consume the iterator through successful completion. Concatenate text deltas in order; replace cumulative snapshots rather than concatenating them. Keep tool/status events out of the answer, and do not append a final full-text event to already collected deltas.

For remote SSE/NDJSON, parse complete events across network-buffer boundaries. For Structured output, assemble the fragments before parsing the final object. Preserve the final session ID and declared metadata. A disconnect or missing required completion marker is a failure, not a completed answer.

Return a normal JSON response only after completion. Bound collection by size and time; close the upstream stream on failure and return a sanitized error. Use the first Hub connection test to identify problems; add collector-specific tests only to investigate a failure or satisfy an explicit requirement.
