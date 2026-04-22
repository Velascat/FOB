# FOB — Forward Operating Base

A persistent, repo-scoped operator workspace for Claude-driven development. Run `fob` from any repo — it attaches to your existing session or creates a new one, and Claude resumes exactly where you left off.

## What FOB Is

FOB maintains a persistent workspace that you can leave and return to without losing context.

- **Session persistence** — a single named Zellij session (`fob`) stays alive across terminal closes and reconnects; `fob brief` attaches to it or creates it
- **Context persistence** — `.fob/` mission files give Claude structured, explicit context that survives across sessions
- **Layout persistence** — `fob save` captures the live Zellij tab layout per profile; `fob layout save/load` for explicit KDL-based restore
- **Auto-discovery** — every git repo under `~/Documents/GitHub/` appears in the picker automatically; no YAML required
- **Group profiles** — define named groups (e.g. `platform`) to open multiple repos as a single tab with one command

FOB is not a neutral bootstrap script or a multiplexer-agnostic tool. Zellij is a core dependency, and persistence is the point.

## Workspace Layout

**Single repo:**
```
┌────────────────────────────────────────────────────────┐
│  FOB  │  YourRepo  │  ...                         │  ← tab bar
├──────────┬──────────────────────────────┬──────────────┤
│          │                              │              │
│ lazygit  │   claude / codex / aider     │     logs     │
│  (28%)   │      stacked in center       │    (28%)     │
├──────────┤──────────────────────────────┤              │
│ status   │  shell  (15%)                │              │
│  (25%)   │                              │              │
└──────────┴──────────────────────────────┴──────────────┘
│  NORMAL  │  fob  │  ...                               │  ← status bar
```

Left 28%: lazygit (top) + ControlPlane status script (bottom 25%). Center 44%: stacked `claude`, `codex`, and `aider`, plus a shell at the bottom (15%). Right 28%: logs.

**Multi repo (`fob multi` or group profile) — single tab:**
```
┌──────────────────────────────────────────────────────┐
│  platform  │  ...                                │  ← tab bar (group name, not member list)
├──────────┬─────────────────────────┬──────────────────┤
│ lazygit  │                         │  shell-A ▸       │
│  repo-A  │  claude / codex / aider │  shell-B ▸  (75%)│
│ lazygit  │      (GitHub/)          ├──────────────────┤
│  repo-B  │                         │  cp-status  (25%)│
│   ...  ▸ │                         │                  │
└──────────┴─────────────────────────┴──────────────────┘
```

Left 28%: stacked lazygits (all repos). Center: stacked `claude`, `codex`, and `aider`, rooted at `~/Documents/GitHub/`. Right 28%: stacked shells (75%) + ControlPlane status (25%).

Tab naming: group profiles use the group name (`platform`); ad-hoc multi-select joins all repo names (`RepoA+RepoB+RepoC`).

## What Happens When You Run `fob`

1. Python environment bootstraps itself if needed (first run only)
2. If inside a known repo → always auto-selects that repo, no picker
3. If that repo's tab is already open → attaches to the running session (no duplicate tab)
4. If outside all known repos (e.g. at `~/Documents/GitHub/`) → single-select picker
5. Session `fob` exists → adds repo as a new named tab
6. Session `fob` doesn't exist → generates layout, launches Zellij session
7. Claude starts with `claude --resume <session-id>` (first run: fresh; subsequent runs: resumes saved session)

Use `fob multi` to explicitly open multiple repos at once.

## Why It Exists

`claude --continue` resumes the most recent conversation globally — wrong when you have multiple groups running. FOB tracks a session ID per profile/group in `config/profiles/<name>.session` (gitignored) and uses `claude --resume <id>` so each workspace always resumes its own conversation. `.fob/` mission files give Claude structured context: standing orders, active mission, objectives, and a mission log.

## Installation

```bash
cd ~/Documents/GitHub/FOB
./fob install         # symlinks fob to ~/.local/bin (bootstraps Python env automatically)
source ~/.bashrc
fob doctor            # verify dependencies
```

Dependencies: `zellij`, `claude` (Claude Code CLI), `lazygit`, `git`, `python3`, `fzf`

## First Run

```bash
cd ~/Documents/GitHub/YourRepo
fob
```

`.fob/` is auto-initialized in the repo on first launch.

## Group Profiles

Create a group profile to open multiple repos as a single tab in one step:

```yaml
# config/profiles/platform.yaml
name: platform
group:
  - controlplane
  - fob
  - switchboard
  - workstation
```

```bash
fob brief platform    # opens all four repos in one multi-pane tab
```

Groups appear in the picker with a `▸` prefix and their member list. Selecting a group expands it into its constituent profiles automatically.

## State Boundaries

FOB state lives in four distinct layers:

| Layer | What persists | Location |
|-------|--------------|----------|
| Zellij | Session, tabs, pane arrangement | Zellij session manager |
| `.fob/` | Mission files, layout, compiled briefing | `<repo>/.fob/` (gitignored) |
| CLI config | Profile YAML (tracked for platform group) | `config/profiles/*.yaml` |
| Private config | Saved layouts, session IDs | `config/profiles/*.kdl`, `*.session` (gitignored) |
| Global | Last session group (for `fob restore`) | `~/.local/share/fob/last-session.json` |

## `.fob/` Continuity Model

**Source files** — edit these directly:

| File | Role |
|------|------|
| `active-mission.md` | Current objective — singular, replace when focus changes |
| `standing-orders.md` | Stable repo policy — branch rules, operating constraints |
| `objectives.md` | Work inventory — in-progress, up-next, done |
| `mission-log.md` | Chronological log — decisions, stop points, what changed |

**Compiled artifact** — generated at launch, do not edit:

| File | Role |
|------|------|
| `.briefing` | All four files + runtime context compiled into one startup document |

`fob resume` prints the current briefing so you can inspect exactly what Claude will see.

## Commands

**Workspace:**

| Command | Description |
|---------|-------------|
| `fob` / `fob brief [profile]` | Auto-select current repo and launch |
| `fob brief --layout` | Launch using saved layout (explicit restore) |
| `fob multi` | Multi-select picker — open several repos as tabs |
| `fob restore` | Re-open last saved session group (`--show` to preview without launching) |
| `fob attach` | Re-attach to running `fob` session |
| `fob kill` | Terminate the `fob` session and all panes (warns first) |
| `fob init [repo]` | Initialize `.fob/` mission files in a repo |
| `fob resume` | Print current mission brief from `.fob/` |
| `fob test` | Run project tests |
| `fob audit` | Run project audit |
| `fob doctor` | Check and install dependencies |

**Visibility:**

| Command | Description |
|---------|-------------|
| `fob status` | Session, layout, branch, `.fob/` state |
| `fob status --all` | Compact table of all repos |
| `fob map` | Full state snapshot |
| `fob map --all` | Snapshot of all repos |
| `fob map --json` | Machine-readable state (single repo or `--all`) |

**Reset & Recovery:**

FOB is a persistent system. Every persistent system needs a clear escape hatch.

| Command | Description |
|---------|-------------|
| `fob reset` | Full reset — kills session, clears layout, deletes mission files (confirms first) |
| `fob reset --session` | Kill session only |
| `fob reset --layout` | Clear saved layout only |
| `fob reset --state` | Delete `.fob/` mission files only |
| `fob clear [--all]` | Delete saved layout (current repo or all) |

**Layout:**

| Command | Description |
|---------|-------------|
| `fob save [profile]` | Capture live Zellij tab layout → saved to `config/profiles/<name>.kdl` (gitignored) |
| `fob save --reset [profile]` | Delete saved layout, revert to YAML-generated |
| `fob layout save` | Save generated layout to `.fob/layout.json` (explicit KDL-based restore) |
| `fob layout load` | Restore saved layout (starts Zellij session) |
| `fob layout show` | Show saved layout metadata and path |
| `fob layout reset` | Delete saved layout for current repo |

`fob save` captures the live pane arrangement from the running session. `fob layout save` saves the YAML-generated layout for session-level restore via `--new-session-with-layout`.

**Utility:**

| Command | Description |
|---------|-------------|
| `fob loadout` | Install and configure dev tools |
| `fob cheat` | Open keybinding reference |
| `fob install` | Symlink `fob` to `~/.local/bin` |

**Platform validation:**

| Command | Description |
|---------|-------------|
| `fob demo` | Golden-path platform demo: preflight, stack, providers, SwitchBoard, ControlPlane |
| `fob demo --no-start` | Run the same validation without starting the stack |
| `fob demo --json` | Machine-readable demo summary |
| `fob providers` | Open the provider dashboard and show free provider options |
| `fob providers --wait` | Poll until a provider is connected |

## Typical Session

First run (no existing session):

```
$ cd ~/Documents/GitHub/YourRepo
$ fob

  Brief: YourRepo
  session  creating   (fob)
  layout   fresh
  mission  implement feature X…

[Zellij opens — Claude pane starts, reads .fob/.briefing, begins fresh session]
```

Returning to an existing session:

```
$ fob

  Brief: YourRepo
  session  attaching  (fob)
  mission  implement feature X…

[Zellij attaches — Claude resumes saved session ID for this profile]
```

## Inter-Repo Work

FOB handles multiple repos in two complementary ways:

**Group profiles** — define a named group in `config/profiles/<name>.yaml` with a `group:` list. `fob brief platform` opens all members as a single multi-pane tab. Groups appear in the picker with `▸` prefix.

**Multi-tab** — run `fob multi` from anywhere to get the multi-select picker. Tab to select multiple repos; each opens as a named tab in the same `fob` session. In multi-repo mode, Claude's working directory starts at `~/Documents/GitHub/` so it can navigate across repos freely.

**Peer context** — when multiple repos are opened together in a single `fob brief`, each repo's `.fob/.briefing` automatically includes the active mission and objectives of the other selected repos. Claude in each tab sees what the others are working on without any profile config required.

For persistent cross-repo awareness (across separate `fob brief` invocations), configure peers in a profile:

```yaml
claude:
  peers:
    - controlplane   # always pulls ControlPlane's mission + objectives into this briefing
```

**Session groups** — every `fob brief` auto-saves the selected repos as the "last group". Re-open the exact same set with:

```bash
fob restore             # re-open last saved group (briefings regenerated fresh)
fob restore --show      # preview what would be restored without launching
```

**Cross-repo visibility:**

```bash
fob status --all        # one-line summary of every repo: tab, layout, branch, mission
fob map --all           # detailed snapshot of every repo
fob map --all --json    # machine-readable — useful for ControlPlane delegation
```

## Profiles (Optional)

Repos are auto-discovered — no YAML needed for basic use. Create `config/profiles/<name>.yaml` to configure custom Claude context files, peer repo awareness, custom pane commands, or group multiple repos under one name.

Profile visibility:
- **Platform group members** (`controlplane`, `fob`, `switchboard`, `workstation`, `platform`) are tracked in git
- **All other profiles** are gitignored by default — private repos never appear in tracked files

See [docs/profiles.md](docs/profiles.md).

## Ownership boundary

FOB owns the operator experience: session management, workspace layout, mission files, and operator-facing command entrypoints like `fob demo` and `fob brief`. FOB delegates platform lifecycle actions (stack up/down/health) to WorkStation and does not own infrastructure internals.

FOB does **not** own service Dockerfiles, compose manifests, routing policy, or autonomy logic. Those belong to WorkStation, SwitchBoard, and ControlPlane respectively.

For the full platform ownership model see `WorkStation/docs/architecture/ownership.md`.

---

## Further Reading

- [docs/architecture.md](docs/architecture.md) — launcher flow, session model, layout persistence internals
- [docs/profiles.md](docs/profiles.md) — profile format and optional configuration
- [docs/guardrails.md](docs/guardrails.md) — safe branch practices and Claude operating model
