"""Zellij session creation and attachment."""
from __future__ import annotations
import os
import subprocess
import tempfile
from pathlib import Path

from fob.session import session_exists
from fob.guardrails import check_branch
from fob.bootstrap import get_claude_command

FOB_SESSION = "fob"


def _pane_block(profile: dict, fob_dir: Path, indent: str = "        ") -> str:
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
    i = indent

    return (
        f'{i}pane split_direction="vertical" {{\n'
        f'{i}    pane name="claude" size="60%" command="bash" {{\n'
        f'{i}        args "-c" "cd \'{safe_repo}\' && {claude_cmd}"\n'
        f'{i}    }}\n'
        f'{i}    pane size="40%" split_direction="horizontal" {{\n'
        f'{i}        pane name="git" size="34%" command="bash" {{\n'
        f'{i}            args "-c" "cd \'{safe_repo}\' && {git_cmd}; exec bash -l"\n'
        f'{i}        }}\n'
        f'{i}        pane name="logs" size="33%" command="bash" {{\n'
        f'{i}            args "-c" "cd \'{safe_repo}\' && {logs_cmd}; exec bash -l"\n'
        f'{i}        }}\n'
        f'{i}        pane name="shell" command="bash" {{\n'
        f'{i}            args "-c" "cd \'{safe_repo}\' && bash \'{welcome}\'"\n'
        f'{i}        }}\n'
        f'{i}    }}\n'
        f'{i}}}'
    )


def _save_layout(profile: dict, layout: str) -> None:
    fob_state = Path(profile["repo_root"]) / ".fob"
    if fob_state.exists():
        (fob_state / "layout-state.kdl").write_text(layout)


def generate_session_layout(profiles: list[dict], fob_dir: Path) -> Path:
    """Multi-tab layout for creating a new session."""
    tabs = []
    for i, profile in enumerate(profiles):
        focus = " focus=true" if i == 0 else ""
        name = profile["name"]
        panes = _pane_block(profile, fob_dir, indent="        ")
        tabs.append(f'    tab name="{name}"{focus} {{\n{panes}\n    }}')

    layout = "layout {\n" + "\n".join(tabs) + "\n}\n"
    _save_layout(profiles[0], layout)

    tmp = Path(tempfile.gettempdir()) / f"fob-session.kdl"
    tmp.write_text(layout)
    return tmp


def generate_tab_layout(profile: dict, fob_dir: Path) -> Path:
    """Single-tab layout for adding to an existing session."""
    name = profile["name"]
    panes = _pane_block(profile, fob_dir, indent="        ")
    layout = f'layout {{\n    tab name="{name}" {{\n{panes}\n    }}\n}}\n'
    _save_layout(profile, layout)
    tmp = Path(tempfile.gettempdir()) / f"fob-tab-{name}.kdl"
    tmp.write_text(layout)
    return tmp


def attach(session_name: str = FOB_SESSION) -> None:
    os.execvp("zellij", ["zellij", "attach", session_name])


def launch(profiles: list[dict], fob_dir: Path, reset_layout: bool = False) -> None:
    for profile in profiles:
        check_branch(Path(profile["repo_root"]))

    if session_exists(FOB_SESSION):
        for profile in profiles:
            layout_path = generate_tab_layout(profile, fob_dir)
            subprocess.run([
                "zellij", "--session", FOB_SESSION,
                "action", "new-tab",
                "--layout", str(layout_path),
                "--name", profile["name"],
            ])
        print(f"  → Attached to session: {FOB_SESSION}")
        attach(FOB_SESSION)
    else:
        saved = Path(profiles[0]["repo_root"]) / ".fob" / "layout-state.kdl"
        if not reset_layout and len(profiles) == 1 and saved.exists():
            layout_path = saved
            print(f"  → Restoring saved layout")
        else:
            layout_path = generate_session_layout(profiles, fob_dir)
            names = ", ".join(p["name"] for p in profiles)
            print(f"  → Creating session '{FOB_SESSION}' with tabs: {names}")
        print(f"  → Layout: {layout_path}")
        os.execvp(
            "zellij",
            ["zellij", "--session", FOB_SESSION, "--new-session-with-layout", str(layout_path)],
        )
