"""Generate Claude briefing from repo-local .fob/ state files."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

# Ordered sections in the briefing — label maps to filename
BRIEFING_SECTIONS = [
    ("active-mission.md",  "Active Mission"),
    ("standing-orders.md", "Standing Orders"),
    ("objectives.md",      "Objectives"),
    ("mission-log.md",     "Mission Log"),
]

# Files pulled from peer repos (standing-orders are repo-specific, skip them)
PEER_FILES = [
    ("active-mission.md", "Active Mission"),
    ("objectives.md",     "Objectives"),
]


def _get_branch(repo_root: Path) -> str:
    try:
        import subprocess
        r = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def build_resume_prompt(
    repo_root: Path,
    files: list[str] | None = None,
    peer_roots: list[tuple[str, Path]] | None = None,
    profile_name: str | None = None,
) -> str:
    fob_dir = repo_root / ".fob"
    sections: list[str] = []

    if files:
        files_to_read = [(Path(f).name, Path(f).name.replace(".md", "").replace("-", " ").title())
                         for f in files]
    else:
        files_to_read = list(BRIEFING_SECTIONS)

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
                        sections.append(f"## Peer: {peer_name} — {label}\n\n{content}")

    if not sections:
        return (
            "No .fob/ mission files found.\n"
            "Run: fob init  to initialize mission files for this repo."
        )

    repo_root = repo_root.resolve()
    branch = _get_branch(repo_root)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    profile_str = f" · Profile: {profile_name}" if profile_name else ""

    runtime = (
        f"## Runtime Context\n\n"
        f"- **Repo**: {repo_root.name}\n"
        f"- **Repo root**: `{repo_root}`\n"
        f"- **Branch**: `{branch}`\n"
        f"- **Generated**: {timestamp}{profile_str}\n"
    )
    sections.append(runtime)

    header = (
        f"# FOB Briefing — {repo_root.name}\n\n"
        f"_Generated {timestamp} · Branch: {branch}{profile_str}_\n\n"
        "This is your compiled startup context. Read it before acting.\n"
        "The source files in `.fob/` are the editable truth — this file is generated.\n\n"
        "---\n\n"
    )
    return header + "\n\n---\n\n".join(sections)


def write_bootstrap_file(
    repo_root: Path,
    files: list[str] | None = None,
    peer_roots: list[tuple[str, Path]] | None = None,
    profile_name: str | None = None,
) -> Path:
    prompt = build_resume_prompt(repo_root, files, peer_roots, profile_name)
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

    extra_lines = ""
    if extra_files:
        standard = {"standing-orders.md", "active-mission.md", "objectives.md", "mission-log.md"}
        extras = [Path(f).name for f in extra_files if Path(f).name not in standard]
        if extras:
            extra_lines = "\nAdditional context files also compiled into the briefing:\n" + \
                "\n".join(f"- `.fob/{name}`" for name in extras) + "\n"

    block = f"""{marker}
## FOB Briefing

At the start of each session, read the compiled briefing before acting:

- `.fob/.briefing` — compiled startup context (generated fresh each launch)

The briefing contains your mission, standing orders, objectives, recent log, and runtime context.
{extra_lines}
**Source files** (editable truth — update these, not the briefing):

| File | Role |
|------|------|
| `.fob/active-mission.md` | Current objective and definition of done |
| `.fob/standing-orders.md` | Repo policy, branch rules, operating constraints |
| `.fob/objectives.md` | Work inventory — in-progress, up-next, done |
| `.fob/mission-log.md` | Recent decisions, stop points, what changed and why |

After meaningful progress, update `.fob/objectives.md` and `.fob/mission-log.md`.
Do not edit `.fob/.briefing` directly — it is overwritten at each launch.
"""
    if claude_md.exists():
        existing = claude_md.read_text()
        if marker in existing:
            # Replace existing fob block
            import re
            new_text = re.sub(
                r"<!-- fob-context -->.*",
                block.strip(),
                existing,
                flags=re.DOTALL,
            )
            claude_md.write_text(new_text.rstrip() + "\n")
        else:
            claude_md.write_text(existing.rstrip() + "\n\n" + block + "\n")
    else:
        claude_md.write_text(block + "\n")


def ensure_zellij_serialization() -> None:
    pass  # serialization disabled — causes input freezes on VMs
