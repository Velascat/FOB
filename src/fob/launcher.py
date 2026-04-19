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
    """Session layout: tab-bar + first profile panes + status-bar.
    Additional profiles are added as tabs after session creation."""
    profile = profiles[0]
    panes = _pane_block(profile, fob_dir, indent="    ")
    layout = (
        'layout {\n'
        '    pane size=1 borderless=true {\n'
        '        plugin location="tab-bar"\n'
        '    }\n'
        f'{panes}\n'
        '    pane size=2 borderless=true {\n'
        '        plugin location="status-bar"\n'
        '    }\n'
        '}\n'
    )
    _save_layout(profile, layout)
    tmp = Path(tempfile.gettempdir()) / "fob-session.kdl"
    tmp.write_text(layout)
    return tmp


def generate_tab_layout(profile: dict, fob_dir: Path) -> Path:
    """Tab layout for adding to an existing session (panes only)."""
    name = profile["name"]
    panes = _pane_block(profile, fob_dir, indent="    ")
    layout = (
        'layout {\n'
        f'{panes}\n'
        '}\n'
    )
    _save_layout(profile, layout)
    tmp = Path(tempfile.gettempdir()) / f"fob-tab-{name}.kdl"
    tmp.write_text(layout)
    return tmp


def _launch_with_extra_tabs(extra_profiles: list[dict], fob_dir: Path, layout_path: Path) -> None:
    """Start session then add extra tabs via a background wrapper script."""
    import shlex
    adds = []
    for profile in extra_profiles:
        tab_layout = generate_tab_layout(profile, fob_dir)
        adds.append(
            f"zellij --session {FOB_SESSION} action new-tab --name {shlex.quote(profile['name'])} --layout {shlex.quote(str(tab_layout))}"
        )
    # Write a wrapper that starts zellij then adds tabs once session is ready
    script = f"""#!/usr/bin/env bash
zellij --session {FOB_SESSION} --new-session-with-layout {shlex.quote(str(layout_path))} &
ZPID=$!
sleep 2
{"".join(f'{cmd}\n' for cmd in adds)}
wait $ZPID
"""
    tmp = Path(tempfile.gettempdir()) / "fob-launch.sh"
    tmp.write_text(script)
    tmp.chmod(0o755)
    os.execvp("bash", ["bash", str(tmp)])


def _list_tabs(session_name: str) -> set[str]:
    try:
        r = subprocess.run(
            ["zellij", "--session", session_name, "action", "query-tab-names"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            return {line.strip() for line in r.stdout.splitlines() if line.strip()}
    except Exception:
        pass
    return set()


def attach(session_name: str = FOB_SESSION) -> None:
    os.execvp("zellij", ["zellij", "attach", session_name])


def launch(profiles: list[dict], fob_dir: Path, reset_layout: bool = False) -> None:
    for profile in profiles:
        check_branch(Path(profile["repo_root"]))

    if session_exists(FOB_SESSION):
        existing_tabs = _list_tabs(FOB_SESSION)
        for profile in profiles:
            if profile["name"] in existing_tabs:
                print(f"  → Tab '{profile['name']}' already open — skipping")
                continue
            layout_path = generate_tab_layout(profile, fob_dir)
            subprocess.run([
                "zellij", "--session", FOB_SESSION,
                "action", "new-tab",
                "--name", profile["name"],
                "--layout", str(layout_path),
            ])
        print(f"  → Attached to session: {FOB_SESSION}")
        attach(FOB_SESSION)
    else:
        saved = Path(profiles[0]["repo_root"]) / ".fob" / "layout-state.kdl"
        if not reset_layout and saved.exists():
            layout_path = saved
            print(f"  → Restoring saved layout")
        else:
            layout_path = generate_session_layout(profiles, fob_dir)
            print(f"  → Creating session '{FOB_SESSION}'")
        print(f"  → Layout: {layout_path}")
        # For multi-profile, extra tabs are added after session starts via a wrapper
        if len(profiles) > 1 and not (not reset_layout and saved.exists()):
            _launch_with_extra_tabs(profiles[1:], fob_dir, layout_path)
        else:
            os.execvp(
                "zellij",
                ["zellij", "--session", FOB_SESSION, "--new-session-with-layout", str(layout_path)],
            )
