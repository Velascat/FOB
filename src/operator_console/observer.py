"""console observer — derive goal context from local state.

Priority order for goal:
    1. --goal CLI arg
    2. Objective section in .console/task.md (in cwd or repo root)
    3. Default: "Analyze repository health and suggest improvements"

Priority order for repo_key / clone_url:
    1. --repo-key / --clone-url CLI args
    2. Derived from git remote 'origin'
    3. Fallback sentinel values
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


_DEFAULT_GOAL = "Analyze repository health and suggest improvements"
_DEFAULT_REPO_KEY = "default"
_DEFAULT_CLONE_URL = "https://example.invalid/placeholder.git"


def _parse_args(args: list[str]) -> dict:
    parsed: dict = {
        "goal": None,
        "task_type": None,
        "repo_key": None,
        "clone_url": None,
        "repo_path": None,
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
        elif a == "--repo-path" and i + 1 < len(args):
            parsed["repo_path"] = args[i + 1]; i += 2
        else:
            i += 1
    return parsed


def _read_mission_goal(repo_path: Path) -> str | None:
    """Extract content of Objective section from .console/task.md."""
    mission_file = repo_path / ".console" / "task.md"
    if not mission_file.exists():
        return None
    text = mission_file.read_text(encoding="utf-8")

    # Find the ## Objective section and extract its body until the next ## or EOF
    match = re.search(r"^##\s+Objective\s*\n(.*?)(?=^##|\Z)", text, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    body = match.group(1).strip()

    # Reject placeholder / empty content
    if not body or body.startswith("[") or body == "":
        return None
    return body


def _git_remote_url(repo_path: Path) -> str | None:
    """Return origin remote URL for the repo at repo_path, or None."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception:
        pass
    return None


def _repo_key_from_url(url: str) -> str:
    """Derive a short repo key from a clone URL (last path component, no .git)."""
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or _DEFAULT_REPO_KEY


def _find_repo_root(start: Path) -> Path:
    """Walk up from start to find the git repo root, falling back to start."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass
    return start


def observe(args: list[str], cwd: Path | None = None) -> dict:
    """Derive goal context from local state. Returns dict with goal/task_type/repo_key/clone_url."""
    opts = _parse_args(args)
    repo_path = Path(opts["repo_path"]) if opts["repo_path"] else _find_repo_root(cwd or Path.cwd())

    # Goal resolution
    goal = opts["goal"]
    if not goal:
        goal = _read_mission_goal(repo_path)
    if not goal:
        goal = _DEFAULT_GOAL

    # Clone URL + repo key
    clone_url = opts["clone_url"]
    if not clone_url:
        clone_url = _git_remote_url(repo_path)
    if not clone_url:
        clone_url = _DEFAULT_CLONE_URL

    repo_key = opts["repo_key"]
    if not repo_key:
        repo_key = _repo_key_from_url(clone_url)

    task_type = opts["task_type"] or "documentation"

    return {
        "goal": goal,
        "task_type": task_type,
        "repo_key": repo_key,
        "clone_url": clone_url,
        "repo_path": str(repo_path),
        "source": "file" if (not opts["goal"] and _read_mission_goal(repo_path)) else
                  ("arg" if opts["goal"] else "default"),
    }
