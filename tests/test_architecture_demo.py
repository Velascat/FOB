from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_providers_command_reports_selector_only_readiness() -> None:
    text = (REPO_ROOT / "src" / "operator_console" / "providers.py").read_text(encoding="utf-8")
    assert "lane readiness" in text


def test_demo_flow_uses_selector_route_handoff() -> None:
    text = (REPO_ROOT / "src" / "operator_console" / "demo.py").read_text(encoding="utf-8")
    assert "/route" in text
