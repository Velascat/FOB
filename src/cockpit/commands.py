"""Helper command implementations."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

from cockpit.session import list_sessions
from cockpit.guardrails import get_branch, PROTECTED_BRANCHES
from cockpit.bootstrap import build_resume_prompt, write_bootstrap_file

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

def cmd_init(args: list[str], utility_dir: Path) -> None:
    repo_root = Path(args[0]) if args else Path.cwd()
    templates_dir = utility_dir / "templates" / "claude"
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

    from cockpit.bootstrap import ensure_claude_md
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

def cmd_status(args: list[str], utility_dir: Path, default_profile: dict | None) -> None:
    cwd = Path.cwd()
    repo_root = Path(default_profile["repo_root"]) if default_profile else cwd

    branch = get_branch(repo_root)
    branch_disp = branch or c("(not a git repo)", "DIM")
    if branch in PROTECTED_BRANCHES:
        branch_disp = c(f"{branch}  ⚠ protected", "YLW", "B")

    sessions = list_sessions()
    session_disp = ", ".join(sessions) if sessions else c("none", "DIM")

    profile_name = default_profile.get("name", "—") if default_profile else c("none loaded", "DIM")
    session_name = default_profile.get("session_name", "—") if default_profile else "—"

    print(hr())
    print(c("  STATUS", "B", "CYN"))
    print(hr())
    print(f"  {c('cwd         ', 'DIM')} {cwd}")
    print(f"  {c('repo        ', 'DIM')} {repo_root}")
    print(f"  {c('branch      ', 'DIM')} {branch_disp}")
    print(f"  {c('profile     ', 'DIM')} {profile_name}  →  session: {session_name}")
    print(f"  {c('zellij      ', 'DIM')} {session_disp}")
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
    ("zellij", "Terminal workspace manager — https://zellij.dev"),
    ("claude", "Claude Code CLI — https://claude.ai/code"),
    ("lazygit", "Git TUI — brew install lazygit / apt install lazygit"),
    ("git", "Version control"),
    ("python3", "Python 3.x runtime"),
    ("tmux", "Fallback terminal multiplexer"),
    ("fzf", "Fuzzy finder"),
]


def cmd_doctor(args: list[str]) -> None:
    print()
    print(c("  DEPENDENCY CHECK", "B", "CYN"))
    print(hr())
    all_ok = True
    for binary, desc in DEPS:
        found = _which(binary)
        if found:
            print(f"  {c('✓', 'GRN')} {c(binary, 'B'):<20}  {c(found, 'DIM')}")
        else:
            all_ok = False
            print(f"  {c('✗', 'YLW')} {c(binary, 'B'):<20}  {c('not found', 'DIM')}  ←  {desc}")
    print()
    if all_ok:
        print(c("  All dependencies found.", "GRN"))
    else:
        print(c("  Install missing tools, then re-run: fob doctor", "YLW"))
    print()


def _which(binary: str) -> str | None:
    try:
        r = subprocess.run(["which", binary], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
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


# ── dump ──────────────────────────────────────────────────────────────────────

def cmd_dump(args: list[str], scripts_dir: Path) -> None:
    target = args[0] if args else "."
    target_abs = str(Path(target).resolve())
    print(c(f"▶ Dumping: {target_abs}", "CYN"))
    os.execvp("bash", ["bash", str(scripts_dir / "dump_it.sh"), target_abs])


def cmd_rice(args: list[str], scripts_dir: Path) -> None:
    script = scripts_dir / "rice.sh"
    os.execvp("bash", ["bash", str(script)] + args)


# ── install ───────────────────────────────────────────────────────────────────

def cmd_install(args: list[str], utility_dir: Path) -> None:
    rc = Path.home() / ".bashrc"
    line = f'export PATH="{utility_dir}:$PATH"'
    path_entries = os.environ.get("PATH", "").split(":")
    if str(utility_dir) in path_entries:
        print(c("✓ Already in PATH", "GRN"))
        return
    with rc.open("a") as f:
        f.write(f"\n# dev CLI\n{line}\n")
    print(c("✓ Added to PATH in ~/.bashrc", "GRN"))
    print(c(f"  Run: source ~/.bashrc", "DIM"))
