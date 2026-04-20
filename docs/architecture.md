# Architecture

## Overview

```
fob (shell wrapper)
└── src/fob/cli.py              ← main dispatcher + repo discovery + profile picker
    ├── profile_loader.py       ← YAML profile loading + validation
    ├── launcher.py             ← Zellij session creation / tab management
    ├── session.py              ← Zellij session state queries
    ├── guardrails.py           ← branch detection + warnings
    ├── bootstrap.py            ← Claude mission brief generation
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
2. If outside Zellij and cwd is inside a known repo → auto-select that repo, skip picker
3. Otherwise show interactive picker (fzf or numbered fallback menu); Tab to multi-select
4. For each selected repo: initialize `.fob/` if missing, write `.fob/.briefing`, ensure `CLAUDE.md`
5. Ensure Zellij serialization is enabled in `~/.config/zellij/config.kdl`
6. Check branch via `guardrails.py` — warn if on main/master
7. If session `fob` exists → add each repo as a new named tab (skip if tab already open)
8. Otherwise → generate KDL layout, launch `zellij --session fob --new-session-with-layout <kdl>`

## Python Environment

FOB uses an isolated venv at `.venv/` inside the FOB repo root. `bootstrap.sh` creates it and installs `PyYAML` from `requirements.txt`. The `fob` wrapper triggers this automatically on first run — no manual setup step required.

## Zellij Session Model

FOB uses a **single named session**: `fob`. Each project opens as a **named tab** within that session.

- Session survives terminal close, SSH disconnects, and reboots (Zellij serialization)
- Tab bar and status bar are present in every tab via explicit chrome panes in each layout
- Running `fob` from inside the session adds tabs without re-attaching
- Dead (EXITED) sessions are auto-deleted before creating a new one
- `fob exit` kills the session and all panes

Layout files:
- Session start: `/tmp/fob-session.kdl` — includes `default_tab_template` + named first tab + floating cheat pane; saved to `.fob/layout-state.kdl`
- New tabs: `/tmp/fob-tab-<name>.kdl` — panes + explicit chrome + floating cheat pane
- `fob brief --reset-layout` or `fob clear` regenerates from defaults, ignoring saved state

Pane arrangement per tab:
- **Left 35% stacked**: Git (`lazygit`), Logs (`tail -f .fob/runtime.log`), Shell (`bash`) — focused pane expands, others collapse to title strip
- **Right 65%**: Claude pane (`claude --continue`)
- **Floating**: Cheat sheet pane (toggle with Ctrl+p f)

## Profiles

Profiles live in `config/profiles/<name>.yaml`. They are **optional** — any git repo under `~/Documents/GitHub/` is auto-discovered without one.

A profile adds:
- `claude.*` — bootstrap files, peer context, continue flag
- `panes.*` — per-pane command overrides
- `helpers.*` — commands for `fob test`, `fob audit`

Auto-discovered repos that have a matching YAML profile (by `repo_root`) use the profile config. Others get sensible defaults.

See [profiles.md](profiles.md) for format reference.

## Repo Discovery

`_discover_repos()` in `cli.py`:
1. Scans `~/Documents/GitHub/` for directories containing `.git/`
2. Builds a `name → {name, repo_root}` dict (lowercase key, original-case display name)
3. Overlays configured YAML profiles: any profile whose `repo_root` matches a discovered repo replaces the auto-generated entry

`_profile_for_cwd()` uses the same discovery to find which profile's `repo_root` contains the current directory — used by `fob status`, `fob resume`, `fob test`, and `fob audit`.

## Mission Files

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

## Dev Toolchain

`fob loadout` runs `tools/loadout.sh` — an interactive installer for the recommended dev toolchain (fzf, bat, eza, ripgrep, fd, zoxide, delta, lazygit, starship, fastfetch). Tools not available in Ubuntu's standard apt repos (eza, git-delta, fastfetch) use custom GitHub release installers.

`fob doctor` checks both core FOB dependencies and all loadout tools, with install status for each.
