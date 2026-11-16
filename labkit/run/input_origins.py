"""Where a new run's input files came from: the completed run of the same
area whose outputs.json holds the file with the file's present digest —
the "uses" relation of the exploratory workflow
(docs/notes/2026-11-14-exploratory-workflow-plan.md, "Origins of input
files").

A digest proves equal content, not a unique origin: a deterministic rerun
or a copied file gives several runs the same output. So a run is ELIGIBLE
as the origin of an input when it is a completed run of the area whose
outputs.json holds the input's path with the input's digest, and:

    one eligible run              the origin
    several, none chosen          refused, the eligible runs listed
    chosen (`provenance.RunOutput`)  allowed also where one run is eligible;
                                  the chosen run must be eligible, else refused
    none eligible, none chosen    a plain input without origin — no refusal

A run whose record does not read is never eligible, and what it wrote
cannot be read: an automatic decision — the one eligible run, or no
origin — is then made without it. The decision carries every such run of
the area with the kind of its failure (`runs.UnreadableRun`: missing,
access, malformed, or a record of a schema version this labkit does not
read), for each input alike, since none can be ruled out
(`InputOrigin.origin_unreadable_runs`, `unreadable_warning`). After a
format break the area's records of the earlier schema are among them. A
chosen origin skips nothing: the script named it.

A repeat (`repeat_of`) is eligible: an origin says where a file came from,
not that its run may be adopted or reported (`runs.unreportable` decides
that). Runs of other areas are never looked up.

The decided origin is written into each input's entry in config.json
(`with_origins`; `runs.ORIGIN_RUN_KEY` and its neighbours, schema 5) and is
final: a later run that writes the same file does not reopen it. The
origin's own `repeat_of` is not copied; its record holds it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from labkit.formats.gate import with_way_out
from labkit.formats.runs import (
    COMPLETED,
    ORIGIN_CHOSEN_KEY,
    ORIGIN_RUN_KEY,
    ORIGIN_UNREADABLE_KEY,
    OTHER_SCHEMA,
    RECORD_CAUSE_TOLD,
    RECORD_CAUSES,
    RESERVED_DATA_KEYS,
    UNREADABLE,
    ArtefactError,
    OutputEntry,
    RunState,
    UnreadableRun,
    read_outputs,
    resolve_recorded,
    run_dirs,
    run_state,
    runs_path,
)
from labkit.run.provenance import declared_input


class OriginRefused(ValueError):
    """An input whose origin cannot be decided or whose chosen origin does
    not hold; the message is the whole sentence with its way out."""


@dataclass(frozen=True)
class AreaRun:
    """A run of the area as the origin check sees it (`area_runs`).

    Attributes:
        run_id: The run's directory name.
        state: Its `runs.run_state` as its files stand, liveness not asked.
        repeat_of: The run it repeats, None for a primary run.
        outputs: What its outputs.json registered, each path resolved;
            () for a run that is not completed or registered nothing.
        unread: Why its config.json or, completed, its outputs.json does
            not read, the reader's sentence; None when both read. Such a
            run is never eligible.
        unread_cause: The kind of that failure, one of
            `runs.RECORD_CAUSES`; set exactly when UNREAD is.
    """

    run_id: str
    state: RunState
    repeat_of: str | None
    outputs: tuple[OutputEntry, ...]
    unread: str | None = None
    unread_cause: str | None = None

    def __post_init__(self) -> None:
        if (self.unread is None) != (self.unread_cause is None):
            raise ValueError(f"{self.run_id}: an unread run names its cause")
        if self.unread_cause is not None and self.unread_cause not in RECORD_CAUSES:
            raise ValueError(f"{self.run_id}: cause {self.unread_cause!r}")


@dataclass(frozen=True)
class InputOrigin:
    """The origin decided for one input (`decide_origin`).

    Attributes:
        origin_run: The run that wrote the file; None for a plain input
            without origin.
        origin_chosen: True when the script chose the run (`RunOutput`) —
            chosen by the script, not confirmed by an auditor.
        origin_repeat_of: The run ORIGIN_RUN repeats, for the auditor's
            evidence; None when it repeats none or there is no origin.
        origin_unreadable_runs: Every run of the area whose record did
            not read, with the kind of failure, left out of an automatic
            decision — skipped records, not known to have written the
            file, only not ruled out; () when there is none or the script
            chose the run.
    """

    origin_run: str | None
    origin_chosen: bool
    origin_repeat_of: str | None
    origin_unreadable_runs: tuple[UnreadableRun, ...] = ()


#: a plain input without origin, decided with no unreadable run skipped;
#: a plain input that skipped one carries it, so ask `origin_run is None`
NO_ORIGIN = InputOrigin(None, False, None)


def eligible_runs(path: Path, sha256: str, runs: Sequence[AreaRun]) -> list[AreaRun]:
    """The runs among RUNS eligible as the origin of the file at PATH
    (resolved) whose digest is SHA256 (`runs.RECORD_SHA_CHARS` wide): the
    completed ones that read and whose outputs hold PATH with that digest,
    in RUNS' order."""
    return [
        r
        for r in runs
        if r.state == COMPLETED
        and r.unread is None
        and any(e.path == path and e.sha256 == sha256 for e in r.outputs)
    ]


def _named(r: AreaRun) -> str:
    """A run as a refusal lists it: its id, and the run it repeats."""
    return r.run_id if r.repeat_of is None else f"{r.run_id} (repeat of {r.repeat_of})"


def decide_origin(
    key: str,
    recorded: str,
    path: Path,
    sha256: str,
    chosen_run: str | None,
    runs: Sequence[AreaRun],
    runs_dir: Path,
) -> InputOrigin:
    """The origin of input KEY — RECORDED as the record writes its path,
    PATH resolved, SHA256 its present digest — among RUNS, the runs of the
    area under RUNS_DIR, with CHOSEN_RUN the run the script named
    (`provenance.RunOutput`) or None. The table in the module docstring
    decides; an automatic decision carries the area's unreadable runs.
    Raises OriginRefused naming KEY: several eligible runs and no
    choice; a chosen run that is no run of the area, not completed, did not
    register the file or recorded other bytes for it."""
    eligible = eligible_runs(path, sha256, runs)
    if chosen_run is None:
        skipped = tuple(
            UnreadableRun(r.run_id, r.unread_cause)
            for r in runs
            if r.unread_cause is not None
        )
        if not eligible:
            return InputOrigin(None, False, None, skipped)
        if len(eligible) == 1:
            only = eligible[0]
            return InputOrigin(only.run_id, False, only.repeat_of, skipped)
        raise OriginRefused(
            with_way_out(
                f"runlog: data[{key!r}] = {recorded}: {len(eligible)} completed "
                f"runs of this area wrote this file with these bytes — "
                f"{', '.join(_named(r) for r in eligible)} — and the digest "
                f"cannot tell which one this run reads",
                f'name the origin in the script: `runlog.RunOutput("{recorded}", '
                f'run="<one of them>")`',
            )
        )
    for r in eligible:
        if r.run_id == chosen_run:
            return InputOrigin(r.run_id, True, r.repeat_of)
    raise OriginRefused(
        with_way_out(
            f"runlog: data[{key!r}] = RunOutput({recorded}, run={chosen_run!r}): "
            + _not_eligible(chosen_run, recorded, path, runs, runs_dir),
            (
                f"name an eligible run: {', '.join(_named(r) for r in eligible)}"
                if eligible
                else "no completed run of this area wrote this file with these "
                "bytes — pass the plain path; the input is then recorded "
                "without origin"
            ),
        )
    )


def unreadable_warning(decided: Sequence[tuple[str, str, InputOrigin]]) -> str:
    """What a start is told once whose inputs DECIDED — each (key, its path
    as the record writes it, its origin) — were decided without the area's
    unreadable runs (`InputOrigin.origin_unreadable_runs`, not empty): each
    input with its decision, the skipped runs grouped by the kind of
    failure (`runs.RECORD_CAUSE_TOLD`), and the ways to a decision that
    does not rest on them. Whether a skipped run wrote one of the files
    cannot be told. A warning, not a refusal: an unreadable run elsewhere
    in the area does not hold this start."""
    inputs = "; ".join(
        f"data[{key!r}] = {recorded} as "
        + (origin.origin_run or "an input without origin")
        for key, recorded, origin in decided
    )
    skipped = list(
        dict.fromkeys(u for _, _, o in decided for u in o.origin_unreadable_runs)
    )
    groups = "; ".join(
        f"{RECORD_CAUSE_TOLD[cause]}: "
        + ", ".join(u.run for u in skipped if u.cause == cause)
        for cause in RECORD_CAUSES
        if any(u.cause == cause for u in skipped)
    )
    return (
        f"runlog: WARNING — origins decided without the area's runs whose "
        f"record does not read ({groups}); whether one of them wrote these "
        f"files cannot be told, and the record says so for each input. "
        f"Decided: {inputs}. To decide without them, name an origin in the "
        f'script (`runlog.RunOutput("<path>", run="<the run>")`)'
        + (
            ", or repair a record that is damaged or cannot be opened"
            if any(u.cause != OTHER_SCHEMA for u in skipped)
            else ""
        )
        + (
            "; a run of another schema version is read with the labkit that "
            "wrote it, or moved out of the area"
            if any(u.cause == OTHER_SCHEMA for u in skipped)
            else ""
        )
        + " (`runlog <area>` gives each one's reason)."
    )


def _not_eligible(
    chosen_run: str,
    recorded: str,
    path: Path,
    runs: Sequence[AreaRun],
    runs_dir: Path,
) -> str:
    """Why CHOSEN_RUN is no eligible origin of the file at PATH (RECORDED as
    the record writes it): no run of the area, not completed, the file not
    among its outputs, its record unreadable, or its recorded digest not
    the file's."""
    run = next((r for r in runs if r.run_id == chosen_run), None)
    if run is None:
        return (
            f"no run of this area has that id — an origin is looked up only "
            f"among the runs under {runs_dir}"
        )
    if run.unread is not None:
        return f"{chosen_run} does not read: {run.unread}"
    if run.state != COMPLETED:
        return f"{chosen_run} is not completed ({run.state} as its files stand)"
    held = [e for e in run.outputs if e.path == path]
    if not held:
        return f"{chosen_run} registered no output {recorded} (its outputs.json)"
    return (
        f"{chosen_run} recorded {recorded} with sha256 {held[0].sha256}, the "
        f"file now has other bytes — this run would not read what "
        f"{chosen_run} wrote"
    )


def area_runs(area: Path) -> list[AreaRun]:
    """Every run of AREA as the origin check sees it, oldest first; a
    directory without config.json is no run. A run whose config.json, or
    as a completed run whose outputs.json, does not read is carried with
    the reason (`AreaRun.unread`), not raised: it is never eligible, and
    only a choice that names it is refused. Its damage is held where the
    run is read for what it is (`answering_run`, finalize), not at every
    start in the area."""
    out: list[AreaRun] = []
    for rd in run_dirs(area):
        if rd.error is not None:
            out.append(
                AreaRun(rd.dir.name, UNREADABLE, None, (), rd.error, rd.error_cause)
            )
            continue
        if rd.config is None:
            continue
        state = run_state(rd.dir, alive=False)
        outputs: tuple[OutputEntry, ...] = ()
        unread, cause = None, None
        if state == COMPLETED:
            try:
                registered = read_outputs(rd.dir) or []
            except ArtefactError as exc:
                unread, cause = str(exc), exc.cause
            else:
                outputs = tuple(replace(e, path=e.path.resolve()) for e in registered)
        out.append(
            AreaRun(rd.dir.name, state, rd.config.repeat_of, outputs, unread, cause)
        )
    return out


def input_origins(area: Path, data: dict, described: dict) -> dict[str, InputOrigin]:
    """The origin of every input of a new run in AREA (`decide_origin`):
    DATA the script's `data=` mapping, DESCRIBED what
    `provenance.describe_data` made of it (its recorded path and digest per
    key). A chosen run is matched by name against the area's run
    directories, never opened as a path, so no id reaches another area.
    Raises OriginRefused as `decide_origin` and `area_runs` do."""
    runs = area_runs(area)
    out: dict[str, InputOrigin] = {}
    for key, value in data.items():
        entry = described[key]
        out[key] = decide_origin(
            key,
            entry["path"],
            resolve_recorded(entry["path"], area).resolve(),
            entry["sha256"],
            declared_input(key, value).chosen_run,
            runs,
            runs_path(area),
        )
    return out


def with_origins(described: dict, origins: dict[str, InputOrigin]) -> dict:
    """DESCRIBED, the `data=` entries `provenance.describe_data` made, with
    each input's decided origin from ORIGINS added to its entry — the form
    `runs.data_entries` reads back; the reserved keys (`runs.RESERVED_DATA_KEYS`,
    no input) stay as they are. A new dict; DESCRIBED is not changed.
    Raises KeyError for an input without a decided origin: a gap fails at
    the write, not at the next read."""
    return {
        key: entry
        if key in RESERVED_DATA_KEYS
        else {
            **entry,
            ORIGIN_RUN_KEY: origins[key].origin_run,
            ORIGIN_CHOSEN_KEY: origins[key].origin_chosen,
            ORIGIN_UNREADABLE_KEY: [
                {"run": u.run, "cause": u.cause}
                for u in origins[key].origin_unreadable_runs
            ],
        }
        for key, entry in described.items()
    }
