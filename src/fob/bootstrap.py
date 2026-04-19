"""Generate Claude resume context from repo-local .fob/ state files."""
from __future__ import annotations
from pathlib import Path

DEFAULT_FILES = [
    ("standing-orders.md", "STANDING ORDERS"),
    ("active-mission.md",  "ACTIVE MISSION"),
    ("objectives.md",      "OBJECTIVES"),
    ("mission-log.md",     "MISSION LOG"),
]

# Files pulled from peer repos (standing-orders are repo-specific, skip them)
PEER_FILES = [
    ("active-mission.md", "ACTIVE MISSION"),
    ("objectives.md",     "OBJECTIVES"),
]


def build_resume_prompt(
    repo_root: Path,
    files: list[str] | None = None,
    peer_roots: list[tuple[str, Path]] | None = None,
) -> str:
    fob_dir = repo_root / ".fob"
    sections: list[str] = []

    if files:
        files_to_read = [(Path(f).name, Path(f).name.replace(".md", "").replace("-", " ").upper())
                         for f in files]
    else:
        files_to_read = list(DEFAULT_FILES)

    for filename, label in files_to_read:
        path = fob_dir / filename
        if path.exists():
            content = path.read_text().strip()
            if content:
                sections.append(f"## {label}\n\n{content}")

    if peer_roots:
        for peer_name, peer_root in peer_roots:
            peer_fob = peer_root / ".fob"
            for filename, label in PEER_FILES:
                path = peer_fob / filename
                if path.exists():
                    content = path.read_text().strip()
                    if content:
                        sections.append(f"## PEER: {peer_name} — {label}\n\n{content}")

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


def write_bootstrap_file(
    repo_root: Path,
    files: list[str] | None = None,
    peer_roots: list[tuple[str, Path]] | None = None,
) -> Path:
    prompt = build_resume_prompt(repo_root, files, peer_roots)
    out = repo_root / ".fob" / ".briefing"
    out.write_text(prompt)
    return out


def get_claude_command(profile: dict, repo_root: Path) -> str:
    cfg = profile.get("claude", {})
    use_continue = cfg.get("continue", True)
    return "claude --continue" if use_continue else "claude"


def ensure_claude_md(
    repo_root: Path,
    templates_dir: Path,
    extra_files: list[str] | None = None,
) -> None:
    claude_md = repo_root / "CLAUDE.md"
    marker = "<!-- fob-context -->"

    file_lines = [
        "- `.fob/standing-orders.md` — operating rules for this repo",
        "- `.fob/active-mission.md`  — what to work on right now",
        "- `.fob/objectives.md`      — active task list with status",
        "- `.fob/mission-log.md`     — recent decisions and scratch notes",
    ]
    if extra_files:
        standard = {"standing-orders.md", "active-mission.md", "objectives.md", "mission-log.md"}
        for f in extra_files:
            name = Path(f).name
            if name not in standard:
                label = name.replace(".md", "").replace("-", " ").lower()
                file_lines.append(f"- `.fob/{name}` — {label}")

    files_block = "\n".join(file_lines)
    block = f"""{marker}
## FOB Mission Files

At the start of each session, read these files before acting:

{files_block}

After meaningful progress, update `.fob/objectives.md` and `.fob/mission-log.md`.
"""
    if claude_md.exists():
        existing = claude_md.read_text()
        if marker not in existing:
            claude_md.write_text(existing.rstrip() + "\n\n" + block + "\n")
    else:
        claude_md.write_text(block + "\n")


def ensure_zellij_serialization() -> None:
    import re
    config_path = Path.home() / ".config" / "zellij" / "config.kdl"
    if not config_path.exists():
        return
    text = config_path.read_text()

    patches = [
        (r"//\s*session_serialization\s+\w+", "session_serialization true"),
        (r"session_serialization\s+false",     "session_serialization true"),
        (r"//\s*serialize_pane_viewport\s+\w+", "serialize_pane_viewport true"),
        (r"serialize_pane_viewport\s+false",    "serialize_pane_viewport true"),
        (r"//\s*serialization_interval\s+\w+",  "serialization_interval 60"),
        (r"serialization_interval\s+(?!60\b)\d+", "serialization_interval 60"),
    ]

    changed = False
    for pattern, replacement in patches:
        new_text, n = re.subn(pattern, replacement, text)
        if n:
            text = new_text
            changed = True

    if changed:
        config_path.write_text(text)
