"""console auto-once — execute exactly one autonomous cycle.

Observe → Propose → Decide → Execute → Record

Reads goal from .console/task.md (or --goal override), then drives the
full OperationsCenter pipeline via run_delegate(). Canonical run artifacts are
written to ~/.console/operations_center/runs/<run_id>/ by the execute entrypoint.
"""
from __future__ import annotations

from pathlib import Path

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m",
}


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


def _info(msg: str) -> None:
    print(f"  {_c('·', 'DIM')} {msg}")


def _ok(msg: str) -> None:
    print(f"  {_c('✓', 'GRN')} {msg}")


def _fail(msg: str) -> None:
    print(f"  {_c('✗', 'RED')} {msg}")


def run_auto_once(args: list[str]) -> int:
    """Single-cycle autonomy loop. Returns 0 on success, 1 on failure."""
    from operator_console.observer import observe
    from operator_console.delegate import run_delegate

    use_json = "--json" in args
    dry_run = "--dry-run" in args

    if not use_json:
        print(_c("\n  console cycle", "B", "CYN") + _c(" — single autonomous cycle", "DIM"))
        print()

    # Observe: derive goal context from local state
    context = observe(args)

    if not use_json:
        source_label = {"arg": "flag", "file": "task.md", "default": "default"}.get(
            context["source"], context["source"]
        )
        _info(f"goal source: {_c(source_label, 'B')}")
        _info(f"goal: {context['goal']!r}")
        _info(f"repo: {context['repo_key']}  ({context['clone_url']})")
        print()

    # Build delegate args from observed context
    delegate_args = [
        "--goal", context["goal"],
        "--task-type", context["task_type"],
        "--repo-key", context["repo_key"],
        "--clone-url", context["clone_url"],
        "--source", "auto_once",
    ]
    if use_json:
        delegate_args.append("--json")
    if dry_run:
        delegate_args.append("--dry-run")

    return run_delegate(delegate_args)
