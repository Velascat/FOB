# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""Local task queue — ~/.console/queue/

Each pending task is a JSON file named <uuid>.json. OperationsCenter's
intake role polls this directory and promotes items for execution.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

TASK_TYPES = [
    ("bug",           "Something is broken"),
    ("feature",       "New functionality"),
    ("refactor",      "Improve structure without changing behaviour"),
    ("docs",          "Documentation update"),
    ("lint",          "Fix lint / formatting errors"),
    ("test",          "Add or fix tests"),
    ("chore",         "Cleanup, dependency update, config"),
    ("investigation", "Explore and report — no code change required"),
]


def queue_dir() -> Path:
    d = Path.home() / ".console" / "queue"
    d.mkdir(parents=True, exist_ok=True)
    return d


def submit(
    goal: str,
    task_type: str,
    repo_name: str,
    repo_path: str | None = None,
    priority: str = "normal",
    source: str = "operator",
) -> Path:
    """Write a task to the local queue. Returns the queue file path."""
    task_id = uuid.uuid4().hex
    payload = {
        "id": task_id,
        "goal": goal,
        "task_type": task_type,
        "repo_name": repo_name,
        "repo_path": repo_path,
        "priority": priority,
        "source": source,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    path = queue_dir() / f"{task_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def list_pending() -> list[dict]:
    """Return all pending queue items, oldest first."""
    items = []
    for f in sorted(queue_dir().glob("*.json")):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return items


def remove(task_id: str) -> bool:
    """Delete a queue item by id. Returns True if it existed."""
    path = queue_dir() / f"{task_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
