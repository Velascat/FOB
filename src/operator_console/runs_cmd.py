# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Velascat
"""console runs — list recent execution runs."""
from __future__ import annotations

import json
from pathlib import Path

from operator_console.runs import list_runs, run_summary, runs_root

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m",
}


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


def _status_mark(s: dict) -> str:
    if s.get("partial"):
        return _c("~", "YLW")
    return _c("✓", "GRN") if s.get("success") else _c("✗", "RED")


def _status_label(s: dict) -> str:
    if s.get("partial"):
        return _c("partial ", "YLW")
    status = s.get("status", "unknown")
    return _c(f"{status:<8}", "GRN" if s.get("success") else "RED")


def run_runs(args: list[str]) -> int:
    use_json = "--json" in args

    # --limit N (default 20)
    limit = 20
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
            except ValueError:
                pass

    root: Path | None = None
    for i, a in enumerate(args):
        if a == "--root" and i + 1 < len(args):
            root = Path(args[i + 1])

    all_runs = list_runs(root)
    if not all_runs:
        if use_json:
            print(json.dumps({"runs": [], "runs_root": str(runs_root())}, ensure_ascii=False))
        else:
            print(_c("  No runs found.", "DIM"))
            print(_c(f"  Expected location: {runs_root()}", "DIM"))
            print(_c("  Run `console run` or `console demo` to create a run.", "DIM"))
        return 1

    # Most recent first, limited
    recent = list(reversed(all_runs))[:limit]
    summaries = [run_summary(r) for r in recent]

    if use_json:
        print(json.dumps({"runs": summaries, "total": len(all_runs)}, indent=2, default=str, ensure_ascii=False))
        return 0

    total = len(all_runs)
    showing = len(recent)
    print(_c("\n  console runs", "B", "CYN") + _c(f" — recent executions ({showing}/{total})", "DIM"))
    print()

    header = (
        f"  {'':2}  {'run id':<8}  {'status  ':<8}  {'source':<10}  {'lane':<16}  {'written':<19}  goal"
    )
    print(_c(header, "DIM"))
    print(_c("  " + "─" * 100, "DIM"))

    for s in summaries:
        mark = _status_mark(s)
        status_l = _status_label(s)
        run_id_short = s["run_id"][:8]
        source = (s.get("source") or "—")[:9]
        lane = (s.get("selected_lane") or "?")[:15]
        written = (s.get("written_at") or "?")[:19].replace("T", " ")
        goal = (s.get("goal_text") or "")[:38]
        if len(s.get("goal_text") or "") > 38:
            goal += "…"

        print(f"  {mark}  {_c(run_id_short, 'DIM')}  {status_l}  {_c(source, 'DIM'):<19}  "
              f"{_c(lane, 'DIM'):<25}  {_c(written, 'DIM')}  {goal}")

    print()

    if total > limit:
        print(_c(f"  · {total - limit} older runs not shown — use --limit to see more", "DIM"))
        print()

    print(_c(f"  artifacts: {runs_root()}", "DIM"))
    print()
    return 0
