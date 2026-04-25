"""Tests for run_delegate() exit code semantics.

Verifies that run_delegate returns the correct exit code for each outcome
type without running any real subprocess or OperationsCenter.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from operator_console.delegate import (
    EXIT_SUCCESS,
    EXIT_GENERAL,
    EXIT_ROUTING_FAILURE,
    EXIT_POLICY_BLOCKED,
    EXIT_BACKEND_FAILURE,
    EXIT_TIMEOUT,
    EXIT_MALFORMED,
    run_delegate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan_bundle(lane: str = "claude_cli", backend: str = "kodo") -> dict:
    """Minimal planning bundle that satisfies run_delegate's field reads."""
    return {
        "proposal": {"proposal_id": "abc12345"},
        "decision": {"selected_lane": lane, "selected_backend": backend},
    }


def _make_exec_outcome(
    success: bool = True,
    executed: bool = True,
    failure_category: str | None = None,
    status: str = "SUCCESS",
) -> dict:
    """Minimal execution outcome dict written by the execute entrypoint."""
    return {
        "executed": executed,
        "result": {
            "run_id": "test-run-001",
            "status": status,
            "success": success,
            "failure_category": failure_category,
        },
        "policy_decision": {},
    }


def _fake_run_factory(plan_bundle: dict, exec_outcome: dict, plan_returncode: int = 0):
    """Return a fake subprocess.run that serves planning then execution calls."""
    result_file_content = json.dumps(exec_outcome)
    plan_proc = MagicMock(returncode=plan_returncode, stdout=json.dumps(plan_bundle), stderr="")
    exec_proc = MagicMock(returncode=0, stdout="", stderr="")
    call_count = 0

    def fake_run(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return plan_proc
        # Execution call: write the result file
        output_path = None
        for i, arg in enumerate(cmd):
            if arg == "--output" and i + 1 < len(cmd):
                output_path = Path(cmd[i + 1])
        if output_path:
            output_path.write_text(result_file_content, encoding="utf-8")
        return exec_proc

    return fake_run


def _common_patches(tmp_path: Path):
    """Return stack of patches shared by all execution-path tests."""
    return [
        patch("operator_console.delegate.subprocess.run"),
        patch("operator_console.delegate._repo_root", return_value=tmp_path),
        patch("operator_console.delegate._cp_python", return_value="python3"),
        patch("operator_console.runs.runs_root", return_value=lambda: tmp_path),
    ]


# ---------------------------------------------------------------------------
# Successful run → exit 0
# ---------------------------------------------------------------------------

class TestDelegateSuccess:
    def test_success_returns_0(self, tmp_path):
        """A fully successful run returns EXIT_SUCCESS (0)."""
        bundle = _make_plan_bundle()
        outcome = _make_exec_outcome(success=True)
        fake_run = _fake_run_factory(bundle, outcome)

        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        with patch("operator_console.delegate.subprocess.run", side_effect=fake_run), \
             patch("operator_console.delegate._repo_root", return_value=tmp_path), \
             patch("operator_console.delegate._cp_python", return_value="python3"), \
             patch("operator_console.runs.runs_root", return_value=tmp_path):
            code = run_delegate(["--goal", "smoke test"])

        assert code == EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Backend failure → exit 4
# ---------------------------------------------------------------------------

class TestDelegateBackendFailure:
    def test_backend_error_returns_4(self, tmp_path):
        """When the backend reports backend_error, exit code is EXIT_BACKEND_FAILURE (4)."""
        bundle = _make_plan_bundle()
        outcome = _make_exec_outcome(
            success=False, executed=True,
            failure_category="backend_error", status="BACKEND_ERROR",
        )
        fake_run = _fake_run_factory(bundle, outcome)

        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        with patch("operator_console.delegate.subprocess.run", side_effect=fake_run), \
             patch("operator_console.delegate._repo_root", return_value=tmp_path), \
             patch("operator_console.delegate._cp_python", return_value="python3"), \
             patch("operator_console.runs.runs_root", return_value=tmp_path):
            code = run_delegate(["--goal", "smoke test"])

        assert code == EXIT_BACKEND_FAILURE

    def test_timeout_returns_5(self, tmp_path):
        """When failure_category is timeout, exit code is EXIT_TIMEOUT (5)."""
        bundle = _make_plan_bundle()
        outcome = _make_exec_outcome(
            success=False, executed=True,
            failure_category="timeout", status="TIMEOUT",
        )
        fake_run = _fake_run_factory(bundle, outcome)

        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        with patch("operator_console.delegate.subprocess.run", side_effect=fake_run), \
             patch("operator_console.delegate._repo_root", return_value=tmp_path), \
             patch("operator_console.delegate._cp_python", return_value="python3"), \
             patch("operator_console.runs.runs_root", return_value=tmp_path):
            code = run_delegate(["--goal", "smoke test"])

        assert code == EXIT_TIMEOUT


# ---------------------------------------------------------------------------
# Routing failure → exit 2
# ---------------------------------------------------------------------------

class TestDelegateRoutingFailure:
    def test_planning_failure_returns_2(self, tmp_path):
        """When the planning subprocess exits non-zero with a routing error, exit code is EXIT_ROUTING_FAILURE (2)."""
        error_bundle = {
            "error": "planning_failure",
            "error_type": "routing_failure",
            "message": "SwitchBoard unreachable",
            "partial_run_id": None,
        }
        plan_proc = MagicMock(
            returncode=1,
            stdout=json.dumps(error_bundle),
            stderr="",
        )

        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        with patch("operator_console.delegate.subprocess.run", return_value=plan_proc), \
             patch("operator_console.delegate._repo_root", return_value=tmp_path), \
             patch("operator_console.delegate._cp_python", return_value="python3"):
            code = run_delegate(["--goal", "smoke test"])

        assert code == EXIT_ROUTING_FAILURE


# ---------------------------------------------------------------------------
# Policy blocked → exit 3
# ---------------------------------------------------------------------------

class TestDelegatePolicyBlocked:
    def test_policy_blocked_returns_3(self, tmp_path):
        """When execution is skipped (executed=False), exit code is EXIT_POLICY_BLOCKED (3)."""
        bundle = _make_plan_bundle()
        outcome = _make_exec_outcome(
            success=False, executed=False,
            failure_category=None, status="SKIPPED",
        )
        fake_run = _fake_run_factory(bundle, outcome)

        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        with patch("operator_console.delegate.subprocess.run", side_effect=fake_run), \
             patch("operator_console.delegate._repo_root", return_value=tmp_path), \
             patch("operator_console.delegate._cp_python", return_value="python3"), \
             patch("operator_console.runs.runs_root", return_value=tmp_path):
            code = run_delegate(["--goal", "smoke test"])

        assert code == EXIT_POLICY_BLOCKED


# ---------------------------------------------------------------------------
# Malformed output → exit 6
# ---------------------------------------------------------------------------

class TestDelegateMalformedOutput:
    def test_non_json_planning_output_returns_6(self, tmp_path):
        """When planning stdout is not JSON (success=0 case), exit code is EXIT_MALFORMED (6)."""
        plan_proc = MagicMock(
            returncode=0,
            stdout="not valid json at all",
            stderr="",
        )

        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        with patch("operator_console.delegate.subprocess.run", return_value=plan_proc), \
             patch("operator_console.delegate._repo_root", return_value=tmp_path), \
             patch("operator_console.delegate._cp_python", return_value="python3"):
            code = run_delegate(["--goal", "smoke test"])

        assert code == EXIT_MALFORMED


# ---------------------------------------------------------------------------
# Dry-run → exit 0 regardless
# ---------------------------------------------------------------------------

class TestDelegateDryRun:
    def test_dry_run_returns_0(self, tmp_path):
        """--dry-run returns 0 when planning succeeds."""
        bundle = _make_plan_bundle()
        plan_proc = MagicMock(returncode=0, stdout=json.dumps(bundle), stderr="")

        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        with patch("operator_console.delegate.subprocess.run", return_value=plan_proc), \
             patch("operator_console.delegate._repo_root", return_value=tmp_path), \
             patch("operator_console.delegate._cp_python", return_value="python3"):
            code = run_delegate(["--goal", "smoke test", "--dry-run"])

        assert code == EXIT_SUCCESS
