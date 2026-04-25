# OperatorConsole — Daily Use

Practical notes for repeated, reliable use.

---

## Normal Startup

Start the WorkStation stack (SwitchBoard must be healthy before any task):

```bash
cd ~/Documents/GitHub/WorkStation
./scripts/up.sh
```

Confirm readiness:

```bash
console status
console providers
```

`console status` checks SwitchBoard health and OperationsCenter reachability.
`console providers` shows which backend binaries are installed and available.

Expected: SwitchBoard OK, OperationsCenter OK, at least one lane binary available.

---

## Running a Task

**Manual goal:**

```bash
console run --goal "Refresh the README summary"
```

(`console delegate` is an alias for `console run`.)

**With task type:**

```bash
console run --goal "Fix lint errors in src/" --task-type lint_fix
```

**Planning only (no execution):**

```bash
console run --goal "..." --dry-run
```

**One-shot autonomous cycle (reads goal from `.console/task.md`):**

```bash
console cycle
```

(`console auto-once` is an alias for `console cycle`.)

---

## What Success Looks Like

A successful run prints:

```
  [OperationsCenter] proposal created — id=abcd1234…
  [SwitchBoard]      selected lane=claude_cli  backend=kodo
  [Adapter]          executing  lane=claude_cli  backend=kodo
  ✓ status=SUCCESS

  Run ID     f3a9c2d1-…
  Artifacts  ~/.console/operations_center/runs/f3a9c2d1-…
```

`console run` exits with code `0`.

If the backend binary is not installed, you will see:

```
  ⚠ Backend ran but failed — status=BACKEND_ERROR  category=backend_error
  · This is expected when the backend binary is not installed on this machine.
```

`console run` exits with code `4` (`backend_error`). The pipeline ran correctly — only the final binary invocation failed.

---

## Exit Codes

`console run` returns a specific exit code to allow scripting:

| Code | Meaning |
|------|---------|
| 0 | Execution succeeded |
| 1 | General / unknown failure (crash, missing args) |
| 2 | Routing failure — SwitchBoard unreachable or returned an error |
| 3 | Policy blocked / review required |
| 4 | Backend execution failure (`backend_error`, `validation_failed`, etc.) |
| 5 | Timeout during execution |
| 6 | Malformed / unparseable output from a subprocess |

---

## Autonomy Surfaces

There are two separate autonomy surfaces. They are not interchangeable.

| | `console cycle` | OperationsCenter autonomy cycle |
|---|---|---|
| **What it does** | Observes the repo, proposes one task, delegates it for execution | Runs the OperationsCenter planning loop — creates Plane board tasks |
| **Executes code?** | Yes — goes through the full pipeline to an adapter | No direct execution; produces Plane task proposals |
| **Creates Plane tasks?** | No | Yes |
| **Stops automatically?** | Yes — one cycle, then exits | Yes — one cycle per invocation |
| **When to use** | You want one self-driven code change executed now | You want the planner to queue work on the board |

Run `console cycle` for immediate local execution.
Run `python -m operations_center.entrypoints.autonomy_cycle.main` (from the OperationsCenter repo) for board-driven planning.

---

## Inspecting Runs

**Most recent run:**

```bash
console last
```

**All fields + recent run list:**

```bash
console last --all
```

**List of recent runs (newest first):**

```bash
console runs
```

**Limit to last 5:**

```bash
console runs --limit 5
```

**Machine-readable:**

```bash
console last --json
console runs --json
```

**Browse artifact files directly:**

```bash
ls ~/.console/operations_center/runs/
ls ~/.console/operations_center/runs/<run_id>/
```

Each run directory contains:

```
proposal.json          TaskProposal
decision.json          LaneDecision
execution_request.json ExecutionRequest
result.json            ExecutionResult
run_metadata.json      run id, lane, status, timestamp
```

---

## Artifact Behavior

Each run gets a unique UUID-based run ID. Directories never overwrite each other.

Failed runs remain as `failure_category=backend_error` or `partial` directories. They do not affect subsequent runs.

`console last` and `console runs` sort by `written_at` timestamp in the metadata — newest run is always correct regardless of directory naming.

---

## Cleanup

Runs accumulate indefinitely. To prune old runs:

```bash
console clean --keep 10    # keep 10 most recent, delete the rest
console clean --dry-run    # preview what would be deleted
```

Or manually:

```bash
ls -lt ~/.console/operations_center/runs/     # newest first
rm -rf ~/.console/operations_center/runs/<run_id>
```

---

## Failure Recovery

If a run fails (backend not installed, SwitchBoard unreachable), the failure is recorded as a partial or failed artifact. The next run gets a fresh run ID and is unaffected.

Check what went wrong:

```bash
console last
cat ~/.console/operations_center/runs/<run_id>/result.json
```

`failure_category=backend_error` with `success=False` is **expected** when a backend binary (`kodo`, `aider`, etc.) is not installed. The execution boundary was still exercised. `console run` exits with code `4` in this case.

If SwitchBoard is unreachable, `console run` exits with code `2`. Run `./scripts/up.sh` from WorkStation to restart the stack.

---

## Daily Regression Path

Run these in order to confirm the system is working:

```bash
console status                              # stack + OperationsCenter + binaries
console providers                           # backend binary readiness
console run --goal "smoke test" --dry-run   # planning only, no adapter needed
console last                                # confirm a run was recorded
```

All four should complete without errors. If `console status` shows SwitchBoard unreachable, run `./scripts/up.sh` from WorkStation first.

---

## Full End-to-End Validation

```bash
console demo
```

Runs all six steps: preflight → stack → health → route → planning → execution.

---

## Known Limits

| Limit | Detail |
|---|---|
| Single machine only | No distributed or multi-user support |
| No scheduling | `console cycle` must be triggered manually each cycle |
| Backend binary required for success | Execution without `kodo`/`aider` records `backend_error` (exit 4) — not a pipeline bug |
| SwitchBoard must be running | All routing calls fail (exit 2) if WorkStation stack is down |
| No run search | `console runs` shows recent runs by time; no filtering by status or goal |
| Partial runs counted | `console runs` shows partial artifacts alongside complete runs |
