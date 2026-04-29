# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""Zellij session state queries."""
from __future__ import annotations
import re
import subprocess

_ANSI = re.compile(r"\033\[[0-9;]*m")


def list_sessions() -> list[str]:
    try:
        r = subprocess.run(
            ["zellij", "list-sessions"],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            return []
        sessions = []
        for line in r.stdout.strip().splitlines():
            clean = _ANSI.sub("", line).strip()
            if clean and "EXITED" not in clean:
                sessions.append(clean.split()[0])
        return sessions
    except FileNotFoundError:
        return []


def session_exists(name: str) -> bool:
    return name in list_sessions()
