"""Pytest wrapper for the reference text-to-SQL giskard suite."""

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
from src.agent import analytics_agent
from src.sql_tools import ensure_database

load_dotenv(ROOT / ".env")

DB_PATH = Path(os.environ.get("DATABASE_PATH", ROOT / "sample_data" / "analytics.db"))
JUNIT_PATH = ROOT / "eval" / "results.xml"


pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="Set OPENAI_API_KEY in example-agent/.env to run LLM-backed checks",
)


@pytest.fixture(scope="module", autouse=True)
def _seed_database() -> None:
    """Ensure SQLite seed DB exists before suite runs."""
    ensure_database(DB_PATH)


@pytest.mark.asyncio
async def test_static_quality_suite_passes() -> None:
    """Run static quality scenarios (no personas); assert full pass rate."""
    set_default_generator(
        Generator(model=os.environ.get("GISKARD_JUDGE_MODEL", "openai/gpt-4o-mini"))
    )
    suite = build_suite(
        include_static=True,
        include_personas=False,
        include_safety=False,
        include_out_of_scope=False,
    )
    result = await suite.run(target=lambda inputs: analytics_agent(inputs, db_path=DB_PATH))
    JUNIT_PATH.write_text(result.to_junit_xml(), encoding="utf-8")
    assert result.pass_rate == 1.0
