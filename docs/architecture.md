# Architecture

## Overview

```
fob (shell wrapper)
└── src/fob/cli.py              ← main dispatcher
    ├── profile_loader.py       ← YAML profile loading + validation
    ├── launcher.py             ← Zellij session creation/attachment
    ├── session.py              ← Zellij session state queries
    ├── guardrails.py           ← branch detection + warnings
    ├── bootstrap.py            ← Claude mission brief generation
    └── commands.py             ← all helper command implementations
```

## Launcher Flow

`fob brief default`:

1. Load `config/profiles/default.yaml` via `profile_loader.py`
2. Validate profile fields and `repo_root` path
3. Initialize `.fob/` files from templates if missing (`fob init`)
4. Write `.fob/.briefing` — current mission brief for Claude
5. Ensure `CLAUDE.md` in repo references `.fob/` files
6. Check branch via `guardrails.py` — warn if on main/master
7. If Zellij session exists → `zellij attach <session_name>`
8. Otherwise → generate dynamic KDL, `zellij --session <name> --new-session-with-layout <kdl>`

## Zellij Session Model

FOB uses named sessions: `brief-<profile-name>`. Sessions survive terminal close and SSH disconnects.

The dynamic layout is generated at launch time by `launcher.generate_layout()` and written to `/tmp/fob-brief-<session>.kdl`, then passed to Zellij via `--new-session-with-layout`.

Pane arrangement:
- **Left 60%**: Claude pane (`claude --continue`)
- **Top-right 34%**: Git pane (`lazygit`)
- **Mid-right 33%**: Logs pane (`tail -f .fob/runtime.log`)
- **Bottom-right**: Shell pane (`bash`)

## Profiles

Profiles live in `config/profiles/<name>.yaml`. They define:
- `repo_root` — absolute path to the target repo
- `session_name` — Zellij session name
- `panes.*` — per-pane `cwd` and `command` overrides
- `helpers.*` — commands for `fob test`, `fob audit`

See [profiles.md](profiles.md) for format reference.

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

`bootstrap.py` reads the four `.fob/` files and builds a formatted mission brief, written to `.fob/.briefing`.

At launch, this file is refreshed before Zellij starts. The Claude pane runs `claude --continue`; the Claude Code runtime reads `CLAUDE.md` which directs Claude to read the mission files.

`fob resume` prints this brief to stdout so the operator can inspect what Claude will see.
