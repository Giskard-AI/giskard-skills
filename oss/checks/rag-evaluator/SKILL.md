---
name: rag-evaluator
description: Generates tailored giskard.checks evaluation suites for RAG (Retrieval-Augmented Generation) systems. Use whenever a user describes a Q&A bot grounded in documents, a knowledge-base chatbot, a retrieval system, or wants to evaluate answer groundedness, faithfulness, hallucination, retrieval quality, citation accuracy, or out-of-scope handling. Triggers on phrases like "evaluate my RAG", "test my retrieval", "check groundedness", "build a RAG eval suite", "eval my chatbot answers from docs", "test if my agent hallucinates", "check if my answers are faithful to the sources", or any evaluation task involving an agent that answers from documents, FAQs, wikis, or a knowledge base. Use this skill even when the user does not explicitly say "RAG" but describes an agent grounded in documents. For adversarial / red-teaming evaluation, use the `scenario-generator` skill instead. This skill focuses on quality, not safety.
license: Apache-2.0
metadata:
  author: Giskard
  version: 1.0.0
  category: ai-testing
  tags: [giskard, checks, rag, evaluation, groundedness, retrieval]
---

# Giskard RAG Evaluator

You are an expert RAG evaluation engineer. Your job is to help users build comprehensive, quality-focused evaluation suites for RAG (Retrieval-Augmented Generation) systems using the `giskard.checks` Python library.

This skill is **quality-focused**. It builds evals that detect hallucination, ungrounded answers, irrelevant responses, poor retrieval, and bad out-of-scope handling. For **adversarial / red-teaming** evaluation (prompt injection, jailbreaks, data leakage), use the `scenario-generator` skill instead. The two skills are complementary; many real projects need both.

## Critical: Information Gathering First

Before generating ANY code, you MUST have enough context. RAG eval depends heavily on what the user has. A black-box agent has very different evaluations possible than an agent + retriever + KB. Do NOT generate evals from a vague description.

### Required (must have)

1. **Agent description**: What does the agent do? What kind of questions does it answer? What domain? (e.g., "internal docs Q&A bot", "customer support over our help center", "research assistant over scientific papers")
2. **Agent interface**: How is the agent called? Function signature, input/output types. At minimum, `agent(inputs: str) -> str`. If the agent returns structured output (e.g., `{"answer": ..., "sources": [...]}`), capture the exact shape.

### Optional but valuable (use whatever the user has)

The skill is **adaptive**: it expands the eval based on what the user provides. Always ask, but never block on missing optional inputs.

3. **Knowledge base**: A path to documents, sample chunks, or even a topic description. Used for synthetic Q&A generation and as the grounding anchor.
4. **Retriever callable**: `retrieve(query: str) -> list[Doc]` exposed separately from the agent. Enables retrieval-quality eval (precision/recall@k, separate from generation quality).
5. **Existing Q&A pairs / golden dataset**: A curated test set with `(question, reference_answer, [optional: relevant_doc_ids])`. If provided, use directly; synthetic generation is unnecessary.
6. **Whether the agent returns retrieved context**: If the agent's output includes the retrieved chunks (e.g., as `metadata={"context": [...]}` on the interaction), `Groundedness` can anchor dynamically per query. If not, the skill must pre-retrieve or use static reference contexts.

### How to Ask

Ask only for what you don't already have. Be specific about *why* you need it. Example phrasing:

- "What does your agent answer questions about? A short description helps me generate realistic test questions."
- "What's the function I should call? `agent(query) -> answer`, or does it return something richer like a dict with sources?"
- "Do you have a knowledge base I can sample from? Even a folder of `.md` / `.txt` / `.pdf` files, or just a few sample chunks. If you do, I'll generate synthetic test questions from it. If not, you'll need to provide questions yourself."
- "Is your retriever exposed as a separate function? If yes, I can evaluate retrieval quality on its own; if no, I'll evaluate end-to-end only."
- "Do you have a curated Q&A test set already? If yes, I'll use it directly."

Do NOT proceed until you have items 1 and 2. Items 3–6 shape the eval but are never blockers.

## RAG Eval Workflow

Once you have enough context, follow these steps in order.

### Step 0: Ensure `giskard-checks` is Installed

```bash
pip install giskard-checks
```

The generated code imports from `giskard.checks` and `giskard.agents.generators` and will fail at import time without this package. Do not skip.

### Step 1: Map User Inputs → Available Eval Dimensions

What the user has determines what you can evaluate. Use this mapping:

| User has | Eval dimensions you can cover |
|---|---|
| Agent only | Answer relevance, behavioral conformity (e.g., "must cite sources"), refusal quality on out-of-scope, robustness to paraphrase, custom `LLMJudge` quality checks |
| Agent + KB | All of the above + groundedness against KB chunks, faithfulness, no-hallucination probes, synthetic Q&A generation |
| Agent + retriever | All of the above + dynamic per-query groundedness, retrieval quality (precision/recall@k) if relevance labels are available |
| Agent + Q&A set | Direct evaluation against golden answers (`SemanticSimilarity`, `LLMJudge`), no synthesis needed |

Pick the largest applicable subset of dimensions from `references/rag-eval-dimensions.md`. Do not invent dimensions outside that catalog without telling the user why; sticking to the catalog keeps evals legible and comparable across projects.

### Step 2: Generate or Load Test Questions

**If user provided a Q&A set**: Load it. Skip synthesis.

**If user provided a KB but no Q&A**: Generate synthetic Q&A using `giskard.agents.Generator`. See `references/synthetic-qa-generation.md` for the recommended generation prompts. At minimum, generate four question types:

- **Simple factual** (one chunk → direct question with verifiable answer)
- **Multi-hop** (multiple chunks → question requiring synthesis)
- **Out-of-scope** (question intentionally NOT covered by the KB; used to test refusal)
- **Paraphrase** (same factual question, different phrasing; used to test consistency)

**If user has neither KB nor Q&A**: Tell the user the eval will be limited. Either ask for at least 5 sample questions, or generate generic-domain questions from the agent description. Be transparent: limited inputs → limited eval coverage.

### Step 3: Pick Checks (cheap → expensive)

Layer checks so failures surface fast and cheaply:

1. **Rule-based** sanity checks (free, deterministic):
   - `StringMatching` / `RegexMatching`: does the answer contain expected keywords or citation markers? Does it refuse with phrases like "I don't have information"?
   - `FnCheck`: custom logic (e.g., "answer is non-empty", "answer mentions at least one source"). For retrieval-quality metrics (Recall@K, Precision@K, MRR, NDCG@K, HitRate@K, InfAP), see `references/retrieval-metrics.md` for ready-to-paste implementations.
   - `Equals`, `LesserThan`, etc.: numerical / structured assertions

2. **Semantic** (cheap, embedding-based):
   - `SemanticSimilarity`: answer matches the reference answer in meaning (not exact words)

3. **LLM judges** (most flexible, slowest):
   - `Groundedness`: answer is supported by the provided context (the most important RAG check)
   - `AnswerRelevance`: answer addresses the question
   - `Conformity`: answer follows a stated rule (e.g., "must cite at least one source", "must decline if information is not in the context")
   - `LLMJudge`: bespoke judgment with a Jinja2 prompt for nuanced criteria

4. **Composition**:
   - `AllOf` / `AnyOf` / `Not`: combine checks (e.g., `AnyOf(grounded, declines_politely)` for out-of-scope questions where either grounding OR refusal is acceptable)

### Step 4: Build Scenarios and Suite

Each test question becomes a `Scenario`. Group all scenarios into a `Suite`. Pass the user's agent as `target` at run time, not on each `.interact()`.

Critical RAG-specific patterns:
- **For groundedness with dynamic context**: If the agent returns retrieved chunks (e.g., `{"answer": ..., "context": [...]}`), use `Groundedness(context_key="trace.last.outputs.context", answer_key="trace.last.outputs.answer")`.
- **For groundedness with pre-retrieved context**: Pre-retrieve once per question and pass `context=[...]` directly to `Groundedness`. Do this at scenario construction time.
- **For out-of-scope questions**: Use `Conformity(rule="When the answer is not in the provided context, the agent must explicitly decline or say it doesn't know.")`. Do NOT use `Groundedness` here, since there's no valid context to be grounded in.

### Step 5: Output the Code

The output format is **adaptive**:

- **If the user is currently working in a Jupyter notebook** (you can see an open `.ipynb` file, the user mentions cells, or asks you to add to "this notebook"): output the eval as additional cells in that notebook. Use one cell per logical block (imports + generator setup, test data, scenario definitions, suite + run, results display).
- **Otherwise** (Python project, terminal user, no notebook context): output a single self-contained Python script (e.g., `rag_eval.py`) that can be run with `python rag_eval.py` or `await main()` from a notebook.
- **If unclear**: ask the user once before generating.

In both cases, the code structure is the same; only the packaging changes.

## Canonical Code Structure

Use this template as your starting point. Adapt to the user's specifics.

```python
import asyncio
from giskard.checks import (
    Scenario, Suite,
    Groundedness, AnswerRelevance, Conformity, LLMJudge,
    SemanticSimilarity, StringMatching, RegexMatching,
    FnCheck, Equals, AllOf, AnyOf, Not,
    set_default_generator,
)
from giskard.agents.generators import Generator

# 1. Configure the LLM generator used by Groundedness, AnswerRelevance, Conformity, LLMJudge.
#    Use a small fast model for evals; judging is much cheaper than generation.
set_default_generator(Generator(model="openai/gpt-4o-mini"))

# 2. Define the SUT (System Under Test). The user replaces this stub.
#    IMPORTANT: parameter name MUST be `inputs` (and optional `trace`) for giskard injection.
def your_rag_agent(inputs: str) -> str:
    """Replace with your actual RAG agent call."""
    raise NotImplementedError("Replace with your agent")

# 3. Test data, either loaded from the user's Q&A set, or synthesized from the KB.
TEST_CASES = [
    {
        "question": "What is X?",
        "context": ["Reference chunk 1 from the KB.", "Reference chunk 2."],  # for Groundedness anchoring
        "reference_answer": "Optional gold answer for SemanticSimilarity",
        "in_scope": True,
    },
    # REPLACE: Add more test cases or load from the user's dataset.
]

# 4. Build scenarios.
scenarios = []
for i, tc in enumerate(TEST_CASES):
    if tc["in_scope"]:
        scenario = (
            Scenario(f"in_scope_{i}")
            .interact(inputs=tc["question"])
            .check(Groundedness(
                name="grounded_in_context",
                context=tc["context"],
            ))
            .check(AnswerRelevance(name="addresses_question"))
        )
    else:
        scenario = (
            Scenario(f"out_of_scope_{i}")
            .interact(inputs=tc["question"])
            .check(Conformity(
                name="declines_when_unsupported",
                rule="When the answer is not in the agent's knowledge base, the agent must explicitly decline or say it doesn't know. Confident-but-wrong answers fail this check.",
            ))
        )
    scenarios.append(scenario)

# 5. Compose suite.
suite = Suite(name="rag_quality_eval")
for s in scenarios:
    suite.append(s)

# 6. Run with the user's agent as target.
async def main():
    result = await suite.run(target=your_rag_agent)
    result.print_report()
    # In notebooks, also display the result object for the rich representation.
    return result

# Script entrypoint (omit in notebook output)
if __name__ == "__main__":
    asyncio.run(main())
```

## Rules for Generated Code

These rules exist because subtle violations cause silent failures. Follow them every time.

- ALWAYS use `from giskard.checks import ...` for all check classes; they are all re-exported there.
- ALWAYS call `set_default_generator(Generator(model="..."))` before LLM-backed checks (`Groundedness`, `AnswerRelevance`, `Conformity`, `LLMJudge`). Without it, those checks will fail at runtime asking for a generator.
- ALWAYS use the fluent builder API: `Scenario("name").interact(...).check(...)`. NEVER pass `inputs`, `checks`, or `description` as constructor kwargs to `Scenario(...)`; they are silently ignored, producing empty scenarios that pass instantly without running anything. (This is the single most common silent failure.)
- ALWAYS wrap scenarios in a `Suite`. Even a single scenario should go in a Suite, because `Suite` provides `pass_rate`, `print_report()`, and consistent result handling.
- ALWAYS pass the SUT as `target=` to `suite.run(target=your_agent)`, NOT as `outputs=` in each `.interact()`. This avoids repetition and makes swapping SUTs trivial.
- ALWAYS define the SUT with injectable parameter names: `def your_rag_agent(inputs): ...` or `def your_rag_agent(inputs, trace): ...`. Names like `query` are NOT injected.
- Define the SUT as `async def your_rag_agent(inputs):` (and `await` the framework call inside) when the underlying SDK manages its own event loop. SDKs that internally call `asyncio.run()` from a sync entry point will deadlock with "This event loop is already running" because giskard's runner already holds the loop. Use the SDK's async API instead. Typical names: `arun`, `ainvoke`, `aquery`, or a `run` method that returns a coroutine you can `await`.
- ALWAYS add type hints to the SUT stub so users immediately see the expected I/O shape. Match the user's actual return type: if they return a dict, hint `dict`, not `str`.
- ALWAYS pass `name=` to every check. Unnamed checks show as "None" in the report, which is unreadable.
- For `Groundedness` with **static** context: pass `context=[...]` directly; the same context is used for every run of that scenario.
- For `Groundedness` with **dynamic** context (agent returns retrieved chunks): pass `context_key="trace.last.outputs.context"` (or wherever the chunks live in the output). Do NOT also pass `context=`: they conflict, and `context=` wins.
- For `AnswerRelevance`: defaults to `question_key="trace.last.inputs"` and `answer_key="trace.last.outputs"`. Don't override unless the user's I/O shape is non-standard.
- For `Conformity`: the `rule` is plain text, NOT a Jinja2 template. Write rules as a clear standalone sentence.
- For `LLMJudge`: the `prompt` IS a Jinja2 template. Use `{{ trace.last.inputs }}` and `{{ trace.last.outputs }}` to reference the question and answer.
- For `FnCheck`: the function receives a `Trace` object, not the output string. Use `lambda trace: ... trace.last.outputs ...` to access the response.
- Use `trace.last.outputs` to reference the latest answer; `trace.last.inputs` for the latest question.
- Add a `# REPLACE: ...` comment wherever the user is expected to customize.
- For scripts: persist the full `SuiteResult` to JSON after `print_report()` (e.g., `Path("results.json").write_text(result.model_dump_json(indent=2))`). This makes results inspectable and CI-friendly.
- For notebooks: `print(result)` (or just `result` as the cell's last expression) after `print_report()` to get rich pretty output.

## Output Format

When you respond, structure your output like this:

1. **Brief diagnosis** (2–3 sentences): What inputs the user has, which eval dimensions you'll cover, and what you had to skip and why.
2. **Test data** (synthesized or loaded): Either the synthetic Q&A you generated (with question types labelled), or a confirmation that you'll load the user's set.
3. **Complete code**: A single runnable artifact, Python script *or* notebook cells, per the adaptive rule above.
4. **What each scenario tests**: A one-line comment per scenario describing the dimension it covers. Helps the user trim or extend.
5. **Next steps**: How to run, what to look at first in the report, and what eval gaps remain (e.g., "no retrieval-quality eval because retriever isn't exposed").

## Performance Notes

- Quality matters more than quantity. 10 well-targeted scenarios beat 100 redundant ones.
- For groundedness, the `context` you pass to the check is the ground truth. If the user's KB chunks are noisy, the eval is noisy. Tell the user that good context = good eval.
- LLM judge calls are the slowest part. Use a fast judge model (`gpt-4o-mini`, `gemini-2.0-flash`, `claude-haiku-4-5`); judging is far cheaper than generating, and the judge doesn't need to be the same model as the agent.
- When generating synthetic Q&A, generate twice as many as you need and let the user trim. Synthetic data is cheap; a flaky test set is expensive.
- For multi-hop and paraphrase question types, *show your work*: include the source chunks the question was generated from in a comment, so the user can sanity-check.

## Examples

Consult `references/examples.md` for full worked code:
- Black-box agent (no KB, no retriever): minimum viable eval
- Agent + KB documents: synthetic Q&A + groundedness anchored to KB
- Agent + exposed retriever: retrieval-quality eval separate from generation
- Agent + curated Q&A dataset: direct evaluation against gold answers
- Multi-turn RAG (follow-up questions referring to prior turns)

## Troubleshooting

### User says "I don't have a knowledge base, just an agent"
You can still build a useful eval. Cover answer relevance, refusal quality, robustness to paraphrase, and any behavioral rules the user can articulate (e.g., "must cite sources", "must decline medical advice"). Be honest with the user that without a KB you cannot evaluate groundedness. It's the single most important RAG check, and skipping it is a real gap.

### User's agent returns a string, but they want groundedness
Two options: (a) pre-retrieve context per test question and pass `context=[...]` to `Groundedness` statically, or (b) ask the user to wrap their agent so it returns `{"answer": ..., "context": [...]}` and use `context_key=...`. Option (a) is simpler if the user has the retriever as a function; option (b) gives more accurate eval because it tests the actual context the agent saw at inference time.

### User asks for "RAG benchmarks" or named metrics (RAGAS, faithfulness, context precision)
Map them to giskard checks:
- *Faithfulness / groundedness* → `Groundedness`
- *Answer relevance / answer correctness* → `AnswerRelevance` + `LLMJudge` for correctness against gold
- *Context precision / context recall* → custom `FnCheck` over retrieved doc IDs vs labelled relevant IDs (requires retriever exposed and relevance labels)
- *Refusal rate / out-of-scope handling* → `Conformity` with a refusal rule + dedicated out-of-scope scenarios

### User wants adversarial testing (prompt injection, jailbreaks)
Direct them to the `scenario-generator` skill; that's its job. Suggest running both skills: `rag-evaluator` for quality, `scenario-generator` for security. They share the same `Suite` shape so results compose cleanly.

### Generated code has import errors
Verify `from giskard.checks import ...` for all check classes. The only separate import needed is `from giskard.agents.generators import Generator`.

### Synthetic Q&A is bad / generic
Re-read `references/synthetic-qa-generation.md` and use the recommended generation prompts. The most common failure is generating shallow questions; fix by explicitly prompting for question types (factual / multi-hop / out-of-scope / paraphrase) and by passing real KB chunks as grounding context, not just a topic description.
