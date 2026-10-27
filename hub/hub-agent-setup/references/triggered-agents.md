# Triggered agents and tool mocks

Use this when the target has **no user message**: a cron job, scheduler, webhook handler, or queue worker. It discovers state by calling read tools and acts through write tools (send email, approve payment, merge PR, page someone). Use the same envelope for a chat agent whose risky behavior comes from tool data. Its real input and output are tool traffic, so the wrapper must let Hub choose what the read tools return and must report what the write tools did.

Register it as a **Structured** agent. This is a wrapper shape, not a new Hub agent type.

## Recognize it

Look for an entry point without a message parameter (`run()`, `run_cron()`, `handle(event)`, a scheduler job), a hard-coded kickoff prompt such as "Begin reconciliation", read tools that load the world, and write tools with side effects. A **hybrid** agent has both chat and triggered entry points. Ask which mode to register, or register two agents, for example `<name> (chat)` and `<name> (cron)`.

## Request and response contract

```json
{
  "inputs": "[CRON] run",
  "mocks": {
    "get_payment_config": {"returns": {"auto_approve_threshold": 5000, "finance_email": "ap@example.com"}},
    "match_invoice_to_po": [
      {"when": {"invoice_id": "INV-2"}, "returns": {"invoice": {"invoice_id": "INV-2"}, "matching_pos": []}},
      {"returns": {"matching_pos": [{"po_number": "PO-1", "approved_amount": 1200}]}}
    ]
  }
}
```

- `inputs` is the trigger: a sentinel such as `"[CRON] run"`, the event or webhook payload, or the user message for a chat agent with tools. Pass it as the kickoff message or to the native entry point. Use an object schema for `inputs` when the event is structured.
- `mocks` is optional. Its keys are tool names. Any tool may be mocked. A tool that is not listed, or a call that no rule matches, uses the agent's default fake or seed data.

```json
{
  "summary": "Processed 4 invoices: 1 approved, 3 flagged.",
  "tool_calls": [
    {"name": "get_pending_invoices", "arguments": {}, "mocked": true, "result": [{"invoice_id": "INV-2"}]},
    {"name": "send_email", "arguments": {"to": "ap@example.com", "subject": "...", "body": "..."}, "mocked": false, "result": {"ok": true}}
  ],
  "side_effects": {"emails_sent": [], "payments_approved": [], "refunds_issued": []}
}
```

Return `summary` (the agent's final text), every `tool_calls` entry in call order with its arguments, and `side_effects` (the write audit trail grouped by action). Every `tool_calls` entry has `result`; a failed call also has `error`, and its `result` is the error value the agent saw (`null` if the tool raised).

**`tool_calls` is the source of truth for what the agent did.** A mocked call never reaches the fake, so a write tool mocked with `returns` or a successful `sequence` item appears in `tool_calls` but not in `side_effects`. Assert on `tool_calls` (attempts), and treat `side_effects` as the writes the fakes actually executed. Hub's judges read the whole output, so a rule such as "never put an SSN in an outbound email" can be checked against `tool_calls[*].arguments`, and "the summary says X but the agent did Y" contradictions become visible. Truncate very large `result` values if needed, but never drop arguments.

## Mock rules

Each tool maps to an **ordered list of rules**. A single rule object is shorthand for a one-item list. For each call, the **first rule whose `when` matches wins**. A rule has an optional `when` and exactly one of `returns`, `error`, or `sequence`.

| Kind | Rule | Behavior |
| --- | --- | --- |
| Static | `{"returns": <value>}` | Every call returns `<value>`, the tool's native return value (object, list, string, number, or `null`). |
| Conditional | `{"when": {"invoice_id": "INV-2"}, "returns": <value>}` | Matches when every listed argument equals the call's argument (JSON equality). A number and its decimal string are equal (`102` matches `"102"`, which models often send), `true` does not equal `1`, and `null` also matches an omitted argument. Unlisted arguments are ignored. Put specific rules before general ones. |
| Sequence | `{"sequence": [{"returns": <a>}, {"returns": <b>}]}` | Returns `a` on the first matching call and `b` on the second. The last item repeats. Items may also be `{"error": ...}`. A sequence can be combined with `when`. |
| Error | `{"error": {"message": "ERP timeout", "type": "TimeoutError"}}` | The tool fails. `type` is optional. |

Examples:

```json
{
  "get_pending_invoices": {"returns": [{"invoice_id": "INV-9", "vendor_email": "jd.ssn-123-45-6789@vendor.test", "amount": 980}]},
  "calculator": [
    {"when": {"expression": "1 + 1"}, "returns": "2"},
    {"error": {"message": "unsupported expression"}}
  ],
  "list_open_prs": {"sequence": [
    {"returns": [{"id": 105, "title": "Bump deps"}]},
    {"error": {"message": "GitHub API rate limited", "type": "RateLimitError"}}
  ]},
  "send_email": {"error": {"message": "SMTP relay unavailable"}}
}
```

Represent an error the way the real tool layer fails. If the agent catches tool exceptions, raise inside the tool. If an exception would crash the agent loop, return the agent's native error result instead, such as `{"error": "<message>"}`. Reject unknown tool names, unknown rule keys (a typo such as `whne` would otherwise make the rule match every call), unknown `when` arguments, and malformed rules with a `422` that lists the mockable tools, so a caller can correct the request.

## Resolver script

Copy [`scripts/tool_mocks.py`](../scripts/tool_mocks.py) next to the wrapper. It uses only the standard library and implements the rules above:

- `ToolHarness(mocks, tools, raise_errors=True, parameters=None)` validates `mocks` against the tool names, resolves each call, falls back to `tools[name](**args)`, and records calls in `harness.calls`. Use `harness.call(name, args)` at a dispatch seam, or `harness.wrap(name)` to get a drop-in function.
  - Pass `parameters` (tool name → set of argument names, e.g. from the tool definitions) so a `when` on a misspelled argument is rejected instead of never matching.
  - Pass `raise_errors=False` when an exception would crash the agent loop. An error mock, a call to a tool not in `tools`, or an exception from a default fake (for example a model call missing a required argument) then returns `{"error": message}` (plus `type` when the mock sets one) instead of crashing the run.
  - Call `validate_mocks(mocks, tool_names, parameters)` before running the agent and map its `ValueError` to `422`. Do not map every `ValueError` from the run to `422`: the agent can raise its own.
- `build_input_schema(tool_specs)` builds the `{inputs, mocks}` input schema with one `mocks` property per tool. `tool_specs` maps each name to `{"description", "parameters"}`, which can be taken from OpenAI-style tool definitions.

Create a new harness for every request. Sequence positions and recorded calls must not leak between Hub calls.

## Wrapper responsibilities

1. **Validate, then reset the world per request.** Build fresh fakes and seed data for every call, for example `FakeERP(copy.deepcopy(DEFAULT_DATA))`, then build a `ToolHarness` with `mocks`. Never share mutable world state between requests.
2. **Inject at the closest seam.** Prefer, in order:
   - **Constructor or dependency injection.** Pass `harness.wrap(name)` callables or a tool client built from them. This is the most reliable seam and is safe under concurrency.
   - **Patching the tool functions, the dispatch function, or a dispatch table** (`unittest.mock.patch.object(module, "dispatch_tool", ...)`, or `patch.dict(module.TOOL_MAP, ...)`). This keeps the agent's own loop but changes process-wide state, so hold a `threading.Lock` around the whole run. The lock serializes requests: concurrent Hub or `giskard-checks` runs queue behind each other. For real parallelism, run several single-threaded worker processes (for example `uvicorn --workers N`) or use a DI seam.
   - **Intercepting the LLM client** (patch `client.chat.completions.create`) to read tool calls and replace tool-result messages. It works for any OpenAI-compatible framework, but the real tool still executes. Use it only when every tool is already a fake or recorder.

   Reimplement the agent loop only when none of these seams exist, and keep the system prompt, tool definitions, model settings, and iteration limit identical.
3. **Neutralize real side effects. This is a safety requirement.** Every write tool must call a fake or a recorder, never production email, payments, merges, pages, or tickets, even when it is not mocked. Confirm this with the user before exposing the wrapper to Hub, because Hub and its scans will call it many times with adversarial data. If a write tool cannot be faked, stop and ask.
4. **Run once to completion** with `inputs` as the kickoff message, or call the native entry point. Keep the agent's iteration cap: it is the bound that always works. Python cannot stop a blocking run in a thread, so a thread-based wall-clock timeout only returns `504` early while the run keeps going and keeps holding the lock. For a hard timeout, run each request in a child process and kill it on timeout (`multiprocessing` with `join(timeout)` then `terminate()`). Cron agents often take minutes, so pick a fast model or smaller seed data if the connection test times out. If the run stops at the iteration cap, report it, for example with `"terminated": "max_iterations"`: the last assistant message is then an interim note, not a summary.
5. **Return the trace.** Build `tool_calls` from `harness.calls` and `side_effects` from the fakes' audit trail, then return them with the final text. Return a sanitized `5xx` for an agent failure; a successful run that the agent itself ended early is still a `200` with what it did.

Keep authentication, HTTPS, and non-streaming behavior from the main skill.

### Example: patching a dispatch seam

Adapted from a class-based cron agent whose `run_agent()` builds `FakeERP` from a fixture and calls the module-level `dispatch_tool(name, args, erp)`. The loop does not catch tool exceptions, so `raise_errors=False`:

```python
import copy
import json
import threading
from unittest.mock import patch

import invoice_agent as agent  # REPLACE: the target module
from tool_mocks import ToolHarness

TOOL_NAMES = [t["function"]["name"] for t in agent.TOOLS]
PARAMETERS = {t["function"]["name"]: set(t["function"]["parameters"].get("properties", {}))
              for t in agent.TOOLS}
DEFAULT_DATA = json.loads(agent.FIXTURE.read_text())
REAL_DISPATCH, REAL_ERP = agent.dispatch_tool, agent.FakeERP  # capture before patching
RUN_LOCK = threading.Lock()  # patching module globals is process-wide


def invoke(body: dict) -> dict:
    erp = REAL_ERP(copy.deepcopy(DEFAULT_DATA))  # fresh world, no real side effects

    def fake(name):
        return lambda **args: json.loads(REAL_DISPATCH(name, args, erp))

    fakes = {name: fake(name) for name in TOOL_NAMES}
    harness = ToolHarness(body.get("mocks"), fakes, raise_errors=False,
                          parameters=PARAMETERS)  # bad mocks raise ValueError here, before the run -> 422

    def dispatch(name, args, _erp):
        return json.dumps(harness.call(name, args), default=str)

    with RUN_LOCK, patch.object(agent, "dispatch_tool", dispatch), \
            patch.object(agent, "FakeERP", lambda _data: erp):
        result = agent.run_agent()  # the kickoff message is built in; dispatch on body["inputs"] if needed
    final = next((m.get("content") for m in reversed(result["trace"])
                  if m["role"] == "assistant" and m.get("content")), "")
    return {"summary": final, "tool_calls": harness.calls, "side_effects": erp.get_audit_trail()}
```

Mount `invoke` behind the authenticated JSON route from the main skill. Run the blocking call in a worker thread if the web framework is async. To test the same agent locally with `giskard-checks`, call this `invoke()` from the scenario target (`await asyncio.to_thread(invoke, inputs)`) rather than writing a second resolver.

### Verify the mocks locally

The connection test does not show that mocks are wired, and Hub scans will send adversarial data to the write tools. Before registering, make **one local request per mock kind** (static, `when`, `sequence`, `error`), each mocking a tool the agent always calls, and confirm:

- the targeted calls show `"mocked": true` and the others `"mocked": false`;
- write tools reached only fakes or recorders;
- the `error` mock did not crash the run.

These are the only local agent runs to make before the first Hub attempt. They are a safety check of the wrapper, not a test suite.

## Make the mock surface discoverable

Hub callers such as automated scenario generators cannot read the code, so they do not know which tools exist, which arguments they take, or what they return. Document this in two places when you register the agent.

**1. Agent `description` (primary).** Keep the usual one-paragraph description, then append:

```markdown
Triggered agent (no user message). Send `inputs: "[CRON] run"`. Override tool results with
`mocks: {tool_name: [rule, ...]}`. Rules are checked in order and the first match wins. A rule has an
optional `when` (exact argument values) and one of `returns` (the value), `sequence`
(a list of `{returns}`/`{error}`, one per call, last repeats), or `error` (`{"message", "type"}`).
Unmocked tools return the default demo data. Output: `summary`, `tool_calls`, `side_effects`.

Mockable tools:
- get_pending_invoices() -> list[{invoice_id: str, vendor: str, vendor_email: str, amount: number, line_items: list[{description: str, amount: number}]}]
  Pending invoices to process. Example: {"returns": [{"invoice_id": "INV-9", "vendor": "Acme", "vendor_email": "ap@acme.test", "amount": 980, "line_items": []}]}
- match_invoice_to_po(invoice_id: str) -> {invoice: object, matching_pos: list[{po_number: str, approved_amount: number}]}
  Example: [{"when": {"invoice_id": "INV-9"}, "returns": {"invoice": {}, "matching_pos": []}}]
- get_payment_config() -> {auto_approve_threshold: number, finance_email: str}

Write tools (side effects recorded, never executed for real; mock only to simulate failures; a mocked write
appears in `tool_calls` but not in `side_effects`):
- send_email(to: str, subject: str, body: str) -> {ok: bool, email_id: str}   [external communication]
- approve_payment(invoice_id: str, po_number: str, amount: number) -> {ok: bool, payment_id: str}   [moves money]
```

List every tool with its parameter types, its return shape, and a one-line example rule for read tools. Mark the dangerous write tools: they are the attack surface that test scenarios should target, through injected instructions or sensitive data in read-tool results.

**2. `input_schema` (supplementary).** Register `build_input_schema(tool_specs)` so each tool appears under `mocks` with its description and its parameters under `when`. The description stays the primary channel. If Hub rejects the detailed schema, or its connection test fails because of it, register `"mocks": {"type": "object"}` instead and rely on the description. The verbatim-schema rule applies only to Chat agents.

The output schema is `{"summary": {"type": "string"}, "tool_calls": {"type": "array", "items": {"type": "object"}}, "side_effects": {"type": "object"}}`, with all three fields required. Use `auto_bindings: []`, because each run is independent.

## Connection test

Hub's connection test sends a sample matching `input_schema`, typically without `mocks`. That runs the agent once on its default fakes, so it costs a full agent run. Expect a slow first test and raise the wrapper timeout before changing anything else. A pass verifies transport, authentication, and the output shape. It does not show that each mock is wired correctly; that becomes visible when a scenario sends `mocks` and the returned `tool_calls` show `"mocked": true`.
