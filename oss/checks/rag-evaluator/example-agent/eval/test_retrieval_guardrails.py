"""Deterministic retrieval guardrail tests (no LLM, no API key)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.kb import load_documents  # noqa: E402
from src.retriever import retrieve  # noqa: E402


def test_kb_loads_documents() -> None:
    docs = load_documents()
    assert len(docs) >= 5
    ids = {doc.doc_id for doc in docs}
    assert "refund-policy" in ids
    assert "deployment" in ids


def test_retrieve_refund_query() -> None:
    docs = retrieve("What is the refund policy for annual plans?")
    assert docs
    assert docs[0].doc_id == "refund-policy"


def test_retrieve_deployment_query() -> None:
    docs = retrieve("How do we deploy to GCP production?")
    assert docs
    assert any(doc.doc_id == "deployment" for doc in docs)


def test_retrieve_oos_query_returns_empty_or_low_relevance() -> None:
    docs = retrieve("What is the capital of France?")
    assert len(docs) == 0 or docs[0].doc_id not in {"refund-policy", "pricing", "deployment"}


if __name__ == "__main__":
    test_kb_loads_documents()
    test_retrieve_refund_query()
    test_retrieve_deployment_query()
    test_retrieve_oos_query_returns_empty_or_low_relevance()
    print("All retrieval guardrail tests passed.")
