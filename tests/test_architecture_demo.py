from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_providers_command_no_longer_mentions_9router() -> None:
    text = (REPO_ROOT / "src" / "fob" / "providers.py").read_text(encoding="utf-8")
    assert "9router" not in text
    assert "lane readiness" in text


def test_demo_flow_no_longer_requires_provider_proxy() -> None:
    text = (REPO_ROOT / "src" / "fob" / "demo.py").read_text(encoding="utf-8")
    assert "9router" not in text
    assert "/route" in text
