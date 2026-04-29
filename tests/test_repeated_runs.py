# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""Tests for Phase 12 repeated-run reliability.

Covers:
- list_runs() sorts by written_at, not directory name
- latest_run() returns the most recently written run
- artifact isolation (no overwrites)
- console runs command
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from operator_console.runs import _run_sort_key, latest_run, list_runs, run_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(root: Path, run_id: str, written_at: str, success: bool = True, partial: bool = False) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    meta = {
        "run_id": run_id,
        "written_at": written_at,
        "status": "success" if success else "failed",
        "success": success,
        "executed": True,
        "selected_lane": "claude_cli",
        "selected_backend": "kodo",
        "partial": partial,
    }
    (run_dir / "run_metadata.json").write_text(json.dumps(meta))
    (run_dir / "result.json").write_text(json.dumps({"status": meta["status"], "success": success}))
    (run_dir / "proposal.json").write_text(json.dumps({"goal_text": f"goal for {run_id}", "task_type": "documentation"}))
    return run_dir


# ---------------------------------------------------------------------------
# list_runs() sort correctness
# ---------------------------------------------------------------------------


class TestListRunsSort:
    def test_empty_dir_returns_empty(self, tmp_path):
        assert list_runs(tmp_path) == []

    def test_missing_root_returns_empty(self, tmp_path):
        assert list_runs(tmp_path / "nonexistent") == []

    def test_single_run(self, tmp_path):
        _make_run(tmp_path, "run-a", "2026-04-24T10:00:00")
        result = list_runs(tmp_path)
        assert len(result) == 1

    def test_sorted_by_timestamp_oldest_first(self, tmp_path):
        _make_run(tmp_path, "zzz-latest", "2026-04-24T12:00:00")
        _make_run(tmp_path, "aaa-oldest", "2026-04-24T10:00:00")
        _make_run(tmp_path, "mmm-middle", "2026-04-24T11:00:00")
        result = list_runs(tmp_path)
        names = [r.name for r in result]
        # Must be in timestamp order, not alphabetical
        assert names == ["aaa-oldest", "mmm-middle", "zzz-latest"]

    def test_uuid_named_dirs_sorted_by_timestamp(self, tmp_path):
        # UUIDs don't sort chronologically — metadata timestamp must be used
        _make_run(tmp_path, "ffffffff-0000-0000-0000-000000000000", "2026-04-24T09:00:00")
        _make_run(tmp_path, "00000000-ffff-ffff-ffff-ffffffffffff", "2026-04-24T11:00:00")
        result = list_runs(tmp_path)
        # ffffffff... sorts alphabetically last but timestamp-wise is oldest
        assert result[0].name.startswith("ffffffff")
        assert result[1].name.startswith("00000000")

    def test_dir_without_metadata_excluded(self, tmp_path):
        (tmp_path / "orphan").mkdir()
        _make_run(tmp_path, "valid-run", "2026-04-24T10:00:00")
        result = list_runs(tmp_path)
        assert len(result) == 1
        assert result[0].name == "valid-run"

    def test_run_sort_key_returns_empty_on_bad_metadata(self, tmp_path):
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "run_metadata.json").write_text("not-json{{{")
        assert _run_sort_key(bad_dir) == ""

    def test_run_sort_key_returns_empty_when_no_written_at(self, tmp_path):
        run_dir = tmp_path / "notime"
        run_dir.mkdir()
        (run_dir / "run_metadata.json").write_text(json.dumps({"run_id": "x"}))
        assert _run_sort_key(run_dir) == ""


# ---------------------------------------------------------------------------
# latest_run() correctness
# ---------------------------------------------------------------------------


class TestLatestRun:
    def test_returns_none_when_no_runs(self, tmp_path):
        assert latest_run(tmp_path) is None

    def test_returns_most_recent_by_timestamp(self, tmp_path):
        _make_run(tmp_path, "old", "2026-04-24T08:00:00")
        _make_run(tmp_path, "new", "2026-04-24T16:00:00")
        _make_run(tmp_path, "mid", "2026-04-24T12:00:00")
        result = latest_run(tmp_path)
        assert result is not None
        assert result.name == "new"

    def test_latest_not_confused_by_alphabetical_order(self, tmp_path):
        # 'zzz' sorts last alphabetically but has the earliest timestamp
        _make_run(tmp_path, "zzz-run", "2026-04-24T07:00:00")
        _make_run(tmp_path, "aaa-run", "2026-04-24T15:00:00")
        result = latest_run(tmp_path)
        assert result.name == "aaa-run"


# ---------------------------------------------------------------------------
# Artifact isolation — no overwrites
# ---------------------------------------------------------------------------


class TestArtifactIsolation:
    def test_two_runs_create_separate_dirs(self, tmp_path):
        _make_run(tmp_path, "run-1", "2026-04-24T10:00:00")
        _make_run(tmp_path, "run-2", "2026-04-24T11:00:00")
        assert len(list_runs(tmp_path)) == 2

    def test_failure_run_isolated_from_success_run(self, tmp_path):
        _make_run(tmp_path, "fail-run", "2026-04-24T10:00:00", success=False)
        _make_run(tmp_path, "success-run", "2026-04-24T11:00:00", success=True)
        runs = list_runs(tmp_path)
        assert len(runs) == 2
        fail_summary = run_summary(runs[0])
        success_summary = run_summary(runs[1])
        assert fail_summary["success"] is False
        assert success_summary["success"] is True

    def test_partial_run_does_not_corrupt_next_run(self, tmp_path):
        _make_run(tmp_path, "partial-run", "2026-04-24T10:00:00", partial=True)
        _make_run(tmp_path, "full-run", "2026-04-24T11:00:00", success=True)
        runs = list_runs(tmp_path)
        assert run_summary(runs[0])["partial"] is True
        assert run_summary(runs[1])["partial"] is False

    def test_each_run_has_unique_run_id_in_summary(self, tmp_path):
        _make_run(tmp_path, "run-a", "2026-04-24T10:00:00")
        _make_run(tmp_path, "run-b", "2026-04-24T11:00:00")
        run_ids = {run_summary(r)["run_id"] for r in list_runs(tmp_path)}
        assert len(run_ids) == 2


# ---------------------------------------------------------------------------
# console runs command
# ---------------------------------------------------------------------------


class TestRunsCommand:
    def test_returns_1_when_no_runs(self, tmp_path, capsys):
        from operator_console.runs_cmd import run_runs
        code = run_runs(["--root", str(tmp_path)])
        assert code == 1

    def test_returns_0_when_runs_exist(self, tmp_path, capsys):
        _make_run(tmp_path, "run-a", "2026-04-24T10:00:00")
        from operator_console.runs_cmd import run_runs
        code = run_runs(["--root", str(tmp_path)])
        assert code == 0

    def test_json_output_has_runs_key(self, tmp_path, capsys):
        _make_run(tmp_path, "run-a", "2026-04-24T10:00:00")
        from operator_console.runs_cmd import run_runs
        run_runs(["--root", str(tmp_path), "--json"])
        out = json.loads(capsys.readouterr().out)
        assert "runs" in out
        assert "total" in out

    def test_json_runs_newest_first(self, tmp_path, capsys):
        _make_run(tmp_path, "run-old", "2026-04-24T08:00:00")
        _make_run(tmp_path, "run-new", "2026-04-24T16:00:00")
        from operator_console.runs_cmd import run_runs
        run_runs(["--root", str(tmp_path), "--json"])
        out = json.loads(capsys.readouterr().out)
        assert out["runs"][0]["run_id"] == "run-new"
        assert out["runs"][1]["run_id"] == "run-old"

    def test_limit_applied(self, tmp_path, capsys):
        for i in range(5):
            _make_run(tmp_path, f"run-{i:02d}", f"2026-04-24T{10+i:02d}:00:00")
        from operator_console.runs_cmd import run_runs
        run_runs(["--root", str(tmp_path), "--json", "--limit", "2"])
        out = json.loads(capsys.readouterr().out)
        assert len(out["runs"]) == 2
        assert out["total"] == 5

    def test_json_empty_has_runs_key(self, tmp_path, capsys):
        from operator_console.runs_cmd import run_runs
        run_runs(["--root", str(tmp_path), "--json"])
        out = json.loads(capsys.readouterr().out)
        assert out["runs"] == []

    def test_text_output_contains_run_id_prefix(self, tmp_path, capsys):
        _make_run(tmp_path, "abcd1234-rest", "2026-04-24T10:00:00")
        from operator_console.runs_cmd import run_runs
        run_runs(["--root", str(tmp_path)])
        out = capsys.readouterr().out
        assert "abcd1234" in out
