"""Interactive CLI to run the reference data analytics agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.agent import analytics_agent
from src.sql_tools import DEFAULT_DB_PATH, ensure_database

load_dotenv()


def main() -> None:
    """Start an interactive session with the analytics agent."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY in .env or the environment.", file=sys.stderr)
        sys.exit(1)

    db_path = Path(os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH))
    ensure_database(db_path)
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    print("Data analytics agent (SQLite demo)")
    print(f"  database: {db_path}")
    print(f"  model:    {model}")
    print('  commands: "exit" or Ctrl-D to quit\n')

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        result = analytics_agent(question, db_path=db_path)
        print(f"\n{result['answer']}\n")
        if result.get("queries"):
            print(f"  ({len(result['queries'])} quer{'y' if len(result['queries']) == 1 else 'ies'} executed)")
            if os.environ.get("SHOW_SQL", "").lower() in {"1", "true", "yes"}:
                for q in result["queries"]:
                    print(f"  SQL: {q.get('sql')}")
                    if q.get("blocked"):
                        print(f"       blocked: {q.get('error')}")
                    elif q.get("success"):
                        print(f"       rows: {q.get('row_count')}")
                    else:
                        print(f"       error: {q.get('error')}")
            print()


if __name__ == "__main__":
    main()
