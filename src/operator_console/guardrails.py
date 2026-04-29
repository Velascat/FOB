# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""Branch and command guardrails."""
from __future__ import annotations
import subprocess
from pathlib import Path

PROTECTED_BRANCHES = {"main", "master"}

_C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "green": "\033[32m",
    "dim": "\033[2m",
}


def _c(text: str, *codes: str) -> str:
    prefix = "".join(_C[k] for k in codes)
    return f"{prefix}{text}{_C['reset']}"


def get_branch(repo_root: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        return r.stdout.strip() or None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def check_branch(repo_root: Path, force: bool = False) -> None:
    """Warn (but don't block) if on a protected branch."""
    branch = get_branch(repo_root)
    if branch is None:
        return
    if branch in PROTECTED_BRANCHES:
        print(_c(f"⚠  Launching from protected branch: {branch}", "yellow", "bold"))
        print(_c("   Claude's guardrails.md will enforce branch discipline.", "dim"))
        print(_c("   To override: console open <profile> --force-branch", "dim"))
        print()
