# Agent Discovery: Call Before You Build

Before generating scenarios or checks, you need **background on what the agent does, what it can access, and what it must refuse**. Users often give a vague description ("our support bot") without domain boundaries, tools, or output shape.

**When that background has not been provided, call the agent first** — do not invent evals from assumptions.

## When to discover by calling

| Missing from the user | Discover by asking the agent |
|------------------------|------------------------------|
| Domain / purpose | "What kinds of questions can you help with?" |
| Tools and capabilities | "What tools, APIs, or functions can you call?" |
| Out-of-scope behavior | "What topics or tasks are outside your scope?" |
| Safety boundaries | "What are you not allowed to do or say?" |
| Refusal style | "What do you do when you don't know the answer?" |
| Output shape | Run a sample question; inspect answer + any metadata (sources, tool traces) |

If the user **has** already supplied a system prompt, product spec, or structured answers to the required checklist, use that — discovery calls are redundant.

## How to run discovery

1. **Get a callable** — even a thin wrapper around an API is enough (`def agent(inputs: str) -> str`).
2. **Send 3–6 discovery turns** — one topic per message; keep them neutral (not adversarial yet).
3. **Summarize back to the user** — confirm your understanding before writing the suite.
4. **Fill the skill checklist** — map discovery answers to required fields (description, interface, boundaries, fears / eval dimensions).

Example discovery prompts (adapt to the agent type):

```
What is your role and what can you help me with?
What tools or external systems do you have access to?
What topics or requests should you refuse or redirect?
How do you handle questions when you don't have enough information?
Can you walk me through how you would answer a typical user question?
```

For RAG agents, also ask: "Do you cite sources? Where do your answers come from?"

For tool-using agents, also ask: "List the actions you can perform" and run one in-domain request to see trace shape.

## What discovery is not

- **Not red-teaming** — save adversarial probes for the scenario suite.
- **Not a substitute for labels** — retrieval gold doc IDs and curated Q&A still come from the user or KB.
- **Not optional when the user is a black box** — if they only expose `chat(message)`, discovery is often the *only* way to learn scope before meaningful evals.

## After discovery

Use what you learned to:

- Pick eval dimensions (`rag-eval-dimensions.md`) or fear categories (`attack-patterns.md`)
- Choose checks per [`check-selection.md`](./check-selection.md)
- Wire `target=` with the confirmed function signature and output keys

Then follow the eval iteration loop — [`eval-iteration-loop.md`](./eval-iteration-loop.md).
