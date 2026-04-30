# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Velascat
"""Session group persistence — save/restore multi-repo session composition."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

_STATE_DIR  = Path.home() / ".local" / "share" / "operator_console"
_LAST_GROUP = "last-session.json"


def save(profile_names: list[str], session_name: str) -> Path:
    """Persist the current repo group so console context can reopen it."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "session":  session_name,
        "repos":    profile_names,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    path = _STATE_DIR / _LAST_GROUP
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def load() -> dict | None:
    """Return saved group metadata or None."""
    path = _STATE_DIR / _LAST_GROUP
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
