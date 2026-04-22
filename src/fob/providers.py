"""fob providers — report selector and lane readiness."""
from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m", "MAG": "\033[35m",
}


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


def _ok(msg: str) -> None:
    print(f"  {_c('✓', 'GRN')} {msg}")


def _fail(msg: str) -> None:
    print(f"  {_c('✗', 'RED')} {msg}")


def _info(msg: str) -> None:
    print(f"  {_c('·', 'DIM')} {msg}")


def _section(title: str) -> None:
    print()
    print(_c(f"── {title} ", "B", "CYN") + _c("─" * max(0, 48 - len(title)), "DIM"))


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _find_repo(name: str) -> Path:
    return Path.home() / "Documents" / "GitHub" / name


def run_providers(args: list[str]) -> int:
    do_wait = "--wait" in args
    switchboard_port = os.environ.get("PORT_SWITCHBOARD", "20401")
    switchboard_health = f"http://localhost:{switchboard_port}/health"

    print(_c("\n  fob providers", "B", "CYN") + _c(" — execution lane readiness", "DIM"))

    _section("Selector")
    if _http_ok(switchboard_health):
        _ok(f"SwitchBoard healthy at {switchboard_health}")
    else:
        _fail(f"SwitchBoard not reachable at {switchboard_health}")
        _info("Start the stack first with:  fob demo")
        if not do_wait:
            return 1

    _section("Lane Inputs")
    local_lane_cfg = _find_repo("WorkStation") / "config" / "workstation" / "local_lane.yaml"
    if local_lane_cfg.exists():
        _ok(f"aider_local config present: {local_lane_cfg}")
    else:
        _fail("aider_local config missing")
        _info("Copy WorkStation/config/workstation/local_lane.example.yaml to local_lane.yaml")

    for binary in ("claude", "codex", "aider"):
        if os.system(f"which {binary} >/dev/null 2>&1") == 0:
            _ok(f"{binary} CLI available")
        else:
            _fail(f"{binary} CLI not found")

    _section("ControlPlane")
    worker_path = _find_repo("ControlPlane") / "src" / "control_plane" / "entrypoints" / "worker" / "main.py"
    if worker_path.exists():
        _ok("planning handoff entrypoint present")
    else:
        _fail("planning handoff entrypoint missing")

    if do_wait:
        _section("Waiting")
        _info("Polling for SwitchBoard readiness... (Ctrl+C to stop)")
        try:
            while True:
                if _http_ok(switchboard_health):
                    _ok("SwitchBoard is ready")
                    return 0
                time.sleep(3)
                print(".", end="", flush=True)
        except KeyboardInterrupt:
            print()
            _info("Stopped waiting.")

    return 0
