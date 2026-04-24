"""fob status — show system readiness: SwitchBoard, ControlPlane, lane binaries, last run."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m", "MAG": "\033[35m",
}


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _which(binary: str) -> bool:
    import subprocess
    try:
        return subprocess.run(["which", binary], capture_output=True).returncode == 0
    except Exception:
        return False


def _repo_root(name: str) -> Path:
    return Path.home() / "Documents" / "GitHub" / name


def _row(label: str, ok: bool, detail: str = "") -> None:
    mark = _c("OK", "GRN") if ok else _c("--", "DIM")
    suffix = f"  {_c(detail, 'DIM')}" if detail else ""
    print(f"  {_c(label + ' ', 'DIM'):<26}{mark}{suffix}")


def run_status(args: list[str]) -> int:
    use_json = "--json" in args

    switchboard_port = os.environ.get("PORT_SWITCHBOARD", "20401")
    sb_health_url = f"http://localhost:{switchboard_port}/health"

    sb_ok = _http_ok(sb_health_url)
    cp_repo = _repo_root("ControlPlane")
    cp_ok = (cp_repo / "src" / "control_plane" / "entrypoints" / "execute" / "main.py").exists()

    binaries = ["claude", "codex", "kodo", "aider"]
    binary_status = {b: _which(b) for b in binaries}

    from fob.runs import latest_run, run_summary
    last_run_dir = latest_run()
    last = run_summary(last_run_dir) if last_run_dir else None

    if use_json:
        import json
        payload = {
            "switchboard": {"ok": sb_ok, "url": sb_health_url},
            "control_plane": {"ok": cp_ok, "path": str(cp_repo)},
            "binaries": binary_status,
            "last_run": last,
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print(_c("\n  fob status", "B", "CYN") + _c(" — system readiness", "DIM"))
    print()

    # SwitchBoard
    _row("SwitchBoard", sb_ok, sb_health_url if sb_ok else f"not reachable at {sb_health_url}")

    # ControlPlane
    _row("ControlPlane", cp_ok, str(cp_repo) if cp_ok else f"not found at {cp_repo}")

    print()

    # Lane binaries
    print(_c("  Lanes", "B"))
    lane_map = {
        "claude": "claude_cli",
        "codex":  "codex_cli",
        "kodo":   "kodo",
        "aider":  "aider_local",
    }
    for binary, lane in lane_map.items():
        ok = binary_status[binary]
        mark = _c("available", "GRN") if ok else _c("unavailable", "DIM")
        print(f"    {_c(lane, 'DIM'):<22}{mark}  {_c(f'({binary})', 'DIM')}")

    print()

    # Last run
    if last:
        status = last.get("status", "unknown")
        success = last.get("success")
        run_id = last.get("run_id", "?")
        lane = last.get("selected_lane", "?")
        goal = last.get("goal_text") or "?"
        written_at = (last.get("written_at") or "?")[:19].replace("T", " ")

        status_color = "GRN" if success else "RED"
        status_disp = _c(status, status_color)
        goal_disp = goal[:50] + ("…" if len(goal) > 50 else "")

        print(_c("  Last run", "B"))
        print(f"    {_c('id     ', 'DIM')} {_c(run_id[:36], 'B')}")
        print(f"    {_c('status ', 'DIM')} {status_disp}")
        print(f"    {_c('lane   ', 'DIM')} {lane}")
        print(f"    {_c('goal   ', 'DIM')} {_c(goal_disp, 'DIM')}")
        print(f"    {_c('at     ', 'DIM')} {_c(written_at, 'DIM')}")
    else:
        print(_c("  Last run", "B"))
        print(f"    {_c('·', 'DIM')} no runs yet — try `fob delegate` or `fob demo`")

    print()

    overall_ok = sb_ok and cp_ok
    return 0 if overall_ok else 1
