"""runlog_command — the `runlog` console command.

`runlog start AREA -- CMD` starts a run detached and returns once its
directory exists; `runlog [AREA]` shows what an area's runs are doing and
how they ended, `--wait` and `--follow` block until it is idle; `runlog
reindex` rebuilds
runs.tsv from the run directories (`runlog.reindex`). The run itself is
written by `runlog.Run`; this module only reads it and starts processes.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from labkit.formats.runs import metrics_path
from labkit.formats import console, repo
from labkit.formats.runs import (
    COMPLETED,
    FAILED_STATES,
    RUN_ID_TIME,
    RunConfigError,
    read_failure,
    read_metrics,
    run_dirs,
    summarize,
)
from labkit.formats.answering_run import newest_completed
from labkit.run.runlog import ActiveRun, active, notify_desktop, reindex


def _newest_output(area: Path) -> str:
    """One line about the freshest file in <area>/output/ — the improvised
    `tail`/`wc` poll, done once and correctly."""
    out_dir = area / "output"
    if not out_dir.is_dir():
        return ""
    files = [p for p in out_dir.iterdir() if p.is_file()]
    if not files:
        return ""
    newest = max(files, key=lambda p: p.stat().st_mtime)
    try:
        lines = sum(1 for _ in newest.open("rb"))
    except OSError:
        return ""
    age = int(time.time() - newest.stat().st_mtime)
    return f"output: {newest.name} {lines} line(s), last write {age}s ago"


def _print_status(area: str, live: list[ActiveRun]) -> None:
    if not live:
        print(f"{area}: no open runs")
    for r in live:
        pid, script = (r.config.pid, r.config.script) if r.config else (None, None)
        print(f"{r.run_id}  {r.state:12s} pid={pid}  {script}")
        if r.config is None:
            print(f"    {r.error}")
        else:
            shown = r.config.as_record()["config"]  # as stored: key order, null
            print(f"    {json.dumps(shown, ensure_ascii=False)[:160]}")


def _print_finished(area: Path) -> None:
    """One line per finished run: what it is, whether its code was committed,
    how it was started — `runlog <area>` after the open runs."""
    done = []
    for rd in run_dirs(Path(area)):
        if rd.error is not None:
            print(f"  {rd.dir.name}  unreadable — {rd.error}")
            continue
        if rd.config is None:
            continue
        s = summarize(rd.dir, rd.config)
        if s.state == COMPLETED:
            done.append(s)
    if not done:
        return
    print(f"finished runs ({len(done)}, oldest first):")
    for s in done:
        kind = f"{s.run_kind} run, " + (
            f"derived from {s.derived_from} (its rows re-evaluated)"
            if s.derived_from
            else "fresh run of the script"
            + (f" (models: {', '.join(s.models)})" if s.models else "")
        )
        commit = s.git.removesuffix("+dirty")
        if s.uncommitted_bytes:
            code = (
                f"code {commit} + uncommitted changes "
                f"({s.uncommitted_bytes} B in uncommitted.patch)"
            )
        elif s.git.endswith("+dirty"):
            code = f"code {commit}, tracked files committed (untracked files present)"
        else:
            code = f"code {commit}, committed"
        print(f"  {s.run_id}  {kind} · {code}")
        print(f"      started as: {s.command or '(not recorded)'}")


def _finished_line(area: Path) -> str:
    """The newest COMPLETED run, by its own marker — a run whose metrics
    landed but whose finalization broke off is not a finished run."""
    try:
        last = newest_completed(area, with_repeats=True)
    except RunConfigError as exc:
        return f"last finished: cannot say — {exc}"
    if last is None:
        return "no finished runs"
    m = read_metrics(metrics_path(last))
    keys = ", ".join(list(m)[:6])
    return f"last finished: {last.name} ({keys})"


def _wait(
    area: str, max_seconds: float | None, interval: float, follow: bool, notify: bool
) -> int:
    """Block until the area has no open runs. Exit codes are the contract:
    0 = no open runs (finished) · 2 = a run crashed · 3 = still running at
    --max-seconds. The waiter only OBSERVES — the run owns its process group
    and its lock, so a killed waiter is harmless (verified in the detach
    probe: killing the waiter left run and lock untouched)."""
    t0 = time.monotonic()
    apath = Path(area)
    while True:
        live = active(area)
        if not live:
            print(f"{area}: no open runs — {_finished_line(apath)}")
            if notify:
                notify_desktop("runlog --wait", f"{area}: no open runs")
            return 0
        # Exit 2 covers every failed state: a machine only needs "did not
        # finish cleanly", a human tells them apart by state and message.
        WHY = {
            "crashed": "config.json without metrics.json",
            "unfinalized": "metrics.json without completion.json — "
            "finalization broke off, numbers must not be "
            "reported",
            "corrupt": "completion.json without metrics.json — the results are gone",
            "unreadable": "config.json cannot be read — the run's record is damaged",
        }
        failed = [r for r in live if r.state in FAILED_STATES]
        if failed:
            for r in failed:
                state = r.state
                why = r.error or f"{r.dir}: {WHY.get(state, '')}"
                failure = read_failure(r.dir)
                if failure:
                    why += f" — broke off with {failure}"
                print(
                    f"{r.run_id}  {state.upper()}  pid={r.config.pid if r.config else None}  "
                    f"{r.config.script if r.config else None}  ({why})"
                )
            if notify:
                notify_desktop("runlog --wait", f"{area}: run {failed[0].state}")
            return 2
        if follow:
            stamp = time.strftime("%H:%M:%S")
            extra = _newest_output(apath)
            print(
                f"[{stamp}] {len(live)} open run(s): "
                + ", ".join(r.run_id for r in live)
                + (f" · {extra}" if extra else ""),
                flush=True,
            )
        if max_seconds is not None and time.monotonic() - t0 >= max_seconds:
            extra = _newest_output(apath)
            print(
                f"{area}: still running after {int(max_seconds)}s — "
                + ", ".join(
                    f"{r.run_id} pid={r.config.pid if r.config else None}" for r in live
                )
                + (f" · {extra}" if extra else "")
                + "\nre-check: runlog "
                + area
                + " --wait"
            )
            return 3
        time.sleep(interval)


def _start(argv: list[str]) -> int:
    """runlog start AREA [--log FILE] -- <cmd ...>: detach a run and return.

    AREA is named, not guessed from the command: the default log goes to
    AREA/output/ and the printed wait command names AREA. Until 0.90.0 the
    log went to `output/` under the working directory — the repo root when
    started from there, as the task sheets ask — and a cold agent looked for
    it in the area (cloud judge probe, 2026-10-14).

    setsid puts the run in its OWN process group and session: the shell that
    started it — and any tool timeout that kills that shell's group — cannot
    take the run down with it (scar 2026-08-13). LABKIT_DETACHED=1 tells the
    `run_kind='measurement'` gate inside the script that the detach already happened.
    """
    import argparse

    ap = argparse.ArgumentParser(
        prog="runlog start",
        usage="runlog start AREA [--log FILE] -- <cmd ...>",
        description="Start a command detached (own session via setsid), "
        "output to a log file, return immediately.",
    )
    ap.add_argument("area", type=Path, help="the experiment area the run belongs to")
    ap.add_argument(
        "--log", default=None, help="log file (default: AREA/output/start-<ts>.log)"
    )
    words, cmd = console.split_command(argv)
    if cmd is None:
        ap.parse_args(argv)  # --help prints and exits; a bad flag is named
        ap.error(
            "no command given — usage: runlog start AREA [--log FILE] -- <cmd ...>"
        )
    args = ap.parse_args(words)
    if not cmd:
        ap.error(
            "no command given — usage: runlog start AREA [--log FILE] -- <cmd ...>"
        )
    area: Path = args.area
    if not area.is_dir():
        ap.error(
            f"{area} is not a directory — name the experiment area first: "
            f"runlog start AREA -- <cmd ...>"
        )
    log = (
        Path(args.log)
        if args.log
        else area / "output" / f"start-{time.strftime(RUN_ID_TIME)}.log"
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "LABKIT_DETACHED": "1"}
    with log.open("ab") as fh:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=fh,
            stderr=fh,
            start_new_session=True,
            env=env,
        )
    print(f"started detached: pid={proc.pid}  log={log}")
    print(f"status:  runlog {area}        wait:  runlog {area} --wait")
    return 0


def main(argv: list[str]) -> int:
    """Status, wait, follow or start — the run monitor of record."""
    if argv and argv[0] == "start":
        return _start(argv[1:])
    if argv and argv[0] == "reindex":
        try:
            area = repo.area_path(argv[1]) if len(argv) > 1 else Path(".")
        except repo.AmbiguousArea as exc:
            console.refuse("runlog", str(exc))
            return 2
        if not area.is_dir():
            console.refuse("runlog", repo.no_such_area(area))
            return 2
        return reindex(area)
    import argparse

    ap = argparse.ArgumentParser(
        prog="runlog",
        description="List an experiment area's runs: the open ones (not yet "
        "completed) with state (running/unknown/crashed/unfinalized/corrupt), "
        "script and frozen config; then the finished ones — what each is "
        "(a run, or derived from which), whether its code was committed, "
        "and the command that started it. "
        "'Nachsehen statt nachfragen' — "
        "check this before starting a run in a shared repo. "
        "`--wait` blocks until the area is idle (exit 0), a run "
        "crashed (exit 2) or --max-seconds passed (exit 3); "
        "`--follow` prints a status line per interval until idle; "
        "`runlog start <area> -- <cmd>` detaches a run (own session, "
        "log file) and returns. "
        "`runlog reindex <area>` appends rows for completed "
        "runs the index missed.",
    )
    ap.add_argument(
        "area",
        nargs="?",
        default=".",
        help="experiment area holding a runs/ dir (default: .)",
    )
    ap.add_argument(
        "--wait",
        action="store_true",
        help="block until no open runs; exit 0/2/3 (idle/crashed/"
        "still running at --max-seconds)",
    )
    ap.add_argument(
        "--follow",
        action="store_true",
        help="like --wait but unbounded, one status line per "
        "interval (for a human terminal)",
    )
    ap.add_argument(
        "--max-seconds",
        type=float,
        default=90.0,
        help="--wait: give up after this long (default 90 — "
        "safely under the shell tool's timeout)",
    )
    ap.add_argument(
        "--interval",
        type=float,
        default=None,
        help="poll interval in s (default: 2 for --wait, 5 for --follow)",
    )
    ap.add_argument(
        "--notify", action="store_true", help="macOS notification when the wait ends"
    )
    args = ap.parse_args(argv)
    # a misspelt area read as "no open runs", exit 0 — and `--wait` as
    # finished (audit 2026-10-15); `reindex` refused it, status did not
    try:
        area = repo.area_path(args.area)
    except repo.AmbiguousArea as exc:
        console.refuse("runlog", str(exc))
        return 2
    if not area.is_dir():
        console.refuse("runlog", repo.no_such_area(area))
        return 2
    shown = str(area)
    if args.follow:
        return _wait(shown, None, args.interval or 5.0, True, args.notify)
    if args.wait:
        return _wait(shown, args.max_seconds, args.interval or 2.0, False, args.notify)
    _print_status(shown, active(area))
    _print_finished(area)
    return 0


def cli() -> None:
    """Entry point for the installed `runlog` command."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
