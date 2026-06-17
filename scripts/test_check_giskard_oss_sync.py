"""Tests for check_giskard_oss_sync.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

import check_giskard_oss_sync as sync


def test_load_checks_all(tmp_path: Path) -> None:
    init = tmp_path / "libs/giskard-checks/src/giskard/checks/__init__.py"
    init.parent.mkdir(parents=True)
    init.write_text(
        textwrap.dedent(
            """
            __all__ = [
                "Scenario",
                "Suite",
                "FnCheck",
            ]
            """
        ),
        encoding="utf-8",
    )
    assert sync.load_checks_all(tmp_path) == {"Scenario", "Suite", "FnCheck"}


def test_extract_documented_symbols(tmp_path: Path) -> None:
    ref = tmp_path / "rag-evaluator/references/api-reference.md"
    ref.parent.mkdir(parents=True)
    ref.write_text(
        textwrap.dedent(
            """
            ```python
            from giskard.checks import (
                Scenario, Suite,
                Groundedness,
            )
            from giskard.checks import Toxicity
            ```
            """
        ),
        encoding="utf-8",
    )
    documented = sync.extract_documented_symbols(tmp_path)
    assert documented == {"Scenario", "Suite", "Groundedness", "Toxicity"}


def test_check_sync_reports_missing_and_stale(tmp_path: Path) -> None:
    oss = tmp_path / "oss"
    skills = tmp_path / "skills"
    init = oss / sync.CHECKS_INIT
    init.parent.mkdir(parents=True)
    init.write_text('__all__ = ["Scenario", "Toxicity"]\n', encoding="utf-8")

    ref = skills / "x/references/api-reference.md"
    ref.parent.mkdir(parents=True)
    ref.write_text(
        '```python\nfrom giskard.checks import Scenario, RemovedCheck\n```\n',
        encoding="utf-8",
    )

    errors = sync.check_sync(oss, skills)
    assert any("RemovedCheck" in err for err in errors)
    assert any("Toxicity" in err for err in errors)
