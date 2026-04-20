"""Helper command implementations."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

from fob.session import list_sessions
from fob.guardrails import get_branch, PROTECTED_BRANCHES
from fob.bootstrap import build_resume_prompt, write_bootstrap_file

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

def cmd_init(args: list[str], fob_dir: Path) -> None:
    repo_root = Path(args[0]) if args else Path.cwd()
    templates_dir = fob_dir / "templates" / "mission"
    claude_dir = repo_root / ".fob"
    claude_dir.mkdir(exist_ok=True)

    files = ["standing-orders.md", "active-mission.md", "objectives.md", "mission-log.md"]
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

    from fob.bootstrap import ensure_claude_md
    ensure_claude_md(repo_root, templates_dir)

    print(c("Initialized .fob/ mission files", "B"))
    print(f"  Repo: {repo_root}")
    print()
    for name in created:
        print(c(f"  ✓ created  .fob/{name}", "GRN"))
    for name in skipped:
        print(c(f"  – skipped  .fob/{name}  (already exists)", "DIM"))
    print()
    print(c("  CLAUDE.md updated with context reference.", "DIM"))


# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(args: list[str], fob_dir: Path, default_profile: dict | None) -> None:
    cwd = Path.cwd()
    repo_root = Path(default_profile["repo_root"]) if default_profile else cwd

    branch = get_branch(repo_root)
    branch_disp = branch or c("(not a git repo)", "DIM")
    if branch in PROTECTED_BRANCHES:
        branch_disp = c(f"{branch}  ⚠ protected", "YLW", "B")

    from fob.launcher import FOB_SESSION
    sessions = list_sessions()
    fob_running = FOB_SESSION in sessions
    session_disp = (c(f"{FOB_SESSION}  (running)", "GRN") if fob_running
                    else c(f"{FOB_SESSION}  (stopped)", "DIM"))

    profile_name = default_profile.get("name", "—") if default_profile else c("none loaded", "DIM")

    print(hr())
    print(c("  STATUS", "B", "CYN"))
    print(hr())
    print(f"  {c('cwd         ', 'DIM')} {cwd}")
    print(f"  {c('repo        ', 'DIM')} {repo_root}")
    print(f"  {c('branch      ', 'DIM')} {branch_disp}")
    print(f"  {c('profile     ', 'DIM')} {profile_name}")
    print(f"  {c('session     ', 'DIM')} {session_disp}")
    print()

    claude_dir = repo_root / ".fob"
    if claude_dir.exists():
        print(f"  {c('.fob/    ', 'DIM')}")
        for name in ["standing-orders.md", "active-mission.md", "objectives.md", "mission-log.md"]:
            p = claude_dir / name
            status = c("✓", "GRN") if p.exists() else c("✗", "DIM")
            print(f"    {status}  {name}")
    else:
        print(c("  ✗  .fob/ not initialized — run: fob init", "YLW"))
    print()
    print(f"  {c('HELPERS', 'B')}")
    helpers = [
        ("fob brief", "launch Zellij workspace"),
        ("fob resume", "print Claude resume context"),
        ("fob status", "this view"),
        ("fob test", "run project tests"),
        ("fob audit", "run project audit"),
        ("fob doctor", "check dependencies"),
    ]
    for cmd, desc in helpers:
        print(f"    {c(cmd, 'CYN')}  {c(desc, 'DIM')}")
    print()


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
    if (repo_root / ".fob").exists():
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
    ("zellij",  ["zellij"],          "Terminal workspace manager — https://zellij.dev"),
    ("claude",  ["claude"],           "Claude Code CLI — https://claude.ai/code"),
    ("gitcomet", ["gitcomet"],         "Git UI — github.com/Auto-Explore/GitComet"),
    ("git",     ["git"],              "Version control"),
    ("python3", ["python3"],          "Python 3.x runtime"),
    ("fzf",     ["fzf"],              "Fuzzy finder"),
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
    ("gitcomet",  ["gitcomet"],          "Fast git UI — stage, commit, diff, log"),
    ("btop",      ["btop"],             "System monitor"),
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
        print(c(f"  {len(installable)} tool(s) missing — fob loadout can install them", "YLW"))
        try:
            answer = input(c("  Install now? [y/N] ", "B"))
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() == "y":
            os.execvp("bash", ["bash", str(scripts_dir / "loadout.sh"), "install"])
        else:
            print(c("  Run: fob loadout  to install when ready", "DIM"))
    elif installable:
        print(c("  Run: fob loadout  to install missing tools", "YLW"))
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


# ── vf ────────────────────────────────────────────────────────────────────────

def cmd_vf(args: list[str], vf_dir: Path) -> None:
    sub = args[0] if args else "help"
    rest = args[1:]

    cmds = {
        "codex": ("bash", str(vf_dir / "tools" / "codex-helper.sh")),
        "run": ("bash", str(vf_dir / "run-main.sh")),
        "work": ("bash", str(vf_dir / "tools" / "open-workbench.sh"), "--menu"),
        "workspace": ("bash", str(vf_dir / "open-codex-workflow.sh")),
    }

    if sub not in cmds:
        print(f"  {c('vf codex', 'CYN')}  /  {c('vf run', 'CYN')}  /  {c('vf work', 'CYN')}  /  {c('vf workspace', 'CYN')}")
        return

    cmd_parts = list(cmds[sub]) + list(rest)
    print(c(f"▶ VideoFoundry: vf {sub}", "CYN"))
    os.chdir(vf_dir)
    os.execvp(cmd_parts[0], cmd_parts)


def cmd_exit(args: list[str]) -> None:
    from fob.launcher import FOB_SESSION
    from fob.session import session_exists
    if not session_exists(FOB_SESSION):
        print(c(f"  No active session '{FOB_SESSION}'", "DIM"))
        return
    print(c(f"  Killing session '{FOB_SESSION}' and all panes...", "YLW"))
    os.execvp("zellij", ["zellij", "kill-session", FOB_SESSION])


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


# ── clear ────────────────────────────────────────────────────────────────────

def cmd_clear(args: list[str], default_profile: dict | None) -> None:
    clear_all = "--all" in args
    if clear_all:
        github_dir = Path.home() / "Documents" / "GitHub"
        targets = list(github_dir.glob("*/.fob/layout-state.kdl")) if github_dir.exists() else []
        if not targets:
            print(c("  No saved layouts found.", "DIM"))
            return
        for f in targets:
            f.unlink()
            print(c(f"  ✓ cleared  {f}", "GRN"))
        print()
        print(c(f"  {len(targets)} layout(s) cleared.", "B"))
    else:
        repo_root = Path(default_profile["repo_root"]) if default_profile else Path.cwd()
        saved = repo_root / ".fob" / "layout-state.kdl"
        if saved.exists():
            saved.unlink()
            print(c(f"  ✓ cleared  {saved}", "GRN"))
        else:
            print(c(f"  No saved layout for {repo_root.name}", "DIM"))


# ── install ───────────────────────────────────────────────────────────────────

def cmd_install(args: list[str], fob_dir: Path) -> None:
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)

    src = fob_dir / "fob"
    link = local_bin / "fob"

    if link.exists() or link.is_symlink():
        if link.is_symlink() and link.resolve() == src.resolve():
            print(c("✓ fob already installed", "GRN"))
            print(c(f"  {link} → {src}", "DIM"))
            return
        link.unlink()

    link.symlink_to(src)
    print(c("✓ Installed fob", "GRN"))
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
