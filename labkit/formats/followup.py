"""followup — what an analysis audit is shown of the area's earlier decided
BLOCKERs, and the chain a carried finding forms with its origin.

A BLOCKER that was decided — `fixed`, `accepted`, `dismissed`, `deferred` —
in a record that is not of the state now audited is an *earlier* BLOCKER.
The next analysis audit is shown each one and says per finding whether the
fault it names is in the state it sees (`resolved`: not there, repaired
or never a fault — the why says which; `unresolved`; `not_assessable`).
A finding not found resolved is not dropped: labkit writes it into the new
record as a *carried* finding (`carried_finding`), open, with the
original's text, check and note, and `carries = "<record>#<n>"` naming
the finding it continues. There it is decided like any finding of the
current state, and an accepted one renders as a limit of the current
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
(`audit.bound_prompt`, `audit._record`); report-check holds the release
(`report_check.followup_findings`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from labkit.formats.findings import Finding, FindingsError, FixVerdict, Record

#: the statuses under which a BLOCKER is earlier evidence to follow up
DECIDED = ("fixed", "accepted", "dismissed", "deferred")


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


def origins_of(members: Iterable[Member], c: Chain) -> list[str]:
    """The distinct origins of MEMBERS under C, in their order."""
    out: list[str] = []
    for m in members:
        o = c.origin[m.ref]
        if o not in out:
            out.append(o)
    return out
