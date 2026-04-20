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
        f'{i}    pane size="35%" stacked=true {{\n'
        f'{i}        pane name="git" command="bash" {{\n'
        f'{i}            args "-c" "cd \'{safe_repo}\' && {git_cmd}; exec bash -l"\n'
        f'{i}        }}\n'
        f'{i}        pane name="logs" command="bash" {{\n'
        f'{i}            args "-c" "cd \'{safe_repo}\' && {logs_cmd}; exec bash -l"\n'
        f'{i}        }}\n'
        f'{i}        pane name="shell" command="bash" {{\n'
        f'{i}            args "-c" "cd \'{safe_repo}\' && bash \'{welcome}\'"\n'
        f'{i}        }}\n'
        f'{i}    }}\n'
        f'{i}    pane name="claude" command="bash" {{\n'
        f'{i}        args "-c" "cd \'{safe_repo}\' && {claude_cmd}"\n'
        f'{i}    }}\n'
        f'{i}}}'
    )


def _save_layout(profile: dict, layout: str) -> None:
    fob_state = Path(profile["repo_root"]) / ".fob"
    if fob_state.exists():
        (fob_state / "layout-state.kdl").write_text(layout)


def _chrome_template() -> str:
    """default_tab_template block — injects chrome into every tab including new ones."""
    return (
        '    default_tab_template {\n'
        '        pane size=1 borderless=true {\n'
        '            plugin location="tab-bar"\n'
        '        }\n'
        '        children\n'
        '        pane size=2 borderless=true {\n'
        '            plugin location="status-bar"\n'
        '        }\n'
        '    }\n'
    )


def _floating_cheat_block(fob_dir: Path, indent: str = "    ") -> str:
    """Floating cheat pane block for inclusion in any layout."""
    cheat = str(fob_dir / "tools" / "cheat.sh").replace("'", "'\\''")
    i = indent
    return (
        f'{i}floating_panes {{\n'
        f'{i}    pane name="cheat" command="bash" {{\n'
        f'{i}        args "-c" "bash \'{cheat}\'"\n'
        f'{i}    }}\n'
        f'{i}}}\n'
    )


def generate_session_layout(profiles: list[dict], fob_dir: Path) -> Path:
    """Session layout with default_tab_template so all tabs inherit chrome."""
    profile = profiles[0]
    name = profile["name"]
    panes = _pane_block(profile, fob_dir, indent="        ")
    layout = (
        'layout {\n'
        + _chrome_template()
        + f'    tab name="{name}" {{\n'
        + f'{panes}\n'
        + _floating_cheat_block(fob_dir, indent="        ")
        + '    }\n'
        + '}\n'
    )
    _save_layout(profile, layout)
    tmp = Path(tempfile.gettempdir()) / "fob-session.kdl"
    tmp.write_text(layout)
    return tmp


def generate_tab_layout(profile: dict, fob_dir: Path) -> Path:
    """Tab layout with explicit chrome (default_tab_template doesn't apply to new-tab action)."""
    name = profile["name"]
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
        + _floating_cheat_block(fob_dir, indent="    ")
        + '}\n'
    )
    tmp = Path(tempfile.gettempdir()) / f"fob-tab-{name}.kdl"
    tmp.write_text(layout)
    return tmp


def generate_tool_tab_layout(name: str, command: str) -> Path:
    """Single-pane tab with chrome for session-level tools (btop, gitcomet, etc.)."""
    layout = (
        'layout {\n'
        '    pane size=1 borderless=true {\n'
        '        plugin location="tab-bar"\n'
        '    }\n'
        f'    pane name="{name}" command="bash" {{\n'
        f'        args "-c" "{command}; exec bash -l"\n'
        '    }\n'
        '    pane size=2 borderless=true {\n'
        '        plugin location="status-bar"\n'
        '    }\n'
        '}\n'
    )
    tmp = Path(tempfile.gettempdir()) / f"fob-tab-{name}.kdl"
    tmp.write_text(layout)
    return tmp


def _add_tool_tabs(existing_tabs: set[str]) -> None:
    """Add btop and gitcomet as session-level tabs if not already open."""
    tool_tabs = [
        ("btop",      "command -v btop &>/dev/null && btop"),
        ("gitcomet",  "command -v gitcomet &>/dev/null && gitcomet"),
    ]
    for name, cmd in tool_tabs:
        if name in existing_tabs:
            continue
        layout_path = generate_tool_tab_layout(name, cmd)
        subprocess.run([
            "zellij", "--session", FOB_SESSION,
            "action", "new-tab",
            "--name", name,
            "--layout", str(layout_path),
        ])


def _launch_with_extra_tabs(extra_profiles: list[dict], fob_dir: Path, layout_path: Path) -> None:
    """Start session then add extra profile tabs and tool tabs via a background wrapper script."""
    import shlex
    adds = []
    for profile in extra_profiles:
        tab_layout = generate_tab_layout(profile, fob_dir)
        adds.append(
            f"zellij --session {FOB_SESSION} action new-tab --name {shlex.quote(profile['name'])} --layout {shlex.quote(str(tab_layout))}"
        )
    tool_tabs = [
        ("btop",     "command -v btop &>/dev/null && btop"),
        ("gitcomet", "command -v gitcomet &>/dev/null && gitcomet"),
    ]
    for name, cmd in tool_tabs:
        tl = generate_tool_tab_layout(name, cmd)
        adds.append(
            f"zellij --session {FOB_SESSION} action new-tab --name {shlex.quote(name)} --layout {shlex.quote(str(tl))}"
        )
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


def _delete_dead_session(session_name: str) -> None:
    try:
        r = subprocess.run(
            ["zellij", "list-sessions"],
            capture_output=True, text=True,
        )
        import re
        ansi = re.compile(r"\033\[[0-9;]*m")
        for line in r.stdout.splitlines():
            clean = ansi.sub("", line).strip()
            parts = clean.split()
            if parts and parts[0] == session_name and "EXITED" in clean:
                subprocess.run(
                    ["zellij", "delete-session", session_name],
                    capture_output=True,
                )
                break
    except Exception:
        pass


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

    _delete_dead_session(FOB_SESSION)

    # ZELLIJ_SESSION_NAME is authoritative — if we're inside the target session,
    # skip the subprocess query which can fail or return stale state.
    already_in_session = os.environ.get("ZELLIJ_SESSION_NAME") == FOB_SESSION
    if already_in_session or session_exists(FOB_SESSION):
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
        _add_tool_tabs(existing_tabs)
        if os.environ.get("ZELLIJ"):
            print(f"  → Tab added")
        else:
            print(f"  → Attaching to session: {FOB_SESSION}")
            attach(FOB_SESSION)
    else:
        saved = Path(profiles[0]["repo_root"]) / ".fob" / "layout-state.kdl"
        if not reset_layout and saved.exists() and all(
            kw in saved.read_text() for kw in ("tab-bar", "floating_panes")
        ):
            layout_path = saved
            print(f"  → Restoring saved layout")
        else:
            layout_path = generate_session_layout(profiles, fob_dir)
            print(f"  → Creating session '{FOB_SESSION}'")
        print(f"  → Layout: {layout_path}")
        _launch_with_extra_tabs(profiles[1:], fob_dir, layout_path)
