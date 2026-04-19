"""Zellij session creation and attachment."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path

from cockpit.session import session_exists
from cockpit.guardrails import check_branch
from cockpit.bootstrap import get_claude_command


def _build_pane_command(cwd: str, cmd: str) -> str:
    """Wrap a command so the pane keeps a shell alive on exit."""
    return f"cd '{cwd}' && ( {cmd} ); exec bash -l"


def generate_layout(profile: dict, template_path: Path) -> Path:
    repo = profile["repo_root"]
    panes = profile.get("panes", {})

    claude_cmd = get_claude_command(profile, Path(repo))
    git_cmd = panes.get("git", {}).get("command", "lazygit")
    logs_cmd = panes.get("logs", {}).get(
        "command",
        "tail -f .fob/runtime.log 2>/dev/null || echo 'No runtime.log yet'",
    )

    # Escape single quotes in repo path (defensive)
    safe_repo = repo.replace("'", "'\\''")

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
                args "-c" "cd '{safe_repo}' && exec bash -l"
            }}
        }}
    }}
}}
"""
    tmp = Path(tempfile.gettempdir()) / f"fob-brief-{profile['session_name']}.kdl"
    tmp.write_text(layout)
    return tmp


def attach(session_name: str) -> None:
    os.execvp("zellij", ["zellij", "attach", session_name])


def launch(profile: dict, utility_dir: Path) -> None:
    repo_root = Path(profile["repo_root"])
    session_name = profile["session_name"]
    template_path = utility_dir / "zellij" / "layouts" / "brief.kdl"

    check_branch(repo_root)

    if session_exists(session_name):
        print(f"  → Attaching to existing session: {session_name}")
        attach(session_name)
    else:
        layout_path = generate_layout(profile, template_path)
        print(f"  → Creating session: {session_name}")
        print(f"  → Layout: {layout_path}")
        os.execvp(
            "zellij",
            ["zellij", "--session", session_name, "--new-session-with-layout", str(layout_path)],
        )
