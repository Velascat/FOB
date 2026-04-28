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
    """Parse OC config for Plane connection details. Returns None if not configured."""
    try:
        import yaml  # type: ignore[import]
        text = _OC_CONFIG.read_text()
        cfg = yaml.safe_load(text)
        p = cfg.get("plane", {})
        return {
            "base_url":       p.get("base_url", "http://localhost:8080").rstrip("/"),
            "workspace_slug": p.get("workspace_slug", ""),
            "project_id":     p.get("project_id", ""),
            "token_env":      p.get("api_token_env", "PLANE_API_TOKEN"),
        }
    except Exception:
        return None


def _plane_fetch(cfg: dict) -> list[dict]:
    """Fetch all work items from Plane. Returns [] on any error."""
    token = os.environ.get(cfg["token_env"], "")
    if not token or not cfg["workspace_slug"] or not cfg["project_id"]:
        return []
    url = (
        f"{cfg['base_url']}/api/v1/workspaces/{cfg['workspace_slug']}"
        f"/projects/{cfg['project_id']}/work-items/?expand=state"
    )
    req = urllib.request.Request(url, headers={"X-API-Key": token})
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            payload = json.loads(r.read())
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                return payload.get("results", [])
    except Exception:
        pass
    return []


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


# ── main view ─────────────────────────────────────────────────────────────────

def _draw_main(stdscr, data: dict, sel: int, refreshing: bool, flash: str, C: dict) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    put = lambda r, t, a=0: _put(stdscr, r, h, w, t, a)

    spin = " ⟳" if refreshing else "  "
    ts   = time.strftime("%H:%M:%S")
    put(0, f" Operations Center{spin}  {ts}", C["HEAD"] | curses.A_BOLD)
    row = _sep(stdscr, 1, h, w, C["DIM"])

    # ── roles ──
    roles    = data.get("roles", {})
    restarts = data.get("restarts", {})
    n_up = sum(1 for r in _ROLES if roles.get(r, {}).get("alive", False))
    hdr_attr = C["HEAD"] | curses.A_BOLD if n_up == len(_ROLES) else C["YLW"] | curses.A_BOLD
    put(row, f" Workers ({n_up}/{len(_ROLES)} running)", hdr_attr); row += 1
    for i, role in enumerate(_ROLES):
        if row >= h - 2:
            break
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
            hint = " [enter]"
            full = ("▶" + line[1:] + hint)[:w - 1]
            put(row, full, C["SEL"] | curses.A_BOLD)
        else:
            put(row, line, attr)
        row += 1

    # ── active tasks (Plane: Running) ──
    plane     = data.get("plane", {})
    active_tasks = plane.get("active", [])
    if active_tasks and row < h - 2:
        row = _sep(stdscr, row, h, w, C["DIM"])
        put(row, f" Active ({len(active_tasks)} running)", C["HEAD"] | curses.A_BOLD); row += 1
        for item in active_tasks:
            if row >= h - 2:
                break
            repo  = item.get("repo", "?")[:10]
            title = item.get("title", "?")[:max(w - 16, 8)]
            put(row, f"  ▶  {repo:<11} {title}", C["RUN"]); row += 1

    # ── board (Plane: Ready for AI / Backlog) ──
    board_items = plane.get("board", [])
    if board_items and row < h - 2:
        row = _sep(stdscr, row, h, w, C["DIM"])
        put(row, f" Board ({len(board_items)} queued)", C["HEAD"] | curses.A_BOLD); row += 1
        for item in board_items:
            if row >= h - 2:
                break
            repo  = item.get("repo", "?")[:10]
            state = item.get("state", "")
            icon  = "·" if "backlog" in state.lower() else "→"
            title = item.get("title", "?")[:max(w - 16, 8)]
            put(row, f"  {icon}  {repo:<11} {title}", C["DIM"]); row += 1

    # ── campaigns ──
    campaigns = data.get("campaigns", [])
    if campaigns and row < h - 2:
        row = _sep(stdscr, row, h, w, C["DIM"])
        put(row, f" Campaigns ({len(campaigns)} active)", C["HEAD"] | curses.A_BOLD); row += 1
        for c in campaigns:
            if row >= h - 2:
                break
            slug   = c.get("slug", c.get("campaign_id", "?"))[:w - 6]
            status = c.get("status", "")
            if status == "done":
                icon, attr = "✓", C["RUN"]
            elif status == "failed":
                icon, attr = "✗", C["ERR"]
            else:
                icon, attr = "▶", C["YLW"]
            put(row, f"  {icon}  {slug}", attr)
            row += 1

    # ── queue ──
    queue = data.get("queue", [])
    if queue and row < h - 2:
        row = _sep(stdscr, row, h, w, C["DIM"])
        put(row, f" Queue ({len(queue)} pending)", C["HEAD"] | curses.A_BOLD); row += 1
        for item in queue:
            if row >= h - 2:
                break
            typ  = (item.get("task_type") or "?")[:4]
            repo = (item.get("repo_name") or "?")[:10]
            goal = (item.get("goal") or "")[:max(w - 20, 8)]
            put(row, f"  {typ:<5} {repo:<11} {goal}", C["DIM"])
            row += 1

    # ── services ──
    if row < h - 2:
        row = _sep(stdscr, row, h, w, C["DIM"])
    sb = data.get("sb", False)
    if row < h - 2:
        put(row, " Services", C["HEAD"] | curses.A_BOLD); row += 1
    if row < h - 2:
        sb_icon = "✓" if sb else "✗"
        sb_attr = C["RUN"] if sb else C["ERR"]
        put(row, f"  {sb_icon} SwitchBoard", sb_attr); row += 1

    # ── system resources ──
    if row < h - 2:
        row = _sep(stdscr, row, h, w, C["DIM"])
    res = data.get("resources", {})
    if row < h - 2:
        put(row, " System Resources", C["HEAD"] | curses.A_BOLD); row += 1
    if row < h - 2:
        put(row, f"                        1m       5m      15m", C["DIM"]); row += 1
    if row < h - 2:
        load_str = res.get('load', '?')
        parts = load_str.split('/') if '/' in load_str else ['?', '?', '?']
        load_formatted = f"{parts[0]:>7} {parts[1]:>7} {parts[2]:>7}"
        put(row, f"  Processes/Queue {load_formatted}", C["DIM"]); row += 1
    if row < h - 2:
        load_pct_str = res.get('load_pct', '?')
        num_cores = res.get('num_cores', 0)
        cores_str = f"({num_cores} cores)" if num_cores > 0 else ""
        pct_parts = load_pct_str.split('/') if '/' in load_pct_str else ['?', '?', '?']
        pct_formatted = f"{pct_parts[0]:>7} {pct_parts[1]:>7} {pct_parts[2]:>7}"
        put(row, f"  CPU Utilization {pct_formatted}  {cores_str}", C["DIM"]); row += 1
    if row < h - 2:
        mp  = res.get("mem_pct", 0)
        mug = res.get("mem_used_gb", 0)
        mtg = res.get("mem_total_gb", 0)
        put(row, f"  RAM  {_bar(mp)} {mp:3d}%  {mug:.1f}/{mtg:.1f}G",
            C["YLW"] if mp > 80 else C["DIM"]); row += 1
    if row < h - 2 and res.get("swap_total_gb", 0) > 0:
        sp  = res.get("swap_pct", 0)
        sug = res.get("swap_used_gb", 0)
        stg = res.get("swap_total_gb", 0)
        put(row, f"  Swap {_bar(sp)} {sp:3d}%  {sug:.1f}/{stg:.1f}G",
            C["YLW"] if sp > 50 else C["DIM"]); row += 1

    if flash:
        put(h - 2, f" {flash}", C["HEAD"])
    put(h - 1, " ↑↓ navigate   enter = actions   r = refresh   q = quit", C["DIM"])
    stdscr.refresh()


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
            _draw_main(stdscr, snap, role_sel, refreshing, flash, C)

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
