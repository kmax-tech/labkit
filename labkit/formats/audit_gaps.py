"""Which audit a step owes and the area does not have.

`audit_coverage` answers whether an audit of a mode binds the area as it
is now (report-check, preflight); `audit_record_gap` whether the preflight
record a full run's head names covers that run (runlog's freeze gate,
preflight); `records_of_gone_runs` names the analysis records whose run
directory is gone (finalize). They read the records through `findings` and
the failed attempts through `failed_attempts`, and write nothing.
"""

from __future__ import annotations


from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import promises
from labkit.formats.gate import (
    BLOCKER,
    TECHNICAL_RULE,
    RuleAssignment,
    cited_rule,
    with_way_out,
)
from labkit.formats.protocol_check import (
    INVALID,
    MISSING,
    PLACEHOLDER,
    REPAIR_TABLES,
    check_fields,
    registration_drift,
    registration_stamp,
)
from labkit.formats.commands import audit_command
from labkit.formats.scope_sha import area_stamp, validation_note
from labkit.formats.standard_contract import ANALYSIS_AUDIT, PREFLIGHT_AUDIT
from labkit.formats.attempts import AttemptError, running, running_words
from labkit.formats.failed_attempts import unproven_attempts
from labkit.formats.findings import (
    AuditedState,
    DECIDED_LIST,
    DIR,
    FindingsError,
    MODES,
    NO_RUN,
    Record,
    area_records,
    decide_ways,
    names_preflight_record,
    open_findings,
    read,
    record_way,
)


#: how the writer's refusal names a must gap's state (`protocol_check.MustGap.state`)
_STATE_WORDS = {
    MISSING: "absent",
    PLACEHOLDER: "still a placeholder",
    INVALID: "invalid",
}


def covering_records(records: list[Record], now: AuditedState) -> list[Record]:
    """The RECORDS that saw the area as it is NOW: that code, that promise
    block, that registration and — mode analysis — that run and what was
    shown of it (`findings.AuditedState`)."""
    return [r for r in records if r.state == now]


def registration_note(records: list[Record], registration: Mapping[str, str]) -> str:
    """For a refusal: "" unless the newest of RECORDS judged another
    registration than REGISTRATION, else a clause naming what changed
    (`protocol_check.registration_drift`) — the question or another field
    the kind owes, rewritten after the audit, owes a new one."""
    if not records:
        return ""
    changed = registration_drift(dict(records[-1].registration), registration)
    if not changed:
        return ""
    return (
        f" — the registration changed after the audit ({', '.join(changed)}): "
        f"the audit judged another question than the protocol asks now"
    )


def records_of_gone_runs(records: list[Record], known: set[str]) -> list[Record]:
    """The analysis RECORDS whose run is not among KNOWN (the run ids the
    area holds now). A record is evidence that the run existed and was
    read; the directory it names is gone. A record of NO_RUN names none.
    Why: the records of a run deleted after its audit would otherwise read
    as "every finding decided"."""
    return [
        r
        for r in records
        if r.run_id is not None and r.run_id != NO_RUN and r.run_id not in known
    ]


def audit_coverage(area: Path, mode: str, now: AuditedState) -> str | None:
    """Why no audit of MODE covers the area as it is NOW, or None: a record
    with that `mode` that binds NOW (`findings.AuditedState`: the code, the
    promises, the registration and — mode analysis — the answering run and
    what the prompt showed of it, recomputed now: a metrics.json or output
    rows changed after the audit owe a new one), every finding of it
    decided. The head names a record by hand; this is what makes
    "the frozen code was audited" a fact instead of a line. Its caller is
    report-check, mode `analysis`; the freeze holds the record its head
    names instead (`audit_record_gap`: runlog, preflight).

    Raises:
        FindingsError: A findings file of AREA cannot be read.
        ValueError: MODE is not one of MODES, or NOW's run and shown sha
            are given for `preflight` or missing for `analysis`.
    """
    if mode not in MODES:
        raise ValueError(f"audit mode {mode!r} is not one of {', '.join(MODES)}")
    analysis = mode == ANALYSIS_AUDIT
    if analysis != (now.run_id is not None) or analysis != (now.shown_sha is not None):
        raise ValueError(
            f"audit mode {mode!r} with run_id {now.run_id!r}, shown_sha "
            f"{now.shown_sha!r}: "
            f"an analysis audit is held to the answering run and what it was "
            f"shown of it, a preflight audit to neither"
        )
    records = [r for r in area_records(area) if r.mode == mode]
    covering = covering_records(records, now)
    if not covering:
        # the code, promises and run as audited, the registration rewritten
        same_state = [r for r in records if r.state.bound == now.bound]
        if same_state:
            return (
                f"no {mode} audit saw the area as it is now"
                f"{registration_note(same_state, now.registration)} — "
                f"`labkit-audit <area> --mode {mode}`"
            )
        seen = "; ".join(sorted({r.state.words() for r in records})) or "none"
        stopped = unproven_attempts(area, mode, now.scope_sha, now.block_sha)
        if stopped:
            models = ", ".join(sorted({f.model for f in stopped}))
            return (
                f"no {mode} audit saw the area as it is now ({now.words()}): "
                f"{len(stopped)} attempt(s) unproven — {models} did not write the "
                f"answer whole (a safety stop or another model; "
                f"{stopped[-1].path.name}); the same model is not tried again on "
                f"this state: `labkit-audit <area> --mode {mode} --model <alias>`"
            )
        try:
            under_way = running(area, mode)
        except AttemptError:
            under_way = []  # an unreadable journal is the evidence gates' finding
        if under_way:
            return f"no {mode} audit record covers the area yet — " + running_words(
                under_way[-1]
            )
        # with no record yet, "a change after the audit" would speak of an
        # audit that never ran
        why = (
            "a change after the audit owes a new one" if records else "none has run yet"
        )
        return (
            f"no {mode} audit saw the area as it is now "
            f"({now.words()}; audited: {seen}) — {why}: "
            f"`labkit-audit <area> --mode {mode}`"
            f"{validation_note(area)}"
        )
    still_open = open_findings(covering)
    if still_open:
        return (
            f"{len(still_open)} finding(s) of the {mode} audit of {now.scope_sha} still "
            f"`open` — decide each ({DECIDED_LIST})"
        )
    return None


LAB_015 = cited_rule("LAB-015 Preflight audit before freezing")


@dataclass(frozen=True)
class RecordGap:
    """Why the record a head names covers no full run (`audit_record_gap`),
    the step that closes it — the way out a gate tells beside the sentence
    (`gate.with_way_out`) — and the rule the cause breaks: the preflight
    audit's, the technical contract where the record or the area's stamp
    does not read, or the rule of the cause where the promise block does
    not (`promises.PromiseError.rule`). The sentence does not cite that
    rule; whoever tells it cites it from here (`gate.with_rule`)."""

    why: str
    fix: str
    rule: RuleAssignment


def audit_way(area: Path) -> str:
    """The way out of a record that saw other code, another promise block
    or another registration than AREA carries now: the preflight audit on
    the state as it stands, then its decisions."""
    return (
        f"audit this code and promise block: "
        f"`{audit_command(area, '--mode', 'preflight')}`, then decide its findings"
    )


def audit_record_gap(area: Path, name: str, text: str) -> RecordGap | None:
    """Why the head's non-empty `preflight_audit` NAME does not cover a full
    run of AREA under the protocol TEXT, or None: it names no record (an
    `n/a`, a sentence, a path — the field is the file name of the decided
    preflight record under audits/, and nobody waives their own audit),
    there is no such record in the area, the record is of another mode,
    it saw other code than the area stamps now (`scope_sha`) or another
    promise block than TEXT carries (`block_sha`), or a finding of it is
    still open — each with its own way out (`RecordGap.fix`): a new
    audit where the record covers other code, another block or another
    registration (`audit_way`), the decisions where its findings are
    still open (`findings.decide_ways`), the record restored where it does not
    read (`findings.record_way`). One answer for runlog's freeze gate, `preflight`
    and `protocol-check`; the caller decides what an empty field and
    `low` mean. The record names its sha itself, so the head names the
    record. The refusal names the honest ways and offers no word to write
    instead."""
    name = name.strip()
    audit = audit_way(area)
    if not names_preflight_record(name):
        return RecordGap(
            "`preflight_audit` names no record — the field is the file name of the "
            "decided preflight record under audits/ (`<minute>-preflight.toml`, "
            "printed by `labkit-audit <area> --mode preflight` when it writes one); "
            "at high repeat cost a full run owes that audit, and nobody waives their "
            "own: run it and name its record; when the backend does not answer, "
            "labkit-audit records the failed attempt and a full run acknowledges "
            "it with LABKIT_UNFROZEN=1 (its number stays unreportable). If no "
            "audit is owed at all, the repeat cost is wrong, not the field "
            "(LAB-017 The number of audits follows the cost tier) — and a tier "
            "lowered after the protocol's first commit is reported",
            audit,
            LAB_015,
        )
    path = area / DIR / name
    if not path.is_file():
        return RecordGap(
            f"`preflight_audit` names {DIR}/{name}, and there is no such record in "
            f"this area — name the one `labkit-audit <area> --mode preflight` wrote",
            audit,
            LAB_015,
        )
    try:
        record = read(path)
    except FindingsError as exc:
        return RecordGap(str(exc), record_way(area), TECHNICAL_RULE)
    if record.mode != PREFLIGHT_AUDIT:
        return RecordGap(
            f"{name} is a {record.mode} record — `preflight_audit` names the "
            "preflight audit",
            audit,
            LAB_015,
        )
    try:
        now = area_stamp(area)[0]
    except (FileNotFoundError, ValueError) as exc:
        return RecordGap(
            f"the area cannot be stamped now ({exc})", audit, TECHNICAL_RULE
        )
    if record.scope_sha != now:
        return RecordGap(
            f"the record {name} saw scope sha {record.scope_sha}, the code now stamps "
            f"{now} — it changed after the audit, so the change owes a new audit "
            f"(`labkit-audit <area> --mode preflight`); naming another record "
            f"without one is refused too{validation_note(area)}",
            audit,
            LAB_015,
        )
    judged = _protocol_gap(record, name, text, audit)
    if judged:
        return judged
    if record.open:
        return RecordGap(
            f"{len(record.open)} finding(s) of {name} still `open` — decide each "
            f"({DECIDED_LIST})",
            decide_ways(area, record),
            LAB_015,
        )
    return None


def freeze_refusals(area: Path, text: str, record: str) -> list[str]:
    """Why TEXT — AREA's protocol as the freeze would write it, `frozen =
    true` and `preflight_audit = RECORD` — may not be frozen; empty when
    it may. A MUST field absent, still a placeholder or written twice
    (`protocol_check.check_fields`: frozen, every should is a must), the
    record not covering this code, block and registration or a finding of
    it open (`audit_record_gap`), and a BLOCKER open in another preflight
    record of the area (what runlog's freeze gate refuses the run on). The
    writer's half of one rule — the gates' readers keep theirs for a head
    edited by hand (the writer refuses what a gate would later hold).
    Raises FindingsError
    when a record of the area does not read."""
    report = check_fields(text)
    out = [f"{report.head_error}"] if report.head_error else []
    out += [
        f"MUST field {_STATE_WORDS[gap.state]}: {gap.label}" for gap in report.must_gaps
    ]
    out += [
        f"MUST field still a placeholder: {label} (line {n})"
        for n, label in report.must_holes
    ]
    out += [f"written twice: {twice}" for twice in report.repeated]
    gap = audit_record_gap(area, record, text)
    if gap is not None:
        out.append(with_way_out(f"preflight_audit: {gap.why}", gap.fix))
    out += [
        f"open BLOCKER: {u.line}"
        for u in open_findings(area_records(area), mode=PREFLIGHT_AUDIT)
        if u.grade == BLOCKER and u.record.path.name != record
    ]
    return out


def _protocol_gap(record: Record, name: str, text: str, audit: str) -> RecordGap | None:
    """Why RECORD (named NAME) judged another protocol than TEXT, or None:
    another promise block (`block_sha`) or another registration — the kind,
    the question or another field the kind owes (`registration`) —, the
    preflight audit's rule, the way out a new audit (AUDIT). A promise
    block that does not read is not compared: its own cause with the rule
    that cause names (`PromiseError.rule`), the way out its repair — a new
    audit would not read it either."""
    try:
        block = promises.block_stamp(text)
    except promises.PromiseError as exc:
        return RecordGap(
            f"the promise block does not read, so the record {name} cannot be "
            f"held to it: {exc}",
            REPAIR_TABLES,
            exc.rule,
        )
    if record.block_sha != block:
        return RecordGap(
            f"the record {name} saw the promise block {record.block_sha}, the protocol "
            f"carries {block} now — a promise rewritten after the audit owes a new one",
            audit,
            LAB_015,
        )
    changed = registration_note([record], registration_stamp(text))
    if not changed:
        return None
    return RecordGap(
        f"the record {name} no longer covers the protocol{changed}", audit, LAB_015
    )
