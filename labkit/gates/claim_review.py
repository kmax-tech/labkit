"""claim_review — the person's decision on a report review's claim, and a
second, cold reviewer on that decision.

    labkit-audit <AREA> --report-review REPORT --decide N false-positive
                 --why REASON [--record FILE] [--protocol FILE]
    labkit-audit <AREA> --review --record <report review file> [--again]
                 [--protocol FILE] [--model ALIAS] [--timeout S] [--out FILE]

A report review's claim holds the report's state (`report_reviews.standing`).
A true claim is answered by changing the report or a source the reviewer
read. A false one — the reviewer misread: the line stands inside a
discussion block, the number is the adopted one, the statement agrees
with the record — is decided `false-positive`, the counter-evidence as
its reason (`decide_claim`, stored by `report_reviews.write_claim_decision`
in the review record itself). `limitation` and `fixed` are refused
(`report_reviews.claim_refusal`). The decision is taken on the state the
record saw: a record that read another state covers nothing any more,
and deciding on it is refused.

The decision alone releases nothing (LAB-015 Preflight audit before
freezing: a decision that releases a BLOCKER is confirmed by a second
auditor). `review_claims` hands a cold reviewer, in one call, every claim
of the record decided `false-positive` and not yet upheld — the claim,
its line, the reason — and the inputs the first reviewer saw
(`report_review.gather_report`, held to the record's fingerprint).
Instructions: `claim-review.agent.md`. Its verdicts are written beside
the review (`audits/report-reviews/<minute>-claim-review.toml`), bound to
the record, the state and each decision as it stood
(`report_reviews.claim_decision_digest`). Only `upheld` releases. After
`rejected` or `insufficient` no further draw releases the same decision:
the command refuses one unless asked with `--again`, whose verdicts count
and release nothing. The way on is a decision with a revised reason — a
new decision, which owes a confirmation of its own — or the changed
report. The call is an attempt in the area's journal (mode
`report-review-claim`).

Exit codes of the review: 0 every decision reviewed is released (or all
were already: nothing to do), 1 at least one is held, 2 no review — the
record does not read, saw another state, holds no decided claim, a
decision was already reviewed and not upheld (without `--again`), the
backend did not answer, or a reply whose lines and counts disagree.
Of the decision: 0 stored, 2 refused, the file untouched.
"""

from __future__ import annotations

from pathlib import Path

from labkit.checks.audit_binding import AuditError
from labkit.checks.report_review_inputs import review_keys
from labkit.formats import attempts, console, evidence, report_reviews
from labkit.formats.commands import (
    claim_decide_command,
    claim_review_command,
    report_review_command,
)
from labkit.formats.prompts import prompt_body
from labkit.formats.repo import given_or_in, layout_root, shown, the_protocol
from labkit.formats.report_reviews import (
    FALSE_POSITIVE,
    ClaimReview,
    ClaimVerdict,
    ReportClaim,
    ReportReview,
    ReportReviewError,
)
from labkit.gates import audit_call, audit_prompt, report_hold, report_review
from labkit.gates.decision_review import parse_review

#: the review's mode: its instructions (`audit_prompt.instructions`)
CLAIM_REVIEW = "claim"
CLAIMS_LABEL = (
    "CLAIMS — the decisions under review: each claim the report's first reader "
    "named and the person decided `false-positive`, with the reason given"
)


def report_review_named(area: Path, record: Path | None) -> Path | None:
    """RECORD as the report review of AREA it names, or None when it names
    none: the path as given when it lies in the area's report-review
    folder, else that folder's file of the bare name given — a review's
    name (`…-review.toml`) is no audit record's, so the name alone tells
    `--review --record` which reviewer is asked. A claim review's own file
    is none. A name that matches no file there is none either: `--review`
    then takes RECORD for an audit record, and its refusal lists the
    records the area holds."""
    if record is None or report_reviews.CLAIM_REVIEW_NAME.search(record.name):
        return None
    where = report_reviews.folder(area)
    path = given_or_in(record, where)
    if path.is_file() and path.resolve().parent == where.resolve():
        return path
    return None


def claim_records(area: Path) -> tuple[list[ReportReview], list[ClaimReview]]:
    """AREA's report reviews and claim reviews from its audit evidence
    read once (`evidence.read_evidence`); raises ReportReviewError with
    the sentence when one does not read, as the reader did."""
    read = evidence.read_evidence(area, staged=False)
    if read.report_reviews_unread:
        raise ReportReviewError(read.report_reviews_unread)
    return list(read.report_reviews), list(read.claim_reviews)


def state_now(area: Path, report: Path, protocol: Path) -> tuple[str, str, str, list]:
    """(report key, protocol key, fingerprint, pieces) of REPORT under
    PROTOCOL as it is now: the keys a review record names
    (`review_keys`), the fingerprint of the inputs a reviewer reads now
    (`report_hold.review_fingerprint`) and those inputs
    (`report_review.gather_report`). Raises as `gather_report` does."""
    _, _, pieces = report_review.gather_report(area, report, protocol)
    whole, _ = report_hold.review_fingerprint(pieces)
    report_key, protocol_key = review_keys(area, report, protocol)
    return report_key, protocol_key, whole, pieces


def held_to_state(
    review: ReportReview,
    report_key: str,
    protocol_key: str,
    whole: str,
    command: str,
) -> None:
    """Refuse (AuditError) REVIEW when it is no review of REPORT_KEY under
    PROTOCOL_KEY, or read another state than WHOLE: its claims then hold
    nothing, and a decision or a confirmation on it would release
    nothing. COMMAND reviews the state as it is."""
    if (review.report, review.protocol) != (report_key, protocol_key):
        raise AuditError(
            f"{review.path.name} is a review of {review.report} under "
            f"{review.protocol}, not of {report_key} under {protocol_key}",
            fix="name the record of this report (`--record`), or the report and "
            "the protocol the record names",
        )
    if review.fingerprint != whole:
        raise AuditError(
            f"{review.path.name} read another state of {report_key} — the report "
            f"or a source the reviewer read changed since, so its claims hold "
            f"nothing any more and a decision on them releases nothing",
            fix=f"review the state as it is: `{command}`",
        )


def decided_record(
    area: Path, record: Path | None, report_key: str, protocol_key: str, whole: str
) -> Path:
    """The review record a claim decision goes into: RECORD when given
    (`report_review_named`), else the one review of this state — REPORT_KEY
    under PROTOCOL_KEY, fingerprint WHOLE — that names a claim. Raises
    ReportReviewError when RECORD names no report review of AREA, when no
    review of this state names a claim, or when several do (the refusal
    lists them: `--record` chooses)."""
    if record is not None:
        path = report_review_named(area, record)
        if path is None:
            names = sorted(
                p.name
                for p in report_reviews.folder(area).glob("*.toml")
                if not report_reviews.CLAIM_REVIEW_NAME.search(p.name)
            )
            raise ReportReviewError(
                f"{record}: no report review in {report_reviews.folder(area)} — "
                f"it holds " + (", ".join(names) if names else "none")
            )
        return path
    reviews, _ = claim_records(area)
    naming = [
        r
        for r in reviews
        if (r.report, r.protocol, r.fingerprint) == (report_key, protocol_key, whole)
        and r.claims
    ]
    if not naming:
        raise ReportReviewError(
            f"{report_key}: no review of this state names a claim — nothing to decide"
        )
    if len(naming) > 1:
        raise ReportReviewError(
            f"{report_key}: {len(naming)} reviews of this state name claims "
            f"({', '.join(r.path.name for r in naming)}) — choose one with --record"
        )
    return naming[0].path


def decide_claim(
    area: Path,
    report: Path,
    decide: list[str],
    reason: str,
    record: Path | None,
    protocol: Path | None,
) -> int:
    """`--report-review REPORT --decide N STATUS --why REASON`: store the
    person's decision on claim N of RECORD (without it the one review of
    this state that names a claim, `decided_record`) through
    `report_reviews.write_claim_decision`, then print what was written and
    the confirmation it owes. Refused with exit 2, the file untouched: a
    record that is not this report's or read another state
    (`held_to_state`), a status a claim cannot take, a reason owed and
    empty. STATUS `open` is stored too: it takes a decision back, and the
    claim holds the report again. Exit 0 when stored."""
    n_text, status = decide
    try:
        if not n_text.isdigit():
            raise ReportReviewError(f"N must be a claim number, not {n_text!r}")
        chosen = the_protocol(area, protocol)
        report_key, protocol_key, whole, _ = state_now(area, report, chosen)
        path = decided_record(area, record, report_key, protocol_key, whole)
        held_to_state(
            report_reviews.read_report_review(path),
            report_key,
            protocol_key,
            whole,
            report_review_command(area, report, chosen).line,
        )
        after = report_reviews.write_claim_decision(path, int(n_text), status, reason)
    except audit_call.REFUSAL_ERRORS as exc:
        console.refuse("labkit-audit", str(exc).strip(chr(39)))
        return 2
    still_open = sum(1 for c in after.claims if c.status == report_reviews.OPEN)
    print(
        f"decided: {path.name} claim {n_text}: {status}"
        + (f" — {reason.strip()}" if reason.strip() else "")
        + f" · {still_open} open"
    )
    if status == FALSE_POSITIVE:
        print(
            f"  the decision alone releases nothing: a second reviewer confirms "
            f"it — `{claim_review_command(area, path.name, chosen)}` (one model "
            f"call, every decided claim of the record at once); until it is "
            f"upheld the claim holds the report"
        )
    return 0


def claims_text(
    review: ReportReview,
    decided: list[tuple[int, ReportClaim]],
    found: list[ClaimReview],
    report_lines: list[str],
) -> str:
    """The decisions of REVIEW under review, as the second reviewer reads
    them: per claim its number, the report line it cites, kind and the
    first reviewer's sentence, the line's text (REPORT_LINES, the report
    split at its line breaks), the status, the reason, and — for a claim
    decided again after a claim review among FOUND did not uphold an
    earlier decision (`report_reviews.verdict_on_revised_decision`) — that verdict
    with its sentence."""
    blocks: list[str] = []
    for n, c in decided:
        lines = [
            f"#{n} · line {c.line} · {c.kind} · {c.why}",
            f"   the line: {report_lines[c.line - 1]}",
            f"   status: {c.status}",
            f"   reason: {c.reason}",
        ]
        was = report_reviews.verdict_on_revised_decision(review, n, found)
        if was is not None:
            lines.append(
                f"   decided again after a review said {was[1].verdict}: {was[1].why}"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def contested_claim_gap(
    area: Path,
    report: Path,
    protocol: Path,
    review: ReportReview,
    decided: list[tuple[int, ReportClaim]],
    found: list[ClaimReview],
) -> AuditError | None:
    """Why another draw on REVIEW's decisions settles nothing, as the
    refusal to raise, or None: a claim review among FOUND already said
    `rejected` or `insufficient` of a decision among DECIDED as it stands
    (`report_reviews.not_upheld`). The ways on are a decision with a
    revised reason or the changed REPORT, not another call."""
    contested = [n for n, _ in decided if report_reviews.not_upheld(review, n, found)]
    if not contested:
        return None
    again = "; ".join(
        f"`{claim_decide_command(area, report, n, review.path.name, protocol)}`"
        for n in contested
    )
    return AuditError(
        f"{review.path.name}: the decision on claim(s) {', '.join(map(str, contested))} "
        f"was reviewed as it stands and not upheld — another draw settles nothing",
        fix=f"decide again with a revised reason that names the evidence ({again}) "
        f"— a new decision, which a second reviewer judges anew —, or change the "
        f"report or a source the reviewer read and review that state "
        f"(`{report_review_command(area, report, protocol)}`); `--again` draws once "
        f"more: its verdicts count, and it never releases this decision",
    )


def review_claims(
    area: Path,
    protocol: Path | None,
    record: Path,
    model: str,
    timeout: int,
    out: Path | None,
    *,
    again: bool = False,
) -> int:
    """`--review --record <report review>`: 1 read RECORD and hold it to
    the report's state now (`held_to_state`) · 2 the claims decided
    `false-positive` (none: refused) · 3 without AGAIN, draw only on the
    decisions no review judged as they stand: end with 0 when every
    decided claim is upheld already, and refuse the call when all that is
    left was reviewed and not upheld (`contested_claim_gap`) · 4 refuse while the area's
    audit evidence is gone · 5 one call, parse, write the claim review ·
    6 print the draw and, apart, the report's state. With AGAIN every
    decided claim is drawn on once more; the draw counts and releases
    nothing. Exit the decisions': 0 every one reviewed is released
    (`report_reviews.upheld`), 1 not every one, 2 no review."""
    try:
        chosen = the_protocol(area, protocol)
        review = report_reviews.read_report_review(record)  # 1
        report = layout_root(area) / review.report
        if not report.is_file():
            raise AuditError(
                f"{record.name} reviews {review.report}, and no such file is there",
                fix="restore the report, or review the report that replaces it",
            )
        report_key, protocol_key, whole, pieces = state_now(area, report, chosen)
        held_to_state(
            review,
            report_key,
            protocol_key,
            whole,
            report_review_command(area, report, chosen).line,
        )
        _, found = claim_records(area)
        decided = [  # 2
            (n, c)
            for n, c in enumerate(review.claims, start=1)
            if c.status == FALSE_POSITIVE
        ]
        if not decided:
            raise AuditError(
                f"{record.name}: no claim decided `false-positive` — nothing to review",
                fix="a claim the reviewer misread is decided first "
                f"(`{claim_decide_command(area, report, 1, record.name, chosen)}`); "
                "a true one is answered by changing the report",
            )
        if not again:  # 3
            unjudged = [
                (n, c)
                for n, c in decided
                if not report_reviews.upheld(review, n, found)
                and report_reviews.not_upheld(review, n, found) is None
            ]
            contested = contested_claim_gap(
                area, report, chosen, review, decided, found
            )
            if not unjudged and contested is not None:
                raise contested
            decided = unjudged
            if not decided:
                print(
                    f"claim review: every decided claim of {record.name} is upheld "
                    f"— nothing to do"
                )
                return 0
        lost = report_hold.lost_evidence(  # 4
            chosen, evidence.read_evidence(area, staged=False)
        )
        if lost is not None:
            raise AuditError(
                f"no claim review of {record.name} — {lost.cause}", fix=lost.fix
            )
        prompt = claim_prompt(area, review, report, decided, found, pieces)
        numbers = [n for n, _ in decided]
        console.progress(
            "labkit-audit",
            f"claim review · {record.name} · {len(numbers)} decision(s) · "
            f"{model} · {len(prompt) // 1000} kB",
        )
        # journaled like the report review, started on the same fingerprint:
        # a claim review deleted before the commit is named by its attempt
        with audit_call.journaled_answer(  # 5
            area, report_reviews.CLAIM_ATTEMPT_MODE, model, whole, prompt, timeout
        ) as (running, reply):
            lines = parse_review(reply, numbers, subject="claim")
            verdicts = [
                ClaimVerdict(
                    n,
                    report_reviews.claim_decision_digest(review.claims[n - 1]),
                    verdict,
                    why,
                )
                for n, verdict, why in lines
            ]
            written = report_reviews.write_claim_review(
                area,
                model=model,
                record=record.name,
                whole=whole,
                verdicts=verdicts,
                again=again,
            )
            running.end("record", file=attempts.under_audits(area, written))
    except audit_call.REFUSAL_ERRORS as exc:
        console.refuse("labkit-audit", str(exc).strip(chr(39)))
        return 2
    print(reply)  # 6
    if out:
        out.write_text(reply, encoding="utf-8")
    counts = report_reviews.verdict_counts(verdicts)
    print()
    print(
        f"claim review: this draw{' (--again, it releases nothing)' if again else ''} "
        f"— {counts[0]} upheld, {counts[1]} rejected, {counts[2]} insufficient, "
        f"recorded in {shown(written, Path.cwd())}"
    )
    _, found = claim_records(area)
    unreleased = [n for n in numbers if not report_reviews.upheld(review, n, found)]
    print(
        "claim review state: "
        + (
            f"held — the decision on claim(s) {', '.join(map(str, unreleased))} is "
            f"not released"
            if unreleased
            else "every decision reviewed is released"
        )
    )
    standing = report_review.state_after(area, report_key, protocol_key, whole)
    print(
        f"report review state: "
        f"{report_review.state_line(standing, area, report, chosen)}"
    )
    return 1 if unreleased else 0  # the decisions reviewed, not the whole report


def claim_prompt(
    area: Path,
    review: ReportReview,
    report: Path,
    decided: list[tuple[int, ReportClaim]],
    found: list[ClaimReview],
    pieces: list[tuple[str, str]],
) -> str:
    """The second reviewer's prompt: its instructions, the decisions under
    review (`claims_text`), the PIECES the first reviewer read — the
    report with its line numbers, the adopted and the discussed runs, the
    protocol, the runs' metrics, the audit records — and the rules the
    instructions cite."""
    repo = layout_root(area)
    label, rules_text = audit_prompt.standard_excerpt(CLAIM_REVIEW)
    report_lines = report.read_text(encoding="utf-8").split("\n")
    body = prompt_body(
        [
            (CLAIMS_LABEL, claims_text(review, decided, found, report_lines)),
            *pieces,
            (f"FILE: {label}", rules_text),
        ]
    )
    return (
        f"{audit_prompt.instructions(CLAIM_REVIEW)}\n\nMODE: claim review · AREA: "
        f"{shown(area, repo)} · RECORD: {review.path.name}\n\n"
        f"{report_review.INLINE_NOTE}\n\n{body}"
    )
