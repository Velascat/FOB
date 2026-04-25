# Guardrails

## Safe Branch Practices

OperatorConsole warns when launched from `main` or `master`. This is not a hard block — it's a reminder.

Claude's `directives.md` (in each repo's `.console/`) enforces the actual discipline:
- Claude will not commit to protected branches
- Claude will stop and ask for a working branch before making changes

Create a working branch before launching:
```bash
cd <repo>
git checkout -b feature/<description>
console
```

## Intended Claude Usage Model

Claude operates as an AI operator inside the workspace. The expected loop:

1. **Read mission files** — Claude reads `.console/` to understand current context
2. **Summarize plan** — Claude describes what it intends to do before any edits
3. **Edit** — targeted changes, not rewrites
4. **Validate** — run `console test` or `console audit`
5. **Summarize result** — what changed, what passed or failed
6. **Update mission files** — Claude updates `.console/objectives.md` and `.console/mission-log.md`

This loop is described in `.console/directives.md` in each repo.

## Helper Commands

Prefer wrapper commands over raw shell sequences:

| Command | Replaces |
|---------|---------|
| `console test` | `pytest -x -v` / `npm test` / etc. |
| `console audit` | `ruff check` / `tsc --noEmit` / custom lint |
| `console status` | `git status` + session / layout / branch info |
| `console map` | full structured state snapshot |
| `console resume` | reading `.console/` files manually |
| `console reset` | manually killing sessions and deleting state files |
| `console clear` | deleting `.console/layout.json` + `.console/layout.kdl` manually |
| `console cheat` | looking up keybindings |

These are stable entrypoints. Claude should use them rather than constructing long shell pipelines.

## Filesystem Scope

Intended writable scope for Claude:
- The configured `repo_root` and its children
- `<repo>/.console/` for mission file updates
- `/tmp/` for transient files

Claude should not write outside `repo_root` without explicit operator confirmation.

## Claude Process Lifecycle

Understanding what happens to Claude when Zellij state changes:

| Action | Claude process |
|--------|---------------|
| Close terminal window | Keeps running — Zellij session stays alive in background |
| Detach (Ctrl+o d) | Keeps running — session persists, re-attach with `console attach` |
| Kill Claude pane (Ctrl+p x) | Process dies — that tab's Claude is gone |
| `console kill` | Everything dies — session and all panes killed (confirms first) |

**Closing the terminal does not kill Claude.** Zellij sessions persist as background processes. The panes — Claude, shell, lazygit — keep running. Re-attach at any time with:
```bash
console attach        # re-attach to the running console session
console               # from inside a known repo: adds/re-opens that repo's tab
```

**Key point:** Even if Claude is killed, `claude --continue` on the next `console open` resumes the conversation from where it left off. Conversation history is preserved by Claude Code; only work that was mid-execution is lost.

Recovery path after an accidental kill: `console open` restores everything.

### Letting Claude Work Autonomously

To kick off a task and walk away:

1. Give Claude instructions in the pane
2. Detach: `Ctrl+o d` (or just close the terminal — same result)
3. Come back later: `console attach` or `console` from the repo

Claude continues working. When you re-attach, the pane shows exactly what happened.

For cross-repo autonomous work (e.g. Claude on OperationsCenter monitoring OperatorConsole state), the pattern is:
- Run `console open operations_center operator_console` to open both repos in tabs
- Give Claude in the OperationsCenter tab explicit instructions and a clear stopping condition
- Detach — both Claude instances keep running independently

## What Is Not Automated

By design, the following require explicit operator action:

- Pushing to remote branches
- Creating pull requests
- Merging branches
- Deploying / releasing
- Modifying CI/CD configuration

These are human-in-the-loop checkpoints. OperatorConsole is a local workspace, not a deployment pipeline.
