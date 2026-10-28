"""detached — the record `runlog start` keeps of a command it detached, so
`runlog AREA` and `runlog AREA --wait` see it before its run opens a record.

A stamped script computes its rows before `runlog.run` opens the run's
record, and `runlog start` stops waiting for that record after
`--max-seconds`; until the record opens, this is the only trace of the run.
One JSON file per started command:

    {"pid": 1814, "command": [".venv/bin/python", "experiments/01-x/scripts/01_measure.py"],
     "log": "experiments/01-x/output/start-2026-10-28T17-22-29.log",
     "started": "2026-10-28T17:22:29"}

named `<area digest>-<pid>.json` in `labkit-run-starts/` of the git
directory of the area's repository (local, never committed; outside a
repository the system's temp dir, `repo.local_dir`).

A record is *running* while the lock on it is held (`fcntl.flock`): the
started command inherits the descriptor that holds it, and the kernel
releases the lock when the last process holding that descriptor ends —
never a pid, which the system reuses. `runlog start` writes the record
(`HeldStart`), `running` reads the ones still held. A record whose command
ended is read as nothing; the next `runlog start` in the area removes it.
Why: docs/notes/2026-10-27-workflow-stages.md ("Separate observation").
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.repo import local_dir
from labkit.formats.runs import now_stamp
from labkit.formats.scope_sha import digest

#: the folder of the records, under the git directory (`repo.local_dir`)
STARTS_DIR = "labkit-run-starts"
#: a record before its command started: never read, never removed here
#: (a concurrent start may not hold its lock yet)
UNSTARTED_SUFFIX = ".starting"


@dataclass(frozen=True)
class DetachedStart:
    """A command `runlog start` detached that still runs: its pid, its
    command line, its log and when it started (local time, seconds)."""

    pid: int
    command: tuple[str, ...]
    log: str
    started: str


def _folder(area: Path) -> Path:
    return local_dir(area, STARTS_DIR)


def _key(area: Path) -> str:
    """The prefix of AREA's records: the digest of its resolved path, so a
    relative and an absolute spelling of one area meet."""
    return digest(str(area.resolve()).encode())


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


class HeldStart:
    """The record of one start, locked before its command starts.

    `fd` holds the lock and goes to the command (`subprocess.Popen(...,
    pass_fds=(held.fd,))`); then `record` writes the record and closes this
    process's descriptor, or `abandon` removes it when the command did not
    start.

    Side effects: removes AREA's records whose command ended, creates
    the record file (under its unstarted name until `record`).
    """

    def __init__(self, area: Path) -> None:
        folder = _folder(area)
        folder.mkdir(parents=True, exist_ok=True)
        for path in _records(area):
            try:
                ended = not _held(path)
            except FileNotFoundError:
                continue  # removed by a concurrent start: it had ended
            if ended:
                path.unlink(missing_ok=True)
        self._folder, self._key = folder, _key(area)
        self.fd, name = tempfile.mkstemp(
            dir=folder, prefix=f"{self._key}-", suffix=UNSTARTED_SUFFIX
        )
        self._unstarted = Path(name)
        fcntl.flock(self.fd, fcntl.LOCK_EX)

    def record(self, pid: int, command: list[str], log: Path) -> Path:
        """Write the started command's record, give it its name and close
        this process's descriptor — the lock stays with the command.
        Returns the record's path."""
        data = {
            "pid": pid,
            "command": list(command),
            "log": str(log),
            "started": now_stamp(),
        }
        with open(self.fd, "w", encoding="utf-8", closefd=False) as fh:
            json.dump(data, fh)
        path = self._folder / f"{self._key}-{pid}.json"
        # the lock belongs to this file's open description, and a new file
        # written beside it would carry none — home: not files.write_atomic
        os.replace(self._unstarted, path)
        os.close(self.fd)
        return path

    def abandon(self) -> None:
        """The command did not start: remove the record, release the lock."""
        self._unstarted.unlink()
        os.close(self.fd)


def running(area: Path) -> list[DetachedStart]:
    """The commands `runlog start` detached in AREA that still run — their
    record's lock is held —, oldest first. Raises RuntimeError on a record
    that does not read."""
    out: list[DetachedStart] = []
    for path in _records(area):
        try:
            if not _held(path):
                continue
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue  # removed since the listing, which only ended starts are
        out.append(_parse(path, text))
    return sorted(out, key=lambda s: (s.started, s.pid))


def _parse(path: Path, text: str) -> DetachedStart:
    """The record TEXT of PATH, its fields as `HeldStart.record` writes
    them. Raises RuntimeError naming the field that does not read."""

    def bad(why: str) -> RuntimeError:
        return RuntimeError(
            f"{path}: the record of a command `runlog start` detached does not "
            f"read — {why}"
        )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise bad(f"not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise bad("not a JSON object")
    pid, command = data.get("pid"), data.get("command")
    if not isinstance(pid, int) or isinstance(pid, bool):
        raise bad(f"pid is {pid!r}, not a number")
    if not isinstance(command, list) or not all(isinstance(w, str) for w in command):
        raise bad(f"command is {command!r}, not a list of words")
    for key in ("log", "started"):
        if not isinstance(data.get(key), str):
            raise bad(f"{key} is {data.get(key)!r}, not text")
    return DetachedStart(pid, tuple(command), data["log"], data["started"])
