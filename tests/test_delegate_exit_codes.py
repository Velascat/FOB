"""Tests for run_delegate() — queue submission wizard.

Verifies exit codes and queue file output without any subprocess calls
or OperationsCenter dependencies.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from operator_console.delegate import run_delegate
from operator_console.queue import queue_dir, list_pending


def _patch_queue(tmp_path: Path):
    """Redirect the queue directory to a temp path."""
    q = tmp_path / "queue"
    q.mkdir()
    return patch("operator_console.queue.queue_dir", return_value=q)


def _patch_repos(repos: dict):
    """Stub _discover_repos with a fixed set."""
    return patch("operator_console.delegate._discover_repos", return_value=repos)


def _fake_repos(tmp_path: Path) -> dict:
    repo = tmp_path / "MyRepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return {"MyRepo": repo}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestDelegateSubmit:
    def test_noninteractive_success_returns_0(self, tmp_path):
        repos = _fake_repos(tmp_path)
        with _patch_repos(repos), _patch_queue(tmp_path):
            code = run_delegate([
                "--goal", "Fix the login bug",
                "--task-type", "bug",
                "--repo", "MyRepo",
            ])
        assert code == 0

    def test_writes_queue_file(self, tmp_path):
        repos = _fake_repos(tmp_path)
        q = tmp_path / "queue"
        q.mkdir(exist_ok=True)
        with _patch_repos(repos), patch("operator_console.queue.queue_dir", return_value=q):
            run_delegate([
                "--goal", "Fix the login bug",
                "--task-type", "bug",
                "--repo", "MyRepo",
            ])
        files = list(q.glob("*.json"))
        assert len(files) == 1
        payload = json.loads(files[0].read_text())
        assert payload["goal"] == "Fix the login bug"
        assert payload["task_type"] == "bug"
        assert payload["repo_name"] == "MyRepo"
        assert payload["source"] == "operator"

    def test_json_flag_prints_json(self, tmp_path, capsys):
        repos = _fake_repos(tmp_path)
        q = tmp_path / "queue"
        q.mkdir(exist_ok=True)
        with _patch_repos(repos), patch("operator_console.queue.queue_dir", return_value=q):
            code = run_delegate([
                "--goal", "Fix the login bug",
                "--task-type", "bug",
                "--repo", "MyRepo",
                "--json",
            ])
        assert code == 0
        out = capsys.readouterr().out
        # JSON block starts at the first '{'
        json_start = out.index("{")
        data = json.loads(out[json_start:])
        assert data["queued"] is True
        assert data["goal"] == "Fix the login bug"
        assert data["task_type"] == "bug"


# ---------------------------------------------------------------------------
# Validation failures → exit 1
# ---------------------------------------------------------------------------

class TestDelegateValidation:
    def test_missing_goal_noninteractive_returns_1(self, tmp_path):
        repos = _fake_repos(tmp_path)
        with _patch_repos(repos), _patch_queue(tmp_path), \
             patch("sys.stdin.isatty", return_value=False):
            code = run_delegate(["--task-type", "bug", "--repo", "MyRepo"])
        assert code == 1

    def test_missing_repo_noninteractive_returns_1(self, tmp_path):
        with _patch_repos({}), _patch_queue(tmp_path), \
             patch("sys.stdin.isatty", return_value=False):
            code = run_delegate(["--goal", "Fix something", "--task-type", "bug"])
        assert code == 1

    def test_unknown_task_type_returns_1(self, tmp_path):
        repos = _fake_repos(tmp_path)
        with _patch_repos(repos), _patch_queue(tmp_path):
            code = run_delegate([
                "--goal", "Fix something",
                "--task-type", "notarealtype",
                "--repo", "MyRepo",
            ])
        assert code == 1

    def test_empty_goal_returns_1(self, tmp_path):
        repos = _fake_repos(tmp_path)
        with _patch_repos(repos), _patch_queue(tmp_path), \
             patch("sys.stdin.isatty", return_value=False):
            code = run_delegate(["--goal", "", "--task-type", "bug", "--repo", "MyRepo"])
        assert code == 1
