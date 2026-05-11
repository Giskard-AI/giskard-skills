# Synthetic Q&A Generation from a Knowledge Base

When the user provides a KB but no curated test set, generate synthetic questions yourself. Bad synthetic Q&A = bad eval, so this matters. The patterns below come from the same lineage as `RAGET` (Giskard v2's RAG eval test set generator).

## Goals

A good synthetic Q&A set:
1. **Has known answers**: every question is anchored to specific KB chunks, so groundedness can be evaluated
2. **Covers question diversity**: not just simple factuals; includes multi-hop, paraphrases, and out-of-scope
3. **Reflects real user intent**: phrased the way a user actually would, not the way the source document phrases things
4. **Is verifiable**: you can show the user the source chunks each question came from

## Output schema

Generate test cases in this shape so they plug directly into the canonical code structure:

```python
@dataclass
class TestCase:
    question: str
    question_type: Literal["factual", "multi_hop", "paraphrase", "out_of_scope"]
    context: list[str]              # KB chunks the question is grounded in (empty for out_of_scope)
    reference_answer: str | None    # optional, for SemanticSimilarity / LLMJudge against gold
    source_chunk_ids: list[str]     # IDs/paths of chunks the question was generated from (for provenance)
    in_scope: bool                  # True for factual/multi_hop/paraphrase, False for out_of_scope
```

## Generation prompts

Use these prompts as templates with `giskard.agents.Generator`. Each prompt is run with KB chunks as context (or, for out-of-scope, with the agent description).

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

**Generate 2× and trim**. Synthetic data is cheap. Generate twice as many questions as the user asked for, then have the user (or you) trim shallow / duplicate / poorly-grounded ones.

**Show source chunks in the output**. Every generated question must come with the chunk IDs it was generated from. This lets the user sanity-check the grounding without re-reading the entire KB.

**Don't paraphrase the source verbatim**. If the chunk says "The Eiffel Tower was completed in 1889", don't generate "When was the Eiffel Tower completed?", which just tests the agent's ability to copy-paste. Better: "How old is the Eiffel Tower?" requires the agent to compute, ground, and respond appropriately.

**Mix question types in roughly this ratio** for a balanced 20-question test set:
- 8 simple factual
- 4 multi-hop
- 4 paraphrases (of selected factuals)
- 4 out-of-scope (mix of unrelated, adjacent, post-cutoff)

**Avoid leakage**. Don't generate the question and the gold answer using the same model run that wrote the chunk. Generate question and answer separately, with the chunk as context for both.

**Verify multi-hop genuinely needs hops**. Re-read each multi-hop question: can it be answered from a single chunk? If yes, it's not multi-hop. Discard.

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

## When NOT to generate synthetically

If the user has any of:
- A curated golden test set
- Real production logs with user questions (even unlabelled)
- A list of known FAQs

Use those instead. Real user questions beat synthetic ones for realism. Synthetic Q&A is the fallback when nothing else is available.

If the user has *some* real questions but not enough, mix: real questions for relevance/refusal coverage, synthetic for groundedness anchoring (because synthetic questions come with known source chunks, which makes groundedness auto-anchorable).
