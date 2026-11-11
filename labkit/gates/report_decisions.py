"""The stations of `report_check` that hold a reported number to the audit
decisions behind it: the generated Recorded results and Limitation lines
(`limit_gaps`), the decision reviews of `stands` limits and of closing
decisions a review once did not uphold (`review_findings`), and the
follow-up of earlier decided BLOCKERs (`followup_findings`).

The three stations read the covering records and compose; each condition
they hold is a pure check below them (`check_*`: records, reviews and the
protocol text in, findings out), tested from data in
`tests/test_rules_report_decisions.py`. A check builds no command of its
own: a printed `labkit-audit` line depends on the protocols the area holds
(`commands.audit_command` lists them), so the station hands the way out in as a
callable, and it is built only when a finding names it.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from labkit.formats.gate import TECHNICAL_RULE
from labkit.formats.gate import GUARANTEED
from labkit.formats.gate import (
    BLOCKER,
    GateFinding,
    WARNING,
    blocker,
    cited_rule,
    outcome_of_failed_read,
)
from labkit.formats import (
    findings,
    followup,
    protocol_block,
    reviews,
    runs,
)
from labkit.checks.audit_binding import (
    AuditError,
    check_evidence,
    covering_analysis,
    dependency_pieces,
)
from labkit.checks.result_render import render_gaps, rendering
from labkit.formats.protocol_check import conclusion_written
from labkit.formats.commands import (
    Command,
    audit_command,
    decide_command,
    render_command,
)
from labkit.formats.evidence import AreaEvidence
from labkit.gates.report_context import Checked

#: the rule of a decision that does not release yet: a limitation carries
#: its effect on the verdicts, and a decision that releases a BLOCKER is
#: confirmed by a second auditor or judged by the follow-up analysis audit
LAB_015 = cited_rule("LAB-015 Preflight audit before freezing")


def limit_gaps(ctx: Checked) -> list[GateFinding]:
    """The generated results and limits: every BLOCKER decided `limitation` of the covering analysis
    records has its effect decided, and the result section says exactly
    what those records and the run render (`result_render.render_gaps`):
    the Recorded results line with its note, one Limitation line per decided limitation, none
    that no record decides. Exact in what it holds — equality with the
    rendering — and silent on whether a limit is enough: that is the
    audit's question. Empty when no covering record exists
    (`report_check.analysis_audit_gap` names that), and the rendering is not owed while
    the head declares no result."""
    if ctx.run is None:
        return []
    try:
        records = covering_analysis(ctx.area, ctx.text, ctx.run)
    except (AuditError, FileNotFoundError, ValueError):
        return []
    gaps: list[GateFinding] = []
    for r in records:
        gaps += check_limit_effects_decided(r, decide_again=_decide_again(ctx, r))
    if ctx.declared is None:
        return gaps  # nothing reported: the result section is not owed yet
    try:
        expected = rendering(ctx.area, ctx.text, ctx.run)
    except (OSError, ValueError) as exc:
        return gaps + [
            blocker(
                f"the result cannot be rendered from {ctx.run.name}: {exc}",
                fix=f"repair what the sentence names, then "
                f"`{render_command(ctx.protocol)}` writes the result section",
                check_outcome=outcome_of_failed_read(exc),
                rule=TECHNICAL_RULE,
            )
        ]
    return gaps + render_gaps(ctx.text, expected)


def review_findings(ctx: Checked) -> list[GateFinding]:
    """The decision reviews: every `stands` among the limits of the
    covering analysis records is upheld by a decision review
    (`reviews.upholding`: a review of that record, its code and its run as
    shown, under the claim the protocol makes now, of the decision as it
    stands now, every draw saying `upheld`). The grade follows the
    finding's: a BLOCKER limitation's `stands` no review upholds — never
    reviewed, rejected, insufficient, contested, or reviewed as another
    decision or claim — is a BLOCKER (a severe finding is not settled by
    a reason alone), a
    WARNING limitation's a WARNING (not every lesser limit owes a second
    auditor; LAB-015 Preflight audit before freezing, "By risk"). A finding a review of the record once did not
    uphold (`reviews.once_not_upheld`) and that is now `false-positive`, `fixed`
    (`findings.CLOSING`) is held the same way until a review
    upholds the new decision: closing it is not settling it. A BLOCKER decided `false-positive`
    (`check_first_dismissals_upheld`) and one on the Conclusion decided `fixed`
    (`check_repaired_claims_upheld`) are held as well. Empty when no record covers the run
    (`report_check.analysis_audit_gap` names that), and silent on whether the verdict is
    right: that is the reviewer's judgement."""
    if ctx.run is None:
        return []
    try:
        records = covering_analysis(ctx.area, ctx.text, ctx.run)
    except (AuditError, FileNotFoundError, ValueError):
        return []  # ValueError: FindingsError — analysis_audit_gap names them
    # an unread review is named, and the decisions are judged as unreviewed:
    # a file nobody can read must not hide a BLOCKER's unupheld `stands`
    out = check_decision_reviews_read(ctx.evidence)
    found = list(ctx.evidence.reviews)
    for r in records:
        step = partial(_review_step, ctx, r)
        out += check_stands_upheld(r, found, text=ctx.text, review_way=step)
        out += check_contested_closings_upheld(r, found, text=ctx.text, review_way=step)
        out += check_first_dismissals_upheld(r, found, text=ctx.text, review_way=step)
        out += check_repaired_claims_upheld(r, found, text=ctx.text, review_way=step)
    return out


def followup_findings(ctx: Checked) -> list[GateFinding]:
    """The follow-up of earlier decided BLOCKERs (`followup.release_holds`): each
    one not released by a valid `resolved` of the state reported now, and a
    BLOCKER `fixed` in that state itself, is a BLOCKER naming the missing
    step. A carried finding (`carries`) closed in a covering record as
    `false-positive` is held until a decision review of that
    record upholds the new decision — the follow-up did not find the fault
    gone, so closing it is not settling it (the rule of
    `reviews.once_not_upheld`, for a verdict of the follow-up). A chain
    that does not read is a BLOCKER. Without a covering record no
    follow-up saw any earlier decided BLOCKER: one whose only missing step
    is the follow-up audit is not held here, since the missing analysis
    audit (`report_check.analysis_audit_gap`) is that one cause's blocker;
    one that also owes a required check in the run is held. Empty without an
    answering run, or when the covering records or the area's records do
    not read (`report_check.analysis_audit_gap` names those); silent on whether a verdict
    is right: that is the auditor's judgement."""
    if ctx.run is None:
        return []
    try:
        covering = covering_analysis(ctx.area, ctx.text, ctx.run)
        records = followup.protocol_records(ctx.area, protocol_block.head(ctx.text).id)
    except (AuditError, FileNotFoundError, ValueError):
        return []  # analysis_audit_gap names them
    try:
        metrics: dict | None = runs.read_metrics(runs.metrics_path(ctx.run))
    except (OSError, ValueError):
        metrics = None
    evidence = check_evidence(metrics, dependency_pieces(ctx.run))
    try:
        out = check_earlier_blockers_released(records, covering, evidence)
    except findings.FindingsError as exc:
        return [
            blocker(
                f"the carried findings of {ctx.area.name} do not form a chain: {exc}",
                fix=findings.record_way(ctx.area, ctx.protocol),
                rule=TECHNICAL_RULE,
            )
        ]
    # review_findings names a file that does not read; unreviewed holds here
    found = list(ctx.evidence.reviews)
    for r in covering:
        out += check_carried_closings_upheld(
            r, found, text=ctx.text, review_way=partial(_review_step, ctx, r)
        )
    return out


def check_limit_effects_decided(
    record: findings.Record, *, decide_again: Callable[[int], Command]
) -> list[GateFinding]:
    """Every BLOCKER of RECORD decided `limitation` has its effect on the
    verdicts decided (`Record.limits`): one without is a BLOCKER — a record
    changed by hand, since `--decide … limitation` writes the effect.

    Args:
        record: One covering analysis record.
        decide_again: The `--decide` command for finding N of RECORD, as
            the station spells it.
    """
    return [
        blocker(
            f"{findings.limit_label(record, n)}: a BLOCKER decided limitation "
            "owes its effect on the verdicts",
            fix=f"decide it again: `{decide_again(n)}`",
            rule=LAB_015,
        )
        for n, f in record.limits()
        if not f.effect
    ]


def check_decision_reviews_read(evidence: AreaEvidence) -> list[GateFinding]:
    """The area's decision reviews read: a file that does not
    (`AreaEvidence.reviews_unread`) is a WARNING naming why. It releases
    nothing — EVIDENCE then holds no review, so every decision is judged as
    unreviewed. That a file reads is its format's condition, not the
    standard's (TECHNICAL_RULE)."""
    if not evidence.reviews_unread:
        return []
    return [
        GateFinding(
            WARNING,
            f"a review nobody can read: {evidence.reviews_unread}",
            evidence_kind=GUARANTEED,
            rule=TECHNICAL_RULE,
        )
    ]


def check_stands_upheld(
    record: findings.Record,
    found: list[reviews.Review],
    *,
    text: str,
    review_way: Callable[[], str],
) -> list[GateFinding]:
    """Every limit of RECORD whose effect is `stands` is upheld by a decision
    review among FOUND, as decided now and under the claim TEXT makes now
    (`reviews.upholding`). One that is not is held at the finding's grade:
    a BLOCKER limitation blocks, a WARNING limitation warns (LAB-015
    Preflight audit before freezing, "By risk").

    Args:
        record: One covering analysis record.
        found: The area's decision reviews, oldest first.
        text: The protocol text; its Conclusion is the claim reviewed.
        review_way: Gives the way to the decision review of RECORD, as the
            station spells it (`_review_step`); called per finding held.
    """
    return [
        GateFinding(
            BLOCKER if f.grade == BLOCKER else WARNING,
            f"{findings.limit_label(record, n)}: `stands` on a {f.grade} decided limitation "
            f"{reviews.state(record, n, found, text)} — no decision review "
            f"upholds that the reported claim stands within this limit "
            f"(LAB-015 Preflight audit before freezing)",
            fix=f"{review_way()} asks a second auditor (owed at "
            f"every repeat cost); after a rejection, decide again",
            evidence_kind=GUARANTEED,
            rule=LAB_015,
        )
        for n, f in record.limits()
        if f.effect == findings.EFFECT_STANDS
        and not reviews.upholding(record, n, found, text)
    ]


def check_contested_closings_upheld(
    record: findings.Record,
    found: list[reviews.Review],
    *,
    text: str,
    review_way: Callable[[], str],
) -> list[GateFinding]:
    """Every finding of RECORD that a review among FOUND once did not uphold
    (`reviews.once_not_upheld`) and that is now `false-positive` or `fixed`
    (`findings.CLOSING`) is upheld as decided now (`reviews.upholding`):
    closing a contested finding is not settling it. One that is not is held
    at the finding's grade. FOUND, TEXT and REVIEW_WAY as
    `check_stands_upheld` takes them."""
    out: list[GateFinding] = []
    for n, f in enumerate(record.findings, 1):
        if f.status not in findings.CLOSING:
            continue
        was = reviews.once_not_upheld(record, n, found)
        if was is None or reviews.upholding(record, n, found, text):
            continue
        out.append(
            GateFinding(
                BLOCKER if f.grade == BLOCKER else WARNING,
                f"audit {record.path.stem} #{n}: `{f.status}` on a {f.grade} a "
                f"review said {was.verdict} on ({was.why}) — closing a finding "
                f"a reviewer did not uphold settles nothing by itself; the new "
                f"decision is {reviews.state(record, n, found, text)} "
                f"(LAB-015 Preflight audit before freezing)",
                fix=f"{review_way()} asks a second auditor whether the "
                f"reason shows it {_closing_question(f.status)}",
                evidence_kind=GUARANTEED,
                rule=LAB_015,
            )
        )
    return out


def check_repaired_claims_upheld(
    record: findings.Record,
    found: list[reviews.Review],
    *,
    text: str,
    review_way: Callable[[], str],
) -> list[GateFinding]:
    """Every BLOCKER of RECORD on the Conclusion decided `fixed`
    (`findings.fixed_claim`) is upheld by a review among FOUND for the claim
    as it stands — else a BLOCKER: no follow-up audit is shown a repaired
    claim, so the decision review judges it. One a review once did not
    uphold is `check_contested_closings_upheld`'s; each is held once. FOUND,
    TEXT and REVIEW_WAY as `check_stands_upheld` takes them."""
    out: list[GateFinding] = []
    for n, f in enumerate(record.findings, 1):
        if (
            not findings.fixed_claim(f)
            or reviews.once_not_upheld(record, n, found) is not None
            or reviews.upholding(record, n, found, text)
        ):
            continue
        out.append(
            GateFinding(
                BLOCKER,
                f"audit {record.path.stem} #{n}: `fixed` on a BLOCKER on the Conclusion "
                f"{reviews.state(record, n, found, text)} — no follow-up audit is "
                f"shown a repaired claim; a second auditor judges the Conclusion as "
                f"it stands (LAB-015 Preflight audit before freezing)",
                fix=f"{review_way()} asks a second auditor whether the "
                f"Conclusion as it stands no longer makes the claim the finding "
                f"names; no new measurement and no analysis audit",
                evidence_kind=GUARANTEED,
                rule=LAB_015,
            )
        )
    return out


def check_first_dismissals_upheld(
    record: findings.Record,
    found: list[reviews.Review],
    *,
    text: str,
    review_way: Callable[[], str],
) -> list[GateFinding]:
    """Every BLOCKER of RECORD decided `false-positive`
    (`findings.false_positive_blocker`) is upheld by a review among FOUND —
    else a BLOCKER: the deciding agent's own decision would release a
    blocking finding. A carried one is `check_carried_closings_upheld`'s,
    one a review once did not uphold `check_contested_closings_upheld`'s;
    each is held once. FOUND, TEXT and REVIEW_WAY as `check_stands_upheld`
    takes them."""
    out: list[GateFinding] = []
    for n, f in enumerate(record.findings, 1):
        if (
            not findings.false_positive_blocker(f)
            or f.carries
            or reviews.once_not_upheld(record, n, found) is not None
            or reviews.upholding(record, n, found, text)
        ):
            continue
        out.append(
            GateFinding(
                BLOCKER,
                f"audit {record.path.stem} #{n}: `false-positive` on a BLOCKER "
                f"{reviews.state(record, n, found, text)} — a blocking finding is not "
                f"released by the deciding agent's own decision (LAB-015 Preflight "
                f"audit before freezing)",
                fix=f"{review_way()} asks a second auditor whether the reason "
                f"shows it {_closing_question('false-positive')}",
                evidence_kind=GUARANTEED,
                rule=LAB_015,
            )
        )
    return out


def check_earlier_blockers_released(
    records: list[findings.Record],
    covering: list[findings.Record],
    evidence: dict | None,
) -> list[GateFinding]:
    """Every earlier decided BLOCKER is released for the state reported now
    (`followup.release_holds` over RECORDS and COVERING as it takes them,
    with EVIDENCE as its metrics — where a required check is looked up, the
    run's metrics and the files shown, `audit_binding.check_evidence`):
    each hold is a BLOCKER naming the missing step. With no
    covering record, a hold whose only missing step is the follow-up audit
    is left out — the missing analysis audit is that one cause's blocker
    (`report_check.analysis_audit_gap`), named once and not once per earlier
    BLOCKER. Raises FindingsError when the carried findings of RECORDS do
    not form a chain (`followup.chain`)."""
    return [
        blocker(
            f"audit {h.ref}: {h.why} (LAB-015 Preflight audit before freezing)",
            fix=h.step,
            rule=LAB_015,
        )
        for h in followup.release_holds(records, covering, evidence)
        if covering or h.step != followup.STEP_AUDIT
    ]


def check_carried_closings_upheld(
    record: findings.Record,
    found: list[reviews.Review],
    *,
    text: str,
    review_way: Callable[[], str],
) -> list[GateFinding]:
    """Every carried finding of RECORD closed `false-positive`
    (`findings.carried_and_closed`) is upheld by a review among FOUND as
    decided now — else a BLOCKER: the follow-up did not find the fault
    gone, so closing it is not settling it. FOUND, TEXT and REVIEW_WAY as
    `check_stands_upheld` takes them."""
    return [
        blocker(
            f"audit {record.path.stem} #{n}: a carried finding (from {f.carries}) "
            f"`{f.status}` — the follow-up did not find the fault gone, so "
            f"closing it settles nothing by itself "
            f"(LAB-015 Preflight audit before freezing)",
            fix=f"{review_way()} asks a second auditor whether "
            f"the reason shows it {_closing_question(f.status)}",
            rule=LAB_015,
        )
        for n, f in enumerate(record.findings, 1)
        if findings.carried_and_closed(f)
        and not reviews.upholding(record, n, found, text)
    ]


def _decide_again(ctx: Checked, record: findings.Record) -> Callable[[int], Command]:
    """The `--decide` command that decides finding N of RECORD as a
    limitation again, with the area as seen from here
    (`check_limit_effects_decided` prints it)."""

    def command(n: int) -> Command:
        return decide_command(
            ctx.area, n, "limitation", "<why>", record.path.name, protocol=ctx.protocol
        )

    return command


def _review_step(ctx: Checked, record: findings.Record) -> str:
    """The decision review of RECORD as the next step: the whole command
    with the area as seen from here, and — while the protocol's Conclusion
    is unwritten — the step `--review` refuses without (it judges the
    claim), so the step can be followed as printed."""
    command = f"`{audit_command(ctx.area, '--review', '--record', record.path.name, protocol=ctx.protocol)}`"
    if conclusion_written(ctx.text):
        return command
    return (
        f"write the Conclusion in {ctx.protocol.name} first (the review judges "
        f"that claim, and refuses without it), then {command}"
    )


def _closing_question(status: str) -> str:
    """What the reviewer is asked of a closed contested finding, by status."""
    return {
        "false-positive": "does not apply to the code and run as audited",
        "fixed": "gone in the files as audited",
    }[status]
