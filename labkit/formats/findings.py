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
from labkit.formats import decision_history, promises
from labkit.formats.decision_history import ReplacedDecision
from labkit.formats.protocol_history import correctable
from labkit.formats.protocol_check import (
    CONCLUSION_LABEL,
    field_name,
    field_or_none,
)
from labkit.formats.repo import (
    EVIDENCE_DIR,
    is_protocol_name,
)
from labkit.formats.commands import audit_command, decide_command
from labkit.formats.runs import (
    NAME_MINUTE,
    as_stored,
)
from labkit.formats.digests import digest
from labkit.formats.standard_contract import ANALYSIS_AUDIT, PREFLIGHT_AUDIT
from labkit.formats.finding_line import (
    GRADES,
    IMPLEMENTATION,
    SETTLED_SUBJECTS,
    STATEMENT,
    UNDETERMINED,
    tagged_line,
)
from labkit.formats.required_check import CHECK_FORM, REQUEST_CHECKS, check_order

DIR = EVIDENCE_DIR
#: the attempt journal under DIR (`attempts`)
JOURNAL = "attempts.jsonl"
#: the folder under DIR that keeps each answer, named by its attempt
ANSWERS = "answers"
#: the suffix of a failed attempt's file, never of a record of findings
FAILED_SUFFIX = "-failed.toml"
#: the word a review's file name holds where a record's holds its mode
#: (`<minute>-<word>[-<n>].toml`) — a decision review's and a report
#: review's, then a claim review's. The writers of a name and its readers
#: (`name_ending`, `_WRITTEN_NAME`) take the word from here
REVIEW_WORD = "review"
CLAIM_REVIEW_WORD = "claim-review"


def name_ending(word: str) -> re.Pattern[str]:
    """How the name of a file ends that `create_file` wrote as
    `<minute>-WORD` with the suffix `.toml`: `-WORD[-<n>].toml`
    (`create_file` numbers a second file of the minute before the suffix)."""
    return re.compile(rf"-{re.escape(word)}(?:-\d+)?\.toml$")


#: the name of a decision review (`reviews`), written beside the records
#: and never read as one: `<minute>-review[-<n>].toml`. A claim review's
#: name ends the same way (`report_reviews.CLAIM_REVIEW_NAME` tells it)
REVIEW_NAME = name_ending(REVIEW_WORD)
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
#: a limit's effect on the verdicts: they stand with the limit, or the run
#: judges the named promises not at all (`--not-assessable`)
EFFECT_STANDS = "stands"
EFFECT_GRADES = (BLOCKER, WARNING)
_EFFECT_NOT = re.compile(r"^(\S+(?:\s*,\s*\S+)*)\s+not assessable$")
EFFECT_FORM = (
    '`stands` or `<ID>[, <ID>] not assessable` (e.g. "criterion-1 not assessable")'
)
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


def subject_refusal(f: Finding, status: str) -> str | None:
    """Why STATUS cannot decide F, by the subject the auditor gave it, or None:
    an `implementation` finding is never closed by `limitation` — the
    number came from code or data that depart from what was registered, and
    a limit line does not change that. Nor
    is an `undetermined` one: a limit line does not settle
    a suspicion — its check runs, the person decides `fixed` (the check
    built and run), and the follow-up judges the value."""
    if status != LIMITATION or f.subject not in (IMPLEMENTATION, UNDETERMINED):
        return None
    if f.subject == UNDETERMINED and f.check.startswith(REQUEST_CHECKS):
        return (
            "an undetermined finding is no limitation: a limit line does not "
            "settle the suspicion — decide `fixed` (nothing to build: the "
            "follow-up analysis audit shows the evidence the check asks for) and "
            "the follow-up judges it. `false-positive` when the auditor misread"
        )
    if f.subject == UNDETERMINED:
        return (
            "an undetermined finding is no limitation: a limit line does not "
            "settle the suspicion — make the measuring code write the check the "
            "finding names, measure anew, then decide `fixed` naming the check; "
            "the follow-up audit judges its value. `false-positive` when the "
            "auditor misread; or end the protocol without a result by a handover "
            "(`protocol-fill <PROTOCOL> --handover`), where the finding stays open"
        )
    return (
        "an implementation finding is no limitation: the code, the data "
        "handling or the run departs from the registration — repair it and "
        "measure anew, then decide `fixed`; `false-positive` when the auditor "
        "misread; or end the protocol without a result by a handover "
        "(`protocol-fill <PROTOCOL> --handover`), where the finding stays open"
    )


def allowed_decisions(f: Finding) -> tuple[str, ...]:
    """The decided statuses F can take, in DECIDED's order: every one but
    those `subject_refusal` refuses for F's subject."""
    return tuple(s for s in DECIDED if subject_refusal(f, s) is None)


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


def decision_after_restore(f: Finding) -> tuple[str, str] | None:
    """(status, the reason left for the person) F takes when its place is a
    registered protocol field and the field is restored as registered:
    `limitation` for a `statement` finding — the registered text stands,
    and what the finding names is a limit of the claim; None for an
    implementation finding, which is repaired in code or data and measured
    anew, and for an undetermined one, whose check runs first
    (`subject_refusal`)."""
    if f.subject != STATEMENT:
        return None
    return (
        LIMITATION,
        "<the registered text stands; what the finding names is a limit>",
    )


def decision_entails(
    f: Finding, area: Path, record: Path, protocol: Path | None = None
) -> str:
    """What F's decided status entails — the line `labkit-audit --decide`
    prints under the decision it recorded on F, a finding of RECORD in
    AREA, and the one home of its texts. `fixed`: a repair is
    claimed, confirmation pending; the next analysis audit judges it, a
    BLOCKER's number does not leave before, the check owed named when F
    carries one (`check_order`); what `fixed` means for this kind of
    repair, and that `labkit-next` names the step it owes, the line below
    says (`audit_decisions.repair_hint`).
    `limitation` with effect `stands`: the claim stands within the finding;
    a second auditor's review is owed at every repeat cost (`--review
    --record`) — a BLOCKER's number does not leave without it, a WARNING's
    absent review warns. `limitation` with `<ids> not assessable`: the run does
    not judge those promises; it releases the finding too, so the same
    review is owed, which confirms that the fault prevents judging them; a
    NOTE's limitation is
    recorded and limits nothing in the report (`Record.limits`).
    `false-positive`: the finding does not apply to the code and run as
    audited; the reason names the counter-evidence, and a BLOCKER's or a
    carried finding's is held by
    the review (`false_positive_blocker`, `carried_and_closed`). Each
    status is named by its consequence, so it is not misread as another.
    `open`, a decision taken back: the finding is undecided again, and a
    BLOCKER's number does not leave while it is open (a handover may
    record it open); of any grade it holds a frozen protocol's preflight.
    Raises ValueError on a status outside STATUSES."""
    here = Path.cwd()
    review = audit_command(
        area, "--review", "--record", record.name, protocol=protocol, base=here
    )
    if f.status == FIXED:
        owed = (
            f"; the check owed: {check_order(f.check, f.check_note)}" if f.check else ""
        )
        return (
            "fixed: a repair is claimed, confirmation pending — the next analysis "
            "audit judges it, and a BLOCKER's number does not leave before"
            f"{owed}; what `fixed` means for this repair, and where its next step is named, is the line below"
        )
    if f.status == LIMITATION and f.effect == EFFECT_STANDS:
        # the review is owed at every repeat cost, a low one too; a
        # WARNING's line does not say "before the number leaves", since the
        # adoption lets it through
        held = (
            "the number does not leave until a second auditor upholds it"
            if f.grade == BLOCKER
            else "a second auditor's review is owed; for a WARNING its absence "
            "does not hold the number, the adoption and report-check warn "
            "until a review upholds it"
        )
        return (
            "limitation: the finding holds and the number carries it as a Limitation line "
            "— give its effect on the claim in the reason; "
            f"{held}, at every repeat cost: `{review}`"
        )
    if f.status == LIMITATION and f.effect:
        held = (
            "the number does not leave until a second auditor confirms that the "
            "fault prevents judging it"
            if f.grade == BLOCKER
            else "a second auditor's review is owed, which confirms that the fault "
            "prevents judging it; for a WARNING its absence does not hold the "
            "number, the adoption and report-check warn until a review upholds it"
        )
        return (
            f"limitation: the finding holds and this run does not judge what it "
            f"names — `{f.effect}` stands in the report's Limitation line; "
            f"{held}, at every repeat cost: `{review}`"
        )
    if f.status == LIMITATION:
        return (
            "limitation: the finding holds and is recorded; a NOTE limits nothing in "
            "the report"
        )
    if f.status == FALSE_POSITIVE:
        held = (
            f"; a second auditor must uphold it before the number leaves: `{review}`"
            if false_positive_blocker(f) or carried_and_closed(f)
            else ""
        )
        return (
            "false-positive: the auditor misread this state — the reason must "
            f"name the counter-evidence (file, line, value){held}"
        )
    if f.status == OPEN:
        decide = audit_command(area, "--findings", protocol=protocol, base=here)
        held = (
            "; the number does not leave while it is open, unless a handover "
            "records it open"
            if f.grade == BLOCKER
            else ""
        )
        return (
            "open: the decision is taken back and the finding is undecided again"
            f"{held}; a frozen protocol's preflight blocks on it — `{decide}` "
            "prints the command that decides it"
        )
    raise ValueError(f"status {f.status!r} — one of {', '.join(STATUSES)}")


def corrected_field(f: Finding, protocol: Path, text: str) -> str | None:
    """The field F corrects in PROTOCOL, TEXT its text, as `field_name`
    gives it: F decided `fixed`, its place (`Finding.place`) PROTOCOL's
    file name and the field TEXT holds that it means — its label in full,
    or the one label it begins (`protocol_check.field_at`) — that a
    correction can release (`protocol_history.correctable`). None
    otherwise — a line number, a section or another file names no field,
    and the question has no correction in place. Raises
    `protocol_check.FieldPlaceError` when the place begins several fields
    or means one written twice: which field the correction is bound to
    cannot be told, and the caller says so.
    What a correction in place is bound to: a follow-up audit judges it on
    the field's change (`followup.earlier_corrections`), and finalize
    releases that change only on its `resolved` (`registration_hold.scope_changes`)."""
    at = f.place
    if f.status != FIXED or at is None or at[0] != protocol.name:
        return None
    hit = field_or_none(text, at[1])
    return hit.name if hit is not None and correctable(hit.label) else None


def decision_digest(f: Finding) -> str:
    """The digest of F as decided — grade, text, status, reason, effect, and
    the required check and its note, the finding a carried one continues
    and the decisions this one replaced when there are — which a review and
    a fix verdict
    bind to (`reviews.Decision.decision_sha`, `FixVerdict.decision_sha`): a
    changed reason, effect or check is another decision, and a verdict on
    the old one says nothing about it. So is a decision taken back and
    given again word for word: its replaced decisions differ
    (`decision_history.digest_fields`), and a confirmation of the earlier
    one does not return with the wording. The check, the carried finding
    and the replaced decisions join the digest only when there are any, so
    a finding without them keeps its digest and the reviews bound to it."""
    fields = [f.grade, f.text, f.status, f.reason, f.effect]
    if f.check:
        fields += [f.check] + ([f.check_note] if f.check_note else [])
    if f.carries:
        fields += ["carries", f.carries]
    fields += decision_history.digest_fields(f.replaced_decisions)
    return digest(as_stored(fields).encode("utf-8"))


def leaves_unjudged(effect: str) -> bool:
    """Whether the limitation's EFFECT is `<ID>[, <ID>] not assessable` — it
    voids the verdicts of what it names —, not `stands` and not none. The
    one test of the form: rendering lifts such an effect a review did not
    uphold, and the way after a rejection is its own."""
    return bool(effect) and effect != EFFECT_STANDS


def effect_ids(effect: str) -> tuple[str, ...]:
    """The promise ids EFFECT leaves not assessable, in its order — () for
    `stands`. Raises ValueError on any other text or an id that is no
    promise id (`promises.is_block_id`)."""
    if effect == EFFECT_STANDS:
        return ()
    m = _EFFECT_NOT.match(effect.strip())
    ids = tuple(i.strip() for i in m.group(1).split(",")) if m else ()
    if not ids or not all(promises.is_block_id(i) for i in ids):
        # an id in the letters of 0.103.0 names the version that reads it
        earlier = any(promises.EARLIER_ID.match(f"[{i}]") for i in ids)
        help_ = f"; {promises.EARLIER_IDS_HELP}" if earlier else ""
        raise ValueError(f"effect {effect!r} — {EFFECT_FORM}{help_}")
    return ids


def effect_sentence(effect: str) -> str:
    """EFFECT as the protocol's Limitation line opens with it."""
    ids = effect_ids(effect)
    if not ids:
        return "the verdicts stand, read within this limit"
    return f"{', '.join(ids)} not assessable with this run"


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


#: how every Limitation line's label opens
LIMIT_PREFIX = "Limitation (audit "


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


def limit_label(record: Record, n: int) -> str:
    """The protocol label that carries finding N of RECORD as a limit."""
    return f"{LIMIT_PREFIX}{record.path.stem} #{n})"


#: the Limitation line's opening for a `stands` a decision review did not
#: confirm: it claims neither that the verdicts stand nor that they fall
UNCONFIRMED = "a limit proposed, not confirmed by a second auditor — unresolved"


def limit_line(finding: Finding, *, contested: bool) -> str:
    """The value of a Limitation line: FINDING's effect, then the person's reason
    (`limit_label` is the label beside it). CONTESTED: a decision review of
    the decision as it stands said other than `upheld`
    (`reviews.contested`) — the line then opens with UNCONFIRMED in place
    of the effect."""
    reason = " ".join(finding.reason.split())
    opening = UNCONFIRMED if contested else effect_sentence(finding.effect)
    return f"{opening} — {reason}"


def answer_note(limits: list[tuple[str, str]]) -> str:
    """What the Recorded results line says of LIMITS, (label, effect) each:
    one note counting them; the Limitation lines below carry each one whole, and
    which promise one leaves not assessable stands in the line's verdicts
    (`result_render.verdicts`). Empty for no limits. One note for all, so
    the line does not grow a "read within" tail per limit."""
    if not limits:
        return ""
    n = len(limits)
    return f"; subject to {n} recorded limitation{'s' if n > 1 else ''} (the Limitation lines below)"


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


def false_positive_blocker(f: Finding) -> bool:
    """Is F a BLOCKER decided `false-positive`? It owes a decision review
    before the number leaves: the deciding agent's own decision would
    otherwise release a blocking finding, and a second auditor judges
    whether it does not apply to the code and run as audited. A WARNING's
    owes none (its missing review warns). The one rule the gate
    (`report_decisions.review_findings`) and the review
    (`decision_review.reviewable`) both read."""
    return f.grade == BLOCKER and f.status == FALSE_POSITIVE


def fixed_claim(f: Finding) -> bool:
    """Is F a BLOCKER decided `fixed` whose place is a protocol's Conclusion
    (`<PROTOCOL-…>.md:Conclusion`, `Finding.place`)? The claim is written
    after the audit and is not in the state an analysis record binds, so no
    follow-up audit is shown such a repair (`followup.earlier_blockers`); a
    decision review judges the Conclusion as it stands and binds it
    (`reviews.claim_digest`). The one rule the gate
    (`report_decisions.review_findings`), the review
    (`decision_review.reviewable`), the follow-up (`followup.release_holds`)
    and the decision's line (`audit_decisions.repair_hint`) read, so a
    Conclusion BLOCKER decided `fixed` has a release."""
    at = f.place
    return (
        f.grade == BLOCKER
        and f.status == FIXED
        and at is not None
        and is_protocol_name(at[0])
        and field_name(at[1]) == field_name(CONCLUSION_LABEL)
    )


def carried_and_closed(f: Finding) -> bool:
    """Is F a carried finding (`carries`: a follow-up did not find its fault
    gone) closed `false-positive` (CARRIED_CLOSING)? Such a
    decision owes a decision review before the number leaves — the one rule
    the gate (`report_decisions.followup_findings`) and the review
    (`decision_review.reviewable`) both read."""
    return bool(f.carries) and f.status in CARRIED_CLOSING


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


def create_file(folder: Path, name: str, suffix: str, text: str) -> Path:
    """Write TEXT to `FOLDER/<name><suffix>`, else `<name>-2<suffix>`, … —
    the first name no file holds, taken by exclusive create, so two audits
    finishing in one minute get two files: a check for a free name before
    a plain write would let both take the same one. Creates FOLDER."""
    folder.mkdir(exist_ok=True)
    n = 1
    while True:
        path = folder / f"{name}{'' if n == 1 else f'-{n}'}{suffix}"
        try:
            with path.open("x", encoding="utf-8") as f:
                f.write(text)
        except FileExistsError:
            n += 1
            continue
        return path


#: the minute as `runs.name_minute` writes it, read off its format: four
#: digits for the year, two for every other field
_NAME_MINUTE_SHAPE = re.sub(
    r"%[YmdHM]",
    lambda field: r"\d{4}" if field.group() == "%Y" else r"\d{2}",
    re.escape(NAME_MINUTE),
)
#: the words of the mode's place, the longer first: `claim-review` ends in
#: `review`
_WRITTEN_WORDS = "|".join(
    re.escape(word) for word in (*MODES, CLAIM_REVIEW_WORD, REVIEW_WORD)
)
#: the name `create_file` gives a record, a failed attempt or a review (a
#: decision review, a report review, a claim review under `report-reviews/`):
#: `<minute>-<mode>[-<n>]` and its suffix, n counting the files of one minute
_WRITTEN_NAME = re.compile(
    rf"^({_NAME_MINUTE_SHAPE})-(?P<mode>{_WRITTEN_WORDS})(?:-(?P<n>\d+))?"
    rf"(?P<failed>{re.escape(FAILED_SUFFIX)})?(?(failed)|\.toml)$"
)


def written_order(path: Path) -> tuple[str, int, str]:
    """The sort key of a file `create_file` wrote, oldest first: its minute, then
    its number within the minute as a number — by name, `-2` and `-3`
    would sort before the minute's first file. Raises FindingsError for a name of
    another shape: its age cannot be told."""
    m = _WRITTEN_NAME.match(path.name)
    if m is None:
        raise FindingsError(
            f"{path}: not a name labkit-audit writes (<minute>-<mode>[-<n>].toml) "
            f"— its place among the records cannot be told; rename or move it"
        )
    return (m.group(1), int(m.group("n") or 1), path.name)


def is_record_name(name: str) -> bool:
    """Whether a file directly in `audits/` named NAME is a record of
    findings: TOML, neither a failed attempt nor a decision review."""
    return (
        name.endswith(".toml")
        and not name.endswith(FAILED_SUFFIX)
        and not REVIEW_NAME.search(name)
    )


def names_preflight_record(name: str) -> bool:
    """Does NAME read as a preflight record's file name — the name
    `create_file` gave it under audits/ (`<minute>-preflight[-n].toml`),
    not a failed attempt's?"""
    m = _WRITTEN_NAME.match(name)
    return (
        m is not None and m.group("mode") == PREFLIGHT_AUDIT and not m.group("failed")
    )


def decide_way(
    area: Path, open_finding: OpenFinding, protocol: Path | None = None
) -> str:
    """The way out of OPEN_FINDING, an audit finding nobody decided in AREA:
    its `--decide` command (`commands.decide_command`, STATUS and the reason
    left for the person), and for a BLOCKER the `--findings` command that
    prints the ways out by cause beside it — the fix the gates that hold an
    undecided finding name."""
    cmd = decide_command(
        area,
        open_finding.number,
        "STATUS",
        "<why>",
        open_finding.record.path.name,
        protocol=protocol,
    )
    allowed = " / ".join(allowed_decisions(open_finding.finding))
    way = f"decide it ({allowed}): `{cmd}`"
    if open_finding.grade != BLOCKER:
        return way
    return (
        f"{way} — `{audit_command(area, '--findings', protocol=protocol)}` "
        f"prints the ways out of a BLOCKER by its cause"
    )


def decide_ways(area: Path, record: Record) -> str:
    """The ways out of RECORD's open findings in AREA, one `decide_way` per
    finding, joined by "; " — the fix of a record whose findings are still
    open."""
    return "; ".join(decide_way(area, OpenFinding(record, f)) for f in record.open)
