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
```

Expected: SwitchBoard OK, OperationsCenter OK, at least one lane binary available.

---

## Running a Task

**Manual goal:**

```bash
console delegate --goal "Refresh the README summary"
```

**With task type:**

```bash
console delegate --goal "Fix lint errors in src/" --task-type lint_fix
```

**Planning only (no execution):**

```bash
console delegate --goal "..." --dry-run
```

**Autonomous cycle (reads goal from `.console/task.md`):**

```bash
console auto-once
```

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
ls -lt ~/.console/operations_center/runs/     # newest first
rm -rf ~/.console/operations_center/runs/<run_id>
```

There is no automatic pruning. Delete by hand when the directory grows large.

---

## Failure Recovery

If a run fails (backend not installed, SwitchBoard unreachable), the failure is recorded as a partial or failed artifact. The next run gets a fresh run ID and is unaffected.

Check what went wrong:

```bash
console last
cat ~/.console/operations_center/runs/<run_id>/result.json
```

`failure_category=backend_error` with `success=False` is **expected** when a backend binary (`kodo`, `aider`, etc.) is not installed. The execution boundary was still exercised.

---

## Daily Regression Path

Run these in order to confirm the system is working:

```bash
console status                       # stack + OperationsCenter + binaries
console delegate --goal "smoke test" --dry-run   # planning only, no adapter needed
console last                         # confirm a run was recorded
```

All three should complete without errors. If `console status` shows SwitchBoard unreachable, run `./scripts/up.sh` from WorkStation first.

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
| No scheduling | `console auto-once` must be triggered manually each cycle |
| No pruning | Artifacts accumulate — manual cleanup required |
| Backend binary required for success | Execution without `kodo`/`aider` records `backend_error` — not a pipeline bug |
| SwitchBoard must be running | All routing calls fail if WorkStation stack is down |
| No run search | `console runs` shows recent runs by time; no filtering by status or goal |
| Partial runs counted | `console runs` shows partial artifacts alongside complete runs |
