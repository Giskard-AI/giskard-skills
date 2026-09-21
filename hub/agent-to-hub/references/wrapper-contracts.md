# Wrapper contracts

Read when implementing the adapter and choosing its schemas. The authoritative wire formats are in [Hub agent setup](https://docs.giskard.ai/hub/ui/setup/agents); the wrapper must implement the schemas submitted during registration.

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

Do not return a bare string, an OpenAI-style `choices` envelope, or native stream events. Adapt those native formats inside the wrapper. These schemas cover a text-chat wrapper; expand fields deliberately if the actual contract needs them:

```python
CHAT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "messages": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["role", "content"],
            },
        },
        "metadata": {"type": "object"},
    },
    "required": ["messages"],
}

CHAT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "const": "assistant"},
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

`target` is the destination field path; `source` and `outputs_path` are JSONPaths into the previous output. Use paths present in the real schemas. Do not substitute guessed fields such as `input_path` or `output_path`.

For history aggregation, Hub combines earlier inputs and the selected assistant outputs with the next input. The wrapper consumes that resulting history once. For forwarding, make the state field optional in the input schema because the first request has no state. Create a fresh conversation on that first call and return its identifier in the declared output field on every successful turn. Add typed state properties to both schemas. Use only the current turn with a forwarded session unless the native API explicitly also requires history; enable both binding modes only in that case.

## Collecting a native stream

Use the target SDK's final-result helper if one exists. Otherwise implement a collector for its actual event format:

1. Authenticate and validate before opening the upstream request. Request non-streaming operation if supported.
2. Consume the entire iterator or async iterator. For remote SSE/NDJSON, parse complete protocol events across network-buffer boundaries; a socket chunk is not necessarily a message.
3. Accumulate answer **deltas in order**. For cumulative snapshots, replace the previous snapshot instead of concatenating it. Handle tool/status events separately from the answer. Never append both deltas and a final full-text event, which would duplicate the answer.
4. Require the native protocol's successful terminal state. A documented normal iterator exhaustion may be completion; a broken connection or missing required completion marker is a failure. A tool-call finish event is not necessarily the end of an agent run.
5. For Structured output, assemble all fragments before parsing and validating the final JSON object. Preserve any final session identifier or other declared metadata.
6. On success, build the Hub response in memory and send it once using the framework's normal JSON response API. On timeout or error, cancel/close the upstream request and send a sanitized failure. Do not send a success status or flush body bytes while generation is in progress.

Set byte and duration limits; do not collect an unbounded stream. Test delta streams, cumulative snapshots if used by this target, and final events so the adapter cannot silently truncate or duplicate an answer. HTTP transport framing alone does not determine streaming: the required behavior is one complete JSON document emitted only after generation finishes.
