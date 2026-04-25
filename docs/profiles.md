# Profiles

Profiles are **optional**. Any git repo under `~/Documents/GitHub/` is auto-discovered and appears when you run `console` without a profile. Create a profile when you need custom Claude context, peer cross-repo awareness, custom pane commands, or to define a named group of repos.

Profiles live in `config/profiles/<name>.yaml`.

## Git Visibility

Only platform-group member profiles are tracked in git. All other profiles are gitignored by default — private repos never appear in committed files:

```
config/profiles/*.yaml        # gitignored
!config/profiles/platform.yaml      # tracked
!config/profiles/operations_center.yaml  # tracked
!config/profiles/console.yaml           # tracked
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

status_repos: MyRepo                      # OperationsCenter status filter (empty = show all)

claude:
  bootstrap_files:                        # Files fed to Claude at launch (in order)
    - .console/guidelines.md             # Omit to use these four defaults
    - .console/task.md
    - .console/backlog.md
    - .console/log.md
    # - .console/extra-context.md            # Add project-specific files here
  peers: []                              # Other profile names to pull context from
    # - operations_center                     # Includes that repo's task and backlog

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
  - operations_center
  - console
  - switchboard
  - workstation
```

Groups appear in the picker with `▸` prefix and their member list. `console open platform` opens all four repos as a single multi-pane tab.

## Adding a Profile

1. Create `config/profiles/<name>.yaml` — minimum required fields are `name` and `repo_root`
2. Run `console init <repo_root>` if `.console/` doesn't exist in the target repo yet
3. Launch: `console open <name>` or just run `console` from inside the repo

## Profile Constraints

- `name` must match the filename stem (e.g., `name: operations_center` → `operations_center.yaml`)
- `repo_root` must be an absolute path to an existing directory
- Tilde (`~`) is expanded automatically
- All fields except `name` and `repo_root` are optional

## status_repos

Controls which repos appear in the OperationsCenter status pane. Set to the repo's board key to filter, or omit/empty to show all managed repos:

```yaml
status_repos: OperationsCenter    # show only OperationsCenter on the board
status_repos: ""              # show all CP-tracked repos (useful for OperatorConsole itself)
```

## Claude Session IDs

OperatorConsole tracks a Claude session ID per profile in `config/profiles/<name>.session` (gitignored). On launch, if a session ID is saved, Claude starts with `claude --resume <id>` instead of a fresh conversation. If the saved session no longer exists, it falls back to a fresh start automatically.

The session ID is captured when Claude exits — no manual step needed. Each profile and group maintains its own session independently.

To discard a saved session and start fresh next open:
```bash
rm config/profiles/<name>.session
```

## Claude Context: bootstrap_files

`bootstrap_files` controls which files are concatenated into `.console/.context` at launch. If omitted, the standard four `.console/` files are used. Add extra files for project-specific context:

```yaml
claude:
  bootstrap_files:
    - .console/guidelines.md
    - .console/task.md
    - .console/backlog.md
    - .console/log.md
    - .console/api-contracts.md        # project-specific: pipeline I/O spec
```

## Claude Context: peers

### Automatic (multi-select open)

When multiple repos are selected in a single `console open` run, each repo's `.console/.context` automatically includes the active task and backlog of the other selected repos. No profile config needed — it's implicit when repos are opened together.

### Configured (persistent across sessions)

`peers` lists other profile names. At launch, `task.md` and `backlog.md` from each peer repo are appended to the context as `PEER: <name>` sections. Use this when repos are tightly coupled and Claude needs cross-repo awareness on every session, not just when opened together:

```yaml
claude:
  peers:
    - operations_center    # Claude sees OperationsCenter's current task + backlog
```

## Layout Persistence

### Live Layout Capture (console save)

`console save [profile]` captures the current Zellij tab layout — pane sizes, commands, everything — and saves it to `config/profiles/<name>.kdl` (gitignored). The next `console open` uses it automatically instead of regenerating from YAML.

The default generated layouts now assume:

- single-repo tabs: stacked `claude`, `codex`, and `aider` in the center column
- multi-repo tabs: the same stacked chat/tool panes, rooted at `~/Documents/GitHub/`

```bash
console save                      # save current tab for the auto-detected profile
console save myrepo               # save the tab named "myrepo"
console save --reset myrepo       # delete saved layout, revert to YAML-generated
```

### KDL-Based Restore (console layout)

`console layout save` saves the YAML-generated layout for explicit session-level restore:

```bash
console layout save         # save generated layout to .console/layout.json + .console/layout.kdl
console layout load         # restore saved layout (starts Zellij session)
console open --layout      # full open flow + restore saved layout
console layout show         # inspect what is saved (backend, profile, saved_at, path)
console layout reset        # delete saved layout for current repo
console clear               # same as layout reset
console clear --all         # delete saved layouts across all repos
```

Saved layout metadata (`.console/layout.json`) includes the backend, repo root, profile name, and timestamp. If the repo root in the saved file does not match the current path, `console layout load` will refuse and explain the mismatch.

## Example: Configured Profile

```yaml
name: operations_center
repo_root: /home/dev/Documents/GitHub/OperationsCenter
status_repos: OperationsCenter

claude:
  bootstrap_files:
    - .console/guidelines.md
    - .console/task.md
    - .console/backlog.md
    - .console/log.md
    - .console/agent-boundaries.md    # OperationsCenter-specific rules
  peers:
    - console                         # pulls OperatorConsole's task context

panes:
  logs:
    command: tail -f logs/dev.log 2>/dev/null

helpers:
  test: pytest -x -v
  audit: ./dev audit
```
