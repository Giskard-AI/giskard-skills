"""Run the giskard evaluation suite against the deployed analytics agent."""

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

from src.agent import analytics_agent
from src.sql_tools import ensure_database

load_dotenv(ROOT / ".env")

RESULTS_PATH = ROOT / "eval" / "results.json"


def _load_scenarios_module():
    path = ROOT / "eval" / "scenarios.py"
    spec = importlib.util.spec_from_file_location("analytics_scenarios", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the reference data analytics agent with giskard.checks. "
            "Full suite uses static + persona scenarios; ~100%% pass may mean tests are too easy."
        ),
    )
    parser.add_argument(
        "--safety-only",
        action="store_true",
        help="Run only SQL safety scenarios (4 scenarios).",
    )
    parser.add_argument(
        "--quality-only",
        action="store_true",
        help="Run static quality, personas, and out-of-scope (no safety).",
    )
    parser.add_argument(
        "--personas-only",
        action="store_true",
        help="Run only UserSimulator persona scenarios (9 scenarios).",
    )
    parser.add_argument(
        "--no-personas",
        action="store_true",
        help="Skip persona scenarios (static + safety + out-of-scope).",
    )
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("GISKARD_JUDGE_MODEL", "openai/gpt-4o-mini"),
        help="Model for LLM-backed checks and UserSimulator (default: openai/gpt-4o-mini).",
    )
    parser.add_argument(
        "--agent-model",
        default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        help="Model used by the analytics agent (OPENAI_MODEL).",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("DATABASE_PATH", ROOT / "sample_data" / "analytics.db")),
        help="Path to SQLite database.",
    )
    return parser.parse_args()


def _build_suite_from_flags(scenarios_mod, args: argparse.Namespace):
    """Build suite and return (suite, group_labels_for_logging)."""
    if args.safety_only:
        return (
            scenarios_mod.build_suite(
                include_static=False,
                include_personas=False,
                include_safety=True,
                include_out_of_scope=False,
            ),
            scenarios_mod.scenario_groups_for_run(safety_only=True),
        )
    if args.personas_only:
        return (
            scenarios_mod.build_suite(
                include_static=False,
                include_personas=True,
                include_safety=False,
                include_out_of_scope=False,
            ),
            scenarios_mod.scenario_groups_for_run(personas_only=True),
        )
    if args.quality_only:
        return (
            scenarios_mod.build_suite(
                include_static=True,
                include_personas=not args.no_personas,
                include_safety=False,
                include_out_of_scope=True,
            ),
            scenarios_mod.scenario_groups_for_run(
                quality_only=True, no_personas=args.no_personas
            ),
        )
    return (
        scenarios_mod.build_suite(
            include_static=True,
            include_personas=not args.no_personas,
            include_safety=True,
            include_out_of_scope=True,
        ),
        scenarios_mod.scenario_groups_for_run(no_personas=args.no_personas),
    )


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
    ensure_database(args.database)

    scenarios_mod = _load_scenarios_module()
    suite, groups = _build_suite_from_flags(scenarios_mod, args)
    n = sum(len(scenarios) for scenarios in groups.values())

    set_default_generator(Generator(model=args.judge_model))

    print(f"Running {n} scenarios ({', '.join(f'{k}={len(v)}' for k, v in groups.items())})...")
    print(f"  agent model:  {args.agent_model}")
    print(f"  judge model:  {args.judge_model}")
    print(f"  database:     {args.database}\n")

    def target(inputs: str) -> dict:
        return analytics_agent(inputs, db_path=args.database)

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
