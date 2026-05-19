# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 ProtocolWarden
"""Interactive multi-repo git dirty watcher.

Displays live dirty/clean status across repo roots, grouped by component.
Arrow keys navigate, Enter launches lazygit for the selected repo (exec —
the restart loop in the launcher brings the watcher back when lazygit exits).

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

# ── component groups ──────────────────────────────────────────────────────────
# Each entry: (display label, frozenset of canonical repo folder names).
# Repos not matched by any group land in "Other".

_GROUPS: list[tuple[str, frozenset[str]]] = [
    ("Orchestration", frozenset({"OperationsCenter", "SwitchBoard"})),
    ("Executors",     frozenset({"TeamExecutor", "DAGExecutor", "CritiqueExecutor", "ExecutorRuntime"})),
    ("Contracts",     frozenset({"CxRP", "RxP"})),
    ("Platform",      frozenset({"PlatformDeployment", "PlatformManifest", "Custodian", "SourceRegistry"})),
    ("Console",       frozenset({"OperatorConsole"})),
    ("Library",       frozenset({"RepoGraph"})),
    ("Web",           frozenset({"ProtocolWarden.github.io", "ProtocolWarden"})),
]

_HINT_CHUNKS: tuple[str, ...] = (
    "↑↓ Navigate",
    "↵ lazygit",
    "g Next Group",
    "c Collapse Group",
    "x Collapse All",
    "e Expand All",
    "r Refresh",
    "? Hints",
    "q Quit",
)


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
    if s[0]:
        parts.append(f"{s[0]}S")
    if s[1]:
        parts.append(f"{s[1]}M")
    if s[2]:
        parts.append(f"{s[2]}?")
    return " ".join(parts)


# ── layout helpers ────────────────────────────────────────────────────────────

def _group_repos(repos: list[str]) -> list[tuple[str, list[str]]]:
    """Return [(group_label, [repo_path, ...]), ...] preserving group order."""
    by_name: dict[str, str] = {Path(r).name: r for r in repos}
    assigned: set[str] = set()
    result: list[tuple[str, list[str]]] = []
    for label, members in _GROUPS:
        grp = [by_name[n] for n in members if n in by_name]
        if grp:
            grp.sort(key=lambda r: Path(r).name.casefold())
            result.append((label, grp))
            assigned.update(Path(r).name for r in grp)
    other = sorted(
        [r for r in repos if Path(r).name not in assigned],
        key=lambda r: Path(r).name.casefold(),
    )
    if other:
        result.append(("Other", other))
    return result


def _build_items(groups: list[tuple[str, list[str]]]) -> list[dict]:
    """Flat list of header/repo items. Each repo item carries its group label."""
    items: list[dict] = []
    for label, grp_repos in groups:
        items.append({"kind": "header", "label": label, "repos": grp_repos})
        for repo in grp_repos:
            items.append({"kind": "repo", "path": repo, "group": label})
    return items


def _navigable(items: list[dict], collapsed: set[str]) -> list[int]:
    """Indices of repo items whose group is not collapsed."""
    return [
        i for i, it in enumerate(items)
        if it["kind"] == "repo" and it["group"] not in collapsed
    ]


def _header_indices(items: list[dict]) -> list[int]:
    return [i for i, it in enumerate(items) if it["kind"] == "header"]


def _wrap_hints(chunks: tuple[str, ...], width: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for chunk in chunks:
        candidate = chunk if not cur else f"{cur}  {chunk}"
        if len(candidate) <= width:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = chunk if len(chunk) <= width else chunk[:width]
    if cur:
        lines.append(cur)
    return lines or [""]


# ── drawing ───────────────────────────────────────────────────────────────────

def _put(stdscr, row: int, h: int, w: int, text: str, attr: int = 0) -> None:
    if row < 0 or row >= h:
        return
    try:
        stdscr.addstr(row, 0, text[: w - 1].ljust(min(len(text) + 1, w - 1)), attr)
    except curses.error:
        pass


def _sep(stdscr, row: int, h: int, w: int, attr: int) -> int:
    _put(stdscr, row, h, w, "─" * (w - 1), attr)
    return row + 1


def _build_vbuf(
    groups: list[tuple[str, list[str]]],
    items: list[dict],
    statuses: dict,
    branches: dict,
    sel_item: int,
    collapsed_groups: set[str],
    w: int,
    C: dict,
) -> tuple[list[tuple[str, int]], int]:
    """Build the full virtual line buffer for the scrollable body.

    Returns (lines, sel_vrow) where lines is a list of (text, attr) and
    sel_vrow is the virtual row index of the selected repo (or 0).
    """
    name_w   = max((len(Path(r).name) for _, gr in groups for r in gr), default=18)
    branch_w = max((len(branches.get(r, "?")) for _, gr in groups for r in gr), default=10)
    name_w   = min(name_w, 30)
    branch_w = min(branch_w, 20)

    SEP  = ("─" * (w - 1), C["DIM"])
    vbuf: list[tuple[str, int]] = []
    sel_vrow = 0

    for item_idx, item in enumerate(items):
        if item["kind"] == "header":
            label     = item["label"]
            grp_repos = item["repos"]
            is_coll   = label in collapsed_groups
            chevron   = "▸" if is_coll else "▾"

            n_dirty = sum(1 for r in grp_repos if _dirty(statuses.get(r)))
            n_wait  = sum(1 for r in grp_repos if statuses.get(r) is None)
            if n_dirty:
                tag  = f"{n_dirty} dirty"
                attr = C["YLW"] | curses.A_BOLD
            elif n_wait and not is_coll:
                tag  = "…"
                attr = C["DIM"] | curses.A_BOLD
            else:
                tag  = "clean"
                attr = C["RUN"] | curses.A_BOLD
            if is_coll:
                hdr_text = f" {chevron} {label}  ({len(grp_repos)} repos, {tag}) [collapsed]"
                attr     = C["DIM"] | curses.A_BOLD
            else:
                hdr_text = f" {chevron} {label}  ({len(grp_repos)} repos, {tag})"

            if vbuf:  # no leading sep before the very first group
                vbuf.append(SEP)
            vbuf.append((hdr_text[: w - 1], attr))

        else:
            if item["group"] in collapsed_groups:
                continue

            repo   = item["path"]
            name   = Path(repo).name
            branch = branches.get(repo, "?")
            s      = statuses.get(repo)

            if s is None:
                icon, detail, c_attr = "…", "", C["DIM"]
            elif _dirty(s):
                icon, detail, c_attr = "✗", _fmt(s), C["YLW"]
            else:
                icon, detail, c_attr = "✓", "", C["RUN"]

            line = f"  {icon}  {name:<{name_w}} {branch:<{branch_w}} {detail}"
            line = line[: w - 1].ljust(w - 1)

            if item_idx == sel_item:
                sel_vrow = len(vbuf)
                vbuf.append((line, C["SEL"] | curses.A_BOLD))
            else:
                vbuf.append((line, c_attr))

    if vbuf:
        vbuf.append(SEP)
    return vbuf, sel_vrow


def _draw(
    stdscr,
    groups: list[tuple[str, list[str]]],
    items: list[dict],
    statuses: dict,
    branches: dict,
    sel_item: int,
    refreshing: bool,
    hints_collapsed: bool,
    collapsed_groups: set[str],
    scroll_offset: int,
    C: dict,
) -> tuple[int, int]:
    """Render the watcher. Returns (sel_vrow, total_vrows) for scroll bookkeeping."""
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    # ── header bar ────────────────────────────────────────────────────────────
    spin  = " ⟳" if refreshing else ""
    ts    = time.strftime("%H:%M:%S")
    title = "  Git Watcher"
    right = f"{ts}{spin}  "
    pad   = max(0, w - 1 - len(title) - len(right))
    hdr   = (title + " " * pad + right)[: w - 1]
    _sep(stdscr, 0, h, w, C["DIM"])
    _put(stdscr, 1, h, w, hdr, C["HEAD"] | curses.A_BOLD)
    _sep(stdscr, 2, h, w, C["DIM"])

    # ── hints footer (anchored) ───────────────────────────────────────────────
    if hints_collapsed:
        hint_lines: list[str] = [" ? Hints  (Press ? to Expand)"]
    else:
        hint_lines = [" " + ln for ln in _wrap_hints(_HINT_CHUNKS, max(1, w - 2))]
    hint_h      = len(hint_lines)
    footer_rows = 2 + hint_h   # sep-above + hints + sep-below
    body_bottom = h - footer_rows

    _sep(stdscr, body_bottom, h, w, C["DIM"])
    for i, line in enumerate(hint_lines):
        _put(stdscr, body_bottom + 1 + i, h, w, line, C["MUTED"])
    _sep(stdscr, body_bottom + 1 + hint_h, h, w, C["DIM"])

    # ── scrollable body ───────────────────────────────────────────────────────
    body_h   = max(0, body_bottom - 3)  # rows 0-2 are sep/header/sep
    vbuf, sel_vrow = _build_vbuf(
        groups, items, statuses, branches, sel_item, collapsed_groups, w, C
    )
    total_vrows = len(vbuf)

    visible = vbuf[scroll_offset: scroll_offset + body_h]
    for screen_row, (text, attr) in enumerate(visible):
        _put(stdscr, 3 + screen_row, h, w, text, attr)

    stdscr.refresh()
    return sel_vrow, total_vrows


# ── main loop ─────────────────────────────────────────────────────────────────

def _watcher(stdscr, repos: list[str]) -> None:
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK,  curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_GREEN,  -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_RED,    -1)
    curses.init_pair(5, curses.COLOR_WHITE,  -1)

    C = {
        "SEL":   curses.color_pair(1),
        "RUN":   curses.color_pair(2),
        "YLW":   curses.color_pair(3),
        "ERR":   curses.color_pair(4),
        "HEAD":  curses.color_pair(5),
        "DIM":   curses.color_pair(5) | curses.A_DIM,
        "MUTED": curses.color_pair(5),
    }

    statuses: dict[str, tuple | None] = {r: None for r in repos}
    branches: dict[str, str]          = {r: "?" for r in repos}
    refreshing       = False
    hints_collapsed  = True
    collapsed_groups: set[str] = set()   # all open by default
    scroll_offset    = 0
    total_vrows      = 0
    body_h           = 1
    lock             = threading.Lock()

    groups   = _group_repos(repos)
    all_labels = [label for label, _ in groups]
    items    = _build_items(groups)
    hdr_idxs = _header_indices(items)

    def nav_idxs() -> list[int]:
        return _navigable(items, collapsed_groups)

    # start selection on first navigable repo
    sel_item = nav_idxs()[0] if nav_idxs() else 0

    def _current_group() -> str | None:
        it = items[sel_item] if sel_item < len(items) else None
        return it["group"] if it and it["kind"] == "repo" else None

    def _clamp_sel() -> None:
        """After collapsing, move selection to nearest navigable repo."""
        nonlocal sel_item
        nav = nav_idxs()
        if not nav:
            return
        if sel_item in nav:
            return
        # nearest navigable index
        sel_item = min(nav, key=lambda i: abs(i - sel_item))

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

    for repo in repos:
        statuses[repo] = _git_status(repo)
        branches[repo] = _git_branch(repo)

    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    stdscr.timeout(500)

    while True:
        with lock:
            s_snap = dict(statuses)
            b_snap = dict(branches)

        h, w = stdscr.getmaxyx()
        # hints footer height mirrors _draw logic
        if hints_collapsed:
            hint_h = 1
        else:
            hint_h = len(_wrap_hints(_HINT_CHUNKS, max(1, w - 2)))
        body_h = max(1, h - 3 - 2 - hint_h)  # h - sep/header/sep(3) - sep-above-hints(1) - hints - sep-below-hints(1)

        sel_vrow, total_vrows = _draw(
            stdscr, groups, items, s_snap, b_snap,
            sel_item, refreshing, hints_collapsed, collapsed_groups, scroll_offset, C,
        )

        # auto-scroll to keep selection visible
        if sel_vrow < scroll_offset:
            scroll_offset = sel_vrow
        elif sel_vrow >= scroll_offset + body_h:
            scroll_offset = sel_vrow - body_h + 1
        scroll_offset = max(0, min(scroll_offset, max(0, total_vrows - body_h)))

        key = stdscr.getch()

        if key in (ord("q"), 27):
            break

        elif key == curses.KEY_UP:
            nav = nav_idxs()
            if nav:
                cur_pos  = nav.index(sel_item) if sel_item in nav else 0
                sel_item = nav[(cur_pos - 1) % len(nav)]

        elif key == curses.KEY_DOWN:
            nav = nav_idxs()
            if nav:
                cur_pos  = nav.index(sel_item) if sel_item in nav else -1
                sel_item = nav[(cur_pos + 1) % len(nav)]

        elif key == ord("g"):
            # jump to first navigable repo of the next group
            nav = nav_idxs()
            if hdr_idxs and nav:
                cur_hdr = max(
                    (hi for hi in hdr_idxs if hi < sel_item),
                    default=hdr_idxs[-1],
                )
                # cycle through group headers until we find one with navigable repos
                cur_hdr_pos = hdr_idxs.index(cur_hdr)
                for step in range(1, len(hdr_idxs) + 1):
                    next_hdr   = hdr_idxs[(cur_hdr_pos + step) % len(hdr_idxs)]
                    next_repos = [ri for ri in nav if ri > next_hdr
                                  and (next_hdr == hdr_idxs[-1]
                                       or ri < hdr_idxs[(hdr_idxs.index(next_hdr) + 1) % len(hdr_idxs)]
                                       or next_hdr > hdr_idxs[hdr_idxs.index(next_hdr)])]
                    # simpler: just first nav index past the header
                    next_repos = [ri for ri in nav if ri > next_hdr]
                    if next_repos:
                        sel_item = next_repos[0]
                        break

        elif key == ord("c"):
            grp = _current_group()
            if grp:
                if grp in collapsed_groups:
                    collapsed_groups.discard(grp)
                else:
                    collapsed_groups.add(grp)
                    _clamp_sel()

        elif key == ord("x"):
            collapsed_groups = set(all_labels)
            _clamp_sel()
            scroll_offset = 0

        elif key == ord("e"):
            collapsed_groups.clear()
            scroll_offset = 0

        elif key == curses.KEY_PPAGE:
            scroll_offset = max(0, scroll_offset - body_h)

        elif key == curses.KEY_NPAGE:
            scroll_offset = min(max(0, total_vrows - body_h), scroll_offset + body_h)

        elif key == curses.KEY_MOUSE:
            try:
                _, _mx, _my, _mz, bstate = curses.getmouse()
                if bstate & curses.BUTTON4_PRESSED:   # wheel up
                    scroll_offset = max(0, scroll_offset - 3)
                elif bstate & curses.BUTTON5_PRESSED:  # wheel down
                    scroll_offset = min(max(0, total_vrows - body_h), scroll_offset + 3)
            except curses.error:
                pass

        elif key == ord("r"):
            with lock:
                for repo in repos:
                    statuses[repo] = None

        elif key in (ord("?"), ord("/")):
            hints_collapsed = not hints_collapsed

        elif key in (curses.KEY_ENTER, 10, 13):
            if sel_item < len(items) and items[sel_item]["kind"] == "repo":
                repo = items[sel_item]["path"]
                curses.endwin()
                os.execvp("lazygit", ["lazygit", "-p", repo])


def main() -> None:
    repos = sys.argv[1:]
    if not repos:
        print("usage: python3 -m operator_console.git_watcher <repo> [<repo> ...]")
        sys.exit(1)
    curses.wrapper(_watcher, repos)


if __name__ == "__main__":
    main()
