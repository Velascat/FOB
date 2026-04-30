# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Velascat
"""Layout persistence — save, load, show, reset OperatorConsole workspace layouts."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

LAYOUT_JSON = "layout.json"
LAYOUT_KDL  = "layout.kdl"
BACKEND     = "zellij"


def _json_path(repo_root: Path) -> Path:
    return repo_root / ".console" / LAYOUT_JSON


def _kdl_path(repo_root: Path) -> Path:
    return repo_root / ".console" / LAYOUT_KDL


def save(repo_root: Path, profile_name: str, kdl_content: str) -> dict:
    """Write layout KDL + metadata. Returns the metadata dict."""
    console_dir = repo_root / ".console"
    console_dir.mkdir(exist_ok=True)
    _kdl_path(repo_root).write_text(kdl_content, encoding="utf-8")
    meta = {
        "backend":      BACKEND,
        "repo_root":    str(repo_root.resolve()),
        "profile_name": profile_name,
        "saved_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "kdl_file":     f".console/{LAYOUT_KDL}",
    }
    _json_path(repo_root).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def load(repo_root: Path) -> tuple[dict, Path] | None:
    """Return (metadata, kdl_path) or None if no valid saved layout."""
    jp = _json_path(repo_root)
    kp = _kdl_path(repo_root)
    if not jp.exists() or not kp.exists():
        return None
    try:
        meta = json.loads(jp.read_text(encoding="utf-8"))
    except Exception:
        return None
    saved_root = Path(meta.get("repo_root", "")).resolve()
    if saved_root != repo_root.resolve():
        return None  # stale / moved repo
    return meta, kp


def load_any(repo_root: Path) -> tuple[dict, Path, bool] | None:
    """Like load() but also returns stale layouts so show/reset still work.

    Returns (meta, kdl_path, is_current) or None if nothing exists.
    """
    jp = _json_path(repo_root)
    kp = _kdl_path(repo_root)
    if not jp.exists() or not kp.exists():
        return None
    try:
        meta = json.loads(jp.read_text(encoding="utf-8"))
    except Exception:
        return None
    saved_root = Path(meta.get("repo_root", "")).resolve()
    is_current = saved_root == repo_root.resolve()
    return meta, kp, is_current


def reset(repo_root: Path) -> list[Path]:
    """Delete saved layout files. Returns list of deleted paths."""
    deleted = []
    for p in [_json_path(repo_root), _kdl_path(repo_root)]:
        if p.exists():
            p.unlink()
            deleted.append(p)
    return deleted
