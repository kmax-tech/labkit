"""exploration_hold — finalize's station 2 for an exploratory protocol:
each run is bound to its own text and the step it made, not to the first
measurement (docs/notes/2026-11-14-exploratory-workflow-plan.md,
"Exploratory per-run binding"). Which workflow applies is the first
measurements' own type (`registration_hold.workflow`); a confirmatory or
undecided protocol keeps the first-measurement lock unchanged.

Held, in this order, for the answering run and every basis it builds on,
back to a run without a step (`step_chain`) — the runs its release depends
on, and no other:

1. each run's own text and step read back (`protocol_history.step_then`);
   a step that cannot be told holds, never reads as "no step";
2. each step's declared changes are the differences of its run's own text
   from its basis run's own text (`protocol_history.step_change_gaps`) —
   a guaranteed statement about the registered protocol parts only; a
   method changed in code alone is the analysis audit's question;
3. the run without a step reads as the first measurements without a step
   registered (`unstepped_holds`): a change in exploration is declared;
4. the protocol as it stands is the answering run's own text in what the
   number is about (`live_holds`): the result is read under the text it
   was measured under.

Read-only; finalize tells what it finds.
"""

from __future__ import annotations

from pathlib import Path

from labkit.checks.audit_binding import AuditError
from labkit.formats import evidence, protocol_history
from labkit.formats.area_state import AreaState, Measured
from labkit.formats.commands import (
    builds_on_command,
    gate_command,
    register_anew,
)
from labkit.formats.gate import (
    OPEN_RULE,
    TECHNICAL_RULE,
    GateFinding,
    blocker,
)
from labkit.formats.protocol_history import StepThen
from labkit.formats.runs import RunDir, read_run_dir, run_path
from labkit.gates.registration_hold import (
    anew_way,
    awaiting_followup,
    by_cause,
    first_measurement,
    quoted_changes,
    scope_now,
    scope_rule,
    split_hold,
    unread_hold,
    waiting_refs,
)
from labkit.gates.ways_out import handover


def exploration_changes(
    area: Path,
    protocol: Path,
    pid: str,
    run: Path,
    root: Path | None,
    measured: Measured,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> list[GateFinding]:
    """The holds of an exploratory PROTOCOL (stamped id PID) on its
    answering RUN, in the module's order: a chain that cannot be read
    stops there (what follows needs its texts); otherwise every step whose
    declared changes do not match, the run without a step against the
    first measurements, and the protocol as it stands against RUN's own
    text. MEASURED is what the area measured of PID, STATE the area's
    state, HELD its audit evidence. Outside a repository (ROOT None) no
    run's text reads back and nothing is held here. Raises RuntimeError
    when git fails."""
    if root is None:
        return []
    chain, unknown = step_chain(area, protocol, pid, run, root)
    if unknown is not None:
        return [unknown]
    found = [
        hold
        for later, basis in zip(chain, chain[1:])
        if (hold := step_gap_hold(protocol, pid, later, basis)) is not None
    ]
    found += unstepped_holds(area, protocol, pid, chain[-1], measured, root)
    found += live_holds(area, protocol, pid, run, chain[0], root, measured, state, held)
    return found


def step_chain(
    area: Path, protocol: Path, pid: str, run: Path, root: Path
) -> tuple[list[StepThen], GateFinding | None]:
    """(chain, None): RUN and every basis it builds on, back to a run
    without a step, each as its own text holds it (`step_then`), RUN
    first. ([read so far], the BLOCKER) where a link cannot be read: a
    run whose record does not read or is gone, a text that cannot be read
    back (`as_measured`: no commit, a lost patch, …) or a `[builds_on]`
    that does not read — the step is unknown, and what depends on it is
    held, never read as no step (`unknown_step_hold`). A basis named twice
    is a loop no start lets through; held as unknown too. Raises
    RuntimeError when git fails."""
    chain: list[StepThen] = []
    rd = read_run_dir(run)
    while True:
        if rd.config is None:
            why = f"run {rd.dir.name} does not read: {rd.error or 'no record'}"
            return chain, unknown_step_hold(area, protocol, pid, chain, why)
        st = protocol_history.step_then(protocol, rd, root)
        if st.unknown is not None or st.text is None:
            return chain, unknown_step_hold(
                area, protocol, pid, chain, st.unknown or st.where
            )
        chain.append(st)
        if st.step is None:
            return chain, None
        if st.step.run in {s.run_id for s in chain}:
            why = f"run {st.run_id} builds on {st.step.run}, which builds on it again"
            return chain, unknown_step_hold(area, protocol, pid, chain, why)
        rd = read_run_dir(run_path(area, st.step.run))


def unknown_step_hold(
    area: Path, protocol: Path, pid: str, chain: list[StepThen], why: str
) -> GateFinding:
    """The BLOCKER when a run of the answering run's CHAIN cannot be read
    back (WHY): which registration it was measured under is unknown, so
    the comparison did not run and nothing says the steps hold. The way
    back: the run's record or its uncommitted.patch restored from git or a
    backup, the commit fetched; where it cannot be read back at all, a new
    registration or a handover."""
    through = (
        f" (reached from the answering run {chain[0].run_id} through its steps)"
        if chain
        else ""
    )
    return blocker(
        f"the step a run was measured under cannot be told: {' '.join(why.split())}"
        f"{through} — the comparison with its basis did not run, so nothing says "
        f"its changes are declared",
        fix="make it readable: the run's record or its uncommitted.patch restored "
        "from git or a backup, the commit from a clone that holds it (`git fetch`), "
        f"then `{gate_command('finalize', area)}`; where it cannot be "
        f"read back at all, {register_anew(pid)}; or {handover(protocol)}",
        rule=TECHNICAL_RULE,
    )


def step_gap_hold(
    protocol: Path, pid: str, later: StepThen, basis: StepThen
) -> GateFinding | None:
    """The BLOCKER when LATER's step declares other changes than the
    differences of LATER's own text from its BASIS's
    (`protocol_history.step_change_gaps`): each entry to add and each to
    remove, named. The run keeps the text it saw, so the way out is the
    step written as the texts stand and a new run measured under it — or
    a new registration; never an edited run. None when the step matches.
    Raises BlockError or PromiseError on a head or block that does not
    read."""
    assert later.step is not None and later.text is not None and basis.text
    gaps = protocol_history.step_change_gaps(basis.text, later.text, later.step)
    if not gaps.undeclared and not gaps.not_shown:
        return None
    parts = []
    if gaps.undeclared:
        parts.append(f"not declared: {quoted_changes(list(gaps.undeclared))}")
    if gaps.not_shown:
        parts.append(
            f"declared, but not between the texts: {quoted_changes(list(gaps.not_shown))}"
        )
    return blocker(
        f'run {later.run_id} made the step "{later.step.id}" on {basis.run_id}, and '
        f"its declared changes are not the differences of the two texts — "
        f"{'; '.join(parts)} — a step declares every change of the registration "
        f"from its basis, no more and no fewer",
        fix=f"write the step as the texts stand (`{builds_on_command(protocol, basis.run_id)}` "
        f"computes the changes), measure again and audit that run — {later.run_id} "
        f"keeps the text it ran under; or, {anew_way(pid)}",
        rule=OPEN_RULE,
    )


def unstepped_holds(
    area: Path,
    protocol: Path,
    pid: str,
    origin: StepThen,
    measured: Measured,
    root: Path,
) -> list[GateFinding]:
    """The holds on ORIGIN, the run of the chain that declares no step: it
    is measured under the registration, which is the text of the first
    measurements that declare no step (MEASURED's first groups). A first
    measurement whose text or step cannot be read back holds the
    comparison (`unread_hold`); first measurements without a step that saw
    different registrations hold as in confirmation (`split_hold`: which
    stood cannot be told); ORIGIN differing from them is a change without
    a step, named with the way to declare it. Raises RuntimeError when
    git fails."""
    registered: list[tuple[RunDir, str]] = []
    unread: list[str] = []
    for rd in (rd for group in measured.first_groups for rd in group):
        st = protocol_history.step_then(protocol, rd, root)
        if st.unknown is not None or st.text is None:
            unread.append(st.unknown or st.where)
        elif st.step is None:
            registered.append((rd, st.text))
    if unread:
        return [unread_hold(area, protocol, pid, unread)]
    if not registered:
        return []
    (first, first_text), *rest = registered
    for other, other_text in rest:
        diffs = protocol_history.registration_differences(first_text, other_text)
        if diffs:
            return split_hold(protocol, pid, first, other, diffs)
    if any(rd.dir.name == origin.run_id for rd, _ in registered):
        return []
    assert origin.text is not None
    diffs = protocol_history.registration_differences(first_text, origin.text)
    if not diffs:
        return []
    return [
        blocker(
            f"run {origin.run_id} was measured without a step, and its registration "
            f"differs from the first measurement {first.dir.name}'s: "
            f"{quoted_changes(diffs)} — in exploration a change is declared as a "
            f"step on the run it builds on",
            fix=f"declare the step (`{builds_on_command(protocol, first.dir.name)}`, "
            f"or on another run it builds on), measure again and audit that run — "
            f"{origin.run_id} keeps the text it ran under; or, {anew_way(pid)}",
            rule=OPEN_RULE,
        )
    ]


def live_holds(
    area: Path,
    protocol: Path,
    pid: str,
    run: Path,
    answering: StepThen,
    root: Path,
    measured: Measured,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> list[GateFinding]:
    """The holds on PROTOCOL as it stands against ANSWERING, the answering
    RUN's own text, in what the number is about (`scope_now` with the
    answering run in place of the first measurements, so a correction in
    place releases a field as it does in confirmation): the result is
    read under the text it was measured under, and a changed text no run
    measured would present it under another question. One BLOCKER per
    cause (`by_cause`, `scope_rule`); the ways out: measure the change as a
    step on RUN, the text back as RUN saw it, or a new registration. A
    release that cannot be checked holds as such. Raises RuntimeError when
    git fails."""
    rd = read_run_dir(run)
    try:
        now = scope_now(
            area, protocol, pid, run, root, measured, state, held, against=[rd]
        )
        waiting = (
            awaiting_followup(area, protocol, state.text_of(protocol), run, held)
            if now is not None and now.kept
            else {}
        )
    except AuditError as exc:
        return [
            blocker(
                f"whether a correction in place releases what the number is about "
                f"cannot be checked: {exc.why}",
                fix=exc.fix
                or f"repair what the sentence names, then "
                f"`{gate_command('finalize', area)}`",
                rule=TECHNICAL_RULE,
            )
        ]
    if now is None or not now.kept:
        return []
    shown = first_measurement(protocol, rd, root)
    refs = waiting_refs(now.kept, waiting)
    return [
        blocker(
            f"what the number is about changed after the answering run "
            f"{answering.run_id}: {quoted_changes(cause)} (as the protocol stands "
            f"now; no run measured under it yet) — the result would be read under a "
            f"text no run measured",
            fix=f"measure the change as a step on {answering.run_id} "
            f"(`{builds_on_command(protocol, answering.run_id)}`, then the run and "
            f"its audit); or restore {', '.join(w for w, _, _ in cause)} as "
            f"{answering.run_id} saw them{shown.shown}"
            + (
                f" — or, a description corrected in place, the follow-up analysis "
                f"audit judges {', '.join(r for r in cause_refs if r)}"
                if all(cause_refs)
                else ""
            )
            + f"; or, {anew_way(pid)}",
            step=shown.step,
            rule=scope_rule(cause),
        )
        for cause, cause_refs in by_cause(now.kept, refs)
    ]
