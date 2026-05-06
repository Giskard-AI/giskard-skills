# Worked Examples

Complete, runnable examples for each common RAG eval setup. Pick the example that matches what the user has, then adapt to their specifics.

All examples:
- Use `from giskard.checks import ...`
- Wrap scenarios in a `Suite`
- Pass the agent as `target` at run time
- Configure the LLM judge globally with `set_default_generator(...)`

---

## Example 1: Black-Box Agent (no KB, no retriever, no Q&A)

**Setup**: User has a callable agent and an agent description, but no documents to ground against.

**Coverage**: Answer relevance, behavioral conformity, refusal quality, paraphrase consistency. No groundedness; be transparent about this.

```python
import asyncio
from pathlib import Path
from giskard.checks import (
    Scenario, Suite, AnswerRelevance, Conformity, SemanticSimilarity,
    StringMatching, FnCheck, set_default_generator,
)
from giskard.agents.generators import Generator

set_default_generator(Generator(model="openai/gpt-4o-mini"))

# REPLACE: Wire up your actual agent
def your_rag_agent(inputs: str) -> str:
    """Your Q&A agent. Replace this stub."""
    raise NotImplementedError("Replace with your agent")

DOMAIN = "An internal HR assistant that answers employee questions about company benefits, leave policies, and onboarding."

# In-domain question
in_scope = (
    Scenario("vacation_policy")
    .interact(inputs="How many vacation days do I get as a new hire?")
    .check(AnswerRelevance(name="addresses_vacation", context=DOMAIN))
    .check(FnCheck(name="non_empty", fn=lambda trace: len(str(trace.last.outputs).strip()) > 20))
)

# Out-of-domain question
out_of_scope = (
    Scenario("unrelated_topic")
    .interact(inputs="What's the weather in Paris today?")
    .check(Conformity(
        name="declines_unrelated",
        rule="The assistant only answers HR questions. For unrelated topics it must decline politely and not invent an answer.",
    ))
)

# Behavioral check: must not give legal advice
no_legal = (
    Scenario("no_legal_advice")
    .interact(inputs="Can my manager fire me without cause? Is that legal?")
    .check(Conformity(
        name="no_legal_advice",
        rule="The assistant must not provide legal interpretations or advice. It should redirect to HR or legal counsel.",
    ))
)

# Paraphrase consistency (same factual, three phrasings)
paraphrase = (
    Scenario("paraphrase_consistency")
    .interact(inputs="How do I request parental leave?")
    .interact(inputs="Where can I apply for paternity leave?")
    .interact(inputs="leave for new parents, process?")
    .check(SemanticSimilarity(
        name="answers_consistent",
        reference_key="trace.interactions[0].outputs",  # compare turn 1 to turn 0
        text_key="trace.interactions[1].outputs",
        threshold=0.7,
    ))
)

suite = Suite(name="rag_eval_blackbox")
for s in [in_scope, out_of_scope, no_legal, paraphrase]:
    suite.append(s)

async def main():
    result = await suite.run(target=your_rag_agent)
    result.print_report()
    Path("rag_results.json").write_text(result.model_dump_json(indent=2))
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

**What's missing here**: groundedness. Tell the user this is the single biggest eval gap and ask if they can share even a few sample chunks.

---

## Example 2: Agent + KB (synthetic Q&A + groundedness)

**Setup**: User has the agent and a KB. Groundedness is anchored to the KB chunks the synthetic question was generated from.

```python
import asyncio
from pathlib import Path
from giskard.checks import (
    Scenario, Suite, Groundedness, AnswerRelevance, Conformity,
    AnyOf, set_default_generator,
)
from giskard.agents.generators import Generator

set_default_generator(Generator(model="openai/gpt-4o-mini"))

def your_rag_agent(inputs: str) -> str:
    """Your RAG agent. Replace this stub."""
    raise NotImplementedError("Replace with your agent")

DOMAIN = "An assistant that answers questions about our SaaS product's features and pricing."

# REPLACE: Synthetic test set generated from KB chunks. See references/synthetic-qa-generation.md.
TEST_CASES = [
    {
        "question": "How many users are included in the Pro plan?",
        "type": "factual",
        "context": [
            "The Pro plan includes 10 user seats. Additional seats can be purchased at $15/user/month.",
            "All plans include unlimited projects and 24/7 support.",
        ],
        "in_scope": True,
    },
    {
        "question": "What is the price difference between Pro and Enterprise per user, and which is cheaper for a 50-person team?",
        "type": "multi_hop",
        "context": [
            "The Pro plan is $50/month for the first 10 seats, $15/user/month thereafter.",
            "The Enterprise plan is $1500/month flat for up to 100 users.",
        ],
        "in_scope": True,
    },
    {
        "question": "Does the product integrate with SAP S/4HANA?",  # NOT covered by KB
        "type": "out_of_scope",
        "context": [],
        "in_scope": False,
    },
]

scenarios = []
for i, tc in enumerate(TEST_CASES):
    base = Scenario(f"{tc['type']}_{i}").interact(inputs=tc["question"])
    if tc["in_scope"]:
        scenario = (
            base
            .check(Groundedness(
                name="grounded_in_kb",
                context=tc["context"],
            ))
            .check(AnswerRelevance(name="addresses_question", context=DOMAIN))
        )
    else:
        scenario = base.check(Conformity(
            name="declines_when_unsupported",
            rule="When the answer is not in the agent's knowledge base, the agent must explicitly decline or say it does not know. Confident-but-unsupported answers fail this check.",
        ))
    scenarios.append(scenario)

suite = Suite(name="rag_eval_with_kb")
for s in scenarios:
    suite.append(s)

async def main():
    result = await suite.run(target=your_rag_agent)
    result.print_report()
    Path("rag_results.json").write_text(result.model_dump_json(indent=2))
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Example 3: Agent + Exposed Retriever (retrieval quality eval)

**Setup**: User exposes both the end-to-end agent AND the retriever as separate functions. Adds retrieval quality eval (precision/recall@k).

```python
import asyncio
from pathlib import Path
from giskard.checks import (
    Scenario, Suite, Groundedness, AnswerRelevance,
    FnCheck, GreaterEquals, set_default_generator,
)
from giskard.agents.generators import Generator

set_default_generator(Generator(model="openai/gpt-4o-mini"))

def your_rag_agent(inputs: str) -> dict:
    """Your RAG agent. Returns {"answer": str, "retrieved_ids": list[str]} so we can eval retrieval."""
    raise NotImplementedError("Replace with your agent")

# REPLACE: Test set with relevance labels (which doc IDs *should* be retrieved)
TEST_CASES = [
    {
        "question": "What is the refund policy?",
        "context": ["Full refunds within 30 days; partial after that..."],
        "relevant_doc_ids": ["policy/refunds-v3"],
        "k": 5,
    },
    # ...
]

def recall_at_k(relevant: list[str], retrieved: list[str], k: int) -> float:
    if not relevant:
        return 1.0
    top_k = retrieved[:k]
    return sum(1 for r in relevant if r in top_k) / len(relevant)

def make_retrieval_check(tc: dict):
    def fn(trace) -> bool:
        retrieved = trace.last.outputs.get("retrieved_ids", [])
        return recall_at_k(tc["relevant_doc_ids"], retrieved, tc["k"]) >= 0.8
    return FnCheck(name=f"recall@{tc['k']}>=0.8", fn=fn)

scenarios = []
for i, tc in enumerate(TEST_CASES):
    scenario = (
        Scenario(f"rag_with_retrieval_{i}")
        .interact(inputs=tc["question"])
        .check(make_retrieval_check(tc))  # retrieval quality
        .check(Groundedness(                # generation quality
            name="grounded",
            context=tc["context"],
            answer_key="trace.last.outputs.answer",
        ))
        .check(AnswerRelevance(
            name="relevant",
            answer_key="trace.last.outputs.answer",
        ))
    )
    scenarios.append(scenario)

suite = Suite(name="rag_eval_full")
for s in scenarios:
    suite.append(s)

async def main():
    result = await suite.run(target=your_rag_agent)
    result.print_report()
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

Note: `Groundedness` and `AnswerRelevance` use `answer_key="trace.last.outputs.answer"` because the agent returns a dict. Without this, they'd try to evaluate the whole dict as the answer.

---

## Example 4: Agent + Curated Q&A (gold-answer comparison)

**Setup**: User has a curated test set with reference answers. Use `SemanticSimilarity` and `LLMJudge` for direct comparison; no synthesis needed.

```python
import asyncio
import json
from pathlib import Path
from giskard.checks import (
    Scenario, Suite, SemanticSimilarity, LLMJudge, AnswerRelevance,
    set_default_generator,
)
from giskard.agents.generators import Generator

set_default_generator(Generator(model="openai/gpt-4o-mini"))

def your_rag_agent(inputs: str) -> str:
    raise NotImplementedError("Replace with your agent")

# REPLACE: Load your golden Q&A
TEST_CASES = json.loads(Path("golden_qa.json").read_text())
# Expected shape: [{"question": str, "reference_answer": str}, ...]

scenarios = []
for i, tc in enumerate(TEST_CASES):
    scenario = (
        Scenario(f"qa_{i}")
        .interact(inputs=tc["question"])
        .check(SemanticSimilarity(
            name="similar_to_gold",
            reference=tc["reference_answer"],
            text_key="trace.last.outputs",
            threshold=0.8,
        ))
        .check(LLMJudge(
            name="factually_matches_gold",
            prompt=f"""Compare the agent's answer to the gold answer. Pass if they convey the same factual information, even if worded differently. Fail if the agent's answer omits key facts, adds incorrect facts, or contradicts the gold.

Question: {{{{ trace.last.inputs }}}}
Agent answer: {{{{ trace.last.outputs }}}}
Gold answer: {tc["reference_answer"]}

Return passed=true if the agent's answer is factually equivalent to the gold; passed=false otherwise.""",
        ))
        .check(AnswerRelevance(name="relevant"))
    )
    scenarios.append(scenario)

suite = Suite(name="rag_eval_against_gold")
for s in scenarios:
    suite.append(s)

async def main():
    result = await suite.run(target=your_rag_agent)
    result.print_report()
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Example 5: Multi-Turn RAG (follow-up questions)

**Setup**: User wants to test conversational RAG where follow-ups depend on prior turns.

```python
import asyncio
from giskard.checks import (
    Scenario, Suite, Groundedness, AnswerRelevance, Conformity,
    set_default_generator,
)
from giskard.agents.generators import Generator

set_default_generator(Generator(model="openai/gpt-4o-mini"))

async def your_rag_agent(inputs: str, trace) -> str:
    """Multi-turn RAG agent. Receives the full trace to maintain conversation state."""
    raise NotImplementedError("Replace with your agent")

POLICY_CHUNKS = [
    "All employees accrue 20 days of paid vacation per year, prorated by start date.",
    "New hires can take up to 5 days in the first 3 months; remaining days unlock at 90 days tenure.",
    "Vacation must be requested at least 2 weeks in advance via the HR portal.",
]

multi_turn = (
    Scenario("vacation_followups")
    .interact(inputs="How many vacation days do I get?")
    .check(Groundedness(name="grounded_1", context=POLICY_CHUNKS))
    .check(AnswerRelevance(name="relevant_1"))
    .interact(inputs="And what if I'm a new hire?")
    .check(Groundedness(name="grounded_2", context=POLICY_CHUNKS))
    .check(AnswerRelevance(name="relevant_2"))
    .interact(inputs="How do I request them?")
    .check(Groundedness(name="grounded_3", context=POLICY_CHUNKS))
    .check(AnswerRelevance(name="relevant_3"))
)

# Test that the agent maintains context across turns; references "them" should resolve to vacation days
context_carry = (
    Scenario("context_carry")
    .interact(inputs="What's the parental leave policy?")
    .interact(inputs="Is it paid?")  # "it" must resolve to parental leave
    .check(AnswerRelevance(
        name="resolves_pronoun",
        context="The user is asking a follow-up about parental leave.",
    ))
)

suite = Suite(name="rag_multi_turn")
suite.append(multi_turn)
suite.append(context_carry)

async def main():
    result = await suite.run(target=your_rag_agent)
    result.print_report()
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Notebook output (instead of script)

If the user is in a Jupyter notebook, package the same code into cells. Recommended cell layout:

**Cell 1 (Setup)**:
```python
from giskard.checks import (
    Scenario, Suite, Groundedness, AnswerRelevance, Conformity,
    set_default_generator,
)
from giskard.agents.generators import Generator

set_default_generator(Generator(model="openai/gpt-4o-mini"))
```

**Cell 2 (SUT, often already exists in the notebook)**:
```python
# REPLACE: Wire to your existing agent. If the agent is already defined above, you can skip this cell.
def your_rag_agent(inputs: str) -> str:
    return existing_agent.query(inputs)
```

**Cell 3 (Test data)**: defining `TEST_CASES`

**Cell 4 (Scenarios + Suite)**: building the suite

**Cell 5 (Run, notebook idiom; no `asyncio.run()`)**:
```python
result = await suite.run(target=your_rag_agent)
result.print_report()
result  # rich pretty-print
```

In notebooks, the cell's last expression is auto-displayed, so just put `result` at the end. Don't write to JSON unless the user asks; that's a script idiom.
