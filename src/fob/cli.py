#!/usr/bin/env python3
"""fob — forward operating base CLI entrypoint."""
from __future__ import annotations
import sys
from pathlib import Path

FOB_DIR = Path(__file__).resolve().parent.parent.parent
PROFILES_DIR = FOB_DIR / "config" / "profiles"
SCRIPTS_DIR = FOB_DIR / "tools"
VF_DIR = FOB_DIR.parent / "VideoFoundry"

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m", "MAG": "\033[35m",
}


def c(text: str, *keys: str) -> str:
    prefix = "".join(_C[k] for k in keys)
    return f"{prefix}{text}{_C['R']}"


BANNER = r"""
    ███████╗ ██████╗ ██████╗
    ██╔════╝██╔═══██╗██╔══██╗
    █████╗  ██║   ██║██████╔╝
    ██╔══╝  ██║   ██║██╔══██╗
    ██║     ╚██████╔╝██████╔╝
    ╚═╝      ╚═════╝ ╚═════╝
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
    print(c("    forward operating base\n", "DIM"))
    print(_dep_status_line())
    print()

    options = [
        ("brief",   "pick and launch a workspace"),
        ("status",  "repo, branch, session state"),
        ("resume",  "print mission brief"),
        ("doctor",  "full dependency check + install"),
        ("rice",    "terminal tools installer"),
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
            ["fzf", "--prompt", "  fob > ", "--height", "~12",
             "--border", "--no-sort", "--tabstop", "1"],
            input=fzf_input, text=True, capture_output=True,
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
    print(c("    forward operating base\n", "DIM"))

    sections = [
        ("BRIEF", [
            ("brief [profile]", "Pick or launch a workspace profile"),
            ("brief --reset-layout", "Regenerate layout from profile, discarding saved state"),
            ("attach",            "Re-attach to the fob Zellij session"),
            ("init    [repo]",    "Initialize .fob/ state files in repo"),
            ("resume",            "Print Claude resume context from .fob/"),
            ("doctor",            "Check dependencies (Zellij, Claude, lazygit…)"),
        ]),
        ("OPS", [
            ("status",            "Show repo, branch, session, .fob/ state"),
            ("test",              "Run project tests"),
            ("audit",             "Run project audit"),
        ]),
        ("VIDEO FOUNDRY", [
            ("vf codex",          "Launch Codex AI workspace"),
            ("vf run",            "Run main pipeline"),
            ("vf work",           "Open workbench menu"),
            ("vf workspace",      "Spawn full gnome-terminal layout"),
        ]),
        ("TOOLS", [
            ("cheat",             "Open full cheatsheet in floating pane"),
            ("rice",              "Terminal ricing guide & tool installer"),
            ("install",           "Add fob to PATH via ~/.bashrc"),
        ]),
    ]

    for heading, entries in sections:
        print(c(f"  {heading}", "B"))
        for cmd, desc in entries:
            print(f"    {c(cmd, 'CYN'):<34}{c(desc, 'DIM')}")
        print()


def _load_default_profile() -> dict | None:
    from fob.profile_loader import load_profile, validate_profile
    try:
        profile = load_profile("default", PROFILES_DIR)
        errs = validate_profile(profile)
        if errs:
            return None
        return profile
    except Exception:
        return None


def _pick_profiles() -> list[str]:
    import subprocess
    from fob.session import session_exists
    from fob.launcher import FOB_SESSION

    profiles = sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))
    if not profiles:
        print(c("✗ No profiles found in config/profiles/", "RED"))
        sys.exit(1)
    if len(profiles) == 1:
        return profiles

    session_running = session_exists(FOB_SESSION)

    entries = [(name, session_running) for name in profiles]

    try:
        result = subprocess.run(["fzf", "--version"], capture_output=True)
        has_fzf = result.returncode == 0
    except FileNotFoundError:
        has_fzf = False

    if has_fzf:
        session_label = c("  (session running)", "GRN") if session_running else ""
        fzf_lines = "\n".join(f"{'● ' if session_running else '○ '}{n}" for n in profiles)
        result = subprocess.run(
            ["fzf", "--prompt", "  brief > ", "--height", "~12",
             "--border", "--ansi", "--no-sort",
             "--multi", "--bind", "tab:toggle+down",
             "--header", f"Tab to select multiple · Enter to open{session_label}"],
            input=fzf_lines, text=True, capture_output=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            sys.exit(0)
        return [line.lstrip("●○ ").strip() for line in result.stdout.strip().splitlines()]

    # Numbered menu fallback
    print()
    print(c("  SELECT PROFILES", "B", "CYN"))
    if session_running:
        print(c(f"  session '{FOB_SESSION}' is running — selected profiles open as new tabs", "GRN"))
    print(c("─" * 44, "DIM"))
    dot = c("●", "GRN") if session_running else c("○", "DIM")
    for i, name in enumerate(profiles, 1):
        print(f"  {c(str(i), 'CYN')}  {dot}  {name}")
    print()
    print(c("  Enter numbers separated by spaces (e.g. 1 2)", "DIM"))
    try:
        choice = input(c("  profiles: ", "B")).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)

    selected = []
    for token in choice.replace(",", " ").split():
        if token.isdigit() and 1 <= int(token) <= len(profiles):
            selected.append(profiles[int(token) - 1])
        elif token in profiles:
            selected.append(token)
    if not selected:
        print(c("✗ No valid selection", "RED"))
        sys.exit(1)
    return selected


def _require_zellij() -> None:
    import subprocess
    try:
        subprocess.run(["zellij", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(c("✗ Zellij not found.", "RED"))
        print(c("  Install: https://zellij.dev/documentation/installation", "DIM"))
        print(c("  Or check with: fob doctor", "DIM"))
        sys.exit(1)


# ── dispatch ──────────────────────────────────────────────────────────────────

def main() -> None:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "menu"
    args = argv[1:]

    if cmd in ("-h", "--help"):
        cmd = "help"
    if cmd == "--menu":
        cmd = "menu"

    from fob import commands

    match cmd:

        case "menu":
            show_menu(args)

        case "help":
            show_help(args)

        case "brief":
            _require_zellij()
            reset_layout = "--reset-layout" in args
            named = [a for a in args if not a.startswith("--")]
            from fob.profile_loader import load_profile, validate_profile
            from fob.launcher import launch
            from fob.bootstrap import (
                ensure_claude_md, write_bootstrap_file, ensure_zellij_serialization,
            )
            from pathlib import Path

            profile_names = named if named else _pick_profiles()
            profiles = []
            for pname in profile_names:
                try:
                    p = load_profile(pname, PROFILES_DIR)
                except FileNotFoundError as e:
                    print(c(f"✗ {e}", "RED")); sys.exit(1)
                errs = validate_profile(p)
                if errs:
                    print(c(f"✗ Profile '{pname}' validation errors:", "RED"))
                    for e in errs:
                        print(c(f"  · {e}", "DIM"))
                    sys.exit(1)
                profiles.append(p)

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

                repo_root = Path(profile["repo_root"])
                if not (repo_root / ".fob").exists():
                    print(c(f"  .fob/ not found in {profile['name']} — initializing...", "YLW"))
                    commands.cmd_init([str(repo_root)], FOB_DIR)
                write_bootstrap_file(repo_root, files=bootstrap_files, peer_roots=peer_roots or None)

                extra_files = [f for f in (bootstrap_files or [])
                               if Path(f).name not in {
                                   "standing-orders.md", "active-mission.md",
                                   "objectives.md", "mission-log.md",
                               }]
                ensure_claude_md(repo_root, FOB_DIR / "templates" / "mission",
                                 extra_files=extra_files or None)

            ensure_zellij_serialization()
            names = ", ".join(p["name"] for p in profiles)
            print(c(f"\n  Brief: {names}", "B", "CYN"))
            launch(profiles, FOB_DIR, reset_layout=reset_layout)

        case "attach":
            _require_zellij()
            from fob.launcher import attach, FOB_SESSION
            from fob.session import session_exists
            if not session_exists(FOB_SESSION):
                print(c(f"✗ No session '{FOB_SESSION}'. Run: fob brief", "RED"))
                sys.exit(1)
            attach(FOB_SESSION)

        case "init":
            commands.cmd_init(args, FOB_DIR)

        case "resume":
            commands.cmd_resume(args, _load_default_profile())

        case "status":
            commands.cmd_status(args, FOB_DIR, _load_default_profile())

        case "test":
            commands.cmd_test(args, _load_default_profile())

        case "audit":
            commands.cmd_audit(args, _load_default_profile())

        case "doctor":
            commands.cmd_doctor(args, SCRIPTS_DIR)

        case "vf":
            commands.cmd_vf(args, VF_DIR)

        case "cheat":
            commands.cmd_cheat(args, SCRIPTS_DIR)

        case "rice":
            commands.cmd_rice(args, SCRIPTS_DIR)

        case "install":
            commands.cmd_install(args, FOB_DIR)

        case _:
            print(c(f"✗ Unknown command: {cmd}", "RED"))
            print(c("  Run: fob help", "DIM"))
            sys.exit(1)


if __name__ == "__main__":
    main()
