---
name: rag-evaluator
description: Generates tailored giskard.checks evaluation suites for RAG (Retrieval-Augmented Generation) systems. Use whenever a user describes a Q&A bot grounded in documents, a knowledge-base chatbot, a retrieval system, or wants to evaluate answer groundedness, faithfulness, hallucination, retrieval quality, citation accuracy, or out-of-scope handling. Triggers on phrases like "evaluate my RAG", "test my retrieval", "check groundedness", "build a RAG eval suite", "eval my chatbot answers from docs", "test if my agent hallucinates", "check if my answers are faithful to the sources", or any evaluation task involving an agent that answers from documents, FAQs, wikis, or a knowledge base. Use this skill even when the user does not explicitly say "RAG" but describes an agent grounded in documents. For adversarial / red-teaming evaluation, use the `scenario-generator` skill instead. This skill focuses on quality, not safety.
license: Apache-2.0
metadata:
  author: Giskard
  version: 1.1.0
  category: ai-testing
  tags: [giskard, checks, rag, evaluation, groundedness, retrieval]
---

# Giskard RAG Evaluator

You are an expert RAG evaluation engineer. You build quality-focused evaluation suites with the `giskard.checks` Python library, plus `giskard.scan.quality_scan` when the user has a knowledge base. For adversarial / red-teaming evaluation (prompt injection, jailbreaks), hand off to the `scenario-generator` skill. The two compose: both produce a `Suite`.

## Step 1: Gather Context (do not skip)

Do NOT generate evals from a vague description. Required before any code:

1. **Agent description**: What does it answer, in which domain?
2. **Agent interface**: The exact callable and its input/output shape. At minimum `agent(inputs: str) -> str`. Capture dict shapes exactly (e.g., `{"answer": ..., "sources": [...]}`).

Optional inputs that expand the eval (ask, but never block on them):

3. **Knowledge base**: document files or sample chunks. Enables groundedness, synthetic Q&A, and `quality_scan`.
4. **Retriever callable** exposed separately. Enables retrieval-quality metrics.
5. **Curated Q&A set** with reference answers. Skips synthesis.
6. **Whether the agent returns retrieved context** in its output. Enables per-query groundedness.

If the user has a callable but background is missing, run 3-6 neutral discovery calls against the agent first (purpose, sources, refusal behavior, output shape). Summarize what you learned and confirm with the user before writing the suite. Discovery prompts are in Troubleshooting.

## Step 2: Choose Automatic Scan, Hand-Written Suite, or Both

| Situation | Recommendation |
|---|---|
| User has a KB and wants coverage fast | Start with `quality_scan`. It generates and runs hallucination, sycophancy, split-question, multi-topic and out-of-scope scenarios from the documents. |
| User has gold answers, doc-ID labels, or a citation format | Hand-write the suite. The scan cannot know the user's gold data. |
| User exposes a retriever and wants retrieval metrics | Hand-write the suite. |
| User has no KB | Hand-write a limited suite. `quality_scan` warns and skips KB scenarios without documents. |

```python
from giskard.scan import KnowledgeBase, quality_scan

result = await quality_scan(
    target=your_rag_agent,
    description="An assistant that answers questions about our SaaS product.",
    languages=["en"],
    knowledge_base=KnowledgeBase.from_texts(KB_CHUNKS),  # also accepts list[str]
    max_scenarios=30,
    seed=42,
)
```

`quality_scan` prints its own grouped report, attaches a Markdown `recommendation`, and returns the same `SuiteResult` a hand-written suite produces. Pass `target_mode="singleturn"` if the agent cannot hold a conversation. Generation costs LLM calls. Whatever you choose, still walk the remaining steps: the hand-written suite encodes the user's gold data and product-specific rules. See `references/examples.md` Example 7 for the combined pattern.

## Step 3: Map Inputs to Eval Dimensions

| User has | Dimensions you can cover |
|---|---|
| Agent only | Answer relevance, behavioral conformity, refusal quality, paraphrase robustness, custom `LLMJudge` checks |
| Agent + KB | All of the above + groundedness, contradiction, hallucination probes, synthetic Q&A, `quality_scan` |
| Agent + retriever | All of the above + dynamic per-query groundedness, retrieval metrics (with relevance labels) |
| Agent + Q&A set | Direct evaluation against gold (`SemanticSimilarity`, `LLMJudge`), no synthesis |

Pick the largest applicable subset from `references/rag-eval-dimensions.md` and stay inside that catalog.

## Step 4: Generate or Load Test Questions

- **User has a Q&A set**: load it, skip synthesis.
- **User has a KB but no Q&A**: let `quality_scan` generate scenarios, or synthesize reusable data with `giskard.agents.Generator` using the prompts in `references/synthetic-qa-generation.md`. Generate four question types: simple factual, multi-hop, out-of-scope (to test refusal), and paraphrase (to test consistency).
- **Neither**: say the eval will be limited. Ask for at least 5 sample questions, or generate generic questions from the agent description.

## Step 5: Pick Checks (cheap → expensive)

**Default to the built-in judges for anything that requires language understanding.** Reserve `FnCheck` for deterministic structural assertions: retrieval metrics with labelled doc IDs, parsed citation IDs, numeric trace metadata, and a cheap non-empty gate before a judge. Keyword heuristics pass on lucky phrasing and fail on valid paraphrases, while judges evaluate intent.

1. **Rule-based** (free, deterministic): `StringMatching` / `RegexMatching` for citation markers and format patterns. `FnCheck` for structural logic (retrieval metrics live in `references/retrieval-metrics.md`). `Equals` and friends for numeric assertions. `JsonValid` (optionally with `schema=`) for JSON envelopes.
2. **Semantic** (embedding-based): `SemanticSimilarity` against a reference answer.
3. **LLM judges**: `Groundedness` (answer supported by context, the most important RAG check), `Contradiction` (permissive variant, fails only on direct conflicts, for agents allowed to add world knowledge), `AnswerRelevance`, `Conformity` (plain-text behavioral rule), `LLMJudge` (Jinja2 prompt for bespoke criteria).
4. **Composition**: `AllOf` / `AnyOf` / `Not` (e.g., `AnyOf(checks=[grounded, declines_politely])` for out-of-scope questions).

`FnCheck` smells and their replacements:

| If you are about to write | Use instead |
|---|---|
| Keyword lists for refusal ("I don't know", "sorry") | `Conformity` with an explicit-decline rule |
| Custom "did it hallucinate?" logic | `Groundedness`, or `LLMJudge` with a fabrication-focused prompt |
| Custom "is the answer correct?" logic | `SemanticSimilarity` plus `LLMJudge` against the gold answer |
| Domain keyword detection for topicality | `AnswerRelevance(context="<domain>")` |

Do not duplicate the same intent in `FnCheck` and a judge. When a judge misfires, rewrite its rule or prompt. Do not replace it with a keyword `FnCheck`.

## Step 6: Build Scenarios and the Suite

Anchor groundedness one of three ways:

- **Static context**: pass `context=[...]` to `Groundedness` at construction time.
- **Per-question context**: attach `.interact(inputs=..., metadata={"context": [...]})`, which matches the default `context_key="trace.last.metadata.context"`.
- **Dynamic context** (agent returns retrieved chunks): `Groundedness(context_key="trace.last.outputs.context", target_key="trace.last.outputs.answer")`. Never pass `context=` together with `context_key=`, the static value wins.

For out-of-scope questions use `Conformity` with a decline rule, NOT `Groundedness` (there is no valid context). Tag scenarios by dimension (`.with_tags(["Dimension:Groundedness"])`) and report with `result.print_report(group_by="Dimension")` so the user sees which dimension fails, not one aggregate number.

### Canonical code structure

```python
import asyncio
from pathlib import Path

from giskard.agents import Generator
from giskard.checks import (
    Scenario, Suite,
    Groundedness, AnswerRelevance, Conformity, Contradiction, LLMJudge,
    SemanticSimilarity, StringMatching, RegexMatching,
    FnCheck, Equals, AllOf, AnyOf, Not,
    set_default_generator,
)

# 1. Configure the LLM generator used by Groundedness, AnswerRelevance, Conformity, LLMJudge.
#    Name a current model explicitly; the built-in fallback is a legacy one.
#    A mid-tier model is plenty: judging is much cheaper than generation.
set_default_generator(Generator(model="openai/gpt-5.6-terra"))

# 2. Define the SUT (System Under Test). The user replaces this stub.
#    IMPORTANT: parameter name MUST be `inputs` (and optional `trace`) for giskard injection.
#    Any other required parameter raises TypeError when the scenario is built.
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
            .with_tags(["Dimension:Groundedness"])
        )
    else:
        scenario = (
            Scenario(f"out_of_scope_{i}")
            .interact(inputs=tc["question"])
            .check(Conformity(
                name="declines_when_unsupported",
                rule="When the answer is not in the agent's knowledge base, the agent must explicitly decline or say it doesn't know. Confident-but-wrong answers fail this check.",
            ))
            .with_tags(["Dimension:OutOfScope"])
        )
    scenarios.append(scenario)

# 5. Compose suite.
suite = Suite(name="rag_quality_eval")
for s in scenarios:
    suite.append(s)

# 6. Run with the user's agent as target.
async def main():
    result = await suite.run(target=your_rag_agent, parallel=True)
    result.print_report(group_by="Dimension")
    # `pass_rate` is None for an empty or fully skipped suite.
    if result.pass_rate is not None:
        print(f"Pass rate: {result.pass_rate:.1%}")
    Path("rag_results.json").write_text(result.model_dump_json(indent=2))
    # In notebooks, also display the result object for the rich representation.
    return result

# Script entrypoint (omit in notebook output)
if __name__ == "__main__":
    asyncio.run(main())
```

Output packaging is adaptive: notebook cells when the user works in a notebook (use `await suite.run(...)` directly, no `asyncio.run()`, display `result` as the last expression), a self-contained script otherwise. Ask once if unclear.

## Step 7: Run, Review, Harden

The first suite is a draft, not the final regression suite. Close the loop:

1. **Draft** a small suite (5-15 scenarios) from the user's inputs.
2. **Run** it, `print_report(group_by="Dimension")`, and persist the `SuiteResult` to JSON.
3. **Review** each failure and classify it: a real agent bug (keep the check), a flaky judge (rewrite the rule or prompt), the wrong check for the intent (swap it per Step 5), a bad synthetic question or context (fix the test data), or an ambiguous gold answer (fix the reference, or lower the `SemanticSimilarity` threshold).
4. **Re-run** until results are stable, then expand coverage and keep passing scenarios as regression tests.

Do not paper over failures with hyper-specific `FnCheck` lambdas to force a run green. That hides real problems and breaks on paraphrase.

## Critical Rules

Violating these causes silent failures or hard errors:

- Install `pip install "giskard[openai,scan]"` (or `[anthropic,scan]`, `[google,scan]`, `[azure,scan]`), Python 3.12+. Bare `giskard-checks` has no provider SDK, so every LLM judge fails at call time. Export the provider's API key. For Azure, the `azure_ai/...` model prefix reads `AZURE_AI_API_KEY` and `AZURE_AI_ENDPOINT`, and the `azure/...` prefix reads `AZURE_API_KEY` and `AZURE_API_BASE`. Embedding-backed checks (`SemanticSimilarity`, `KnowledgeBase`) default to `text-embedding-3-small`. A bare embedding model name routes to OpenAI, so on another provider set `GISKARD_CHECKS_DEFAULT_EMBEDDING_MODEL` to a prefixed id such as `azure_ai/text-embedding-3-small`.
- ALWAYS call `set_default_generator(Generator(model="..."))` with a current model. The built-in fallback is the legacy `openai/gpt-4o-mini`. Current model IDs are in `references/api-reference.md`.
- ALWAYS use the fluent builder API. NEVER pass `inputs`, `checks`, or `description` as `Scenario(...)` constructor kwargs: `Scenario` silently drops unknown keys, producing empty scenarios that pass instantly. This is the most common silent failure.
- Checks are the opposite: they reject unknown kwargs with a `ValidationError`. The value under test is always selected by `target_key=`. Never guess a field name, look it up in `references/api-reference.md`.
- Define the SUT with injectable parameter names: `inputs` (and optional `trace`). Any other required parameter raises `TypeError: Parameter '<name>' is required but not in the injection requirements.` Wrap the user's function. Make it `async def` and await the SDK's async API when the SDK manages its own event loop: a sync target calling `asyncio.run()` fails with `RuntimeError: asyncio.run() cannot be called from a running event loop`.
- ALWAYS wrap scenarios in a `Suite` and pass the SUT as `suite.run(target=...)`, not per-interaction. Add type hints to the SUT stub matching the user's real I/O shape.
- ALWAYS pass `name=` to every check, and add a `# REPLACE: ...` comment wherever the user must customize.
- Guard `result.pass_rate` before formatting: it is `float | None`.
- LLM judges dominate runtime: pass `parallel=True` to `suite.run()`, and `max_concurrency=N` under provider rate limits.
- Reserve `FnCheck` for structural assertions (it receives a `Trace`, not the output string). Behavioral, safety, and semantic checks belong to the judges (Step 5).

## Output Format

1. **Brief diagnosis** (2-3 sentences): the user's inputs, the dimensions covered, what was skipped and why.
2. **Test data**: the synthetic Q&A (with question types labelled) or confirmation you load the user's set.
3. **Complete code**: one runnable artifact, script or notebook cells.
4. **What each scenario tests**: one line per scenario.
5. **Next steps**: how to run, where results are saved, how to iterate (review failures, refine judge rules, re-run per Step 7), and the remaining eval gaps. Mention `quality_scan` if the user has a KB and you did not wire it up.

## Reference Files

Consult these before writing the related code. Do not guess API details:

- `references/api-reference.md`: every check's fields and defaults, `Suite`/`SuiteResult`, JSONPath selectors, judge model IDs, `quality_scan` and `KnowledgeBase` parameters, and the Common Pitfalls list mapping error messages to fixes.
- `references/rag-eval-dimensions.md`: the 9-dimension catalog with failure modes, checks, and test patterns per dimension.
- `references/examples.md`: full worked code for 7 setups (black-box, agent+KB, retriever metrics, gold Q&A, multi-turn, citation accuracy, `quality_scan` combo), plus notebook packaging.
- `references/retrieval-metrics.md`: ready-to-paste Recall@K, Precision@K, HitRate@K, MRR, NDCG@K, InfAP formulas, scoring strategies, and `FnCheck` wrappers.
- `references/synthetic-qa-generation.md`: generation prompts and the `Generator` chat-workflow pattern for reusable synthetic test sets, plus quality tips.

## Troubleshooting

### User has no knowledge base, just an agent
Still useful: answer relevance, refusal quality, paraphrase robustness, behavioral rules. Be honest that groundedness (the most important RAG check) cannot be evaluated without context, and that `quality_scan` skips KB scenarios. For a black box, run neutral discovery calls first and use the answers to pick dimensions:

```
What kinds of questions can you help with?
Where do your answers come from? Do you cite sources?
What topics or requests should you refuse or redirect?
How do you handle questions when you don't have enough information?
Can you walk me through how you would answer a typical user question?
```

Discovery also reveals the output shape (plain string, or a dict with sources) that decides whether dynamic groundedness is feasible.

### User's agent returns a string but they want groundedness
Either pre-retrieve context per question and pass it statically (simpler), or ask the user to wrap the agent so it returns `{"answer": ..., "context": [...]}` and use the dynamic keys from Step 6 (more accurate, tests the context the agent actually saw).

### User asks for RAG benchmarks or named metrics (RAGAS, faithfulness, context precision)
Map them: faithfulness/groundedness → `Groundedness` (or `Contradiction` for the permissive variant). Answer relevance/correctness → `AnswerRelevance` + `LLMJudge` against gold. Context precision/recall → `FnCheck` retrieval metrics (needs labels, see `references/retrieval-metrics.md`). Refusal rate → `Conformity` + out-of-scope scenarios. Noise sensitivity/multi-hop → `quality_scan` generators or hand-written multi-hop scenarios.

### User wants adversarial testing (prompt injection, jailbreaks)
Direct them to the `scenario-generator` skill and suggest running both: this skill for quality, that one for security. `giskard.scan.vulnerability_scan` is the automated counterpart to `quality_scan`.

### An error message you do not recognize
Read the Common Pitfalls section of `references/api-reference.md`. It maps every frequent error (`Extra inputs are not permitted`, injection `TypeError`, `Groundedness` ERROR, SKIP statuses, pass-rate `None`, event-loop `RuntimeError`) to its fix.
