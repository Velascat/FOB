# Log

_Chronological continuity log. Decisions, stop points, what changed and why._
_Not a task tracker — that's backlog.md. Keep entries concise and dated._

## Recent Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
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

_(none recorded)_

## Notes

_Free-form scratch space. Clear periodically._
