"""fob last — inspect the most recent execution run."""
from __future__ import annotations

from pathlib import Path

from fob.runs import latest_run, list_runs, run_summary, runs_root

_C = {
    "R": "\033[0m", "B": "\033[1m", "DIM": "\033[2m",
    "RED": "\033[31m", "GRN": "\033[32m", "YLW": "\033[33m",
    "CYN": "\033[36m", "MAG": "\033[35m",
}


def _c(text: str, *keys: str) -> str:
    return "".join(_C[k] for k in keys) + text + _C["R"]


def _status_color(status: str, success: bool | None) -> str:
    if success is True:
        return _c(status, "GRN")
    if status in ("timeout", "skipped"):
        return _c(status, "YLW")
    return _c(status, "RED")


def run_last(args: list[str]) -> int:
    use_json = "--json" in args

    root: Path | None = None
    for i, a in enumerate(args):
        if a == "--root" and i + 1 < len(args):
            root = Path(args[i + 1])

    run_dir = latest_run(root)
    if run_dir is None:
        if use_json:
            import json
            print(json.dumps({"error": "no runs found", "runs_root": str(runs_root())}))
        else:
            print(_c("  No runs found.", "DIM"))
            print(_c(f"  Expected location: {runs_root()}", "DIM"))
            print(_c("  Run `fob delegate` or `fob demo` to create a run.", "DIM"))
        return 1

    summary = run_summary(run_dir)

    if use_json:
        import json
        print(json.dumps(summary, indent=2, default=str))
        return 0

    print(_c("\n  fob last", "B", "CYN") + _c(" — most recent execution run", "DIM"))
    print()

    run_id = summary["run_id"]
    status = summary["status"]
    success = summary["success"]
    executed = summary["executed"]
    lane = summary["selected_lane"]
    backend = summary["selected_backend"]
    written_at = summary.get("written_at", "?")
    goal_text = summary.get("goal_text")
    task_type = summary.get("task_type")
    repo_key = summary.get("repo_key")
    failure_category = summary.get("failure_category")
    failure_reason = summary.get("failure_reason")
    partial = summary.get("partial", False)
    artifacts_dir = summary["artifacts_dir"]

    status_disp = _status_color(status, success)

    if partial:
        status_disp = _c("partial", "YLW")

    print(f"  {_c('Run ID   ', 'DIM')} {_c(run_id, 'B')}")
    print(f"  {_c('Status   ', 'DIM')} {status_disp}")
    if executed is not None:
        exec_disp = _c("yes", "GRN") if executed else _c("no (policy gate)", "YLW")
        print(f"  {_c('Executed ', 'DIM')} {exec_disp}")
    print(f"  {_c('Lane     ', 'DIM')} {lane}  {_c('→', 'DIM')} {backend}")
    if written_at and written_at != "?":
        print(f"  {_c('Written  ', 'DIM')} {written_at}")
    print()

    if goal_text or task_type or repo_key:
        print(_c("  Task", "B"))
        if goal_text:
            print(f"    {_c('goal     ', 'DIM')} {goal_text}")
        if task_type:
            print(f"    {_c('type     ', 'DIM')} {task_type}")
        if repo_key:
            print(f"    {_c('repo     ', 'DIM')} {repo_key}")
        print()

    if failure_category or failure_reason:
        print(_c("  Failure", "B", "RED"))
        if failure_category:
            print(f"    {_c('category ', 'DIM')} {failure_category}")
        if failure_reason:
            snippet = failure_reason[:120] + ("…" if len(failure_reason) > 120 else "")
            print(f"    {_c('reason   ', 'DIM')} {snippet}")
        print()

    print(f"  {_c('·', 'DIM')} artifacts: {_c(artifacts_dir, 'DIM')}")

    # Show all recent runs if --all
    if "--all" in args:
        all_runs = list_runs(root)
        if len(all_runs) > 1:
            print()
            print(_c("  Recent runs", "B"))
            for rd in reversed(all_runs[-10:]):
                s = run_summary(rd)
                mark = _c("✓", "GRN") if s.get("success") else _c("✗", "RED")
                ts = (s.get("written_at") or "?")[:19].replace("T", " ")
                print(f"    {mark}  {_c(s['run_id'][:36], 'DIM')}  {ts}  {s['status']}")

    print()
    return 0
