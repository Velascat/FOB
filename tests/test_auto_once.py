"""Tests for observer.py and auto_once.py.

observer.observe() is a pure function (no subprocess / FS side effects when
given --goal and --clone-url on the command line). auto_once.run_auto_once()
is tested by mocking run_delegate so we don't need live OperationsCenter.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from operator_console.observer import (
    _DEFAULT_CLONE_URL,
    _DEFAULT_GOAL,
    _DEFAULT_REPO_KEY,
    _read_mission_goal,
    _repo_key_from_url,
    observe,
)


# ---------------------------------------------------------------------------
# observer — unit tests
# ---------------------------------------------------------------------------


class TestObserveArgPriority:
    """--goal / --repo-key / --clone-url flags take top priority."""

    def _observe(self, *args):
        # Patch git commands so tests don't depend on the environment
        with patch("operator_console.observer._git_remote_url", return_value=None), \
             patch("operator_console.observer._find_repo_root", return_value=Path("/tmp")):
            return observe(list(args))

    def test_goal_from_flag(self):
        ctx = self._observe("--goal", "Fix docs")
        assert ctx["goal"] == "Fix docs"

    def test_source_is_arg_when_flag_given(self):
        ctx = self._observe("--goal", "Fix docs")
        assert ctx["source"] == "arg"

    def test_task_type_default(self):
        ctx = self._observe("--goal", "Fix docs")
        assert ctx["task_type"] == "documentation"

    def test_task_type_from_flag(self):
        ctx = self._observe("--goal", "Fix docs", "--task-type", "lint_fix")
        assert ctx["task_type"] == "lint_fix"

    def test_repo_key_from_flag(self):
        ctx = self._observe("--goal", "g", "--repo-key", "myrepo")
        assert ctx["repo_key"] == "myrepo"

    def test_clone_url_from_flag(self):
        ctx = self._observe("--goal", "g", "--clone-url", "https://example.com/repo.git")
        assert ctx["clone_url"] == "https://example.com/repo.git"

    def test_default_goal_used_when_no_flag_no_mission(self):
        ctx = self._observe()
        assert ctx["goal"] == _DEFAULT_GOAL

    def test_source_is_default_when_fallback(self):
        ctx = self._observe()
        assert ctx["source"] == "default"

    def test_default_clone_url_when_no_remote(self):
        ctx = self._observe("--goal", "g")
        assert ctx["clone_url"] == _DEFAULT_CLONE_URL


class TestObserveMissionFile:
    """task.md is read when no --goal flag is given."""

    def test_reads_objective_section(self, tmp_path):
        console_dir = tmp_path / ".console"
        console_dir.mkdir()
        (console_dir / "task.md").write_text(
            "# Current Focus\n\n## Objective\n\nRefactor the routing layer.\n\n## Context\n\nSome context.\n"
        )
        with patch("operator_console.observer._find_repo_root", return_value=tmp_path), \
             patch("operator_console.observer._git_remote_url", return_value=None):
            ctx = observe([])
        assert ctx["goal"] == "Refactor the routing layer."
        assert ctx["source"] == "file"

    def test_placeholder_objective_ignored(self, tmp_path):
        console_dir = tmp_path / ".console"
        console_dir.mkdir()
        (console_dir / "task.md").write_text(
            "## Objective\n\n[Describe what you're working on]\n"
        )
        with patch("operator_console.observer._find_repo_root", return_value=tmp_path), \
             patch("operator_console.observer._git_remote_url", return_value=None):
            ctx = observe([])
        assert ctx["goal"] == _DEFAULT_GOAL
        assert ctx["source"] == "default"

    def test_missing_mission_file_uses_default(self, tmp_path):
        with patch("operator_console.observer._find_repo_root", return_value=tmp_path), \
             patch("operator_console.observer._git_remote_url", return_value=None):
            ctx = observe([])
        assert ctx["goal"] == _DEFAULT_GOAL

    def test_flag_overrides_mission_file(self, tmp_path):
        console_dir = tmp_path / ".console"
        console_dir.mkdir()
        (console_dir / "task.md").write_text(
            "## Objective\n\nMission goal.\n"
        )
        with patch("operator_console.observer._find_repo_root", return_value=tmp_path), \
             patch("operator_console.observer._git_remote_url", return_value=None):
            ctx = observe(["--goal", "Override goal"])
        assert ctx["goal"] == "Override goal"
        assert ctx["source"] == "arg"


class TestObserveRepoKey:
    """repo_key is derived from clone URL when not given as flag."""

    def test_repo_key_from_url(self):
        assert _repo_key_from_url("https://github.com/acme/my-service.git") == "my-service"
        assert _repo_key_from_url("git@github.com:acme/repo.git") == "repo"
        assert _repo_key_from_url("https://github.com/acme/repo") == "repo"

    def test_repo_key_derived_from_remote(self):
        with patch("operator_console.observer._find_repo_root", return_value=Path("/tmp")), \
             patch("operator_console.observer._git_remote_url", return_value="https://github.com/acme/widget.git"):
            ctx = observe(["--goal", "g"])
        assert ctx["repo_key"] == "widget"
        assert ctx["clone_url"] == "https://github.com/acme/widget.git"


class TestReadMissionGoal:
    """_read_mission_goal unit tests."""

    def test_returns_none_when_no_file(self, tmp_path):
        assert _read_mission_goal(tmp_path) is None

    def test_returns_none_when_no_objective_section(self, tmp_path):
        (tmp_path / ".console").mkdir()
        (tmp_path / ".console" / "task.md").write_text("## Context\n\nSome context.\n")
        assert _read_mission_goal(tmp_path) is None

    def test_returns_objective_content(self, tmp_path):
        (tmp_path / ".console").mkdir()
        (tmp_path / ".console" / "task.md").write_text(
            "## Objective\n\nImprove test coverage.\n"
        )
        assert _read_mission_goal(tmp_path) == "Improve test coverage."

    def test_multiline_objective(self, tmp_path):
        (tmp_path / ".console").mkdir()
        (tmp_path / ".console" / "task.md").write_text(
            "## Objective\n\nLine one.\nLine two.\n\n## Context\n\nOther.\n"
        )
        result = _read_mission_goal(tmp_path)
        assert "Line one." in result
        assert "Line two." in result


# ---------------------------------------------------------------------------
# auto_once — integration tests (mock run_delegate)
# ---------------------------------------------------------------------------


class TestAutoOnce:
    def _run(self, extra_args: list[str] = (), delegate_return: int = 0):
        with patch("operator_console.delegate.run_delegate", return_value=delegate_return) as mock_del, \
             patch("operator_console.observer._find_repo_root", return_value=Path("/tmp")), \
             patch("operator_console.observer._git_remote_url", return_value=None):
            from operator_console.auto_once import run_auto_once
            code = run_auto_once(["--goal", "Test goal", *extra_args])
        return code, mock_del

    def test_returns_0_on_success(self):
        code, _ = self._run()
        assert code == 0

    def test_returns_1_on_delegate_failure(self):
        code, _ = self._run(delegate_return=1)
        assert code == 1

    def test_passes_goal_to_delegate(self):
        _, mock_del = self._run()
        delegate_args = mock_del.call_args[0][0]
        assert "--goal" in delegate_args
        idx = delegate_args.index("--goal")
        assert delegate_args[idx + 1] == "Test goal"

    def test_passes_dry_run_to_delegate(self):
        _, mock_del = self._run(extra_args=["--dry-run"])
        delegate_args = mock_del.call_args[0][0]
        assert "--dry-run" in delegate_args

    def test_passes_json_to_delegate(self):
        _, mock_del = self._run(extra_args=["--json"])
        delegate_args = mock_del.call_args[0][0]
        assert "--json" in delegate_args

    def test_passes_task_type_to_delegate(self):
        _, mock_del = self._run(extra_args=["--task-type", "lint_fix"])
        delegate_args = mock_del.call_args[0][0]
        assert "--task-type" in delegate_args
        idx = delegate_args.index("--task-type")
        assert delegate_args[idx + 1] == "lint_fix"

    def test_uses_mission_goal_when_no_flag(self, tmp_path):
        console_dir = tmp_path / ".console"
        console_dir.mkdir()
        (console_dir / "task.md").write_text(
            "## Objective\n\nMission-driven goal.\n"
        )
        with patch("operator_console.delegate.run_delegate", return_value=0) as mock_del, \
             patch("operator_console.observer._find_repo_root", return_value=tmp_path), \
             patch("operator_console.observer._git_remote_url", return_value=None):
            from operator_console.auto_once import run_auto_once
            run_auto_once([])
        delegate_args = mock_del.call_args[0][0]
        idx = delegate_args.index("--goal")
        assert delegate_args[idx + 1] == "Mission-driven goal."

    def test_uses_default_goal_when_no_flag_no_mission(self):
        from operator_console.observer import _DEFAULT_GOAL
        with patch("operator_console.delegate.run_delegate", return_value=0) as mock_del, \
             patch("operator_console.observer._find_repo_root", return_value=Path("/tmp")), \
             patch("operator_console.observer._git_remote_url", return_value=None):
            from operator_console.auto_once import run_auto_once
            run_auto_once([])
        delegate_args = mock_del.call_args[0][0]
        idx = delegate_args.index("--goal")
        assert delegate_args[idx + 1] == _DEFAULT_GOAL
