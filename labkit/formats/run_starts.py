"""run_starts — the start file of a run, `run-starts/<run_id>.json` in its
area: written once, before the run's block executes, outside the run's
directory and outside `runs/` — a listing of `runs/` meets directories
only, and deleting `runs/` leaves the start files (`START_FIELDS`: the run id, the protocol id it is bound to, its
start in UTC, its run kind). It answers what the run index cannot — which
run started with which protocol, when and as what —, also for a run that
never finished or whose directory is gone; which runs reached completion
stays the run index's (`run_index`), and no completion state or result is
kept here. One file per run: a second run never writes into a file another
wrote, and a file that exists is never overwritten — the same run id
started twice fails loudly. Tracked, not ignored: a start file nobody
committed leaves the tree changed, which is what happened, and a clone has
exactly the start files a commit holds. Never rebuilt: only a start writes
one, so a run from before this file has none and its start is unknown. A
start file that does not read is an incomplete start (`RunStart.unread`):
nothing is taken from it and nothing stands in for it, and it is never
rewritten — a value comes only from where it is kept. The one home of its
name, its fields, its reading and its writing. Who reads
it: the area state (`area_state`); what holds a committed one against
change: `evidence`. Why, and what was rejected:
docs/notes/2026-11-18-run-start-record.md.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from labkit.formats.run_index import RunIndexError
from labkit.formats.runs import RUN_ID, RunKind, parse_run_kind

#: the directory of an area that holds its runs' start files, beside `runs/`
START_FILES_DIR = "run-starts"
#: what follows the run id in a start file's name
START_SUFFIX = ".json"

#: the file in a run's own directory that says a start file was written
#: for it (`write_start_mark`): what tells a run that owes a start file
#: from one started before start files, by the run's own record
START_MARK = "start-file"
#: the keys of a start file, all of them and no other
START_FIELDS = ("run_id", "protocol_id", "started_utc", "run_kind")


class RunStartsError(RunIndexError):
    """Text that is no start file as written (`parse_start`): no JSON
    object, other keys than START_FIELDS, a run id that is not its name's,
    a start that is no UTC time, a kind that is none. WHY names the file.
    The readers of an area's start files do not raise it: such a file is
    one run's incomplete start (`start_of`), not a state of the area."""


@dataclass(frozen=True)
class RunStart:
    """What a start file holds — or, for one that does not read, that a
    run of this id started and nothing else (an incomplete start).

    Attributes:
        run_id: The run that started; from the file's name where the file
            does not read.
        protocol_id: The protocol id it was bound to at its start, "" for a
            run that started unbound; None when the file does not say.
        started: When it started, an aware time in UTC, taken from the
            starting machine's clock — right only if that clock was; None
            when the file does not say.
        run_kind: What it started as: a measurement, a probe or a
            preparation (`runs.RunKind`); None when the file does not say.
            A reader that asks for the measurements that started compares
            it with `runs.MEASUREMENT`; a start file alone says "a run
            started", never "a measurement".
        unread: Why the file does not read, "" for one that does. With it
            the three values above are None: unknown, each on its own — no
            default stands in, and a reader that needs one treats it as
            missing (the binding from other evidence or unassigned, the
            order unknown, the kind as without a start file).
    """

    run_id: str
    protocol_id: str | None
    started: datetime | None
    run_kind: RunKind | None
    unread: str = ""


def utc_now() -> datetime:
    """The time now in UTC, to the second — the one spelling of a start."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def start_path(area: Path, run_id: str) -> Path:
    """Where the start file of RUN_ID lies in AREA:
    `run-starts/<run_id>.json` — outside the run's directory, so deleting
    that directory leaves it."""
    return area / START_FILES_DIR / f"{run_id}{START_SUFFIX}"


def is_start_file(rel: str) -> bool:
    """Is REL, a path relative to an area, a run's start file?"""
    parts = rel.split("/")
    return (
        len(parts) == 2
        and parts[0] == START_FILES_DIR
        and parts[1].endswith(START_SUFFIX)
        and RUN_ID.fullmatch(parts[1].removesuffix(START_SUFFIX)) is not None
    )


def write_start(area: Path, start: RunStart) -> Path:
    """Write the start file of START's run in AREA, whole and durable before
    returning, and never over a file that is there: the text goes to a
    temporary file beside it and is synced, a hard link then creates the
    start file in one step — failing when the name exists —, and the
    directory is synced.

    Side effects:
        Creates AREA/run-starts/<run_id>.json, and the directory where it
        is missing; leaves no temporary file.

    Returns the path. Raises FileExistsError when a start file of that run
    id exists — a run starts once, and nothing is overwritten —, OSError
    when the file cannot be written or synced; the caller refuses the
    start on either. ValueError for an incomplete START: only a start that
    names all its values is written."""
    if start.protocol_id is None or start.started is None or start.run_kind is None:
        raise ValueError(f"the start of {start.run_id} is incomplete: not written")
    path = start_path(area, start.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        {
            "run_id": start.run_id,
            "protocol_id": start.protocol_id,
            "started_utc": start.started.isoformat(timespec="seconds"),
            "run_kind": start.run_kind,
        },
        indent=2,
    )
    staged = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with staged.open("x", encoding="utf-8") as f:
            f.write(text + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.link(staged, path)  # atomic, and refuses a name that exists
    finally:
        staged.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return path


def write_start_mark(run_dir: Path) -> None:
    """Write the mark into the run directory RUN_DIR that a start file is
    written for this run: the file START_MARK, holding the start file's
    path from the area. Written before the start file itself, so a run
    whose record carries the mark is one whose start file was to exist,
    and a failed start leaves neither (the run directory is removed).

    Side effects:
        Creates RUN_DIR/start-file.

    The mark is the evidence, in the run's own record, that the run is
    one of the format with start files: a run without it — every run
    started before them — owes no start file, and nothing is guessed from
    a version or a date. Raises OSError when it cannot be written."""
    (run_dir / START_MARK).write_text(
        f"{START_FILES_DIR}/{run_dir.name}{START_SUFFIX}\n", encoding="utf-8"
    )


def parse_start(text: str, where: str, run_id: str) -> RunStart:
    """TEXT, the content of the start file of RUN_ID, as a `RunStart`. WHERE
    names the file in the error. Raises RunStartsError for text that is no
    JSON object of exactly START_FIELDS, a `run_id` other than RUN_ID, a
    start that is no time in UTC, or a kind that is none. Pure."""
    way = (
        "restore the file from the commit that holds it (`git checkout <commit> -- "
        "<path>`); never write one anew from memory or delete it — it may be the "
        "only trace of a run whose folder is gone"
    )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RunStartsError(f"{where}: not JSON ({exc}); {way}") from exc
    if not isinstance(data, dict) or tuple(data) != START_FIELDS:
        raise RunStartsError(
            f"{where}: a start file holds exactly the keys {', '.join(START_FIELDS)}, "
            f"in this order; {way}"
        )
    if data["run_id"] != run_id:
        raise RunStartsError(
            f"{where}: run_id = {data['run_id']!r} is not the run its name says "
            f"({run_id}); {way}"
        )
    written = data["started_utc"]
    try:
        started = datetime.fromisoformat(written) if isinstance(written, str) else None
    except ValueError:
        started = None
    if started is None or started.utcoffset() != timedelta(0):
        raise RunStartsError(
            f"{where}: started_utc = {written!r} is no time in UTC "
            f"(`2026-11-18T12:03:15+00:00`); {way}"
        )
    if not isinstance(data["protocol_id"], str):
        raise RunStartsError(
            f"{where}: protocol_id = {data['protocol_id']!r} is no text; {way}"
        )
    try:
        run_kind = parse_run_kind(data["run_kind"])
    except ValueError as exc:
        raise RunStartsError(f"{where}: {exc}; {way}") from exc
    return RunStart(run_id, data["protocol_id"], started, run_kind)


def start_of(text: str | None, where: str, run_id: str, why: str = "") -> RunStart:
    """The start of RUN_ID from TEXT, its start file's content (WHERE names
    the file): what `parse_start` reads, or — for text that is no start
    file, and for None with WHY saying why it could not be read — the
    incomplete start of that run (`RunStart.unread`). The one fallback of
    every reader of start files (the working tree's, the index's, a
    commit's), so none refuses an area over one file. Pure."""
    if text is None:
        return RunStart(run_id, None, None, None, why or f"{where}: not read")
    try:
        return parse_start(text, where, run_id)
    except RunStartsError as exc:
        return RunStart(run_id, None, None, None, str(exc))


def read_starts(area: str | Path) -> dict[str, RunStart]:
    """The start files of AREA as the working tree holds them, by run id,
    oldest first by name; {} without one. A file whose name is no run id's
    is not a start file and is left alone. A start file that does not read
    — damaged, or not readable as text — is that run's incomplete start
    (`start_of`): never "no run started", and never a refusal."""
    held = Path(area) / START_FILES_DIR
    if not held.is_dir():
        return {}
    out: dict[str, RunStart] = {}
    for path in sorted(held.glob(f"*{START_SUFFIX}")):
        run_id = path.name.removesuffix(START_SUFFIX)
        if RUN_ID.fullmatch(run_id) is None:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            out[run_id] = start_of(None, str(path), run_id, f"{path}: {exc}")
        else:
            out[run_id] = start_of(text, str(path), run_id)
    return out
