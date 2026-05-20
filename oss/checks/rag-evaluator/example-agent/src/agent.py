"""Reference RAG agent: retrieve from KB then answer with OpenAI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from src.retriever import document_sources, documents_to_context, retrieve

load_dotenv()


def rag_agent(
    inputs: str,
    *,
    kb_path: Path | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """Answer a question using retrieved KB context.

    Args:
        inputs: User question (giskard injects as ``inputs``).
        kb_path: Optional knowledge-base directory.
        top_k: Number of chunks to retrieve.

    Returns:
        Dict with ``answer``, ``context``, ``sources``, and ``tool_calls``.

    Raises:
        RuntimeError: If OPENAI_API_KEY is missing.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in the environment or .env file")

    docs = retrieve(inputs, k=top_k, kb_path=kb_path)
    context = documents_to_context(docs)
    sources = document_sources(docs)

    if not context:
        return {
            "answer": (
                "I don't have relevant documentation to answer that question. "
                "Please ask about Acme Analytics product topics covered in our docs."
            ),
            "context": [],
            "sources": [],
            "tool_calls": [{"name": "retrieve", "arguments": {"query": inputs}, "result_count": 0}],
        }

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    system = (
        "You are a helpful assistant for Acme Analytics internal documentation. "
        "Answer ONLY using the provided context. If the context does not contain "
        "the answer, say you don't know — do not invent facts. Cite doc ids like [refund-policy]."
    )
    context_block = "\n\n---\n\n".join(context)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Context:\n{context_block}\n\nQuestion: {inputs}",
            },
        ],
        temperature=0,
    )
    answer = response.choices[0].message.content or ""

    return {
        "answer": answer,
        "context": context,
        "sources": sources,
        "tool_calls": [
            {
                "name": "retrieve",
                "arguments": {"query": inputs, "top_k": top_k},
                "result_count": len(docs),
            }
        ],
    }
