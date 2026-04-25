"""Zellij session creation and attachment."""
from __future__ import annotations
import os
import re
import subprocess
import tempfile
from pathlib import Path

from operator_console.session import session_exists
from operator_console.guardrails import check_branch
from operator_console.bootstrap import get_claude_command, get_codex_command


CONSOLE_SESSION = "operator_console"
_GITHUB_DIR = Path.home() / "Documents" / "GitHub"
_OC_STATUS  = _GITHUB_DIR / "OperationsCenter" / "scripts" / "operations-center.sh"

_C = {"R": "\033[0m", "DIM": "\033[2m", "GRN": "\033[32m", "YLW": "\033[33m"}

def _status_viewer_cmd(oc_status_raw: str, status_arg: str, key: str = "default") -> str:
    """Write a restart-loop launch script for the status viewer and return the bash command.

    Uses operator_console.status_viewer (mirrors git_watcher): clears screen, runs status,
    disables mouse modes Rich may have enabled, waits for r/q.  The while-loop
    in the script restarts the viewer if the user presses q (keeps pane alive).
    """
    key = key.lower()

    # Build the extra args list for status_viewer (repo filter, if any)
    # status_arg is already shell-safe: single quotes replaced with double quotes
    safe_arg = status_arg.replace("'", '"').strip()
    viewer_extra = f" {safe_arg}" if safe_arg else ""

    script_path = Path(tempfile.gettempdir()) / f"console-status-{key}.sh"
    script_path.write_text(
        "#!/usr/bin/env bash\n"
        f"while true; do\n"
        f"    python3 -m operator_console.status_viewer '{oc_status_raw}'{viewer_extra}\n"
        f"    sleep 1\n"
        f"done\n"
    )
    script_path.chmod(0o755)

    safe_path = str(script_path).replace("'", "'\\''")
    return f"bash '{safe_path}'"


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


# ── single-repo pane block ────────────────────────────────────────────────────
#
#  Left  28%: lazygit
#  Center   : stacked chats — claude / codex
#  Right 28%: stacked shell + status (status last)

def _single_pane_block(
    profile: dict,
    console_dir: Path,
    indent: str = "        ",
    claude_cwd: Path | None = None,
) -> str:
    repo       = profile["repo_root"]
    panes_cfg  = profile.get("panes", {})
    git_cmd    = panes_cfg.get("git",  {}).get("command", "lazygit")
    safe_repo  = repo.replace("'", "'\\''")
    safe_cwd   = str(claude_cwd).replace("'", "'\\''") if claude_cwd else safe_repo
    status_repos = profile.get("status_repos", Path(repo).name)
    status_arg   = f" --repo '{status_repos}'" if status_repos else ""
    i = indent

    claude_cmd   = get_claude_command(profile, Path(repo), console_dir=console_dir, claude_cwd=claude_cwd)
    codex_cmd    = get_codex_command(profile, Path(repo), console_dir=console_dir)
    status_cmd   = _status_viewer_cmd(str(_OC_STATUS), status_arg, key=profile.get("name", "single"))

    return (
        f'{i}pane split_direction="vertical" {{\n'
        # Left column: lazygit only
        f'{i}    pane size="28%" name="git" command="bash" {{\n'
        f'{i}        args "-c" "cd \'{safe_repo}\' && {git_cmd}; exec bash -l"\n'
        f'{i}    }}\n'
        # Center: stacked chats — claude / codex
        f'{i}    pane {{\n'
        f'{i}        pane stacked=true {{\n'
        f'{i}            pane name="claude" focus=true command="bash" {{\n'
        f'{i}                args "-c" "cd \'{safe_cwd}\' && {claude_cmd}"\n'
        f'{i}            }}\n'
        f'{i}            pane name="codex" command="bash" {{\n'
        f'{i}                args "-c" "cd \'{safe_cwd}\' && {codex_cmd}"\n'
        f'{i}            }}\n'
        f'{i}        }}\n'
        f'{i}    }}\n'
        # Right column: stacked shell + status (status last)
        f'{i}    pane size="28%" {{\n'
        f'{i}        pane stacked=true {{\n'
        f'{i}            pane name="shell" command="bash" {{\n'
        f'{i}                args "-c" "cd \'{safe_repo}\' && while true; do bash -l; sleep 1; done"\n'
        f'{i}            }}\n'
        f'{i}            pane name="status" command="bash" {{\n'
        f'{i}                args "-c" "{status_cmd}"\n'
        f'{i}            }}\n'
        f'{i}        }}\n'
        f'{i}    }}\n'
        f'{i}}}'
    )


# ── multi-repo pane block ─────────────────────────────────────────────────────
#
#  Left  28%: interactive git-dirty watcher (Enter → lazygit for that repo)
#  Center   : stacked chats — claude / codex
#  Right 28%: shell (GitHub dir) + status (status last)

def _multi_pane_block(
    profiles: list[dict],
    console_dir: Path,
    indent: str = "        ",
    tab_name: str | None = None,
) -> str:
    safe_cwd    = str(_GITHUB_DIR).replace("'", "'\\''")
    session_key = tab_name or _multi_tab_name(profiles)
    i = indent

    claude_cmd = get_claude_command(
        profiles[0], Path(profiles[0]["repo_root"]),
        console_dir=console_dir, session_key=session_key, claude_cwd=_GITHUB_DIR,
    )
    codex_cmd = get_codex_command(
        profiles[0], _GITHUB_DIR,
        console_dir=console_dir, session_key=session_key,
    )

    # Left column: single interactive git-dirty watcher (replaces N lazygit instances).
    # Enter on a repo execs lazygit for it; the restart loop brings the watcher back.
    repo_args = " ".join(f"'{p['repo_root']}'" for p in profiles)
    watcher_cmd = (
        f"while true; do "
        f"python3 -m operator_console.git_watcher {repo_args}; "
        f"sleep 1; "
        f"done"
    )
    left_block = (
        f'{i}    pane size="28%" name="git" command="bash" {{\n'
        f'{i}        args "-c" "{watcher_cmd}"\n'
        f'{i}    }}\n'
    )

    # Center: stacked chats — claude / codex
    center_block = (
        f'{i}    pane {{\n'
        f'{i}        pane stacked=true {{\n'
        f'{i}            pane name="claude" focus=true command="bash" {{\n'
        f'{i}                args "-c" "cd \'{safe_cwd}\' && {claude_cmd}"\n'
        f'{i}            }}\n'
        f'{i}            pane name="codex" command="bash" {{\n'
        f'{i}                args "-c" "cd \'{safe_cwd}\' && {codex_cmd}"\n'
        f'{i}            }}\n'
        f'{i}        }}\n'
        f'{i}    }}\n'
    )

    # Right column: stacked shells + status (status last)
    _repo_filter = next(
        (p["status_repos"] for p in profiles if "status_repos" in p),
        "",
    )
    status_arg = f" --repo '{_repo_filter}'" if _repo_filter else ""
    status_cmd = _status_viewer_cmd(str(_OC_STATUS), status_arg, key=session_key)

    right_block = (
        f'{i}    pane size="28%" {{\n'
        f'{i}        pane stacked=true {{\n'
        f'{i}            pane name="shell" command="bash" {{\n'
        f'{i}                args "-c" "cd \'{safe_cwd}\' && while true; do bash -l; sleep 1; done"\n'
        f'{i}            }}\n'
        f'{i}            pane name="status" command="bash" {{\n'
        f'{i}                args "-c" "{status_cmd}"\n'
        f'{i}            }}\n'
        f'{i}        }}\n'
        f'{i}    }}\n'
    )

    return (
        f'{i}pane split_direction="vertical" {{\n'
        + left_block
        + center_block
        + right_block
        + f'{i}}}'
    )


def _multi_tab_name(profiles: list[dict]) -> str:
    return "+".join(p["name"] for p in profiles)


# ── chrome / chrome-less wrappers ─────────────────────────────────────────────

def _chrome_template() -> str:
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


def _tab_chrome_wrap(panes_kdl: str) -> str:
    """Wrap pane KDL in a standalone tab layout with explicit chrome."""
    return (
        'layout {\n'
        '    pane size=1 borderless=true {\n'
        '        plugin location="tab-bar"\n'
        '    }\n'
        f'{panes_kdl}\n'
        '    pane size=2 borderless=true {\n'
        '        plugin location="status-bar"\n'
        '    }\n'
        '}\n'
    )


# ── public generators ─────────────────────────────────────────────────────────

def _saved_panes_kdl(profile: dict, console_dir: Path) -> str | None:
    """Return saved KDL panes for a profile if one exists, else None."""
    name = profile.get("name", "")
    if not name:
        return None
    kdl_path = console_dir / "config" / "profiles" / f"{name.lower()}.kdl"
    if kdl_path.exists():
        try:
            return kdl_path.read_text()
        except Exception:
            pass
    return None


def generate_session_kdl(profiles: list[dict], console_dir: Path, tab_name: str | None = None) -> str:
    """Return session layout KDL string (no side effects)."""
    if len(profiles) == 1:
        name  = tab_name or profiles[0]["name"]
        panes = _saved_panes_kdl(profiles[0], console_dir) or _single_pane_block(profiles[0], console_dir, indent="        ")
    else:
        name  = tab_name or _multi_tab_name(profiles)
        panes = _multi_pane_block(profiles, console_dir, indent="        ", tab_name=name)

    return (
        'layout {\n'
        + _chrome_template()
        + f'    tab name="{name}" {{\n'
        + f'{panes}\n'
        + '    }\n'
        + '}\n'
    )


def generate_session_layout(profiles: list[dict], console_dir: Path, tab_name: str | None = None) -> Path:
    """Write session layout to /tmp, return path."""
    tmp = Path(tempfile.gettempdir()) / "console-session.kdl"
    tmp.write_text(generate_session_kdl(profiles, console_dir, tab_name=tab_name))
    return tmp


def generate_tab_layout(profiles: list[dict], console_dir: Path, tab_name: str | None = None) -> tuple[Path, str]:
    """Write a standalone tab layout (for adding to running session) to /tmp."""
    if len(profiles) == 1:
        name  = tab_name or profiles[0]["name"]
        panes = _saved_panes_kdl(profiles[0], console_dir) or _single_pane_block(profiles[0], console_dir, indent="    ")
    else:
        name  = tab_name or _multi_tab_name(profiles)
        panes = _multi_pane_block(profiles, console_dir, indent="    ", tab_name=name)

    tmp = Path(tempfile.gettempdir()) / f"console-tab-{name}.kdl"
    tmp.write_text(_tab_chrome_wrap(panes))
    return tmp, name


# ── session helpers ───────────────────────────────────────────────────────────

def _delete_dead_session(session_name: str) -> None:
    try:
        r = subprocess.run(["zellij", "list-sessions"], capture_output=True, text=True)
        ansi = re.compile(r"\033\[[0-9;]*m")
        for line in r.stdout.splitlines():
            clean = ansi.sub("", line).strip()
            parts = clean.split()
            if parts and parts[0] == session_name and "EXITED" in clean:
                subprocess.run(["zellij", "delete-session", session_name], capture_output=True)
                break
    except Exception:
        pass


def _clear_resurrection_cache(session_name: str) -> None:
    """Delete Zellij's stale resurrection KDL for this session to prevent parse errors."""
    try:
        cache_dir = Path.home() / ".cache" / "zellij"
        for stale in cache_dir.glob(f"*/session_info/{session_name}/session-layout.kdl"):
            stale.unlink()
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


def attach(session_name: str = CONSOLE_SESSION) -> None:
    os.execvp("zellij", ["zellij", "attach", session_name])


# ── launch ────────────────────────────────────────────────────────────────────

def launch(
    profiles: list[dict],
    console_dir: Path,
    saved_layout_path: Path | None = None,
    tab_name: str | None = None,
) -> None:
    for profile in profiles:
        check_branch(Path(profile["repo_root"]))

    _delete_dead_session(CONSOLE_SESSION)

    already_in_session = os.environ.get("ZELLIJ_SESSION_NAME") == CONSOLE_SESSION
    if already_in_session or session_exists(CONSOLE_SESSION):
        existing_tabs = _list_tabs(CONSOLE_SESSION)
        layout_path, tab_name = generate_tab_layout(profiles, console_dir, tab_name=tab_name)
        if tab_name in existing_tabs:
            print(f"  {_c('tab', 'DIM')}  {_c(tab_name, 'DIM')}  {_c('already open', 'DIM')}")
        else:
            r = subprocess.run([
                "zellij", "--session", CONSOLE_SESSION,
                "action", "new-tab",
                "--name", tab_name,
                "--layout", str(layout_path),
            ], capture_output=True, text=True)
            if r.returncode == 0:
                print(f"  {_c('tab', 'DIM')}  {_c(tab_name, 'GRN')}  {_c('added', 'GRN')}")
            else:
                print(f"  {_c('tab', 'DIM')}  {_c(tab_name, 'YLW')}  {_c('failed', 'YLW')}")
                print(f"  {_c(r.stderr.strip(), 'DIM')}")
        if not os.environ.get("ZELLIJ"):
            _clear_resurrection_cache(CONSOLE_SESSION)
            attach(CONSOLE_SESSION)
    else:
        if saved_layout_path is not None:
            layout_path = saved_layout_path
        else:
            layout_path = generate_session_layout(profiles, console_dir, tab_name=tab_name)
        os.execvp(
            "zellij",
            ["zellij", "--session", CONSOLE_SESSION, "--new-session-with-layout", str(layout_path)],
        )
