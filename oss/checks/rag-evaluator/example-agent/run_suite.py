"""Run the giskard evaluation suite against the reference RAG agent."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from giskard.agents.generators import Generator
from giskard.checks import set_default_generator

from src.agent import rag_agent

load_dotenv(ROOT / ".env")

RESULTS_PATH = ROOT / "eval" / "results.json"
KB_PATH = ROOT / "sample_kb"


def _load_scenarios_module():
    path = ROOT / "eval" / "scenarios.py"
    spec = importlib.util.spec_from_file_location("rag_scenarios", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the reference RAG agent with giskard.checks.")
    parser.add_argument(
        "--in-scope-only",
        action="store_true",
        help="Run only in-scope KB scenarios (4 scenarios).",
    )
    parser.add_argument(
        "--oos-only",
        action="store_true",
        help="Run only out-of-scope refusal scenarios (2 scenarios).",
    )
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("GISKARD_JUDGE_MODEL", "openai/gpt-4o-mini"),
        help="Model for LLM-backed checks.",
    )
    parser.add_argument(
        "--agent-model",
        default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        help="Model used by the RAG agent.",
    )
    return parser.parse_args()


async def run_suite(args: argparse.Namespace) -> int:
    """Execute the suite and write results.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code 0 if all scenarios pass, 1 otherwise.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY in example-agent/.env", file=sys.stderr)
        return 1

    os.environ["OPENAI_MODEL"] = args.agent_model
    scenarios_mod = _load_scenarios_module()

    include_in_scope = not args.oos_only
    include_out_of_scope = not args.in_scope_only
    suite = scenarios_mod.build_suite(
        include_in_scope=include_in_scope,
        include_out_of_scope=include_out_of_scope,
    )

    set_default_generator(Generator(model=args.judge_model))

    def target(inputs: str) -> dict:
        return rag_agent(inputs, kb_path=KB_PATH)

    print(f"Running RAG eval (agent={args.agent_model}, judge={args.judge_model})...\n")
    result = await suite.run(target=target)
    result.print_report()

    if hasattr(result, "model_dump_json"):
        RESULTS_PATH.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nResults written to {RESULTS_PATH}")

    if getattr(result, "pass_rate", 1.0) < 1.0:
        return 1
    return 0


def main() -> None:
    """CLI entrypoint."""
    args = _parse_args()
    raise SystemExit(asyncio.run(run_suite(args)))


if __name__ == "__main__":
    main()
