"""registration_station — finalize's station 2: which workflow binds the
answering run, read from the first measurements' own type
(`registration_hold.workflow`), the hold on a type changed since, and the
holds of that workflow (`protocol_history.Workflow`) — confirmation and
an undecided type the first-measurement lock
(`registration_hold.registration_changes`), exploration each run's own
text and step (`exploration_hold`). Read-only; finalize tells what it
finds.
"""

from __future__ import annotations

from pathlib import Path

from labkit.formats import evidence
from labkit.formats.area_state import (
    AreaState,
    missing_start_warning,
    unread_start_warning,
)
from labkit.formats.gate import Findings, GateFinding
from labkit.formats.repo import git_root
from labkit.formats.protocol_history import Workflow
from labkit.gates import exploration_hold
from labkit.gates.registration_hold import (
    corrected_in_place,
    declares_as_result,
    lost_record_warnings,
    registration_changes,
    type_changes,
    without_record_of,
    workflow,
)


def station_changes(
    area: Path,
    protocol: Path,
    pid: str | None,
    run: Path,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> tuple[Workflow, list[GateFinding]]:
    """(the workflow, the holds) of the answering RUN of PROTOCOL (stamped
    id PID). The workflow is the one reading (`registration_hold.workflow`):

    0. no stamped id — UNDECIDED, nothing held here;
    1. something leaves the first measurement untold — UNDECIDED, and
       that hold is the one finding: the type that decides the workflow
       is that run's;
    2. the holds on a type changed since the first measurement
       (`type_changes`), in every workflow;
    3. EXPLORATORY — `exploration_hold.exploration_changes`; CONFIRMATORY
       and UNDECIDED — the first-measurement lock (`registration_changes`):
       an undecided or unreadable type is never read as exploratory.

    Raises RuntimeError when git fails."""
    if pid is None:  # 0
        return Workflow.UNDECIDED, []
    root = git_root(protocol)
    measured = state.measured_of(pid)
    read = workflow(area, protocol, pid, root, measured)
    if read.untold:  # 1
        return read.workflow, read.untold
    typed = type_changes(protocol, pid, run, root, read.seen, state)  # 2
    if read.workflow is Workflow.EXPLORATORY:  # 3
        return read.workflow, typed + exploration_hold.exploration_changes(
            area, protocol, pid, run, root, measured, state, held
        )
    return read.workflow, typed + registration_changes(
        area, protocol, pid, run, state, held
    )


def check_registration(
    findings: Findings,
    area: Path,
    protocol: Path,
    pid: str | None,
    run: Path,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> None:
    """Hold the answering RUN to its workflow's registration
    (`station_changes`, read from STATE, the area's state built once); a
    note when it holds — what the workflow held —, and one per field a
    correction released (`corrected_in_place`), so the release names what
    changed and why. With a stamped id PID, the runs without a record that
    hold no number are warned of either way (`lost_record_warnings`), and
    so are start files that do not read (`area_state.unread_start_warning`)
    and start files a run's record names and nobody finds
    (`area_state.missing_start_warning`); while one of them is a record of
    unknown protocol, the confirmatory note names the first measurement as
    the first that reads and says that an earlier one is not excluded.
    HELD is the area's audit evidence, read once at the entry."""
    flow, changes = station_changes(area, protocol, pid, run, state, held)
    findings.take_all(changes)
    unassigned: tuple[str, ...] = ()
    if pid is not None:
        measured = state.measured_of(pid)
        without = without_record_of(measured)
        findings.take_all(lost_record_warnings(without))
        unread = unread_start_warning(
            measured.unread_starts, measured.unassigned_starts
        )
        # of the protocol's own runs it is the hold above; here the ones
        # nothing assigns
        missing = missing_start_warning((), measured.unassigned_missing_starts)
        for warning in (unread, missing):
            if warning is not None:
                findings.take(warning)
        unassigned = without.unassigned
    if changes:
        return
    corrected = corrected_in_place(area, protocol, pid, run, state, held, flow=flow)
    findings.note(
        (
            "  exploratory: each step the answering run builds on declares its "
            "changes"
            + (
                ", and what the number is about is the text the answering run measured"
                if declares_as_result(state.text_of(protocol), run)
                else "; the protocol as it stands is held to the answering run's "
                "text once it adopts that run as its result"
            )
            if flow is Workflow.EXPLORATORY
            else "  what the number is about and the promise block are the ones "
            "the first measurement "
            + (
                "that reads registered — an earlier measurement is not excluded "
                f"while the record of run {', '.join(unassigned)} does not read "
                "(the warning above)"
                if unassigned
                else "registered"
            )
        )
        + (", but for the fields corrected in place below" if corrected else "")
    )
    for line in corrected:
        findings.note(f"  {line}")
