"""registration_hold — whether the answering run holds what its protocol's
first measurement registered, finalize's station 2 (and the declaring
protocol station 3 withdraws first): the promise block as the first measurement recorded it
(`registration_changes`, `check_registration`), what the number is about
as first measured (`scope_changes`), which change a correction in place
releases (`resolved_corrections`, `awaiting_followup`) and the phrasing
of each hold and its way back. Read-only; finalize tells what it finds.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labkit.formats import evidence
from labkit.formats.commands import gate_command
from labkit.formats.gate import (
    OPEN_RULE,
    TECHNICAL_RULE,
    GateFinding,
    RuleAssignment,
    blocker,
    cited_rule,
    withdrawn_first,
)
from labkit.formats import (
    findings as audit_findings,
    promises,
    protocol_block,
)
from labkit.formats.gate import Findings
from labkit.formats.runs import (
    RunDir,
    patch_text,
    read_run_dir,
    recorded_commit,
    read_run_config,
)
from labkit.formats.answering_run import first_registrations
from labkit.formats.area_state import AreaState, Measured
from labkit.formats import protocol_history
from labkit.formats.reference import LAB_035
from labkit.formats.repo import (
    rel_posix,
    area_protocols,
    only_protocol,
    git_root,
)
from labkit.formats.commands import (
    Command,
    RESTORE,
    audit_command,
    measure_command,
    withdraw_command,
)
from labkit.gates.ways_out import unclear_correction, HANDOVER
from labkit.formats.commands import register_anew
from labkit.checks.audit_binding import AuditError, covering_analysis
from labkit.formats.protocol_check import (
    FieldPlaceError,
    field_name,
)
from labkit.checks.run_record_check import (
    code_since_run,
)
from labkit.formats.findings import corrected_field
from labkit.formats.followup import (
    Correction,
    awaited_corrections,
    chain,
    released_corrections,
)

LAB_003 = cited_rule("LAB-003 No run without an intent paragraph")
#: the parts of the head the scope hold compares that no sentence of a rule
#: names, as `protocol_history.scope_differences` labels them
UNNAMED_HEAD_PARTS = ("kind", "[kept]")
#: the head's registered comparison as `scope_differences` labels it: LAB_035
#: fixes it before the first measurement
REFERENCE_PART = "[reference]"


def scope_rule(diffs: list[tuple[str, str, str]]) -> RuleAssignment:
    """The rule a scope hold records for DIFFS, which must be the
    differences of one cause (`by_cause`; the comparison beside another
    part raises): LAB_035 where they are the registered comparison
    (REFERENCE_PART) — a changed one is reported as exploratory, which the
    hold's last way out, the exploratory successor, is; LAB_003 where its
    text names every changed field; an open assignment as soon as one
    difference is in a part of UNNAMED_HEAD_PARTS. The hold blocks either
    way. Raises ValueError for the comparison together with another part:
    two causes are two findings. Pure."""
    changed = {what for what, _, _ in diffs}
    if REFERENCE_PART in changed:
        if changed != {REFERENCE_PART}:
            raise ValueError(
                f"a scope hold records one rule, and {sorted(changed)} holds the "
                f"registered comparison beside another part (`by_cause` parts them)"
            )
        return LAB_035
    return OPEN_RULE if changed & set(UNNAMED_HEAD_PARTS) else LAB_003


def by_cause(
    diffs: list[tuple[str, str, str]], refs: list[str | None]
) -> list[tuple[list[tuple[str, str, str]], list[str | None]]]:
    """DIFFS (what, from, to) with their REFS (`waiting_refs`, one per
    difference) as the causes a scope hold tells one finding each for: the
    fields and head parts first, then the registered comparison
    (REFERENCE_PART) — another rule fixes it (`scope_rule`) and no
    correction releases it, so its way out is its own. A cause without a
    difference is left out. Pure."""
    pairs = list(zip(diffs, refs, strict=True))
    groups = (
        [(d, r) for d, r in pairs if d[0] != REFERENCE_PART],
        [(d, r) for d, r in pairs if d[0] == REFERENCE_PART],
    )
    return [([d for d, _ in g], [r for _, r in g]) for g in groups if g]


def registration_rule(was: dict, now: dict) -> RuleAssignment:
    """The rule the hold on a changed registration records, from the promise
    snapshots WAS (the first measurement's) and NOW (the answering run's):
    LAB_003, whose text names a promise's sentence, key and constant — an
    id added or dropped changes those —; an open assignment as soon as a
    promise's declared scope changed, which no sentence of it names. The
    hold blocks either way. Pure."""
    return OPEN_RULE if promises.scope_changed_ids(was, now) else LAB_003


def registration_changes(
    area: Path,
    protocol: Path,
    pid: str | None,
    run: Path | None,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> list[GateFinding]:
    """The answering RUN holds the registration its protocol's first
    measurement recorded (K3, docs/notes/2026-10-27-new-registration-contracts.md):
    the promise block in each run's record (`promises.snapshot`: ids, keys,
    sentences through the block's digest, scopes, constants — not the code
    the scopes name, so a repair measured again under the same promises
    passes). A run whose block differs from the first measurement's is held,
    each change named — sentences, keys, constants and scopes together,
    from the protocol texts both runs saw (`named_changes`) — with the way
    out: restore what was registered and measure again, or register anew.
    Every lane: a bar moved after a result was seen answers no registered
    question at any repeat cost. Run here, after every measurement, and not
    first at the adoption, so no further run or audit goes into a changed
    registration before it is named. The first measurements are every run at each first
    position (`answering_run.first_registrations`), not one chosen by name;
    when they recorded different blocks, which one stood cannot be told and
    no run answers a registered question: held too, the ways out a new
    registration that declares its changes against each (K1,
    `report_replacement.replacement_gaps`) or a handover without a declared
    result. Empty without an answering run, a stamped id PID, or a block in
    the records. Raises RuntimeError when git fails."""
    if pid is None or run is None:
        return []
    root = git_root(protocol)
    measured = state.measured_of(pid)
    scope = scope_changes(area, protocol, pid, run, root, measured, state, held)
    cfg = read_run_config(run)
    now = cfg.promises if cfg is not None else None
    if now is None:
        return scope
    registered = first_registrations(measured.first_groups)
    if len(registered) > 1:
        named = ", ".join(
            f"{rd.dir.name} (block {sha})" for sha, (rd, _) in registered.items()
        )
        return scope + [
            blocker(
                f"the first measurements recorded different registrations: {named} — "
                f"which one stood before the number cannot be told, so no run of "
                f"this protocol answers a registered question",
                fix="either "
                + register_anew(
                    pid,
                    "per change against each of these registrations (report-check "
                    "of the new protocol lists them)",
                )
                + f"; or {HANDOVER}",
                rule=LAB_003,
            )
        ]
    if not registered:
        return scope
    ((sha, (first, snap)),) = registered.items()
    if now["block_sha"] == sha:
        return scope
    changes, restores = named_changes(
        protocol, first, read_run_dir(run), snap, now, root
    )
    restore_from = shown_then(protocol, first, root)
    return scope + [
        blocker(
            f"the registration changed after the first measurement {first.dir.name}: "
            f"{'; '.join(changes)} (recorded by the answering run {run.name}) — a "
            f"bar set after a result was seen does not answer the registered "
            f"question",
            fix=f"restore the [[promise]] tables as {first.dir.name} "
            f"registered them ({'; '.join(restores)}){restore_from}, "
            f"and measure again, then audit that run (the earlier runs stay); or, "
            f"when the registration cannot be answered as written, "
            + register_anew(pid)
            + " — the earlier protocol, its runs and their verdict stay",
            rule=registration_rule(snap, now),
        )
    ]


def restore_step(protocol: Path, first: RunDir, root: Path | None) -> Command | None:
    """The restore of a scope hold as a step (`commands.RESTORE`): the `git
    show` of PROTOCOL as the first measurement FIRST's commit holds it —
    what `shown_then` names in words; None without a recorded commit or a
    repository. Read by `next_step` to tell a restore from another hold."""
    commit = recorded_commit(first.config) if first.config is not None else None
    if not commit or root is None:
        return None
    rel = rel_posix(protocol, root)
    return Command(RESTORE, f"git show {commit[:12]}:{rel}")


def shown_then(protocol: Path, first: RunDir, root: Path | None) -> str:
    """The clause that shows PROTOCOL as the first measurement FIRST saw it:
    the `git show` of its recorded commit, and its uncommitted.patch where
    the run kept one; "" without a recorded commit or a repository."""
    commit = recorded_commit(first.config) if first.config is not None else None
    if not commit or root is None:
        return ""
    rel = rel_posix(protocol, root)
    return f" — `git show {commit[:12]}:{rel}` shows them as committed then" + (
        f", runs/{first.dir.name}/uncommitted.patch what its tree changed"
        if patch_text(first.dir)
        else ""
    )


#: how much of a field's old and new value a scope hold quotes
SCOPE_QUOTE = 120


def scope_changes(
    area: Path,
    protocol: Path,
    pid: str,
    run: Path,
    root: Path | None,
    measured: Measured,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> list[GateFinding]:
    """The answering RUN holds what its protocol's first measurement said the
    number is about (`protocol_history.scope_differences`: the question and
    its terms, the data, the exclusions, the unit, the head's kind,
    `[kept]` and `[reference]`), read from the protocol each run saw (`as_measured`) —
    at every kind, so a computation, which has no promise block, is held too.
    Two texts are held to it, in this order: the protocol as the answering
    run saw it, and the protocol as it stands — a field rewritten after the
    last measurement is a change before any run carries it, and an audit of
    the first run on the rewritten text would release it otherwise
    (docs/notes/2026-11-02-registered-field-repair.md). Both
    comparisons release a field the same way (`released_fields`): a
    correction in place judged `resolved` by a follow-up that covers RUN as
    it stands, the field as RUN saw it and as it stands one text — so a run
    measured again under a corrected field, after a code repair, is
    released by a follow-up on that run, never by the verdict on an earlier
    one. A change
    no correction releases is a BLOCKER naming each field with its old and
    new value and the way out: restore them — and, when a run measured
    under the change, measure again — or register anew. A code change
    measured again under the same fields passes: what the run computes is
    the analysis audit's question, not this one. The first measurements are
    every run at each first position (HELD, what the area measured of PID:
    `area_state.Measured.first_groups`); the answering run, when it is
    one of them, has no run text to compare, the text as it stands still
    is. In a repository, a text either comparison needs that cannot be read
    back — a first measurement's, the answering run's — is a BLOCKER of its
    own naming the run, git's or the record's reason and the way back
    (`unread_hold`): the comparison could not run, which is no "nothing
    changed" (docs/notes/2026-11-03-finalize-hold-missing-once.md).
    Raises RuntimeError when git fails."""
    firsts = [rd for group in measured.first_groups for rd in group]
    others = [rd for rd in firsts if rd.dir.resolve() != run.resolve()]
    if root is not None:
        needed = [*firsts, *([read_run_dir(run)] if others else [])]
        unread = protocol_history.unread_measurements(protocol, needed, root)
        if unread:
            return [unread_hold(area, pid, unread)]
    try:
        return _scope_held(
            area, protocol, pid, run, root, others, measured, state, held
        )
    except AuditError as exc:
        # whether a follow-up's release still covers the run cannot be told:
        # held as that, never as an unreleased change whose way back would
        # undo a correction
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


def _scope_held(
    area: Path,
    protocol: Path,
    pid: str,
    run: Path,
    root: Path | None,
    others: list[RunDir],
    measured: Measured,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> list[GateFinding]:
    """`scope_changes` once every text it compares reads: the hold of the
    answering run's text, then of the protocol as it stands. Raises
    AuditError when a release cannot be checked (`resolved_corrections`),
    RuntimeError when git fails."""
    seen, _ = (
        protocol_history.as_measured(protocol, read_run_dir(run), root)
        if others
        else (None, "")
    )
    if seen is not None:
        found = protocol_history.first_measured_differences(
            protocol, others, seen, root, protocol_history.scope_differences
        )
        if found is not None:
            first, all_diffs = found
            text = state.text_of(protocol)
            diffs, _ = released_fields(all_diffs, area, protocol, text, run, seen, held)
            if diffs:
                refs = waiting_refs(
                    diffs,
                    awaiting_followup(area, protocol, text, run, held),
                    moved_fields(seen, text),
                )
                return seen_hold(
                    pid,
                    run.name,
                    first_measurement(protocol, first, root),
                    diffs,
                    refs,
                    audit_command(area, "--mode", "analysis", protocol=protocol),
                )
    now = scope_now(area, protocol, pid, run, root, measured, state, held)
    if now is None or not now.kept:
        return []
    text = state.text_of(protocol)
    refs = waiting_refs(now.kept, awaiting_followup(area, protocol, text, run, held))
    # the code's state is read only where a way depends on it: at least one
    # cause has every held field's correction decided. `measure` and
    # `withdraw` below are one answer for the whole hold; `now_hold` uses
    # `measure` only in the way of a cause decided like that
    any_cause_decided = any(
        all(cause_refs) for _, cause_refs in by_cause(now.kept, refs)
    )
    code_changed = any_cause_decided and code_since_run(area, run)[0]
    declaring = declaring_protocol(protocol, text, run, state) if code_changed else None
    return now_hold(
        pid,
        run.name,
        first_measurement(protocol, now.first, root),
        now.kept,
        refs,
        audit_command(area, "--mode", "analysis", protocol=protocol),
        measure=measure_command(area) if code_changed else None,
        withdraw=withdraw_command(declaring) if declaring else None,
    )


@dataclass(frozen=True)
class FirstMeasurement:
    """The first measurement a scope hold names: its RUN_ID, the clause
    saying where its text can be read (`shown_then`) and the step that
    restores it (`restore_step`)."""

    run_id: str
    shown: str
    step: Command | None


def first_measurement(
    protocol: Path, first: RunDir, root: Path | None
) -> FirstMeasurement:
    """FIRST as a scope hold on PROTOCOL names it (`FirstMeasurement`).
    Reads git through `shown_then` and `restore_step`."""
    return FirstMeasurement(
        first.dir.name,
        shown_then(protocol, first, root),
        restore_step(protocol, first, root),
    )


def waiting_refs(
    diffs: list[tuple[str, str, str]],
    waiting: dict[str, str],
    moved: set[str] | frozenset[str] = frozenset(),
) -> list[str | None]:
    """Per difference of DIFFS (what, from, to), the ref of the decided
    correction a follow-up would judge for its field (WAITING, by
    `field_name`, `awaiting_followup`), None where there is none — or where
    the field moved (MOVED: the run saw another text than the protocol
    holds now, so no verdict on this text covers the run). A hold leads
    with the follow-up only when every difference has a ref. Pure."""
    return [
        None if what in moved else waiting.get(field_name(what)) for what, _, _ in diffs
    ]


def seen_hold(
    pid: str,
    run_id: str,
    first: FirstMeasurement,
    diffs: list[tuple[str, str, str]],
    refs: list[str | None],
    analysis: Command,
) -> list[GateFinding]:
    """The BLOCKERs on DIFFS — what the number is about, changed since
    FIRST, as the answering run RUN_ID saw the protocol —, one per cause
    (`by_cause`: the fields, the registered comparison), each with its rule
    (`scope_rule`) and its own way out: where every difference of the
    cause has its correction decided (REFS, `waiting_refs`), the follow-up
    audit on RUN_ID (ANALYSIS) that judges them, since a verdict on an
    earlier run releases nothing for this one; otherwise the restore and
    measuring again, with the correction route for the fields that have
    one (`correction_way`). Registering anew is always the last way.
    Pure."""
    found: list[GateFinding] = []
    for cause, cause_refs in by_cause(diffs, refs):
        labels = _labels(cause)
        restore = (
            f"restore {labels} as {first.run_id} registered them"
            f"{first.shown}, and measure again, then "
            f"audit that run (the earlier runs stay)"
        ) + description_added(cause)
        if all(cause_refs):
            # run B measured under a correction released for an earlier
            # run: the follow-up on B judges it again
            fix = (
                f"the follow-up analysis audit on {run_id} "
                f"(`{analysis}`) "
                f"judges {', '.join(r for r in cause_refs if r)}, decided `fixed` "
                f"as a correction of {labels} in place — only its `resolved` "
                f"on that finding, judged on this run and this text, releases "
                f"the change; a verdict on an earlier run releases nothing "
                f"for this one; or, a changed definition, population or "
                f"question is no correction: {restore}; or, {anew_way(pid)}"
            )
        else:
            fix = f"{restore}{correction_way(cause)}; or, {anew_way(pid)}"
        found.append(
            blocker(
                f"what the number is about changed after the first measurement "
                f"{first.run_id}: {quoted_changes(cause)} (as the answering "
                f"run {run_id} saw the protocol) — a scope set after a "
                f"result was seen does not answer the registered question",
                fix=fix,
                step=first.step,
                rule=scope_rule(cause),
            )
        )
    return found


def now_hold(
    pid: str,
    run_id: str,
    first: FirstMeasurement,
    kept: list[tuple[str, str, str]],
    refs: list[str | None],
    analysis: Command,
    *,
    measure: Command | None,
    withdraw: Command | None,
) -> list[GateFinding]:
    """The BLOCKERs on KEPT — what the number is about, changed since FIRST
    in the protocol as it stands, no run measured under it —, one per cause
    (`by_cause`: the fields, the registered comparison), each with its rule
    (`scope_rule`) and its own way out: where every held field of the
    cause has its correction decided (REFS, `waiting_refs`) and the
    measuring code changed since RUN_ID (MEASURE, the command that measures
    again), the new run and its follow-up (ANALYSIS) that judges the
    corrections; decided and the code unchanged, the follow-up on the run
    as it stands, no new measurement owed; otherwise the restore, with the
    correction route for the fields that have one (`correction_way`).
    Registering anew is always the last way. MEASURE is one command for
    the whole hold, used only in the way of a cause whose every correction
    is decided. WITHDRAW, the withdrawal of a standing adoption, comes
    first in every finding returned, not only the first
    (`gate.withdrawn_first`). Pure."""
    found: list[GateFinding] = []
    for cause, cause_refs in by_cause(kept, refs):
        labels = _labels(cause)
        restore = (
            f"restore {labels} as {first.run_id} registered them"
            f"{first.shown} — the runs measured under them "
            f"stay; an audit that read the rewritten fields is owed again "
            f"(`labkit-next` names it)"
        ) + description_added(cause)
        if all(cause_refs) and measure is not None:
            # a code repair after the correction: the run that answers was measured
            # by other code, so a new run comes first and its follow-up judges the
            # correction on it — a follow-up of the old run would be held by the
            # changed code
            fix = (
                f"the measuring code changed since {run_id} ran: measure again "
                f"(`{measure}`), then the follow-up analysis audit on that "
                f"run (`{analysis}`) judges "
                f"{', '.join(r for r in cause_refs if r)}, decided "
                f"`fixed` as a correction of {labels} in place, beside the repair — "
                f"only its `resolved` on that finding, judged on the new run and "
                f"this text, releases the change; or, a changed definition, "
                f"population or question is no correction: {restore}; or, "
                f"{anew_way(pid)}"
            )
        elif all(cause_refs):
            # each held field's correction is decided: the follow-up that judges
            # it comes first, the way back after it
            fix = (
                f"the follow-up analysis audit on the run as it stands "
                f"(`{analysis}`) "
                f"judges {', '.join(r for r in cause_refs if r)}, decided `fixed` "
                f"as a correction of {labels} in place — only its `resolved` on "
                f"that finding, for exactly this text, releases the change, and no "
                f"new measurement is owed; or, a changed definition, population or "
                f"question is no correction: {restore}; or, {anew_way(pid)}"
            )
        else:
            fix = f"{restore}{correction_way(cause)}; or, {anew_way(pid)}"
        found.append(
            blocker(
                f"what the number is about changed after the first measurement "
                f"{first.run_id}: {quoted_changes(cause)} (as the protocol stands "
                f"now; no run measured under it yet) — a scope set after a result "
                f"was seen does not answer the registered question, and a new "
                f"measurement would carry the change",
                fix=fix,
                step=first.step,
                rule=scope_rule(cause),
            )
        )
    return withdrawn_first(found, withdraw)


def unread_hold(area: Path, pid: str, unread: list[str]) -> GateFinding:
    """The BLOCKER when the protocol as a first measurement or the answering
    run saw it cannot be read back (UNREAD, `unread_measurements`): what
    the number is about cannot be compared, so finalize does not say it is
    unchanged. The way back: make the text readable — the commit from a
    clone that holds it, the repository's missing objects restored — then
    finalize again; where it cannot be read back at all, the registration
    cannot be held and is made anew or handed over."""
    return blocker(
        f"what the number is about cannot be compared with its first measurement: "
        f"{'; '.join(' '.join(why.split()) for why in unread)} — the comparison "
        f"did not run, so nothing says the "
        f"registration is unchanged",
        fix=f"make it readable: the commit from a clone that holds it (`git fetch`), "
        f"the repository's missing objects restored (`git fsck` names them), then "
        f"`{gate_command('finalize', area)}`; where it cannot be read back at all, "
        f"{anew_way(pid)}; or {HANDOVER}",
        rule=TECHNICAL_RULE,
    )


def anew_way(pid: str) -> str:
    """The last way out of a scope hold on protocol PID: a new registration."""
    return (
        "when the registration cannot be answered as written, "
        + register_anew(pid)
        + " — the earlier protocol, its runs and their verdict stay"
    )


def moved_fields(seen: str, text: str) -> set[str]:
    """What the number is about in which SEEN, the protocol as a run saw
    it, and TEXT, the protocol as it stands, differ — by the labels
    `protocol_history.scope_differences` names. Pure."""
    return {what for what, _, _ in protocol_history.scope_differences(seen, text)}


def declaring_protocol(
    protocol: Path, text: str, run: Path, state: AreaState
) -> Path | None:
    """PROTOCOL (TEXT its text) when it declares RUN as its result, so a
    hold on RUN withdraws first (`gate.withdrawn_first`); None otherwise,
    and while the declaration is an adoption's proposal under its own
    check (STATE's `adoption_pending`): no adoption stands to withdraw."""
    if protocol_block.declared_run_shown(text) != run.name:
        return None
    return None if state.adoption_pending_for(protocol) else protocol


#: the way a field corrected in place is released (`scope_now`)
CORRECTION_ROUTE = (
    "an audit finding that names the field as its place decided `fixed`, "
    "then a follow-up analysis audit on the run as it stands whose `resolved` "
    "on that finding judged exactly this text — a fresh audit without that "
    "verdict releases nothing"
)


#: the clause of a scope hold whose every held field only grew
DESCRIPTION_ADDED = (
    " — the registered text stands inside the new one: an addition that only "
    "describes what was delivered, the number unchanged, goes into the Conclusion "
    "or the report after the restore, not into the registered field; one that "
    "changes the data, the population or a bar is no description, and the "
    "restore is the way"
)


def description_added(diffs: list[tuple[str, str, str]]) -> str:
    """DESCRIPTION_ADDED when every field of DIFFS — (what, from, to), the
    values as `protocol_history.scope_value` compares them — only grew: the
    registered text stands inside the new one. "" when one was rewritten
    or DIFFS is empty. Pure. The hold is the same either way (labkit
    cannot tell a description from a changed population); the clause
    names where the addition belongs, so "restore" does not stand alone
    ("512 validation pairs" grown to "512 validation pairs and 512 test
    pairs")."""
    if not diffs or not all(old != new and old in new for _, old, new in diffs):
        return ""
    return DESCRIPTION_ADDED


def correction_way(diffs: list[tuple[str, str, str]]) -> str:
    """The clause of a hold on DIFFS (what, from, to) about correcting the
    fields: the correction route for the SCOPE_FIELDS among them a
    correction can release (`protocol_history.correctable`), named, and for
    the others that they stand as registered; "" without a scope field —
    the head's kind, `[kept]`, `[reference]` and a promise have no
    correction. The hold here offers it; the decision's line
    (`audit_decisions.repair_hint`) explains the condition and names no
    way of its own. Pure."""
    scope = [what for what, _, _ in diffs if what in protocol_history.SCOPE_FIELDS]
    fixable = [what for what in scope if protocol_history.correctable(what)]
    fixed_as_registered = [what for what in scope if what not in fixable]
    out = ""
    if fixable:
        out += (
            f"; or, {', '.join(fixable)} misdescribing the unchanged run: "
            f"{CORRECTION_ROUTE}"
        )
    if fixed_as_registered:
        out += (
            f"; {', '.join(fixed_as_registered)} "
            f"{protocol_history.STANDS_AS_REGISTERED}"
        )
    return out


@dataclass(frozen=True)
class ScopeNow:
    """The protocol as it stands against its first measurement FIRST in
    what the number is about: KEPT the differences (what, from, to) no
    correction releases, CORRECTED those a follow-up's `resolved` on a
    correction of that field released (`Correction`)."""

    first: RunDir
    kept: list[tuple[str, str, str]]
    corrected: list[tuple[tuple[str, str, str], Correction]]


def scope_now(
    area: Path,
    protocol: Path,
    pid: str,
    run: Path,
    root: Path | None,
    measured: Measured,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> ScopeNow | None:
    """PROTOCOL as it stands against the first measurements in what the
    number is about (`protocol_history.first_measured_differences`,
    `scope_differences`), each difference sorted by whether a correction
    releases it (`resolved_corrections`): a difference in a field whose
    correction RUN's covering follow-up judged `resolved`. Every prose field
    the hold compares is released that way but for
    `protocol_history.UNCORRECTABLE_FIELDS`; the head's kind, `[kept]` and
    `[reference]` never — they name no field a finding can place itself in
    (`protocol_history.correctable`). None without a difference. Raises RuntimeError when
    git fails."""
    firsts = [rd for group in measured.first_groups for rd in group]
    text = state.text_of(protocol)
    found = protocol_history.first_measured_differences(
        protocol, firsts, text, root, protocol_history.scope_differences
    )
    if found is None:
        return None
    first, diffs = found
    held_fields, corrected = released_fields(
        diffs, area, protocol, text, run, text, held
    )
    return ScopeNow(first, held_fields, corrected)


def released_fields(
    diffs: list[tuple[str, str, str]],
    area: Path,
    protocol: Path,
    text: str,
    run: Path,
    seen: str,
    held: evidence.AreaEvidence,
) -> tuple[list[tuple[str, str, str]], list[tuple[tuple[str, str, str], Correction]]]:
    """DIFFS — (what, from, to) against a first measurement — sorted into
    (kept, released): a difference is released when its field's correction
    is judged `resolved` by a follow-up that covers RUN and PROTOCOL as it
    stands (TEXT; `resolved_corrections`), and the field reads the same in
    SEEN, the protocol as RUN saw it — the run measured, the verdict judged
    and the text now one value. The one release of both comparisons in
    `scope_changes`; SEEN is TEXT where no run carries the text yet. Each
    field stands on its own: one released field releases no other. HELD is
    the area's audit evidence, read once. Raises RuntimeError when git
    fails."""
    return split_released(
        diffs,
        resolved_corrections(area, protocol, text, run, held),
        moved_fields(seen, text),
    )


def split_released(
    diffs: list[tuple[str, str, str]],
    resolved: dict[str, Correction],
    moved: set[str],
) -> tuple[list[tuple[str, str, str]], list[tuple[tuple[str, str, str], Correction]]]:
    """DIFFS (what, from, to) sorted into (kept, released): released where
    RESOLVED (by `field_name`, `resolved_corrections`) holds the field's
    correction and the field is not in MOVED — the labels in which the
    protocol as the run saw it and as it stands differ (`moved_fields`).
    Each field on its own: one field's correction releases no other. Pure."""
    kept: list[tuple[str, str, str]] = []
    corrected: list[tuple[tuple[str, str, str], Correction]] = []
    for d in diffs:
        c = resolved.get(field_name(d[0]))
        if c is None or d[0] in moved:
            kept.append(d)
        else:
            corrected.append((d, c))
    return kept, corrected


def resolved_corrections(
    area: Path, protocol: Path, text: str, run: Path, held: evidence.AreaEvidence
) -> dict[str, Correction]:
    """The fields of PROTOCOL (TEXT as it stands) a correction releases, by
    `field_name`: a finding that names the field as its place, decided
    `fixed` (`findings.corrected_field`), with a `resolved` verdict bound to
    that decision as it stands (`decision_digest`) in an analysis record
    that covers the area now — its code, promises, registration, the fields
    read before the run, RUN and what was shown of it
    (`audit_binding.covering_analysis`). A text edited after that verdict
    leaves the record covering nothing, a fresh audit carries no verdict,
    and a verdict on a finding of another field releases this one not:
    each is no correction. Empty when the area's records cannot be read —
    finalize's audit station names that. Raises AuditError when the state
    RUN was audited in cannot be computed (a registered output gone): then
    whether a release covers RUN cannot be told, and the caller holds that
    (`scope_changes`), never reads it as no correction.
    HELD is the area's audit evidence: its records, read once."""
    if held.unreadable:
        return {}
    try:
        records = list(held.records)
        covering = covering_analysis(area, text, run)
        members = chain(records).members
    except (ValueError, FileNotFoundError):
        return {}
    return released_corrections(
        covering, members, lambda f: _correction_field(f, protocol, text)
    )


def _correction_field(
    f: audit_findings.Finding, protocol: Path, text: str
) -> str | None:
    """`findings.corrected_field`, its unclear place as an AuditError: which
    field the correction is bound to cannot be told, and the station that
    holds the change names that as its blocker."""
    try:
        return corrected_field(f, protocol, text)
    except FieldPlaceError as exc:
        raise unclear_correction(f.one_line, protocol.name, exc) from exc


def awaiting_followup(
    area: Path, protocol: Path, text: str, run: Path, held: evidence.AreaEvidence
) -> dict[str, str]:
    """The fields of PROTOCOL (TEXT as it stands) whose correction a
    follow-up analysis audit of the state now would be shown and judge, by
    `field_name`, each with the correction's ref (`<record>#<n>`): a
    finding decided `fixed` that names the field as its place
    (`findings.corrected_field`), a head of its chain in a record that does
    not cover the area now — what `audit_prompt.earlier_of` shows, through
    the same `followup.earlier_blockers` and `earlier_corrections`. Empty
    when the area holds more than one protocol (no correction is shown
    then) or its records cannot be read. Raises AuditError when the state
    RUN was audited in cannot be computed, as `resolved_corrections` does:
    the two read the same state, so neither answers where the other
    cannot. HELD is the area's audit evidence: its records, read once."""
    if only_protocol(area_protocols(area)) is None:
        return {}
    if held.unreadable:
        return {}
    try:
        records = list(held.records)
        covering = {r.path.name for r in covering_analysis(area, text, run)}
    except (ValueError, FileNotFoundError):
        return {}

    try:
        return awaited_corrections(
            records,
            lambda r: r.path.name in covering,
            lambda f: _correction_field(f, protocol, text),
        )
    except audit_findings.FindingsError:
        return {}


def corrected_in_place(
    area: Path,
    protocol: Path,
    pid: str | None,
    run: Path | None,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> list[str]:
    """One line per field of PROTOCOL changed since its first measurement
    that a correction released (`scope_now`): the field, its old and new
    value, the correction and the follow-up's why — what the release says
    of a description corrected in place. Empty without an answering run, a
    stamped id or such a field. Raises RuntimeError when git fails."""
    if pid is None or run is None:
        return []
    now = scope_now(
        area,
        protocol,
        pid,
        run,
        git_root(protocol),
        state.measured_of(pid),
        state,
        held,
    )
    if now is None:
        return []
    return [
        f"corrected in place after the first measurement {now.first.dir.name}: "
        f'{what} "{_quoted(old)}" → "{_quoted(new)}" — {c.ref} resolved in '
        f"{c.judged_in}: {_quoted(c.why)}"
        for (what, old, new), c in now.corrected
    ]


def quoted_changes(diffs: list[tuple[str, str, str]]) -> str:
    """DIFFS — (what, from, to) — as a hold names them: `what "from" → "to"`,
    each value cut to SCOPE_QUOTE characters, joined by "; "."""
    return "; ".join(
        f'{what} "{_quoted(old)}" → "{_quoted(new)}"' for what, old, new in diffs
    )


def _labels(diffs: list[tuple[str, str, str]]) -> str:
    """The fields DIFFS name, in order, for a way back."""
    return ", ".join(what for what, _, _ in diffs)


def _quoted(value: str) -> str:
    """VALUE cut to SCOPE_QUOTE characters for a hold's sentence."""
    return value if len(value) <= SCOPE_QUOTE else value[: SCOPE_QUOTE - 1] + "…"


def named_changes(
    protocol: Path,
    first: RunDir,
    answering: RunDir,
    was: dict,
    now: dict,
    root: Path | None,
) -> tuple[list[str], list[str]]:
    """(changes, restores): every change of the promise block from the
    first measurement FIRST to the ANSWERING run, and what undoes each. From
    the protocol texts both runs saw (`protocol_history.as_measured`,
    `promise_differences`): sentences, keys, constants and scopes together —
    the run records keep sentences only through the block's digest, and a
    restore that names only the constants leaves a changed sentence that
    holds the next run again. Where a text cannot be read back,
    what the records WAS and NOW hold (`promises.snapshot_changes`) and why
    the sentences go unnamed. Raises RuntimeError when git fails."""
    then, why_then = protocol_history.as_measured(protocol, first, root)
    current, why_now = protocol_history.as_measured(protocol, answering, root)
    if then is not None and current is not None:
        diffs = protocol_history.promise_differences(then, current)
        if diffs:
            return (
                [change_phrase(*d) for d in diffs],
                [restore_phrase(*d) for d in diffs],
            )
    changes = promises.snapshot_changes(was, now)
    restores = [_restored(c) for c in changes]
    if then is None or current is None:
        why = why_then if then is None else why_now
        changes.append(f"the sentences unread ({why})")
    return changes, restores


def change_phrase(what: str, old: str, new: str) -> str:
    """One `protocol_history.promise_differences` entry as the hold names it:
    `[quality-check-2] null_band 0.1 → 0.15`, `[criterion-1] sentence "…" → "…"`, `[quality-check-3] added`."""
    pid, _, part = what.partition(" ")
    if not part:
        return (
            f"[{pid}] added" if old == protocol_history.ABSENT else f"[{pid}] dropped"
        )
    if part == "sentence":
        return f'[{pid}] sentence "{old}" → "{new}"'
    return f"[{pid}] {part} {old} → {new}"


def restore_phrase(what: str, old: str, new: str) -> str:
    """What undoes one `promise_differences` entry: a value or a sentence
    back, an added promise out, a dropped one back in."""
    pid, _, part = what.partition(" ")
    if not part:
        return f"[{pid}] out" if old == protocol_history.ABSENT else f"[{pid}] back in"
    if part == "sentence":
        return f'[{pid}] sentence "{old}" back'
    return f"[{pid}] {part} {old} back"


def _restored(change: str) -> str:
    """What undoes CHANGE, a phrase of `promises.snapshot_changes`: a value
    back, an added promise out, a dropped one back in, the sentences as then
    (the snapshot keeps them only through the block's digest)."""
    if " → " in change:
        return change.split(" → ")[0] + " back"
    if change.endswith(" added"):
        return change.removesuffix(" added") + " out"
    if change.endswith(" dropped"):
        return change.removesuffix(" dropped") + " back in"
    return "every sentence as then"


def check_registration(
    findings: Findings,
    area: Path,
    protocol: Path,
    pid: str | None,
    run: Path,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> None:
    """Hold the answering RUN to the registration of the first measurement
    (`registration_changes`: what the number is about, and the promise
    block, read from STATE, the area's state built once); a note when it
    holds, and one per field a correction released (`corrected_in_place`),
    so the release names what changed and why.
    HELD is the area's audit evidence, read once at the entry."""
    changes = registration_changes(area, protocol, pid, run, state, held)
    findings.take_all(changes)
    if not changes:
        corrected = corrected_in_place(area, protocol, pid, run, state, held)
        findings.note(
            "  what the number is about and the promise block are the ones the first "
            "measurement registered"
            + (", but for the fields corrected in place below" if corrected else "")
        )
        for line in corrected:
            findings.note(f"  {line}")
