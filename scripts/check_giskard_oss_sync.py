#!/usr/bin/env python3
"""Verify skill api-reference import blocks match giskard.checks public exports.

Compares ``__all__`` from giskard-oss ``giskard/checks/__init__.py`` against
``from giskard.checks import (...)`` blocks in skill reference markdown files.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS_ROOT = REPO_ROOT / "oss" / "checks"
DEFAULT_GISKARD_OSS = REPO_ROOT / "giskard-oss"
CHECKS_INIT = Path("libs/giskard-checks/src/giskard/checks/__init__.py")

IMPORT_BLOCK_RE = re.compile(
    r"from\s+giskard\.checks\s+import\s+\((.*?)\)",
    re.DOTALL,
)
IMPORT_LINE_RE = re.compile(
    r"from\s+giskard\.checks\s+import\s+([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)"
)

# Public exports that skills need not list in import blocks (modules, runners, etc.).
ALLOW_UNDOCUMENTED = frozenset(
    {
        "__version__",
        "builtin",
        "judges",
        "ScenarioRunner",
        "TestCaseRunner",
        "resolve",
        "InputGenerationException",
        "BaseLLMGenerator",
        "LLMGenerator",
        "Target",
        "TestCase",
        "TestCaseResult",
    }
)

API_REFERENCE_GLOBS = (
    "**/references/api-reference.md",
)


def load_checks_all(giskard_oss_path: Path) -> set[str]:
    init_path = giskard_oss_path / CHECKS_INIT
    if not init_path.is_file():
        raise FileNotFoundError(f"giskard.checks __init__ not found: {init_path}")

    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    value = node.value
                    if isinstance(value, (ast.List, ast.Tuple)):
                        return {
                            elt.value
                            for elt in value.elts
                            if isinstance(elt, ast.Constant)
                            and isinstance(elt.value, str)
                        }
    raise ValueError(f"No __all__ found in {init_path}")


def _symbols_from_import_body(body: str) -> set[str]:
    symbols: set[str] = set()
    for part in body.split(","):
        token = part.strip()
        if not token or token.startswith("#"):
            continue
        name = token.split()[0]
        if name.isidentifier():
            symbols.add(name)
    return symbols


def extract_documented_symbols(skills_root: Path) -> set[str]:
    documented: set[str] = set()
    for pattern in API_REFERENCE_GLOBS:
        for path in skills_root.glob(pattern):
            text = path.read_text(encoding="utf-8")
            for match in IMPORT_BLOCK_RE.finditer(text):
                documented |= _symbols_from_import_body(match.group(1))
            for match in IMPORT_LINE_RE.finditer(text):
                documented |= _symbols_from_import_body(match.group(1))
    return documented


def check_sync(giskard_oss_path: Path, skills_root: Path) -> list[str]:
    errors: list[str] = []
    public = load_checks_all(giskard_oss_path)
    documented = extract_documented_symbols(skills_root)

    stale = sorted(documented - public)
    if stale:
        errors.append(
            "Documented in skill import blocks but missing from giskard.checks __all__: "
            + ", ".join(stale)
        )

    missing = sorted(
        name
        for name in public - documented - ALLOW_UNDOCUMENTED
    )
    if missing:
        errors.append(
            "In giskard.checks __all__ but not in any skill api-reference import block "
            f"(add to references/api-reference.md or ALLOW_UNDOCUMENTED): "
            + ", ".join(missing)
        )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--giskard-oss-path",
        type=Path,
        default=DEFAULT_GISKARD_OSS,
        help="Path to a giskard-oss checkout (default: ./giskard-oss)",
    )
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=DEFAULT_SKILLS_ROOT,
        help="Path to oss/checks skill tree",
    )
    args = parser.parse_args(argv)

    if not args.giskard_oss_path.is_dir():
        print(
            f"error: giskard-oss path not found: {args.giskard_oss_path}\n"
            "Clone it alongside this repo or pass --giskard-oss-path.",
            file=sys.stderr,
        )
        return 2

    try:
        errors = check_sync(args.giskard_oss_path, args.skills_root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("giskard-oss sync check FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    public = load_checks_all(args.giskard_oss_path)
    documented = extract_documented_symbols(args.skills_root)
    print(
        f"OK: {len(documented)} documented symbols; "
        f"{len(public)} in __all__; "
        f"{len(ALLOW_UNDOCUMENTED)} allowlisted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
