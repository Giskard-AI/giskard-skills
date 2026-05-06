# Retrieval Metrics

Ready-to-paste implementations of the standard retrieval-quality metrics, plus three scoring strategies for picking how strictly to count a retrieved document as "relevant". The `giskard.checks` library does not bundle these as named checks; the recipe is to wrap each formula in a `FnCheck`.

This file covers two questions:

1. **Which metric should I report?** Pick from Section 1 (set-based) or Section 2 (rank-aware) or Section 3 (sparse-label).
2. **How do I decide if a retrieved doc counts as relevant?** Pick from Section 4 (Strict, Cosine, or LLM-judged scoring).

You combine one answer from each. The metric formula stays the same; only the relevance test changes.

---

## Section 1: Set-based metrics (strict scoring assumed)

These ignore rank order. They look at which docs appear in the top-K and check overlap with the labelled relevant set.

### Recall@K

**What it measures**: Of all the docs labelled relevant for this query, what fraction appears in the top-K retrieved?

**Formula**: `|relevant ∩ top_K_retrieved| / |relevant|`

**Use when**: Your headline question is "did the retriever find the right doc?" Sensible default for almost every retrieval eval.

```python
def recall_at_k(relevant_ids: set[str], retrieved_ids: list[str], k: int) -> float:
    if not relevant_ids:
        return 1.0  # vacuous: nothing to find
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)
```

### Precision@K

**What it measures**: Of the top-K retrieved docs, what fraction is relevant?

**Formula**: `|relevant ∩ top_K_retrieved| / K`

**Use when**: K is small and you care about how cluttered the top-K is with irrelevant docs (the LLM has limited context, so noisy top-K hurts).

```python
def precision_at_k(relevant_ids: set[str], retrieved_ids: list[str], k: int) -> float:
    if k == 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / k
```

### HitRate@K

**What it measures**: Did at least one relevant doc appear in the top-K? Binary 0 or 1.

**Use when**: You need a cheap floor metric for "the retriever didn't completely miss". Pairs nicely with Recall@K, since HitRate@K is easier to satisfy.

```python
def hit_at_k(relevant_ids: set[str], retrieved_ids: list[str], k: int) -> float:
    return 1.0 if set(retrieved_ids[:k]) & relevant_ids else 0.0
```

---

## Section 2: Rank-aware metrics (strict scoring assumed)

These reward putting relevant docs higher in the ranked list. Use when your retriever returns more docs than fit in the LLM's context, so position matters.

### MRR (Mean Reciprocal Rank)

**What it measures**: 1 divided by the rank of the first relevant doc. Returns 0 if no relevant doc was retrieved.

**Formula**: `1 / rank_of_first_relevant`

**Use when**: Only one or a small number of docs are relevant per query, and you want to know how high the first one ranks.

```python
def mrr(relevant_ids: set[str], retrieved_ids: list[str]) -> float:
    for i, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / i
    return 0.0
```

### NDCG@K (Normalized Discounted Cumulative Gain)

**What it measures**: Rewards relevant docs at top positions more than at lower positions. Normalized so the perfect ranking scores 1.0.

**Formula**: `DCG@K / IDCG@K`, where `DCG@K = sum_{i=1..K}(rel_i / log2(i + 1))` and `IDCG@K` is the same with all relevants at the top.

**Use when**: You want a single number that captures both "relevant docs retrieved" and "ranked at the top".

```python
import math

def ndcg_at_k(relevant_ids: set[str], retrieved_ids: list[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    top_k = retrieved_ids[:k]
    dcg = sum(
        (1.0 if doc_id in relevant_ids else 0.0) / math.log2(i + 2)
        for i, doc_id in enumerate(top_k)
    )
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0
```

---

## Section 3: Sparse-label metric

When you suspect there are relevant docs you have not labelled (e.g., 50 docs in the corpus, 5 labelled relevant per query, but several others would also be acceptable), strict scoring under-reports. Use Inferred Average Precision.

### InfAP (Inferred Average Precision)

**What it measures**: Like AP, but treats unlabelled docs as having a default partial probability of being relevant. Robust to incomplete labelling.

**Formula** (informal): `sum_i(p_i * cumulative_precision_i) / sum_i(p_i)`, where `p_i = 1` for labelled relevant, `p_i = unjudged_prob` (default 0.5) for unlabelled, `p_i = 0` for labelled non-relevant.

**Use when**: Your relevance labels are known to be incomplete, and you want to avoid penalising the retriever for finding unlabelled-but-actually-relevant docs.

```python
def inf_ap(
    relevant_ids: set[str],
    non_relevant_ids: set[str],
    retrieved_ids: list[str],
    unjudged_prob: float = 0.5,
) -> float:
    cumulative_relevance = 0.0
    weighted_precision_sum = 0.0
    for i, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            p = 1.0
        elif doc_id in non_relevant_ids:
            p = 0.0
        else:
            p = unjudged_prob
        cumulative_relevance += p
        precision_at_i = cumulative_relevance / i
        weighted_precision_sum += p * precision_at_i
    return weighted_precision_sum / cumulative_relevance if cumulative_relevance > 0 else 0.0
```

---

## Section 4: Scoring strategies (how to decide if a doc is "relevant")

The metrics above all assume each retrieved doc is either in `relevant_ids` (relevant) or not (not relevant). That assumption breaks down in two cases:

1. The retriever returns the right doc but with a different ID (e.g., a re-chunked version).
2. You have no relevance labels at all.

For those cases, swap the strict membership test for one of the strategies below. The metric formulas stay the same; you replace `doc_id in relevant_ids` with a real-valued or fuzzy relevance score.

### 4a. Strict scoring (default)

`is_relevant(doc, relevant) = (doc.id in relevant_ids)`. Already used in Sections 1 to 3. Choose this when your labels are exhaustive: every relevant doc in the corpus has been labelled.

### 4b. Cosine similarity scoring

For each retrieved doc, compute embedding cosine similarity against every labelled relevant doc; count as "relevant" if the max similarity passes a threshold (commonly 0.85). Useful when labels are by exemplar text rather than exhaustive ID list.

```python
import numpy as np

def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

def is_relevant_cosine(
    retrieved_text: str,
    relevant_texts: list[str],
    embedder,  # any callable: text -> np.ndarray
    threshold: float = 0.85,
) -> bool:
    if not relevant_texts:
        return False
    q = embedder(retrieved_text)
    sims = [cosine(q, embedder(r)) for r in relevant_texts]
    return max(sims) >= threshold
```

Then plug this into the metric formulas by replacing `doc_id in relevant_ids` with `is_relevant_cosine(doc.text, relevant_texts, embedder)`. Cache embeddings or this gets expensive fast.

### 4c. LLM-as-judge scoring

For each retrieved doc, ask an LLM "is this relevant to the query?". Use when you have no labels at all (or want to validate cosine scoring against a stronger signal).

```python
from giskard.agents.generators import Generator
from pydantic import BaseModel

class RelevanceVerdict(BaseModel):
    relevant: bool
    reason: str

async def is_relevant_llm(
    query: str,
    retrieved_text: str,
    generator: Generator,
) -> bool:
    chat = await (
        generator
        .chat(
            "Decide if the following document is relevant to the query.\n\n"
            f"Query: {query}\n\nDocument: {retrieved_text}\n\n"
            "Return relevant=true if the document directly addresses the query, false otherwise."
        )
        .with_output(RelevanceVerdict)
        .run()
    )
    return chat.output.relevant
```

This is slow and costs LLM calls per retrieved doc. Sample a subset of queries if you go this route. Consider using a smaller, faster judge (e.g., `gpt-4o-mini`).

---

## Putting it together: FnCheck wrappers

Each metric becomes a `FnCheck` that returns a boolean (passes if metric meets a threshold). The pattern:

```python
from giskard.checks import FnCheck

def make_recall_check(
    relevant_ids: set[str],
    k: int,
    threshold: float,
    retrieved_path: str = "retrieved_ids",
) -> FnCheck:
    def fn(trace) -> bool:
        outputs = trace.last.outputs
        retrieved = outputs.get(retrieved_path, []) if isinstance(outputs, dict) else getattr(outputs, retrieved_path, [])
        return recall_at_k(relevant_ids, retrieved, k) >= threshold
    return FnCheck(name=f"recall@{k}>={threshold:.2f}", fn=fn)
```

For metrics that should report the value (not just pass/fail), wrap the same function with `LesserThan` / `GreaterThan` against a numeric metric instead. The simpler path is the boolean `FnCheck` shown above.

## Picking thresholds

Defaults that work well as a starting point:

| Metric | Threshold | Reasoning |
|---|---|---|
| Recall@5 | 0.8 | At K=5 most retrievers can find at least 80% of the relevant set |
| Precision@5 | 0.4 | Precision drops fast as K grows; 40% in top-5 is solid |
| HitRate@10 | 1.0 | Top-10 should always contain at least one relevant doc |
| MRR | 0.5 | First relevant doc should appear in the top 2 on average |
| NDCG@10 | 0.7 | Catch-all ranking quality |
| InfAP | 0.5 | Default for sparse-label setups |

These are starting points; tune to your corpus and retriever.

## Reporting numbers, not just pass/fail

Pass/fail thresholds are useful for CI gates, but during development you usually want the raw scores. The pattern:

1. Run the suite with `FnCheck` thresholds for CI.
2. Separately, compute the raw metrics outside the suite for trend tracking and report them in `result.print_report()` output via a custom post-processing step.

Example post-processing helper, called after `await suite.run(...)`:

```python
def aggregate_retrieval_metrics(suite_result, test_cases, k: int = 5):
    recalls, precisions, mrrs = [], [], []
    for tc, scen in zip(test_cases, suite_result.results):
        try:
            outputs = scen.final_trace.last.outputs  # ScenarioResult exposes .final_trace
        except Exception:
            continue
        retrieved = outputs.get("retrieved_ids") or outputs.get("retrieved_paper_ids") or []
        relevant = set(tc["relevant_ids"])
        recalls.append(recall_at_k(relevant, retrieved, k))
        precisions.append(precision_at_k(relevant, retrieved, k))
        mrrs.append(mrr(relevant, retrieved))
    n = len(recalls) or 1
    return {
        f"recall@{k}_mean": sum(recalls) / n,
        f"precision@{k}_mean": sum(precisions) / n,
        "mrr_mean": sum(mrrs) / n,
    }
```

Track these means in your CI logs for trend lines independent of the pass/fail gate.
