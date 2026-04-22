"""fob demo — validate the selector and planning handoff architecture."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


@dataclass
class StepResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class DemoResult:
    steps: list[StepResult] = field(default_factory=list)

    def add(self, step: StepResult) -> None:
        self.steps.append(step)

    @property
    def passed(self) -> bool:
        return all(step.passed for step in self.steps)


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, Any]:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _http_post(url: str, payload: dict[str, Any], timeout: float = 10.0) -> tuple[int, Any]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        try:
            body = json.loads(body_text)
        except Exception:
            body = {"raw": body_text}
        return exc.code, body
    except Exception as exc:
        return 0, {"error": str(exc)}


def _repo_root(name: str) -> Path:
    return Path.home() / "Documents" / "GitHub" / name


def _find_workstation() -> Path | None:
    repo = _repo_root("WorkStation")
    return repo if (repo / "scripts" / "ensure-up.sh").exists() else None


def step_preflight(workstation_root: Path | None) -> StepResult:
    _section("1 · Preflight")
    if workstation_root is None:
        _fail("WorkStation repo not found")
        return StepResult("preflight", False, "WorkStation not found")

    expected = {
        "WorkStation": workstation_root,
        "SwitchBoard": _repo_root("SwitchBoard"),
        "ControlPlane": _repo_root("ControlPlane"),
    }
    missing: list[str] = []
    for name, path in expected.items():
        if path.exists():
            _ok(f"{name}: {path}")
        else:
            _fail(f"{name} missing at {path}")
            missing.append(name)

    env_file = workstation_root / ".env"
    if env_file.exists():
        _ok(".env present")
    else:
        _fail(".env missing")
        missing.append(".env")

    endpoints = workstation_root / "config" / "workstation" / "endpoints.yaml"
    if endpoints.exists():
        _ok("workstation endpoints config present")
    else:
        _fail("config/workstation/endpoints.yaml missing")
        missing.append("endpoints.yaml")

    return StepResult("preflight", not missing, ", ".join(missing) if missing else "all checks passed")


def step_stack(workstation_root: Path) -> StepResult:
    _section("2 · Stack")
    script = workstation_root / "scripts" / "ensure-up.sh"
    result = subprocess.run(["bash", str(script)], capture_output=False)
    if result.returncode == 0:
        _ok("WorkStation stack ready")
        return StepResult("stack", True, "healthy")
    _fail(f"ensure-up.sh exited {result.returncode}")
    return StepResult("stack", False, f"ensure-up.sh exited {result.returncode}")


def step_health() -> StepResult:
    _section("3 · Health")
    port = os.environ.get("PORT_SWITCHBOARD", "20401")
    code, body = _http_get(f"http://localhost:{port}/health")
    if code == 200:
        _ok(f"SwitchBoard health: {body.get('status', 'ok')}")
        return StepResult("health", True, body.get("status", "ok"))
    _fail(f"SwitchBoard health failed: HTTP {code}")
    return StepResult("health", False, f"HTTP {code}")


def step_route() -> StepResult:
    _section("4 · Route Selection")
    port = os.environ.get("PORT_SWITCHBOARD", "20401")
    payload = {
        "task_id": "fob-demo-route",
        "project_id": "fob-demo",
        "task_type": "documentation",
        "execution_mode": "goal",
        "goal_text": "Refresh the architecture summary wording",
        "target": {
            "repo_key": "docs",
            "clone_url": "https://example.invalid/docs.git",
            "base_branch": "main",
            "allowed_paths": [],
        },
        "priority": "normal",
        "risk_level": "low",
        "constraints": {
            "allowed_paths": [],
            "require_clean_validation": True,
        },
        "validation_profile": {
            "profile_name": "default",
            "commands": [],
        },
        "branch_policy": {
            "push_on_success": True,
            "open_pr": False,
        },
        "labels": [],
    }
    code, body = _http_post(f"http://localhost:{port}/route", payload)
    if code == 200:
        _ok(f"lane={body['selected_lane']} backend={body['selected_backend']}")
        return StepResult("route", True, f"{body['selected_lane']}/{body['selected_backend']}")
    _fail(f"SwitchBoard route failed: HTTP {code}")
    return StepResult("route", False, f"HTTP {code}")


def step_controlplane_handoff() -> StepResult:
    _section("5 · ControlPlane Handoff")
    repo = _repo_root("ControlPlane")
    cmd = [
        "python",
        "-m",
        "control_plane.entrypoints.worker.main",
        "--goal",
        "Refresh architecture wording",
        "--task-type",
        "documentation",
        "--repo-key",
        "docs",
        "--clone-url",
        "https://example.invalid/docs.git",
        "--project-id",
        "fob-demo",
        "--task-id",
        "fob-demo-worker",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(repo / "src"),
            str(repo.parent / "SwitchBoard" / "src"),
        ]
    )
    result = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        _fail("ControlPlane worker handoff failed")
        _info(result.stderr.strip() or result.stdout.strip())
        return StepResult("controlplane", False, f"exit {result.returncode}")
    body = json.loads(result.stdout)
    summary = body["run_summary"]
    _ok(summary)
    return StepResult("controlplane", True, summary)


def _print_summary(result: DemoResult) -> None:
    _section("Summary")
    for step in result.steps:
        marker = _c("PASS", "GRN") if step.passed else _c("FAIL", "RED")
        print(f"  {marker} {step.name:<14} {step.detail}")
    print()
    if result.passed:
        _ok("Architecture validation passed")
    else:
        _fail("Architecture validation failed")


def run_demo(args: list[str]) -> int:
    no_start = "--no-start" in args
    print(_c("\n  fob demo", "B", "CYN") + _c(" — selector and planning handoff validation", "DIM"))
    workstation_root = _find_workstation()
    result = DemoResult()

    preflight = step_preflight(workstation_root)
    result.add(preflight)
    if not preflight.passed or workstation_root is None:
        _print_summary(result)
        return 1

    if not no_start:
        stack = step_stack(workstation_root)
        result.add(stack)
        if not stack.passed:
            _print_summary(result)
            return 1

    time.sleep(1)
    for step in (step_health(), step_route(), step_controlplane_handoff()):
        result.add(step)
        if not step.passed:
            _print_summary(result)
            return 1

    _print_summary(result)
    return 0
