"""Zellij session creation and attachment."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path

from fob.session import session_exists
from fob.guardrails import check_branch
from fob.bootstrap import get_claude_command


def generate_layout(profile: dict, fob_dir: Path) -> Path:
    repo = profile["repo_root"]
    panes = profile.get("panes", {})

    claude_cmd = get_claude_command(profile, Path(repo))
    git_cmd = panes.get("git", {}).get("command", "lazygit")
    logs_cmd = panes.get("logs", {}).get(
        "command",
        "tail -f .fob/runtime.log 2>/dev/null || echo 'No runtime.log yet'",
    )

    safe_repo = repo.replace("'", "'\\''")
    welcome = str(fob_dir / "tools" / "welcome.sh").replace("'", "'\\''")

    layout = f"""layout {{
    pane split_direction="vertical" {{
        pane name="claude" size="60%" command="bash" {{
            args "-c" "cd '{safe_repo}' && {claude_cmd}"
        }}
        pane size="40%" split_direction="horizontal" {{
            pane name="git" size="34%" command="bash" {{
                args "-c" "cd '{safe_repo}' && {git_cmd}; exec bash -l"
            }}
            pane name="logs" size="33%" command="bash" {{
                args "-c" "cd '{safe_repo}' && {logs_cmd}; exec bash -l"
            }}
            pane name="shell" command="bash" {{
                args "-c" "cd '{safe_repo}' && bash '{welcome}'"
            }}
        }}
    }}
}}
"""
    # Persist layout to .fob/ so edits survive session death
    repo_root = Path(repo)
    fob_state = repo_root / ".fob"
    if fob_state.exists():
        (fob_state / "layout-state.kdl").write_text(layout)

    tmp = Path(tempfile.gettempdir()) / f"fob-brief-{profile['session_name']}.kdl"
    tmp.write_text(layout)
    return tmp


def attach(session_name: str) -> None:
    os.execvp("zellij", ["zellij", "attach", session_name])


def launch(profile: dict, fob_dir: Path, reset_layout: bool = False) -> None:
    repo_root = Path(profile["repo_root"])
    session_name = profile["session_name"]

    check_branch(repo_root)

    if session_exists(session_name):
        print(f"  → Attaching to existing session: {session_name}")
        attach(session_name)
    else:
        saved = repo_root / ".fob" / "layout-state.kdl"
        if not reset_layout and saved.exists():
            layout_path = saved
            print(f"  → Restoring saved layout")
        else:
            layout_path = generate_layout(profile, fob_dir)
            if reset_layout:
                print(f"  → Reset layout from profile defaults")
            else:
                print(f"  → Creating session: {session_name}")
        print(f"  → Layout: {layout_path}")
        os.execvp(
            "zellij",
            ["zellij", "--session", session_name, "--new-session-with-layout", str(layout_path)],
        )
