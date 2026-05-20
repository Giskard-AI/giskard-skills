"""Load knowledge-base documents from the sample_kb directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Document:
    """A KB document with stable id and body text."""

    doc_id: str
    title: str
    content: str


def kb_root(path: Path | None = None) -> Path:
    """Return the knowledge-base directory path.

    Args:
        path: Override KB root; defaults to ``sample_kb`` next to ``src/``.

    Returns:
        Absolute path to the KB folder.
    """
    if path is not None:
        return path.resolve()
    return (Path(__file__).resolve().parent.parent / "sample_kb").resolve()


def load_documents(kb_path: Path | None = None) -> list[Document]:
    """Load all markdown files from the knowledge base.

    Args:
        kb_path: Optional KB directory override.

    Returns:
        List of documents sorted by doc_id.
    """
    root = kb_root(kb_path)
    docs: list[Document] = []
    for file_path in sorted(root.glob("*.md")):
        text = file_path.read_text(encoding="utf-8")
        title = text.split("\n", 1)[0].lstrip("# ").strip()
        docs.append(
            Document(
                doc_id=file_path.stem,
                title=title,
                content=text.strip(),
            )
        )
    return docs
