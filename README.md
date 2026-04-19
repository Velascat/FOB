# FOB — Forward Operating Base

Personal operator console for local development. One command to enter a structured workspace where Claude drives terminal work inside a predefined layout.

## What This Is

A local-first operator hub built around:

- **Zellij** — single persistent session with per-project tabs, tab bar, and status bar
- **Claude Code** — running in the primary pane with reliable resume context
- **`.fob/` mission files** — explicit on-disk continuity so `--continue` means something
- **Auto-discovery** — all git repos under `~/Documents/GitHub/` appear in the picker automatically

## Why It Exists

`fob brief` is the single entrypoint. It opens (or reuses) a Zellij session named `fob`, each project as a tab. Claude reads local mission files at startup and knows exactly what it was working on.

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
fob doctor          # check and install dependencies
fob brief           # pick a repo from the interactive picker, launch workspace
```

No profile YAML required — any git repo under `~/Documents/GitHub/` appears automatically.

## Main Commands

| Command | Description |
|---------|-------------|
| `fob brief [repo]` | Pick repos from interactive picker; launch or add tabs |
| `fob brief --reset-layout` | Regenerate layout from defaults, discarding saved state |
| `fob attach` | Re-attach to the running `fob` session |
| `fob exit` | Kill the `fob` session and all panes |
| `fob init [repo]` | Initialize `.fob/` mission files in a repo |
| `fob resume` | Print Claude mission brief from `.fob/` files |
| `fob status` | Show repo, branch, session, and `.fob/` state |
| `fob test` | Run project tests |
| `fob audit` | Run project audit |
| `fob doctor` | Check and install dependencies |
| `fob cheat` | Open keybinding reference (floating pane inside Zellij) |

## Expected User Flow

1. `fob brief` → picker appears; select one or more repos (Tab to multi-select)
2. Zellij opens with a named tab per repo — tab bar and status bar always visible
3. Claude pane starts with `claude --continue` — reads mission context from `.fob/`
4. Work happens in Claude pane; manual tasks in shell pane; git in lazygit pane
5. When done: Claude updates `.fob/objectives.md` and `.fob/mission-log.md`
6. Detach or close — session stays alive; Zellij serialization survives reboots
7. Next session: `fob brief` → cwd auto-selects your repo, Claude resumes with full context

## Workspace Layout

Each tab:

```
┌─────────────────────┬──────────────┐
│                     │     git      │
│      Claude         ├──────────────┤
│      (60%)          │     logs     │
│                     ├──────────────┤
│                     │    shell     │
└─────────────────────┴──────────────┘
```

## Using Multiple Projects

`fob brief` supports multi-select (Tab key in fzf). Each selected repo opens as a separate named tab in the same Zellij session. Running `fob brief` from inside the session adds tabs without re-attaching.

## Profiles (Optional)

Repos are auto-discovered — no YAML needed for basic use. Create a profile in `config/profiles/<name>.yaml` to configure Claude context, peer repos, or custom helper commands.

See [docs/profiles.md](docs/profiles.md).

## Other Tools

```bash
fob vf codex      # VideoFoundry: launch Codex workspace
fob vf run        # VideoFoundry: run main pipeline
fob rice          # Terminal ricing guide + tool installer
```
