"""runs.py — read Phase 7 canonical run artifacts from ~/.fob/control_plane/runs/.

Provides lightweight accessors so cockpit commands (fob last, fob status, etc.)
never need to navigate artifact directories directly.
"""
from __future__ import annotations

import json
from pathlib import Path

_RUNS_ROOT = Path.home() / ".fob" / "control_plane" / "runs"


def runs_root() -> Path:
    return _RUNS_ROOT


def list_runs(root: Path | None = None) -> list[Path]:
    """Return sorted run directories (oldest first) from the artifact root."""
    r = root or _RUNS_ROOT
    if not r.exists():
        return []
    return sorted(p for p in r.iterdir() if p.is_dir() and (p / "run_metadata.json").exists())


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
    """Return a flat summary dict for display — merges metadata + result + proposal fields."""
    meta = read_metadata(run_dir)
    result = read_result(run_dir)
    proposal = read_proposal(run_dir)

    return {
        "run_id": meta.get("run_id", run_dir.name),
        "status": meta.get("status", result.get("status", "unknown")),
        "success": meta.get("success", result.get("success")),
        "executed": meta.get("executed"),
        "selected_lane": meta.get("selected_lane", "?"),
        "selected_backend": meta.get("selected_backend", "?"),
        "failure_category": meta.get("failure_category"),
        "failure_reason": result.get("failure_reason"),
        "written_at": meta.get("written_at"),
        "partial": meta.get("partial", False),
        "goal_text": proposal.get("goal_text"),
        "task_type": proposal.get("task_type"),
        "repo_key": proposal.get("target", {}).get("repo_key"),
        "artifacts_dir": str(run_dir),
    }
