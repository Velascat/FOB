"""Generate Claude resume context from repo-local .fob/ state files."""
from __future__ import annotations
from pathlib import Path

CONTEXT_FILES = [
    ("standing-orders.md", "STANDING ORDERS"),
    ("active-mission.md",  "ACTIVE MISSION"),
    ("objectives.md",      "OBJECTIVES"),
    ("mission-log.md",     "MISSION LOG"),
]


def build_resume_prompt(repo_root: Path) -> str:
    fob_dir = repo_root / ".fob"
    sections: list[str] = []

    for filename, label in CONTEXT_FILES:
        path = fob_dir / filename
        if path.exists():
            content = path.read_text().strip()
            if content:
                sections.append(f"## {label}\n\n{content}")

    if not sections:
        return (
            "No .fob/ mission files found.\n"
            "Run: fob init  to initialize mission files for this repo."
        )

    header = (
        "# FOB Mission Brief\n\n"
        "Read and apply this context before taking any action:\n\n"
        "---\n\n"
    )
    return header + "\n\n---\n\n".join(sections)


def write_bootstrap_file(repo_root: Path) -> Path:
    prompt = build_resume_prompt(repo_root)
    out = repo_root / ".fob" / ".briefing"
    out.write_text(prompt)
    return out


def get_claude_command(profile: dict, repo_root: Path) -> str:
    cfg = profile.get("claude", {})
    use_continue = cfg.get("continue", True)
    if (repo_root / ".fob").exists():
        write_bootstrap_file(repo_root)
    return "claude --continue" if use_continue else "claude"


def ensure_claude_md(repo_root: Path, templates_dir: Path) -> None:
    """Add a .fob/ reference block to CLAUDE.md if not already present."""
    claude_md = repo_root / "CLAUDE.md"
    marker = "<!-- fob-context -->"
    block = f"""{marker}
## FOB Mission Files

At the start of each session, read these files before acting:

- `.fob/standing-orders.md` — operating rules for this repo
- `.fob/active-mission.md`  — what to work on right now
- `.fob/objectives.md`      — active task list with status
- `.fob/mission-log.md`     — recent decisions and scratch notes

After meaningful progress, update `.fob/objectives.md` and `.fob/mission-log.md`.
"""
    if claude_md.exists():
        existing = claude_md.read_text()
        if marker not in existing:
            claude_md.write_text(existing.rstrip() + "\n\n" + block + "\n")
    else:
        claude_md.write_text(block + "\n")
