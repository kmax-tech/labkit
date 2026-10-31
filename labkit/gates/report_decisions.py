"""The stations of `report_check` that hold a reported number to the audit
decisions behind it: the generated Recorded results and Limitation lines
(`limit_gaps`), the decision reviews of `stands` limits and of closing
decisions a review once did not uphold (`review_findings`), and the
follow-up of earlier decided BLOCKERs (`followup_findings`).
"""

from __future__ import annotations


import shlex
from pathlib import Path

from labkit.formats.gate import GUARANTEED
from labkit.formats.gate import (
    BLOCKER,
    WARNING,
    GateFinding,
    blocker,
)
from labkit.formats import (
    findings,
    followup,
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
from labkit.formats.repo import (
    area_protocols,
    audit_command,
    decide_command,
    shown,
)
from labkit.gates.report_context import Checked


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
        for n, f in r.limits():
            if not f.effect:
                # a record changed by hand: `--decide … limit` writes the effect
                gaps.append(
                    blocker(
                        f"{findings.limit_label(r, n)}: a BLOCKER decided limitation "
                        "owes its effect on the verdicts",
                        fix="decide it again: `"
                        + decide_command(
                            ctx.area,
                            n,
                            "limitation",
                            "<why>",
                            r.path.name,
                            protocol=ctx.protocol,
                        )
                        + "`",
                    )
                )
    if ctx.declared is None:
        return gaps  # nothing reported: the result section is not owed yet
    try:
        expected = rendering(ctx.area, ctx.text, ctx.run)
    except (OSError, ValueError) as exc:
        return gaps + [
            blocker(
                f"the result cannot be rendered from {ctx.run.name}: {exc}",
                fix=f"repair what the sentence names, then "
                f"`protocol-fill {shlex.quote(shown(ctx.protocol, Path.cwd()))} "
                f"--render` writes the result section",
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
    a reason alone; decided 2026-10-22 after the fifth round's replay and
    the assessment of its fifteen decisions from their sources), an
    accepted WARNING's a WARNING for now (the release does not yet hang
    on every lesser limit). A finding a review of the record once did not
    uphold (`reviews.once_not_upheld`) and that is now `false-positive`, `fixed`
    (`findings.CLOSING`) is held the same way until a review
    upholds the new decision: closing it is not settling it (sixth haiku
    round, 2026-10-23, t5). Empty when no record covers the run
    (`report_check.analysis_audit_gap` names that), and silent on whether the verdict is
    right: that is the reviewer's judgement."""
    if ctx.run is None:
        return []
    try:
        records = covering_analysis(ctx.area, ctx.text, ctx.run)
    except (AuditError, FileNotFoundError, ValueError):
        return []  # ValueError: FindingsError — analysis_audit_gap names them
    out: list[GateFinding] = []
    try:
        found = reviews.area_reviews(ctx.area)
    except reviews.ReviewError as exc:
        # named, and the decisions are judged as unreviewed: a file nobody
        # can read must not hide a BLOCKER's unupheld `stands`
        out.append(
            GateFinding(
                WARNING, f"a review nobody can read: {exc}", evidence_kind=GUARANTEED
            )
        )
        found = []
    for r in records:
        for n, f in r.limits():
            if f.effect != findings.EFFECT_STANDS or reviews.upholding(
                r, n, found, ctx.text
            ):
                continue
            out.append(
                GateFinding(
                    BLOCKER if f.grade == "BLOCKER" else WARNING,
                    f"{findings.limit_label(r, n)}: `stands` on a {f.grade} decided limitation "
                    f"{reviews.state(r, n, found, ctx.text)} — no decision review "
                    f"upholds that the reported claim stands within this limit "
                    f"(LAB-015 Preflight audit before freezing)",
                    fix=f"{_review_step(ctx, r)} asks a second auditor (owed at "
                    f"every repeat cost); after a rejection, decide again",
                    evidence_kind=GUARANTEED,
                )
            )
        for n, f in enumerate(r.findings, 1):
            if f.status not in findings.CLOSING:
                continue
            was = reviews.once_not_upheld(r, n, found)
            if was is None or reviews.upholding(r, n, found, ctx.text):
                continue
            out.append(
                GateFinding(
                    BLOCKER if f.grade == "BLOCKER" else WARNING,
                    f"audit {r.path.stem} #{n}: `{f.status}` on a {f.grade} a "
                    f"review said {was.verdict} on ({was.why}) — closing a finding "
                    f"a reviewer did not uphold settles nothing by itself; the new "
                    f"decision is {reviews.state(r, n, found, ctx.text)} "
                    f"(LAB-015 Preflight audit before freezing)",
                    fix=f"{_review_step(ctx, r)} asks a second auditor whether the "
                    f"reason shows it {_closing_question(f.status)}",
                    evidence_kind=GUARANTEED,
                )
            )
        out += first_dismissals(ctx, r, found)
    return out


def first_dismissals(
    ctx: Checked, r: findings.Record, found: list[reviews.Review]
) -> list[GateFinding]:
    """A BLOCKER of record R decided `false-positive` (`findings.false_positive_blocker`)
    that no review among FOUND upholds — held as a BLOCKER: the deciding
    agent's own decision would release a blocking finding. A carried one is
    the follow-up's (`followup_findings`), one a review once did not uphold
    the closing rule's (`review_findings`); each is held once."""
    out: list[GateFinding] = []
    for n, f in enumerate(r.findings, 1):
        if (
            not findings.false_positive_blocker(f)
            or f.carries
            or reviews.once_not_upheld(r, n, found) is not None
            or reviews.upholding(r, n, found, ctx.text)
        ):
            continue
        out.append(
            GateFinding(
                BLOCKER,
                f"audit {r.path.stem} #{n}: `false-positive` on a BLOCKER "
                f"{reviews.state(r, n, found, ctx.text)} — a blocking finding is not "
                f"released by the deciding agent's own decision (LAB-015 Preflight "
                f"audit before freezing)",
                fix=f"{_review_step(ctx, r)} asks a second auditor whether the reason "
                f"shows it {_closing_question('false-positive')}",
                evidence_kind=GUARANTEED,
            )
        )
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
    that does not read is a BLOCKER. Without a covering record every
    earlier decided BLOCKER is held — no follow-up saw it. Empty without an
    answering run, or when the covering records or the area's records do
    not read (`report_check.analysis_audit_gap` names those); silent on whether a verdict
    is right: that is the auditor's judgement. Why: the fixed-followup
    pilots, 2026-10-26."""
    if ctx.run is None:
        return []
    try:
        covering = covering_analysis(ctx.area, ctx.text, ctx.run)
        records = findings.area_records(ctx.area)
    except (AuditError, FileNotFoundError, ValueError):
        return []  # analysis_audit_gap names them
    try:
        metrics: dict | None = runs.read_metrics(runs.metrics_path(ctx.run))
    except (OSError, ValueError):
        metrics = None
    evidence = check_evidence(metrics, dependency_pieces(ctx.run))
    try:
        held = followup.release_holds(records, covering, evidence)
    except findings.FindingsError as exc:
        return [
            blocker(
                f"the carried findings of {ctx.area.name} do not form a chain: {exc}",
                fix=findings.record_way(ctx.area, ctx.protocol),
            )
        ]
    # the follow-up refuses an area with several protocols (`audit_prompt.earlier_of`):
    # no step there may name it
    several = len(area_protocols(ctx.area)) > 1
    out = [
        blocker(
            f"audit {h.ref}: {h.why} (LAB-015 Preflight audit before freezing)",
            fix=followup.STEP_NONE_SEVERAL
            if several and h.needs_followup_audit
            else h.step,
        )
        for h in held
    ]
    try:
        found = reviews.area_reviews(ctx.area)
    except reviews.ReviewError:
        found = []  # review_findings names the file; unreviewed holds here
    for r in covering:
        for n, f in enumerate(r.findings, 1):
            if findings.carried_and_closed(f) and not reviews.upholding(
                r, n, found, ctx.text
            ):
                out.append(
                    blocker(
                        f"audit {r.path.stem} #{n}: a carried finding (from {f.carries}) "
                        f"`{f.status}` — the follow-up did not find the fault gone, so "
                        f"closing it settles nothing by itself "
                        f"(LAB-015 Preflight audit before freezing)",
                        fix=f"{_review_step(ctx, r)} asks a second auditor whether "
                        f"the reason shows it {_closing_question(f.status)}",
                    )
                )
    return out


def _review_step(ctx: Checked, record: findings.Record) -> str:
    """The decision review of RECORD as the next step: the whole command
    with the area as seen from here, and — while the protocol's Conclusion
    is unwritten — the step `--review` refuses without (it judges the
    claim). A refusal naming `<area>` and no precondition was not followed
    (ninth haiku round, t3)."""
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
