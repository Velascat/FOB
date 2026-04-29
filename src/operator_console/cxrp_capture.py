"""CxRP boundary surface for OperatorConsole.

OperatorConsole speaks CxRP at its edges: it captures operator-submitted
work as an CxRP-shaped ``TaskProposal`` and consumes CxRP-shaped
``ExecutionResult`` payloads for display. It does not own lane selection
(SwitchBoard) or adapter dispatch (OperationsCenter).

This module is intentionally thin — three pure functions that read or
build CxRP envelopes. No network calls, no subprocess execution, no
delegation logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from cxrp.contracts import ExecutionResult as CxrpExecutionResult, TaskProposal as CxrpTaskProposal
from cxrp.validation.json_schema import validate_contract


def build_task_proposal(
    *,
    title: str,
    objective: str,
    repo_key: str,
    base_branch: str = "main",
    clone_url: Optional[str] = None,
    submitter: Optional[str] = None,
    constraints: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> CxrpTaskProposal:
    """Build an CxRP TaskProposal from operator input.

    OperatorConsole does not infer task_type, priority, or risk_level —
    those are downstream classifications. The proposal it emits names
    *what* the operator wants and *where*; routing/planning fills in
    the rest.
    """
    target = {
        "$payload_schema": "coding_agent_target/v0.2",
        "repo_key": repo_key,
        "base_branch": base_branch,
    }
    if clone_url is not None:
        target["clone_url"] = clone_url

    md: dict[str, Any] = {"source": "operator_console"}
    if submitter is not None:
        md["submitter"] = submitter
    if metadata:
        md.update(metadata)

    return CxrpTaskProposal(
        proposal_id=_new_proposal_id(),
        created_at=datetime.now(tz=timezone.utc),
        metadata=md,
        title=title,
        objective=objective,
        target=target,
        constraints=list(constraints) if constraints else [],
    )


def validate_inbound_execution_result(payload: dict[str, Any]) -> None:
    """Validate an inbound ExecutionResult payload against CxRP's schema.

    Raises jsonschema.ValidationError on shape mismatch.
    """
    validate_contract("execution_result", payload)


def summarize_execution_result(payload: dict[str, Any]) -> str:
    """Render a one-line operator-facing summary of an CxRP ExecutionResult."""
    validate_inbound_execution_result(payload)
    status = payload.get("status", "?")
    request_id = payload.get("request_id", "?")
    artifact_count = len(payload.get("artifacts", []))
    diagnostics = payload.get("diagnostics") or {}
    duration = diagnostics.get("duration_seconds")
    parts = [f"run={request_id}", f"status={status}", f"artifacts={artifact_count}"]
    if duration is not None:
        parts.append(f"took={duration}s")
    return " | ".join(parts)


def _new_proposal_id() -> str:
    import uuid
    return f"prop-{uuid.uuid4().hex[:12]}"
