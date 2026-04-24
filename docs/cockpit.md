# FOB Cockpit Commands

FOB is the primary operator interface to the system. After Phase 8, all common
operations are available without touching ControlPlane internals or artifact
directories directly.

---

## Commands

### `fob delegate` — run a task

Triggers a full execution: planning → SwitchBoard routing → adapter → result.

```bash
fob delegate --goal "Refresh the README summary"
fob delegate --goal "Fix lint errors" --repo-key myrepo --clone-url https://github.com/org/repo.git
fob delegate --goal "Update docs" --task-type documentation
fob delegate --goal "..." --dry-run    # planning only, no execution
fob delegate --goal "..." --json       # machine-readable output
```

**Flags:**

| Flag | Default | Description |
|---|---|---|
| `--goal TEXT` | prompted | Task goal (required) |
| `--task-type TYPE` | `documentation` | Task classification |
| `--repo-key KEY` | `default` | Repository key |
| `--clone-url URL` | placeholder | Repository clone URL |
| `--task-branch BRANCH` | auto-generated | Git branch for this run |
| `--dry-run` | false | Planning only, no adapter execution |
| `--json` | false | Machine-readable output |

**Example output:**

```
  fob delegate — delegating task to ControlPlane

  [FOB] goal='Refresh README summary'  type=documentation  repo=default
  ── planning
  [ControlPlane] proposal created — id=a1b2c3d4…
  [SwitchBoard] selected lane=claude_cli  backend=kodo
  [Adapter] executing  lane=claude_cli  backend=kodo
  ⚠ Backend ran but failed — status=failed  category=backend_error
  · This is expected when the backend binary is not installed on this machine.

  Run ID     abc123...
  Artifacts  ~/.fob/control_plane/runs/abc123.../
```

**Artifacts:** Every run persists all four canonical contracts to
`~/.fob/control_plane/runs/<run_id>/`. See `fob last` to inspect.

---

### `fob last` — inspect the most recent run

Shows a concise summary of the most recent execution run from Phase 7 artifacts.

```bash
fob last               # most recent run summary
fob last --all         # summary + list of recent runs
fob last --json        # machine-readable JSON
```

**Example output:**

```
  fob last — most recent execution run

  Run ID    abc123ef-...
  Status    success
  Executed  yes
  Lane      claude_cli  → kodo
  Written   2026-04-24 10:00:00

  Task
    goal      Refresh README summary
    type      documentation
    repo      default

  · artifacts: ~/.fob/control_plane/runs/abc123.../
```

**No runs found:** If no runs exist, `fob last` returns exit code 1 and suggests
running `fob delegate` or `fob demo`.

---

### `fob status` — system readiness

Shows SwitchBoard health, ControlPlane availability, lane binary status, and
a summary of the most recent run.

```bash
fob status             # system readiness overview
fob status --json      # machine-readable
fob status --repo      # old repo/session state view (branch, layout, .fob/)
fob status --all       # compact table of all repos
```

**Example output:**

```
  fob status — system readiness

  SwitchBoard            OK  http://localhost:20401/health
  ControlPlane           OK  ~/Documents/GitHub/ControlPlane

  Lanes
    claude_cli           available  (claude)
    codex_cli            available  (codex)
    kodo                 available  (kodo)
    aider_local          unavailable  (aider)

  Last run
    id      abc123ef-...
    status  success
    lane    claude_cli
    goal    Refresh README summary
    at      2026-04-24 10:00:00
```

Returns exit code 1 if SwitchBoard or ControlPlane are not reachable.

---

## Artifact location

All run artifacts are in:

```
~/.fob/control_plane/runs/<run_id>/
  proposal.json
  decision.json
  execution_request.json
  result.json
  run_metadata.json
```

See `docs/operator/run-artifacts.md` (ControlPlane repo) for full field reference.

---

## Quick reference

```bash
fob delegate --goal "..."    # trigger execution
fob last                     # inspect last run
fob last --all               # inspect + history
fob status                   # system health + last run
fob demo                     # full 7-step architecture validation
fob providers                # lane readiness detail
```

---

## Known limitations

- `fob delegate` uses placeholder `clone-url` and `repo-key` by default — the
  execution boundary is real but the adapter won't find a real repo to clone
  unless you provide `--clone-url`.
- Lane binary failures (e.g. `kodo` or `aider` not installed) produce a canonical
  `ExecutionResult(success=False, failure_category=backend_error)` — the pipeline
  itself ran correctly.
- `fob status` lane checks are binary (installed / not installed); they do not
  verify API credentials or model access.
- Run history is stored locally in `~/.fob/`; no cross-machine sync.
