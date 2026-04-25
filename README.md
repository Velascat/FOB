# OperatorConsole — Operator Console

Operator console for Claude-driven development. Persistent Zellij workspaces with mission-file continuity, plus a full execution pipeline that delegates tasks to OperationsCenter, routes them through SwitchBoard, and records canonical run artifacts.

## What OperatorConsole Is

OperatorConsole maintains a persistent workspace that you can leave and return to without losing context.

- **Session persistence** — a single named Zellij session (`console`) stays alive across terminal closes and reconnects; `console open` attaches to it or creates it
- **Context persistence** — `.console/` mission files give Claude structured, explicit context that survives across sessions
- **Layout persistence** — `console save` captures the live Zellij tab layout per profile; `console layout save/load` for explicit KDL-based restore
- **Auto-discovery** — every git repo under `~/Documents/GitHub/` appears in the picker automatically; no YAML required
- **Group profiles** — define named groups (e.g. `platform`) to open multiple repos as a single tab with one command

OperatorConsole is not a neutral bootstrap script or a multiplexer-agnostic tool. Zellij is a core dependency, and persistence is the point.

## Workspace Layout

**Single repo:**
```
┌────────────────────────────────────────────────────────┐
│  OperatorConsole  │  YourRepo  │  ...                         │  ← tab bar
├──────────┬──────────────────────────────┬──────────────┤
│          │                              │              │
│ lazygit  │   claude / codex / aider     │     logs     │
│  (28%)   │      stacked in center       │    (28%)     │
├──────────┤──────────────────────────────┤              │
│ status   │  shell  (15%)                │              │
│  (25%)   │                              │              │
└──────────┴──────────────────────────────┴──────────────┘
│  NORMAL  │  console  │  ...                               │  ← status bar
```

Left 28%: lazygit (top) + OperationsCenter status script (bottom 25%). Center 44%: stacked `claude`, `codex`, and `aider`, plus a shell at the bottom (15%). Right 28%: logs.

**Multi repo (`console multi` or group profile) — single tab:**
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

Left 28%: stacked lazygits (all repos). Center: stacked `claude`, `codex`, and `aider`, rooted at `~/Documents/GitHub/`. Right 28%: stacked shells (75%) + OperationsCenter status (25%).

Tab naming: group profiles use the group name (`platform`); ad-hoc multi-select joins all repo names (`RepoA+RepoB+RepoC`).

## What Happens When You Run `console`

1. Python environment bootstraps itself if needed (first run only)
2. If inside a known repo → always auto-selects that repo, no picker
3. If that repo's tab is already open → attaches to the running session (no duplicate tab)
4. If outside all known repos (e.g. at `~/Documents/GitHub/`) → single-select picker
5. Session `console` exists → adds repo as a new named tab
6. Session `console` doesn't exist → generates layout, launches Zellij session
7. Claude starts with `claude --resume <session-id>` (first run: fresh; subsequent runs: resumes saved session)

Use `console multi` to explicitly open multiple repos at once.

## Why It Exists

`claude --continue` resumes the most recent conversation globally — wrong when you have multiple groups running. OperatorConsole tracks a session ID per profile/group in `config/profiles/<name>.session` (gitignored) and uses `claude --resume <id>` so each workspace always resumes its own conversation. `.console/` mission files give Claude structured context: standing orders, active mission, objectives, and a mission log.

## Installation

```bash
cd ~/Documents/GitHub/OperatorConsole
./console install         # symlinks console to ~/.local/bin (bootstraps Python env automatically)
source ~/.bashrc
console doctor            # verify dependencies
```

Dependencies: `zellij`, `claude` (Claude Code CLI), `lazygit`, `git`, `python3`, `fzf`

## First Run

```bash
cd ~/Documents/GitHub/YourRepo
console
```

`.console/` is auto-initialized in the repo on first launch.

## Group Profiles

Create a group profile to open multiple repos as a single tab in one step:

```yaml
# config/profiles/platform.yaml
name: platform
group:
  - operations_center
  - operator_console
  - switchboard
  - workstation
```

```bash
console open platform    # opens all four repos in one multi-pane tab
```

Groups appear in the picker with a `▸` prefix and their member list. Selecting a group expands it into its constituent profiles automatically.

## State Boundaries

OperatorConsole state lives in four distinct layers:

| Layer | What persists | Location |
|-------|--------------|----------|
| Zellij | Session, tabs, pane arrangement | Zellij session manager |
| `.console/` | Mission files, layout, compiled briefing | `<repo>/.console/` (gitignored) |
| CLI config | Profile YAML (tracked for platform group) | `config/profiles/*.yaml` |
| Private config | Saved layouts, session IDs | `config/profiles/*.kdl`, `*.session` (gitignored) |
| Global | Last session group (for `console restore`) | `~/.local/share/console/last-session.json` |

## `.console/` Continuity Model

**Source files** — edit these directly:

| File | Role |
|------|------|
| `active-task.md` | Current objective — singular, replace when focus changes |
| `directives.md` | Stable repo policy — branch rules, operating constraints |
| `objectives.md` | Work inventory — in-progress, up-next, done |
| `mission-log.md` | Chronological log — decisions, stop points, what changed |

**Compiled artifact** — generated at launch, do not edit:

| File | Role |
|------|------|
| `.briefing` | All four files + runtime context compiled into one startup document |

`console context` prints the current briefing so you can inspect exactly what Claude will see.

## Commands

**Workspace:**

| Command | Description |
|---------|-------------|
| `console` / `console open [profile]` | Auto-select current repo and launch |
| `console open --layout` | Launch using saved layout (explicit restore) |
| `console multi` | Multi-select picker — open several repos as tabs |
| `console restore` | Re-open last saved session group (`--show` to preview without launching) |
| `console attach` | Re-attach to running `console` session |
| `console kill` | Terminate the `console` session and all panes (warns first) |
| `console init [repo]` | Initialize `.console/` mission files in a repo |
| `console context` | Print current mission brief from `.console/` |
| `console test` | Run project tests |
| `console audit` | Run project audit |
| `console doctor` | Check and install dependencies |

**Visibility:**

| Command | Description |
|---------|-------------|
| `console status` | Session, layout, branch, `.console/` state |
| `console status --all` | Compact table of all repos |
| `console overview` | Full state snapshot |
| `console overview --all` | Snapshot of all repos |
| `console overview --json` | Machine-readable state (single repo or `--all`) |

**Reset & Recovery:**

OperatorConsole is a persistent system. Every persistent system needs a clear escape hatch.

| Command | Description |
|---------|-------------|
| `console reset` | Full reset — kills session, clears layout, deletes mission files (confirms first) |
| `console reset --session` | Kill session only |
| `console reset --layout` | Clear saved layout only |
| `console reset --state` | Delete `.console/` mission files only |
| `console clear [--all]` | Delete saved layout (current repo or all) |

**Layout:**

| Command | Description |
|---------|-------------|
| `console save [profile]` | Capture live Zellij tab layout → saved to `config/profiles/<name>.kdl` (gitignored) |
| `console save --reset [profile]` | Delete saved layout, revert to YAML-generated |
| `console layout save` | Save generated layout to `.console/layout.json` (explicit KDL-based restore) |
| `console layout load` | Restore saved layout (starts Zellij session) |
| `console layout show` | Show saved layout metadata and path |
| `console layout reset` | Delete saved layout for current repo |

`console save` captures the live pane arrangement from the running session. `console layout save` saves the YAML-generated layout for session-level restore via `--new-session-with-layout`.

**Utility:**

| Command | Description |
|---------|-------------|
| `console install` | Install and configure dev tools |
| `console cheat` | Open keybinding reference |
| `console install` | Symlink `console` to `~/.local/bin` |

**Execution pipeline:**

| Command | Description |
|---------|-------------|
| `console status` | System readiness: SwitchBoard, OperationsCenter, lane binaries, last run |
| `console status --json` | Machine-readable system readiness |
| `console run --goal TEXT` | Run a task through the full OperationsCenter pipeline |
| `console run --dry-run` | Planning only — print lane decision without executing |
| `console cycle` | Single autonomous cycle: observe → propose → decide → execute |
| `console cycle --dry-run` | Observe + plan only, no execution |
| `console last` | Inspect the most recent run (status, lane, artifacts) |
| `console last --all` | Most recent run + list of recent runs |
| `console last --json` | Machine-readable last run summary |
| `console runs` | List recent runs newest-first (status, lane, timestamp, goal) |
| `console runs --limit N` | Show N most recent runs |
| `console runs --json` | Machine-readable run list |

Run artifacts are written to `~/.console/operations_center/runs/<run_id>/` by OperationsCenter's `RunArtifactWriter`. Each run directory contains `proposal.json`, `decision.json`, `execution_request.json`, `result.json`, and `run_metadata.json`. Runs accumulate — use `console runs` to browse history.

**Platform validation:**

| Command | Description |
|---------|-------------|
| `console demo` | End-to-end validation: preflight → stack → health → route → planning → execution |
| `console demo --no-start` | Same validation without starting the stack |
| `console demo --json` | Machine-readable demo summary |
| `console providers` | Show selector and lane readiness |
| `console providers --wait` | Poll until SwitchBoard is healthy |

## Typical Session

First run (no existing session):

```
$ cd ~/Documents/GitHub/YourRepo
$ console

  Brief: YourRepo
  session  creating   (console)
  layout   fresh
  mission  implement feature X…

[Zellij opens — Claude pane starts, reads .console/.briefing, begins fresh session]
```

Returning to an existing session:

```
$ console

  Brief: YourRepo
  session  attaching  (console)
  mission  implement feature X…

[Zellij attaches — Claude resumes saved session ID for this profile]
```

## Inter-Repo Work

OperatorConsole handles multiple repos in two complementary ways:

**Group profiles** — define a named group in `config/profiles/<name>.yaml` with a `group:` list. `console open platform` opens all members as a single multi-pane tab. Groups appear in the picker with `▸` prefix.

**Multi-tab** — run `console multi` from anywhere to get the multi-select picker. Tab to select multiple repos; each opens as a named tab in the same `console` session. In multi-repo mode, Claude's working directory starts at `~/Documents/GitHub/` so it can navigate across repos freely.

**Peer context** — when multiple repos are opened together in a single `console open`, each repo's `.console/.briefing` automatically includes the active mission and objectives of the other selected repos. Claude in each tab sees what the others are working on without any profile config required.

For persistent cross-repo awareness (across separate `console open` invocations), configure peers in a profile:

```yaml
claude:
  peers:
    - operations_center   # always pulls OperationsCenter's mission + objectives into this briefing
```

**Session groups** — every `console open` auto-saves the selected repos as the "last group". Re-open the exact same set with:

```bash
console restore             # re-open last saved group (briefings regenerated fresh)
console restore --show      # preview what would be restored without launching
```

**Cross-repo visibility:**

```bash
console status --all        # one-line summary of every repo: tab, layout, branch, mission
console overview --all           # detailed snapshot of every repo
console overview --all --json    # machine-readable — useful for OperationsCenter delegation
```

## Profiles (Optional)

Repos are auto-discovered — no YAML needed for basic use. Create `config/profiles/<name>.yaml` to configure custom Claude context files, peer repo awareness, custom pane commands, or group multiple repos under one name.

Profile visibility:
- **Platform group members** (`operations_center`, `operator_console`, `switchboard`, `workstation`, `platform`) are tracked in git
- **All other profiles** are gitignored by default — private repos never appear in tracked files

See [docs/profiles.md](docs/profiles.md).

## Ownership boundary

OperatorConsole owns the operator experience: session management, workspace layout, mission files, and execution pipeline commands (`console run`, `console cycle`, `console last`, `console runs`, `console demo`). OperatorConsole delegates platform lifecycle actions (stack up/down/health) to WorkStation and delegates all planning, routing, and execution to OperationsCenter and SwitchBoard via subprocess.

OperatorConsole does **not** own service Dockerfiles, compose manifests, routing policy, adapter logic, or contract definitions. Those belong to WorkStation, SwitchBoard, and OperationsCenter respectively. OperatorConsole has no direct imports from any of those repos at runtime.

For the full platform ownership model see `WorkStation/docs/architecture/ownership.md`.

---

## Further Reading

- [docs/architecture.md](docs/architecture.md) — launcher flow, session model, layout persistence internals
- [docs/cockpit.md](docs/cockpit.md) — execution pipeline commands: run, last, status, runs
- [docs/daily-use.md](docs/daily-use.md) — startup, run, inspect, cleanup, and known limits
- [docs/demo.md](docs/demo.md) — end-to-end architecture validation walkthrough
- [docs/profiles.md](docs/profiles.md) — profile format and optional configuration
- [docs/guardrails.md](docs/guardrails.md) — safe branch practices and Claude operating model
