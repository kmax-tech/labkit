"""runlog_command — the `runlog` console command.

`runlog start AREA -- CMD` starts a run detached and returns once its
directory exists (or the command ended first, said so); `runlog [AREA]` shows what an area's runs are doing and
how they ended, `--wait` and `--follow` block until it is idle — no open
run and no command `runlog start` detached still running (`detached`) —
or a run, or a started command, ended without finishing cleanly;
`runlog reindex` rebuilds
runs.tsv from the run directories (`runlog.reindex`). The run itself is
written by `runlog.Run`; this module only reads it and starts processes.
"""

from __future__ import annotations

import json
import os
import shlex
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
from labkit.run import detached
from labkit.run.detached import DetachedStart
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


def _unopened(
    starts: list[DetachedStart], live: list[ActiveRun]
) -> list[DetachedStart]:
    """The STARTS still running that no open run of LIVE names by its pid:
    a stamped script prepares its rows before `runlog.run` opens the
    record; a wrapper process's run records another pid (`_unopened_words`
    tells the two apart)."""
    pids = {r.config.pid for r in live if r.config is not None}
    return [s for s in starts if s.running and s.pid not in pids]


def _unopened_words(live: list[ActiveRun]) -> tuple[str, str]:
    """(state, sentence) of an unopened start beside LIVE: with no open run
    in the area its run has no record yet; beside an open run it may be
    that run's wrapper or a run still to open — only its pid matched none."""
    if not live:
        return "starting", "no run record yet"
    return "active", "started process still active; matched to no open run by its pid"


def _failed_starts(area: Path, starts: list[DetachedStart]) -> list[DetachedStart]:
    """The STARTS of AREA that ended without finishing cleanly and without a
    run record bound to them: an exit other than 0, or none recorded, and no
    run record that names their pid and started no earlier than they did (a
    pid the system reused for an older run binds nothing). A bound run
    tells its own state; an exit 0 without one is a command that opened no
    run, as `runlog start` says when it sees it end."""
    bound = {
        (rd.config.pid, rd.config.started)
        for rd in run_dirs(area)
        if rd.config is not None
    }

    def is_bound(s: DetachedStart) -> bool:
        return any(pid == s.pid and started >= s.started for pid, started in bound)

    return [s for s in starts if not s.running and s.exit != 0 and not is_bound(s)]


def _failed_start_line(s: DetachedStart) -> str:
    """One line for a failed start: what ended, how, where its log is."""
    return (
        f"(detached)  ENDED  pid={s.pid}  {shlex.join(s.command)}  "
        f"({detached.exit_words(s)} without a run record — check the log: {s.log})"
    )


def _print_status(
    area: str,
    live: list[ActiveRun],
    pending: list[DetachedStart],
    failed_starts: list[DetachedStart],
) -> None:
    if not live and not pending and not failed_starts:
        print(f"{area}: no open runs")
    for r in live:
        pid, script = (r.config.pid, r.config.script) if r.config else (None, None)
        print(f"{r.run_id}  {r.state:12s} pid={pid}  {script}")
        if r.config is None:
            print(f"    {r.error}")
        else:
            shown = r.config.as_record()["config"]  # as stored: key order, null
            print(f"    {json.dumps(shown, ensure_ascii=False)[:160]}")
    state, unopened = _unopened_words(live)
    for s in pending:
        print(f"(detached)  {state:12s} pid={s.pid}  {shlex.join(s.command)}")
        print(f"    started {s.started} by runlog start, {unopened} — log: {s.log}")
    for s in failed_starts:
        print(f"(detached)  {'ended':12s} pid={s.pid}  {shlex.join(s.command)}")
        print(
            f"    started {s.started} by runlog start, {detached.exit_words(s)} "
            f"without a run record — check the log: {s.log} (the next "
            f"`runlog start` in this area clears this line)"
        )


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


#: why a run in a failed state is one, for `--wait`'s line
_FAILED_WHY = {
    "crashed": "config.json without metrics.json",
    "unfinalized": "metrics.json without completion.json — "
    "finalization broke off, numbers must not be "
    "reported",
    "corrupt": "completion.json without metrics.json — the results are gone",
    "unreadable": "config.json cannot be read — the run's record is damaged",
}


def _print_failures(
    failed: list[ActiveRun], failed_starts: list[DetachedStart]
) -> None:
    """`--wait`'s exit-2 lines: each failed start, then each run in a failed
    state. Exit 2 covers every failed state: a machine only needs "did not
    finish cleanly", a human tells them apart by state and message."""
    for s in failed_starts:
        print(_failed_start_line(s))
    for r in failed:
        why = r.error or f"{r.dir}: {_FAILED_WHY.get(r.state, '')}"
        failure = read_failure(r.dir)
        if failure:
            why += f" — broke off with {failure}"
        print(
            f"{r.run_id}  {r.state.upper()}  pid={r.config.pid if r.config else None}  "
            f"{r.config.script if r.config else None}  ({why})"
        )


def _wait(
    area: str, max_seconds: float | None, interval: float, follow: bool, notify: bool
) -> int:
    """Block until the area is idle: no open runs and no command `runlog
    start` detached that still runs without one (`_unopened`). Exit codes
    are the contract: 0 = idle (finished) · 2 = a run crashed, or a started
    command ended without a run record and not with exit 0
    (`_failed_starts`) · 3 = still running at --max-seconds. The waiter
    only OBSERVES — the run owns its process group and its lock, so a
    killed waiter is harmless (verified in the detach probe: killing the
    waiter left run and lock untouched)."""
    t0 = time.monotonic()
    apath = Path(area)
    while True:
        live = active(area)
        starts = detached.starts(apath)
        pending = _unopened(starts, live)
        failed_starts = _failed_starts(apath, starts)
        if not live and not pending and not failed_starts:
            print(f"{area}: no open runs — {_finished_line(apath)}")
            if notify:
                notify_desktop("runlog --wait", f"{area}: no open runs")
            return 0
        failed = [r for r in live if r.state in FAILED_STATES]
        if failed or failed_starts:
            _print_failures(failed, failed_starts)
            if notify:
                what = f"run {failed[0].state}" if failed else "started command ended"
                notify_desktop("runlog --wait", f"{area}: {what}")
            return 2
        _, unopened = _unopened_words(live)
        starting = [f"pid={s.pid} (detached, {unopened})" for s in pending]
        if follow:
            stamp = time.strftime("%H:%M:%S")
            extra = _newest_output(apath)
            print(
                f"[{stamp}] {len(live)} open run(s): "
                + ", ".join([r.run_id for r in live] + starting)
                + (f" · {extra}" if extra else ""),
                flush=True,
            )
        if max_seconds is not None and time.monotonic() - t0 >= max_seconds:
            extra = _newest_output(apath)
            print(
                f"{area}: still running after {int(max_seconds)}s — "
                + ", ".join(
                    [
                        f"{r.run_id} pid={r.config.pid if r.config else None}"
                        for r in live
                    ]
                    + starting
                )
                + (f" · {extra}" if extra else "")
                + "\nre-check: runlog "
                + area
                + " --wait"
            )
            return 3
        time.sleep(interval)


#: how long `runlog start` waits for the run's directory by default: the
#: script's gates and provenance (hashing its data) come before it
START_WAIT_S = 60.0
#: how long `runlog start` waits for the supervisor to name the command it
#: started (an interpreter's start-up and one fork: well under a second)
SUPERVISOR_WAIT_S = 30.0


def _await_supervisor(
    area: Path, proc: subprocess.Popen[bytes], log: Path, interval: float = 0.05
) -> int | None:
    """The pid of the command the supervisor PROC started, once its record
    in AREA names it (`detached.supervise`). None, refused with the log's
    tail, when the supervisor ended first (the command could not be
    started) or named none within SUPERVISOR_WAIT_S."""
    t0 = time.monotonic()
    while True:
        code = proc.poll()  # before the look: a record written just before exit is seen
        named = [s.pid for s in detached.starts(area) if s.supervisor == proc.pid]
        if named:
            return named[0]
        if code is not None or time.monotonic() - t0 >= SUPERVISOR_WAIT_S:
            tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
            why = (
                f"the command could not be started (exit {code})"
                if code is not None
                else f"its supervisor (pid {proc.pid}) named no command within "
                f"{int(SUPERVISOR_WAIT_S)}s"
            )
            console.refuse(
                "runlog start", f"{why} — log {log}:\n  " + "\n  ".join(tail)
            )
            return None
        time.sleep(interval)


def _await_run(
    area: Path,
    before: set[str],
    proc: subprocess.Popen[bytes],
    pid: int,
    log: Path,
    max_seconds: float,
    interval: float = 0.2,
) -> int:
    """Block until the run directory of the command PID (started by the
    supervisor PROC, whose exit is the command's) exists in AREA (a
    directory not in BEFORE): exit 0, the run named. The command ending
    first: exit 0 when it ended cleanly without a run (nothing to wait for),
    2 when it failed, with the log's last lines. Still alive after
    MAX_SECONDS without one: exit 3, and `runlog AREA --wait` waits for
    the command (`detached`)."""
    t0 = time.monotonic()
    while True:
        code = proc.poll()  # before the look, so a run made just before exit is seen
        new = [rd for rd in run_dirs(area) if rd.dir.name not in before]
        # this command's run, where its record names its pid; else the newest
        # new one (a wrapper shell records another pid)
        own = [rd for rd in new if rd.config is not None and rd.config.pid == pid]
        if new:
            rd = (own or new)[-1]
            if rd.error is not None:
                console.refuse(
                    "runlog start",
                    f"run {rd.dir.name}: its record does not read — {rd.error}",
                )
                return 2
            if rd.config is not None:
                print(f"run: {rd.dir.name}")
                return 0
        if code is not None:
            if code == 0:
                print(
                    f"the command ended (exit 0) without a run in {area} — nothing to wait for"
                )
                return 0
            tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
            console.refuse(
                "runlog start",
                f"the command ended with exit {code} before its run existed — "
                f"log {log}:\n  " + "\n  ".join(tail),
            )
            return 2
        if time.monotonic() - t0 >= max_seconds:
            print(
                f"no run in {area} after {int(max_seconds)}s; pid {pid} is still "
                f"starting — `runlog {area} --wait` waits for it"
            )
            return 3
        time.sleep(interval)


def _start(argv: list[str]) -> int:
    """runlog start AREA [--log FILE] [--max-seconds S] -- <cmd ...>: detach
    a run and return once its directory exists (`_await_run`: exit 0 the
    run named or the command ended cleanly without one, 2 it failed first,
    3 still starting after S seconds).

    AREA is named, not guessed from the command: the default log goes to
    AREA/output/ and the printed wait command names AREA. Until 0.90.0 the
    log went to `output/` under the working directory — the repo root when
    started from there, as the task sheets ask — and a cold agent looked for
    it in the area (cloud judge probe, 2026-10-14).

    setsid puts the run in its OWN process group and session: the shell that
    started it — and any tool timeout that kills that shell's group — cannot
    take the run down with it (scar 2026-08-13). LABKIT_DETACHED=1 tells the
    `run_kind='measurement'` gate inside the script that the detach already happened.
    A supervisor in that session starts the command and keeps its start
    record (`detached`): `runlog AREA` and `--wait` see the command until it
    ends, its run record open or not, and an exit without a run record
    after it. Starting again prints the failed starts the area kept and
    clears every ended one.
    """
    import argparse

    ap = argparse.ArgumentParser(
        prog="runlog start",
        usage="runlog start AREA [--log FILE] [--max-seconds S] -- <cmd ...>",
        description="Start a command detached (own session via setsid), "
        "output to a log file, return once its run directory exists: exit 0 "
        "(the run named, or the command ended cleanly without a run), 2 the "
        "command failed before its run existed (the log's tail shown), 3 "
        "still starting after --max-seconds. A start that ended without a "
        "run record and not with exit 0 stays in `runlog AREA` and exits "
        "`--wait` with 2 until the next `runlog start` in the area clears it.",
    )
    ap.add_argument("area", type=Path, help="the experiment area the run belongs to")
    ap.add_argument(
        "--log", default=None, help="log file (default: AREA/output/start-<ts>.log)"
    )
    ap.add_argument(
        "--max-seconds",
        type=float,
        default=START_WAIT_S,
        help=f"wait this long for the run's directory (default {int(START_WAIT_S)})",
    )
    words, cmd = console.split_command(argv)
    if cmd is None:
        ap.parse_args(argv)  # --help prints and exits; a bad flag is named
        ap.error(
            "no command given — usage: runlog start AREA [--log FILE] "
            "[--max-seconds S] -- <cmd ...>"
        )
    args = ap.parse_args(words)
    if not cmd:
        ap.error(
            "no command given — usage: runlog start AREA [--log FILE] "
            "[--max-seconds S] -- <cmd ...>"
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
    before = {rd.dir.name for rd in run_dirs(area)}
    # starting again clears what earlier starts left: an ended command's
    # failure is said once more here, then its record goes
    for s in _failed_starts(area, detached.starts(area)):
        print(f"earlier start, cleared now: {_failed_start_line(s)}")
    detached.remove_ended(area)
    held = detached.HeldStart(area)
    with log.open("ab") as fh:
        try:
            proc = subprocess.Popen(
                detached.supervisor_command(held, log, cmd),
                stdin=subprocess.DEVNULL,
                stdout=fh,
                stderr=fh,
                start_new_session=True,
                env=env,
                pass_fds=(held.fd,),
            )
        except OSError:
            held.abandon()
            raise
    held.release()
    pid = _await_supervisor(area, proc, log)
    if pid is None:
        return 2
    print(f"started detached: pid={pid}  log={log}", flush=True)
    print(f"status:  runlog {area}        wait:  runlog {area} --wait", flush=True)
    return _await_run(area, before, proc, pid, log, args.max_seconds)


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
        "`--wait` blocks until the area is idle — no open run and no "
        "command `runlog start` detached still running without one "
        "(exit 0), a run "
        "crashed (exit 2) or --max-seconds passed (exit 3); "
        "`--follow` prints a status line per interval until idle; "
        "`runlog start <area> -- <cmd>` detaches a run (own session, "
        "log file) and returns once its run directory exists (exit 0; 2 the "
        "command failed first, 3 still starting after --max-seconds). "
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
        help="block until no open runs and no detached command still "
        "starting; exit 0/2/3 (idle/crashed/still running at --max-seconds)",
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
    if (area / repo.EXPERIMENTS).is_dir():
        # the lab root read as an area: "no open runs", and --wait as idle
        # while a measurement ran (audit 2026-10-27, third, I10)
        console.refuse(
            "runlog",
            f"{area} is the lab root, not an experiment area — name the area: "
            f"runlog experiments/<NN-name>",
        )
        return 2
    shown = str(area)
    if args.follow:
        return _wait(shown, None, args.interval or 5.0, True, args.notify)
    if args.wait:
        return _wait(shown, args.max_seconds, args.interval or 2.0, False, args.notify)
    live = active(area)
    starts = detached.starts(area)
    _print_status(shown, live, _unopened(starts, live), _failed_starts(area, starts))
    _print_finished(area)
    return 0


def cli() -> None:
    """Entry point for the installed `runlog` command."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
