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

A repeat (`repeat_of`) is eligible: an origin says where a file came from,
not that its run may be adopted or reported (`runs.unreportable` decides
that). Runs of other areas are never looked up.

The origins are checked at start and not yet written: the run record
carries them from schema 5 on, the plan's format step.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from labkit.formats.gate import with_way_out
from labkit.formats.runs import (
    COMPLETED,
    UNREADABLE,
    ArtefactError,
    OutputEntry,
    RunState,
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
            not read; None when both read. Such a run is never eligible.
    """

    run_id: str
    state: RunState
    repeat_of: str | None
    outputs: tuple[OutputEntry, ...]
    unread: str | None = None


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
    """

    origin_run: str | None
    origin_chosen: bool
    origin_repeat_of: str | None


#: what a plain input without origin is decided as
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
    decides. Raises OriginRefused naming KEY: several eligible runs and no
    choice; a chosen run that is no run of the area, not completed, did not
    register the file or recorded other bytes for it."""
    eligible = eligible_runs(path, sha256, runs)
    if chosen_run is None:
        if not eligible:
            return NO_ORIGIN
        if len(eligible) == 1:
            only = eligible[0]
            return InputOrigin(only.run_id, False, only.repeat_of)
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
            out.append(AreaRun(rd.dir.name, UNREADABLE, None, (), rd.error))
            continue
        if rd.config is None:
            continue
        state = run_state(rd.dir, alive=False)
        outputs: tuple[OutputEntry, ...] = ()
        unread = None
        if state == COMPLETED:
            try:
                registered = read_outputs(rd.dir) or []
            except ArtefactError as exc:
                unread = str(exc)
            else:
                outputs = tuple(replace(e, path=e.path.resolve()) for e in registered)
        out.append(AreaRun(rd.dir.name, state, rd.config.repeat_of, outputs, unread))
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
