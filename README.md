# FOB — Forward Operating Base

Personal operator console for local development. One command to enter a structured workspace where Claude drives terminal work inside a predefined layout.

## What This Is

A local-first operator hub built around:

- **Zellij** — persistent named sessions with predefined pane layouts
- **Claude Code** — running in the primary pane with reliable resume context
- **`.fob/` mission files** — explicit on-disk continuity so `--continue` means something
- **Workspace profiles** — reproducible, repo-scoped brief configurations

## Why It Exists

`fob brief` is the single entrypoint. It opens a reusable Zellij session with Claude in one pane, git in another, logs in a third, and a shell in the fourth. Claude reads local mission files at startup and knows exactly what it was working on.

## Installation

```bash
cd ~/Documents/GitHub/FOB
pip install pyyaml
./fob install
source ~/.bashrc
fob doctor
```

## First Run

```bash
fob doctor                                    # check dependencies
fob init ~/Documents/GitHub/VideoFoundry      # initialize .fob/ in target repo
nano config/profiles/default.yaml             # point profile at your repo
fob brief                                     # launch the workspace
```

## Main Commands

| Command | Description |
|---------|-------------|
| `fob brief [profile]` | Launch or attach to Zellij workspace |
| `fob attach [profile]` | Attach to existing session without recreating |
| `fob init [repo]` | Initialize `.fob/` mission files in a repo |
| `fob resume` | Print Claude mission brief from `.fob/` files |
| `fob status` | Show repo, branch, session, and `.fob/` state |
| `fob test` | Run project tests |
| `fob audit` | Run project audit |
| `fob doctor` | Check all dependencies |

## Expected User Flow

1. `fob brief` → Zellij opens with 4 panes
2. Claude pane starts with `claude --continue` — reads mission context from `.fob/`
3. Work happens in Claude pane; manual tasks in shell pane; git in lazygit pane
4. When done: Claude updates `.fob/objectives.md` and `.fob/mission-log.md`
5. Detach or close — session stays alive
6. Next session: `fob brief` → Claude resumes with full context

## Workspace Layout

```
┌─────────────────────┬──────────────┐
│                     │     git      │
│      Claude         ├──────────────┤
│      (60%)          │     logs     │
│                     ├──────────────┤
│                     │    shell     │
└─────────────────────┴──────────────┘
```

## Other Tools

```bash
fob vf codex      # VideoFoundry: launch Codex workspace
fob vf run        # VideoFoundry: run main pipeline
fob cheat         # Full command/keybinding reference (floating pane)
fob rice          # Terminal ricing guide + tool installer
```

## Adding a Profile

See [docs/profiles.md](docs/profiles.md).
