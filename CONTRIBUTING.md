# Contributing to OperatorConsole

OperatorConsole is a local operator console for Claude-driven development — a Zellij session manager with context-file continuity and an execution pipeline that delegates to OperationsCenter.

## Before You Start

- Check open issues to avoid duplicate work
- For significant changes, open an issue first to discuss the approach
- All contributions must pass the test suite and linter before merging

## Development Setup

```bash
git clone https://github.com/Velascat/OperatorConsole.git
cd OperatorConsole
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Dependencies: `zellij`, `lazygit`, `fzf`, `python3 >= 3.11`

## Running Tests

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/ -v
```

## Running the Linter

```bash
ruff check src/
```

## Project Structure

```
src/operator_console/
  cli.py          # main dispatcher
  launcher.py     # Zellij session/tab management
  bootstrap.py    # .console/ context generation
  delegate.py     # delegation to OperationsCenter
  auto_once.py    # single-cycle autonomy run
  observer.py     # repo + goal observation
  commands.py     # helper command implementations
  status_viewer.py # status pane loop
config/profiles/  # YAML profile definitions
templates/console/ # .console/ state file templates
```

## What Belongs Here

OperatorConsole is the **operator UX layer only**. It must not contain:
- Planning or proposal logic (belongs in OperationsCenter)
- Routing logic (belongs in SwitchBoard)
- Adapter/execution logic (belongs in OperationsCenter backends)

If you are unsure whether a feature belongs in OperatorConsole, open an issue first.

## Pull Requests

- Keep PRs focused — one concern per PR
- Write or update tests for any changed behavior
- Update relevant docs in `docs/` if the change affects user-facing behavior
- Reference related issues in the PR description

## Commit Style

Use conventional commit prefixes:

| Prefix | Use for |
|--------|---------|
| `feat:` | new user-facing feature |
| `fix:` | bug fix |
| `refactor:` | internal restructure, no behavior change |
| `docs:` | documentation only |
| `test:` | test additions or fixes |
| `chore:` | tooling, CI, dependency updates |

## Code of Conduct

This project follows the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md). By participating you agree to uphold its standards.
