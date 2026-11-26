"""findings — an audit's findings as data the person decides, not as prose.

`labkit-audit` writes what it found into the area, one file per audit
(`audit_records`: the file's layout, its writer, its loud reader and the
decision stored in place).

When the backend does not answer, `labkit-audit` writes no findings but
a failed attempt beside them (`failed_attempts`); `area_records` reads the
records only.
A record binds what the auditor read: the code (`scope_sha`), the promise
block (`block_sha`), the registration it judged — the kind and the
question with the other fields the kind owes (`registration`), not the
report fields written after the run; a preflight record also the fields
read before the run (`protocol_check.AUDITED_FIELDS`), which an analysis
record binds through what it was shown — and, in mode analysis, the
answering run (`run_id`).
A full run at `high` needs the preflight record the head names
(`preflight_audit = "<minute>-preflight.toml"`) to be one of the code and
the promises as they are now, every finding decided (`audit_gaps.audit_record_gap`,
held by runlog's freeze gate and by `preflight`; `audit_gaps`); a reported number needs
an analysis record of code, promises and the answering run as they are
now (`report-check`); a record of the code alone would keep an audit
valid for a promise rewritten after it or a later run under the same
code. `preflight` reads every
findings file of the area: a finding still `open`
is a warning before the freeze and a blocker once `frozen = true`
(LAB-015 Preflight audit before freezing: every finding is decided). A
finding nobody can settle stays `open`: a handover of its protocol records
it and ends the protocol without a result, and the gates read the handover
(`handovers.acknowledgement`); open findings a handover elsewhere in the
repo lists are printed as a reminder and never counted.

Why as data: a decision in a protocol line is lost in its prose, while
the unsettled findings as data stay visible across areas, and an audit's
yield (fixed / limitation / false-positive per class) can be counted
instead of read.

The statuses are named by their consequence: `fixed` — the person claims
the whole confirmed fault repaired, with confirmation still owed; on an
`undetermined` finding the required check is built and run (a `diff:`
check is shown by the follow-up audit, nothing is built), and the
follow-up audit settles the suspicion from its value, carrying a confirmed
fault as `implementation` or `statement`; `limitation` — the
finding is true and the number carries it as a Limitation line; `false-positive`
— the auditor misread, the reason names the counter-evidence. A `limitation` on
a BLOCKER or WARNING records its effect (`effect`): `stands` — the
verdicts hold, read within the limit — unless `--not-assessable IDS` names
the promises this run does not judge (`criterion-1 not assessable`). Which
follows from what the promise's sentence claims — a threshold on these
items, or a capability — not from the grade. The protocol carries each as a `Limitation (audit <record> #N)` line
and a note in Recorded results (`protocol-fill --from-run` writes both from the
record), and report-check holds them to it (`limit_line`, `answer_note`). Whether the
named limit is enough stays the audit's question, not this check's.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.gate import (
    BLOCKER,
    WARNING,
    RuleAssignment,
)
from labkit.formats.decision_history import ReplacedDecision
from labkit.formats.standard_contract import ANALYSIS_AUDIT, PREFLIGHT_AUDIT
from labkit.formats.finding_line import (
    GRADES,
    IMPLEMENTATION,
    SETTLED_SUBJECTS,
    STATEMENT,
    UNDETERMINED,
    tagged_line,
)
from labkit.formats.required_check import CHECK_FORM

#: what a person decided about a finding — the one spelling every reader
#: compares a `status` with, and the word the record's TOML holds
OPEN = "open"
FIXED = "fixed"
LIMITATION = "limitation"
FALSE_POSITIVE = "false-positive"
STATUSES = (OPEN, FIXED, LIMITATION, FALSE_POSITIVE)
REASON_OWED = (LIMITATION, FALSE_POSITIVE)
#: the statuses under which a finding leaves the result's limits without
#: a Limitation line — the fault removed, put off, or not a fault. After a
#: review did not uphold a decision on the finding, none of them settles
#: it alone (`reviews.once_not_upheld`, `report_decisions.review_findings`)
CLOSING = (FIXED, FALSE_POSITIVE)
#: every status but `open`: what deciding a finding sets
DECIDED = tuple(s for s in STATUSES if s != OPEN)
#: the decided statuses as a step names them: "fixed / limitation / false-positive"
DECIDED_LIST = " / ".join(DECIDED)
#: a carried finding (`carries`: a follow-up did not find its fault gone)
#: closed with one of these owes a decision review before the number leaves
CARRIED_CLOSING = (FALSE_POSITIVE,)
EFFECT_GRADES = (BLOCKER, WARNING)
MODES = (PREFLIGHT_AUDIT, ANALYSIS_AUDIT)
#: what an analysis record names as its run when no completed run was
#: bound to the protocol while the auditor read — it saw no rows
NO_RUN = "none"


class FindingsError(ValueError):
    """A findings file that cannot be read as such; the message names file and field."""


class EffectFormError(FindingsError):
    """A decision's effect missing where it is owed (a BLOCKER decided limitation) or
    not in EFFECT_FORM — the refusals whose example is a promise id, which
    `labkit-audit --decide` completes for a protocol without promises."""


@dataclass(frozen=True)
class Finding:
    """One finding of one audit and what the person decided about it."""

    grade: str
    # the finding whole, as the auditor wrote it: its grade line and the
    # lines below it up to the next finding or section, stripped, joined by
    # "\n" (`audit_reply.finding_entries`); its closing field is the check
    text: str
    status: str
    reason: str
    effect: str = ""  # limit: EFFECT_STANDS or "<ids> not assessable"
    # the diagnostic the auditor requires to show a repair: a metrics.json
    # key, set from the finding line when the record is written, never by
    # a decision ("" when none is required)
    check: str = ""
    # what the check's value must show, as the auditor wrote it after the
    # key ("" when it wrote none); bound with the check
    check_note: str = ""
    # a carried finding: the earlier finding it continues, `<record file>#<n>`
    # — written by labkit-audit when a follow-up did not find it resolved,
    # never by a person ("" for the auditor's own findings); its origin is
    # found by following the chain (`followup.chain`)
    carries: str = ""
    # SUBJECTS: the auditor's third field, read when the record is written
    # (`subject_of`) and carried with the finding, never set by a decision;
    # every record names it (`_auditor_fields`)
    subject: str = ""
    # the rule the auditor assigned (`active_rule_of`), as the gate's value
    # (`gate.RuleAssignment`): a known rule with the ledger's name, or the
    # new class; read when the record is written, never set by a decision;
    # apart from the subject and the place, and never inferred from them.
    # None only for a finding not read from a record (a test's)
    rule: RuleAssignment | None = None
    # the decisions a later one replaced, oldest first (`decision_history`):
    # added by `write_decision` alone, never copied to a carried finding
    replaced_decisions: tuple[ReplacedDecision, ...] = ()

    @property
    def never_decided(self) -> bool:
        """Is this the state a finding is written in — `open`, no reason, no
        effect? It is no decision. An `open` with a reason is undecided too,
        but it is a decision taken back, and replacing it keeps it."""
        return (self.status, self.reason, self.effect) == (OPEN, "", "")

    @property
    def one_line(self) -> str:
        """TEXT on one line, its lines joined by a space — how a view that
        gives each finding one line shows it (the decision list, a gate's
        line, a reminder); the record and the prompts keep TEXT."""
        return " ".join(self.text.splitlines())

    @property
    def place(self) -> tuple[str, str] | None:
        """(file, place) of the grade line as the instructions write it,
        `<GRADE> · <file>:<place> · <subject> · …`, read by the one grammar
        (`tagged_line`, its fields parted at a dot or a dash as `subject_of`
        reads them): the file's name and what follows its first colon; None
        for a line of another grade, or without a field after the place.
        Read from that one field, never searched for in the text."""
        first = self.text.splitlines()[0] if self.text else ""
        line = tagged_line(first)
        if line is None or line.tag != self.grade or len(line.fields) < 2:
            return None
        at = line.file_place
        return (Path(at[0]).name, at[1]) if at is not None else None

    @property
    def effect_owed(self) -> bool:
        """A BLOCKER decided `limitation` owes the effect it has on the verdicts."""
        return self.grade == BLOCKER and self.status == LIMITATION

    @property
    def effect_allowed(self) -> bool:
        """A BLOCKER or WARNING decided `limitation` carries an effect; nothing else."""
        return self.grade in EFFECT_GRADES and self.status == LIMITATION


#: an analysis audit's verdict on an earlier decided BLOCKER (fixed,
#: limitation or false-positive):
#: the fault is gone in the files and rows it was shown, still there, or
#: not to be judged from them (no diagnostic shown that could tell)
FIX_VERDICTS = ("resolved", "unresolved", "not_assessable")


@dataclass(frozen=True)
class FixVerdict:
    """An analysis audit's verdict on one earlier decided BLOCKER: the
    record and number it stands in, the decision as it was shown
    (`decision_digest`), the verdict and its why. Bound to that decision:
    a changed status or reason is another decision, which this verdict
    says nothing about."""

    record: str  # the earlier record's file name
    n: int  # the finding's number in it, as `--decide` takes it
    decision_sha: str
    verdict: str  # one of FIX_VERDICTS
    why: str
    # the check the finding required ("" for none) and whether its key stood
    # in the metrics.json the prompt showed — computed by labkit from that
    # snapshot, never by the model; None when no check was required. A
    # `resolved` with check_present False is kept as written: the verdict
    # is the measure, the missing key the gap.
    check: str = ""
    check_present: bool | None = None
    # for an undetermined finding found `unresolved`: what the fault turned
    # out to be (SETTLED_SUBJECTS), the subject its carried finding takes;
    # "" on every other verdict
    subject: str = ""

    @property
    def ref(self) -> str:
        """`<record>#<n>` — how the auditor names the finding."""
        return f"{self.record}#{self.n}"


#: how a carried finding names the one it continues: `<record file>#<n>`
CARRIES_REF = re.compile(r"^[^\s#/]+\.toml#[1-9]\d*$")


def undetermined_finding_problem(
    grade: str, subject: str, check: str, note: str
) -> str | None:
    """Why a finding of GRADE and SUBJECT with the required CHECK and its
    NOTE cannot stand, or None: an `undetermined` finding is a BLOCKER — the
    follow-up judges earlier BLOCKERs only, and a suspicion no one judges is
    never settled — and names the check that settles it and, after the key,
    what its value must show. One rule for the writer and the reader."""
    if subject != UNDETERMINED:
        return None
    if grade != BLOCKER:
        return (
            f"an {UNDETERMINED} finding is a BLOCKER, not a {grade}: only a "
            f"BLOCKER's check is judged by the follow-up"
        )
    if check and note:
        return None
    return (
        f"an {UNDETERMINED} finding closes with the check that settles it and "
        f"what its value must show — {CHECK_FORM}, the note required"
    )


def undetermined_fix_problem(judged: Finding, v: FixVerdict) -> str | None:
    """Why the follow-up verdict V cannot stand on the earlier finding
    JUDGED, by JUDGED's subject, or None. On an `undetermined` finding the
    check's value decides: `resolved` only with the check shown (the
    suspicion is cleared by its value, not by the auditor's word);
    `not_assessable` only while it is missing (shown, it settles the
    suspicion one way or the other, so an unclear finding cannot be carried
    unclear for ever); `unresolved` names what the fault turned out to be
    (SETTLED_SUBJECTS), which its carried finding takes — with the check
    shown or missing, when the fault is plain from other evidence. A
    subject on a verdict on another finding is refused: nothing else is
    reclassified by a follow-up; a subject on a verdict other than
    `unresolved` is `fix_verdict_problem`'s."""
    if judged.subject != UNDETERMINED:
        if v.subject:
            return (
                f"fix verdict on {v.ref}: a subject ({v.subject!r}) only on an "
                f"`unresolved` verdict on an {UNDETERMINED} finding — {v.ref} is "
                f"recorded as `{judged.subject}`: "
                f"`FIX · {v.ref} · unresolved · <why>`"
            )
        return None
    if v.verdict == "resolved" and not v.check_present:
        return (
            f"fix verdict on {v.ref}: `resolved` on an {UNDETERMINED} finding "
            f"needs its check `{judged.check}` shown — without its value the "
            f"suspicion is not cleared; `not_assessable` while it is missing"
        )
    if v.verdict == "not_assessable" and v.check_present:
        return (
            f"fix verdict on {v.ref}: its check `{judged.check}` is shown — on an "
            f"{UNDETERMINED} finding its value settles the suspicion: `resolved`, "
            f"or `unresolved` naming what the fault is"
        )
    if v.verdict == "unresolved" and v.subject not in SETTLED_SUBJECTS:
        return (
            f"fix verdict on {v.ref}: `unresolved` on an {UNDETERMINED} finding "
            f"names what the fault turned out to be — `FIX · {v.ref} · unresolved "
            f"· {IMPLEMENTATION}|{STATEMENT} · <why>`"
        )
    return None


@dataclass(frozen=True)
class AuditedState:
    """The state of an area an audit saw and its record binds: the code
    (SCOPE_SHA, `scope_sha.area_stamp`), the promise block (BLOCK_SHA,
    `promises.block_stamp`), the REGISTRATION it judged
    (`protocol_check.registration_stamp`, compared as a mapping) and, mode
    analysis, the RUN_ID it read (NO_RUN: none) and the SHOWN_SHA of what
    it was shown of that run; both None for preflight. One type for the
    prompt that binds it (`audit_prompt.bound_prompt`), the record (`Record.state`)
    and every match of the two (`audit_gaps.covering_records`)."""

    scope_sha: str
    block_sha: str
    registration: Mapping[str, str]
    run_id: str | None = None
    shown_sha: str | None = None

    def __eq__(self, other: object) -> bool:
        # the registration as a mapping: a record keeps it in the order written
        if not isinstance(other, AuditedState):
            return NotImplemented
        return self.bound == other.bound and dict(self.registration) == dict(
            other.registration
        )

    def __hash__(self) -> int:
        # what __eq__ compares, the registration as sorted pairs
        return hash((self.bound, tuple(sorted(dict(self.registration).items()))))

    @property
    def bound(self) -> tuple[str, str, str | None, str | None]:
        """(code, promises, run, shown) — the state, its registration aside."""
        return (self.scope_sha, self.block_sha, self.run_id, self.shown_sha)

    def words(self) -> str:
        """What the state binds, in words: `code <sha>, promises <block>[,
        run <id>, shown <sha>]`."""
        return (
            f"code {self.scope_sha}, promises {self.block_sha}"
            + (f", run {self.run_id}" if self.run_id is not None else "")
            + (f", shown {self.shown_sha}" if self.shown_sha is not None else "")
        )


@dataclass(frozen=True)
class Record:
    """One audit's findings file."""

    path: Path
    date: str
    mode: str
    model: str
    scope_sha: str  # the code the auditor read
    block_sha: str  # the promise block it read (promises.NO_BLOCK: none declared)
    # the registration it judged: the kind and a digest per owed field —
    # in mode preflight also per field read before the run
    # (`protocol_check.registration_stamp`), in the order written
    registration: tuple[tuple[str, str], ...]
    run_id: (
        str | None
    )  # mode analysis: the run whose rows it read (NO_RUN: none); preflight: None
    # mode analysis: the digest of what the prompt showed of that run (its
    # rows' excerpts and metrics.json, `audit_binding.run_shown`); preflight: None
    shown_sha: str | None
    verdict: tuple[int, int, int]
    findings: tuple[Finding, ...]
    # the id of the protocol the audit read (`protocol_block.ID_SHAPE`): in
    # an area of several protocols, whose question each finding judged
    protocol_id: str
    # mode analysis: its verdicts on earlier decided BLOCKERs, one per
    # finding at most; a finding shown without one is unchecked
    fix_verdicts: tuple[FixVerdict, ...] = ()

    @property
    def state(self) -> AuditedState:
        """The state this record binds (`AuditedState`)."""
        return AuditedState(
            self.scope_sha,
            self.block_sha,
            dict(self.registration),
            self.run_id,
            self.shown_sha,
        )

    @property
    def open(self) -> list[Finding]:
        """The findings nobody has decided yet."""
        return [f for f in self.findings if f.status == OPEN]

    def limits(self) -> list[tuple[int, Finding]]:
        """(number, finding) of every finding that is a limit of the result:
        a BLOCKER decided `limitation` (its effect owed) and a WARNING decided
        `limitation` with its effect — numbered as `--decide` takes them."""
        return [
            (n, f)
            for n, f in enumerate(self.findings, 1)
            if f.effect_owed or (f.effect_allowed and f.effect)
        ]


@dataclass(frozen=True)
class OpenFinding:
    """One finding still `open`, with the record it stands in."""

    record: Record
    finding: Finding

    @property
    def number(self) -> int:
        """The finding's number in its record, as `--decide` takes it
        (`number_of`)."""
        return number_of(self.record, self.finding)

    @property
    def grade(self) -> str:
        """The finding's grade — BLOCKER, WARNING or NOTE."""
        return self.finding.grade

    @property
    def line(self) -> str:
        """`<record file>: <text on one line>` — how every gate names it."""
        return f"{self.record.path.name}: {self.finding.one_line}"


def number_of(record: Record, finding: Finding) -> int:
    """FINDING's 1-based number in RECORD, found by identity, not by
    equality: two equal findings in one record each keep their own number,
    so a printed `--decide` names the right one.
    Raises ValueError when FINDING is not one of RECORD's."""
    for n, f in enumerate(record.findings, 1):
        if f is finding:
            return n
    raise ValueError(f"{record.path.name}: the finding is not one of its own")


def open_findings(
    records: Iterable[Record], *, mode: str | None = None
) -> list[OpenFinding]:
    """Every finding still `open` in RECORDS, in record order — of MODE's
    records only when MODE is given. The one home of the question "is an
    audit finding still undecided". What a gate makes of an undecided
    finding is that gate's rule; the rules stand side by side here:

        gate                         records            an undecided finding is
        preflight, unfrozen          every mode         a WARNING — the decision is owed at the freeze, not before
        preflight, frozen            every mode         a BLOCKER — frozen = true owes every decision
                                                        (LAB-015 Preflight audit before freezing)
        runlog start, full run       preflight only     a BLOCKER refuses the run; a WARNING or NOTE is told
                                                        only with the run acknowledged (LABKIT_UNFROZEN=1),
                                                        a clean start says nothing of it — the run rests on
                                                        the preflight audit; an analysis record judges a
                                                        run, and finalize holds it
        the record the head names    that record only   any grade is a gap (`audit_gaps.audit_record_gap`): the freeze
        (runlog, preflight,                             refuses, preflight warns unfrozen and blocks frozen,
        protocol-check)                                 protocol-check reports — the named record stands
                                                        for the frozen state, decided whole
        finalize                     every mode, the    its grade: BLOCKER blocks, WARNING warns, NOTE is told
                                     protocol's own     — a finding on another protocol of the area holds nothing
        claude-hook stop / undecided every mode, the    a BLOCKER only — the hook says what the commit would be
                                     areas the session  refused for and nags for nothing less (`open_blockers`)
                                     touched
        protocol-fill --handover     every mode         an open BLOCKER stays open: the handover records it
                                                        (`handovers.remaining`) and the stop/commit read the
                                                        handover instead of holding it
        labkit-audit --findings      every mode         a BLOCKER selects its record for the listing and prints
                                                        the handover command beside its `--decide` (`open_blockers`)
        report-check, replacement    the predecessor's  a BLOCKER holds the replacement until it is decided
                                     area               or a handover of the predecessor lists it (`open_blockers`)
        audit_coverage (report-check) the covering record  any grade: the record is not decided

    The differences are intended. A change to one row is a change to that
    gate's rule: say so in its docstring and in this table. `audit_gaps.audit_record_gap`
    reads `Record.open` of the one named record itself; every walk over
    records goes through here.
    """
    return [
        OpenFinding(r, f)
        for r in records
        if mode is None or r.mode == mode
        for f in r.open
    ]


def open_blockers(records: Iterable[Record]) -> list[OpenFinding]:
    """The open findings of RECORDS graded BLOCKER (`open_findings`): what
    the stop and the commit hold, what a handover owes decided first, what
    `labkit-audit --findings` opens its handover steps on (its listing
    shows every record with an open finding of any grade)."""
    return [u for u in open_findings(records) if u.grade == BLOCKER]


def counts_outrun(verdict: tuple[int, int, int], grades: list[str]) -> str | None:
    """Why VERDICT counts more blockers or warnings than GRADES lists, or
    None: a record whose counts outrun its tables reads as "nothing open"
    — covered, decided, frozen. Notes are not held; an auditor counts
    them loosely. One answer for the writer and the reader: a person edits
    the files, so the reader holds the same line."""
    b, w, _ = verdict
    listed = {g: sum(1 for grade in grades if grade == g) for g in GRADES}
    if b > listed[BLOCKER] or w > listed[WARNING]:
        return (
            f"the verdict counts {b} blocker(s) and {w} warning(s), the record "
            f"carries {listed[BLOCKER]} BLOCKER and {listed[WARNING]} WARNING "
            f"line(s)"
        )
    return None


def count_problem(name: str, value: object) -> str | None:
    """Why VALUE is no count of NAME (blockers, warnings, notes), or None: a
    count is a non-negative integer. One rule for the writer and the reader,
    so `blockers = -1` is neither written nor read."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return f"{name} = {value!r} is not a non-negative integer"
    return None


def verdict_disagrees(verdict: tuple[int, int, int], grades: list[str]) -> str | None:
    """Why VERDICT's blockers and warnings are not exactly the BLOCKER and
    WARNING lines GRADES lists, or None — the one audit result a record and
    an exit code are made from. More lines than counted is a withdrawn
    finding ("Correction: no finding" under a BLOCKER line), which would
    exit 0 while the record keeps the blocker open. Notes are not held; an
    auditor counts them loosely."""
    b, w, _ = verdict
    listed = {g: sum(1 for grade in grades if grade == g) for g in GRADES}
    if b != listed[BLOCKER] or w != listed[WARNING]:
        return (
            f"the verdict counts {b} blocker(s) and {w} warning(s), the report "
            f"lists {listed[BLOCKER]} BLOCKER and {listed[WARNING]} WARNING "
            f"line(s)"
        )
    return None


def fix_verdict_problem(verdicts: Iterable[FixVerdict]) -> str | None:
    """Why VERDICTS cannot stand in one record, or None: a verdict outside
    FIX_VERDICTS, an empty why, a number below 1, two verdicts on one
    finding — which of two would count is no question a gate should answer
    —, or a subject outside SETTLED_SUBJECTS or on a verdict other than
    `unresolved`. One rule for the writer and the reader; what the subject
    may be for the finding judged is `undetermined_fix_problem`'s."""
    seen: set[str] = set()
    for v in verdicts:
        if v.verdict not in FIX_VERDICTS:
            return f"fix verdict on {v.ref}: {v.verdict!r} — one of {', '.join(FIX_VERDICTS)}"
        if not v.why.strip():
            return f"fix verdict on {v.ref}: no why"
        if v.n < 1:
            return f"fix verdict on {v.ref}: finding numbers start at 1"
        if v.ref in seen:
            return f"fix verdict on {v.ref}: a second verdict on the same finding"
        if bool(v.check) != (v.check_present is not None):
            return (
                f"fix verdict on {v.ref}: check {v.check!r} with check_present "
                f"{v.check_present!r} — a required check names whether its key was shown"
            )
        if v.subject and (
            v.verdict != "unresolved" or v.subject not in SETTLED_SUBJECTS
        ):
            return (
                f"fix verdict on {v.ref}: subject {v.subject!r} — one of "
                f"{', '.join(SETTLED_SUBJECTS)}, and only on an `unresolved` verdict"
            )
        seen.add(v.ref)
    return None
