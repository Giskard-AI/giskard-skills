# Agent description

Write a detailed `description` that covers the agent's flows, tools, and rules. The full description is part of the registration, not extra documentation.

Take each fact from the target, such as the system prompt, tool definitions, guardrails, routing, UI code that calls tools (buttons, cards), knowledge-base setup, and README. Do not invent features or rules that the target does not have. Leave out secrets, internal hostnames, and keys.

Write plain text in this structure:

```text
<Name> is the <role> of <product or company>, run by <operator> for <users> in <market or region>. Users reach it through <channel>.
It <does each task or flow, step by step: what it asks for, reads, decides, and returns>.
It answers from <a knowledge base, documents, APIs, uploaded files, or the model's general knowledge>.
<How the operator benefits from user actions, which can bias answers.>
<Whether users sign in, and what each user or role can see or change.>
It handles <the personal, financial, health, or confidential data, by field>.
It cannot <actions out of its reach, such as buy, sign, approve, or change records>.

Tools:
- <tool_name>: <what it does>. <Data it reads or writes>. <Read-only, or its side effect>. <Who calls it: the model, a UI button, or a scheduler>.

The agent must always: <required steps, such as consent, a disclaimer, a confirmation before a write, or a handoff to a human>.
The agent must never: <forbidden actions, advice, claims, data requests, disclosures, topics, and instructions to ignore>.
For an off-topic or forbidden request, it <refuses, redirects, or hands off>.
Users write in <languages>. Answers are <plain text, Markdown, cards, or buttons>.
```

Be specific. Name the data fields, limits, and parties, for example "IBAN and date of birth", not "personal data", and "refunds above 500 EUR", not "large refunds". For a triggered agent, the [Mockable tools](triggered-agents.md#make-the-mock-surface-discoverable) section replaces the Tools list. If the wrapper returns tool calls, add the [tool-call sentences](wrapper-contracts.md#make-the-calls-discoverable) at the end.

All sources and lines are optional. Skip a source that you cannot access. Leave out a line when you cannot find its facts or it does not apply to the target.
