# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""console clean — remove old run artifacts, keeping the most recent N runs."""
from __future__ import annotations

import shutil
from pathlib import Path

from operator_console.runs import list_runs, runs_root

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m",
}


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


def _parse_args(args: list[str]) -> dict:
    parsed = {"keep": 10, "yes": False, "root": None, "dry_run": False}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--keep" and i + 1 < len(args):
            try:
                parsed["keep"] = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif a in ("-y", "--yes"):
            parsed["yes"] = True; i += 1
        elif a == "--dry-run":
            parsed["dry_run"] = True; i += 1
        elif a == "--root" and i + 1 < len(args):
            parsed["root"] = Path(args[i + 1]); i += 2
        else:
            i += 1
    return parsed


def run_clean(args: list[str]) -> int:
    opts = _parse_args(args)
    keep = max(1, opts["keep"])
    root = opts["root"]

    all_runs = list_runs(root)
    if not all_runs:
        print(_c("  No runs found — nothing to clean.", "DIM"))
        return 0

    to_delete = all_runs[:-keep] if len(all_runs) > keep else []
    if not to_delete:
        print(_c(f"  {len(all_runs)} run(s) present — fewer than keep={keep}, nothing to remove.", "DIM"))
        return 0

    print(_c(f"\n  console clean", "B", "CYN") + _c(f" — keeping {keep} most recent runs", "DIM"))
    print()
    print(_c(f"  Total runs : {len(all_runs)}", "DIM"))
    print(_c(f"  To delete  : {len(to_delete)}", "DIM"))
    print(_c(f"  To keep    : {len(all_runs) - len(to_delete)}", "DIM"))
    print()

    for run_dir in to_delete:
        print(f"  {_c('·', 'DIM')} {run_dir.name}")
    print()

    if opts["dry_run"]:
        print(_c("  --dry-run: no files deleted.", "YLW"))
        return 0

    if not opts["yes"]:
        try:
            answer = input(_c(f"  Delete {len(to_delete)} run(s)? [y/N] ", "B")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if answer not in ("y", "yes"):
            print(_c("  Cancelled.", "DIM"))
            return 0

    deleted = 0
    for run_dir in to_delete:
        try:
            shutil.rmtree(run_dir)
            deleted += 1
        except Exception as exc:
            print(f"  {_c('✗', 'RED')} failed to delete {run_dir.name}: {exc}")

    print(_c(f"  ✓ Deleted {deleted} run(s).", "GRN"))
    print(_c(f"  · artifacts: {runs_root()}", "DIM"))
    print()
    return 0
