# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""Interactive multi-repo git dirty watcher.

Displays live dirty/clean status across repo roots. Arrow keys navigate,
Enter launches lazygit for the selected repo (exec — the restart loop in
the launcher brings the watcher back when lazygit exits).

Usage: python3 -m operator_console.git_watcher <repo1> <repo2> ...
"""
from __future__ import annotations
import curses
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


# ── git helpers ───────────────────────────────────────────────────────────────

def _git_status(repo: str) -> tuple[int, int, int] | None:
    """Return (staged, modified, untracked) counts, or None on error."""
    try:
        r = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return None
        staged = modified = untracked = 0
        for line in r.stdout.splitlines():
            if len(line) < 2:
                continue
            x, y = line[0], line[1]
            if x not in (" ", "?"):
                staged += 1
            if y in ("M", "D", "A"):
                modified += 1
            if x == "?" and y == "?":
                untracked += 1
        return staged, modified, untracked
    except Exception:
        return None


def _git_branch(repo: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        return r.stdout.strip() if r.returncode == 0 else "?"
    except Exception:
        return "?"


def _dirty(s: tuple[int, int, int] | None) -> bool:
    return s is not None and any(s)


def _fmt(s: tuple[int, int, int]) -> str:
    parts = []
    if s[0]: parts.append(f"{s[0]}S")
    if s[1]: parts.append(f"{s[1]}M")
    if s[2]: parts.append(f"{s[2]}?")
    return " ".join(parts)


# ── TUI ───────────────────────────────────────────────────────────────────────

_HELP = "↑↓ navigate   ↵ lazygit (q to return)   r refresh   q quit"

_CLEAN = "✓"
_DIRTY = "✗"
_WAIT  = "…"


def _draw(stdscr, repos: list[str], statuses: dict, branches: dict, sel: int, refreshing: bool) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    C_DIM    = curses.A_DIM
    C_BOLD   = curses.A_BOLD
    C_SEL    = curses.color_pair(1)
    C_CLEAN  = curses.color_pair(2)
    C_DIRTY  = curses.color_pair(3)
    C_WAIT   = curses.color_pair(4)

    # header
    spin = " ⟳" if refreshing else "  "
    hdr = f" {_HELP}{spin}"
    stdscr.addstr(0, 0, hdr[:w - 1], C_DIM)

    # rows
    for i, repo in enumerate(repos):
        row = i + 2
        if row >= h:
            break

        name   = Path(repo).name
        branch = branches.get(repo, "?")
        s      = statuses.get(repo)

        if s is None:
            icon, detail, color = _WAIT, "", C_WAIT
        elif _dirty(s):
            icon, detail, color = _DIRTY, _fmt(s), C_DIRTY
        else:
            icon, detail, color = _CLEAN, "", C_CLEAN

        label = f" {icon}  {name:<18} {branch:<14} {detail}"
        label = label[:w - 1].ljust(w - 1)

        if i == sel:
            stdscr.attron(C_SEL | C_BOLD)
            stdscr.addstr(row, 0, label)
            stdscr.attroff(C_SEL | C_BOLD)
        else:
            stdscr.addstr(row, 0, label, color)

    stdscr.refresh()


def _watcher(stdscr, repos: list[str]) -> None:
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)   # selected
    curses.init_pair(2, curses.COLOR_GREEN,  -1)                   # clean
    curses.init_pair(3, curses.COLOR_YELLOW, -1)                   # dirty
    curses.init_pair(4, curses.COLOR_WHITE,  -1)                   # waiting

    statuses: dict[str, tuple | None] = {r: None for r in repos}
    branches: dict[str, str]          = {r: "?" for r in repos}
    sel       = 0
    refreshing = False
    lock      = threading.Lock()

    def refresh_all() -> None:
        nonlocal refreshing
        while True:
            refreshing = True
            for repo in repos:
                s = _git_status(repo)
                b = _git_branch(repo)
                with lock:
                    statuses[repo] = s
                    branches[repo] = b
            refreshing = False
            time.sleep(5)

    threading.Thread(target=refresh_all, daemon=True).start()

    # initial blocking fetch so first paint isn't all "…"
    for repo in repos:
        statuses[repo] = _git_status(repo)
        branches[repo] = _git_branch(repo)

    stdscr.timeout(500)

    while True:
        with lock:
            s_snap = dict(statuses)
            b_snap = dict(branches)

        _draw(stdscr, repos, s_snap, b_snap, sel, refreshing)

        key = stdscr.getch()

        if key in (ord("q"), 27):
            break
        elif key == curses.KEY_UP:
            sel = (sel - 1) % len(repos)
        elif key == curses.KEY_DOWN:
            sel = (sel + 1) % len(repos)
        elif key == ord("r"):
            for repo in repos:
                statuses[repo] = None
        elif key in (curses.KEY_ENTER, 10, 13):
            repo = repos[sel]
            curses.endwin()
            os.execvp("lazygit", ["lazygit", "-p", repo])


def main() -> None:
    repos = sys.argv[1:]
    if not repos:
        print("usage: python3 -m operator_console.git_watcher <repo> [<repo> ...]")
        sys.exit(1)
    repos = sorted(repos, key=lambda r: Path(r).name.casefold())
    curses.wrapper(_watcher, repos)


if __name__ == "__main__":
    main()
