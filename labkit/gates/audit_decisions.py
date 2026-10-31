"""The person's side of an audit record: `labkit-audit <AREA> --findings`
lists what there is to decide (`show_findings`), `--decide N STATUS --why
REASON` stores one decision (`decide`), and `decision_lines` prints the
numbered findings both show after an audit.
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from labkit.formats import (
    attempts,
    console,
    evidence,
    findings,
    promises,
    protocol_check,
)
from labkit.formats.repo import (
    ProtocolChoiceError,
    area_protocols,
    audit_command,
    decide_command,
    given_or_in,
    handover_command,
    shown,
    the_protocol,
)
from labkit.gates import ways_out
from labkit.gates.audit_reply import READ_HINT

DECISION_TEXT_WIDTH = 160


def decision_lines(
    record: findings.Record, area: Path, report: str, protocol: Path | None = None
) -> list[str]:
    """What the person decides, as printed after an audit is recorded: the
    record's path, its findings numbered as `--decide` takes them — from
    the stored record, never counted in the model's text — each with the
    command that decides it (`--record` named, so a later audit cannot
    shift it), then the READ lines of REPORT apart: printed, not recorded,
    nothing to decide. Five of six sandbox probes (2026-10-21) numbered the
    printed lines and decided findings the record does not hold. The effect
    `<ID> not assessable` is named only where the protocol registers a
    promise (`may_leave_unassessed`)."""
    here = Path.cwd()
    where = shown(record.path, here)
    out: list[str] = []
    if not record.findings:
        out.append(f"findings: {where} — no findings to decide")
    else:
        owed = ", ".join(findings.REASON_OWED)
        out.append(
            f"findings: {where} — {len(record.findings)} to decide "
            f"({findings.DECIDED_LIST}; a reason "
            f"owed for {owed}):"
        )
        promised = may_leave_unassessed(area, protocol)
        # the id named with its field: an agent cannot pick `quality-check-2` unnamed
        named = effect_ids_named(area, protocol) if promised else ""
        # what the route owes and what it does by itself: readers took the
        # review clause of `stands` for this route too, and named every
        # criterion an unjudged quality check already voids
        unassessed = (
            "limitation --not-assessable <ID>[,<ID>]"
            + (f" (<ID>: {named})" if named else "")
            + " — no review owed; a quality check left unjudged "
            "leaves every criterion without a verdict by itself, so name the "
            "condition, not the criteria"
        )
        if any(f.grade == "BLOCKER" for f in record.findings):
            out.extend(ways_out.blocker_routes(promised, full=False))
        for n, f in enumerate(record.findings, 1):
            text = (
                f.one_line
                if len(f.one_line) <= DECISION_TEXT_WIDTH
                else f.one_line[: DECISION_TEXT_WIDTH - 1] + "…"
            )
            out.append(f"  {n} · {text}")
            out.append(
                "      "
                + decide_command(
                    area, n, "STATUS", "<why>", where, protocol=protocol, base=here
                )
            )
            if f.check:
                # where the decision is made: in the repair case the check went
                # unwritten and every follow-up judged the repair not assessable
                out.append(
                    f"      check owed before `fixed` holds: "
                    f"{findings.check_order(f.check, f.check_note)}; then measure "
                    f"again and run `{audit_command(area, '--mode', 'analysis', protocol=protocol, base=here)}` "
                    f"— the follow-up judges `fixed` by that value"
                )
            if f.grade == "BLOCKER":
                out.append(
                    "      limitation: the verdicts hold, read within it; a second "
                    "auditor must uphold it before the number leaves, at every "
                    f"repeat cost: `"
                    f"{audit_command(area, '--review', '--record', record.path.name, protocol=protocol, base=here)}"
                    f"`"
                    + (
                        f" or {unassessed}"
                        if promised
                        else " — no promise is registered to leave not assessable; "
                        "a fault the claim cannot be read within: hand the "
                        "protocol over"
                    )
                )
            elif f.grade == "WARNING":
                out.append(
                    "      limitation: the verdicts hold, read within it (its missing "
                    "review warns)" + (f" | {unassessed}" if promised else "")
                )
    hints = [ln.strip() for ln in report.splitlines() if READ_HINT.match(ln)]
    if hints:
        out.append("reading hints — not recorded, nothing to decide:")
        out += [f"  {h}" for h in hints]
    return out


#: how `--decide` takes its values, as its refusals name the form
DECIDE_FORM = '--decide takes <n> <status> --why "<reason>"'


def decide_shape(argv: list[str]) -> str | None:
    """Why ARGV's `--decide` is not `<n> <status>` followed by its options,
    or None: the words after `--decide` up to the next option are its
    values; not two, or a third word where `--why` belongs, is refused
    naming the form. A positional reason once surfaced as "unrecognized
    arguments" and agents dropped what followed (SAB round 1, 2026-10-29).
    Checked before argparse parses, so a usage error names the reason."""
    if "--decide" not in argv:
        return None
    after = argv[argv.index("--decide") + 1 :]
    values = after[
        : next((i for i, w in enumerate(after) if w.startswith("-")), len(after))
    ]
    if len(values) < 2:
        return f"{DECIDE_FORM} — {len(values)} of 2 given"
    if len(values) > 2:
        return (
            f"{DECIDE_FORM} — the reason goes after --why: "
            f"--why {shlex.quote(' '.join(values[2:]))}"
        )
    return None


def record_path(area: Path, record: Path) -> Path:
    """RECORD as given when it exists, else the file of that name under
    AREA's audits/ (`repo.given_or_in`) — the gates name a record by its
    file name (`Limitation (audit <record> #N)`, report-check's `--record
    <name>`), and judge-2 (round on 86e38bc, 2026-10-22) copied the name
    and was refused with "No such file"."""
    return given_or_in(record, area / findings.DIR)


def _newest_record(area: Path) -> Path:
    """The area's newest findings record; FindingsError when it has none."""
    records = findings.area_records(area)
    if not records:
        raise findings.FindingsError(
            f"{area}: no findings record — run the audit first"
        )
    return records[-1].path


@dataclass(frozen=True)
class _Superseded:
    """A failed audit call a later completed audit took the place of
    (`attempts.superseding_record`): its LABEL as `--findings` names it,
    its MODE, the RECORD file that supersedes it, and OF_MODE_ONLY — the
    call is historical, so an audit of its mode in the current format, of
    any protocol, superseded it."""

    label: str
    mode: str
    record: str
    of_mode_only: bool


@dataclass(frozen=True)
class _Calls:
    """The failed audit calls of an area as `--findings` shows them: the
    FAILED files and UNRECORDED attempts (ended without a record) still
    open, why each historical one among them is (HISTORICAL_WHY, by file
    name or attempt id), and those a later audit SUPERSEDED."""

    failed: tuple[findings.Failed, ...] = ()
    unrecorded: tuple[attempts.Attempt, ...] = ()
    historical_why: Mapping[str, str] = field(default_factory=dict)
    superseded: tuple[_Superseded, ...] = ()


@dataclass(frozen=True)
class _Listing:
    """The shown RECORDS, evidence ERRORS, HIDDEN record count, the FAILED
    calls (`-failed.toml`) and the UNRECORDED ones (audit attempts the
    journal ended without a record) that no later completed audit of their
    mode, protocol and promise block superseded, which of them are
    HISTORICAL, the calls a later audit SUPERSEDED, and the evidence CHANGED
    against git (`evidence.changes`, `evidence.ignored`) — undone by a
    restore, never by a handover."""

    records: list[findings.Record]
    errors: list[str]
    hidden: int
    failed: tuple[findings.Failed, ...] = ()
    unrecorded: tuple[attempts.Attempt, ...] = ()
    # of those, the historical calls (`attempts.historical_call`): failed file
    # name or attempt id → why its binding or order is not known; superseded
    # by the audit of its mode run again now
    historical_why: Mapping[str, str] = field(default_factory=dict)
    # the failed calls a later audit superseded: shown as such, never as open
    superseded: tuple[_Superseded, ...] = ()
    changed: tuple[str, ...] = ()


def _recovery_records(area: Path, record: Path | None) -> _Listing:
    """RECORD alone; else every readable record with an open finding of
    any grade — what a frozen preflight blocks on (`findings.open_findings`)
    — and the newest one, the others counted. Evidence and read errors of the
    area are kept beside them (`attempts.area_integrity`). A failed audit
    call — a `-failed.toml`, or an audit attempt the journal ended without
    a record (outcome `none`: an answer that did not read, a call that
    raised) — remains recovery guidance until a later completed audit of
    the same mode and the same protocol with the same promise block
    supersedes it, in the journal's order, also after a code change
    (`attempts.superseding_record`); an earlier record, another mode,
    protocol or promise block supersede nothing, nor a record no attempt
    names. A superseded call is shown as such, never as open; that
    confirms neither its content nor the repair of any finding — a
    recorded BLOCKER stays under the follow-up rule. A historical call —
    a start without its promise block and protocol (labkit 0.103.0 or
    earlier), a failed file no attempt names — is superseded by a later
    audit of its mode in the current format, and named as such until
    then. An attempt
    without an end (running, or interrupted: killed, timed out in the
    shell) is not listed; the next audit's start names it
    (`attempts.begin`). This does not establish whether that audit covers
    the current run.
    """
    state = attempts.area_integrity(area)
    errors = list(state.problems)
    changed = (*evidence.changes(area), *evidence.ignored(area))
    if record is not None:
        try:
            read = findings.read(record_path(area, record))
            return _Listing([read], errors, 0, changed=changed)
        except findings.FindingsError as exc:
            return _Listing([], [*errors, str(exc)], 0, changed=changed)
    calls = _open_calls(area, state.records, errors)
    opened = {u.record.path for u in findings.open_findings(state.records)}
    records = [r for r in state.records if r.path in opened]
    if state.records and state.records[-1] not in records:
        records.append(state.records[-1])
    hidden = len(state.records) - len(records)
    return _Listing(
        records,
        errors,
        hidden,
        calls.failed,
        calls.unrecorded,
        calls.historical_why,
        calls.superseded,
        changed,
    )


def _open_calls(
    area: Path, records: list[findings.Record], errors: list[str]
) -> _Calls:
    """AREA's failed audit calls against its RECORDS (`_Calls`): each is
    superseded or still open (`_classify`). A journal or a failed file
    that does not read is added to ERRORS; without the journal no failed
    file is superseded, and none is called historical — the journal's
    error is the cause."""
    journal: list[attempts.Attempt] = []
    journal_read = True
    try:
        journal = attempts.read_journal(area)
    except (attempts.AttemptError, OSError) as exc:
        errors.append(str(exc))
        journal_read = False
    by_file = {r.path.name: r for r in records}  # records of findings only
    of_files = _Calls()
    try:
        of_files = _open_failed(area, journal, by_file, journal_read)
    except (findings.FindingsError, OSError) as exc:
        errors.append(str(exc))
    unrecorded: tuple[attempts.Attempt, ...] = ()
    why: dict[str, str] = {}
    superseded: list[_Superseded] = []
    for i, a in enumerate(journal):
        if a.outcome != "none" or a.mode not in findings.MODES:
            continue
        by, is_historical = _classify(
            journal, i, by_file, a.mode, a.protocol, a.block_sha, f"attempt {a.id}"
        )
        if by is not None:
            superseded.append(by)
            continue
        unrecorded += (a,)
        if is_historical:
            missing = [
                n
                for n, v in (("promise block", a.block_sha), ("protocol", a.protocol))
                if not v
            ]
            why[a.id] = (
                "its start, written by labkit 0.103.0 or earlier, names no "
                + " and no ".join(missing)
            )
    return _Calls(
        of_files.failed,
        unrecorded,
        {**of_files.historical_why, **why},
        (*of_files.superseded, *superseded),
    )


def _classify(
    journal: list[attempts.Attempt],
    at: int | None,
    records: Mapping[str, findings.Record],
    mode: str,
    protocol: str,
    block_sha: str,
    label: str,
) -> tuple[_Superseded | None, bool]:
    """(the supersession of the failed call LABEL — at AT in JOURNAL, of
    MODE, PROTOCOL and BLOCK_SHA — by a later record of RECORDS, None while
    it is open; whether the call is historical): the one test both kinds of
    failed call go through (`attempts.superseding_record`,
    `attempts.historical_call`)."""
    by = attempts.superseding_record(journal, at, records, mode, protocol, block_sha)
    is_historical = attempts.historical_call(at, block_sha, protocol)
    if by is None:
        return None, is_historical
    return _Superseded(label, mode, by.path.name, is_historical), is_historical


def _open_failed(
    area: Path,
    journal: list[attempts.Attempt],
    records: Mapping[str, findings.Record],
    journal_read: bool,
) -> _Calls:
    """AREA's `-failed.toml` files as `_Calls` (no UNRECORDED): each
    superseded by a later audit of RECORDS in the JOURNAL's order or still
    open (`_classify`), why each open historical one is — none where the
    journal did not read (JOURNAL_READ false). A failed file takes its
    promise block from itself, its protocol from the start of the attempt
    that wrote it. Raises FindingsError on a failed file that does not
    read."""
    failed_at = {a.file: i for i, a in enumerate(journal) if a.outcome == "failed"}
    failed: tuple[findings.Failed, ...] = ()
    why: dict[str, str] = {}
    superseded: list[_Superseded] = []
    for f in findings.failed_attempts(area):
        at = failed_at.get(f.path.name)  # None: no attempt names the file
        protocol = journal[at].protocol if at is not None else ""
        by, is_historical = _classify(
            journal, at, records, f.mode, protocol, f.block_sha, f.path.name
        )
        if by is not None:
            superseded.append(by)
            continue
        failed += (f,)
        if not (journal_read and is_historical):
            continue
        if at is None:
            why[f.path.name] = (
                "no attempt of the journal names it, so its order is not known"
            )
        elif not f.block_sha:
            why[f.path.name] = "its file names no promise block"
        else:
            why[f.path.name] = (
                "the start of the attempt that wrote it, of labkit 0.103.0 or "
                "earlier, names no protocol"
            )
    return _Calls(failed, (), why, tuple(superseded))


def show_findings(area: Path, record: Path | None, protocol: Path | None = None) -> int:
    """`--findings`: what there is to decide, without a model call or a
    write. Shown: the evidence errors of the area, each failed audit call
    — a `-failed.toml`, or an attempt the journal ended without a record,
    named with its kept answer — that no later completed audit of its
    mode, protocol and promise block superseded (`_recovery_records`);
    each superseded one as superseded, informational; then each
    shown record's decisions (`decision_lines`) — RECORD alone, else every
    record with an open finding of any grade (a NOTE still open holds a
    frozen preflight too) and the newest, the others counted. Where
    an open BLOCKER, an evidence error or such a failed call stands, the
    way to end the area unresolved follows: the handover command per
    protocol, which records the open BLOCKERs as they stand. A partial failure hides no readable finding; READ hints are
    not stored.

        exit 0   nothing failed: the decisions shown are all there is
        exit 2   no audit record and no attempt (refused, nothing to
                 decide); an evidence error of the area (also with
                 RECORD); a failed call no completed audit covers;
                 evidence changed against git (`evidence.changes`,
                 `evidence.ignored`, shown first with its restore — a
                 handover does not settle it)
    """
    listing = _recovery_records(area, record)
    records, errors = listing.records, listing.errors
    failed, unrecorded = listing.failed, listing.unrecorded
    changed = listing.changed
    for line in changed:
        print(f"evidence changed: {line}")
    if not records and not errors and not failed and not unrecorded:
        if changed:
            return 2
        console.refuse(
            "labkit-audit",
            f"{area}: no audit record yet — nothing to decide; the area's "
            "README, `protocol-check <PROTOCOL> --contract` and the repo's "
            "AGENTS.md name the next step",
        )
        return 2
    _print_problems(area, errors, listing, protocol)
    blockers: list[findings.OpenFinding] = []
    for rec in records:
        for line in decision_lines(rec, area, "", protocol):
            print(line)
        blockers += findings.open_blockers([rec])
    if listing.hidden:
        print(
            f"  {listing.hidden} earlier record(s) without an open finding not "
            "shown — `--record FILE` shows one"
        )
    if not blockers and not errors and not failed and not unrecorded:
        return 2 if changed else 0
    _print_handover_steps(area, blockers, protocol)
    return 2 if errors or failed or unrecorded or changed else 0


def _print_problems(
    area: Path, errors: list[str], listing: _Listing, protocol: Path | None
) -> None:
    """`--findings`' lines for AREA's evidence ERRORS, each once, and for
    the failed calls no completed audit covers (LISTING): the failed
    files, the attempts that ended without a record by id with the answer
    each kept; a historical one says so and names the audit, run again
    now in the current format, that settles it (PROTOCOL where the area
    holds several)."""
    for error in dict.fromkeys(errors):
        print(f"audit evidence incomplete: {error}")
    for f in listing.failed:
        call = f"{f.path.name} ({f.mode}, {f.model}): {f.error}"
        if f.path.name in listing.historical_why:
            why = listing.historical_why[f.path.name]
            print(_historical_line(area, call, why, f.mode, protocol))
            continue
        print(
            f"audit did not complete: {call} — no findings to decide; "
            "the failed call approves no result"
        )
    for a in listing.unrecorded:
        kept = ""
        if a.answer:
            answer = area / findings.DIR / a.answer
            kept = f"; its answer is kept in {shown(answer, Path.cwd())}"
        call = (
            f"attempt {a.id} ({a.mode}, {a.model}) ended without a record: "
            f"{a.error}{kept}"
        )
        if a.id in listing.historical_why:
            why = listing.historical_why[a.id]
            print(_historical_line(area, call, why, a.mode, protocol))
            continue
        print(
            f"audit did not complete: {call} — no findings to decide; the "
            "failed call approves no result"
        )
    for c in listing.superseded:
        print(_superseded_line(c))


#: what superseding a failed call means and does not: the one wording of
#: `--findings`' line, which the docs (README, workflow, CHANGELOG) state
SUPERSEDED_MEANS = (
    "this confirms neither its content nor the repair of any finding — a "
    "recorded BLOCKER stays under the follow-up rule; the call and its answer "
    "stay as they are, and the call needs nothing more"
)


def _superseded_line(c: _Superseded) -> str:
    """The `--findings` line of a failed call a later audit superseded —
    informational, it changes no exit: which record took its place and
    what that means (SUPERSEDED_MEANS)."""
    by = (
        f"the later audit {c.record} of its mode in the current format (a "
        "historical call: any protocol of the area)"
        if c.of_mode_only
        else f"the later audit {c.record} of its mode, protocol and promise block "
        "(its code may differ)"
    )
    return f"audit call superseded: {c.label} ({c.mode}) by {by} — {SUPERSEDED_MEANS}"


def _historical_line(
    area: Path, call: str, why: str, mode: str, protocol: Path | None
) -> str:
    """The `--findings` line of a historical failed CALL (`attempts.historical_call`):
    WHY its binding or order is not known, and the step that settles it —
    the audit of its MODE run again now, in the current format, whose
    record binds today's code and promises (no block is supplied for the
    old call, and its evidence stays as written)."""
    command = audit_command(area, "--mode", mode, protocol=protocol)
    return (
        f"audit did not complete, historical: {call} — {why}; no findings to "
        f"decide, and it approves no result. Run the audit again in the current "
        f"format, which settles it: `{command}`"
    )


def _print_handover_steps(
    area: Path, blockers: list[findings.OpenFinding], protocol: Path | None
) -> None:
    """`--findings`' way to end AREA unresolved: the handover command per
    protocol; BLOCKERS stay open, and the handover records them."""
    print(
        "if the area cannot be finished, hand it over unresolved (no model call; "
        "it records the loss and approves no result"
        + (f"; its {len(blockers)} open BLOCKER(s) stay open in it" if blockers else "")
        + "):"
    )
    selected = [protocol.resolve()] if protocol is not None else area_protocols(area)
    for chosen in selected:
        print(f"  hand over: {handover_command(chosen)}")


def decide(
    area: Path,
    decide: list[str],
    reason: str,
    record: Path | None,
    not_assessable: str = "",
    protocol: Path | None = None,
) -> int:
    """`--decide`: store the person's decision on one finding of RECORD (the
    area's newest record without it) through `findings.write_decision`. A
    `limitation` on a BLOCKER or WARNING records its effect: `stands`, or the
    ids NOT_ASSESSABLE names (`<ids> not assessable`), held to the promises
    the protocol registers; `--not-assessable` with another status is
    refused. Print what was written and how many findings stay open, what
    the status entails (`findings.decision_entails`) and, under `fixed`,
    the hint that nothing changed since the audit (`repair_hint`). Exit 2
    on a decision that cannot be stored, the file untouched; a refusal of
    the ids adds, for a protocol without promises, the routes that work
    there (`ways_out.NO_PROMISE_ROUTE`)."""
    n_text, status = decide
    effect = ""
    try:
        if not n_text.isdigit():
            raise findings.FindingsError(f"N must be a finding number, not {n_text!r}")
        record = _newest_record(area) if record is None else record_path(area, record)
        if not_assessable and status != "limitation":
            raise findings.FindingsError(
                f"--not-assessable goes with limit, not with {status}"
            )
        if status == "limitation":
            rec_before = findings.read(record)
            n = int(n_text)
            grade = (
                rec_before.findings[n - 1].grade
                if 1 <= n <= len(rec_before.findings)
                else ""
            )
            if not_assessable:
                ids = [i.strip() for i in not_assessable.split(",") if i.strip()]
                effect = ", ".join(ids) + " not assessable"
                _registered(area, protocol, effect)
            elif grade in findings.EFFECT_GRADES:
                effect = findings.EFFECT_STANDS
        rec = findings.write_decision(record, int(n_text), status, reason, effect)
    except findings.FindingsError as exc:
        why = str(exc)
        # an effect missing or malformed: its form's example is a promise id
        if isinstance(exc, findings.EffectFormError) and not may_leave_unassessed(
            area, protocol
        ):
            why += f" — {ways_out.NO_PROMISE_ROUTE}"
        console.refuse("labkit-audit", why)
        return 2
    print(
        f"decided: {record.name} finding {n_text}: {status}"
        + (f" ({effect.strip()})" if effect.strip() else "")
        + (f" — {reason.strip()}" if reason.strip() else "")
        + f" · {len(rec.open)} open"
    )
    print(
        findings.decision_entails(rec.findings[int(n_text) - 1], area, record, protocol)
    )
    if status == "fixed":
        hint = repair_hint(area, record, protocol)
        if hint is not None:
            print(hint)
    return 0


def repair_hint(area: Path, record: Path, protocol: Path | None) -> str | None:
    """The `hint:` line under a `fixed` decision on RECORD: nothing the
    record binds — code, promise block, registration
    (`findings.state_unchanged`) — has changed since the audit, so the
    claimed repair is not in the area yet; or the state could not be
    compared, naming why (no one protocol to read, nothing to stamp). None
    when something changed. A hint, never a refusal: the decision stands as
    given. Agents decided `fixed` on the audited state itself (SAB round 1,
    2026-10-29)."""
    repair = (
        "a repair changes code, inputs or configuration — repair first, then "
        "measure and audit again"
    )
    try:
        text = the_protocol(area, protocol).read_text(encoding="utf-8")
        unchanged = findings.state_unchanged(findings.read(record), area, text)
    except (ValueError, FileNotFoundError) as exc:
        return f"hint: the audited state could not be compared ({exc}); {repair}"
    if not unchanged:
        return None
    return (
        f"hint: nothing relevant changed since the audit {record.name} (code, "
        f"promise block and registration stamp as it saw them): {repair}"
    )


def _registered(area: Path, protocol: Path | None, effect: str) -> None:
    """FindingsError unless every id EFFECT names is a promise of the area's
    protocol (`promises.table_ids`) — EffectFormError when EFFECT is not in
    `findings.EFFECT_FORM`."""
    try:
        ids = findings.effect_ids(effect)
    except ValueError as exc:
        raise findings.EffectFormError(str(exc)) from exc
    if not ids:
        return
    try:
        chosen = the_protocol(area, protocol)
    except ProtocolChoiceError as exc:
        raise findings.FindingsError(f"the effect's ids: {exc}") from exc
    known = promises.table_ids(chosen.read_text(encoding="utf-8"))
    unknown = [i for i in ids if i not in known]
    if unknown and not known:
        raise findings.FindingsError(
            f"effect names {', '.join(unknown)} — {chosen.name}: "
            f"{ways_out.NO_PROMISE_ROUTE}"
        )
    if unknown:
        text = chosen.read_text(encoding="utf-8")
        raise findings.FindingsError(
            f"effect names {', '.join(unknown)} — {chosen.name} registers "
            f"{protocol_check.named_ids(sorted(known), protocol_check.promise_names(text))}"
        )


def may_leave_unassessed(area: Path, protocol: Path | None) -> bool:
    """Whether to offer the effect `<ID> not assessable` — False only when the
    protocol is known to register no promise; True when it registers one,
    and when that is not known here (no one protocol to choose, or its
    block does not read), so the route stays named and `--decide` says why
    it refuses. The protocol is the one `--decide` holds an effect to
    (`_registered`): PROTOCOL, else the area's only one. False means a
    protocol without [[promise]] tables — a computation —, where `--decide`
    refuses every id (protocol-check names a block's fault)."""
    try:
        chosen = the_protocol(area, protocol)
        return bool(promises.table_ids(chosen.read_text(encoding="utf-8")))
    except (ProtocolChoiceError, promises.PromiseError):
        return True


def effect_ids_named(area: Path, protocol: Path | None) -> str:
    """The ids an effect may leave not assessable, each with its field's
    name (`protocol_check.named_ids`): "criterion-1 (inference criterion),
    quality-check-1 (quality check)" — "" when the protocol registers none or
    is not known here (`may_leave_unassessed` decides whether the route is
    named at all)."""
    try:
        text = the_protocol(area, protocol).read_text(encoding="utf-8")
        ids = sorted(promises.table_ids(text))
    except (ProtocolChoiceError, promises.PromiseError):
        return ""
    return protocol_check.named_ids(ids, protocol_check.promise_names(text))
