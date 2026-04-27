"""Generate Claude context from repo-local .console/ state files."""
from __future__ import annotations
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# Ordered sections in the context — label maps to filename
CONTEXT_SECTIONS = [
    ("task.md",   "Task"),
    ("guidelines.md",    "Guidelines"),
    ("backlog.md",    "Backlog"),
    ("log.md",   "Log"),
]

# Files pulled from peer repos (guidelines are repo-specific, skip them)
PEER_FILES = [
    ("task.md", "Task"),
    ("backlog.md",  "Backlog"),
]


def _get_branch(repo_root: Path) -> str:
    try:
        import subprocess
        r = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def build_resume_prompt(
    repo_root: Path,
    files: list[str] | None = None,
    peer_roots: list[tuple[str, Path]] | None = None,
    profile_name: str | None = None,
) -> str:
    console_dir = repo_root / ".console"
    sections: list[str] = []

    if files:
        files_to_read = [(Path(f).name, Path(f).name.replace(".md", "").replace("-", " ").title())
                         for f in files]
    else:
        files_to_read = list(CONTEXT_SECTIONS)

    for filename, label in files_to_read:
        path = console_dir / filename
        if path.exists():
            content = path.read_text().strip()
            if content:
                sections.append(f"## {label}\n\n{content}")

    if peer_roots:
        for peer_name, peer_root in peer_roots:
            peer_console = peer_root / ".console"
            for filename, label in PEER_FILES:
                path = peer_console / filename
                if path.exists():
                    content = path.read_text().strip()
                    if content:
                        sections.append(f"## Peer: {peer_name} — {label}\n\n{content}")

    if not sections:
        return (
            "No .console/ context files found.\n"
            "Run: console init  to initialize context files for this repo."
        )

    repo_root = repo_root.resolve()
    branch = _get_branch(repo_root)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    profile_str = f" · Profile: {profile_name}" if profile_name else ""

    runtime = (
        f"## Runtime Context\n\n"
        f"- **Repo**: {repo_root.name}\n"
        f"- **Repo root**: `{repo_root}`\n"
        f"- **Branch**: `{branch}`\n"
        f"- **Generated**: {timestamp}{profile_str}\n"
    )
    sections.append(runtime)

    header = (
        f"# OperatorConsole Context — {repo_root.name}\n\n"
        f"_Generated {timestamp} · Branch: {branch}{profile_str}_\n\n"
        "This is your compiled startup context. Read it before acting.\n"
        "The source files in `.console/` are the editable truth — this file is generated.\n\n"
        "---\n\n"
    )
    return header + "\n\n---\n\n".join(sections)


def write_bootstrap_file(
    repo_root: Path,
    files: list[str] | None = None,
    peer_roots: list[tuple[str, Path]] | None = None,
    profile_name: str | None = None,
) -> Path:
    prompt = build_resume_prompt(repo_root, files, peer_roots, profile_name)
    out = repo_root / ".console" / ".context"
    out.write_text(prompt)
    return out


def get_claude_command(
    profile: dict,
    repo_root: Path,
    console_dir: Path | None = None,
    session_key: str | None = None,
    claude_cwd: Path | None = None,
) -> str:
    """Return a shell command string that launches Claude with session resume support.

    Generates a wrapper script in /tmp that:
      1. Reads the saved session ID (config/profiles/<key>.session)
      2. Runs `claude --resume <id>` or fresh Claude if none saved
      3. After exit, saves the newest session ID for this project
    """
    import tempfile

    if console_dir is None:
        return "claude"

    key = (session_key or profile.get("name", "unknown")).lower()
    cwd = claude_cwd or repo_root

    session_file = console_dir / "config" / "profiles" / f"{key}.session"

    # Derive the Claude project dir from the cwd (mirrors Claude's own convention)
    project_key = str(cwd.resolve()).lstrip("/").replace("/", "-")
    project_dir = Path.home() / ".claude" / "projects" / f"-{project_key}"

    sf = str(session_file).replace("'", "'\\''")
    pd = str(project_dir).replace("'", "'\\''")

    script = (
        "#!/usr/bin/env bash\n"
        f"SESSION_FILE='{sf}'\n"
        f"PROJECT_DIR='{pd}'\n"
        "_save_session() {\n"
        "    newest=$(ls -t \"$PROJECT_DIR\"/*.jsonl 2>/dev/null | head -1)\n"
        "    [ -n \"$newest\" ] && basename \"$newest\" .jsonl > \"$SESSION_FILE\" || true\n"
        "}\n"
        "_save_session\n"
        "if [ -f \"$SESSION_FILE\" ]; then\n"
        "    claude --resume \"$(cat \"$SESSION_FILE\")\" || claude\n"
        "else\n"
        "    claude\n"
        "fi\n"
        "_save_session\n"
        "exec bash -l\n"
    )

    script_path = Path(tempfile.gettempdir()) / f"console-claude-{key}.sh"
    script_path.write_text(script)
    script_path.chmod(0o755)

    safe_path = str(script_path).replace("'", "'\\''")
    return f"bash '{safe_path}'"


def get_codex_command(
    profile: dict,
    repo_root: Path,
    console_dir: Path | None = None,
    session_key: str | None = None,
) -> str:
    """Return a shell command string that launches Codex CLI, or a usable shell if not installed.

    Single-repo (session_key is None): uses `codex resume --last` so codex's own cwd
    filter picks the right session — avoids cross-profile UUID contamination.

    Multi-repo (session_key provided): file-based UUID keyed by tab name, because all
    profiles share the same cwd (~/Documents/GitHub) and codex can't distinguish them.
    """
    import tempfile

    codex_cfg    = profile.get("codex", {})
    codex_bin    = codex_cfg.get("bin", "codex")
    safe_bin     = codex_bin.replace("'", "'\\''")
    # Default to --full-auto (sandboxed, no per-command approval prompts).
    # Override per-profile with codex.approval_mode: "" to get default behaviour.
    approval     = codex_cfg.get("approval_mode", "--full-auto")
    approval_arg = f" {approval}" if approval else ""

    not_found_block = (
        "#!/usr/bin/env bash\n"
        f"if ! command -v '{safe_bin}' &>/dev/null; then\n"
        "  echo 'codex CLI not found.'\n"
        "  echo 'Install: npm install -g @openai/codex'\n"
        "  exec bash -l\n"
        "fi\n"
    )

    if session_key is None:
        # Single-repo: let codex filter by cwd natively
        script = (
            not_found_block
            + f"'{safe_bin}'{approval_arg} resume --last 2>/dev/null || '{safe_bin}'{approval_arg}\n"
            + "exec bash -l\n"
        )
        key = profile.get("name", "unknown").lower()
    else:
        # Multi-repo: file-based UUID keyed by tab name
        key = session_key.lower()
        if console_dir is not None:
            session_file = console_dir / "config" / "profiles" / f"{key}.codex-session"
            sf = str(session_file).replace("'", "'\\''")
            _codex_save = (
                "newest=$(find ~/.codex/sessions -name 'rollout-*.jsonl' 2>/dev/null"
                + " | sort -r | head -1)\n"
                + "[ -n \"$newest\" ] && basename \"$newest\" .jsonl"
                + " | grep -oE '[0-9a-f-]{36}$' > \"$SESSION_FILE\" || true\n"
            )
            script = (
                not_found_block
                + f"SESSION_FILE='{sf}'\n"
                # Refresh session file at launch — catches missed saves from abrupt shutdown
                + _codex_save
                + "if [ -f \"$SESSION_FILE\" ]; then\n"
                + f"    '{safe_bin}'{approval_arg} resume \"$(cat \"$SESSION_FILE\")\" || '{safe_bin}'{approval_arg}\n"
                + "else\n"
                + f"    '{safe_bin}'{approval_arg}\n"
                + "fi\n"
                # Save again after clean exit
                + _codex_save
                + "exec bash -l\n"
            )
        else:
            script = (
                not_found_block
                + f"'{safe_bin}'{approval_arg}\n"
                + "exec bash -l\n"
            )

    script_path = Path(tempfile.gettempdir()) / f"console-codex-{key}.sh"
    script_path.write_text(script)
    script_path.chmod(0o755)

    safe_path = str(script_path).replace("'", "'\\''")
    return f"bash '{safe_path}'"


# TODO: OperatorConsole's own profile (config/profiles/operator_console.yaml) still uses Claude.
# Switch it to `tool: aider` once SwitchBoard integration is validated end-to-end.
def get_aider_command(
    profile: dict,
    repo_root: Path,
    console_dir: Path | None = None,
    session_key: str | None = None,
) -> str:
    """Return a shell command string for the retired SwitchBoard+Aider flow."""
    import tempfile

    script = (
        "#!/usr/bin/env bash\n"
        "echo 'ERROR: SwitchBoard no longer ships the legacy OpenAI-compatible Aider bridge.'\n"
        "echo 'Use the canonical lane-based SwitchBoard flow or a direct local Aider setup instead.'\n"
        "exec bash -l\n"
    )

    key = (session_key or profile.get("name", "unknown")).lower()
    script_path = Path(tempfile.gettempdir()) / f"console-aider-{key}.sh"
    script_path.write_text(script)
    script_path.chmod(0o755)

    safe_path = str(script_path).replace("'", "'\\''")
    return f"bash '{safe_path}'"


def ensure_claude_md(
    repo_root: Path,
    templates_dir: Path,
    extra_files: list[str] | None = None,
) -> None:
    claude_md = repo_root / "CLAUDE.md"
    marker = "<!-- console-context -->"

    extra_lines = ""
    if extra_files:
        standard = {"guidelines.md", "task.md", "backlog.md", "log.md"}
        extras = [Path(f).name for f in extra_files if Path(f).name not in standard]
        if extras:
            extra_lines = "\nAdditional context files also compiled into the startup context:\n" + \
                "\n".join(f"- `.console/{name}`" for name in extras) + "\n"

    block = f"""{marker}
## OperatorConsole Context

At the start of each session, read the compiled context before acting:

- `.console/.context` — compiled startup context (generated fresh each launch)

The context file contains your current task, guidelines, backlog, log, and runtime context.
{extra_lines}
**Source files** (editable truth — update these, not the context file):

| File | Role |
|------|------|
| `.console/task.md` | Current objective and definition of done |
| `.console/guidelines.md` | Repo policy, branch rules, operating constraints |
| `.console/backlog.md` | Work inventory — in-progress, up-next, done |
| `.console/log.md` | Recent decisions, stop points, what changed and why |

After meaningful progress, update `.console/backlog.md` and `.console/log.md`.
Do not edit `.console/.context` directly — it is regenerated at each launch.
"""
    if claude_md.exists():
        existing = claude_md.read_text()
        if marker in existing:
            # Replace existing console block
            import re
            new_text = re.sub(
                r"<!-- console-context -->.*",
                block.strip(),
                existing,
                flags=re.DOTALL,
            )
            claude_md.write_text(new_text.rstrip() + "\n")
        else:
            claude_md.write_text(existing.rstrip() + "\n\n" + block + "\n")
    else:
        claude_md.write_text(block + "\n")


# ── CLI update helpers ────────────────────────────────────────────────────────

_UPDATE_LOG = Path("/tmp/console-cli-update.log")

_CLI_UPDATES: list[tuple[str, list[str]]] = [
    ("claude",  ["claude", "update"]),
    ("codex",   ["npm", "install", "-g", "@openai/codex"]),
    ("aider",   ["pipx", "upgrade", "aider-chat"]),
]


def update_clis(*, verbose: bool = False) -> dict[str, str]:
    """Run update commands for claude, codex, and aider. Returns {name: status}."""
    results: dict[str, str] = {}
    for name, cmd in _CLI_UPDATES:
        bin_name = cmd[0]
        if not shutil.which(bin_name):
            results[name] = "skipped (not found)"
            continue
        try:
            r = subprocess.run(cmd, capture_output=not verbose, text=True, timeout=120)
            results[name] = "ok" if r.returncode == 0 else f"failed (exit {r.returncode})"
        except subprocess.TimeoutExpired:
            results[name] = "timeout"
        except Exception as exc:
            results[name] = f"error: {exc}"
    return results


def spawn_update_clis_background() -> None:
    """Fire-and-forget background CLI update; output goes to /tmp/console-cli-update.log."""
    import sys
    log = _UPDATE_LOG.open("w")
    try:
        subprocess.Popen(
            [sys.executable, "-c",
             "from operator_console.bootstrap import update_clis; r = update_clis(); "
             "[print(f'{k}: {v}') for k,v in r.items()]"],
            stdout=log, stderr=log,
            start_new_session=True,
        )
    except Exception:
        pass
