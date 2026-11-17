"""origin_check — each input of a run held to the origin run its record names.

At start runlog decides which completed run of the area wrote each input
file (`input_origins`) and records it in the input's entry
(`runs.ORIGIN_RUN_KEY`). That entry is a promise: "this input is the
recorded output of that origin run". This check holds the promise against
the area as it stands (the source station of
docs/notes/2026-11-14-exploratory-workflow-plan.md). In order, the first
part that fails is named (`origin_gap`):

    gone             no run directory of that id under the area's runs/
    unread           the origin's config.json or outputs.json does not read
    not completed    the origin is not completed as its files stand
    not registered   its outputs.json holds no output at the input's path
    other bytes      it registered other bytes than the input's record
    bytes changed    the file's bytes now differ from both records

A stored origin is never decided again: a later run that writes the same
file does not change it. A plain input (no origin) and the runs the lookup
skipped are facts for the auditor, not findings (`origin_notes`). The
facts are read once (`origin_now`); the decision opens no file. Read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labkit.formats.commands import measure_anew
from labkit.formats.gate import TECHNICAL_RULE, GateFinding, blocker
from labkit.formats.repo import path_kind
from labkit.formats.runs import (
    COMPLETED,
    RECORD_CAUSE_TOLD,
    RECORD_CAUSES,
    ArtefactError,
    DataEntry,
    read_data,
    read_run_dir,
    resolve_recorded,
    runs_path,
)
from labkit.run.input_origins import AreaRun, grouped_by_cause, read_area_run
from labkit.checks.run_record_check import source_drift

#: the parts of the origin promise, in the order `origin_gap` checks them
#: (`OriginGap.part`); GONE: no run of that id under runs/ — no directory,
#: or a directory without config.json
GONE = "gone"
UNREAD = "unread"
NOT_COMPLETED = "not completed"
NOT_REGISTERED = "not registered"
OTHER_BYTES = "other bytes"
BYTES_CHANGED = "bytes changed"
#: the parts that are the origin's record, not the file: restored from git
#: or a backup, never edited
RECORD_PARTS = (GONE, UNREAD, NOT_COMPLETED, NOT_REGISTERED, OTHER_BYTES)

#: what an input's origin may never be made to pass by; every way out says it
NEVER_REWRITTEN = (
    "never adjust a recorded sha256 or origin to make the check pass — "
    "evidence is restored, not rewritten"
)

#: the lookup's reach, as the auditor and the notes state it
LOOKED_UP_WITHIN_AREA = (
    "origins are looked up only among the runs of this area (its runs/); "
    "a file from elsewhere is a plain input"
)


@dataclass(frozen=True)
class OriginNow:
    """What the area says now of one input's recorded origin (`origin_now`)
    — the facts `origin_gap` decides on.

    Attributes:
        entry: The input as the run recorded it; its `origin_run` is set.
        path: The input file, resolved against the repository.
        origin: The origin run as the lookup reads it (`input_origins.AreaRun`);
            None when no run of that id stands under the area's runs/ — no
            directory, or one without config.json.
        drift: Why the file's bytes are not the input's record
            (`run_record_check.source_drift`), None when they are — and
            None, not computed, when a part of the origin's record already
            fails (`record_gap`), which `origin_gap` then names.
    """

    entry: DataEntry
    path: Path
    origin: AreaRun | None
    drift: str | None = None


@dataclass(frozen=True)
class OriginGap:
    """The first part of an input's origin promise that fails
    (`origin_gap`): PART one of GONE … BYTES_CHANGED, TOLD the sentence
    naming the input, the origin and the condition."""

    part: str
    told: str


def origin_now(area: Path, entry: DataEntry) -> OriginNow:
    """The facts on ENTRY, an input of a run of AREA whose record names an
    origin run, in AREA as it stands: the origin read as the lookup at start reads
    it (`input_origins.read_area_run`), by name under the area's runs/ and never
    as a path, and — only when the origin's record holds the input's path
    with its digest — whether the file's bytes drifted. Reads files, writes
    nothing. Raises ValueError for an entry without origin."""
    if entry.origin_run is None:
        raise ValueError(f"data[{entry.key!r}]: a plain input has no origin to check")
    # against the area, as the lookup at start resolved it (`input_origins`)
    path = resolve_recorded(entry.recorded, area).resolve()
    origin_dir = runs_path(area) / entry.origin_run
    origin = (
        read_area_run(read_run_dir(origin_dir))
        if path_kind(origin_dir) == "dir"
        else None
    )
    if record_gap(entry, path, origin) is not None:
        # a record part fails first: the file is not hashed for nothing
        return OriginNow(entry, path, origin)
    return OriginNow(entry, path, origin, source_drift(path, entry.sha256))


def _registered(origin: AreaRun, path: Path) -> list[str | None]:
    """The sha256 values ORIGIN's outputs.json registered for PATH (resolved),
    in its order; [] when it registered no output there."""
    return [e.sha256 for e in origin.outputs if e.path == path]


def origin_gap(now: OriginNow) -> OriginGap | None:
    """The first part of the promise "this input is the recorded output of
    its origin run" that NOW (`origin_now`) breaks, in the module's order:
    the origin's record (`record_gap`), then the file's bytes; None when
    every part holds. Opens no file."""
    gap = record_gap(now.entry, now.path, now.origin)
    if gap is not None:
        return gap
    if now.drift is not None:
        e = now.entry
        return OriginGap(
            BYTES_CHANGED,
            f"data[{e.key!r}] = {e.recorded} is not the output of its origin run "
            f"{e.origin_run} any more: {now.drift}, both records hold sha256 "
            f"{e.sha256}",
        )
    return None


def record_gap(e: DataEntry, path: Path, origin: AreaRun | None) -> OriginGap | None:
    """The first part of the origin's record that fails for input E at
    PATH (resolved), ORIGIN as `origin_now` read it — GONE to OTHER_BYTES,
    in the module's order; None when the record holds the input's path
    with its digest, so only the file's bytes are left. Opens no file."""
    what = f"data[{e.key!r}] = {e.recorded}: its origin run {e.origin_run}"
    if origin is None:
        return OriginGap(GONE, f"{what} is gone (no run of that id under runs/)")
    if origin.unread is not None:
        assert origin.unread_cause in RECORD_CAUSES, "AreaRun pairs reason and cause"
        return OriginGap(
            UNREAD,
            f"{what} does not read — {RECORD_CAUSE_TOLD[origin.unread_cause]}: "
            f"{origin.unread}",
        )
    if origin.state != COMPLETED:
        return OriginGap(
            NOT_COMPLETED,
            f"{what} is not completed ({origin.state} as its files stand)",
        )
    registered = _registered(origin, path)
    if not registered:
        return OriginGap(
            NOT_REGISTERED,
            f"{what} registered no output {e.recorded} (its outputs.json)",
        )
    if e.sha256 not in registered:
        return OriginGap(
            OTHER_BYTES,
            f"{what} registered {e.recorded} with sha256 {registered[0]}, the "
            f"run recorded it as read with sha256 {e.sha256}",
        )
    return None


def origin_finding(gap: OriginGap, area: Path) -> GateFinding:
    """The blocker for GAP (`origin_gap`) in a run of AREA, with the way out
    its part owes: a changed file gets the bytes the run read back from the
    evidence that holds them, an origin record is restored from git or a
    backup — "repair" means restore, not edit; either way, or the run is
    measured anew with the right sources. Never a rewritten sha256 or
    origin (`NEVER_REWRITTEN`). The technical contract of the record, a
    guaranteed blocker."""
    if gap.part == BYTES_CHANGED:
        restore = (
            "restore the bytes the run read (from git where it tracks them, "
            "else from the source or access route Data / scope names)"
        )
    else:
        assert gap.part in RECORD_PARTS, gap.part
        restore = "restore the origin run's directory or record from git or a backup"
    return blocker(
        gap.told,
        fix=f"{restore}, or, with the right sources, {measure_anew(area)}; "
        f"{NEVER_REWRITTEN}",
        rule=TECHNICAL_RULE,
    )


@dataclass(frozen=True)
class OriginState:
    """One input's origin as finalize's station and the auditor's piece
    both tell it (`origin_state`), in that order: NOTES (`origin_notes`),
    then — for an input that names an origin — NOW (`origin_now`) and GAP
    (`origin_gap`, None when the promise holds). NOW is None for a plain
    input."""

    notes: tuple[str, ...]
    now: OriginNow | None
    gap: OriginGap | None


def origin_state(area: Path, entry: DataEntry) -> OriginState:
    """ENTRY's origin in AREA as it stands (`OriginState`) — the one walk
    over an input that the station and the piece share. Reads files."""
    notes = tuple(origin_notes(entry))
    if entry.origin_run is None:
        return OriginState(notes, None, None)
    now = origin_now(area, entry)
    return OriginState(notes, now, origin_gap(now))


#: the label of the piece MODE analysis shows of a run's input origins
ORIGINS_LABEL = "INPUT ORIGINS"


def origin_piece(area: Path, run_dir: Path) -> list[tuple[str, str]]:
    """What MODE analysis shows of RUN_DIR's input origins, one `(label,
    text)` piece: that origins are looked up only within the area, then
    per input its origin run — chosen or decided by digest, the run it
    repeats where it is a repeat (read from the origin's own record) — and
    the first part of the promise that fails now (`origin_gap`), or a plain
    input and the runs the lookup skipped (`origin_notes`). [] for a run
    without input files or whose record does not read (the record checks
    name that). Reads files, writes nothing."""
    try:
        entries = read_data(run_dir) or []
    except ArtefactError:
        return []  # a record that does not read: the record checks name it
    if not entries:
        return []
    lines = [LOOKED_UP_WITHIN_AREA]
    for entry in entries:
        state = origin_state(area, entry)
        lines += state.notes
        if state.now is None:
            continue  # a plain input: its note says so
        origin = state.now.origin
        repeats = (
            f", a repeat of {origin.repeat_of}"
            if origin is not None and origin.repeat_of is not None
            else ""
        )
        lines.append(
            f"{origin_held(entry)}{repeats}"
            if state.gap is None
            else f"{state.gap.told} — finalize holds the run"
        )
    return [(ORIGINS_LABEL, "\n".join(lines))]


def origin_held(entry: DataEntry) -> str:
    """The note for ENTRY when its origin promise holds."""
    chosen = "chosen by the script" if entry.origin_chosen else "decided by digest"
    return (
        f"data[{entry.key!r}] = {entry.recorded}: the output of {entry.origin_run} "
        f"({chosen}), as both records hold it"
    )


def origin_notes(entry: DataEntry) -> list[str]:
    """What ENTRY's record states beside a checked origin, each a fact for
    the auditor, never a finding: a plain input without origin — where it
    came from is the audit's question —, and the runs of the area the
    lookup skipped because their record did not read, grouped by cause
    (`runs.RECORD_CAUSE_TOLD`), not known to have written the file, only
    not ruled out."""
    out: list[str] = []
    if entry.origin_run is None:
        out.append(
            f"data[{entry.key!r}] = {entry.recorded}: an input without origin — "
            f"no completed run of this area had registered it with these bytes "
            f"at start; where it came from is the auditor's question"
        )
    if entry.origin_unreadable_runs:
        out.append(
            f"data[{entry.key!r}] = {entry.recorded}: decided without the "
            f"area's runs whose record did not read "
            f"({grouped_by_cause(entry.origin_unreadable_runs)})"
        )
    return out
