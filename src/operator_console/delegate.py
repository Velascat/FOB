# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""console run — submit a task to the local queue for OperationsCenter intake.

Interactive wizard (repo → task type → goal) writes a JSON task file to
~/.console/queue/. OperationsCenter's intake role picks it up, elaborates
it using repo context, and drives it through the execution pipeline.

Non-interactive fast path:
    console run --goal "Fix the login bug" --task-type bug --repo myrepo

Exit codes:
    0  task submitted successfully
    1  cancelled or missing required input
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from operator_console.queue import TASK_TYPES, submit

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m", "MAG": "\033[35m",
}


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


def _ok(msg: str) -> None:
    print(f"  {_c('✓', 'GRN')} {msg}")


def _fail(msg: str) -> None:
    print(f"  {_c('✗', 'RED')} {msg}")


def _info(msg: str) -> None:
    print(f"  {_c('·', 'DIM')} {msg}")


def _has_fzf() -> bool:
    try:
        return subprocess.run(["fzf", "--version"], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def _fzf_pick(items: list[str], prompt: str, header: str = "") -> str | None:
    """Single-select via fzf. Returns selected line or None if cancelled."""
    args = ["fzf", "--prompt", prompt, "--height", "12",
            "--border", "--no-sort", "--ansi"]
    if header:
        args += ["--header-first", "--header", header]
    result = subprocess.run(args, input="\n".join(items), text=True, stdout=subprocess.PIPE)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip()


def _numbered_pick(items: list[str], prompt: str) -> str | None:
    """Fallback numbered picker when fzf is not available."""
    for i, item in enumerate(items, 1):
        print(f"  {_c(str(i), 'YLW')}  {item}")
    print()
    try:
        raw = input(_c(f"  {prompt} [1-{len(items)}]: ", "B")).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(items):
            return items[idx]
    except ValueError:
        pass
    return None


def _pick(items: list[str], prompt: str, header: str = "") -> str | None:
    if _has_fzf():
        return _fzf_pick(items, f"  {prompt} > ", header)
    return _numbered_pick(items, prompt)


def _discover_repos() -> dict[str, Path]:
    """Return name→path for all git repos under ~/Documents/GitHub/."""
    github = Path.home() / "Documents" / "GitHub"
    repos: dict[str, Path] = {}
    if github.is_dir():
        for d in sorted(github.iterdir()):
            if d.is_dir() and (d / ".git").exists():
                repos[d.name] = d
    return repos


def _parse_args(args: list[str]) -> dict:
    parsed: dict = {
        "goal": None,
        "task_type": None,
        "repo": None,
        "priority": "normal",
        "json": False,
    }
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--goal" and i + 1 < len(args):
            parsed["goal"] = args[i + 1]; i += 2
        elif a == "--task-type" and i + 1 < len(args):
            parsed["task_type"] = args[i + 1]; i += 2
        elif a == "--repo" and i + 1 < len(args):
            parsed["repo"] = args[i + 1]; i += 2
        elif a == "--priority" and i + 1 < len(args):
            parsed["priority"] = args[i + 1]; i += 2
        elif a == "--json":
            parsed["json"] = True; i += 1
        else:
            i += 1
    return parsed


def run_delegate(args: list[str], profile_repos: dict[str, Path] | None = None) -> int:
    opts = _parse_args(args)
    interactive = sys.stdin.isatty()

    print(_c("\n  console run", "B", "CYN") + _c(" — submit task to queue", "DIM"))
    print()

    # ── Step 1: Repo ─────────────────────────────────────────────────────────

    repos = profile_repos if profile_repos is not None else _discover_repos()

    # Auto-detect from cwd
    cwd = Path.cwd()
    auto_repo: str | None = None
    for name, path in repos.items():
        try:
            cwd.relative_to(path)
            auto_repo = name
            break
        except ValueError:
            pass

    repo_name: str | None = opts["repo"]
    repo_path: str | None = None

    if not repo_name:
        if auto_repo:
            repo_name = auto_repo
            repo_path = str(repos[auto_repo])
            _info(f"repo: {_c(repo_name, 'B')}  (auto-detected from cwd)")
        elif interactive and repos:
            print(_c("  Select repo:", "B"))
            lines = [f"{name}  {_c(str(path), 'DIM')}" for name, path in repos.items()]
            chosen = _pick(lines, "repo", "\033[93mEnter\033[0m to select")
            if not chosen:
                _fail("cancelled")
                return 1
            repo_name = chosen.split()[0]
            repo_path = str(repos[repo_name]) if repo_name in repos else None
        elif not interactive:
            _fail("--repo is required in non-interactive mode")
            return 1
        else:
            _fail("no git repos found under ~/Documents/GitHub/")
            return 1
    else:
        repo_path = str(repos[repo_name]) if repo_name in repos else None

    # ── Step 2: Task type ────────────────────────────────────────────────────

    task_type: str | None = opts["task_type"]

    if not task_type:
        if interactive:
            print()
            print(_c("  Task type:", "B"))
            type_lines = [
                f"{_c(t, 'CYN'):<24}  {_c(desc, 'DIM')}"
                for t, desc in TASK_TYPES
            ]
            chosen = _pick(type_lines, "type", "\033[93mEnter\033[0m to select")
            if not chosen:
                _fail("cancelled")
                return 1
            # extract the type token (first word, strip ansi)
            import re
            task_type = re.sub(r"\033\[[0-9;]*m", "", chosen).strip().split()[0]
        else:
            task_type = "chore"

    valid_types = {t for t, _ in TASK_TYPES}
    if task_type not in valid_types:
        _fail(f"unknown task type: {task_type!r}  (valid: {', '.join(sorted(valid_types))})")
        return 1

    # ── Step 3: Goal ─────────────────────────────────────────────────────────

    goal: str | None = opts["goal"]

    if not goal:
        if interactive:
            print()
            try:
                goal = input(_c("  What's the problem?\n  > ", "B")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                _fail("cancelled")
                return 1
        if not goal:
            _fail("goal is required")
            return 1

    # ── Submit ────────────────────────────────────────────────────────────────

    print()
    queue_file = submit(
        goal=goal,
        task_type=task_type,
        repo_name=repo_name,
        repo_path=repo_path,
        priority=opts["priority"],
        source="operator",
    )

    if opts["json"]:
        import json
        print(json.dumps({
            "queued": True,
            "file": str(queue_file),
            "repo": repo_name,
            "task_type": task_type,
            "goal": goal,
        }, indent=2))
    else:
        _ok(f"queued  {_c(repo_name, 'B')}  {_c(task_type, 'CYN')}  {_c(repr(goal), 'DIM')}")
        _info(f"queue: {queue_file}")
        _info("OperationsCenter intake will pick this up and elaborate it")
        print()

    return 0
