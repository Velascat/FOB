# Guardrails

## Safe Branch Practices

FOB warns when launched from `main` or `master`. This is not a hard block — it's a reminder.

Claude's `standing-orders.md` (in each repo's `.fob/`) enforces the actual discipline:
- Claude will not commit to protected branches
- Claude will stop and ask for a working branch before making changes

Create a working branch before launching:
```bash
cd <repo>
git checkout -b feature/<description>
fob brief
```

## Intended Claude Usage Model

Claude operates as an AI operator inside the workspace. The expected loop:

1. **Read mission files** — Claude reads `.fob/` to understand current context
2. **Summarize plan** — Claude describes what it intends to do before any edits
3. **Edit** — targeted changes, not rewrites
4. **Validate** — run `fob test` or `fob audit`
5. **Summarize result** — what changed, what passed or failed
6. **Update mission files** — Claude updates `.fob/objectives.md` and `.fob/mission-log.md`

This loop is described in `.fob/standing-orders.md` in each repo.

## Helper Commands

Prefer wrapper commands over raw shell sequences:

| Command | Replaces |
|---------|---------|
| `fob test` | `pytest -x -v` / `npm test` / etc. |
| `fob audit` | `ruff check` / `tsc --noEmit` / custom lint |
| `fob status` | `git status` + session/branch info |
| `fob resume` | reading `.fob/` files manually |
| `fob cheat` | looking up keybindings |

These are stable entrypoints. Claude should use them rather than constructing long shell pipelines.

## Filesystem Scope

Intended writable scope for Claude:
- The configured `repo_root` and its children
- `<repo>/.fob/` for mission file updates
- `/tmp/` for transient files

Claude should not write outside `repo_root` without explicit operator confirmation.

## What Is Not Automated

By design, the following require explicit operator action:

- Pushing to remote branches
- Creating pull requests
- Merging branches
- Deploying / releasing
- Modifying CI/CD configuration

These are human-in-the-loop checkpoints. FOB is a local workspace, not a deployment pipeline.
