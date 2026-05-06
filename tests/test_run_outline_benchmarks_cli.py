"""CLI tests for the Outline benchmark entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_accepts_agent_profile_for_dry_run(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "benchmarks/run_outline_benchmarks.py",
            "--agent-profile",
            "codex",
            "--mode",
            "smoke",
            "--dry-run",
            "--results-dir",
            str(tmp_path),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "projected_suite_tokens=" in completed.stdout
