# Log

_Chronological continuity log. Decisions, stop points, what changed and why._
_Not a task tracker — that's backlog.md. Keep entries concise and dated._

## Recent Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| README ## What OperatorConsole Is Not section | Replaced inline "OperatorConsole is not a neutral bootstrap script..." sentence with a proper `## What OperatorConsole Is Not` H2 section listing the four explicit anti-scopes. Required by Custodian R4 README detector (newly landed). | 2026-05-06 |
| README workspace-layout diagrams corrected (round 2) | First pass still drew shell/status as horizontally split panes; they're actually a Zellij **stack** (overlapping, switchable). Redrew center and right columns with explicit stack notation so the diagram matches launcher.py and Zellij's actual rendering | 2026-05-06 |
| README workspace-layout diagrams corrected | Single-repo and multi-repo ASCII diagrams + descriptions described an older layout (status bottom-left, shell as center pane, logs on right; stacked lazygits in multi). Replaced with current: lazygit | claude/codex/aider | shell+status (single); git_watcher | claude/codex/aider | shell+status (multi). Source of truth: src/operator_console/launcher.py | 2026-05-06 |
| README ownership boundary: contracts attributed to CxRP/RxP | Section listed contracts under OperationsCenter; canonical cross-repo contracts now live in CxRP/RxP. Updated to map Dockerfiles→WS, routing→SB, adapters→OC, contracts→CxRP/RxP | 2026-05-06 |
| Add ExecutorRuntime, SourceRegistry, RxP to platform group | Three new repos joined the platform tab + git-dirty watcher; new profile yamls (bootstrap_files empty until repos grow .console/), `.gitignore` allowlist updated to track them | 2026-05-06 |
| C41 json.dumps ensure_ascii=False | 13 json.dumps calls across 9 files now include ensure_ascii=False | 2026-05-03 |
| Ruff style violations resolved | E701/E702/E741/F401 across clean.py, cli.py, delegate.py, observer.py, watcher_status_pane.py, git_watcher.py, commands.py, auto_once.py, tab_capture.py | 2026-05-03 |
| CLAUDE.md: simplify console update instruction | "Before each commit" → "After meaningful progress" | 2026-05-02 |
| cmd_install restored as `console symlink` | Was dead code (no CLI dispatch); added case "symlink" in cli.py; symlinks CONSOLE_DIR/console → ~/.local/bin/console | 2026-05-02 |
| get_aider_command implemented | Old version was a stub printing an error; now a real launcher (profile["aider"]: bin/model/auto_commits); aider pane added to layout alongside claude/codex | 2026-05-02 |
| spawn_update_clis_background restored | _UPDATE_LOG constant re-added; wired into console update --background; fire-and-forget subprocess.Popen | 2026-05-02 |
| read_decision wired into run_summary | Reads decision.json from run dir; run_summary now includes decision_basis and decision_confidence from OC's routing decision | 2026-05-02 |
| queue.remove wired into console queue cancel | Short-prefix resolution so cancel abc matches abcdef1234; delegates to queue.remove() | 2026-05-02 |
| check_branch gains force param; --force-branch flag | console open <profile> --force-branch suppresses protected-branch warning entirely; wired through cli → _run_open → launch → check_branch | 2026-05-02 |
| any_backend_missing gates run_providers exit code | providers.run_providers() now returns 1 when any backend is absent (unless --wait); was tracking the bool but not acting on it | 2026-05-02 |
| CxrpExecutionResult fully implemented | parse_execution_result(payload) validates + deserializes to typed CxrpExecutionResult; summarize_execution_result() takes typed object; T2 exclusion removed (tests now have real asserts) | 2026-05-02 |
| .console/ migrated to standard naming | active-mission/standing-orders/mission-log/objectives → task/guidelines/log/backlog | 2026-05-02 |

## Stop Points

- CI doctor: drop stale D7 exclude_paths (2026-05-06, on `main`): D7 (dead method param) was retired in Custodian's tool-first deprecation pass. `.custodian/config.yaml` still referenced D7 under exclude_paths, which `custodian-doctor --strict` flagged as an unknown detector. Removed the block.

- CI license header (2026-05-06, on `main`): Added missing SPDX header to `.vulture_whitelist.py`. Same fix pattern applied across other Velascat repos. CI license-header job now passes.

## Notes

_Free-form scratch space. Clear periodically._
