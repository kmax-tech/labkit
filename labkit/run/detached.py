"""detached — the record `runlog start` keeps of a command it detached, so
`runlog AREA` and `runlog AREA --wait` see it before its run opens a record,
and see it end without one.

A stamped script computes its rows before `runlog.run` opens the run's
record, and `runlog start` stops waiting for that record after
`--max-seconds`; until the record opens, this is the only trace of the run,
and when the command dies first, the only trace of the failure. One JSON
file per started command:

    {"pid": 1814, "command": [".venv/bin/python", "experiments/01-x/scripts/01_measure.py"],
     "log": "experiments/01-x/output/start-2026-10-28T17-22-29.log",
     "started": "2026-10-28T17:22:29", "supervisor": 1813, "exit": null}

named `<area digest>-<pid>.json` in `labkit-run-starts/` of the git
directory of the area's repository (local, never committed; outside a
repository the system's temp dir, `repo.local_dir`). `pid` is the
command's own, the pid its run records; `exit` is its exit status once it
ended (negative: killed by that signal), null while it runs.

`runlog start` takes the record's lock (`HeldStart`) and starts the
supervisor (`supervisor_command`, `supervise`) in a session of its own: the
supervisor starts the command as its child, writes the record, waits for
the command and writes its exit status. Supervisor and command both
inherit the descriptor that holds the lock (`fcntl.flock`); the kernel
releases it when the last of them ends — never a pid, which the system
reuses. A record *runs* while its exit is null and its lock is held; it
*ended* when its exit is written, or when the lock is free without one (the
supervisor ended first: exit not recorded). An ended record stays until the
next `runlog start` in the area removes it (`remove_ended`).
Why: docs/notes/2026-10-27-workflow-stages.md ("Separate observation").
"""

from __future__ import annotations

import fcntl
import json
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import console
from labkit.formats.files import write_atomic
from labkit.formats.repo import local_dir
from labkit.formats.runs import now_stamp
from labkit.formats.scope_sha import digest

#: the folder of the records, under the git directory (`repo.local_dir`)
STARTS_DIR = "labkit-run-starts"
#: a record before the supervisor named it: never read, never removed here
#: (a concurrent start may not hold its lock yet)
UNSTARTED_SUFFIX = ".starting"
#: the supervisor's exit when the command cannot be started at all
#: (the shell's "command not found")
CANNOT_START = 127


@dataclass(frozen=True)
class DetachedStart:
    """One command `runlog start` detached, as its record holds it: the
    command's pid, its command line, its log, when it started (local time,
    seconds), the supervisor's pid, the exit status once known (negative:
    the signal that ended it), and whether it still runs."""

    pid: int
    command: tuple[str, ...]
    log: str
    started: str
    supervisor: int
    exit: int | None
    running: bool


def exit_words(start: DetachedStart) -> str:
    """How START ended, in words: `exit 3`, `killed by signal 9`, or that
    no exit was recorded (its supervisor ended first)."""
    if start.exit is None:
        return "exit not recorded (its supervisor ended first)"
    if start.exit < 0:
        return f"killed by signal {-start.exit}"
    return f"exit {start.exit}"


def _folder(area: Path) -> Path:
    return local_dir(area, STARTS_DIR)


def _key(area: Path) -> str:
    """The prefix of AREA's records: the digest of its resolved path, so a
    relative and an absolute spelling of one area meet."""
    return digest(str(area.resolve()).encode())


def _record_path(area: Path, pid: int) -> Path:
    return _folder(area) / f"{_key(area)}-{pid}.json"


def _held(path: Path) -> bool:
    """Is the lock on PATH held? A shared probe, so two readers never see
    each other as the holder. Raises FileNotFoundError when PATH is gone."""
    with path.open("rb") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
        return False


def _records(area: Path) -> list[Path]:
    folder = _folder(area)
    if not folder.is_dir():
        return []
    return sorted(folder.glob(f"{_key(area)}-*.json"))


def starts(area: Path) -> list[DetachedStart]:
    """Every command `runlog start` detached in AREA whose record is kept —
    running and ended —, oldest first. Raises console.Refused on a record
    that does not read (`_parse`)."""
    out: list[DetachedStart] = []
    for path in _records(area):
        try:
            held = _held(path)
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue  # removed since the listing, which only ended starts are
        out.append(_parse(path, text, held))
    return sorted(out, key=lambda s: (s.started, s.pid))


def remove_ended(area: Path) -> None:
    """Remove AREA's records of commands that ended. Side effect: deletes
    those files."""
    for path in _records(area):
        try:
            text = path.read_text(encoding="utf-8")
            start = _parse(path, text, _held(path))
        except FileNotFoundError:
            continue  # removed by a concurrent start: it had ended
        if not start.running:
            path.unlink(missing_ok=True)


def _parse(path: Path, text: str, held: bool) -> DetachedStart:
    """The record TEXT of PATH, its fields as `supervise` writes them;
    HELD says whether its lock is held. Raises console.Refused naming the
    field that does not read and the way out."""

    def bad(why: str) -> console.Refused:
        return console.Refused(
            "runlog",
            f"{path}: the record of a command `runlog start` detached does not "
            f"read — {why}; it is labkit's local note in the git directory, not "
            f"evidence — way out: remove it (`rm {shlex.quote(str(path))}`)",
        )

    def number(key: str) -> int:
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise bad(f"{key} is {value!r}, not a number")
        return value

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise bad(f"not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise bad("not a JSON object")
    command = data.get("command")
    if not isinstance(command, list) or not all(isinstance(w, str) for w in command):
        raise bad(f"command is {command!r}, not a list of words")
    for key in ("log", "started"):
        if not isinstance(data.get(key), str):
            raise bad(f"{key} is {data.get(key)!r}, not text")
    if "exit" not in data:
        raise bad("no exit field (null while the command runs)")
    exit_status = None if data["exit"] is None else number("exit")
    return DetachedStart(
        pid=number("pid"),
        command=tuple(command),
        log=data["log"],
        started=data["started"],
        supervisor=number("supervisor"),
        exit=exit_status,
        running=exit_status is None and held,
    )


class HeldStart:
    """The lock of one start, taken before the supervisor starts.

    `fd` holds the lock and goes to the supervisor (`supervisor_command`,
    `subprocess.Popen(..., pass_fds=(held.fd,))`); then `release` closes
    this process's descriptor, or `abandon` removes the unnamed record when
    the supervisor did not start.

    Side effect: creates the unnamed record file.
    """

    def __init__(self, area: Path) -> None:
        folder = _folder(area)
        folder.mkdir(parents=True, exist_ok=True)
        self.area = area.resolve()
        self.fd, name = tempfile.mkstemp(
            dir=folder, prefix=f"{_key(area)}-", suffix=UNSTARTED_SUFFIX
        )
        self.unstarted = Path(name)
        fcntl.flock(self.fd, fcntl.LOCK_EX)

    def release(self) -> None:
        """The supervisor started: close this process's descriptor — the
        lock stays with the supervisor and the command."""
        os.close(self.fd)

    def abandon(self) -> None:
        """The supervisor did not start: remove the record, release the lock."""
        self.unstarted.unlink()
        os.close(self.fd)


def supervisor_command(held: HeldStart, log: Path, command: list[str]) -> list[str]:
    """The command line of the supervisor for COMMAND: this interpreter,
    without the working directory on its path (`-P`: a `labkit/` there must
    not stand in for the installed one)."""
    return [
        sys.executable,
        "-P",
        "-m",
        "labkit.run.detached",
        str(held.fd),
        str(held.area),
        str(held.unstarted),
        str(log),
        "--",
        *command,
    ]


def supervise(
    fd: int, area: Path, unstarted: Path, log: str, command: list[str]
) -> int:
    """Start COMMAND as this process's child with the lock descriptor FD,
    name its record (UNSTARTED becomes `<area digest>-<pid>.json`), wait
    for it, write its exit status into the record. Returns the command's
    exit status as a process's exit (128 + signal when a signal ended it);
    CANNOT_START when it cannot be started, with the reason on stderr (the
    start's log) and the unnamed record removed.

    Side effects: starts COMMAND; writes and renames the record."""
    try:
        child = subprocess.Popen(command, pass_fds=(fd,))
    except OSError as exc:
        print(f"runlog start: cannot run {shlex.join(command)}: {exc}", file=sys.stderr)
        unstarted.unlink()
        return CANNOT_START
    data = {
        "pid": child.pid,
        "command": command,
        "log": log,
        "started": now_stamp(),
        "supervisor": os.getpid(),
        "exit": None,
    }
    with open(fd, "w", encoding="utf-8", closefd=False) as fh:
        json.dump(data, fh)
    path = _record_path(area, child.pid)
    # the lock belongs to this file's open description, and a new file
    # written beside it would carry none — home: not files.write_atomic
    os.replace(unstarted, path)
    code = child.wait()
    write_atomic(path, json.dumps({**data, "exit": code}))
    return code if code >= 0 else 128 - code


def main(argv: list[str]) -> int:
    """`python -P -m labkit.run.detached FD AREA UNSTARTED LOG -- COMMAND…`:
    the supervisor `runlog start` starts (`supervisor_command`)."""
    if len(argv) < 6 or argv[4] != "--":
        raise SystemExit(
            "usage: python -P -m labkit.run.detached FD AREA UNSTARTED LOG -- COMMAND…"
            " (started by `runlog start`)"
        )
    fd, area, unstarted, log = int(argv[0]), Path(argv[1]), Path(argv[2]), argv[3]
    return supervise(fd, area, unstarted, log, argv[5:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
