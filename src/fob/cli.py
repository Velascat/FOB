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


def show_help(_: list[str]) -> None:
    print(c(BANNER, "CYN", "B"))
    print(c("    forward operating base\n", "DIM"))

    sections = [
        ("BRIEF", [
            ("brief [profile]", "Launch Zellij workspace           (default: default)"),
            ("brief --reset-layout", "Regenerate layout from profile, discarding saved state"),
            ("attach  [profile]", "Attach to existing Zellij session"),
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
    cmd = argv[0] if argv else "help"
    args = argv[1:]

    if cmd in ("-h", "--help"):
        cmd = "help"

    from fob import commands

    match cmd:

        case "help":
            show_help(args)

        case "brief":
            _require_zellij()
            profile_name = args[0] if args else "default"
            reset_layout = "--reset-layout" in args
            from fob.profile_loader import load_profile, validate_profile
            from fob.launcher import launch
            from fob.bootstrap import (
                ensure_claude_md, write_bootstrap_file, ensure_zellij_serialization,
            )
            from pathlib import Path
            try:
                profile = load_profile(profile_name, PROFILES_DIR)
            except FileNotFoundError as e:
                print(c(f"✗ {e}", "RED")); sys.exit(1)
            errs = validate_profile(profile)
            if errs:
                print(c("✗ Profile validation errors:", "RED"))
                for e in errs:
                    print(c(f"  · {e}", "DIM"))
                sys.exit(1)

            # Resolve bootstrap_files and peer repos from profile
            claude_cfg = profile.get("claude", {})
            bootstrap_files = claude_cfg.get("bootstrap_files") or None
            peer_roots: list[tuple[str, Path]] = []
            for peer_name in claude_cfg.get("peers", []):
                try:
                    peer = load_profile(peer_name, PROFILES_DIR)
                    peer_roots.append((peer["name"], Path(peer["repo_root"])))
                except Exception:
                    print(c(f"  ⚠ peer profile '{peer_name}' not found — skipping", "YLW"))

            # Init .fob/ if missing, then write mission brief
            repo_root = Path(profile["repo_root"])
            if not (repo_root / ".fob").exists():
                print(c("  .fob/ not found — initializing...", "YLW"))
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
            print(c(f"\n  Brief: {profile['name']}", "B", "CYN"))
            launch(profile, FOB_DIR, reset_layout=reset_layout)

        case "attach":
            _require_zellij()
            profile_name = args[0] if args else "default"
            from fob.profile_loader import load_profile
            from fob.launcher import attach
            from fob.session import session_exists
            try:
                profile = load_profile(profile_name, PROFILES_DIR)
            except FileNotFoundError as e:
                print(c(f"✗ {e}", "RED")); sys.exit(1)
            sn = profile["session_name"]
            if not session_exists(sn):
                print(c(f"✗ No session named '{sn}'. Run: fob brief {profile_name}", "RED"))
                sys.exit(1)
            attach(sn)

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
