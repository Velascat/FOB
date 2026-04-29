# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Velascat
"""Phase 4: OperatorConsole speaks CxRP at its edges.

Tests assert that operator-submitted work becomes a schema-valid CxRP
TaskProposal, and that inbound ExecutionResult payloads are rejected
when they don't conform.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest
from cxrp.contracts import TaskProposal as CxrpTaskProposal
from cxrp.validation.json_schema import validate_contract
from jsonschema import ValidationError

from operator_console.cxrp_capture import (
    build_task_proposal,
    summarize_execution_result,
    validate_inbound_execution_result,
)


def _serialize_envelope(contract: CxrpTaskProposal) -> dict:
    return contract.to_dict()


def test_build_task_proposal_returns_ecp_envelope():
    tp = build_task_proposal(
        title="Fix flaky test",
        objective="Stabilize tests/test_pipeline.py::test_repeated_runs",
        repo_key="velascat/operator-console",
    )
    assert isinstance(tp, CxrpTaskProposal)
    assert tp.contract_kind == "task_proposal"
    assert tp.schema_version == "0.2"


def test_build_task_proposal_validates_against_schema():
    tp = build_task_proposal(
        title="t",
        objective="o",
        repo_key="velascat/x",
        clone_url="https://github.com/Velascat/x.git",
        submitter="velascat",
        constraints=["preserve public API"],
    )
    validate_contract("task_proposal", _serialize_envelope(tp))


def test_build_task_proposal_target_uses_well_known_payload_schema():
    tp = build_task_proposal(title="t", objective="o", repo_key="velascat/x")
    assert tp.target is not None
    assert tp.target["$payload_schema"] == "coding_agent_target/v0.2"
    assert tp.target["repo_key"] == "velascat/x"
    assert tp.target["base_branch"] == "main"


def test_build_task_proposal_does_not_infer_task_type_or_risk():
    """OperatorConsole does not own task classification."""
    tp = build_task_proposal(title="t", objective="o", repo_key="velascat/x")
    assert tp.task_type is None
    assert tp.priority is None
    assert tp.risk_level is None
    assert tp.execution_mode is None


def test_validate_inbound_execution_result_accepts_valid():
    valid = {
        "schema_version": "0.2",
        "contract_kind": "execution_result",
        "result_id": "ers-1",
        "metadata": {},
        "request_id": "erq-1",
        "ok": True,
        "status": "succeeded",
        "artifacts": [{"kind": "log", "uri": "file:///tmp/run.log"}],
        "diagnostics": {"duration_seconds": 12},
    }
    validate_inbound_execution_result(valid)


def test_validate_inbound_execution_result_rejects_invalid_status():
    invalid = {
        "schema_version": "0.2",
        "contract_kind": "execution_result",
        "result_id": "ers-1",
        "metadata": {},
        "request_id": "erq-1",
        "ok": True,
        "status": "DEFINITELY_NOT_A_REAL_STATUS",
    }
    with pytest.raises(ValidationError):
        validate_inbound_execution_result(invalid)


def test_summarize_execution_result_renders_one_liner():
    payload = {
        "schema_version": "0.2",
        "contract_kind": "execution_result",
        "result_id": "ers-1",
        "metadata": {},
        "request_id": "erq-1",
        "ok": True,
        "status": "succeeded",
        "artifacts": [{"kind": "diff", "uri": "file:///x.diff"}],
        "diagnostics": {"duration_seconds": 42},
    }
    line = summarize_execution_result(payload)
    assert "status=succeeded" in line
    assert "run=erq-1" in line
    assert "artifacts=1" in line
    assert "took=42s" in line


def test_operator_console_does_not_emit_lane_decision():
    """Boundary invariant: OperatorConsole does not own lane selection."""
    src = Path(__file__).resolve().parents[1] / "src" / "operator_console"
    forbidden_terms = (
        "from cxrp.contracts import LaneDecision",
        "cxrp.contracts.lane_decision",
        "to_cxrp_lane_decision",
    )
    offenders = []
    for py_file in src.rglob("*.py"):
        text = py_file.read_text()
        for needle in forbidden_terms:
            if needle in text:
                offenders.append(f"{py_file}: {needle}")
    assert not offenders, "OperatorConsole imports lane-selection contract:\n" + "\n".join(offenders)


def test_operator_console_does_not_dispatch_adapters():
    """Boundary invariant: OperatorConsole does not invoke backend adapters."""
    src = Path(__file__).resolve().parents[1] / "src" / "operator_console"
    forbidden = (
        "operations_center.backends",
        "operations_center.adapters",
        "operations_center.execution.coordinator",
    )
    offenders = []
    for py_file in src.rglob("*.py"):
        text = py_file.read_text()
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{py_file}: {needle}")
    assert not offenders, "OperatorConsole imports adapter/execution code:\n" + "\n".join(offenders)
