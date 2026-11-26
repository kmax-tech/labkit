"""finding_decisions — which decisions a finding allows, what a decided
status entails and owes, the digest a review binds to, and the command that
decides an open finding.

Which status a finding can take rests on the subject its auditor named
(`subject_refusal`, `allowed_decisions`, `decision_after_restore`); what the
status then entails is worded for the person (`decision_entails`). A decided
finding can owe a decision review before its number leaves
(`false_positive_blocker`, `fixed_claim`, `carried_and_closed`). Reviews and
fix verdicts bind to a decision by `decision_digest`; `corrected_field` names
the protocol field a `fixed` finding corrects in place. `decide_way` is the
`--decide` command of an open finding.
"""

from __future__ import annotations

from pathlib import Path

from labkit.formats import decision_history
from labkit.formats.commands import audit_command, decide_command
from labkit.formats.digests import digest
from labkit.formats.gate import BLOCKER
from labkit.formats.protocol_check import (
    field_or_none,
)
from labkit.formats.protocol_fields import CONCLUSION_LABEL, field_name
from labkit.formats.protocol_history import correctable
from labkit.formats.repo import is_protocol_name
from labkit.formats.runs import as_stored
from labkit.formats.finding_limits import EFFECT_STANDS
from labkit.formats.finding_line import IMPLEMENTATION, STATEMENT, UNDETERMINED
from labkit.formats.findings import (
    CARRIED_CLOSING,
    DECIDED,
    FALSE_POSITIVE,
    FIXED,
    Finding,
    LIMITATION,
    OPEN,
    OpenFinding,
    Record,
    STATUSES,
)
from labkit.formats.required_check import REQUEST_CHECKS, check_order


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
    bind to (`reviews.Decision.decision_sha`, `findings.FixVerdict.decision_sha`): a
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
