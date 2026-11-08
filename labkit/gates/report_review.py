"""report_review — `labkit-audit AREA --report-review REPORT`: a cold reader
on a finished report: does it present as a valid result anything the
protocol has not adopted, or state something the audits or the adopted
result contradict?

    labkit-audit <AREA> --report-review REPORT [--protocol FILE] [--again]
                 [--model ALIAS] [--timeout S] [--out FILE]

The adoption (`labkit-adopt`) is the one way a number leaves the area as
a result, and its generated block shows it. Whether the report's prose
keeps to that is semantics: an older run's "PASS", a verdict the adopted
run does not hold, a discussed run's number in a summary. The reviewer
gets, in one call: the report with its line numbers, the run the
protocol has adopted (or none), the discussion blocks of the protocol
(`protocol-fill … --discuss RUN --why … --into REPORT`; or none), the
protocol as it is now, the `metrics.json` of the adopted, each discussed
and each cited run of the area, and every audit record of the area with
its decisions and every failed attempt (`review_pieces`). Instructions:
`report-review.agent.md`.

Agent audit; its record is a gate's input. The review writes
`audits/report-reviews/<minute>-review.toml` with the claims and the
fingerprint of the inputs it read (`report_reviews`). The call is an
attempt in the area's journal (`attempts.attempt`, mode `report-review`,
started on that fingerprint): the answer kept before it is read, the end
naming the record or why there is none — a review with a claim deleted
before the commit is named, so the state stays held once the record is
gone. report-check holds a report with a
discussion block, and the report a protocol's head registers once it
carries its result or handover block, until a review of exactly that
state names no claim (`report_hold.report_review_owed`,
`registered_report.report_owed`); a claim holds the state, and a later clean
draw does not release it. A research note citing a run is not held: it
owes a review only when it discusses one, and may be reviewed by hand.
On a state a review
already judged the command makes no new call: after a claim, change the
report or a source the reviewer read; after a clean review there is
nothing to do. `--again` draws once more on such a state, to see how the
reviewer's answers spread; its record counts like any review's — a claim
it names holds the state — and it releases nothing: a clean `--again`
draw lifts no claim, and a state only `--again` draws saw is still owed
a review. After every draw the command prints two lines, the draw's
claims and the state as every record of it now stands (`state_after`),
and the exit code is the state's: a clean draw on a held state is no
"done". Nothing starts the review but this command: the hooks name it.

Exit codes (the state's, by the release rule report-check holds the
report to, `report_reviews.standing`; at the commit only the records the
index holds count): 0 the state is
released — a review that is no `--again` draw saw it and no review of it
named a claim (this call's, or one before it: nothing to do; the commit
counts the record once it is staged); 1 after a draw, the commit holds
the state — a claim on it, this draw's or an earlier one's, or only
`--again` draws saw it; 2 no review — a discussed run with no
`runs/<id>/`, a state with a claim and no `--again` (refused, no call),
the backend did not answer, or a reply whose lines and closing count
disagree.
"""

from __future__ import annotations

import re
from pathlib import Path

from labkit.checks.audit_binding import AuditError
from labkit.checks.report_blocks import Discussion, ReportBlockError, discussions
from labkit.formats import attempts, console, evidence, findings, report_reviews
from labkit.formats.report_reviews import ReportClaim, held_by
from labkit.checks.report_review_inputs import review_keys, review_pieces
from labkit.formats.repo import layout_root, shown, the_protocol
from labkit.formats.commands import report_review_command
from labkit.formats.prompts import prompt_body
from labkit.gates import audit_call, audit_prompt, audit_reply, report_hold
from labkit.gates.ways_out import ANSWER_AGAIN

REPORT_REVIEW = "report"
#: the mode of its attempts in the area's journal (`attempts`)
ATTEMPT_MODE = report_reviews.ATTEMPT_MODE
#: a claim line of the reviewer's report
CLAIM = re.compile(
    findings.LEAD
    + r"\**CLAIM\s*#(\d+)\**\s*"
    + findings.SEP
    + r"\s*line\s*(\d+)\s*"
    + findings.SEP
    + r"\s*\**(result|contradiction)\**\s*"
    + findings.SEP
    + r"\s*(.*?)\s*$",
    re.M,
)
VERDICT = re.compile(r"verdict:\s*(\d+)\s*claims?(?:\(s\))?", re.I)
#: a line that announces a claim, whatever follows: held to CLAIM's form
CLAIM_LEAD = re.compile(findings.LEAD + r"\**CLAIM\b", re.I)
INLINE_NOTE = (
    "Everything you are told to read is inlined below; each part starts with "
    "a `===== <label> =====` line. Nothing else is in scope."
)


def discussed_under(report: Path, text: str, protocol: Path) -> list[Discussion]:
    """The discussion blocks of REPORT (its TEXT) that name PROTOCOL.
    Raises ReportBlockError on a block that does not read."""
    target = protocol.resolve()
    return [
        d for d in discussions(text) if (report.parent / d.protocol).resolve() == target
    ]


def gather_report(
    area: Path, report: Path, protocol: Path
) -> tuple[str, list[Discussion], list[tuple[str, str]]]:
    """(prompt, the discussion blocks under PROTOCOL — none is a report
    to review too —, the pieces the prompt shows — `review_pieces`) for
    REPORT. Raises AuditError when a discussed run has no `runs/<id>/` in
    AREA, or a block does not read; FindingsError on an unreadable audit
    file."""
    text = report.read_text(encoding="utf-8")
    try:
        discussed = discussed_under(report, text, protocol)
    except ReportBlockError as exc:
        raise AuditError(
            f"{report.name}: {exc}",
            fix="restore the block's comment lines as `protocol-fill` wrote them "
            "(`--discuss … --into` writes the block again)",
        ) from exc
    pieces = review_pieces(
        area, report, text, protocol, protocol.read_text(encoding="utf-8"), discussed
    )
    repo = layout_root(area)
    _, rules = audit_prompt.review_brief()
    shown_pieces = [*pieces, rules]
    body = prompt_body(shown_pieces)
    prompt = (
        f"{audit_prompt.instructions(REPORT_REVIEW)}\n\nMODE: report review · AREA: "
        f"{shown(area, repo)} · REPORT: {shown(report, repo)}\n\n{INLINE_NOTE}\n\n{body}"
    )
    return prompt, discussed, pieces


def parse_claims(report: str, n_lines: int) -> list[ReportClaim]:
    """The claims before the LAST closing line, each citing a line of a
    report of N_LINES, numbered 1, 2, … in order, and as many as the
    closing count says; every line announcing a claim keeps the form, and
    nothing follows the closing line. Raises AuditError otherwise — a
    reply that disagrees with itself names nothing. A claim of a kind
    outside `result|contradiction` breaks the form: matched by nothing, it
    would let the reply count as clean."""
    last = audit_reply.last_verdict(VERDICT, report, "the reply", "a review")
    body = (report or "")[: last.start()]
    stray = [
        line.strip()
        for line in body.splitlines()
        if CLAIM_LEAD.match(line) and not CLAIM.match(line)
    ]
    if stray:
        raise AuditError(
            f"{len(stray)} CLAIM line(s) do not keep the form `CLAIM #<k> · line <n> "
            f"· result|contradiction · <why>` (the first: {stray[0][:80]!r}) — "
            "nothing is named",
            fix=ANSWER_AGAIN,
        )
    if (report or "")[last.end() :].strip():
        raise AuditError(
            "text after the closing line — the closing `verdict:` line is the last "
            "line, and a claim below it names nothing",
            fix=ANSWER_AGAIN,
        )
    found = list(CLAIM.finditer(body))
    numbers = [int(m.group(1)) for m in found]
    if numbers != list(range(1, len(found) + 1)):
        raise AuditError(
            f"the claims are numbered {numbers} — one CLAIM line each, #1, #2, … in order",
            fix=ANSWER_AGAIN,
        )
    said = int(last.group(1))
    if said != len(found):
        raise AuditError(
            f"the closing line counts {said} claim(s), the lines above number "
            f"{len(found)} — nothing is named",
            fix=ANSWER_AGAIN,
        )
    claims = [ReportClaim(int(m.group(2)), m.group(3), m.group(4)) for m in found]
    outside = [c.line for c in claims if not 1 <= c.line <= n_lines]
    if outside:
        raise AuditError(
            f"claim(s) cite line(s) {outside}, the report has {n_lines} — "
            f"nothing is named",
            fix=ANSWER_AGAIN,
        )
    return claims


def review_report(
    area: Path,
    report: Path,
    protocol: Path | None,
    model: str,
    timeout: int,
    out: Path | None,
    *,
    again: bool = False,
) -> int:
    """The command: gather, refuse a state already judged (unless AGAIN),
    one call, parse, write the record, print the claims and the call's
    cost, then the draw and the state apart (`state_after`, `state_line`).
    Exit the state's: 0 released (by this review, or already — nothing to
    do), 1 the commit holds it, 2 no review."""
    try:
        chosen = the_protocol(area, protocol)
        prompt, discussed, pieces = gather_report(area, report, chosen)
        whole, parts = report_hold.review_fingerprint(pieces)
        report_key, protocol_key = review_keys(area, report, chosen)
        standing = report_reviews.standing(
            report_reviews_of(area), report_key, protocol_key, whole
        )
        if not again and standing.claims:
            raise AuditError(
                f"{report_key}: this state is held by {held_by(standing)} — another "
                f"draw settles nothing",
                fix="change the report, or a source the reviewer read, so that the "
                "claim no longer holds, then run this command again on that state "
                "(`--again` draws once more on this one: its claims hold it too, "
                "and it releases nothing)",
            )
        if not again and standing.released:
            print(
                f"report review: {report_key} in this state is reviewed, no claim "
                f"({standing.on_state[-1].path.name}) — nothing to do"
            )
            return 0
        # `attempts.begin` refuses it all the same, but its refusal names
        # `--findings` and the handover, already written in that state, not
        # the removal that leads out
        lost = report_hold.lost_evidence(chosen)
        if lost is not None:
            raise AuditError(
                f"no report review of {report_key} — {lost.cause}", fix=lost.fix
            )
        console.progress(
            "labkit-audit",
            f"report review · {report.name} · {len(discussed)} discussed run(s) · "
            f"{model} · {len(prompt) // 1000} kB",
        )
        # journaled like an audit, started on the inputs' fingerprint: a
        # review with claims deleted before the commit is noticed by the
        # attempt that names it
        with audit_call.journaled_answer(
            area, ATTEMPT_MODE, model, whole, prompt, timeout
        ) as (running, reply):
            claims = parse_claims(
                reply, len(report.read_text(encoding="utf-8").split("\n"))
            )
            written = report_reviews.write_report_review(
                area,
                model=model,
                report=report_key,
                protocol=protocol_key,
                whole=whole,
                parts=parts,
                claims=claims,
                again=again,
            )
            running.end("record", file=attempts.under_audits(area, written))
    except audit_call.REFUSAL_ERRORS as exc:
        console.refuse("labkit-audit", str(exc).strip(chr(39)))
        return 2
    print(reply)
    if out:
        out.write_text(reply, encoding="utf-8")
    print()
    where = shown(report, Path.cwd())
    for c in claims:
        print(f"CLAIM: {where}:{c.line}: {c.kind} — {c.why}")
    print(
        f"report review: this draw names {len(claims)} claim(s), recorded in "
        f"{shown(written, Path.cwd())}"
        + (
            " — an `--again` draw: a claim it names holds the state like any "
            "review's, and it releases nothing"
            if again
            else ""
        )
    )
    standing = state_after(area, report_key, protocol_key, whole)
    print(f"report review state: {state_line(standing, area, report, chosen)}")
    # the state's code, not the draw's: a clean draw on a held state is no "done"
    return 0 if standing.released else 1


def state_after(
    area: Path, report_key: str, protocol_key: str, whole: str
) -> report_reviews.Standing:
    """Where the state of REPORT_KEY under PROTOCOL_KEY (its fingerprint
    WHOLE) stands after the review just written, read back from every
    record of AREA (`report_reviews.standing`) — what the command's exit
    code and its state line say, not the draw alone."""
    return report_reviews.standing(
        report_reviews_of(area), report_key, protocol_key, whole
    )


def report_reviews_of(area: Path) -> list[report_reviews.ReportReview]:
    """AREA's report reviews from its audit evidence read once
    (`evidence.read_evidence`); raises `report_reviews.ReportReviewError`
    with the sentence when one does not read, as the reader did."""
    held = evidence.read_evidence(area, staged=False)
    if held.report_reviews_unread:
        raise report_reviews.ReportReviewError(held.report_reviews_unread)
    return list(held.report_reviews)


def state_line(
    standing: report_reviews.Standing, area: Path, report: Path, protocol: Path
) -> str:
    """STANDING in words, with the step that answers it: released, held by a
    claim — this draw's or an earlier one's on the same state — or owed a
    review that is no `--again` draw (the command for REPORT under PROTOCOL
    in AREA). Printed apart from the draw's own claims: a clean `--again`
    draw on a held state would read as released while the commit stays
    refused."""
    if standing.released:
        return (
            "this state is released (the commit counts the review record "
            "once it is staged)"
        )
    if standing.claims:
        return (
            f"the commit holds this state: {held_by(standing)}; change the report, "
            f"or a source the reviewer read, so that no claim holds, then review "
            f"that state"
        )
    return (
        f"the commit holds this state: only a review that is no `--again` draw "
        f"releases it — `{report_review_command(area, report, protocol)}`"
    )
