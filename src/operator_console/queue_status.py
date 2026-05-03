# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Velascat
"""console queue — inspect pending tasks in ~/.console/queue/."""
from __future__ import annotations

import json

from operator_console.queue import list_pending, remove

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m",
}


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


def run_queue(args: list[str]) -> int:
    # Handle cancel/remove subcommand
    if args and args[0] in ("cancel", "remove"):
        remaining = [a for a in args[1:] if not a.startswith("--")]
        if not remaining:
            print(_c("  Usage: console queue cancel <task-id>", "YLW"))
            return 1
        task_id = remaining[0]
        # Support short IDs: match by prefix
        items = list_pending()
        matched = [i for i in items if i.get("id", "").startswith(task_id)]
        if not matched:
            print(_c(f"  ✗ No task found matching id: {task_id}", "RED"))
            return 1
        if len(matched) > 1:
            print(_c(f"  ✗ Ambiguous id prefix '{task_id}' matches {len(matched)} tasks — use more characters", "RED"))
            return 1
        full_id = matched[0]["id"]
        if remove(full_id):
            print(_c(f"  ✓ Cancelled task {full_id[:8]}", "GRN"))
            return 0
        print(_c(f"  ✗ Failed to remove task {full_id[:8]}", "RED"))
        return 1

    use_json = "--json" in args
    items = list_pending()

    if use_json:
        print(json.dumps(items, indent=2, default=str, ensure_ascii=False))
        return 0

    print(_c("\n  console queue", "B", "CYN") + _c(" — pending tasks", "DIM"))
    print()

    if not items:
        print(f"  {_c('·', 'DIM')} queue is empty")
        print()
        return 0

    print(f"  {_c(str(len(items)), 'B')} task{'s' if len(items) != 1 else ''} pending\n")

    for item in items:
        task_id = item.get("id", "?")[:8]
        task_type = item.get("task_type", "?")
        repo = item.get("repo_name", "?")
        goal = item.get("goal", "?")
        submitted = (item.get("submitted_at") or "?")[:16].replace("T", " ")

        goal_disp = goal[:60] + ("…" if len(goal) > 60 else "")
        print(
            f"  {_c(task_id, 'DIM')}  "
            f"{_c(task_type, 'CYN'):<16}  "
            f"{_c(repo, 'B'):<20}  "
            f"{_c(goal_disp, 'DIM')}"
        )
        print(f"  {' ' * 8}  {_c('submitted', 'DIM')} {_c(submitted, 'DIM')}")
        print()

    return 0
