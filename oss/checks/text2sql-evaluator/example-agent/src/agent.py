"""OpenAI tool-calling analytics agent used as the evaluation SUT."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from src.schema import default_system_prompt
from src.sql_tools import EXECUTE_QUERY_TOOL_SCHEMA, execute_query

load_dotenv()


@dataclass
class AgentResponse:
    """Structured agent output for giskard checks."""

    answer: str
    queries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for giskard trace outputs."""
        return {"answer": self.answer, "queries": self.queries}


def _run_tool(sql: str, db_path: Path | None) -> dict[str, Any]:
    result = execute_query(sql, db_path=db_path)
    payload: dict[str, Any] = {
        "sql": result.sql,
        "success": result.success,
        "blocked": result.blocked,
    }
    if result.success:
        payload["rows"] = result.rows
        payload["row_count"] = result.row_count
        payload["fields"] = result.fields
    else:
        payload["error"] = result.error
    return payload


def analytics_agent(
    inputs: str,
    *,
    db_path: Path | None = None,
    max_steps: int = 8,
) -> dict[str, Any]:
    """Answer a natural-language analytics question using SQL tools.

    Args:
        inputs: User question (injected by giskard as ``inputs``).
        db_path: Optional SQLite database path.
        max_steps: Maximum tool-call iterations.

    Returns:
        Dict with ``answer`` and ``queries`` keys for checks.

    Raises:
        RuntimeError: If OPENAI_API_KEY is not set.

    Example:
        >>> os.environ["OPENAI_API_KEY"] = "test"
        >>> analytics_agent("How many users?")  # doctest: +SKIP
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in the environment or .env file")

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    system = default_system_prompt(db_path)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": inputs},
    ]
    queries: list[dict[str, Any]] = []

    for _ in range(max_steps):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[EXECUTE_QUERY_TOOL_SCHEMA],
            tool_choice="auto",
        )
        message = response.choices[0].message
        if message.tool_calls:
            messages.append(message.model_dump())
            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                sql = str(args.get("sql", ""))
                tool_result = _run_tool(sql, db_path)
                queries.append(tool_result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result),
                    }
                )
            continue

        answer = message.content or ""
        return AgentResponse(answer=answer, queries=queries).to_dict()

    return AgentResponse(
        answer="Could not complete the request within the step limit.",
        queries=queries,
    ).to_dict()
