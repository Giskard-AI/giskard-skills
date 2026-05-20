"""Pytest wrapper for the reference RAG giskard suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from giskard.agents.generators import Generator
from giskard.checks import set_default_generator

from eval.scenarios import build_suite
from src.agent import rag_agent

load_dotenv(ROOT / ".env")

KB_PATH = ROOT / "sample_kb"
JUNIT_PATH = ROOT / "eval" / "results.xml"


pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="Set OPENAI_API_KEY in example-agent/.env to run LLM-backed checks",
)


@pytest.mark.asyncio
async def test_rag_suite_passes() -> None:
    """Run in-scope scenarios; assert full pass rate."""
    set_default_generator(
        Generator(model=os.environ.get("GISKARD_JUDGE_MODEL", "openai/gpt-4o-mini"))
    )
    suite = build_suite(include_in_scope=True, include_out_of_scope=False)
    result = await suite.run(target=lambda inputs: rag_agent(inputs, kb_path=KB_PATH))
    JUNIT_PATH.write_text(result.to_junit_xml(), encoding="utf-8")
    assert result.pass_rate == 1.0
