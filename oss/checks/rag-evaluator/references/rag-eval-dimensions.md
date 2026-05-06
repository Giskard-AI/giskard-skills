# RAG Evaluation Dimensions

The catalog of quality dimensions to evaluate in a RAG system. Use this to decide which checks to apply and to design test scenarios. Each dimension lists what it measures, when it applies, common failure modes, and the checks to use.

A solid RAG eval covers at least dimensions 1–3. Add 4–9 as the user's setup permits.

---

## 1. Groundedness / Faithfulness

**What it measures**: Whether the agent's answer is supported by the provided context. The single most important RAG check. The whole point of retrieval is to ground the answer in real sources.

**When it applies**: Whenever a context is available, either statically (KB chunks attached to test cases) or dynamically (agent returns retrieved chunks).

**Failure modes**:
- Agent makes a claim not present in the context (classic hallucination)
- Agent agrees with a false premise in the question even though the context contradicts it
- Agent paraphrases context loosely enough to drift from the original meaning
- Agent omits key qualifiers from the source (e.g., source says "may cause X in some cases", agent says "causes X")

**Checks to use**:
- `Groundedness`: primary check. Use static `context=[...]` or `context_key=...` for dynamic.
- `LLMJudge`: for nuanced groundedness criteria (e.g., "no claim should go beyond what the source explicitly states")

**Test patterns**:
- Ask a question whose answer is in a single chunk → expect grounded answer
- Ask a question whose answer is in multiple chunks → expect grounded synthesis (overlaps with multi-hop)
- Ask a question with a **false premise** ("Since X is true, why does Y happen?" where X is contradicted by KB) → expect agent to correct the premise, not play along

---

## 2. Answer Relevance

**What it measures**: Whether the answer actually addresses the question. An answer can be perfectly grounded and still off-topic.

**When it applies**: Always.

**Failure modes**:
- Agent dumps a long passage from the source without answering the specific question
- Agent answers a *related* but different question (e.g., asks "when?", agent answers "why")
- Agent gives a vague meta-answer ("That's a great question. Let me think...")
- In multi-turn, agent answers a previous question that no longer applies

**Checks to use**:
- `AnswerRelevance`: primary. Defaults to `question_key="trace.last.inputs"`, `answer_key="trace.last.outputs"`. Pass `context="domain description"` to constrain the judge.
- `LLMJudge`: for stricter or domain-specific relevance criteria

**Test patterns**:
- Ask a narrow specific question → expect a narrow specific answer
- Ask a comparison question ("how does X differ from Y?") → expect both sides
- In multi-turn, ask follow-ups ("what about Z?") → expect contextual answer

---

## 3. Out-of-Scope Refusal

**What it measures**: When the question cannot be answered from the KB, does the agent decline rather than hallucinate?

**When it applies**: Always. Every RAG system encounters questions outside its KB.

**Failure modes**:
- Agent confidently fabricates an answer using world knowledge instead of declining
- Agent says "I don't know" but then proceeds to answer anyway
- Agent declines on questions it *should* be able to answer (over-refusal, also bad)
- Agent answers in-domain questions but with no grounding when its retrieval missed

**Checks to use**:
- `Conformity` with rule like: "When the answer is not in the agent's knowledge base, the agent must explicitly decline or say it does not know. Confident-but-unsupported answers fail."
- `StringMatching(keyword="don't have", ...)` or similar: quick sanity check on refusal phrasing
- `AnyOf(grounded, declines)`: pass if either grounded OR refusal happened

**Test patterns**:
- Generate questions about entities/topics intentionally absent from the KB
- Generate questions adjacent to the KB ("you cover X, what about Y?" where Y is not covered)
- Generate questions about future events or post-cutoff information
- Always pair out-of-scope tests with a few clearly answerable questions to catch over-refusal

---

## 4. Retrieval Quality

**What it measures**: Whether the retriever returns relevant documents for a query. Independent of generation quality; a perfect generator can't fix bad retrieval.

**When it applies**: When the user exposes either a separate retriever callable, or an end-to-end agent that returns retrieved doc IDs alongside the answer. Strict-scoring metrics also need relevance labels (which doc IDs *should* be retrieved per question); cosine or LLM scoring can substitute when labels are absent (see `references/retrieval-metrics.md` Section 4).

**Failure modes**:
- Relevant doc is in the KB but not retrieved (recall failure)
- Many irrelevant docs retrieved, drowning out the relevant one (precision failure)
- Right doc retrieved but ranked too low to fit in the LLM's context window
- The right doc is retrieved but its chunk variant has a different ID than the labelled one (a labelling artefact, not a real failure; cosine scoring rescues this)

**Metrics catalogue**: Pick from `references/retrieval-metrics.md`. The most useful starting set:

- `Recall@K`: of the labelled relevant docs, what fraction lands in the top-K? (Default headline.)
- `Precision@K`: of the top-K, what fraction is relevant? (Pair with Recall@K.)
- `HitRate@K`: did at least one relevant doc make the top-K? (Cheap floor.)
- `MRR`: how high is the first relevant doc ranked? (Use when one or few docs are relevant per query.)
- `NDCG@K`: ranking-aware, normalized to 1.0. (Use when position matters because top-K is truncated for the LLM.)
- `InfAP`: handles unlabelled-but-relevant docs. (Use when labels are known to be incomplete.)

The reference also shows three scoring strategies (Strict, Cosine, LLM-judged) that determine when a retrieved doc counts as "relevant". Strict scoring is the default; Cosine and LLM-judged unlock these metrics for setups with sparse or no labels.

**Checks to use**:
- `FnCheck` wrapping the metric formula (see `references/retrieval-metrics.md` for ready-to-paste implementations and FnCheck wrappers).
- For tracking raw metric values (not just pass/fail), the same reference shows a `aggregate_retrieval_metrics` helper to run after the suite for trend tracking.

**Test patterns**:
- For each test question, label the doc IDs that should be retrieved (often a single chunk).
- Compute `Recall@K` and `Precision@K` at K = 5 or 10 as the headline pair.
- Add `MRR` if your retriever returns a long ranked list.
- Test paraphrased queries to see whether retrieval stays stable across rewordings.

---

## 5. Citation Accuracy

**What it measures**: When the agent cites sources, do the citations exist and do they actually support the cited claim?

**When it applies**: Only if the agent is supposed to cite (system prompt instructs it to, or product requires it).

**Failure modes**:
- Agent fabricates a citation that doesn't exist in the corpus
- Agent cites a real source but it doesn't say what the agent claims it does (citation/claim mismatch)
- Agent cites the right source but at the wrong location (page/section drift)
- Agent makes claims with no citation when citations are required

**Checks to use**:
- `RegexMatching`: does the answer contain citation markers (e.g., `[1]`, `(Smith 2020)`)?
- `FnCheck`: extract cited IDs from the answer and check they exist in the KB
- `LLMJudge`: compare each cited claim against its cited source

**Test patterns**:
- Standard factual questions → expect citations
- Multi-claim answers → expect a citation per distinct claim
- Mix in a question that requires combining sources → expect multiple citations

---

## 6. Hallucination Probes

**What it measures**: Whether the agent invents information. Tightly related to groundedness, but framed actively as adversarial probes for *fabrication*.

**When it applies**: Always, especially when groundedness is hard to verify automatically.

**Note on scope**: This is *quality-focused* hallucination probing; we test whether the agent invents facts in normal use. Adversarial fabrication attacks (jailbreaks, persona manipulation) belong in `scenario-generator`.

**Failure modes**:
- Agent invents a citation, statistic, or quote that isn't in the source
- Agent confidently answers questions about non-existent entities or terms
- Agent fills in plausible-but-fictional details to round out a partial answer

**Checks to use**:
- `Groundedness` with strict criteria
- `LLMJudge` with a fabrication-focused prompt (e.g., "Identify any factual claim in the answer that is not directly supported by the context. Return passed=false if any are found.")

**Test patterns**:
- Ask about a **non-existent entity** in the agent's domain (e.g., a made-up product name) → expect refusal, not invented description
- Ask for a **specific number** the KB doesn't contain → expect refusal
- Ask for a **direct quote** from a source that doesn't contain such a quote → expect refusal

---

## 7. Multi-Hop Reasoning

**What it measures**: Whether the agent can correctly synthesize information across multiple chunks rather than just regurgitating one.

**When it applies**: KBs where information is genuinely distributed across documents (most real KBs).

**Failure modes**:
- Agent answers from one chunk and ignores another that completes the picture
- Agent retrieves all relevant chunks but fails to combine them logically
- Agent invents a connection between chunks that isn't there

**Checks to use**:
- `Groundedness` with all relevant chunks as context
- `LLMJudge` for the combination logic specifically

**Test patterns**:
- Generate questions whose answer requires facts from 2+ chunks (see `synthetic-qa-generation.md`)
- Verify the question is *genuinely* multi-hop, not just a chain of trivial single-hop steps

---

## 8. Paraphrase Consistency

**What it measures**: Does the agent give consistent answers when the same question is rephrased?

**When it applies**: Always, but most useful for high-stakes domains where inconsistency is itself a defect.

**Failure modes**:
- Different phrasings retrieve different chunks → different (sometimes contradictory) answers
- Agent contradicts its own previous answers when the question is reworded

**Checks to use**:
- `SemanticSimilarity` between answers across paraphrases (within a single multi-turn scenario, or between sibling scenarios)
- `LLMJudge` for "do these two answers say the same thing?"

**Test patterns**:
- For each factual question, generate 2–3 paraphrases (formal/casual/abbreviated)
- Run them as separate scenarios; cross-check answers post-hoc, OR put paraphrases in a single multi-turn scenario and compare via `trace.interactions[i].outputs`

---

## 9. Numerical / Factual Precision

**What it measures**: When the answer is a specific value (number, date, name), is it correct?

**When it applies**: Domains where exact values matter (finance, healthcare dosing, legal dates, technical specs).

**Failure modes**:
- Right answer, wrong unit ("$5M" vs "$5K")
- Right value, wrong subject (correct date for the wrong event)
- Off-by-one or rounding errors

**Checks to use**:
- `Equals`: for exact match against a gold value
- `RegexMatching`: for format validation (e.g., dollar amounts, dates)
- `FnCheck`: for numerical tolerance (e.g., within 5%)
- `LLMJudge`: when the gold answer can be expressed many ways

**Test patterns**:
- Curate questions with verifiable single-value answers
- Test edge cases: very large/small numbers, dates near boundaries, names with non-ASCII characters

---

## Picking dimensions for a given user

Default coverage if you have nothing to go on:

| Always | If KB available | If retriever exposed | If gold answers |
|---|---|---|---|
| 2. Answer relevance | 1. Groundedness | 4. Retrieval quality | 9. Numerical/factual |
| 3. Out-of-scope refusal | 6. Hallucination probes | 7. Multi-hop reasoning | (use `SemanticSimilarity` against gold) |
| | 8. Paraphrase consistency | | |
| | 5. Citation accuracy (if agent cites) | | |

Don't try to cover all nine in one suite. Pick the 3–5 most relevant for the user's domain and build them well.
