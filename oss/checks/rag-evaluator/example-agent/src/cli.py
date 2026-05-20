"""Interactive CLI for the reference RAG agent."""

from __future__ import annotations

import sys
from pathlib import Path

from src.agent import rag_agent


def main() -> None:
    """Run a REPL against the bundled knowledge base."""
    kb_path = Path(__file__).resolve().parent.parent / "sample_kb"
    print("Acme Analytics docs assistant (type 'quit' to exit)\n")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line or line.lower() in {"quit", "exit", "q"}:
            break
        result = rag_agent(line, kb_path=kb_path)
        print(f"\nassistant> {result['answer']}\n")
        if result.get("sources"):
            ids = ", ".join(s["doc_id"] for s in result["sources"])
            print(f"(sources: {ids})\n")


if __name__ == "__main__":
    main()
    sys.exit(0)
