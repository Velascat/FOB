# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Velascat
"""runs.py — read Phase 7 canonical run artifacts from ~/.console/operations_center/runs/.

Provides lightweight accessors so pipeline commands (console last, console status, etc.)
never need to navigate artifact directories directly.
"""
from __future__ import annotations

import json
from pathlib import Path

_RUNS_ROOT = Path.home() / ".console" / "operations_center" / "runs"


def runs_root() -> Path:
    return _RUNS_ROOT


def _run_sort_key(p: Path) -> str:
    """Sort key for a run directory: written_at timestamp, or empty string (sorts first)."""
    try:
        meta = json.loads((p / "run_metadata.json").read_text(encoding="utf-8"))
        return meta.get("written_at", "") or ""
    except Exception:
        return ""


def list_runs(root: Path | None = None) -> list[Path]:
    """Return run directories sorted oldest-first by written_at timestamp."""
    r = root or _RUNS_ROOT
    if not r.exists():
        return []
    dirs = [p for p in r.iterdir() if p.is_dir() and (p / "run_metadata.json").exists()]
    return sorted(dirs, key=_run_sort_key)


def latest_run(root: Path | None = None) -> Path | None:
    """Return the most recent run directory, or None if no runs exist."""
    runs = list_runs(root)
    return runs[-1] if runs else None


def read_json(path: Path) -> dict:
    """Read a JSON file, returning {} on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_metadata(run_dir: Path) -> dict:
    return read_json(run_dir / "run_metadata.json")


def read_result(run_dir: Path) -> dict:
    return read_json(run_dir / "result.json")


def read_proposal(run_dir: Path) -> dict:
    return read_json(run_dir / "proposal.json")


def read_decision(run_dir: Path) -> dict:
    return read_json(run_dir / "decision.json")


def run_summary(run_dir: Path) -> dict:
    """Return a flat summary dict for display — merges metadata + result + proposal + decision fields."""
    meta = read_metadata(run_dir)
    result = read_result(run_dir)
    proposal = read_proposal(run_dir)
    decision = read_decision(run_dir)

    # Prefer metadata for lane/backend (written at execution time); fall back to decision
    selected_lane = meta.get("selected_lane") or decision.get("selected_lane", "?")
    selected_backend = meta.get("selected_backend") or decision.get("selected_backend", "?")

    return {
        "run_id": meta.get("run_id", run_dir.name),
        "status": meta.get("status", result.get("status", "unknown")),
        "success": meta.get("success", result.get("success")),
        "executed": meta.get("executed"),
        "selected_lane": selected_lane,
        "selected_backend": selected_backend,
        "failure_category": meta.get("failure_category"),
        "failure_reason": result.get("failure_reason"),
        "written_at": meta.get("written_at"),
        "partial": meta.get("partial", False),
        "source": meta.get("source"),
        "goal_text": proposal.get("goal_text"),
        "task_type": proposal.get("task_type"),
        "repo_key": proposal.get("target", {}).get("repo_key"),
        "artifacts_dir": str(run_dir),
        # Decision fields (populated when decision.json is present)
        "decision_basis": decision.get("policy_rule_matched") or decision.get("rationale"),
        "decision_confidence": decision.get("confidence"),
    }
