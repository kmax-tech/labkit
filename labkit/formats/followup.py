"""followup — what an analysis audit is shown of the area's earlier decided
BLOCKERs, and the chain a carried finding forms with its origin.

A BLOCKER that was decided — `fixed`, `limitation`, `false-positive` —
in a record that is not of the state now audited is an *earlier* BLOCKER.
The next analysis audit is shown each one and says per finding whether the
fault it names is in the state it sees (`resolved`: not there, repaired
or never a fault — the why says which; `unresolved`; `not_assessable`).
A finding not found resolved is not dropped: labkit writes it into the new
record as a *carried* finding (`carried_finding`), open, with the
original's text, check and note, and `carries = "<record>#<n>"` naming
the finding it continues. There it is decided like any finding of the
current state, and one decided limitation renders as a limitation of the current
result. Why (fixed-followup pilots, 2026-10-26): an earlier decision
otherwise left the result without trace — a `fixed` with no check, an
`accepted` limit that the renderer, reading only covering records, no
longer showed.

The chain: a carried finding continues one earlier finding, which may
itself be carried; following `carries` ends at the *origin*, a finding
the auditor wrote. `chain` reads it for a set of records and refuses a
reference to no finding, to a later or the same record, to a finding
that is no BLOCKER, a loop, and two carried findings of one origin in one
record. The *head* of an origin is its finding no other finding carries;
only heads are shown again, so an origin is carried at most once per
record and a limit does not multiply over audits.

Pure: records in, data out. The audit shows and writes
(`audit_prompt.bound_prompt`, `audit._record`); report-check holds the release
(`report_decisions.followup_findings`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from labkit.formats.findings import (
    DECIDED,
    Finding,
    FindingsError,
    FixVerdict,
    Record,
    check_order,
    decision_digest,
)

#: the statuses under which a BLOCKER is earlier evidence to follow up:
#: every decided one (`findings.DECIDED`)


@dataclass(frozen=True)
class Member:
    """One finding of a record, with the record and its number."""

    record: Record
    n: int
    finding: Finding

    @property
    def ref(self) -> str:
        """`<record>#<n>` — how a prompt, a FIX line and `carries` name it."""
        return f"{self.record.path.name}#{self.n}"


@dataclass(frozen=True)
class Chain:
    """The findings of a set of records with their carried links: every
    finding by ref (`members`), the origin of each (`origin`), and the
    refs some other finding carries (`carried`)."""

    members: dict[str, Member]
    origin: dict[str, str]
    carried: set[str]

    def heads(self) -> list[Member]:
        """The findings no other finding carries, in record order."""
        return [m for ref, m in self.members.items() if ref not in self.carried]

    def of_origin(self, origin: str) -> list[Member]:
        """Every finding whose origin is ORIGIN, in record order."""
        return [m for ref, m in self.members.items() if self.origin[ref] == origin]


def chain(records: list[Record]) -> Chain:
    """The chain of RECORDS, oldest first as `findings.area_records` gives
    them. Raises FindingsError on a `carries` that names no finding of
    RECORDS, a finding of the same or a later record, a finding that is no
    BLOCKER; on a loop; on two findings of one origin carried in one
    record."""
    members: dict[str, Member] = {}
    order: dict[str, int] = {}
    for i, r in enumerate(records):
        for n, f in enumerate(r.findings, 1):
            m = Member(r, n, f)
            members[m.ref] = m
            order[m.ref] = i
    for ref, m in members.items():
        target = m.finding.carries
        if not target:
            continue
        if target not in members:
            raise FindingsError(f"{ref}: carries {target}, which no record holds")
        if order[target] >= order[ref]:
            raise FindingsError(
                f"{ref}: carries {target}, a finding of the same or a later record"
            )
        if members[target].finding.grade != "BLOCKER":
            raise FindingsError(f"{ref}: carries {target}, which is no BLOCKER")
    origin = {ref: _origin(ref, members) for ref in members}
    _once_per_record(members, origin)
    carried = {m.finding.carries for m in members.values() if m.finding.carries}
    return Chain(members, origin, carried)


def _once_per_record(members: dict[str, Member], origin: dict[str, str]) -> None:
    """Raise FindingsError when one record carries two findings of one
    origin — an origin is carried once per record."""
    seen: dict[tuple[str, str], str] = {}
    for ref, m in members.items():
        if not m.finding.carries:
            continue
        key = (m.record.path.name, origin[ref])
        if key in seen:
            raise FindingsError(
                f"{ref} and {seen[key]} both carry origin {origin[ref]} in one record "
                f"— an origin is carried once per record"
            )
        seen[key] = ref


def _origin(ref: str, members: dict[str, Member]) -> str:
    """The finding REF's chain ends at. Raises FindingsError on a loop
    (a chain that comes back to a finding it passed)."""
    passed = [ref]
    while members[passed[-1]].finding.carries:
        nxt = members[passed[-1]].finding.carries
        if nxt in passed:
            raise FindingsError(
                f"a loop of carried findings: {' -> '.join(passed + [nxt])}"
            )
        passed.append(nxt)
    return passed[-1]


def earlier_blockers(
    records: list[Record], current: Callable[[Record], bool]
) -> list[Member]:
    """The heads that are BLOCKERs decided (DECIDED) in a record that is not
    of the state CURRENT tells — what a follow-up audit is shown. Raises
    what `chain` raises."""
    return [
        m
        for m in chain(records).heads()
        if m.finding.grade == "BLOCKER"
        and m.finding.status in DECIDED
        and not current(m.record)
    ]


def carried_finding(member: Member, verdict: FixVerdict, origin: Finding) -> Finding:
    """The open BLOCKER a new record carries for MEMBER after VERDICT did not
    find it resolved: the ORIGIN's text under one prefix naming what it
    continues and why (so the text does not grow over a chain), the
    member's check and note, `carries` = its ref."""
    return Finding(
        "BLOCKER",
        f"carried from {member.ref} ({verdict.verdict}): {origin.text}",
        "open",
        "",
        "",
        member.finding.check,
        member.finding.check_note,
        member.ref,
    )


@dataclass(frozen=True)
class Hold:
    """Why an earlier decided BLOCKER (or a finding of the state audited)
    does not release the result: the finding's REF, WHY in words, and the
    STEP that is missing."""

    ref: str
    why: str
    step: str

    @property
    def needs_followup_audit(self) -> bool:
        """Does STEP end in the follow-up audit (FOLLOWUP_AUDIT)? It refuses an
        area holding several protocols (`audit_prompt.earlier_of`)."""
        return FOLLOWUP_AUDIT in self.step


#: the follow-up audit as a step names it
FOLLOWUP_AUDIT = "`labkit-audit <area> --mode analysis`"
#: the step when a follow-up audit is all that is missing
STEP_AUDIT = f"{FOLLOWUP_AUDIT} follows it up"
#: what stands instead of a step ending in the follow-up audit where it
#: cannot run: an area holding several protocols (`audit_prompt.earlier_of`)
STEP_NONE_SEVERAL = (
    "no step labkit offers clears this here yet: the follow-up audit refuses an "
    "area holding several protocols (its records name no protocol, so it would "
    "guess whose question an earlier finding judged), and deciding the finding "
    "again does not remove it from what is followed up — the number stays "
    "unreported from this area"
)


def release_holds(
    records: list[Record], covering: list[Record], metrics: dict | None
) -> list[Hold]:
    """The release rule of earlier decided BLOCKERs, over RECORDS (the
    area's, oldest first), COVERING (the analysis records of the state
    reported now, `audit_binding.covering_analysis`) and METRICS (the
    answering run's metrics.json). Pure.

    An origin whose head is a decided BLOCKER outside COVERING is released
    by a valid `resolved` in a covering record — on that head, on its
    decision as it stands now (`decision_digest`), with the required check
    shown (`check_present`) — and only while no covering record holds a
    verdict other than `resolved` on any finding of that origin: the state
    is the same, so a later favourable draw does not outvote it. A head
    followed up only in a record outside COVERING is held as followed up
    in a record that no longer covers this state, not as never followed
    up: the follow-up happened, the state moved since. A head in a
    covering record is decided there and held by that record's gates; of
    those, one rule is this module's: a BLOCKER `fixed` in a covering
    record is held, since no follow-up has seen the repair. Raises what
    `chain` raises."""
    c = chain(records)
    in_cover = {r.path.name for r in covering}
    verdicts = [v for r in covering for v in r.fix_verdicts]
    stale = [r for r in records if r.path.name not in in_cover and r.fix_verdicts]
    out: list[Hold] = []
    for m in c.heads():
        f = m.finding
        if f.grade != "BLOCKER":
            continue
        if m.record.path.name in in_cover:
            if f.status == "fixed":
                out.append(
                    Hold(
                        m.ref,
                        "decided `fixed` in the state audited — no follow-up has seen "
                        "the repair",
                        "change what the finding names — the code, then a new run; "
                        "a description in the protocol's setup, corrected in place; "
                        "a wrong adoption, `protocol-fill <PROTOCOL> --withdraw "
                        f'--why "…"` — and {FOLLOWUP_AUDIT}',
                    )
                )
            continue
        if f.status not in DECIDED:
            continue
        hold = _earlier_hold(m, c, verdicts, stale, metrics)
        if hold is not None:
            out.append(hold)
    return out


def _earlier_hold(
    m: Member,
    c: Chain,
    verdicts: list[FixVerdict],
    stale: list[Record],
    metrics: dict | None,
) -> Hold | None:
    """Why the earlier head M is not released by VERDICTS (the covering
    records'), or None. STALE are the records outside the cover that hold
    follow-ups, oldest first: a follow-up of M there is named instead of
    "never followed up"."""
    f = m.finding
    of_origin = {x.ref for x in c.of_origin(c.origin[m.ref])}
    against = [v for v in verdicts if v.ref in of_origin and v.verdict != "resolved"]
    if against:
        v = against[0]
        return Hold(
            m.ref,
            f"the follow-up of this state said {v.verdict}: {v.why.splitlines()[0]}",
            "a later draw on the same state settles nothing: change the code or the "
            "run, or decide the finding the follow-up carried",
        )
    on_head = [v for v in verdicts if v.ref == m.ref]
    now = decision_digest(f)
    valid = [v for v in on_head if v.decision_sha == now]
    if not on_head:
        if f.check and (metrics is None or f.check not in metrics):
            return Hold(
                m.ref,
                f"no follow-up, and the run lacks the required check `{f.check}`",
                f"{check_order(f.check, f.check_note)}; then a new run, and {STEP_AUDIT}",
            )
        followed = [r for r in stale if any(v.ref == m.ref for v in r.fix_verdicts)]
        if followed:
            return Hold(
                m.ref,
                f"followed up in {followed[-1].path.name}, which no longer covers "
                f"this state",
                STEP_AUDIT,
            )
        return Hold(m.ref, f"decided `{f.status}`, never followed up", STEP_AUDIT)
    if not valid:
        return Hold(
            m.ref,
            "the follow-up judged another decision — it changed since",
            STEP_AUDIT,
        )
    if f.check and not all(v.check == f.check and v.check_present for v in valid):
        return Hold(
            m.ref,
            f"`resolved`, but the required check `{f.check}` was not in the run shown",
            f"{check_order(f.check, f.check_note)}; then a new run, and {STEP_AUDIT}",
        )
    return None
