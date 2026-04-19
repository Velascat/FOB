# Profiles

Profiles define a reproducible workspace configuration. They live in `config/profiles/<name>.yaml`.

## Format

```yaml
name: default                              # Profile identifier (matches filename stem)
session_name: brief-default               # Zellij session name (must be unique)
repo_root: /absolute/path/to/repo         # Target repository root

claude:
  continue: true                           # Use claude --continue (vs fresh start)
  bootstrap_files:                         # Files fed to Claude at launch (in order)
    - .fob/standing-orders.md
    - .fob/active-mission.md
    - .fob/objectives.md
    - .fob/mission-log.md
    # - .fob/extra-context.md             # Add project-specific files here
  peers: []                               # Other profile names to pull context from
    # - controlplane                      # Includes that repo's active-mission + objectives

panes:
  claude:
    cwd: /absolute/path/to/repo
    command: claude --continue
  git:
    cwd: /absolute/path/to/repo
    command: lazygit
  logs:
    cwd: /absolute/path/to/repo
    command: tail -f .fob/runtime.log 2>/dev/null
  shell:
    cwd: /absolute/path/to/repo
    command: bash

helpers:
  test: pytest -x -v
  audit: ./tools/lint.sh
```

## Adding a Profile

1. Copy `config/profiles/default.yaml` to `config/profiles/<name>.yaml`
2. Edit `name`, `session_name`, `repo_root`, and pane commands
3. Run `fob init <repo_root>` to create `.fob/` mission files in the target repo
4. Launch: `fob brief <name>`

## Profile Constraints

- `name` must match the filename stem (e.g., `name: controlplane` → `controlplane.yaml`)
- `session_name` must be unique across profiles — it becomes the Zellij session name
- `repo_root` must be an absolute path to an existing directory
- Tilde (`~`) is expanded automatically

## Claude Context: bootstrap_files

`bootstrap_files` controls which files are concatenated into `.fob/.briefing` at launch. The standard four files are the default. Add extra files for project-specific context Claude should always have:

```yaml
claude:
  bootstrap_files:
    - .fob/standing-orders.md
    - .fob/active-mission.md
    - .fob/objectives.md
    - .fob/mission-log.md
    - .fob/api-contracts.md        # VideoFoundry: pipeline I/O spec
```

## Claude Context: peers

`peers` lists other profile names. At launch, `active-mission.md` and `objectives.md` from each peer repo are appended to the brief as `PEER: <name>` sections. Use this when repos are tightly coupled and Claude needs to reason across them:

```yaml
claude:
  peers:
    - controlplane    # Claude sees ControlPlane's current mission + objectives
```

## Layout Persistence

FOB saves the generated Zellij layout to `.fob/layout-state.kdl` after each launch. On the next `fob brief` (if the session is dead), it uses that saved layout instead of regenerating — so manual edits to the KDL persist.

To reset to profile defaults:
```bash
fob brief --reset-layout
```

## Example: Second Repo Profile

```yaml
name: controlplane
session_name: brief-controlplane
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
    - default                     # pulls VideoFoundry mission context

panes:
  claude:
    cwd: /home/dev/Documents/GitHub/ControlPlane
    command: claude --continue
  git:
    cwd: /home/dev/Documents/GitHub/ControlPlane
    command: lazygit
  logs:
    cwd: /home/dev/Documents/GitHub/ControlPlane
    command: tail -f logs/dev.log 2>/dev/null
  shell:
    cwd: /home/dev/Documents/GitHub/ControlPlane
    command: bash

helpers:
  test: pytest -x -v
  audit: ./dev audit
```
