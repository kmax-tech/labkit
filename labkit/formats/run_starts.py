"""run_starts — the start record of an area, `run-starts.tsv`: one row per
run that started, of every kind, written before its block executes
(`RUN_START_COLS`: the run id, the protocol id it is bound to, its start in
UTC, its run kind). It answers one question the run index cannot — which
run was started with which protocol, when and as what —, also for a run
that never finished or whose directory is gone; which runs reached completion stays the run index's
(`run_index`), and no completion state or result is kept here. Local like
the index, kept out of the repository by the lab stamp, and never rebuilt:
nothing but a start writes a row, so a run from before this file, or from
another machine, has none and its start time is unknown. The one home of
its name, its columns, its reading and its writing; the lock is the run
index's (`run_index.index_lock`), one lock for both files of an area. Who
reads it: the area state (`area_state`). Why two files, and what was
rejected: docs/notes/2026-11-18-run-start-record.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from labkit.formats.run_index import RunIndexError, index_lock
from labkit.formats.runs import RunKind, parse_run_kind

#: the start record of an area, beside the run index; local, never rebuilt
RUN_STARTS = "run-starts.tsv"

RUN_START_COLS = ["run_id", "protocol_id", "started_utc", "run_kind"]


class RunStartsError(RunIndexError):
    """A start record that does not read as written (`read_starts`): other
    columns, a row without all of them, a start that is no UTC time, a kind
    that is none, a run listed twice. WHY names the file, the line and the
    way out; a command ends on it as runlog's refusal
    (`console.exit_with`), exit 2. A `RunIndexError`: the area state reads
    both files in one step (`area_state.state_of`), and every caller that
    refuses on an index that does not read refuses on this the same way —
    whether a run was measured or started cannot be told from either."""


@dataclass(frozen=True)
class RunStart:
    """One row of the start record.

    Attributes:
        run_id: The run that started.
        protocol_id: The protocol id it was bound to at its start, "" for a
            run that started unbound.
        started: When it started, an aware time in UTC, taken from the
            starting machine's clock — right only if that clock was.
        run_kind: What it started as: a measurement, a probe or a
            preparation (`runs.RunKind`). A reader that asks for the
            measurements that started compares it with `runs.MEASUREMENT`;
            a row alone says "a run started", never "a measurement".
    """

    run_id: str
    protocol_id: str
    started: datetime
    run_kind: RunKind


def utc_now() -> datetime:
    """The time now in UTC, to the second — the one spelling of a start."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def _row(start: RunStart) -> str:
    return "\t".join(
        [
            start.run_id,
            start.protocol_id,
            start.started.isoformat(timespec="seconds"),
            start.run_kind,
        ]
    )


def write_start(base_dir: Path, start: RunStart) -> None:
    """Append START to the start record of the area BASE_DIR and make it
    durable before returning: the header where the file is new, the row,
    flushed and synced to disk, the directory synced for a new file.

    Side effects:
        Creates or appends to BASE_DIR/run-starts.tsv.

    The caller holds the index lock (`run_index.index_lock`): the header
    check reads the same file, and two starts must not interleave. Raises
    OSError when the row cannot be written or synced — the caller refuses
    the start —, RunStartsError when the file there does not read or
    already lists the run."""
    path = base_dir / RUN_STARTS
    known = _parse(path)
    if start.run_id in known:
        raise RunStartsError(
            f"{path} already lists {start.run_id} — a run starts once; repair the "
            f"file by hand (never delete the row of a run that started)"
        )
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8") as f:
        if new:
            f.write("\t".join(RUN_START_COLS) + "\n")
        f.write(_row(start) + "\n")
        f.flush()
        os.fsync(f.fileno())
    if new:
        fd = os.open(base_dir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _parse(path: Path) -> dict[str, RunStart]:
    """The rows of the start record at PATH by run id, in file order,
    checked as written; {} without a file or with an empty one. Raises
    RunStartsError naming the line."""
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return {}
    way = (
        "repair the line by hand; never delete the row of a run that started — it "
        "may be the only trace of a run whose folder is gone"
    )
    if lines[0].split("\t") != RUN_START_COLS:
        raise RunStartsError(
            f"{path}:1: columns {lines[0].split(chr(9))} are not "
            f"{RUN_START_COLS} — a damaged first line; {way}"
        )
    out: dict[str, RunStart] = {}
    for n, line in enumerate(lines[1:], start=2):
        if not line:
            continue
        start = _start_of(line, f"{path}:{n}", way)
        if start.run_id in out:
            raise RunStartsError(f"{path}:{n}: {start.run_id} is listed twice; {way}")
        out[start.run_id] = start
    return out


def _start_of(line: str, where: str, way: str) -> RunStart:
    """The row LINE as a `RunStart`. Raises RunStartsError naming WHERE
    (file and line) and the way out WAY for a row without every column, a
    start that is no time in UTC, or a kind that is none."""
    row = line.split("\t")
    if len(row) != len(RUN_START_COLS):
        raise RunStartsError(
            f"{where}: {len(row)} of {len(RUN_START_COLS)} tab-separated "
            f"columns ({', '.join(RUN_START_COLS)}) — a row cut short or run "
            f"together; {way}"
        )
    run_id, protocol_id, written, kind = row
    try:
        started = datetime.fromisoformat(written)
    except ValueError:
        started = None
    if started is None or started.utcoffset() != timedelta(0):
        raise RunStartsError(
            f"{where}: started_utc = {written!r} is no time in UTC "
            f"(`2026-11-18T12:03:15+00:00`); {way}"
        )
    try:
        run_kind = parse_run_kind(kind)
    except ValueError as exc:
        raise RunStartsError(f"{where}: {exc}; {way}") from exc
    return RunStart(run_id, protocol_id, started, run_kind)


def read_starts(base_dir: str | Path) -> dict[str, RunStart]:
    """The start record of the area BASE_DIR by run id, in file order —
    read under the shared index lock, so a row a starting run appends is
    read whole or not at all; {} without a file, and then no lock file is
    made. Raises RunStartsError on a file that does not read: a short row
    is never read as "no run started"."""
    path = Path(base_dir) / RUN_STARTS
    if not path.exists():
        return {}
    with index_lock(path.parent, shared=True):
        return _parse(path)
