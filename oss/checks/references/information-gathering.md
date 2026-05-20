# Information gathering (before generating code)

Do NOT emit generic evals from a one-line description. Ask only for what you don't already have; be specific about *why* you need it.

## Required for all skills

1. **Agent description** — What does the agent do? Domain, audience, typical tasks.
2. **Agent interface** — Callable signature and return shape. Minimum: `agent(inputs: str) -> str`. Prefer structured returns when tools are used.

Do not proceed until items 1–2 are known (or a clearly marked placeholder stub is provided for item 2).

## Required for scenario-generator (adversarial)

3. **Agent boundaries** — What must the agent NOT do?
4. **Fears / risks** — Top failure modes or abuse vectors (hallucination, injection, leakage, etc.)

Do not proceed until items 1–3 are known for red-teaming work.

## RAG evaluator addendum

### Required

Same as universal required (agent description + interface).

### Optional but valuable

| Input | Why |
|-------|-----|
| Knowledge base (docs, chunks, topic) | Synthetic Q&A, grounding anchor |
| Retriever callable | Retrieval-quality eval separate from generation |
| Golden Q&A set | Direct eval; skip synthesis |
| Retrieved context in output | Dynamic `Groundedness` via `context_key` |
| Tool trace fields (`sources`, `context`, `tool_calls`) | Tool-usage `FnCheck`s |

**Always plan retrieval `FnCheck`s** for in-domain factual questions unless the user opts out.

Example questions:

- "What's the function I should call — plain string or dict with sources?"
- "Do you have a KB I can sample from, or a curated Q&A set?"
- "Is the retriever exposed separately for recall@k eval?"
- "Does output include retrieval trace fields for tool-usage checks?"

## Text-to-SQL evaluator addendum

### Required

1. Agent description (database/domain)
2. Agent interface (prefer `{"answer", "queries"}`)
3. **Database access model** — Read-only? Engine? Case-sensitive identifiers?

### Optional but valuable

| Input | Why |
|-------|-----|
| Schema / DDL | Schema-aware questions, SQL patterns |
| SQL guardrails | Blocked keywords, LIMIT policy |
| Golden Q&A | Gold `FnCheck`s on known metrics |
| Tool trace exposure | `queries[]` in output |
| User personas | `UserSimulator` for multi-turn realism |

**Always propose personas** with the user — see [`iterative-eval-loop.md`](./iterative-eval-loop.md). Do not default to static-only without confirming.

Example questions:

- "Does it return a dict with `answer` and `queries`?"
- "What happens on DELETE requests — blocked at validator or agent?"
- "Who uses this agent — execs, analysts, support? Do they follow up with 'what does active mean?' or 'excluding test users?'"
- "Can you share 2–3 real (redacted) question threads, or should I propose personas from schema + common failure modes?"
- "For revenue, does leadership expect completed orders only unless they say otherwise?"

Before implementing personas, present **2–4 scenario proposals** (conversation sketch + check mix) and ask which to build.

## Scenario-generator addendum

Focus on **boundaries and fears**, not gold metrics.

Example questions:

- "What function should I call? I need the signature."
- "What are the boundaries your agent must respect?"
- "What are your top 3 fears about failure or abuse?"

If only a system prompt is provided, extract description and boundaries from it; ask for the callable.

## See also

- [`error-analysis.md`](./error-analysis.md) — review traces before expanding suites
- Per-skill `references/scenario-directions.md` — which test directions apply
