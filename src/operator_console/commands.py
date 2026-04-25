"""Helper command implementations."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

from operator_console.session import list_sessions
from operator_console.guardrails import get_branch, PROTECTED_BRANCHES
from operator_console.bootstrap import build_resume_prompt, write_bootstrap_file

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m", "MAG": "\033[35m",
}


def c(text: str, *keys: str) -> str:
    prefix = "".join(_C[k] for k in keys)
    return f"{prefix}{text}{_C['R']}"


def hr(width: int = 60) -> str:
    return c("─" * width, "DIM")


# ── init ──────────────────────────────────────────────────────────────────────

def cmd_init(args: list[str], console_dir: Path) -> None:
    repo_root = Path(args[0]) if args else Path.cwd()
    templates_dir = console_dir / "templates" / "console"
    claude_dir = repo_root / ".console"
    claude_dir.mkdir(exist_ok=True)

    files = ["guidelines.md", "task.md", "backlog.md", "log.md"]
    created = []
    skipped = []
    for name in files:
        dst = claude_dir / name
        src = templates_dir / name
        if dst.exists():
            skipped.append(name)
        else:
            if src.exists():
                dst.write_text(src.read_text())
            else:
                dst.write_text(f"# {name.replace('.md','').replace('-',' ').title()}\n\n")
            created.append(name)

    from operator_console.bootstrap import ensure_claude_md
    ensure_claude_md(repo_root, templates_dir)

    print(c("Initialized .console/ context files", "B"))
    print(f"  Repo: {repo_root}")
    print()
    for name in created:
        print(c(f"  ✓ created  .console/{name}", "GRN"))
    for name in skipped:
        print(c(f"  – skipped  .console/{name}  (already exists)", "DIM"))
    print()
    print(c("  CLAUDE.md updated with context reference.", "DIM"))


# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(
    args: list[str],
    console_dir: Path,
    default_profile: dict | None,
    all_repos: dict | None = None,
) -> None:
    import os

    # ── all-repos mode ────────────────────────────────────────────────────────
    if "--all" in args and all_repos is not None:
        from operator_console.launcher import CONSOLE_SESSION, _list_tabs
        from operator_console.session import session_exists as _session_exists
        running  = _session_exists(CONSOLE_SESSION)
        tabs     = _list_tabs(CONSOLE_SESSION) if running else set()
        sess_tag = c("running", "GRN") if running else c("stopped", "DIM")
        snapshots = [
            _repo_snapshot(p, p["name"] in tabs)
            for p in all_repos.values()
        ]
        print(hr())
        print(c("  STATUS", "B", "CYN") + f"  {c('—', 'DIM')}  "
              f"{c('all repos', 'DIM')}  {c('·', 'DIM')}  "
              f"{c('operator_console', 'DIM')} {sess_tag}")
        print(hr())
        col_w = max(len(s["name"]) for s in snapshots) + 2
        for s in snapshots:
            init_mark   = c("●", "GRN") if s["console_initialized"] else c("⚠", "YLW")
            branch_str  = (c(s["branch"] + " ⚠", "YLW") if s["branch_protected"]
                           else c(s["branch"], "DIM"))
            tab_mark    = c("tab ✓", "GRN") if s["tab_open"]    else c("tab –", "DIM")
            layout_mark = c("layout ✓", "GRN") if s["layout_saved"] else c("layout –", "DIM")
            name_col    = c(s["name"], "B") + " " * (col_w - len(s["name"]))
            task_snip   = c(s["task_snippet"], "DIM") if s["task_snippet"] else c("—", "DIM")
            print(f"  {init_mark}  {name_col}  {branch_str:<20}  {tab_mark}  {layout_mark}  {task_snip}")
        print()
        return

    cwd = Path.cwd()
    repo_root = Path(default_profile["repo_root"]) if default_profile else cwd

    branch = get_branch(repo_root)
    branch_disp = branch or c("(not a git repo)", "DIM")
    if branch in PROTECTED_BRANCHES:
        branch_disp = c(f"{branch}  ⚠ protected", "YLW", "B")

    from operator_console.launcher import CONSOLE_SESSION
    from operator_console import layout as layout_mod
    sessions = list_sessions()
    console_running = CONSOLE_SESSION in sessions
    session_disp = (c(f"{CONSOLE_SESSION}  (running)", "GRN") if console_running
                    else c(f"{CONSOLE_SESSION}  (stopped)", "DIM"))
    attached = os.environ.get("ZELLIJ_SESSION_NAME") == CONSOLE_SESSION
    attached_disp = c("yes", "GRN") if attached else c("no", "DIM")

    profile_name = default_profile.get("name", "—") if default_profile else c("none loaded", "DIM")

    print(hr())
    print(c("  STATUS", "B", "CYN"))
    print(hr())
    print(f"  {c('cwd         ', 'DIM')} {cwd}")
    print(f"  {c('repo        ', 'DIM')} {repo_root}")
    print(f"  {c('branch      ', 'DIM')} {branch_disp}")
    print(f"  {c('profile     ', 'DIM')} {profile_name}")
    print(f"  {c('session     ', 'DIM')} {session_disp}")
    print(f"  {c('attached    ', 'DIM')} {attached_disp}")
    print()

    # Layout status
    layout_result = layout_mod.load_any(repo_root)
    if layout_result:
        meta, kdl_path, is_current = layout_result
        tag = "" if is_current else c("  ⚠ stale repo path", "YLW")
        saved_at = meta.get("saved_at", "?")
        pname = meta.get("profile_name", "?")
        print(f"  {c('layout      ', 'DIM')} {c('saved', 'GRN')}  ·  {pname}  ·  {saved_at}{tag}")
        print(f"  {c('            ', 'DIM')} {c(str(kdl_path), 'DIM')}")
    else:
        print(f"  {c('layout      ', 'DIM')} {c('none saved', 'DIM')}  {c('(run: console layout save)', 'DIM')}")
    print()

    # Context files + current task snippet
    claude_dir = repo_root / ".console"
    if claude_dir.exists():
        print(f"  {c('.console/', 'DIM')}")
        for name in ["task.md", "guidelines.md", "backlog.md", "log.md"]:
            p = claude_dir / name
            mark = c("✓", "GRN") if p.exists() else c("✗", "DIM")
            print(f"    {mark}  {name}")
        task_path = claude_dir / "task.md"
        if task_path.exists():
            snippet = _task_snippet(task_path)
            if snippet:
                print(f"\n  {c('task        ', 'DIM')} {c(snippet, 'DIM')}")
    else:
        print(c("  ✗  .console/ not initialized — run: console init", "YLW"))
    print()


def _task_snippet(path: Path, max_len: int = 60) -> str:
    """Return first non-empty, non-heading line from a task file."""
    try:
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped[:max_len] + ("…" if len(stripped) > max_len else "")
    except Exception:
        pass
    return ""


# Keep backward-compatible alias used by cli.py and tests
_task_snippet = _task_snippet


# ── resume ────────────────────────────────────────────────────────────────────

def cmd_resume(args: list[str], default_profile: dict | None) -> None:
    repo_root = Path(default_profile["repo_root"]) if default_profile else Path.cwd()
    prompt = build_resume_prompt(repo_root)

    width = min(70, max(50, max(len(l) for l in prompt.splitlines()) + 4))
    print()
    print(c("╔" + "═" * (width - 2) + "╗", "CYN"))
    print(c("║  Claude Resume Context" + " " * (width - 25) + "║", "CYN", "B"))
    print(c("╚" + "═" * (width - 2) + "╝", "CYN"))
    print()
    print(prompt)
    print()
    print(hr(width))
    print(c("  Paste this context into Claude or run: claude --continue", "DIM"))
    print(hr(width))
    print()

    # Also write the bootstrap file for reference
    if (repo_root / ".console").exists():
        out = write_bootstrap_file(repo_root)
        print(c(f"  Written to: {out}", "DIM"))
    print()


# ── test ──────────────────────────────────────────────────────────────────────

def cmd_test(args: list[str], default_profile: dict | None) -> None:
    repo_root = Path(default_profile["repo_root"]) if default_profile else Path.cwd()
    helpers = (default_profile or {}).get("helpers", {})
    test_cmd = helpers.get("test")

    if test_cmd:
        print(c(f"▶ Running: {test_cmd}", "CYN"))
        os.execvp("bash", ["bash", "-c", f"cd '{repo_root}' && {test_cmd}"])

    # Auto-detect
    if (repo_root / "pytest.ini").exists() or (repo_root / "pyproject.toml").exists():
        cmd = f"cd '{repo_root}' && pytest -x -v"
    elif (repo_root / "package.json").exists():
        cmd = f"cd '{repo_root}' && npm test"
    else:
        print(c("No test command configured.", "YLW"))
        print(c("  Set helpers.test in your profile, or add pytest.ini / package.json.", "DIM"))
        sys.exit(1)

    print(c(f"▶ Running: {cmd}", "CYN"))
    os.execvp("bash", ["bash", "-c", cmd])


# ── audit ─────────────────────────────────────────────────────────────────────

def cmd_audit(args: list[str], default_profile: dict | None) -> None:
    repo_root = Path(default_profile["repo_root"]) if default_profile else Path.cwd()
    helpers = (default_profile or {}).get("helpers", {})
    audit_cmd = helpers.get("audit")

    if audit_cmd:
        print(c(f"▶ Running: {audit_cmd}", "CYN"))
        os.execvp("bash", ["bash", "-c", f"cd '{repo_root}' && {audit_cmd}"])
    else:
        print(c("No audit command configured.", "YLW"))
        print(c("  Set helpers.audit in your profile YAML.", "DIM"))
        print()
        print("  Example:")
        print(c("    helpers:", "DIM"))
        print(c("      audit: ./tools/open-workbench.sh audit", "DIM"))


# ── doctor ────────────────────────────────────────────────────────────────────

DEPS = [
    ("zellij",        ["zellij"],          "Terminal workspace manager — https://zellij.dev"),
    ("claude",        ["claude"],          "Claude Code CLI — https://claude.ai/code"),
    ("lazygit",       ["lazygit"],         "Git TUI — brew install lazygit / apt install lazygit"),
    ("git",           ["git"],             "Version control"),
    ("python3",       ["python3"],         "Python 3.x runtime"),
    ("fzf",           ["fzf"],             "Fuzzy finder"),
    ("inotifywait",   ["inotifywait"],     "Filesystem event watcher — apt install inotify-tools"),
]

# Mirror of loadout.sh TOOLS — name, binary alternatives, description
RICE_TOOLS = [
    ("fzf",       ["fzf"],              "Fuzzy finder — Ctrl+R, file & dir search"),
    ("bat",       ["bat", "batcat"],    "Syntax-highlighted cat"),
    ("eza",       ["eza"],              "Modern ls — colors, icons, git status"),
    ("ripgrep",   ["rg"],               "Fast grep for codebases"),
    ("fd",        ["fd", "fdfind"],     "Smarter find"),
    ("zoxide",    ["zoxide"],           "Smart cd — jump with z"),
    ("delta",     ["delta"],            "Beautiful git diffs"),
    ("lazygit",   ["lazygit"],            "Full git TUI — stage, commit, diff, log visually"),
    ("starship",  ["starship"],         "Cross-shell prompt"),
    ("fastfetch", ["fastfetch"],        "System info display"),
]


def cmd_doctor(args: list[str], scripts_dir: Path | None = None) -> None:
    print()
    print(c("  CORE DEPENDENCIES", "B", "CYN"))
    print(hr())
    missing_core = []
    for name, binaries, desc in DEPS:
        found = _which_any(binaries)
        if found:
            print(f"  {c('✓', 'GRN')} {c(name, 'B'):<20}  {c(found, 'DIM')}")
        else:
            missing_core.append(name)
            print(f"  {c('✗', 'YLW')} {c(name, 'B'):<20}  {c('not found', 'DIM')}  ←  {desc}")
    print()

    print(c("  TERMINAL TOOLS", "B", "CYN"))
    print(hr())
    missing_tools = []
    for name, binaries, desc in RICE_TOOLS:
        found = _which_any(binaries)
        if found:
            print(f"  {c('✓', 'GRN')} {c(name, 'B'):<20}  {c(found, 'DIM')}")
        else:
            missing_tools.append(name)
            print(f"  {c('✗', 'DIM')} {c(name, 'DIM'):<20}  {c(desc, 'DIM')}")
    print()

    if not missing_core and not missing_tools:
        print(c("  All tools found.", "GRN"))
        print()
        return

    manual_missing = [n for n in missing_core if n in ("zellij", "claude")]
    installable = [n for n in missing_core if n not in ("zellij", "claude")] + missing_tools

    if missing_core:
        if manual_missing:
            for name in manual_missing:
                desc = next(d for n, _, d in DEPS if n == name)
                print(c(f"  {name}: manual install required — {desc}", "YLW"))
            print()

    if installable and scripts_dir:
        print(c(f"  {len(installable)} tool(s) missing — console install can install them", "YLW"))
        try:
            answer = input(c("  Install now? [y/N] ", "B"))
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() == "y":
            os.execvp("bash", ["bash", str(scripts_dir / "loadout.sh"), "install"])
        else:
            print(c("  Run: console install  to install when ready", "DIM"))
    elif installable:
        print(c("  Run: console install  to install missing tools", "YLW"))
    print()


def _which_any(binaries: list[str]) -> str | None:
    for binary in binaries:
        try:
            r = subprocess.run(["which", binary], capture_output=True, text=True)
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
    return None



def cmd_kill(args: list[str]) -> None:
    from operator_console.launcher import CONSOLE_SESSION
    from operator_console.session import session_exists
    if not session_exists(CONSOLE_SESSION):
        print(c(f"  No active session '{CONSOLE_SESSION}'", "DIM"))
        return
    print()
    print(c("  ⚠  This terminates the session and ALL panes.", "YLW", "B"))
    print(c("     Claude, shell, lazygit — everything stops immediately.", "YLW"))
    print(c("     To keep Claude running: detach with Ctrl+o d instead.", "DIM"))
    print()
    try:
        answer = input(c("  Kill session? [y/N] ", "B"))
    except (EOFError, KeyboardInterrupt):
        print()
        print(c("  Aborted.", "DIM"))
        sys.exit(0)
    if answer.strip().lower() != "y":
        print(c("  Aborted.", "DIM"))
        sys.exit(0)
    print(c(f"  Killing session '{CONSOLE_SESSION}'...", "YLW"))
    subprocess.run(["zellij", "kill-session", CONSOLE_SESSION])
    # Reset terminal — Zellij leaves mouse tracking enabled when killed externally
    subprocess.run(["tput", "reset"])



def cmd_cheat(args: list[str], scripts_dir: Path) -> None:
    script = scripts_dir / "cheat.sh"
    if os.environ.get("ZELLIJ"):
        os.execvp("zellij", ["zellij", "action", "new-pane", "--floating",
                              "--", "bash", str(script)])
    else:
        os.execvp("bash", ["bash", str(script)])


def cmd_loadout(args: list[str], scripts_dir: Path) -> None:
    script = scripts_dir / "loadout.sh"
    os.execvp("bash", ["bash", str(script)] + args)


# ── update ────────────────────────────────────────────────────────────────────

def cmd_update(args: list[str]) -> None:
    """Update claude, codex, and aider CLIs."""
    from operator_console.bootstrap import update_clis, _CLI_UPDATES
    print()
    print(c("  UPDATING CLIs", "B", "CYN"))
    print(hr())
    results = update_clis(verbose=False)
    for name, cmd in _CLI_UPDATES:
        status = results.get(name, "?")
        if status == "ok":
            print(f"  {c('✓', 'GRN')} {c(name, 'B'):<12}  {c('updated', 'GRN')}")
        elif status.startswith("skipped"):
            print(f"  {c('–', 'DIM')} {c(name, 'DIM'):<12}  {c(status, 'DIM')}")
        else:
            print(f"  {c('✗', 'YLW')} {c(name, 'B'):<12}  {c(status, 'YLW')}")
    print()


# ── reset ────────────────────────────────────────────────────────────────────

def cmd_reset(args: list[str], default_profile: dict | None, console_dir: Path) -> None:
    """Reset OperatorConsole state — session, layout, and/or context files."""
    import os
    from operator_console.launcher import CONSOLE_SESSION
    from operator_console.session import session_exists as _session_exists
    from operator_console import layout as layout_mod

    repo_root = Path(default_profile["repo_root"]) if default_profile else Path.cwd()

    # If no scope flags given, reset everything
    no_flags = not any(f in args for f in ("--session", "--layout", "--state"))
    do_session = "--session" in args or no_flags
    do_layout  = "--layout"  in args or no_flags
    do_state   = "--state"   in args or no_flags

    # Build description of what will happen
    actions: list[tuple[str, str]] = []
    if do_session and _session_exists(CONSOLE_SESSION):
        actions.append(("session", f"kill '{CONSOLE_SESSION}' session"))
    if do_layout and layout_mod.load_any(repo_root):
        actions.append(("layout", f"delete .console/layout.json + .console/layout.kdl"))
    if do_state:
        present = [
            n for n in ("task.md", "guidelines.md", "backlog.md", "log.md")
            if (repo_root / ".console" / n).exists()
        ]
        if present:
            actions.append(("state", f"delete .console/ context files ({len(present)} files)"))

    if not actions:
        print(c("  Nothing to reset.", "DIM"))
        return

    print()
    print(c("  About to reset:", "B"))
    for scope, desc in actions:
        print(f"    {c('✗', 'RED')} {c(scope, 'B'):<12}  {c(desc, 'DIM')}")
    print()
    print(c("  This cannot be undone.", "YLW"))
    try:
        answer = input(c("  Continue? [y/N] ", "B"))
    except (EOFError, KeyboardInterrupt):
        print()
        print(c("  Aborted.", "DIM"))
        sys.exit(0)

    if answer.strip().lower() != "y":
        print(c("  Aborted.", "DIM"))
        sys.exit(0)

    print()
    if do_session and _session_exists(CONSOLE_SESSION):
        subprocess.run(["zellij", "kill-session", CONSOLE_SESSION], capture_output=True)
        print(c(f"  ✓ session  killed '{CONSOLE_SESSION}'", "GRN"))
        if os.environ.get("ZELLIJ_SESSION_NAME") != CONSOLE_SESSION:
            subprocess.run(["tput", "reset"])

    if do_layout:
        deleted = layout_mod.reset(repo_root)
        if deleted:
            print(c(f"  ✓ layout   cleared ({len(deleted)} file(s))", "GRN"))

    if do_state:
        context_files = [
            "task.md", "guidelines.md", "backlog.md", "log.md"
        ]
        removed = 0
        for name in context_files:
            p = repo_root / ".console" / name
            if p.exists():
                p.unlink()
                removed += 1
        if removed:
            print(c(f"  ✓ state    deleted {removed} context file(s)", "GRN"))
            print(c(f"    Run `console init` or `console open` to reinitialize.", "DIM"))
    print()


# ── map ───────────────────────────────────────────────────────────────────────

def _repo_snapshot(profile: dict, tab_open: bool) -> dict:
    """Gather cross-repo state for a single profile — used by --all commands."""
    from operator_console import layout as layout_mod
    repo_root = Path(profile["repo_root"]).resolve()
    branch = get_branch(repo_root)
    console_init = (repo_root / ".console").exists()
    layout_res = layout_mod.load_any(repo_root) if console_init else None
    task_snip = _task_snippet(repo_root / ".console" / "task.md") if console_init else ""
    return {
        "name":             profile["name"],
        "repo_root":        str(repo_root),
        "console_initialized":  console_init,
        "tab_open":         tab_open,
        "branch":           branch or "unknown",
        "branch_protected": branch in PROTECTED_BRANCHES if branch else False,
        "layout_saved":     layout_res is not None,
        "task_snippet":  task_snip,
    }


def cmd_map(
    args: list[str],
    default_profile: dict | None,
    console_dir: Path | None = None,
    all_repos: dict | None = None,
) -> None:
    """Print a structured snapshot of current OperatorConsole state."""
    import os
    import json as _json
    from operator_console.launcher import CONSOLE_SESSION, _list_tabs
    from operator_console.session import session_exists as _session_exists
    from operator_console import layout as layout_mod

    use_json = "--json" in args

    # ── all-repos mode ────────────────────────────────────────────────────────
    if "--all" in args and all_repos is not None:
        running  = _session_exists(CONSOLE_SESSION)
        attached = os.environ.get("ZELLIJ_SESSION_NAME") == CONSOLE_SESSION
        tabs     = _list_tabs(CONSOLE_SESSION) if running else set()
        snapshots = [
            _repo_snapshot(p, p["name"] in tabs)
            for p in all_repos.values()
        ]

        if use_json:
            print(_json.dumps({
                "session": {"name": CONSOLE_SESSION, "running": running, "attached": attached},
                "repos":   snapshots,
            }, indent=2))
            return

        print()
        print(hr())
        sess_tag = c("●", "GRN") if running else c("○", "DIM")
        print(c("  ALL REPOS", "B", "CYN") + f"  {c('session:', 'DIM')} {CONSOLE_SESSION} {sess_tag}")
        print(hr())
        for s in snapshots:
            tab_mark    = c("tab ●", "GRN") if s["tab_open"]    else c("tab ○", "DIM")
            layout_mark = c("layout ✓", "GRN") if s["layout_saved"] else c("layout –", "DIM")
            branch_str  = c(s["branch"] + " ⚠", "YLW") if s["branch_protected"] else s["branch"]
            init_mark   = c("●", "GRN") if s["console_initialized"] else c("⚠", "YLW")
            print(f"\n  {init_mark}  {c(s['name'], 'B'):<22} {branch_str:<18} {tab_mark}  {layout_mark}")
            if s["task_snippet"]:
                print(f"     {c(s['task_snippet'], 'DIM')}")
            elif not s["console_initialized"]:
                print(f"     {c('(not initialized — run: console init)', 'DIM')}")
            else:
                print(f"     {c('(no current task)', 'DIM')}")
        print()
        print(hr())
        print(f"  {c('●', 'GRN')} console initialized  "
              f"{c('⚠', 'YLW')} uninitialized or protected branch  "
              f"{c('tab ●', 'GRN')} open  {c('tab ○', 'DIM')} closed")
        print()
        return

    # ── single-repo mode ──────────────────────────────────────────────────────
    repo_root    = Path(default_profile["repo_root"]).resolve() if default_profile else Path.cwd().resolve()
    profile_name = default_profile.get("name", repo_root.name) if default_profile else repo_root.name

    branch     = get_branch(repo_root)
    running    = _session_exists(CONSOLE_SESSION)
    attached   = os.environ.get("ZELLIJ_SESSION_NAME") == CONSOLE_SESSION
    layout_res = layout_mod.load_any(repo_root)

    console_state_dir = repo_root / ".console"
    context_files = ["task.md", "guidelines.md", "backlog.md", "log.md", ".context"]
    context_state = {n: (console_state_dir / n).exists() for n in context_files}

    if use_json:
        data = {
            "repo": {"name": profile_name, "path": str(repo_root), "branch": branch or "unknown"},
            "session": {"name": CONSOLE_SESSION, "running": running, "attached": attached},
            "layout": (
                {
                    "saved":    True,
                    "current":  layout_res[2],
                    "profile":  layout_res[0].get("profile_name"),
                    "saved_at": layout_res[0].get("saved_at"),
                    "backend":  layout_res[0].get("backend"),
                    "file":     str(layout_res[1]),
                }
                if layout_res else {"saved": False}
            ),
            "context_files": context_state,
        }
        print(_json.dumps(data, indent=2))
        return

    print()
    print(hr())
    print(c("  CONSOLE STATE MAP", "B", "CYN"))
    print(hr())

    def row(label: str, value: str) -> None:
        print(f"    {c(f'{label:<12}', 'DIM')} {value}")

    print(c("  repo", "B"))
    row("name",   profile_name)
    row("path",   str(repo_root))
    row("branch", branch or c("unknown", "DIM"))
    print()

    print(c("  session", "B"))
    row("name",     CONSOLE_SESSION)
    row("status",   c("running", "GRN") if running else c("stopped", "DIM"))
    row("attached", c("yes", "GRN") if attached else c("no", "DIM"))
    print()

    print(c("  layout", "B"))
    if layout_res:
        meta, kdl_path, is_current = layout_res
        stale_tag = "" if is_current else f"  {c('⚠ stale', 'YLW')}"
        row("saved",    c("yes", "GRN") + stale_tag)
        row("profile",  meta.get("profile_name", "?"))
        row("saved at", meta.get("saved_at", "?"))
        row("backend",  meta.get("backend", "?"))
        row("file",     c(str(kdl_path), "DIM"))
    else:
        row("saved", c("none", "DIM") + f"  {c('(run: console layout save)', 'DIM')}")
    print()

    print(c("  context (.console/)", "B"))
    for name, exists in context_state.items():
        mark  = c("✓", "GRN") if exists else c("✗", "DIM")
        label = name + ("  (compiled)" if name == ".context" else "")
        print(f"    {mark}  {c(label, 'DIM') if not exists else label}")
    print()
    print(hr())
    print()


# ── layout ───────────────────────────────────────────────────────────────────

def cmd_layout(args: list[str], default_profile: dict | None, console_dir: Path) -> None:
    sub = args[0] if args else "show"
    from operator_console import layout as layout_mod
    from operator_console.launcher import CONSOLE_SESSION, generate_session_kdl

    repo_root = Path(default_profile["repo_root"]) if default_profile else Path.cwd()
    profile_name = default_profile.get("name", repo_root.name) if default_profile else repo_root.name

    if sub == "save":
        if not (repo_root / ".console").exists():
            print(c(f"  ✗ .console/ not found in {repo_root.name} — run: console init", "RED"))
            sys.exit(1)
        profile = default_profile or {"name": profile_name, "repo_root": str(repo_root)}
        kdl = generate_session_kdl([profile], console_dir)
        meta = layout_mod.save(repo_root, profile_name, kdl)
        print(c("  Layout saved", "GRN", "B"))
        print(f"  {c('backend ', 'DIM')}  {meta['backend']}")
        print(f"  {c('profile ', 'DIM')}  {meta['profile_name']}")
        print(f"  {c('saved at', 'DIM')}  {meta['saved_at']}")
        print(f"  {c('path    ', 'DIM')}  {repo_root / '.console' / layout_mod.LAYOUT_KDL}")
        print()
        print(c("  Run `console layout load` to restore this layout later.", "DIM"))

    elif sub == "load":
        import os
        from operator_console.launcher import _delete_dead_session, attach
        from operator_console.session import session_exists as _session_exists
        from operator_console.guardrails import check_branch

        result = layout_mod.load(repo_root)
        if not result:
            stale = layout_mod.load_any(repo_root)
            if stale:
                meta, _, _ = stale
                saved_root = meta.get("repo_root", "?")
                print(c(f"  ✗ Saved layout references a different repo root:", "YLW"))
                print(c(f"    saved:   {saved_root}", "DIM"))
                print(c(f"    current: {repo_root.resolve()}", "DIM"))
                print(c(f"  Run `console layout reset` then `console layout save` to update it.", "DIM"))
            else:
                print(c(f"  No saved layout for {repo_root.name}.", "YLW"))
                print(c(f"  Run `console layout save` to create one.", "DIM"))
            sys.exit(1)

        meta, kdl_path = result
        _delete_dead_session(CONSOLE_SESSION)
        already_in = os.environ.get("ZELLIJ_SESSION_NAME") == CONSOLE_SESSION
        if already_in or _session_exists(CONSOLE_SESSION):
            print(c(f"  Session '{CONSOLE_SESSION}' is already running.", "YLW"))
            print(c(f"  Run `console kill` first, then `console layout load`.", "DIM"))
            sys.exit(1)

        check_branch(repo_root)
        print(c("  Loading saved layout", "CYN", "B"))
        print(f"  {c('backend ', 'DIM')}  {meta['backend']}")
        print(f"  {c('profile ', 'DIM')}  {meta.get('profile_name', '—')}")
        print(f"  {c('saved at', 'DIM')}  {meta.get('saved_at', '—')}")
        os.execvp(
            "zellij",
            ["zellij", "--session", CONSOLE_SESSION, "--new-session-with-layout", str(kdl_path)],
        )

    elif sub == "show":
        result = layout_mod.load_any(repo_root)
        if not result:
            print(c(f"  No saved layout for {repo_root.name}.", "DIM"))
            print(c(f"  Run `console layout save` to create one.", "DIM"))
        else:
            meta, kdl_path, is_current = result
            print(hr())
            print(c("  SAVED LAYOUT", "B", "CYN"))
            print(hr())
            print(f"  {c('repo    ', 'DIM')}  {meta.get('repo_root', '—')}")
            print(f"  {c('profile ', 'DIM')}  {meta.get('profile_name', '—')}")
            print(f"  {c('backend ', 'DIM')}  {meta.get('backend', '—')}")
            print(f"  {c('saved at', 'DIM')}  {meta.get('saved_at', '—')}")
            print(f"  {c('file    ', 'DIM')}  {kdl_path}")
            if not is_current:
                print()
                print(c("  ⚠ Repo root mismatch — layout may be stale.", "YLW"))
                print(c("    Run `console layout reset` then `console layout save` to refresh.", "DIM"))
            print()

    elif sub == "reset":
        deleted = layout_mod.reset(repo_root)
        if not deleted:
            print(c(f"  No saved layout for {repo_root.name}.", "DIM"))
        else:
            for p in deleted:
                print(c(f"  ✓ removed  {p}", "GRN"))
            print()
            print(c(f"  Layout state cleared for {repo_root.name}.", "B"))

    else:
        print(c(f"  ✗ Unknown subcommand: layout {sub}", "RED"))
        print(c("  Usage: console layout save | load | show | reset", "DIM"))
        sys.exit(1)


# ── clear ────────────────────────────────────────────────────────────────────

def cmd_clear(args: list[str], default_profile: dict | None) -> None:
    from operator_console import layout as layout_mod
    clear_all = "--all" in args
    if clear_all:
        github_dir = Path.home() / "Documents" / "GitHub"
        cleared = 0
        if github_dir.exists():
            for console_dir in github_dir.glob("*/.console"):
                repo_root = console_dir.parent
                deleted = layout_mod.reset(repo_root)
                for f in deleted:
                    print(c(f"  ✓ cleared  {f}", "GRN"))
                    cleared += 1
        if cleared == 0:
            print(c("  No saved layouts found.", "DIM"))
        else:
            print()
            print(c(f"  {cleared} file(s) cleared.", "B"))
    else:
        repo_root = Path(default_profile["repo_root"]) if default_profile else Path.cwd()
        deleted = layout_mod.reset(repo_root)
        if deleted:
            for f in deleted:
                print(c(f"  ✓ cleared  {f}", "GRN"))
        else:
            print(c(f"  No saved layout for {repo_root.name}", "DIM"))


# ── save ─────────────────────────────────────────────────────────────────────

def cmd_save(args: list[str], default_profile: dict | None, console_dir: Path) -> None:
    """Capture the live Zellij tab layout and save it to config/profiles/<name>.kdl."""
    import os
    from operator_console.tab_capture import dump_live_layout, extract_panes_kdl, focused_tab_name

    reset = "--reset" in args
    named = [a for a in args if not a.startswith("--")]
    profile_name = named[0] if named else (default_profile or {}).get("name")

    if not profile_name:
        print(c("✗ Cannot determine profile — run from inside a repo or pass a name.", "RED"))
        sys.exit(1)

    profiles_dir = console_dir / "config" / "profiles"
    kdl_path = profiles_dir / f"{profile_name.lower()}.kdl"

    if reset:
        if kdl_path.exists():
            kdl_path.unlink()
            print(c(f"  ✓ removed  {kdl_path.name}", "GRN"))
            print(c(f"  Layout will be generated from YAML on next open.", "DIM"))
        else:
            print(c(f"  No saved layout for '{profile_name}'.", "DIM"))
        return

    if not os.environ.get("ZELLIJ"):
        print(c("✗ Not inside a Zellij session.", "RED"))
        print(c("  Run `console save` from inside the console session.", "DIM"))
        sys.exit(1)

    kdl = dump_live_layout()
    if not kdl:
        print(c("✗ Could not dump live layout from Zellij.", "RED"))
        sys.exit(1)

    # Find the tab — by profile name (single-profile tab name matches profile name)
    panes = extract_panes_kdl(kdl, tab_name=profile_name)
    if panes is None:
        # Try focused tab
        focused = focused_tab_name(kdl)
        if focused:
            panes = extract_panes_kdl(kdl, tab_name=focused)
            if panes:
                print(c(f"  (no tab named '{profile_name}' — saving focused tab '{focused}')", "DIM"))

    if not panes:
        print(c(f"✗ No tab named '{profile_name}' found in live session.", "RED"))
        print(c("  Make sure the tab is open and try again.", "DIM"))
        sys.exit(1)

    kdl_path.write_text(panes)
    print(c(f"  ✓ saved  config/profiles/{kdl_path.name}", "GRN"))
    print(c(f"  Next `console open {profile_name}` will use this layout.", "DIM"))
    print(c(f"  Run `console save --reset {profile_name}` to revert to YAML-generated.", "DIM"))


# ── install ───────────────────────────────────────────────────────────────────

def cmd_rewatch(args: list[str], console_dir: Path) -> None:
    from operator_console.tab_capture import dump_live_layout, focused_tab_name
    from operator_console.profile_loader import load_profile

    profiles_dir = console_dir / "config" / "profiles"

    # Determine which profiles to watch: args override, else infer from focused tab
    if args:
        raw_names = args
    else:
        kdl = dump_live_layout()
        if not kdl:
            print(c("✗ Could not read Zellij layout — not inside a Zellij session?", "RED"))
            sys.exit(1)
        tab = focused_tab_name(kdl)
        if not tab:
            print(c("✗ Could not detect focused tab name.", "RED"))
            sys.exit(1)
        raw_names = tab.split("+")

    # Resolve each name to repo_root(s), expanding group profiles
    repo_roots: list[str] = []
    for name in raw_names:
        try:
            profile = load_profile(name, profiles_dir)
        except FileNotFoundError:
            matches = [p.stem for p in profiles_dir.glob("*.yaml")
                       if p.stem.lower() == name.lower()]
            if not matches:
                print(c(f"  ⚠ Profile '{name}' not found — skipping", "YLW"))
                continue
            profile = load_profile(matches[0], profiles_dir)

        if "group" in profile:
            for sub_name in profile["group"]:
                try:
                    sub = load_profile(sub_name, profiles_dir)
                    if "repo_root" in sub:
                        repo_roots.append(sub["repo_root"])
                except Exception:
                    pass
        elif "repo_root" in profile:
            repo_roots.append(profile["repo_root"])

    if not repo_roots:
        print(c("✗ No repo roots resolved — cannot start watcher.", "RED"))
        sys.exit(1)

    labels = " ".join(Path(r).name for r in repo_roots)
    print(c(f"  rewatch → {labels}", "CYN", "B"))

    repo_args = " ".join(f"'{r}'" for r in repo_roots)
    watcher_cmd = (
        f"while true; do python3 -m operator_console.git_watcher {repo_args}; sleep 1; done"
    )
    os.execvp("bash", ["bash", "-c", watcher_cmd])


def cmd_install(args: list[str], console_dir: Path) -> None:
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)

    src = console_dir / "console"
    link = local_bin / "console"

    if link.exists() or link.is_symlink():
        if link.is_symlink() and link.resolve() == src.resolve():
            print(c("✓ console already installed", "GRN"))
            print(c(f"  {link} → {src}", "DIM"))
            return
        link.unlink()

    link.symlink_to(src)
    print(c("✓ Installed console", "GRN"))
    print(c(f"  {link} → {src}", "DIM"))

    # ~/.local/bin must be in PATH — add to .bashrc if missing
    rc = Path.home() / ".bashrc"
    local_bin_str = str(local_bin)
    if local_bin_str not in os.environ.get("PATH", "").split(":"):
        if rc.exists() and local_bin_str in rc.read_text():
            pass  # already in .bashrc, just not sourced yet
        else:
            with rc.open("a") as f:
                f.write(f'\nexport PATH="{local_bin_str}:$PATH"\n')
            print(c(f"  Added {local_bin_str} to PATH in ~/.bashrc", "DIM"))
        print(c("  Run: source ~/.bashrc  (or open a new shell)", "DIM"))
    else:
        print(c("  Available in all shells immediately", "GRN"))
