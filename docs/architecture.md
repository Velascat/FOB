# Architecture

## Overview

```
fob (shell wrapper)
└── src/fob/cli.py              ← main dispatcher + repo discovery + profile picker
    ├── profile_loader.py       ← YAML profile loading + validation
    ├── launcher.py             ← Zellij session creation / tab management
    ├── demo.py                 ← end-to-end platform validation flow
    ├── providers.py            ← provider dashboard helper + free-provider guide
    ├── layout.py               ← layout persistence (save/load/show/reset)
    ├── tab_capture.py          ← live Zellij layout capture (dump-layout + KDL extraction)
    ├── session_group.py        ← session group persistence (save/load last group for fob restore)
    ├── session.py              ← Zellij session state queries
    ├── guardrails.py           ← branch detection + warnings
    ├── bootstrap.py            ← Claude mission brief generation + session wrapper scripts
    └── commands.py             ← all helper command implementations
```

## Entry Point

Running `fob` (no subcommand) is equivalent to `fob brief`. The shell wrapper (`fob`) runs first:

1. Check for `.venv/bin/python3` — if absent, run `bootstrap.sh` automatically (first run only)
2. Set `PYTHONPATH` to `src/`
3. Exec `python3 -m fob.cli` with any arguments

`fob brief` is preserved as an explicit alias; both paths are identical.

## Launcher Flow

`fob` / `fob brief`:

1. Scan `~/Documents/GitHub/` for git repos; overlay any YAML profiles from `config/profiles/`
2. Group profiles (those with `group:` and no `repo_root:`) are registered separately and never shadow repo entries
3. If cwd is inside a known repo → always auto-select that repo, skip picker entirely
4. If that repo's tab is already open → `launch()` attaches without adding a duplicate tab
5. If cwd is outside all known repos (e.g. `~/Documents/GitHub/`) → single-select picker (fzf or numbered fallback)
6. `fob multi` → explicit multi-select picker (Tab to toggle); each selected repo opens as a named tab
7. Group selection is expanded to constituent profiles via `_expand_selection()`
8. For each selected repo: initialize `.fob/` if missing; if multiple repos selected, inject siblings as implicit peers in each briefing; write `.fob/.briefing`, ensure `CLAUDE.md`
9. Multi-repo layout: Claude pane starts at `~/Documents/GitHub/` instead of the individual repo root
10. Auto-save group to `~/.local/share/fob/last-session.json` (for `fob restore`)
11. Print structured brief block: `session attaching/creating (fob)`, `layout fresh/saved` (new sessions only), active mission snippet
12. Check branch via `guardrails.py` — warn if on main/master
13. If session `fob` exists → add each repo as a new named tab (skip if tab already open)
14. Otherwise → generate fresh KDL layout (or use saved layout if `--layout` flag passed), launch `zellij --session fob --new-session-with-layout <kdl>`

`fob restore`: loads `last-session.json`, resolves repo names against `_discover_repos()`, injects siblings as implicit peers (same logic as multi-select brief), regenerates briefings, then calls `launch()`.

## Python Environment

FOB uses an isolated venv at `.venv/` inside the FOB repo root. `bootstrap.sh` creates it and installs `PyYAML` from `requirements.txt`. The `fob` wrapper triggers this automatically on first run — no manual setup step required.

## Zellij Session Model

FOB uses a **single named session**: `fob`. Each project opens as a **named tab** within that session.

- Tab bar and status bar are present in every tab via explicit chrome panes in each layout
- Running `fob` from inside the session adds tabs without re-attaching
- Dead (EXITED) sessions are auto-deleted before creating a new one
- `fob kill` terminates the session and all panes (with confirmation prompt); `tput reset` is run afterwards to clear any stale terminal state

Layout files:
- Session start: `/tmp/fob-session.kdl` — includes `default_tab_template` + named first tab
- New tabs: `/tmp/fob-tab-<name>.kdl` — panes + explicit chrome

Pane arrangement — **single repo**:
- **Left 28%**: Git (`lazygit`) top + ControlPlane status (bottom 25%)
- **Center**: Claude (`claude --resume <id>`) top + Shell (`bash`) bottom 15% — horizontal split
- **Right 28%**: Logs (`tail -f .fob/runtime.log`)

Pane arrangement — **multi repo** (single tab):
- **Left 28%**: stacked lazygits (all repos)
- **Center**: Claude only — starts at `~/Documents/GitHub/`
- **Right 28%**: stacked shells (auto height, 75%) + ControlPlane status (bottom 25%)

Tab naming: group profiles use the group name (e.g. `platform`); ad-hoc multi-select joins all repo names (`RepoA+RepoB+RepoC`). `_multi_tab_name()` always lists all repos — no truncation.

## Profiles

Profiles live in `config/profiles/<name>.yaml`. They are **optional** — any git repo under `~/Documents/GitHub/` is auto-discovered without one.

Two profile types:

**Repo profile** — has `repo_root:`. Adds `claude.*` (bootstrap files, peer context), `panes.*` (per-pane command overrides), `helpers.*` (test/audit commands), and `status_repos` (ControlPlane status filter).

**Group profile** — has `group:` list but no `repo_root:`. Appears in picker with `▸` prefix. Selecting it expands to constituent profiles.

Git visibility: platform group profiles are tracked; all others (`*.yaml`, `*.kdl`, `*.session`) are gitignored.

See [profiles.md](profiles.md) for format reference.

## Repo Discovery

`_discover_repos()` in `cli.py`:
1. Scans `~/Documents/GitHub/` for directories containing `.git/`
2. Builds a `name → {name, repo_root}` dict (lowercase key, original-case display name)
3. Overlays configured YAML profiles: any profile whose `repo_root` matches a discovered repo replaces the auto-generated entry
4. Group profiles (no `repo_root:`) are registered under their own key and never replace repo entries

`_profile_for_cwd()` uses the same discovery to find which profile's `repo_root` contains the current directory — used by `fob status`, `fob resume`, `fob test`, and `fob audit`.

## Claude Session Tracking

`get_claude_command()` in `bootstrap.py` generates a per-profile shell wrapper script written to `/tmp/fob-claude-<name>.sh`. The wrapper:

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

`fob save [name]` (in `commands.py`) calls these to capture the live layout and write it to `config/profiles/<name>.kdl`. On the next `fob brief`, `_saved_panes_kdl()` in `launcher.py` checks for this file and uses it instead of generating from YAML.

## Layout Persistence

Two separate systems:

**Live capture** (`config/profiles/<name>.kdl`):
- Captures actual live pane arrangement via `zellij action dump-layout`
- Gitignored; profile-scoped
- Used automatically on next `fob brief`
- `fob save` / `fob save --reset`

**KDL-based restore** (`.fob/layout.kdl` + `.fob/layout.json`):
- Saves the YAML-generated layout for session-level restore
- `layout.py` provides `save`, `load`, `load_any`, `reset`
- `fob brief` always generates fresh layout; `fob brief --layout` is the explicit opt-in
- `fob layout load` starts Zellij directly with the saved KDL

## Two-Layer Continuity Model

FOB uses a two-layer model for Claude context:

**Layer 1 — Human-editable source files** (edit these directly):

| File | Role |
|------|------|
| `active-mission.md` | Current objective — singular, concise, replace when focus changes |
| `standing-orders.md` | Stable repo policy — branch rules, operating constraints, low-churn |
| `objectives.md` | Work inventory — in-progress, up-next, done |
| `mission-log.md` | Chronological log — decisions, stop points, what changed and why |

**Layer 2 — Compiled launch artifact** (generated, do not edit):

| File | Role |
|------|------|
| `.briefing` | Compiled startup context — all four files + runtime context, regenerated each launch |

`fob init` creates the source files from `templates/mission/` if missing. `fob` auto-inits on first launch.

`CLAUDE.md` in the repo root tells Claude to read `.fob/.briefing` as the primary startup context.

## Briefing Generation

`bootstrap.py` reads the four source files and compiles `.fob/.briefing` at launch time. The briefing includes:

- Active Mission, Standing Orders, Objectives, Mission Log (from source files)
- Runtime context: repo name, repo root, current branch, timestamp, profile name
- Peer sections if `claude.peers` is configured

The briefing is regenerated fresh on every `fob brief` run — it is always current.

`fob resume` prints the compiled briefing to stdout so the operator can inspect what Claude will see.

## State Boundaries

FOB state is distributed across five distinct layers:

| Layer | What persists | Location |
|-------|--------------|----------|
| Zellij | Session name, tabs, live pane processes | Zellij session manager |
| `.fob/` | Mission files, layout files, compiled briefing | `<repo>/.fob/` (gitignored) |
| CLI config | Profile YAML (platform group tracked) | `config/profiles/*.yaml` |
| Private config | Saved live layouts, Claude session IDs | `config/profiles/*.kdl`, `*.session` (gitignored) |
| Global state | Last session group (for `fob restore`) | `~/.local/share/fob/last-session.json` |

These layers are independent. Resetting one does not affect the others. `fob reset` scopes resets explicitly:
- `--session` → kills Zellij session only
- `--layout` → deletes `.fob/layout.json` + `.fob/layout.kdl` only
- `--state` → deletes the four mission source files only
- bare `fob reset` → all three (with confirmation)

## Visibility Commands

`fob status` — shows session (running/stopped, attached/detached), layout (saved/none, metadata), branch, profile, and `.fob/` file presence. Active mission snippet is shown if the file exists.

`fob map` — structured full-state snapshot. Includes repo info, session state, layout metadata, and mission file presence. `--json` flag emits machine-readable JSON for tooling/piping.

## Platform Validation Commands

FOB also owns operator-facing validation commands for the shared platform:

- `fob demo` — the golden-path architecture check: preflight, stack health, SwitchBoard route selection, and ControlPlane handoff
- `fob demo --no-start` — same validation but assumes the stack is already up
- `fob providers` — reports selector and lane readiness
- `fob providers --wait` — polls until the selector is healthy and then points the operator back to the demo flow

These are operator UX commands. They do not move infrastructure ownership out of WorkStation.

## Dev Toolchain

`fob loadout` runs `tools/loadout.sh` — an interactive installer for the recommended dev toolchain (fzf, bat, eza, ripgrep, fd, zoxide, delta, lazygit, starship, fastfetch). Tools not available in Ubuntu's standard apt repos (eza, git-delta, fastfetch) use custom GitHub release installers.

`fob doctor` checks both core FOB dependencies and all loadout tools, with install status for each.
