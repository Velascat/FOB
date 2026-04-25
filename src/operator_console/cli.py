#!/usr/bin/env python3
"""console — Operator Console CLI entrypoint."""
from __future__ import annotations
import os
import sys
from pathlib import Path

CONSOLE_DIR = Path(__file__).resolve().parent.parent.parent
PROFILES_DIR = CONSOLE_DIR / "config" / "profiles"
SCRIPTS_DIR = CONSOLE_DIR / "tools"

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m", "MAG": "\033[35m",
}


def c(text: str, *keys: str) -> str:
    prefix = "".join(_C[k] for k in keys)
    return f"{prefix}{text}{_C['R']}"


BANNER = r"""
     ██████╗ ██████╗ ███╗   ██╗███████╗ ██████╗ ██╗     ███████╗
    ██╔════╝██╔═══██╗████╗  ██║██╔════╝██╔═══██╗██║     ██╔════╝
    ██║     ██║   ██║██╔██╗ ██║███████╗██║   ██║██║     █████╗
    ██║     ██║   ██║██║╚██╗██║╚════██║██║   ██║██║     ██╔══╝
    ╚██████╗╚██████╔╝██║ ╚████║███████║╚██████╔╝███████╗███████╗
     ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚══════╝╚══════╝
"""


def _dep_status_line() -> str:
    import subprocess
    deps = ["zellij", "claude", "lazygit", "git", "python3", "fzf"]
    parts = []
    for d in deps:
        try:
            ok = subprocess.run(["which", d], capture_output=True).returncode == 0
        except Exception:
            ok = False
        parts.append(f"{c('✓', 'GRN') if ok else c('✗', 'YLW')} {c(d, 'DIM')}")
    return "  " + "  ".join(parts)


def show_menu(_: list[str]) -> None:
    import subprocess
    print(c(BANNER, "CYN", "B"))
    print(c("    Operator Console\n", "DIM"))
    print(_dep_status_line())
    print()

    options = [
        ("open",    "pick and launch a workspace"),
        ("restore", "re-open last session group"),
        ("context", "print context from .console/"),
        ("rewatch", "restart git watcher for this tab's profile"),
        ("status",  "repo, branch, session state"),
        ("run",        "run a task through the full execution pipeline"),
        ("cycle",      "single autonomous cycle: observe → propose → execute"),
        ("runs",       "list recent execution runs"),
        ("clean",      "remove old run artifacts, keep latest N"),
        ("last",       "inspect the most recent execution run"),
        ("demo",      "validate selector + planning handoff architecture"),
        ("providers", "show selector and lane readiness"),
        ("doctor",    "full dependency check + install"),
        ("update",  "update claude, codex, and aider CLIs"),
        ("install", "install and configure dev tools"),
        ("cheat",   "keybinding reference"),
        ("help",    "full command reference"),
    ]

    try:
        result = subprocess.run(["fzf", "--version"], capture_output=True)
        has_fzf = result.returncode == 0
    except FileNotFoundError:
        has_fzf = False

    if has_fzf:
        fzf_input = "\n".join(f"{cmd:<10} {desc}" for cmd, desc in options)
        result = subprocess.run(
            ["fzf", "--prompt", "  console > ", "--height", "12",
             "--border", "--no-sort", "--tabstop", "1"],
            input=fzf_input, text=True, stdout=subprocess.PIPE,
        )
        if result.returncode != 0 or not result.stdout.strip():
            sys.exit(0)
        chosen = result.stdout.strip().split()[0]
    else:
        for i, (cmd, desc) in enumerate(options, 1):
            print(f"  {c(str(i), 'CYN')}  {c(cmd, 'B'):<12}  {c(desc, 'DIM')}")
        print(f"  {c('q', 'CYN')}  quit")
        print()
        try:
            choice = input(c("  > ", "B")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if choice in ("q", "Q"):
            sys.exit(0)
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            chosen = options[int(choice) - 1][0]
        elif choice in {cmd for cmd, _ in options}:
            chosen = choice
        else:
            print(c("✗ Invalid selection", "RED"))
            sys.exit(1)

    # Re-enter main with chosen command
    sys.argv = [sys.argv[0], chosen]
    main()


def show_help(_: list[str]) -> None:
    print(c(BANNER, "CYN", "B"))
    print(c("    Operator Console\n", "DIM"))

    sections = [
        ("WORKSPACE", [
            ("open [profile]",    "Auto-select current repo and launch"),
            ("open --layout",     "Launch using saved layout (explicit restore)"),
            ("multi [--all]",     "Multi-select picker — open several repos; --all skips picker"),
            ("restore [--show]",  "Re-open last saved session group (--show to preview)"),
            ("context",           "Print Claude resume context from .console/"),
            ("attach",            "Re-attach to running console session"),
            ("kill",              "Terminate console session and all panes (with warning)"),
            ("init    [repo]",    "Initialize .console/ state files in repo"),
            ("doctor",            "Check dependencies (Zellij, Claude, lazygit…)"),
        ]),
        ("VISIBILITY", [
            ("status",            "System readiness: SwitchBoard, OperationsCenter, lanes, last run"),
            ("status --repo",     "Repo/session state (branch, layout, .console/ files)"),
            ("status --all",      "All repos compact table"),
            ("overview",          "Full state snapshot  (--json for machine output)"),
            ("overview --all",    "Snapshot of all repos  (--json supported)"),
        ]),
        ("RESET", [
            ("reset",             "Full reset — session + layout + state (confirms first)"),
            ("reset --session",   "Kill session only"),
            ("reset --layout",    "Clear saved layout only"),
            ("reset --state",     "Delete .console/ state files only"),
            ("clear [--all]",     "Delete saved layout (current repo or all)"),
        ]),
        ("LAYOUT", [
            ("save [profile]",    "Capture live Zellij tab → save to config/profiles/<name>.kdl"),
            ("save --reset [p]",  "Delete saved layout, revert to YAML-generated"),
            ("layout save",       "Save current repo layout to .console/layout.json"),
            ("layout load",       "Restore saved layout (starts Zellij session)"),
            ("layout show",       "Show saved layout metadata and path"),
            ("layout reset",      "Delete saved layout state for current repo"),
        ]),
        ("OPS", [
            ("run --goal TEXT",        "Run a task through the full OperationsCenter pipeline"),
            ("run --dry-run",          "Planning only — print lane decision without executing"),
            ("cycle",                  "Single autonomous cycle: observe → propose → execute"),
            ("cycle --dry-run",        "Observe + plan only — print lane decision without executing"),
            ("cycle --json",           "Machine-readable cycle output"),
            ("runs",                   "List recent execution runs (newest first)"),
            ("runs --limit N",         "Show N most recent runs (default 20)"),
            ("runs --json",            "Machine-readable run list"),
            ("clean --keep N",         "Delete runs older than the N most recent (default 10)"),
            ("clean --dry-run",        "Show what would be deleted without deleting"),
            ("last",                   "Inspect the most recent execution run"),
            ("last --all",             "Show last run + list of recent runs"),
            ("last --json",            "Machine-readable last run summary"),
            ("status",                 "System readiness: SwitchBoard, OperationsCenter, lanes"),
            ("status --json",          "Machine-readable system readiness"),
            ("demo",              "Validate stack → SwitchBoard route → OperationsCenter handoff"),
            ("demo --no-start",   "Run the same validation without starting the stack"),
            ("demo --json",       "Machine-readable summary"),
            ("providers",         "Show selector and lane readiness"),
            ("providers --wait",  "Poll until the selector is healthy"),
            ("test",              "Run project tests"),
            ("audit",             "Run project audit"),
        ]),
        ("TOOLS", [
            ("update",            "Update claude, codex, and aider CLIs"),
            ("cheat",             "Open full cheatsheet in floating pane"),
            ("install",           "Install and configure dev tools"),
            ("install",           "Symlink console to ~/.local/bin"),
        ]),
    ]

    for heading, entries in sections:
        print(c(f"  {heading}", "B"))
        for cmd, desc in entries:
            print(f"    {c(cmd, 'CYN'):<34}{c(desc, 'DIM')}")
        print()


def _profile_for_cwd() -> dict | None:
    """Find the profile whose repo_root contains the current working directory."""
    cwd = Path.cwd()
    try:
        repos = _discover_repos()
        for profile in repos.values():
            repo = Path(profile["repo_root"]).resolve()
            if cwd == repo or cwd.is_relative_to(repo):
                return profile
    except Exception:
        pass
    return None


def _discover_repos() -> dict[str, dict]:
    """Scan ~/Documents/GitHub/ for git repos, return name→profile dict."""
    import yaml
    github_dir = Path.home() / "Documents" / "GitHub"
    found: dict[str, dict] = {}
    if not github_dir.exists():
        return found
    for d in sorted(github_dir.iterdir()):
        if d.is_dir() and (d / ".git").exists():
            found[d.name.lower()] = {"name": d.name, "repo_root": str(d)}
    # Overlay configured profiles (they override auto-discovered by repo_root match)
    for p in PROFILES_DIR.glob("*.yaml"):
        try:
            data = yaml.safe_load(p.read_text())
            if not data:
                continue
            from operator_console.profile_loader import _expand_paths
            _expand_paths(data)
            if "group" in data and "repo_root" not in data:
                # Group profile — register by name, never overlay a repo entry
                found[data["name"].lower()] = data
                continue
            repo = Path(data.get("repo_root", ""))
            # Replace any auto-discovered entry for the same repo
            for name, entry in list(found.items()):
                if Path(entry["repo_root"]).resolve() == repo.resolve():
                    found[name] = data
                    break
            else:
                found[data["name"].lower()] = data
        except Exception:
            pass
    return found


def _autopick() -> tuple[list[dict], str | None]:
    """Auto-select current repo, or show single-select picker if not in any repo."""
    import subprocess
    from operator_console.session import session_exists
    from operator_console.launcher import CONSOLE_SESSION

    all_profiles = _discover_repos()
    if not all_profiles:
        print(c("✗ No repos found", "RED"))
        sys.exit(1)

    # Always auto-select if cwd is inside a known repo — tab-open state doesn't matter,
    # launch() will attach without duplicating if the tab is already there.
    cwd = Path.cwd()
    for profile in all_profiles.values():
        if "repo_root" not in profile:
            continue
        repo = Path(profile["repo_root"]).resolve()
        if cwd == repo or cwd.is_relative_to(repo):
            return [profile], None

    # cwd is outside all repos (e.g. ~/Documents/GitHub/ itself) → single-select picker
    return _run_picker(all_profiles, multi=False)


def _pick_multi(all: bool = False) -> tuple[list[dict], str | None]:
    """Explicit multi-select picker — used by `console multi`."""
    all_profiles = _discover_repos()
    if not all_profiles:
        print(c("✗ No repos found", "RED"))
        sys.exit(1)
    if all:
        return list(all_profiles.values()), None
    return _run_picker(all_profiles, multi=True)


def _expand_selection(selected_raw: list[dict]) -> tuple[list[dict], str | None]:
    """Expand any group profiles in a selection into their constituent profiles.

    Returns (expanded_profiles, tab_name_override).
    tab_name_override is set when a single group profile was selected — the tab
    is named after the group rather than the joined member names.
    """
    from operator_console.profile_loader import load_profile
    result = []
    seen = set()
    # Single group selected → use group name as tab label
    tab_name: str | None = None
    if len(selected_raw) == 1 and "group" in selected_raw[0] and "repo_root" not in selected_raw[0]:
        tab_name = selected_raw[0]["name"]
    for p in selected_raw:
        if "group" in p:
            for sub_name in p["group"]:
                try:
                    sub = load_profile(sub_name, PROFILES_DIR)
                except FileNotFoundError as e:
                    print(c(f"✗ {e}", "RED")); sys.exit(1)
                if sub["name"] not in seen:
                    result.append(sub)
                    seen.add(sub["name"])
        else:
            if p["name"] not in seen:
                result.append(p)
                seen.add(p["name"])
    return result, tab_name


def _run_picker(all_profiles: dict, multi: bool) -> tuple[list[dict], str | None]:
    """Show fzf or numbered picker. multi=True enables Tab multi-select.

    Repos and groups are shown together; groups are prefixed with ▸ and
    show their member list so the distinction is immediately visible.
    """
    import subprocess
    from operator_console.session import session_exists
    from operator_console.launcher import CONSOLE_SESSION

    repo_keys  = sorted(k for k, v in all_profiles.items() if "repo_root" in v)
    group_keys = sorted(k for k, v in all_profiles.items() if "group" in v and "repo_root" not in v)
    session_running = session_exists(CONSOLE_SESSION)

    try:
        result = subprocess.run(["fzf", "--version"], capture_output=True)
        has_fzf = result.returncode == 0
    except FileNotFoundError:
        has_fzf = False

    dot = "●" if session_running else "○"

    # Build ordered list: groups first (so they're easy to spot), then repos
    ordered_keys = group_keys + repo_keys
    display_to_key: dict[str, str] = {}

    def _display_line(k: str) -> str:
        p = all_profiles[k]
        if "group" in p:
            members = ", ".join(p["group"])
            display_to_key[p["name"]] = k        # key = plain name
            return f"▸ {p['name']}  \033[2m{members}\033[0m"
        else:
            display_to_key[p["name"]] = k        # key = plain name
            return f"{dot} {p['name']}"

    if has_fzf:
        fzf_lines = "\n".join(_display_line(k) for k in ordered_keys)
        prompt = "  multi > " if multi else "  open > "
        if multi:
            header = (
                "\033[93mTab\033[0m mark/unmark  ·  "
                "\033[93mEnter\033[0m open  ·  "
                "\033[35m▸ group\033[0m  \033[2mrepo\033[0m"
                + ("  ·  \033[32msession running\033[0m" if session_running else "")
            )
        else:
            header = (
                "\033[93mEnter\033[0m open  ·  "
                "\033[35m▸ group\033[0m  \033[2mrepo\033[0m"
                + ("  ·  \033[32msession running\033[0m" if session_running else "")
            )
        fzf_args = ["fzf", "--prompt", prompt, "--height", "14",
                    "--border", "--no-sort", "--ansi", "--header-first", "--header", header]
        if multi:
            fzf_args += ["--multi", "--bind", "tab:toggle+down"]
        result = subprocess.run(fzf_args, input=fzf_lines, text=True, stdout=subprocess.PIPE)
        if result.returncode != 0 or not result.stdout.strip():
            sys.exit(0)
        selected_raw = []
        for line in result.stdout.strip().splitlines():
            # Strip leading symbol (●, ○, ▸) and spaces, then drop member list
            # that follows double-space on group lines: "▸ name  member1, …"
            name = line.strip().lstrip("●○▸ ").split("  ")[0].strip()
            k = display_to_key.get(name)
            if k:
                selected_raw.append(all_profiles[k])
        return _expand_selection(selected_raw)  # returns (profiles, tab_name)

    # Numbered fallback
    print()
    print(c("  SELECT REPO" + ("S" if multi else ""), "B", "CYN"))
    if session_running:
        print(c("  session running — selected repos open as new tabs", "GRN"))
    print(c("─" * 44, "DIM"))
    sym = c("●", "GRN") if session_running else c("○", "DIM")
    for i, k in enumerate(ordered_keys, 1):
        p = all_profiles[k]
        if "group" in p:
            members = c(", ".join(p["group"]), "DIM")
            print(f"  {c(str(i), 'CYN')}  {c('▸', 'MAG')}  {c(p['name'], 'B')}  {members}")
        else:
            print(f"  {c(str(i), 'CYN')}  {sym}  {p['name']}")
    print()
    prompt_text = "  repos (space-separated): " if multi else "  repo: "
    if multi:
        print(c("  Enter numbers separated by spaces (e.g. 1 2)", "DIM"))
    try:
        choice = input(c(prompt_text, "B")).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)

    selected_raw = []
    for token in choice.replace(",", " ").split():
        if token.isdigit() and 1 <= int(token) <= len(ordered_keys):
            selected_raw.append(all_profiles[ordered_keys[int(token) - 1]])
        elif token in all_profiles:
            selected_raw.append(all_profiles[token])
    if not selected_raw:
        print(c("✗ No valid selection", "RED"))
        sys.exit(1)
    return _expand_selection(selected_raw)  # returns (profiles, tab_name)


def _require_zellij() -> None:
    import subprocess
    try:
        subprocess.run(["zellij", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(c("✗ Zellij not found.", "RED"))
        print(c("  Install: https://zellij.dev/documentation/installation", "DIM"))
        print(c("  Or check with: console doctor", "DIM"))
        sys.exit(1)


def _run_open(profiles: list[dict], use_saved_layout: bool = False, tab_name: str | None = None) -> None:
    """Core launch flow shared by `console open`, `console multi`, and `console context`."""
    from operator_console.profile_loader import load_profile
    from operator_console.launcher import launch, CONSOLE_SESSION
    from operator_console.bootstrap import ensure_claude_md, write_bootstrap_file
    from operator_console.session import session_exists as _sess_exists
    from operator_console.session_group import save as _sg_save
    import os as _os

    for profile in profiles:
        claude_cfg = profile.get("claude", {})
        bootstrap_files = claude_cfg.get("bootstrap_files") or None
        peer_roots: list[tuple[str, Path]] = []
        for peer_name in claude_cfg.get("peers", []):
            try:
                peer = load_profile(peer_name, PROFILES_DIR)
                peer_roots.append((peer["name"], Path(peer["repo_root"])))
            except Exception:
                print(c(f"  ⚠ peer '{peer_name}' not found — skipping", "YLW"))

        if len(profiles) > 1:
            configured = {r for _, r in peer_roots}
            for sibling in profiles:
                if sibling is not profile:
                    sibling_root = Path(sibling["repo_root"])
                    if sibling_root not in configured:
                        peer_roots.append((sibling["name"], sibling_root))

        repo_root = Path(profile["repo_root"])
        if not (repo_root / ".console").exists():
            from operator_console import commands as _cmds
            print(c(f"  .console/ not found in {profile['name']} — initializing...", "YLW"))
            _cmds.cmd_init([str(repo_root)], CONSOLE_DIR)
        write_bootstrap_file(repo_root, files=bootstrap_files,
                             peer_roots=peer_roots or None, profile_name=profile["name"])
        extra_files = [f for f in (bootstrap_files or [])
                       if Path(f).name not in {
                           "guidelines.md", "task.md",
                           "backlog.md", "log.md",
                       }]
        ensure_claude_md(repo_root, CONSOLE_DIR / "templates" / "console",
                         extra_files=extra_files or None)

    _sg_save([p["name"] for p in profiles], CONSOLE_SESSION)

    saved_layout_path = None
    if use_saved_layout and profiles:
        from operator_console import layout as layout_mod
        result = layout_mod.load(Path(profiles[0]["repo_root"]))
        if result:
            saved_layout_path = result[1]

    already_in = _os.environ.get("ZELLIJ_SESSION_NAME") == CONSOLE_SESSION
    session_running = already_in or _sess_exists(CONSOLE_SESSION)

    label = ", ".join(p["name"] for p in profiles)
    print(c(f"\n  Open: {label}", "B", "CYN"))
    if session_running:
        print(f"  {c('session  ', 'DIM')}attaching  {c(f'({CONSOLE_SESSION})', 'DIM')}")
    else:
        print(f"  {c('session  ', 'DIM')}creating   {c(f'({CONSOLE_SESSION})', 'DIM')}")
        if saved_layout_path:
            layout_desc = c("saved", "GRN")
        elif use_saved_layout:
            layout_desc = c("fresh", "DIM") + "  " + c("(no saved layout)", "YLW")
        else:
            layout_desc = c("fresh", "DIM")
        print(f"  {c('layout   ', 'DIM')}{layout_desc}")
    if profiles:
        _ap = Path(profiles[0]["repo_root"]) / ".console" / "task.md"
        if _ap.exists():
            from operator_console.commands import _task_snippet
            snip = _task_snippet(_ap)
            if snip:
                print(f"  {c('task     ', 'DIM')}{c(snip, 'DIM')}")
    print()
    launch(profiles, CONSOLE_DIR, saved_layout_path=saved_layout_path, tab_name=tab_name)


# ── dispatch ──────────────────────────────────────────────────────────────────

def main() -> None:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "open"
    args = argv[1:]

    if cmd in ("-h", "--help"):
        cmd = "help"
    if cmd == "--menu":
        cmd = "menu"
    if cmd == "--open":
        cmd = "open"

    from operator_console import commands

    match cmd:

        case "menu":
            show_menu(args)

        case "help":
            show_help(args)

        case "open":
            _require_zellij()
            use_saved_layout = "--layout" in args
            named = [a for a in args if not a.startswith("--")]
            if named:
                from operator_console.profile_loader import load_profile, validate_profile
                raw = []
                for pname in named:
                    try:
                        raw.append(load_profile(pname, PROFILES_DIR))
                    except FileNotFoundError as e:
                        print(c(f"✗ {e}", "RED")); sys.exit(1)
                profiles, tab_name = _expand_selection(raw)
                for p in profiles:
                    errs = validate_profile(p)
                    if errs:
                        print(c(f"✗ Profile '{p['name']}' validation errors:", "RED"))
                        for e in errs:
                            print(c(f"  · {e}", "DIM"))
                        sys.exit(1)
            else:
                profiles, tab_name = _autopick()
            _run_open(profiles, use_saved_layout=use_saved_layout, tab_name=tab_name)

        case "multi":
            _require_zellij()
            profiles, tab_name = _pick_multi(all="--all" in args)
            _run_open(profiles, use_saved_layout=False, tab_name=tab_name)

        case "kill":
            commands.cmd_kill(args)

        case "restore":
            from operator_console.session_group import load as _sg_load
            data = _sg_load()
            if not data:
                print(c("  No saved session group found.", "DIM"))
                print(c("  Run `console open` to create a restorable group.", "DIM"))
                sys.exit(1)
            repo_names = data.get("repos", [])
            saved_at   = data.get("saved_at", "?")
            print(c(f"\n  Restore: {', '.join(repo_names)}", "B", "CYN"))
            print(f"  {c('saved    ', 'DIM')}{saved_at}")
            if "--show" in args:
                print()
                sys.exit(0)
            _require_zellij()
            all_repos = _discover_repos()
            profiles = []
            for name in repo_names:
                entry = all_repos.get(name.lower()) or all_repos.get(name)
                if entry:
                    profiles.append(entry)
                else:
                    print(c(f"  ⚠ '{name}' not found in repo discovery — skipping", "YLW"))
            if not profiles:
                print(c("  No restorable repos found.", "RED"))
                sys.exit(1)
            _run_open(profiles)

        case "save":
            commands.cmd_save(args, _profile_for_cwd(), CONSOLE_DIR)

        case "layout":
            _require_zellij()
            commands.cmd_layout(args, _profile_for_cwd(), CONSOLE_DIR)

        case "reset":
            commands.cmd_reset(args, _profile_for_cwd(), CONSOLE_DIR)

        case "overview" | "map":
            all_repos = _discover_repos() if "--all" in args else None
            commands.cmd_map(args, _profile_for_cwd(), CONSOLE_DIR, all_repos)

        case "clear":
            commands.cmd_clear(args, _profile_for_cwd())

        case "attach":
            _require_zellij()
            from operator_console.launcher import attach, CONSOLE_SESSION
            from operator_console.session import session_exists
            if not session_exists(CONSOLE_SESSION):
                print(c(f"✗ No session '{CONSOLE_SESSION}'. Run: console open", "RED"))
                sys.exit(1)
            attach(CONSOLE_SESSION)

        case "init":
            commands.cmd_init(args, CONSOLE_DIR)

        case "context" | "resume":
            commands.cmd_resume(args, _profile_for_cwd())

        case "run" | "delegate":
            from operator_console.delegate import run_delegate
            sys.exit(run_delegate(args))

        case "cycle" | "auto-once":
            from operator_console.auto_once import run_auto_once
            sys.exit(run_auto_once(args))

        case "runs":
            from operator_console.runs_cmd import run_runs
            sys.exit(run_runs(args))

        case "clean":
            from operator_console.clean import run_clean
            sys.exit(run_clean(args))

        case "last":
            from operator_console.last import run_last
            sys.exit(run_last(args))

        case "status":
            if "--repo" in args or "--all" in args:
                all_repos = _discover_repos() if "--all" in args else None
                commands.cmd_status(args, CONSOLE_DIR, _profile_for_cwd(), all_repos)
            else:
                from operator_console.system_status import run_status
                sys.exit(run_status(args))

        case "demo":
            from operator_console.demo import run_demo
            sys.exit(run_demo(args))

        case "providers":
            from operator_console.providers import run_providers
            sys.exit(run_providers(args))

        case "test":
            commands.cmd_test(args, _profile_for_cwd())

        case "audit":
            commands.cmd_audit(args, _profile_for_cwd())

        case "doctor":
            commands.cmd_doctor(args, SCRIPTS_DIR)

        case "cheat":
            commands.cmd_cheat(args, SCRIPTS_DIR)

        case "update":
            commands.cmd_update(args)

        case "install" | "loadout":
            commands.cmd_loadout(args, SCRIPTS_DIR)

        case "rewatch":
            commands.cmd_rewatch(args, CONSOLE_DIR)

        case _:
            print(c(f"✗ Unknown command: {cmd}", "RED"))
            print(c("  Run: console help", "DIM"))
            sys.exit(1)


if __name__ == "__main__":
    main()
