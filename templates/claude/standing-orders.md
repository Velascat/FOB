# Guardrails

Operating rules for Claude in this repo.

## Branch Policy

- Do not commit directly to `main` or `master`.
- Before making any changes, confirm you are on a feature branch.
- If on a protected branch, stop and ask the operator to create a working branch.

## Before Acting

1. Read `.fob/current-focus.md` — understand the active objective.
2. Read `.fob/todo.md` — check what's in progress and what's next.
3. Read `.fob/session.md` — review recent decisions and context.
4. Summarize your plan before making edits.

## During Work

- Run `./dev test` before and after changes, not broad validation suites.
- Use `./dev audit` for linting and static checks.
- Prefer `./dev status` over raw git commands to check workspace state.
- Prefer small, targeted edits over large rewrites.

## After Meaningful Progress

- Update `.fob/todo.md` to reflect completed and remaining work.
- Update `.fob/session.md` with decisions made and rationale.
- Summarize what changed and what's next.

## What Not to Do

- Do not run destructive commands (`rm -rf`, `git reset --hard`) without explicit operator confirmation.
- Do not push to remote branches without the operator's explicit request.
- Do not modify files outside the repo root without explicit justification.
