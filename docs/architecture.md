# Architecture

## Overview

```
console (shell wrapper)
└── src/console/cli.py              ← main dispatcher + repo discovery + profile picker
    ├── profile_loader.py       ← YAML profile loading + validation
    ├── launcher.py             ← Zellij session creation / tab management
    ├── demo.py                 ← end-to-end platform validation flow
    ├── providers.py            ← provider dashboard helper + free-provider guide
    ├── layout.py               ← layout persistence (save/load/show/reset)
    ├── tab_capture.py          ← live Zellij layout capture (dump-layout + KDL extraction)
    ├── session_group.py        ← session group persistence (save/load last group for console restore)
    ├── session.py              ← Zellij session state queries
    ├── guardrails.py           ← branch detection + warnings
    ├── bootstrap.py            ← Claude mission brief generation + session wrapper scripts
    └── commands.py             ← all helper command implementations
```

## Entry Point

Running `console` (no subcommand) is equivalent to `console open`. The shell wrapper (`console`) runs first:

1. Check for `.venv/bin/python3` — if absent, run `bootstrap.sh` automatically (first run only)
2. Set `PYTHONPATH` to `src/`
3. Exec `python3 -m operator_console.cli` with any arguments

`console open` is preserved as an explicit alias; both paths are identical.

## Launcher Flow

`console` / `console open`:

1. Scan `~/Documents/GitHub/` for git repos; overlay any YAML profiles from `config/profiles/`
2. Group profiles (those with `group:` and no `repo_root:`) are registered separately and never shadow repo entries
3. If cwd is inside a known repo → always auto-select that repo, skip picker entirely
4. If that repo's tab is already open → `launch()` attaches without adding a duplicate tab
5. If cwd is outside all known repos (e.g. `~/Documents/GitHub/`) → single-select picker (fzf or numbered fallback)
6. `console multi` → explicit multi-select picker (Tab to toggle); each selected repo opens as a named tab
7. Group selection is expanded to constituent profiles via `_expand_selection()`
8. For each selected repo: initialize `.console/` if missing; if multiple repos selected, inject siblings as implicit peers in each briefing; write `.console/.context`, ensure `CLAUDE.md`
9. Multi-repo layout: Claude pane starts at `~/Documents/GitHub/` instead of the individual repo root
10. Auto-save group to `~/.local/share/console/last-session.json` (for `console restore`)
11. Print structured summary block: `session attaching/creating (operator_console)`, `layout fresh/saved` (new sessions only), active mission snippet
12. Check branch via `guardrails.py` — warn if on main/master
13. If session `console` exists → add each repo as a new named tab (skip if tab already open)
14. Otherwise → generate fresh KDL layout (or use saved layout if `--layout` flag passed), launch `zellij --session operator_console --new-session-with-layout <kdl>`

`console restore`: loads `last-session.json`, resolves repo names against `_discover_repos()`, injects siblings as implicit peers (same logic as multi-select open), regenerates briefings, then calls `launch()`.

## Python Environment

OperatorConsole uses an isolated venv at `.venv/` inside the OperatorConsole repo root. `bootstrap.sh` creates it and installs `PyYAML` from `requirements.txt`. The `console` wrapper triggers this automatically on first run — no manual setup step required.

## Zellij Session Model

OperatorConsole uses a **single named session**: `operator_console`. Each project opens as a **named tab** within that session.

- Tab bar and status bar are present in every tab via explicit chrome panes in each layout
- Running `console` from inside the session adds tabs without re-attaching
- Dead (EXITED) sessions are auto-deleted before creating a new one
- `console kill` terminates the session and all panes (with confirmation prompt); `tput reset` is run afterwards to clear any stale terminal state

Layout files:
- Session start: `/tmp/console-session.kdl` — includes `default_tab_template` + named first tab
- New tabs: `/tmp/console-tab-<name>.kdl` — panes + explicit chrome

Pane arrangement — **single repo**:
- **Left 28%**: Git (`lazygit`) top + OperationsCenter status (bottom 25%)
- **Center**: Claude (`claude --resume <id>`) top + Shell (`bash`) bottom 15% — horizontal split
- **Right 28%**: Logs (`tail -f .console/runtime.log`)

Pane arrangement — **multi repo** (single tab):
- **Left 28%**: stacked lazygits (all repos)
- **Center**: Claude only — starts at `~/Documents/GitHub/`
- **Right 28%**: stacked shells (auto height, 75%) + OperationsCenter status (bottom 25%)

Tab naming: group profiles use the group name (e.g. `platform`); ad-hoc multi-select joins all repo names (`RepoA+RepoB+RepoC`). `_multi_tab_name()` always lists all repos — no truncation.

## Profiles

Profiles live in `config/profiles/<name>.yaml`. They are **optional** — any git repo under `~/Documents/GitHub/` is auto-discovered without one.

Two profile types:

**Repo profile** — has `repo_root:`. Adds `claude.*` (bootstrap files, peer context), `panes.*` (per-pane command overrides), `helpers.*` (test/audit commands), and `status_repos` (OperationsCenter status filter).

**Group profile** — has `group:` list but no `repo_root:`. Appears in picker with `▸` prefix. Selecting it expands to constituent profiles.

Git visibility: platform group profiles are tracked; all others (`*.yaml`, `*.kdl`, `*.session`) are gitignored.

See [profiles.md](profiles.md) for format reference.

## Repo Discovery

`_discover_repos()` in `cli.py`:
1. Scans `~/Documents/GitHub/` for directories containing `.git/`
2. Builds a `name → {name, repo_root}` dict (lowercase key, original-case display name)
3. Overlays configured YAML profiles: any profile whose `repo_root` matches a discovered repo replaces the auto-generated entry
4. Group profiles (no `repo_root:`) are registered under their own key and never replace repo entries

`_profile_for_cwd()` uses the same discovery to find which profile's `repo_root` contains the current directory — used by `console status`, `console resume`, `console test`, and `console audit`.

## Claude Session Tracking

`get_claude_command()` in `bootstrap.py` generates a per-profile shell wrapper script written to `/tmp/console-claude-<name>.sh`. The wrapper:

1. Reads `config/profiles/<name>.session` — the saved Claude conversation ID
2. Runs `claude --resume <id>` if saved, otherwise `claude` (fresh start); falls back to `claude` if the session no longer exists
3. After Claude exits, scans `~/.claude/projects/<project-path>/` for the newest `.jsonl` file and saves its stem as the new session ID

The project path is derived from the Claude working directory: `<cwd>` with `/` → `-` prefix convention (mirrors Claude Code's own storage layout).

For single-profile tabs: session key = profile name, project dir derived from `repo_root`.
For multi-profile (group) tabs: session key = `_multi_tab_name(profiles)`, project dir derived from `~/Documents/GitHub/`.

Session files (`config/profiles/*.session`) are always gitignored.

## Live Layout Capture

`tab_capture.py` provides:
- `dump_live_layout()` — runs `zellij action dump-layout`, returns KDL string
- `extract_panes_kdl(kdl, tab_name)` — extracts the inner content panes from a named tab, stripping chrome plugins (tab-bar, status-bar) and the tab wrapper; returns raw KDL ready to embed in a session or tab layout
- `focused_tab_name(kdl)` — returns the name of the focused tab from a dump

`console save [name]` (in `commands.py`) calls these to capture the live layout and write it to `config/profiles/<name>.kdl`. On the next `console open`, `_saved_panes_kdl()` in `launcher.py` checks for this file and uses it instead of generating from YAML.

## Layout Persistence

Two separate systems:

**Live capture** (`config/profiles/<name>.kdl`):
- Captures actual live pane arrangement via `zellij action dump-layout`
- Gitignored; profile-scoped
- Used automatically on next `console open`
- `console save` / `console save --reset`

**KDL-based restore** (`.console/layout.kdl` + `.console/layout.json`):
- Saves the YAML-generated layout for session-level restore
- `layout.py` provides `save`, `load`, `load_any`, `reset`
- `console open` always generates fresh layout; `console open --layout` is the explicit opt-in
- `console layout load` starts Zellij directly with the saved KDL

## Two-Layer Continuity Model

OperatorConsole uses a two-layer model for Claude context:

**Layer 1 — Human-editable source files** (edit these directly):

| File | Role |
|------|------|
| `task.md` | Current objective — singular, concise, replace when focus changes |
| `guidelines.md` | Stable repo policy — branch rules, operating constraints, low-churn |
| `backlog.md` | Work inventory — in-progress, up-next, done |
| `log.md` | Chronological log — decisions, stop points, what changed and why |

**Layer 2 — Compiled launch artifact** (generated, do not edit):

| File | Role |
|------|------|
| `.context` | Compiled startup context — all four files + runtime context, regenerated each launch |

`console init` creates the source files from `templates/mission/` if missing. `console` auto-inits on first launch.

`CLAUDE.md` in the repo root tells Claude to read `.console/.context` as the primary startup context.

## Briefing Generation

`bootstrap.py` reads the four source files and compiles `.console/.context` at launch time. The briefing includes:

- Active Mission, Standing Orders, Objectives, Mission Log (from source files)
- Runtime context: repo name, repo root, current branch, timestamp, profile name
- Peer sections if `claude.peers` is configured

The briefing is regenerated fresh on every `console open` run — it is always current.

`console context` prints the compiled briefing to stdout so the operator can inspect what Claude will see.

## State Boundaries

OperatorConsole state is distributed across five distinct layers:

| Layer | What persists | Location |
|-------|--------------|----------|
| Zellij | Session name, tabs, live pane processes | Zellij session manager |
| `.console/` | Mission files, layout files, compiled briefing | `<repo>/.console/` (gitignored) |
| CLI config | Profile YAML (platform group tracked) | `config/profiles/*.yaml` |
| Private config | Saved live layouts, Claude session IDs | `config/profiles/*.kdl`, `*.session` (gitignored) |
| Global state | Last session group (for `console restore`) | `~/.local/share/console/last-session.json` |

These layers are independent. Resetting one does not affect the others. `console reset` scopes resets explicitly:
- `--session` → kills Zellij session only
- `--layout` → deletes `.console/layout.json` + `.console/layout.kdl` only
- `--state` → deletes the four mission source files only
- bare `console reset` → all three (with confirmation)

## Visibility Commands

`console status` — shows session (running/stopped, attached/detached), layout (saved/none, metadata), branch, profile, and `.console/` file presence. Active mission snippet is shown if the file exists.

`console map` — structured full-state snapshot. Includes repo info, session state, layout metadata, and mission file presence. `--json` flag emits machine-readable JSON for tooling/piping.

## Platform Validation Commands

OperatorConsole also owns operator-facing validation commands for the shared platform:

- `console demo` — the golden-path architecture check: preflight, stack health, SwitchBoard route selection, and OperationsCenter handoff
- `console demo --no-start` — same validation but assumes the stack is already up
- `console providers` — reports selector and lane readiness
- `console providers --wait` — polls until the selector is healthy and then points the operator back to the demo flow

These are operator UX commands. They do not move infrastructure ownership out of WorkStation.

## Dev Toolchain

`console loadout` runs `tools/loadout.sh` — an interactive installer for the recommended dev toolchain (fzf, bat, eza, ripgrep, fd, zoxide, delta, lazygit, starship, fastfetch). Tools not available in Ubuntu's standard apt repos (eza, git-delta, fastfetch) use custom GitHub release installers.

`console doctor` checks both core OperatorConsole dependencies and all loadout tools, with install status for each.
