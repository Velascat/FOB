"""fob demo — golden-path vertical-slice demo command.

Proves the full platform is operational:
  1. Preflight    — repos and config exist, required binaries available
  2. Stack        — WorkStation stack is healthy or started
  3. SwitchBoard  — sends a deterministic request, shows routing decision
  4. ControlPlane — sends a request as ControlPlane would (tenant headers),
                    proves the shared routing path works for autonomous traffic
  5. Summary      — per-step status, artifact locations, exit code
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── colour helpers ────────────────────────────────────────────────────────────

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


# ── result tracking ───────────────────────────────────────────────────────────

@dataclass
class StepResult:
    name: str
    passed: bool
    detail: str = ""
    artifact: str = ""


@dataclass
class DemoResult:
    steps: list[StepResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def add(self, step: StepResult) -> None:
        self.steps.append(step)

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.steps)

    @property
    def failed_step(self) -> StepResult | None:
        return next((s for s in self.steps if not s.passed), None)


# ── HTTP helpers (no external deps beyond stdlib + optional httpx) ────────────

def _http_get(url: str, timeout: float = 5.0) -> tuple[int, Any]:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception:
        return 0, {}


def _http_post(
    url: str,
    payload: dict,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
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


# ── platform discovery ────────────────────────────────────────────────────────

def _find_workstation() -> Path | None:
    candidates = [
        Path(__file__).resolve().parents[4] / "WorkStation",
        Path.home() / "Documents" / "GitHub" / "WorkStation",
    ]
    for c in candidates:
        if (c / "scripts" / "ensure-up.sh").exists():
            return c
    return None


def _find_switchboard_url() -> str:
    port = os.environ.get("PORT_SWITCHBOARD", "20401")
    return f"http://localhost:{port}"


# ── demo steps ────────────────────────────────────────────────────────────────

def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=value .env file, ignoring comments and blanks."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def step_preflight(workstation_root: Path | None) -> StepResult:
    _section("1 · Preflight")

    issues: list[str] = []

    if workstation_root is None:
        _fail("WorkStation repo not found")
        _info("expected at ~/Documents/GitHub/WorkStation")
        return StepResult("preflight", False, "WorkStation not found")

    _ok(f"WorkStation : {workstation_root}")

    # .env
    env_file = workstation_root / ".env"
    if not env_file.exists():
        issues.append(".env")
        _fail(".env missing")
        _info(f"  fix: cp {workstation_root}/.env.example {workstation_root}/.env")
    else:
        _ok(".env present")

    # 9router source repo (needed as Docker build context)
    nine_router_repo = workstation_root.parent / "9router"
    if not (nine_router_repo / "package.json").exists():
        issues.append("9router repo")
        _fail(f"9router source not found at {nine_router_repo}")
        _info("  fix: git clone https://github.com/decolua/9router " + str(nine_router_repo))
    else:
        _ok(f"9router repo : {nine_router_repo}")

    # SwitchBoard source repo (needed as Docker build context)
    switchboard_repo = workstation_root.parent / "SwitchBoard"
    if not (switchboard_repo / "pyproject.toml").exists():
        issues.append("SwitchBoard repo")
        _fail(f"SwitchBoard source not found at {switchboard_repo}")
        _info("  fix: git clone https://github.com/Velascat/SwitchBoard " + str(switchboard_repo))
    else:
        _ok(f"SwitchBoard  : {switchboard_repo}")

    # config/9router/.env — needs JWT_SECRET and INITIAL_PASSWORD
    # Provider credentials are set via 9router dashboard, NOT here.
    nr_env_path = workstation_root / "config" / "9router" / ".env"
    if not nr_env_path.exists():
        issues.append("9router .env")
        _fail("config/9router/.env missing")
        _info(f"  fix: cp {workstation_root}/config/9router/.env.example {nr_env_path}")
        _info("       then set JWT_SECRET and INITIAL_PASSWORD")
    else:
        nr_env = _load_env_file(nr_env_path)
        missing_required = [k for k in ("JWT_SECRET", "INITIAL_PASSWORD")
                            if not nr_env.get(k) or nr_env[k].startswith("change-me")]
        if missing_required:
            issues.append("9router secrets")
            _fail(f"config/9router/.env: {', '.join(missing_required)} not set")
            _info("  fix: set JWT_SECRET=$(openssl rand -hex 32) and INITIAL_PASSWORD=yourpassword")
        else:
            _ok("9router .env  : JWT_SECRET and INITIAL_PASSWORD set")
            _info("providers are connected via the 9router dashboard after startup")

    # Docker
    result = subprocess.run(["which", "docker"], capture_output=True)
    if result.returncode != 0:
        issues.append("docker")
        _fail("docker not found — install Docker")
    else:
        # Check daemon is running
        ping = subprocess.run(["docker", "info"], capture_output=True)
        if ping.returncode != 0:
            issues.append("docker daemon")
            _fail("Docker daemon not running — start Docker Desktop or dockerd")
        else:
            _ok("Docker daemon running")

    if issues:
        print()
        _fail(f"Preflight failed: {', '.join(issues)}")
        return StepResult("preflight", False, f"missing: {', '.join(issues)}")
    return StepResult("preflight", True, "all checks passed")


def step_stack(workstation_root: Path) -> StepResult:
    _section("2 · Stack")

    script = workstation_root / "scripts" / "ensure-up.sh"
    if not script.exists():
        _fail(f"ensure-up.sh not found at {script}")
        return StepResult("stack", False, "ensure-up.sh missing")

    result = subprocess.run(
        ["bash", str(script)],
        capture_output=False,
    )
    if result.returncode == 0:
        return StepResult("stack", True, "healthy")
    return StepResult("stack", False, f"ensure-up.sh exited {result.returncode}")


def step_health(switchboard_url: str) -> StepResult:
    _section("3 · Health")

    sb_port = switchboard_url.rsplit(":", 1)[-1]
    nr_port = os.environ.get("PORT_9ROUTER", "20128")

    all_ok = True
    for name, url in [
        ("SwitchBoard", f"http://localhost:{sb_port}/health"),
        ("9router    ", f"http://localhost:{nr_port}/health"),
    ]:
        code, body = _http_get(url, timeout=5)
        if code == 200:
            _ok(f"{name}  ({url})")
        else:
            _fail(f"{name}  ({url})  → HTTP {code or 'no response'}")
            all_ok = False

    return StepResult("health", all_ok, "all healthy" if all_ok else "one or more services unhealthy")


def step_providers(nr_port: str = "20128") -> StepResult:
    _section("3b · 9router providers")

    # Try to list configured providers via 9router's API
    code, body = _http_get(f"http://localhost:{nr_port}/api/providers", timeout=5)

    if code == 200:
        providers = body if isinstance(body, list) else body.get("providers", [])
        active = [p for p in providers if p.get("enabled") or p.get("active") or p.get("connected")]
        if active:
            names = [p.get("name", p.get("id", "?")) for p in active]
            _ok(f"providers : {', '.join(names)}")
            return StepResult("providers", True, f"{len(active)} active")

    # No providers configured — guide the user
    _fail("No providers configured in 9router")
    print()
    _info("Connect a free provider at http://localhost:20128 (no API keys needed):")
    print()
    print(f"    {_c('Kiro', 'B')}    {_c('→  free Claude Sonnet 4.5  (AWS Builder ID / GitHub OAuth)', 'DIM')}")
    print(f"    {_c('iFlow', 'B')}   {_c('→  free Deepseek R1, Qwen3  (OAuth)', 'DIM')}")
    print(f"    {_c('Gemini', 'B')}  {_c('→  free Gemini 2.5 Pro  (Google OAuth, quota-limited)', 'DIM')}")
    print(f"    {_c('Ollama', 'B')}  {_c('→  free local models  (install: https://ollama.com)', 'DIM')}")
    print()
    _info("After connecting a provider, re-run: fob demo --no-start")
    return StepResult("providers", False, "no providers configured")


def step_switchboard_smoke(switchboard_url: str) -> StepResult:
    _section("4 · SwitchBoard routing proof")

    import uuid
    rid = uuid.uuid4().hex[:12]
    payload = {
        "model": "fast",
        "messages": [{"role": "user", "content": "Reply with a single word: ready"}],
    }
    headers = {
        "X-Request-ID": rid,
        "X-SwitchBoard-Tenant-ID": "fob-demo",
        "Authorization": "Bearer sk-demo",
    }

    _info(f"request_id : {rid}")
    _info(f"model hint : fast")

    code, body = _http_post(
        f"{switchboard_url}/v1/chat/completions",
        payload,
        headers=headers,
        timeout=30,
    )

    if code != 200:
        _fail(f"HTTP {code}  —  {json.dumps(body)[:120]}")
        return StepResult("switchboard", False, f"HTTP {code}")

    try:
        reply = body["choices"][0]["message"]["content"]
        _ok(f"response   : {reply!r}")
    except (KeyError, IndexError):
        _fail("unexpected response shape")
        return StepResult("switchboard", False, "malformed response")

    # Fetch the routing decision
    time.sleep(0.2)
    dcode, decisions = _http_get(
        f"{switchboard_url}/admin/decisions/recent?n=1", timeout=5
    )
    decision_detail = ""
    if dcode == 200 and decisions:
        d = decisions[0]
        profile = d.get("profile_name", "?")
        model   = d.get("downstream_model", "?")
        rule    = d.get("rule_name", "?")
        lat     = d.get("latency_ms")
        lat_str = f"{lat:.0f} ms" if lat is not None else "?"
        _ok(f"profile    : {profile}  →  {model}")
        _info(f"rule       : {rule}")
        _info(f"latency    : {lat_str}")
        decision_detail = f"profile={profile} model={model} rule={rule}"

    return StepResult("switchboard", True, decision_detail)


def step_controlplane_proof(switchboard_url: str) -> StepResult:
    _section("5 · ControlPlane routing proof")
    _info("Sending a request as ControlPlane would (X-SwitchBoard-Tenant-ID: control-plane)")

    import uuid
    rid = uuid.uuid4().hex[:12]
    payload = {
        "model": "capable",
        "messages": [
            {
                "role": "user",
                "content": (
                    "You are a planning assistant. "
                    "Reply with a single word: acknowledged"
                ),
            }
        ],
    }
    headers = {
        "X-Request-ID": rid,
        "X-SwitchBoard-Tenant-ID": "control-plane",
        "X-SwitchBoard-Profile": "capable",
        "Authorization": "Bearer sk-demo",
    }

    _info(f"request_id : {rid}")
    _info(f"profile    : capable (ControlPlane default)")

    code, body = _http_post(
        f"{switchboard_url}/v1/chat/completions",
        payload,
        headers=headers,
        timeout=30,
    )

    if code != 200:
        _fail(f"HTTP {code}  —  {json.dumps(body)[:120]}")
        return StepResult("controlplane", False, f"HTTP {code}")

    try:
        reply = body["choices"][0]["message"]["content"]
        _ok(f"response   : {reply!r}")
    except (KeyError, IndexError):
        _fail("unexpected response shape")
        return StepResult("controlplane", False, "malformed response")

    time.sleep(0.2)
    dcode, decisions = _http_get(
        f"{switchboard_url}/admin/decisions/recent?n=1", timeout=5
    )
    if dcode == 200 and decisions:
        d = decisions[0]
        tenant = d.get("tenant_id", "?")
        profile = d.get("profile_name", "?")
        _ok(f"tenant     : {tenant}  profile={profile}")

    return StepResult("controlplane", True, "ControlPlane traffic routed successfully")


# ── summary ───────────────────────────────────────────────────────────────────

def print_summary(result: DemoResult) -> None:
    elapsed = time.time() - result.started_at
    _section("Summary")
    for step in result.steps:
        icon = _c("✓", "GRN") if step.passed else _c("✗", "RED")
        detail = f"  {_c(step.detail, 'DIM')}" if step.detail else ""
        print(f"  {icon}  {step.name:<16}{detail}")
    print()
    print(f"  {_c('elapsed', 'DIM')} : {elapsed:.1f}s")
    print()
    if result.passed:
        print(_c("  DEMO PASSED — platform is operational.", "GRN", "B"))
    else:
        failed = result.failed_step
        if failed:
            print(_c(f"  DEMO FAILED at step: {failed.name}", "RED", "B"))
            if failed.detail:
                print(_c(f"  {failed.detail}", "DIM"))
        print()
        print(_c("  Logs / admin:", "DIM"))
        print(_c("    bash scripts/health.sh         (WorkStation)", "DIM"))
        print(_c("    curl localhost:20401/admin/decisions/recent?n=5", "DIM"))
    print()


# ── entry point ───────────────────────────────────────────────────────────────

def run_demo(args: list[str]) -> int:
    verbose    = "--verbose" in args or "-v" in args
    no_start   = "--no-start" in args
    as_json    = "--json" in args

    print(_c("\n  fob demo", "B", "CYN") + _c(" — platform vertical slice", "DIM"))

    workstation_root = _find_workstation()
    switchboard_url  = _find_switchboard_url()

    result = DemoResult()

    # 1. Preflight
    pre = step_preflight(workstation_root)
    result.add(pre)
    if not pre.passed:
        print_summary(result)
        return 1

    # 2. Stack
    if no_start:
        _section("2 · Stack")
        _info("--no-start: skipping stack launch")
        result.add(StepResult("stack", True, "skipped (--no-start)"))
    else:
        stack = step_stack(workstation_root)  # type: ignore[arg-type]
        result.add(stack)
        if not stack.passed:
            print_summary(result)
            return 1

    # 3. Health
    health = step_health(switchboard_url)
    result.add(health)
    if not health.passed:
        print_summary(result)
        return 1

    # 3b. Provider check
    nr_port = os.environ.get("PORT_9ROUTER", "20128")
    prov = step_providers(nr_port)
    result.add(prov)
    if not prov.passed:
        print_summary(result)
        return 1

    # 4. SwitchBoard smoke
    sb = step_switchboard_smoke(switchboard_url)
    result.add(sb)
    if not sb.passed:
        print_summary(result)
        return 1

    # 5. ControlPlane proof
    cp = step_controlplane_proof(switchboard_url)
    result.add(cp)

    if as_json:
        summary = {
            "passed": result.passed,
            "elapsed_s": round(time.time() - result.started_at, 1),
            "switchboard_url": switchboard_url,
            "steps": [
                {"name": s.name, "passed": s.passed, "detail": s.detail}
                for s in result.steps
            ],
        }
        print(json.dumps(summary, indent=2))
        return 0 if result.passed else 1

    print_summary(result)
    return 0 if result.passed else 1
