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
from labkit.formats.protocol_check import registration_drift, registration_stamp
from labkit.formats.repo import (
    audit_command,
)
from labkit.formats.scope_sha import area_stamp, validation_note
from labkit.formats.standard_contract import ANALYSIS_AUDIT, PREFLIGHT_AUDIT
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
    Why (labkit-paper area 09, fifth haiku round, 2026-10-22): t18 deleted
    two measured runs with `rm -rf runs/…` after their audits, and finalize
    read the three records left behind as "every finding decided"."""
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
    "the frozen code was audited" a fact instead of a line (2026-10-14: after
    fixing the audit's findings a cold agent stamped the new sha, and no
    audit had seen that code). Its caller is report-check, mode `analysis`;
    the freeze holds the record its head names instead
    (`audit_record_gap`: runlog, preflight). Until 0.97.1 only the code was
    held: a promise rewritten after the audit, or a later run under the same
    code, kept the old record valid (review 2026-10-18).

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
        # before any audit "a change after the audit" spoke of one that
        # never ran (audit 2026-10-27, third, I12)
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


@dataclass(frozen=True)
class RecordGap:
    """Why the record a head names covers no full run (`audit_record_gap`),
    and the step that closes it — the way out a gate tells beside the
    sentence (`gate.with_way_out`)."""

    why: str
    fix: str


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
    `low` mean. Until 0.103.0 the field was a hand-written line (`<date> · scope
    sha <12 hex> · N findings`) whose sha a regex read and whose record the
    sha then had to find — the record names its sha itself, so the head
    names the record (review 2026-10-22). `n/a` passed every gate until
    0.99.0 (third haiku round, t18: "RF model training does not require
    external audit"); the refusal names the honest ways and offers no
    word to write instead."""
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
            "audit is owed at all, the repeat cost is wrong, not the field — and a "
            "tier lowered after the protocol's first commit is reported "
            "(LAB-015 Preflight audit before freezing, LAB-017 The number of audits follows the cost tier)",
            audit,
        )
    path = area / DIR / name
    if not path.is_file():
        return RecordGap(
            f"`preflight_audit` names {DIR}/{name}, and there is no such record in "
            f"this area — name the one `labkit-audit <area> --mode preflight` wrote",
            audit,
        )
    try:
        record = read(path)
    except FindingsError as exc:
        return RecordGap(str(exc), record_way(area))
    if record.mode != PREFLIGHT_AUDIT:
        return RecordGap(
            f"{name} is a {record.mode} record — `preflight_audit` names the "
            "preflight audit",
            audit,
        )
    try:
        now = area_stamp(area)[0]
    except (FileNotFoundError, ValueError) as exc:
        return RecordGap(f"the area cannot be stamped now ({exc})", audit)
    if record.scope_sha != now:
        return RecordGap(
            f"the record {name} saw scope sha {record.scope_sha}, the code now stamps "
            f"{now} — it changed after the audit, so the change owes a new audit "
            f"(`labkit-audit <area> --mode preflight`); naming another record "
            f"without one is refused too{validation_note(area)}",
            audit,
        )
    judged = _protocol_gap(record, name, text)
    if judged:
        return RecordGap(judged, audit)
    if record.open:
        return RecordGap(
            f"{len(record.open)} finding(s) of {name} still `open` — decide each "
            f"({DECIDED_LIST})",
            decide_ways(area, record),
        )
    return None


def _protocol_gap(record: Record, name: str, text: str) -> str | None:
    """Why RECORD (named NAME) judged another protocol than TEXT, or None:
    another promise block (`block_sha`) or another registration — the kind,
    the question or another field the kind owes (`registration`)."""
    try:
        block = promises.block_stamp(text)
    except promises.PromiseError as exc:
        return str(exc)
    if record.block_sha != block:
        return (
            f"the record {name} saw the promise block {record.block_sha}, the protocol "
            f"carries {block} now — a promise rewritten after the audit owes a new one"
        )
    changed = registration_note([record], registration_stamp(text))
    return (
        f"the record {name} no longer covers the protocol{changed}" if changed else None
    )
