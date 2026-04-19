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

## Launcher Flow

`fob brief`:

1. Scan `~/Documents/GitHub/` for git repos; overlay any YAML profiles from `config/profiles/`
2. If outside Zellij and cwd is inside a known repo → auto-select that repo
3. Otherwise show interactive picker (fzf or numbered menu); Tab to multi-select
4. For each selected repo: initialize `.fob/` if missing, write `.fob/.briefing`, ensure `CLAUDE.md`
5. Ensure Zellij serialization is enabled in `~/.config/zellij/config.kdl`
6. Check branch via `guardrails.py` — warn if on main/master
7. If session `fob` exists → add each repo as a new named tab (skip if tab already open)
8. Otherwise → generate KDL layout with `default_tab_template` chrome, launch `zellij --session fob --new-session-with-layout <kdl>`

## Zellij Session Model

FOB uses a **single named session**: `fob`. Each project opens as a **named tab** within that session.

- Session survives terminal close, SSH disconnects, and reboots (Zellij serialization)
- Tab bar and status bar are present in every tab via explicit chrome panes in each layout
- `fob brief` from inside the running session adds tabs without re-attaching
- Dead (EXITED) sessions are auto-deleted before creating a new one
- `fob exit` kills the session and all panes

Layout files:
- Session start: `/tmp/fob-session.kdl` — includes `default_tab_template` + named first tab; saved to `.fob/layout-state.kdl`
- New tabs: `/tmp/fob-tab-<name>.kdl` — panes + explicit chrome (tab-bar/status-bar)
- `fob brief --reset-layout` regenerates from defaults, ignoring saved state

Pane arrangement per tab:
- **Left 60%**: Claude pane (`claude --continue`)
- **Top-right 34%**: Git pane (`lazygit`)
- **Mid-right 33%**: Logs pane (`tail -f .fob/runtime.log`)
- **Bottom-right**: Shell pane (`bash`)

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
2. Builds a `name → {name, repo_root}` dict using lowercased directory names
3. Overlays configured YAML profiles: any profile whose `repo_root` matches a discovered repo replaces the auto-generated entry

## Mission Files

Each repo maintains `.fob/` with four files:

| File | Purpose |
|------|---------|
| `standing-orders.md` | Operating rules — branch policy, workflow loop, what not to do |
| `active-mission.md` | Current objective and definition of done |
| `objectives.md` | Ordered work list with in-progress / up-next / done sections |
| `mission-log.md` | Scratch continuity — decisions, blockers, notes |

`fob init` creates these from `templates/mission/` if missing.

`CLAUDE.md` in the repo root tells Claude to read these files at the start of each session.

## Bootstrap / Resume Behavior

`bootstrap.py` reads the `.fob/` files and builds a formatted mission brief written to `.fob/.briefing`.

At launch, this file is refreshed before Zellij starts. The Claude pane runs `claude --continue`; the Claude Code runtime reads `CLAUDE.md` which directs Claude to read the mission files.

`fob resume` prints this brief to stdout so the operator can inspect what Claude will see.

If `claude.peers` is set in the profile, `active-mission.md` and `objectives.md` from each peer repo are appended as `PEER: <name>` sections, giving Claude cross-repo context.
