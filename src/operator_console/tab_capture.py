# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""Capture live Zellij tab layout for profile save/restore."""
from __future__ import annotations
import subprocess
from pathlib import Path


def dump_live_layout() -> str | None:
    try:
        r = subprocess.run(
            ["zellij", "action", "dump-layout"],
            capture_output=True, text=True,
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None



def _collect_body(lines: list[str], tab_start: int) -> list[str]:
    """Collect lines inside a tab block (after the opening brace line)."""
    depth = 0
    body: list[str] = []
    past_open = False
    for line in lines[tab_start:]:
        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        if not past_open:
            past_open = True
            continue  # skip "tab name=... {" itself
        if depth == 0:
            break
        body.append(line)
    return body


def _filter_chrome(lines: list[str]) -> list[str]:
    """Remove tab-bar and status-bar chrome pane blocks."""
    result: list[str] = []
    block: list[str] = []
    depth = 0

    for line in lines:
        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        block.append(line)
        if depth == 0 and block:
            text = "\n".join(block)
            is_chrome = (
                'plugin location="zellij:tab-bar"' in text
                or 'plugin location="zellij:status-bar"' in text
                or 'plugin location="tab-bar"' in text
                or 'plugin location="status-bar"' in text
            )
            if not is_chrome:
                result.extend(block)
            block = []

    return result


def extract_panes_kdl(kdl: str, tab_name: str | None = None) -> str | None:
    """Extract inner content panes from a tab in dump-layout output.

    Returns KDL with no layout wrapper, no tab wrapper, no chrome plugins —
    ready to embed directly inside a tab or session layout block.
    """
    lines = kdl.splitlines()

    # Find tab start index
    tab_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("tab ") and "{" in s:
            if tab_name is None or f'name="{tab_name}"' in s:
                tab_start = i
                break
    if tab_start is None:
        return None

    body = _collect_body(lines, tab_start)
    content = _filter_chrome(body)

    while content and not content[0].strip():
        content.pop(0)
    while content and not content[-1].strip():
        content.pop()

    return "\n".join(content) if content else None


def focused_tab_name(kdl: str) -> str | None:
    """Return the name of the focused tab in a dump-layout string."""
    for line in kdl.splitlines():
        s = line.strip()
        if s.startswith("tab ") and "focus=true" in s and 'name="' in s:
            start = s.index('name="') + 6
            end = s.index('"', start)
            return s[start:end]
    return None
