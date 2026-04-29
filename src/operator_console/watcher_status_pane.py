# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""Curses watcher-status pane — dense at-a-glance OperationsCenter monitor.

Sections (always visible):
  Roles       — running/stopped, pid, uptime, restart count (⚡)
  Campaigns   — active kodo campaigns from OC state
  Queue       — pending tasks filtered by --profile
  SwitchBoard — health check
  Resources   — load avg, RAM bar, swap bar

Arrows navigate roles. Enter opens action submenu:
  tail logs, board, circuit breaker, memory

Usage: python3 -m operator_console.watcher_status_pane [--profile <name>]
"""
from __future__ import annotations
import curses
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

_OC_ROOT    = Path.home() / "Documents" / "GitHub" / "OperationsCenter"
_WATCH_DIR  = _OC_ROOT / "logs" / "local" / "watch-all"
_STATE_DIR  = _OC_ROOT / "state"
_QUEUE_DIR  = Path.home() / ".console" / "queue"
_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "profiles"

_ROLES   = ("intake", "goal", "test", "improve", "propose", "review", "spec", "watchdog")
_ACTIONS = ("tail logs", "board", "circuit breaker", "memory")

REFRESH_INTERVAL       = 3
PLANE_REFRESH_INTERVAL = 30
LOG_TAIL_LINES         = 60
BAR_W                  = 10   # width of █ progress bars

_OC_CONFIG = _OC_ROOT / "config" / "operations_center.local.yaml"

# States shown in each section
_BOARD_STATES  = {"ready for ai", "backlog"}
_ACTIVE_STATES = {"running"}


# ── Plane data collection ────────────────────────────────────────────────────

def _plane_config() -> dict | None:
    """Parse OC config for Plane connection details. Returns None if not configured.

    Avoids depending on PyYAML — the pane's Python may be a bare interpreter
    (e.g. pyenv system Python without site-packages). The `plane:` block is
    simple key-value pairs, so a manual parse is sufficient and robust.
    """
    if not _OC_CONFIG.exists():
        return None
    out = {
        "base_url":       "http://localhost:8080",
        "workspace_slug": "",
        "project_id":     "",
        "token_env":      "PLANE_API_TOKEN",
    }
    in_plane = False
    try:
        for raw in _OC_CONFIG.read_text().splitlines():
            stripped = raw.rstrip()
            if not stripped or stripped.lstrip().startswith("#"):
                continue
            if not stripped.startswith(" ") and not stripped.startswith("\t"):
                in_plane = stripped.startswith("plane:")
                continue
            if not in_plane:
                continue
            line = stripped.strip()
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            v = v.strip().strip('"').strip("'")
            if not v:
                continue
            if k.strip() == "base_url":
                out["base_url"] = v.rstrip("/")
            elif k.strip() == "workspace_slug":
                out["workspace_slug"] = v
            elif k.strip() == "project_id":
                out["project_id"] = v
            elif k.strip() == "api_token_env":
                out["token_env"] = v
    except Exception:
        return None
    if not out["workspace_slug"] or not out["project_id"]:
        return None
    return out


def _read_token_from_env_file(token_env: str) -> str:
    """Read the Plane token from OperationsCenter's .env file.

    The status pane often outlives a token rotation; reading from the env file
    each fetch keeps it in sync without requiring a pane restart.
    """
    env_file = _OC_ROOT / ".env.operations-center.local"
    if not env_file.exists():
        return ""
    try:
        for raw in env_file.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            k, _, v = line.partition("=")
            if k.strip() == token_env:
                return v.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _plane_get(cfg: dict, token: str, path: str) -> list[dict]:
    url = f"{cfg['base_url']}/api/v1/workspaces/{cfg['workspace_slug']}/projects/{cfg['project_id']}/{path}"
    req = urllib.request.Request(url, headers={"X-API-Key": token})
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            payload = json.loads(r.read())
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                return payload.get("results", [])
    except Exception:
        return []
    return []


def _plane_fetch(cfg: dict) -> list[dict]:
    """Fetch all work items from Plane with label IDs hydrated to names. [] on error."""
    token = _read_token_from_env_file(cfg["token_env"]) or os.environ.get(cfg["token_env"], "")
    if not token or not cfg["workspace_slug"] or not cfg["project_id"]:
        return []
    issues = _plane_get(cfg, token, "work-items/?expand=state")
    if not issues:
        return []
    # Plane returns label refs as UUIDs; resolve to names so _repo_from_labels works.
    labels = _plane_get(cfg, token, "labels/")
    by_id = {str(lab.get("id")): lab for lab in labels if isinstance(lab, dict) and lab.get("id")}
    for issue in issues:
        raw = issue.get("labels") or []
        if raw and not all(isinstance(r, dict) for r in raw):
            issue["labels"] = [by_id.get(str(r), {"name": ""}) if not isinstance(r, dict) else r for r in raw]
    return issues


def _repo_from_labels(labels: list) -> str:
    for lab in labels:
        name = (lab.get("name", "") if isinstance(lab, dict) else str(lab)).strip()
        if name.lower().startswith("repo:"):
            return name.split(":", 1)[1].strip()
    return ""


def _plane_issues(repo_filter: set[str] | None) -> dict[str, list[dict]]:
    """Return {"active": [...], "board": [...]} filtered by repo_filter."""
    cfg = _plane_config()
    if not cfg:
        return {"active": [], "board": []}
    issues = _plane_fetch(cfg)
    active, board = [], []
    for issue in issues:
        state_obj = issue.get("state")
        state_name = (state_obj.get("name", "") if isinstance(state_obj, dict) else str(state_obj or "")).strip()
        state_lower = state_name.lower()
        labels = issue.get("labels", [])
        repo = _repo_from_labels(labels)
        if repo_filter and repo not in repo_filter:
            continue
        item = {
            "title": issue.get("name", "Untitled"),
            "state": state_name,
            "repo":  repo or "?",
        }
        if state_lower in _ACTIVE_STATES:
            active.append(item)
        elif state_lower in _BOARD_STATES:
            board.append(item)
    return {"active": active, "board": board}


# ── data collection ───────────────────────────────────────────────────────────

def _pid_alive(pid: str) -> bool:
    try:
        return subprocess.run(["kill", "-0", pid], capture_output=True).returncode == 0
    except Exception:
        return False


_STALE_HEARTBEAT_S = 600  # 10 minutes — alert threshold


def _stale_heartbeat_roles() -> list[str]:
    """Return role names whose heartbeat file is older than _STALE_HEARTBEAT_S.

    A heartbeat that hasn't ticked in 10+ minutes means the worker is
    either crashed (and the supervisor isn't reviving it) or hung. Either
    way, operator should know immediately.
    """
    if not _WATCH_DIR.exists():
        return []
    now = time.time()
    stale: list[str] = []
    for hb in _WATCH_DIR.glob("heartbeat_*.json"):
        try:
            age = now - hb.stat().st_mtime
        except OSError:
            continue
        if age > _STALE_HEARTBEAT_S:
            role = hb.stem.removeprefix("heartbeat_")
            stale.append(role)
    return sorted(stale)


def _role_info(role: str) -> dict:
    pid_file = _WATCH_DIR / f"{role}.pid"
    if not pid_file.exists():
        return {"alive": False, "pid": "", "mtime": None}
    try:
        pid = pid_file.read_text().strip()
        alive = _pid_alive(pid)
        return {"alive": alive, "pid": pid, "mtime": pid_file.stat().st_mtime if alive else None}
    except Exception:
        return {"alive": False, "pid": "", "mtime": None}


def _restart_counts() -> dict[str, int]:
    """Count watcher_restart events per role from all log files."""
    counts: dict[str, int] = {}
    for log in _WATCH_DIR.glob("*.log"):
        try:
            for line in log.read_text(errors="replace").splitlines():
                if "watcher_restart" not in line:
                    continue
                try:
                    ev = json.loads(line)
                    role = ev.get("role", "")
                    if role:
                        counts[role] = counts.get(role, 0) + 1
                except Exception:
                    pass
        except Exception:
            pass
    return counts


def _active_campaigns() -> list[dict]:
    f = _STATE_DIR / "campaigns" / "active.json"
    try:
        return json.loads(f.read_text()).get("campaigns", [])
    except Exception:
        return []


def _sb_ok() -> bool:
    port = os.environ.get("PORT_SWITCHBOARD", "20401")
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _sys_resources() -> dict:
    load = "?"
    load_pct = "?"
    num_cores = 0
    try:
        parts = Path("/proc/loadavg").read_text().split()
        load = f"{parts[0]}/{parts[1]}/{parts[2]}"
        with open("/proc/cpuinfo") as f:
            num_cores = f.read().count("processor")
        if num_cores > 0:
            l1, l5, l15 = float(parts[0]), float(parts[1]), float(parts[2])
            p1, p5, p15 = int(100 * l1 / num_cores), int(100 * l5 / num_cores), int(100 * l15 / num_cores)
            load_pct = f"{p1}%/{p5}%/{p15}%"
    except Exception:
        pass

    mem_pct = swap_pct = 0
    mem_used_gb = mem_total_gb = swap_used_gb = swap_total_gb = 0.0
    try:
        info: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, *v = line.split()
            if v:
                info[k.rstrip(":")] = int(v[0])
        mt = info.get("MemTotal", 0)
        ma = info.get("MemAvailable", 0)
        st = info.get("SwapTotal", 0)
        sf = info.get("SwapFree", 0)
        if mt:
            mem_used_gb  = (mt - ma) / 1048576
            mem_total_gb = mt / 1048576
            mem_pct      = int(100 * (mt - ma) / mt)
        if st:
            swap_used_gb  = (st - sf) / 1048576
            swap_total_gb = st / 1048576
            swap_pct      = int(100 * (st - sf) / st)
    except Exception:
        pass

    return {
        "load": load,
        "load_pct": load_pct,
        "num_cores": num_cores,
        "mem_pct": mem_pct, "mem_used_gb": mem_used_gb, "mem_total_gb": mem_total_gb,
        "swap_pct": swap_pct, "swap_used_gb": swap_used_gb, "swap_total_gb": swap_total_gb,
    }


def _profile_repos(profile_name: str) -> set[str] | None:
    try:
        from operator_console.profile_loader import load_profile
        p = load_profile(profile_name, _PROFILES_DIR)
        if "group" in p:
            names: set[str] = set()
            for sub in p["group"]:
                try:
                    sp = load_profile(sub, _PROFILES_DIR)
                    names.add(sp.get("name", sub))
                except Exception:
                    names.add(sub)
            return names
        return {p["name"]} if "name" in p else None
    except Exception:
        return None


def _queue_items(repo_filter: set[str] | None) -> list[dict]:
    items = []
    if not _QUEUE_DIR.exists():
        return items
    for f in sorted(_QUEUE_DIR.glob("*.json")):
        try:
            item = json.loads(f.read_text())
            if repo_filter is None or item.get("repo_name") in repo_filter:
                items.append(item)
        except Exception:
            pass
    return items


_plane_cache: dict = {"active": [], "board": [], "fetched_at": 0.0}


def _collect(repo_filter: set[str] | None) -> dict:
    global _plane_cache
    now = time.time()
    if now - _plane_cache["fetched_at"] >= PLANE_REFRESH_INTERVAL:
        fresh = _plane_issues(repo_filter)
        _plane_cache = {**fresh, "fetched_at": now}
    return {
        "roles":     {r: _role_info(r) for r in _ROLES},
        "restarts":  _restart_counts(),
        "campaigns": _active_campaigns(),
        "sb":        _sb_ok(),
        "queue":     _queue_items(repo_filter),
        "resources": _sys_resources(),
        "plane":     {"active": _plane_cache["active"], "board": _plane_cache["board"]},
        "recent":    _recent_activity(),
        "at":        now,
    }


# ── drawing helpers ───────────────────────────────────────────────────────────

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


def _bar(pct: int, width: int = BAR_W) -> str:
    filled = round(pct * width / 100)
    return "█" * filled + "░" * (width - filled)


def _uptime(start: float) -> str:
    e = int(time.time() - start)
    if e < 60:   return f"{e}s"
    if e < 3600: return f"{e // 60}m"
    return f"{e // 3600}h{(e % 3600) // 60}m"


def _latest_log(role: str) -> Path | None:
    logs = sorted(_WATCH_DIR.glob(f"*_{role}.log"))
    return logs[-1] if logs else None


_RECENT_WINDOW_S = 300  # 5 minutes
_RECENT_PAT = re.compile(
    r"^(\d{2}:\d{2}:\d{2}) \[(\w+)\] (?:INFO|WARNING) board_worker\[\w+\]: "
    r"(?:task_id=\S+\s+)?"
    r"(claimed|completed|blocked|processing|failed)"
    r"(?:.*?status=(\S+))?"
    r"(?:.*?title=[\"\']([^\"\']{0,60}))?"
)


def _recent_activity() -> list[dict]:
    """Mine worker logs for claim/complete/block events in the last _RECENT_WINDOW_S seconds.

    Returns events newest-first as {role, action, status, title, ts} dicts.
    """
    cutoff = time.time() - _RECENT_WINDOW_S
    events: list[dict] = []
    for role in ("goal", "test", "improve"):
        log = _latest_log(role)
        if not log:
            continue
        try:
            mtime = log.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue
        try:
            text = log.read_text(errors="replace")
        except OSError:
            continue
        # Walk lines newest-first; stop after a few hits per role
        lines = text.splitlines()
        per_role = 0
        for raw in reversed(lines):
            if "board_worker[" not in raw:
                continue
            if not any(k in raw for k in (" claimed ", " completed ", " blocked ", " processing ", " failed ")):
                continue
            m = _RECENT_PAT.match(raw)
            if not m:
                continue
            ts_str, lrole, action, status, title = m.groups()
            events.append({
                "role":   lrole,
                "action": action,
                "status": status or "",
                "title":  (title or "").strip("`* "),
                "ts":     ts_str,
            })
            per_role += 1
            if per_role >= 5:
                break
    return events


# ── main view ─────────────────────────────────────────────────────────────────

_SEP_MARKER = "\x00SEP\x00"   # synthetic line that renders as a separator


def _build_main_lines(data: dict, sel: int, w: int, C: dict) -> tuple[list[tuple[str, int]], int]:
    """Build all middle-section lines as (text, attr) tuples plus the row index
    of the currently-selected role (so the caller can keep it on screen).

    Lines whose text equals _SEP_MARKER render as a horizontal separator.
    """
    lines: list[tuple[str, int]] = []
    sel_row = -1

    # ── roles ──
    roles    = data.get("roles", {})
    restarts = data.get("restarts", {})
    n_up = sum(1 for r in _ROLES if roles.get(r, {}).get("alive", False))
    total_rc = sum(restarts.get(r, 0) for r in _ROLES)
    hdr_attr = (C["YLW"] | curses.A_BOLD) if (n_up < len(_ROLES) or total_rc > 0) else (C["HEAD"] | curses.A_BOLD)
    rc_tag = f"{total_rc} restarts" if total_rc else "clean"
    lines.append((f" Workers ({n_up}/{len(_ROLES)} running, {rc_tag})", hdr_attr))
    for i, role in enumerate(_ROLES):
        info  = roles.get(role, {})
        alive = info.get("alive", False)
        rc    = restarts.get(role, 0)
        rb    = f" ↺{rc}" if rc else ""
        if alive:
            up   = _uptime(info["mtime"]) if info.get("mtime") else "?"
            line = f"  ✓  {role:<11} up {up}{rb}"
            attr = C["RUN"]
        else:
            line = f"  ✗  {role:<11} STOPPED{rb}"
            attr = C["ERR"]
        if i == sel:
            sel_row = len(lines)
            full = ("▶" + line[1:] + " [enter]")[:w - 1]
            lines.append((full, C["SEL"] | curses.A_BOLD))
        else:
            lines.append((line, attr))

    # ── active tasks (Plane: Running) ──
    plane = data.get("plane", {})
    active_tasks = plane.get("active", [])
    if active_tasks:
        lines.append((_SEP_MARKER, C["DIM"]))
        lines.append((f" Active ({len(active_tasks)} running)", C["HEAD"] | curses.A_BOLD))
        for item in active_tasks:
            repo  = item.get("repo", "?")[:10]
            title = item.get("title", "?")[:max(w - 16, 8)]
            lines.append((f"  ▶  {repo:<11} {title}", C["RUN"]))

    # ── recent activity (worker logs) ──
    recent = data.get("recent", [])
    if recent:
        lines.append((_SEP_MARKER, C["DIM"]))
        lines.append((f" Recent ({len(recent)} events, last 5m)", C["HEAD"] | curses.A_BOLD))
        for ev in recent[:8]:
            action = ev.get("action", "")
            status = ev.get("status", "")
            title  = ev.get("title", "")[:max(w - 32, 8)]
            role   = ev.get("role", "")
            ts     = ev.get("ts", "")
            if action == "blocked":
                icon, attr = "✗", C["ERR"]
            elif action == "completed":
                icon, attr = "✓", C["RUN"]
            elif action == "claimed":
                icon, attr = "→", C["YLW"]
            else:
                icon, attr = "·", C["DIM"]
            tag = f"{action}({status})" if status else action
            lines.append((f"  {icon}  {ts} {role:<8} {tag:<22} {title}", attr))

    # ── board ──
    board_items = plane.get("board", [])
    if board_items:
        lines.append((_SEP_MARKER, C["DIM"]))
        lines.append((f" Board ({len(board_items)} queued)", C["HEAD"] | curses.A_BOLD))
        for item in board_items:
            repo  = item.get("repo", "?")[:10]
            state = item.get("state", "")
            icon  = "·" if "backlog" in state.lower() else "→"
            title = item.get("title", "?")[:max(w - 16, 8)]
            lines.append((f"  {icon}  {repo:<11} {title}", C["DIM"]))

    # ── campaigns ──
    campaigns = data.get("campaigns", [])
    if campaigns:
        lines.append((_SEP_MARKER, C["DIM"]))
        lines.append((f" Campaigns ({len(campaigns)} active)", C["HEAD"] | curses.A_BOLD))
        for c in campaigns:
            slug   = c.get("slug", c.get("campaign_id", "?"))[:w - 6]
            status = c.get("status", "")
            if status == "done":
                icon, attr = "✓", C["RUN"]
            elif status == "failed":
                icon, attr = "✗", C["ERR"]
            else:
                icon, attr = "▶", C["YLW"]
            lines.append((f"  {icon}  {slug}", attr))

    # ── queue ──
    queue = data.get("queue", [])
    if queue:
        lines.append((_SEP_MARKER, C["DIM"]))
        lines.append((f" Queue ({len(queue)} pending)", C["HEAD"] | curses.A_BOLD))
        for item in queue:
            typ  = (item.get("task_type") or "?")[:4]
            repo = (item.get("repo_name") or "?")[:10]
            goal = (item.get("goal") or "")[:max(w - 20, 8)]
            lines.append((f"  {typ:<5} {repo:<11} {goal}", C["DIM"]))

    # ── services ──
    sb = data.get("sb", False)
    lines.append((_SEP_MARKER, C["DIM"]))
    lines.append((" Services", C["HEAD"] | curses.A_BOLD))
    sb_icon = "✓" if sb else "✗"
    sb_attr = C["RUN"] if sb else C["ERR"]
    lines.append((f"  {sb_icon} SwitchBoard", sb_attr))

    return lines, sel_row


def _resources_lines(data: dict, C: dict) -> list[tuple[str, int]]:
    """Build the System Resources block as lines. Always anchored to bottom."""
    out: list[tuple[str, int]] = []
    res = data.get("resources", {})
    out.append((_SEP_MARKER, C["DIM"]))
    out.append((" System Resources", C["HEAD"] | curses.A_BOLD))
    out.append((f"  {'':15}  {'1m':>7} {'5m':>7} {'15m':>7}", C["DIM"]))

    load_str = res.get('load', '?')
    parts = load_str.split('/') if '/' in load_str else ['?', '?', '?']
    out.append((f"  {'Processes/Queue':15}  {parts[0]:>7} {parts[1]:>7} {parts[2]:>7}", C["DIM"]))

    load_pct_str = res.get('load_pct', '?')
    num_cores = res.get('num_cores', 0)
    cores_str = f"({num_cores} cores)" if num_cores > 0 else ""
    pct_parts = load_pct_str.split('/') if '/' in load_pct_str else ['?', '?', '?']
    out.append((f"  {'CPU Utilization':15}  {pct_parts[0]:>7} {pct_parts[1]:>7} {pct_parts[2]:>7}  {cores_str}", C["DIM"]))

    mp  = res.get("mem_pct", 0)
    mug = res.get("mem_used_gb", 0)
    mtg = res.get("mem_total_gb", 0)
    out.append((f"  {'RAM':15}  {_bar(mp):>7} {mp:>3d}%  {mug:.1f}/{mtg:.1f}G",
                C["YLW"] if mp > 80 else C["DIM"]))

    if res.get("swap_total_gb", 0) > 0:
        sp  = res.get("swap_pct", 0)
        sug = res.get("swap_used_gb", 0)
        stg = res.get("swap_total_gb", 0)
        out.append((f"  {'Swap':15}  {_bar(sp):>7} {sp:>3d}%  {sug:.1f}/{stg:.1f}G",
                    C["YLW"] if sp > 50 else C["DIM"]))
    return out


def _draw_main(stdscr, data: dict, sel: int, refreshing: bool, flash: str, C: dict, scroll: int) -> int:
    """Render the main view. Returns the (possibly-clamped) scroll offset."""
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    put = lambda r, t, a=0: _put(stdscr, r, h, w, t, a)

    spin = " ⟳" if refreshing else "  "
    ts   = time.strftime("%H:%M:%S")

    # D4 stall alert: scan heartbeat files; any role whose heartbeat hasn't
    # been touched in > _STALE_HEARTBEAT_S seconds means the worker is
    # silent (crashed, hung, or its supervisor died). Render a red banner
    # at the very top so it's the first thing the operator sees.
    stale_roles = _stale_heartbeat_roles()
    if stale_roles:
        banner = (
            f" ⚠  STALL ALERT — {len(stale_roles)} role(s) silent > "
            f"{_STALE_HEARTBEAT_S // 60}min: {', '.join(stale_roles)}"
        )
        put(0, banner.ljust(w - 1), C["ERR"] | curses.A_BOLD | curses.A_REVERSE)
        put(1, f" Operations Center{spin}  {ts}", C["HEAD"] | curses.A_BOLD)
        _sep(stdscr, 2, h, w, C["DIM"])
    else:
        put(0, f" Operations Center{spin}  {ts}", C["HEAD"] | curses.A_BOLD)
        _sep(stdscr, 1, h, w, C["DIM"])

    # Build content blocks
    middle_lines, sel_row = _build_main_lines(data, sel, w, C)
    bottom_lines          = _resources_lines(data, C)

    # Reserve rows for the bottom-anchored resources block + footer + flash
    bottom_h = len(bottom_lines)
    footer_h = 2 if flash else 1                       # flash on h-2, help on h-1
    middle_top    = 3 if stale_roles else 2            # banner pushes content down by 1
    middle_bottom = h - bottom_h - footer_h            # exclusive
    middle_h      = max(0, middle_bottom - middle_top)

    # Clamp scroll into [0, max_scroll] and auto-scroll to keep selection visible
    max_scroll = max(0, len(middle_lines) - middle_h)
    if sel_row >= 0 and middle_h > 0:
        if sel_row < scroll:
            scroll = sel_row
        elif sel_row >= scroll + middle_h:
            scroll = sel_row - middle_h + 1
    scroll = max(0, min(scroll, max_scroll))

    # Render middle section (with scroll offset)
    visible = middle_lines[scroll:scroll + middle_h]
    for i, (text, attr) in enumerate(visible):
        r = middle_top + i
        if text == _SEP_MARKER:
            _put(stdscr, r, h, w, "─" * (w - 1), attr)
        else:
            put(r, text, attr)

    # Scroll indicators
    if scroll > 0 and middle_h > 0:
        put(middle_top, "▲" + " " * (w - 2), C["YLW"])
    if scroll + middle_h < len(middle_lines) and middle_h > 0:
        put(middle_bottom - 1, "▼" + " " * (w - 2), C["YLW"])

    # Render bottom-anchored resources
    for i, (text, attr) in enumerate(bottom_lines):
        r = middle_bottom + i
        if r >= h - footer_h:
            break
        if text == _SEP_MARKER:
            _put(stdscr, r, h, w, "─" * (w - 1), attr)
        else:
            put(r, text, attr)

    if flash:
        put(h - 2, f" {flash}", C["HEAD"])
    put(h - 1, " ↑↓ role  PgUp/PgDn scroll  enter actions  r refresh  q quit", C["DIM"])
    stdscr.refresh()
    return scroll


# ── submenu view ──────────────────────────────────────────────────────────────

def _draw_submenu(stdscr, role: str, info: dict, sel: int, C: dict) -> None:
    h, w = stdscr.getmaxyx()
    put = lambda r, t, a=0: _put(stdscr, r, h, w, t, a)
    stdscr.erase()

    alive  = info.get("alive", False)
    status = f"running  pid {info['pid']}" if alive else "STOPPED"
    status_attr = (C["HEAD"] | curses.A_BOLD) if alive else (C["ERR"] | curses.A_BOLD)
    put(0, f" {role}  [ {status} ]", status_attr)
    _sep(stdscr, 1, h, w, C["DIM"])

    for i, action in enumerate(_ACTIONS):
        if i == sel:
            put(i + 2, f"  ▶ {action}", C["SEL"] | curses.A_BOLD)
        else:
            put(i + 2, f"    {action}", 0)

    _sep(stdscr, len(_ACTIONS) + 2, h, w, C["DIM"])
    put(h - 1, " ↑↓ select  ↵ run  esc back", C["DIM"])
    stdscr.refresh()


# ── log view ──────────────────────────────────────────────────────────────────

def _draw_log_view(stdscr, role: str, lines: list[str], C: dict) -> None:
    h, w = stdscr.getmaxyx()
    put = lambda r, t, a=0: _put(stdscr, r, h, w, t, a)
    stdscr.erase()

    put(0, f" circuit breaker — {role} (last {LOG_TAIL_LINES} lines)", C["HEAD"] | curses.A_BOLD)
    _sep(stdscr, 1, h, w, C["DIM"])

    for i, line in enumerate(lines[-(h - 3):]):
        put(i + 2, f" {line}", C["DIM"])

    put(h - 1, " esc back", C["DIM"])
    stdscr.refresh()


# ── actions ───────────────────────────────────────────────────────────────────

def _do_tail(role: str) -> str:
    log = _latest_log(role)
    if not log:
        return f"no log found for {role}"
    curses.endwin()
    os.execvp("tail", ["tail", "-f", str(log)])
    return ""


def _do_board() -> str:
    url = os.environ.get("OPERATIONS_CENTER_PLANE_URL", "").strip()
    if not url:
        return "set OPERATIONS_CENTER_PLANE_URL to enable board"
    try:
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return "xdg-open failed"
    return f"opened {url[:50]}"


def _do_memory(info: dict) -> None:
    pid = info.get("pid", "")
    curses.endwin()
    if pid and _pid_alive(pid):
        os.execvp("htop", ["htop", "-p", pid])
    else:
        os.execvp("htop", ["htop"])


def _read_log_lines(role: str) -> list[str]:
    log = _latest_log(role)
    if not log:
        return ["(no log file found)"]
    try:
        return log.read_text(errors="replace").splitlines()[-LOG_TAIL_LINES:]
    except Exception as e:
        return [f"(error: {e})"]


# ── main pane ─────────────────────────────────────────────────────────────────

def _pane(stdscr, profile_name: str) -> None:
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN,  -1)
    curses.init_pair(2, curses.COLOR_WHITE,  -1)
    curses.init_pair(3, curses.COLOR_CYAN,   -1)
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(5, curses.COLOR_YELLOW, -1)
    curses.init_pair(6, curses.COLOR_RED,    -1)

    C = {
        "RUN":  curses.color_pair(1),
        "DIM":  curses.color_pair(2) | curses.A_DIM,
        "HEAD": curses.color_pair(3),
        "SEL":  curses.color_pair(4),
        "YLW":  curses.color_pair(5),
        "ERR":  curses.color_pair(6),
    }

    repo_filter = _profile_repos(profile_name) if profile_name else None

    _empty_roles = {r: {"alive": False, "pid": "", "mtime": None} for r in _ROLES}
    data: dict = {
        "roles": dict(_empty_roles), "restarts": {}, "campaigns": [],
        "sb": False, "queue": [], "resources": {}, "at": time.time(),
    }
    refreshing = False
    lock = threading.Lock()

    def _refresh_loop() -> None:
        nonlocal refreshing
        while True:
            refreshing = True
            fresh = _collect(repo_filter)
            with lock:
                data.update(fresh)
            refreshing = False
            time.sleep(REFRESH_INTERVAL)

    threading.Thread(target=_refresh_loop, daemon=True).start()
    with lock:
        data.update(_collect(repo_filter))

    stdscr.timeout(500)
    role_sel   = 0
    mode       = "roles"
    action_sel = 0
    log_lines: list[str] = []
    flash      = ""
    flash_at   = 0.0
    scroll     = 0

    while True:
        if flash and time.time() - flash_at > 2:
            flash = ""

        with lock:
            snap = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
                    for k, v in data.items()}

        if mode == "log":
            _draw_log_view(stdscr, _ROLES[role_sel], log_lines, C)
        elif mode == "action":
            _draw_submenu(stdscr, _ROLES[role_sel],
                          snap["roles"].get(_ROLES[role_sel], {}), action_sel, C)
        else:
            scroll = _draw_main(stdscr, snap, role_sel, refreshing, flash, C, scroll)

        key = stdscr.getch()

        if mode == "log":
            if key in (27, ord("q"), ord("b")):
                mode = "roles"

        elif mode == "action":
            if key == curses.KEY_UP:
                action_sel = (action_sel - 1) % len(_ACTIONS)
            elif key == curses.KEY_DOWN:
                action_sel = (action_sel + 1) % len(_ACTIONS)
            elif key in (27, ord("b")):
                mode = "roles"
            elif key in (curses.KEY_ENTER, 10, 13):
                action = _ACTIONS[action_sel]
                role   = _ROLES[role_sel]
                if action == "tail logs":
                    msg = _do_tail(role)
                    flash = msg; flash_at = time.time(); mode = "roles"
                elif action == "board":
                    flash = _do_board(); flash_at = time.time(); mode = "roles"
                elif action == "circuit breaker":
                    log_lines = _read_log_lines(role)
                    mode = "log"
                elif action == "memory":
                    _do_memory(snap["roles"].get(role, {}))

        else:
            if key == curses.KEY_UP:
                role_sel = (role_sel - 1) % len(_ROLES)
            elif key == curses.KEY_DOWN:
                role_sel = (role_sel + 1) % len(_ROLES)
            elif key == curses.KEY_PPAGE:
                scroll = max(0, scroll - 10)
            elif key == curses.KEY_NPAGE:
                scroll += 10  # _draw_main clamps to max
            elif key == curses.KEY_HOME:
                scroll = 0
            elif key == curses.KEY_END:
                scroll = 10_000  # clamped by _draw_main
            elif key in (curses.KEY_ENTER, 10, 13):
                mode = "action"; action_sel = 0
            elif key == ord("r"):
                with lock:
                    data.update({"roles": dict(_empty_roles), "campaigns": [],
                                 "sb": False, "queue": [], "resources": {}})
            elif key in (ord("q"), 27):
                break


def main() -> None:
    profile_name = ""
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--profile" and i + 1 < len(args):
            profile_name = args[i + 1]
    curses.wrapper(_pane, profile_name)


if __name__ == "__main__":
    main()
