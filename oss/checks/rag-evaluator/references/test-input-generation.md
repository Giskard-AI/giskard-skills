# Test input generation (RAG)

> Shared workflow (dimensions → tuples → questions, static vs personas): [`../../references/test-input-generation-core.md`](../../references/test-input-generation-core.md)

When the user provides a KB but no curated test set, generate synthetic questions yourself. Bad synthetic Q&A = bad eval. Patterns below follow the same lineage as `RAGET` (Giskard v2's RAG eval test set generator).

## Goals

A good synthetic Q&A set:

1. **Has known answers** — every question anchored to specific KB chunks for groundedness evals
2. **Covers diversity** — factual, multi-hop, paraphrase, out-of-scope
3. **Reflects real user intent** — phrased as users ask, not as documents read
4. **Is verifiable** — source chunk IDs per question

Map tuples from the core workflow to RAG directions in [`scenario-directions.md`](./scenario-directions.md) (e.g. `in_scope=false` → out-of-scope tuple).

## Output schema

```python
@dataclass
class TestCase:
    question: str
    question_type: Literal["factual", "multi_hop", "paraphrase", "out_of_scope"]
    context: list[str]              # KB chunks (empty for out_of_scope)
    reference_answer: str | None
    source_chunk_ids: list[str]
    in_scope: bool
```

## Generation prompts

Use with `giskard.agents.Generator`. Run with KB chunks as context (out-of-scope: agent description + topic list).

### 1. Simple Factual

```jinja
You are generating evaluation questions for a Q&A system over the following knowledge base chunks.

Generate {{ n }} simple factual questions that:
- Can be answered directly from a single chunk below
- Have a clear, verifiable answer (a fact, name, date, number, definition)
- Are phrased the way a real user would ask, not the way the document phrases things
- Avoid yes/no questions. Prefer "what", "when", "who", "how much"

For each question, return:
- question: the user's question
- reference_answer: a short ground-truth answer
- source_chunk_id: which chunk it came from

Knowledge base chunks:
{% for chunk in chunks %}
[{{ chunk.id }}] {{ chunk.text }}
{% endfor %}
```

### 2. Multi-Hop

```jinja
You are generating multi-hop evaluation questions: questions that require combining information from MULTIPLE chunks.

Generate {{ n }} questions that:
- Genuinely require facts from 2 or more of the chunks below to answer
- Are NOT trivially decomposable (avoid "What is X? And what is Y?", which is two single-hops)
- Force the model to *connect* facts: comparisons, causes, sequences, dependencies
- Avoid questions where one chunk is sufficient

For each question, return:
- question
- reference_answer (synthesizing across chunks)
- source_chunk_ids (the IDs of all chunks needed)
- reasoning: a short note on what connection is required

Knowledge base chunks:
{% for chunk in chunks %}
[{{ chunk.id }}] {{ chunk.text }}
{% endfor %}
```

### 3. Paraphrase

```jinja
Rephrase each of the following questions in {{ n }} different ways:
- Vary formality (formal/casual)
- Vary length (terse / verbose)
- Vary phrasing (different verbs, different question words)
- Keep the meaning identical

The reference_answer and source_chunk_ids stay the same as the original.

Original questions:
{% for q in questions %}
- {{ q.question }} (answer: {{ q.reference_answer }})
{% endfor %}
```

### 4. Out-of-Scope

```jinja
You are generating out-of-scope questions for a Q&A system. The system is described as:

"{{ agent_description }}"

It has access only to the following knowledge base topics:
{% for topic in kb_topics %}
- {{ topic }}
{% endfor %}

Generate {{ n }} questions that are intentionally OUTSIDE the system's scope. Mix:
- {{ n // 3 }} questions about a clearly unrelated topic (e.g., weather, sports, current events)
- {{ n // 3 }} questions ADJACENT to the system's domain but not covered (e.g., a related product, a sibling topic)
- {{ n - 2 * (n // 3) }} questions that look in-domain but require post-cutoff or future information

The system should DECLINE to answer these. There is no reference_answer; the gold behavior is refusal.

For each, return:
- question
- expected_behavior: "decline" / "express uncertainty"
- adjacency: "unrelated" / "adjacent" / "post-cutoff"
```

## Tips for high-quality generation

- **Generate 2× and trim** — discard shallow or poorly grounded questions
- **Show source chunks** — every question needs chunk IDs for sanity checks
- **Don't paraphrase the source verbatim** — prefer questions that require grounding + reasoning
- **Mix types** (~20 questions): 8 factual, 4 multi-hop, 4 paraphrases, 4 out-of-scope
- **Verify multi-hop** — discard if one chunk suffices

## Example: full generation flow

```python
import asyncio
from giskard.agents import Generator

generator = Generator(model="openai/gpt-4o-mini")

async def generate_factual(chunks: list[dict], n: int = 8):
    prompt = (
        generator
        .template("rag_eval/factual_qa.j2")
        .with_inputs(chunks=chunks, n=n)
    )
    chat = await prompt.with_output(FactualQASet).run()
    return chat.output.questions

async def generate_test_set(kb_chunks: list[dict], agent_description: str):
    factual = await generate_factual(kb_chunks, n=8)
    multi_hop = await generate_multi_hop(kb_chunks, n=4)
    paraphrases = await generate_paraphrases(factual[:4], n=1)
    out_of_scope = await generate_out_of_scope(agent_description, kb_topics=[...], n=4)
    return factual + multi_hop + paraphrases + out_of_scope
```

## Personas for the same coverage

For phrasing variance and follow-ups on generated topics, attach [`simulate-users.md`](./simulate-users.md) archetypes — do not duplicate tuple planning here.

## See also

- [`../../references/test-input-generation-core.md`](../../references/test-input-generation-core.md)
- [`scenario-directions.md`](./scenario-directions.md)
- [`eval-dimensions.md`](./eval-dimensions.md)
