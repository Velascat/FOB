# Profiles

Profiles are **optional**. Any git repo under `~/Documents/GitHub/` is auto-discovered and appears when you run `fob` without a profile. Create a profile when you need custom Claude context, peer cross-repo awareness, or non-default helper commands.

Profiles live in `config/profiles/<name>.yaml`.

## Format

```yaml
name: myrepo                              # Profile identifier (matches filename stem)
repo_root: /absolute/path/to/repo         # Target repository root

claude:
  continue: true                           # Use claude --continue (vs fresh start)
  bootstrap_files:                         # Files fed to Claude at launch (in order)
    - .fob/standing-orders.md              # Omit to use these four defaults
    - .fob/active-mission.md
    - .fob/objectives.md
    - .fob/mission-log.md
    # - .fob/extra-context.md             # Add project-specific files here
  peers: []                               # Other profile names to pull context from
    # - controlplane                      # Includes that repo's active-mission + objectives

panes:
  git:
    command: lazygit                       # Override default git pane command
  logs:
    command: tail -f logs/dev.log 2>/dev/null

helpers:
  test: pytest -x -v
  audit: ruff check src/
```

## Adding a Profile

1. Create `config/profiles/<name>.yaml` — minimum required fields are `name` and `repo_root`
2. Run `fob init <repo_root>` if `.fob/` doesn't exist in the target repo yet
3. Launch: `fob brief <name>` or just run `fob` from inside the repo

## Profile Constraints

- `name` must match the filename stem (e.g., `name: controlplane` → `controlplane.yaml`)
- `repo_root` must be an absolute path to an existing directory
- Tilde (`~`) is expanded automatically
- All fields except `name` and `repo_root` are optional

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

`peers` lists other profile names. At launch, `active-mission.md` and `objectives.md` from each peer repo are appended to the brief as `PEER: <name>` sections. Use this when repos are tightly coupled and Claude needs to reason across them:

```yaml
claude:
  peers:
    - controlplane    # Claude sees ControlPlane's current mission + objectives
```

## Layout Persistence

Layout persistence is an explicit, opt-in feature. Normal `fob brief` always generates a fresh layout — it does not silently restore a previous one.

To save and restore a layout:
```bash
fob layout save         # save current repo layout to .fob/layout.json + .fob/layout.kdl
fob layout load         # restore saved layout (starts Zellij session)
fob brief --layout      # full brief flow + restore saved layout
fob layout show         # inspect what is saved (backend, profile, saved_at, path)
fob layout reset        # delete saved layout for current repo
fob clear               # same as layout reset
fob clear --all         # delete saved layouts across all repos
```

Saved layout metadata (`.fob/layout.json`) includes the backend, repo root, profile name, and timestamp. If the repo root in the saved file does not match the current path, `fob layout load` will refuse to apply it and explain the mismatch.

## Example: Configured Profile

```yaml
name: controlplane
repo_root: /home/dev/Documents/GitHub/ControlPlane

claude:
  continue: true
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
