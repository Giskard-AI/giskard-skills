"""Simple keyword retriever over KB documents."""

from __future__ import annotations

import re
from pathlib import Path

from src.kb import Document, load_documents


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z0-9]+", text) if len(t) > 2}


def retrieve(
    query: str,
    *,
    k: int = 3,
    kb_path: Path | None = None,
) -> list[Document]:
    """Return top-k documents by keyword overlap with the query.

    Args:
        query: User question.
        k: Maximum documents to return.
        kb_path: Optional KB directory override.

    Returns:
        Ranked documents (may be empty if no overlap).
    """
    docs = load_documents(kb_path)
    query_tokens = _tokenize(query)
    if not query_tokens:
        return docs[:k]

    scored: list[tuple[int, Document]] = []
    for doc in docs:
        doc_tokens = _tokenize(doc.content)
        score = len(query_tokens & doc_tokens)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for _, doc in scored[:k]]


def documents_to_context(docs: list[Document]) -> list[str]:
    """Serialize retrieved documents for Groundedness checks."""
    return [f"[{doc.doc_id}] {doc.content}" for doc in docs]


def document_sources(docs: list[Document]) -> list[dict[str, str]]:
    """Serialize source metadata for tool-usage FnChecks."""
    return [{"doc_id": doc.doc_id, "title": doc.title} for doc in docs]
