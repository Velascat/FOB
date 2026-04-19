# Profiles

Profiles define a reproducible workspace configuration. They live in `config/profiles/<name>.yaml`.

## Format

```yaml
name: default                              # Profile identifier (matches filename stem)
session_name: brief-default               # Zellij session name (must be unique)
repo_root: /absolute/path/to/repo         # Target repository root

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

## Example: Second Repo Profile

```yaml
name: controlplane
session_name: brief-controlplane
repo_root: /home/dev/Documents/GitHub/ControlPlane

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
