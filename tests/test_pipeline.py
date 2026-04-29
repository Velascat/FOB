# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""Tests for pipeline commands: runs.py, last.py, delegate.py, system_status.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers — build fake artifact directories
# ---------------------------------------------------------------------------


def _write_run(root: Path, run_id: str, **overrides) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)

    metadata = {
        "run_id": run_id,
        "proposal_id": f"prop-{run_id}",
        "decision_id": f"dec-{run_id}",
        "selected_lane": "claude_cli",
        "selected_backend": "kodo",
        "status": "success",
        "success": True,
        "executed": True,
        "written_at": "2026-04-24T10:00:00+00:00",
    }
    metadata.update(overrides.get("metadata", {}))
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata))

    proposal = {
        "proposal_id": metadata["proposal_id"],
        "goal_text": overrides.get("goal_text", "Fix lint errors"),
        "task_type": "lint_fix",
        "target": {"repo_key": "svc", "clone_url": "https://example.invalid/svc.git", "base_branch": "main", "allowed_paths": []},
        "constraints": {},
    }
    (run_dir / "proposal.json").write_text(json.dumps(proposal))

    result = {
        "run_id": run_id,
        "proposal_id": metadata["proposal_id"],
        "decision_id": metadata["decision_id"],
        "status": metadata["status"],
        "success": metadata["success"],
    }
    (run_dir / "result.json").write_text(json.dumps(result))

    decision = {
        "decision_id": metadata["decision_id"],
        "proposal_id": metadata["proposal_id"],
        "selected_lane": metadata["selected_lane"],
        "selected_backend": metadata["selected_backend"],
        "confidence": 0.9,
        "policy_rule_matched": "test",
    }
    (run_dir / "decision.json").write_text(json.dumps(decision))

    return run_dir


# ---------------------------------------------------------------------------
# runs.py
# ---------------------------------------------------------------------------


class TestListRuns:
    def test_empty_root_returns_empty_list(self, tmp_path):
        from operator_console.runs import list_runs
        assert list_runs(tmp_path) == []

    def test_nonexistent_root_returns_empty_list(self, tmp_path):
        from operator_console.runs import list_runs
        assert list_runs(tmp_path / "nonexistent") == []

    def test_lists_runs_with_metadata(self, tmp_path):
        from operator_console.runs import list_runs
        _write_run(tmp_path, "run-a")
        _write_run(tmp_path, "run-b")
        runs = list_runs(tmp_path)
        assert len(runs) == 2

    def test_directories_without_metadata_excluded(self, tmp_path):
        from operator_console.runs import list_runs
        _write_run(tmp_path, "run-a")
        (tmp_path / "stale-dir").mkdir()  # no run_metadata.json
        assert len(list_runs(tmp_path)) == 1

    def test_sorted_oldest_first(self, tmp_path):
        from operator_console.runs import list_runs
        _write_run(tmp_path, "aaa")
        _write_run(tmp_path, "zzz")
        runs = list_runs(tmp_path)
        assert runs[0].name == "aaa"
        assert runs[-1].name == "zzz"


class TestLatestRun:
    def test_returns_none_when_empty(self, tmp_path):
        from operator_console.runs import latest_run
        assert latest_run(tmp_path) is None

    def test_returns_last_sorted_dir(self, tmp_path):
        from operator_console.runs import latest_run
        _write_run(tmp_path, "aaa")
        _write_run(tmp_path, "zzz")
        assert latest_run(tmp_path).name == "zzz"

    def test_single_run_returned(self, tmp_path):
        from operator_console.runs import latest_run
        _write_run(tmp_path, "only-run")
        assert latest_run(tmp_path).name == "only-run"


class TestReadJson:
    def test_returns_empty_dict_for_missing_file(self, tmp_path):
        from operator_console.runs import read_json
        assert read_json(tmp_path / "nonexistent.json") == {}

    def test_returns_empty_dict_for_invalid_json(self, tmp_path):
        from operator_console.runs import read_json
        p = tmp_path / "bad.json"
        p.write_text("not json")
        assert read_json(p) == {}

    def test_returns_parsed_dict(self, tmp_path):
        from operator_console.runs import read_json
        p = tmp_path / "data.json"
        p.write_text('{"key": "value"}')
        assert read_json(p) == {"key": "value"}


class TestRunSummary:
    def test_includes_run_id(self, tmp_path):
        from operator_console.runs import run_summary
        run_dir = _write_run(tmp_path, "run-abc")
        s = run_summary(run_dir)
        assert s["run_id"] == "run-abc"

    def test_includes_goal_text(self, tmp_path):
        from operator_console.runs import run_summary
        run_dir = _write_run(tmp_path, "run-abc", goal_text="Refactor auth module")
        s = run_summary(run_dir)
        assert s["goal_text"] == "Refactor auth module"

    def test_includes_lane_and_backend(self, tmp_path):
        from operator_console.runs import run_summary
        run_dir = _write_run(tmp_path, "run-abc")
        s = run_summary(run_dir)
        assert s["selected_lane"] == "claude_cli"
        assert s["selected_backend"] == "kodo"

    def test_success_field(self, tmp_path):
        from operator_console.runs import run_summary
        run_dir = _write_run(tmp_path, "run-abc")
        s = run_summary(run_dir)
        assert s["success"] is True

    def test_artifacts_dir_is_string(self, tmp_path):
        from operator_console.runs import run_summary
        run_dir = _write_run(tmp_path, "run-abc")
        s = run_summary(run_dir)
        assert isinstance(s["artifacts_dir"], str)

    def test_fallback_run_id_from_dir_name(self, tmp_path):
        from operator_console.runs import run_summary
        # metadata with no run_id key
        run_dir = tmp_path / "orphan-run"
        run_dir.mkdir()
        (run_dir / "run_metadata.json").write_text("{}")
        s = run_summary(run_dir)
        assert s["run_id"] == "orphan-run"


# ---------------------------------------------------------------------------
# last.py
# ---------------------------------------------------------------------------


class TestRunLast:
    def test_returns_1_when_no_runs(self, tmp_path, capsys):
        from operator_console.last import run_last
        code = run_last(["--root", str(tmp_path)])
        assert code == 1
        out = capsys.readouterr().out
        assert "No runs found" in out

    def test_returns_0_for_successful_run(self, tmp_path, capsys):
        from operator_console.last import run_last
        _write_run(tmp_path, "run-abc")
        code = run_last(["--root", str(tmp_path)])
        assert code == 0

    def test_prints_run_id(self, tmp_path, capsys):
        from operator_console.last import run_last
        _write_run(tmp_path, "run-abc")
        run_last(["--root", str(tmp_path)])
        out = capsys.readouterr().out
        assert "run-abc" in out

    def test_prints_status(self, tmp_path, capsys):
        from operator_console.last import run_last
        _write_run(tmp_path, "run-abc")
        run_last(["--root", str(tmp_path)])
        out = capsys.readouterr().out
        assert "success" in out

    def test_json_output(self, tmp_path, capsys):
        from operator_console.last import run_last
        _write_run(tmp_path, "run-abc")
        run_last(["--root", str(tmp_path), "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["run_id"] == "run-abc"

    def test_json_no_runs(self, tmp_path, capsys):
        from operator_console.last import run_last
        code = run_last(["--root", str(tmp_path), "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "error" in data
        assert code == 1

    def test_failure_run_shows_category(self, tmp_path, capsys):
        from operator_console.last import run_last
        _write_run(
            tmp_path, "run-fail",
            metadata={"status": "failed", "success": False, "failure_category": "backend_error"},
        )
        run_last(["--root", str(tmp_path)])
        out = capsys.readouterr().out
        assert "backend_error" in out

    def test_all_flag_shows_recent_list(self, tmp_path, capsys):
        from operator_console.last import run_last
        _write_run(tmp_path, "run-a")
        _write_run(tmp_path, "run-b")
        run_last(["--root", str(tmp_path), "--all"])
        out = capsys.readouterr().out
        assert "run-a" in out
        assert "run-b" in out


# ---------------------------------------------------------------------------
# delegate.py — argument parsing (no subprocess needed)
# ---------------------------------------------------------------------------


class TestDelegateArgParsing:
    def _parse(self, args):
        from operator_console.delegate import _parse_args
        return _parse_args(args)

    def test_goal_parsed(self):
        opts = self._parse(["--goal", "Fix lint"])
        assert opts["goal"] == "Fix lint"

    def test_task_type_default(self):
        assert self._parse([])["task_type"] is None

    def test_task_type_override(self):
        opts = self._parse(["--task-type", "bug"])
        assert opts["task_type"] == "bug"

    def test_json_flag(self):
        assert self._parse(["--json"])["json"] is True

    def test_repo_override(self):
        opts = self._parse(["--repo", "myrepo"])
        assert opts["repo"] == "myrepo"

    def test_priority_default(self):
        assert self._parse([])["priority"] == "normal"

    def test_priority_override(self):
        opts = self._parse(["--priority", "high"])
        assert opts["priority"] == "high"


# ---------------------------------------------------------------------------
# system_status.py — module structure
# ---------------------------------------------------------------------------


class TestSystemStatusModule:
    def test_run_status_function_exists(self):
        from operator_console.system_status import run_status
        assert callable(run_status)

    def test_run_status_returns_int(self, capsys):
        from operator_console.system_status import run_status
        code = run_status(["--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(code, int)
        assert "switchboard" in data
        assert "operations_center" in data
        assert "binaries" in data

    def test_json_output_has_last_run_key(self, capsys):
        from operator_console.system_status import run_status
        run_status(["--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "last_run" in data


# ---------------------------------------------------------------------------
# Static file presence checks
# ---------------------------------------------------------------------------


def test_runs_module_exists():
    assert (REPO_ROOT / "src" / "operator_console" / "runs.py").exists()


def test_last_module_exists():
    assert (REPO_ROOT / "src" / "operator_console" / "last.py").exists()


def test_delegate_module_exists():
    assert (REPO_ROOT / "src" / "operator_console" / "delegate.py").exists()


def test_system_status_module_exists():
    assert (REPO_ROOT / "src" / "operator_console" / "system_status.py").exists()


def test_cli_dispatches_delegate():
    text = (REPO_ROOT / "src" / "operator_console" / "cli.py").read_text()
    assert "delegate" in text


def test_cli_dispatches_last():
    text = (REPO_ROOT / "src" / "operator_console" / "cli.py").read_text()
    assert "case \"last\"" in text
