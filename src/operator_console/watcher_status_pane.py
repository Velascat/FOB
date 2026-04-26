"""Curses watcher-status pane — interactive OperationsCenter role monitor.

Arrows navigate roles. Enter opens an action submenu:
  tail logs       — tail the role's latest log file
  board           — open OPERATIONS_CENTER_PLANE_URL in browser
  circuit breaker — view last N log lines in-pane
  memory          — htop for the role's process

Queue section shows pending items, filtered by --profile if given.

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

_WATCH_DIR = (
    Path.home() / "Documents" / "GitHub"
    / "OperationsCenter" / "logs" / "local" / "watch-all"
)
_QUEUE_DIR = Path.home() / ".console" / "queue"
_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "profiles"

_ROLES = ("intake", "goal", "test", "improve", "propose", "review", "spec", "watchdog")
_ACTIONS = ("tail logs", "board", "circuit breaker", "memory")

REFRESH_INTERVAL = 3
LOG_TAIL_LINES = 60


# ── helpers ───────────────────────────────────────────────────────────────────

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


def _sb_ok() -> bool:
    port = os.environ.get("PORT_SWITCHBOARD", "20401")
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _uptime(start: float) -> str:
    e = int(time.time() - start)
    if e < 60:   return f"{e}s"
    if e < 3600: return f"{e // 60}m"
    return f"{e // 3600}h{(e % 3600) // 60}m"


def _latest_log(role: str) -> Path | None:
    logs = sorted(_WATCH_DIR.glob(f"*_{role}.log"))
    return logs[-1] if logs else None


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


def _collect(repo_filter: set[str] | None) -> dict:
    return {
        "roles":  {r: _role_info(r) for r in _ROLES},
        "sb":     _sb_ok(),
        "queue":  _queue_items(repo_filter),
        "at":     time.time(),
    }


# ── drawing ───────────────────────────────────────────────────────────────────

def _put(stdscr, row: int, h: int, w: int, text: str, attr: int = 0) -> None:
    if row >= h or row < 0:
        return
    try:
        stdscr.addstr(row, 0, text[: w - 1].ljust(min(len(text) + 1, w - 1)), attr)
    except curses.error:
        pass


def _sep(stdscr, row: int, h: int, w: int, C_DIM: int) -> None:
    _put(stdscr, row, h, w, "─" * (w - 1), C_DIM)


def _draw_main(stdscr, data: dict, sel: int, refreshing: bool,
               flash: str, C: dict) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    put = lambda r, t, a=0: _put(stdscr, r, h, w, t, a)

    spin = " ⟳" if refreshing else "  "
    ts   = time.strftime("%H:%M:%S")
    put(0, f" Operations Center{spin}  {ts}", C["HEAD"] | curses.A_BOLD)
    _sep(stdscr, 1, h, w, C["DIM"])

    row = 2
    roles = data.get("roles", {})
    for i, role in enumerate(_ROLES):
        if row >= h - 3:
            break
        info = roles.get(role, {})
        alive = info.get("alive", False)
        if alive:
            up   = _uptime(info["mtime"]) if info.get("mtime") else "?"
            line = f"  ✓  {role:<12} {info['pid']:<7} {up}"
            attr = C["RUN"]
        else:
            line = f"  ✗  {role:<12} stopped"
            attr = C["DIM"]
        if i == sel:
            put(row, ("▶" + line[1:])[:w - 1], C["SEL"] | curses.A_BOLD)
            row += 1
            # show action hints inline under selected role
            actions_hint = "    tail logs · board · circuit breaker · memory  [↵]"
            put(row, actions_hint[:w - 1], C["HEAD"])
        else:
            put(row, line, attr)
        row += 1

    if row < h - 2:
        _sep(stdscr, row, h, w, C["DIM"]); row += 1
    if row < h - 1:
        sb   = data.get("sb", False)
        put(row, f"  {'✓' if sb else '✗'}   SwitchBoard", C["RUN"] if sb else C["DIM"])
        row += 1

    queue = data.get("queue", [])
    if queue and row < h - 2:
        _sep(stdscr, row, h, w, C["DIM"]); row += 1
        label = f"  Queue ({len(queue)})"
        put(row, label, C["HEAD"]); row += 1
        for item in queue:
            if row >= h - 1:
                break
            rid  = item.get("id", "?")[:8]
            typ  = item.get("task_type", "?")[:6]
            repo = item.get("repo_name", "?")[:12]
            goal = item.get("goal", "")[:max(w - 32, 10)]
            put(row, f"  {rid}  {typ:<8} {repo:<14} {goal}", C["DIM"])
            row += 1

    if flash:
        put(h - 2, f" {flash}", C["HEAD"])
    put(h - 1, " ↑↓ navigate  ↵ open action  r refresh  q quit", C["DIM"])
    stdscr.refresh()


def _draw_submenu(stdscr, role: str, info: dict, sel: int, C: dict) -> None:
    h, w = stdscr.getmaxyx()
    put = lambda r, t, a=0: _put(stdscr, r, h, w, t, a)

    stdscr.erase()
    alive = info.get("alive", False)
    status = f"running  pid {info['pid']}" if alive else "stopped"
    put(0, f" {role}  [ {status} ]", C["HEAD"] | curses.A_BOLD)
    _sep(stdscr, 1, h, w, C["DIM"])

    for i, action in enumerate(_ACTIONS):
        if i == sel:
            put(i + 2, f"  ▶ {action}", C["SEL"] | curses.A_BOLD)
        else:
            put(i + 2, f"    {action}", 0)

    _sep(stdscr, len(_ACTIONS) + 2, h, w, C["DIM"])
    put(h - 1, " ↑↓ select  ↵ run  esc back", C["DIM"])
    stdscr.refresh()


def _draw_log_view(stdscr, role: str, lines: list[str], C: dict) -> None:
    h, w = stdscr.getmaxyx()
    put = lambda r, t, a=0: _put(stdscr, r, h, w, t, a)

    stdscr.erase()
    put(0, f" circuit breaker — {role} (last {LOG_TAIL_LINES} lines)", C["HEAD"] | curses.A_BOLD)
    _sep(stdscr, 1, h, w, C["DIM"])

    visible = lines[-(h - 3):]
    for i, line in enumerate(visible):
        put(i + 2, f" {line}", C["DIM"])

    put(h - 1, " esc back", C["DIM"])
    stdscr.refresh()


# ── actions ───────────────────────────────────────────────────────────────────

def _do_tail(role: str) -> str:
    log = _latest_log(role)
    if not log:
        return f"no log file found for {role}"
    curses.endwin()
    os.execvp("tail", ["tail", "-f", str(log)])
    return ""  # unreachable


def _do_board() -> str:
    url = os.environ.get("OPERATIONS_CENTER_PLANE_URL", "").strip()
    if not url:
        return "set OPERATIONS_CENTER_PLANE_URL to use board"
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
        text = log.read_text(errors="replace")
        return text.splitlines()[-LOG_TAIL_LINES:]
    except Exception as e:
        return [f"(error reading log: {e})"]


# ── main pane ─────────────────────────────────────────────────────────────────

def _pane(stdscr, profile_name: str) -> None:
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN,  -1)   # running
    curses.init_pair(2, curses.COLOR_WHITE,  -1)   # dim / stopped
    curses.init_pair(3, curses.COLOR_CYAN,   -1)   # header
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE)  # selected

    C = {
        "RUN":  curses.color_pair(1),
        "DIM":  curses.color_pair(2) | curses.A_DIM,
        "HEAD": curses.color_pair(3),
        "SEL":  curses.color_pair(4),
    }

    repo_filter = _profile_repos(profile_name) if profile_name else None

    data: dict = {
        "roles": {r: {"alive": False, "pid": "", "mtime": None} for r in _ROLES},
        "sb": False, "queue": [], "at": time.time(),
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
    mode       = "roles"    # "roles" | "action" | "log"
    action_sel = 0
    log_lines: list[str] = []
    flash      = ""
    flash_at   = 0.0

    while True:
        now = time.time()
        if flash and now - flash_at > 2:
            flash = ""

        with lock:
            snap = {
                "roles": dict(data["roles"]),
                "sb":    data["sb"],
                "queue": list(data["queue"]),
                "at":    data["at"],
            }

        if mode == "log":
            _draw_log_view(stdscr, _ROLES[role_sel], log_lines, C)
        elif mode == "action":
            _draw_submenu(stdscr, _ROLES[role_sel], snap["roles"].get(_ROLES[role_sel], {}), action_sel, C)
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
                if action == "tail logs":
                    msg = _do_tail(_ROLES[role_sel])   # exec — only returns on error
                    flash = msg; flash_at = time.time(); mode = "roles"
                elif action == "board":
                    flash = _do_board(); flash_at = time.time(); mode = "roles"
                elif action == "circuit breaker":
                    log_lines = _read_log_lines(_ROLES[role_sel])
                    mode = "log"
                elif action == "memory":
                    info = snap["roles"].get(_ROLES[role_sel], {})
                    _do_memory(info)   # exec — doesn't return

        else:  # roles mode
            if key == curses.KEY_UP:
                role_sel = (role_sel - 1) % len(_ROLES)
            elif key == curses.KEY_DOWN:
                role_sel = (role_sel + 1) % len(_ROLES)
            elif key in (curses.KEY_ENTER, 10, 13):
                mode = "action"
                action_sel = 0
            elif key == ord("r"):
                with lock:
                    data.update({"roles": {r: {"alive": False, "pid": "", "mtime": None}
                                           for r in _ROLES}, "sb": False, "queue": []})
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
