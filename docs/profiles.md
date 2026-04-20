# Profiles

Profiles are **optional**. Any git repo under `~/Documents/GitHub/` is auto-discovered and appears when you run `fob` without a profile. Create a profile when you need custom Claude context, peer cross-repo awareness, custom pane commands, or to define a named group of repos.

Profiles live in `config/profiles/<name>.yaml`.

## Git Visibility

Only platform-group member profiles are tracked in git. All other profiles are gitignored by default — private repos never appear in committed files:

```
config/profiles/*.yaml        # gitignored
!config/profiles/platform.yaml      # tracked
!config/profiles/controlplane.yaml  # tracked
!config/profiles/fob.yaml           # tracked
!config/profiles/switchboard.yaml   # tracked
!config/profiles/workstation.yaml   # tracked

config/profiles/*.kdl         # always gitignored (saved live layouts)
config/profiles/*.session     # always gitignored (Claude session IDs)
```

To add a private repo profile: create `config/profiles/<name>.yaml` — it will be silently ignored by git.

## Format

```yaml
name: myrepo                              # Profile identifier (matches filename stem)
repo_root: /absolute/path/to/repo         # Target repository root

status_repos: MyRepo                      # ControlPlane status filter (empty = show all)

claude:
  bootstrap_files:                        # Files fed to Claude at launch (in order)
    - .fob/standing-orders.md             # Omit to use these four defaults
    - .fob/active-mission.md
    - .fob/objectives.md
    - .fob/mission-log.md
    # - .fob/extra-context.md            # Add project-specific files here
  peers: []                              # Other profile names to pull context from
    # - controlplane                     # Includes that repo's active-mission + objectives

panes:
  git:
    command: lazygit                      # Override default git pane command
  logs:
    command: tail -f logs/dev.log 2>/dev/null

helpers:
  test: pytest -x -v
  audit: ruff check src/
```

## Group Profiles

A profile with a `group:` list (and no `repo_root:`) defines a named group. Selecting it expands all members automatically:

```yaml
name: platform
group:
  - controlplane
  - fob
  - switchboard
  - workstation
```

Groups appear in the picker with `▸` prefix and their member list. `fob brief platform` opens all four repos as a single multi-pane tab.

## Adding a Profile

1. Create `config/profiles/<name>.yaml` — minimum required fields are `name` and `repo_root`
2. Run `fob init <repo_root>` if `.fob/` doesn't exist in the target repo yet
3. Launch: `fob brief <name>` or just run `fob` from inside the repo

## Profile Constraints

- `name` must match the filename stem (e.g., `name: controlplane` → `controlplane.yaml`)
- `repo_root` must be an absolute path to an existing directory
- Tilde (`~`) is expanded automatically
- All fields except `name` and `repo_root` are optional

## status_repos

Controls which repos appear in the ControlPlane status pane. Set to the repo's board key to filter, or omit/empty to show all managed repos:

```yaml
status_repos: ControlPlane    # show only ControlPlane on the board
status_repos: ""              # show all CP-tracked repos (useful for FOB itself)
```

## Claude Session IDs

FOB tracks a Claude session ID per profile in `config/profiles/<name>.session` (gitignored). On launch, if a session ID is saved, Claude starts with `claude --resume <id>` instead of a fresh conversation. If the saved session no longer exists, it falls back to a fresh start automatically.

The session ID is captured when Claude exits — no manual step needed. Each profile and group maintains its own session independently.

To discard a saved session and start fresh next brief:
```bash
rm config/profiles/<name>.session
```

## Claude Context: bootstrap_files

`bootstrap_files` controls which files are concatenated into `.fob/.briefing` at launch. If omitted, the standard four `.fob/` files are used. Add extra files for project-specific context:

```yaml
claude:
  bootstrap_files:
    - .fob/standing-orders.md
    - .fob/active-mission.md
    - .fob/objectives.md
    - .fob/mission-log.md
    - .fob/api-contracts.md        # project-specific: pipeline I/O spec
```

## Claude Context: peers

### Automatic (multi-select brief)

When multiple repos are selected in a single `fob brief` run, each repo's `.fob/.briefing` automatically includes the active mission and objectives of the other selected repos. No profile config needed — it's implicit when repos are opened together.

### Configured (persistent across sessions)

`peers` lists other profile names. At launch, `active-mission.md` and `objectives.md` from each peer repo are appended to the brief as `PEER: <name>` sections. Use this when repos are tightly coupled and Claude needs cross-repo awareness on every session, not just when opened together:

```yaml
claude:
  peers:
    - controlplane    # Claude sees ControlPlane's current mission + objectives
```

## Layout Persistence

### Live Layout Capture (fob save)

`fob save [profile]` captures the current Zellij tab layout — pane sizes, commands, everything — and saves it to `config/profiles/<name>.kdl` (gitignored). The next `fob brief` uses it automatically instead of regenerating from YAML.

```bash
fob save                      # save current tab for the auto-detected profile
fob save myrepo               # save the tab named "myrepo"
fob save --reset myrepo       # delete saved layout, revert to YAML-generated
```

### KDL-Based Restore (fob layout)

`fob layout save` saves the YAML-generated layout for explicit session-level restore:

```bash
fob layout save         # save generated layout to .fob/layout.json + .fob/layout.kdl
fob layout load         # restore saved layout (starts Zellij session)
fob brief --layout      # full brief flow + restore saved layout
fob layout show         # inspect what is saved (backend, profile, saved_at, path)
fob layout reset        # delete saved layout for current repo
fob clear               # same as layout reset
fob clear --all         # delete saved layouts across all repos
```

Saved layout metadata (`.fob/layout.json`) includes the backend, repo root, profile name, and timestamp. If the repo root in the saved file does not match the current path, `fob layout load` will refuse and explain the mismatch.

## Example: Configured Profile

```yaml
name: controlplane
repo_root: /home/dev/Documents/GitHub/ControlPlane
status_repos: ControlPlane

claude:
  bootstrap_files:
    - .fob/standing-orders.md
    - .fob/active-mission.md
    - .fob/objectives.md
    - .fob/mission-log.md
    - .fob/agent-boundaries.md    # ControlPlane-specific rules
  peers:
    - fob                         # pulls FOB's mission context

panes:
  logs:
    command: tail -f logs/dev.log 2>/dev/null

helpers:
  test: pytest -x -v
  audit: ./dev audit
```
