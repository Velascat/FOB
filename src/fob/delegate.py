"""fob delegate — trigger a full execution through the ControlPlane pipeline.

Wraps the two ControlPlane entrypoints without duplicating their logic:

    1. control_plane.entrypoints.worker.main   → planning (proposal + lane decision)
    2. control_plane.entrypoints.execute.main  → execution (adapter run + artifacts)

Usage:
    fob delegate --goal "Refresh README summary"
    fob delegate --goal "Fix lint errors" --repo-key myrepo --clone-url https://...
    fob delegate --goal "..." --task-type lint_fix --dry-run
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m", "MAG": "\033[35m",
}


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


def _tag(label: str, msg: str) -> None:
    print(f"  {_c(f'[{label}]', 'CYN', 'B')} {msg}")


def _ok(msg: str) -> None:
    print(f"  {_c('✓', 'GRN')} {msg}")


def _fail(msg: str) -> None:
    print(f"  {_c('✗', 'RED')} {msg}")


def _info(msg: str) -> None:
    print(f"  {_c('·', 'DIM')} {msg}")


def _warn(msg: str) -> None:
    print(f"  {_c('⚠', 'YLW')} {msg}")


def _cp_python(cp_repo: Path) -> str:
    venv_python = cp_repo / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else "python3"


def _repo_root(name: str) -> Path:
    return Path.home() / "Documents" / "GitHub" / name


_DEMO_CP_CONFIG = """\
plane:
  base_url: http://localhost:8080
  api_token_env: PLANE_API_TOKEN
  workspace_slug: demo
  project_id: demo
git:
  provider: github
kodo:
  binary: kodo
repos: {}
"""


def _parse_args(args: list[str]) -> dict:
    parsed: dict = {
        "goal": None,
        "task_type": "documentation",
        "repo_key": "default",
        "clone_url": "https://example.invalid/placeholder.git",
        "project_id": None,
        "task_id": None,
        "task_branch": None,
        "dry_run": False,
        "json": False,
    }
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--goal" and i + 1 < len(args):
            parsed["goal"] = args[i + 1]; i += 2
        elif a == "--task-type" and i + 1 < len(args):
            parsed["task_type"] = args[i + 1]; i += 2
        elif a == "--repo-key" and i + 1 < len(args):
            parsed["repo_key"] = args[i + 1]; i += 2
        elif a == "--clone-url" and i + 1 < len(args):
            parsed["clone_url"] = args[i + 1]; i += 2
        elif a == "--project-id" and i + 1 < len(args):
            parsed["project_id"] = args[i + 1]; i += 2
        elif a == "--task-id" and i + 1 < len(args):
            parsed["task_id"] = args[i + 1]; i += 2
        elif a == "--task-branch" and i + 1 < len(args):
            parsed["task_branch"] = args[i + 1]; i += 2
        elif a == "--dry-run":
            parsed["dry_run"] = True; i += 1
        elif a == "--json":
            parsed["json"] = True; i += 1
        else:
            i += 1
    return parsed


def run_delegate(args: list[str]) -> int:
    opts = _parse_args(args)

    # Prompt for goal if not provided
    if not opts["goal"]:
        if sys.stdin.isatty():
            try:
                opts["goal"] = input(_c("  goal: ", "B")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 1
        if not opts["goal"]:
            _fail("--goal is required")
            return 1

    cp_repo = _repo_root("ControlPlane")
    if not cp_repo.exists():
        _fail(f"ControlPlane not found at {cp_repo}")
        return 1

    task_id = opts["task_id"] or f"fob-{uuid.uuid4().hex[:8]}"
    project_id = opts["project_id"] or "fob-delegate"
    task_branch = opts["task_branch"] or f"auto/{task_id}"

    if not opts["json"]:
        print(_c("\n  fob delegate", "B", "CYN") + _c(" — delegating task to ControlPlane", "DIM"))
        print()
        _tag("FOB", f"goal={opts['goal']!r}  type={opts['task_type']}  repo={opts['repo_key']}")

    if opts["dry_run"]:
        if not opts["json"]:
            _info("--dry-run: planning only, skipping execution")

    # ── Step 1: Planning ──────────────────────────────────────────────────────

    python = _cp_python(cp_repo)
    plan_cmd = [
        python, "-m", "control_plane.entrypoints.worker.main",
        "--goal", opts["goal"],
        "--task-type", opts["task_type"],
        "--repo-key", opts["repo_key"],
        "--clone-url", opts["clone_url"],
        "--project-id", project_id,
        "--task-id", task_id,
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(cp_repo / "src")

    if not opts["json"]:
        print(f"  {_c('──', 'DIM')} planning")

    plan_proc = subprocess.run(plan_cmd, cwd=cp_repo, env=env, capture_output=True, text=True)

    # Try to parse structured JSON regardless of exit code — the worker emits
    # structured error JSON on SwitchBoard failure (exit 1 + JSON to stdout).
    try:
        bundle = json.loads(plan_proc.stdout)
    except Exception:
        # stdout is not JSON at all — genuine crash
        _fail("Planning crashed (no JSON output)")
        _info(plan_proc.stderr.strip() or plan_proc.stdout.strip())
        return 1

    if plan_proc.returncode != 0:
        # Structured failure from worker — routing_failure or similar
        error_type = bundle.get("error_type", "unknown")
        message = bundle.get("message", "planning failed")
        partial_run_id = bundle.get("partial_run_id")

        if opts["json"]:
            print(json.dumps({
                "error": bundle.get("error", "planning_failure"),
                "error_type": error_type,
                "message": message,
                "partial_run_id": partial_run_id,
            }, indent=2))
        else:
            _fail(f"Planning failed — {error_type}")
            _info(message)
            if partial_run_id:
                from fob.runs import runs_root
                _info(f"partial artifacts: {runs_root() / partial_run_id}")
        return 1

    decision = bundle.get("decision", {})
    lane = decision.get("selected_lane", "?")
    backend = decision.get("selected_backend", "?")

    if not opts["json"]:
        _tag("ControlPlane", f"proposal created — id={bundle.get('proposal', {}).get('proposal_id', '?')[:8]}…")
        _tag("SwitchBoard", f"selected lane={lane}  backend={backend}")

    if opts["dry_run"]:
        if not opts["json"]:
            _ok("Dry run complete — proposal and lane decision obtained")
        else:
            print(json.dumps({"dry_run": True, "lane": lane, "backend": backend}))
        return 0

    # ── Step 2: Execution ─────────────────────────────────────────────────────

    with tempfile.TemporaryDirectory(prefix="fob-delegate-") as tmpdir:
        tmp = Path(tmpdir)
        bundle_file = tmp / "bundle.json"
        bundle_file.write_text(json.dumps(bundle), encoding="utf-8")
        config_file = tmp / "control_plane.yaml"
        config_file.write_text(_DEMO_CP_CONFIG, encoding="utf-8")
        workspace = tmp / "workspace"
        workspace.mkdir()
        result_file = tmp / "result.json"

        exec_cmd = [
            python, "-m", "control_plane.entrypoints.execute.main",
            "--config", str(config_file),
            "--bundle", str(bundle_file),
            "--workspace-path", str(workspace),
            "--task-branch", task_branch,
            "--output", str(result_file),
        ]

        if not opts["json"]:
            _tag("Adapter", f"executing  lane={lane}  backend={backend}")

        exec_proc = subprocess.run(exec_cmd, cwd=cp_repo, env=env, capture_output=True, text=True)

        if not result_file.exists():
            if exec_proc.returncode != 0:
                _fail("Execute entrypoint crashed (no output file)")
                _info(exec_proc.stderr.strip() or exec_proc.stdout.strip())
            else:
                _fail("Execute entrypoint produced no output")
            return 1

        outcome = json.loads(result_file.read_text(encoding="utf-8"))

        # Coordinator crash produces structured error JSON without 'result' key
        if exec_proc.returncode != 0 and "error" in outcome and "result" not in outcome:
            error_type = outcome.get("error_type", "unknown")
            message = outcome.get("message", "execution failed")
            partial_run_id = outcome.get("partial_run_id")
            if opts["json"]:
                print(json.dumps({
                    "error": outcome.get("error", "execution_failure"),
                    "error_type": error_type,
                    "message": message,
                    "partial_run_id": partial_run_id,
                }, indent=2))
            else:
                _fail(f"Execution failed — {error_type}")
                _info(message)
                if partial_run_id:
                    from fob.runs import runs_root
                    _info(f"partial artifacts: {runs_root() / partial_run_id}")
            return 1

    exec_result = outcome.get("result", {})
    run_id = exec_result.get("run_id", "?")
    status = exec_result.get("status", "unknown")
    success = exec_result.get("success", False)
    executed = outcome.get("executed", False)
    failure_category = exec_result.get("failure_category")

    from fob.runs import runs_root
    artifacts_dir = runs_root() / run_id

    if opts["json"]:
        print(json.dumps({
            "run_id": run_id,
            "status": status,
            "success": success,
            "executed": executed,
            "lane": lane,
            "backend": backend,
            "failure_category": failure_category,
            "artifacts_dir": str(artifacts_dir),
        }, indent=2))
        return 0

    if not opts["json"]:
        if executed and success:
            _tag("Done", _c(f"status={status}", "GRN"))
        elif executed and not success:
            _warn(f"Backend ran but failed — status={status}  category={failure_category}")
            _info("This is expected when the backend binary is not installed on this machine.")
        else:
            policy_notes = outcome.get("policy_decision", {}).get("notes", "")
            _warn(f"Execution skipped by policy gate — status={status}")
            if policy_notes:
                _info(f"policy: {policy_notes}")

        print()
        print(f"  {_c('Run ID    ', 'DIM')} {_c(run_id, 'B')}")
        print(f"  {_c('Artifacts ', 'DIM')} {_c(str(artifacts_dir), 'DIM')}")
        print()

    return 0
