"""report_review — `labkit-audit AREA --report-review REPORT`: a cold reader
on a finished report that discusses a run of AREA (not reported).

    labkit-audit <AREA> --report-review REPORT [--protocol FILE] [--again]
                 [--model ALIAS] [--timeout S] [--out FILE]

A discussion block (`report_blocks.discussions`, written by `protocol-fill
… --discuss RUN --why … --into REPORT`) says the run's numbers did not
leave the area. Whether the report keeps them out is semantics: a number
beside the block may be the why or a result, and a verdict may contradict
an audit decision. The reviewer gets, in one call: the report with its
line numbers, the discussion blocks of the protocol, the protocol as it
is now, each discussed run's `metrics.json`, and every audit record of
the area with its decisions and every failed attempt (`review_pieces`).
Instructions: `report-review.agent.md`.

Agent audit; its record is a gate's input. The review writes
`audits/report-reviews/<minute>-review.toml` with the claims and the
fingerprint of the inputs it read (`report_reviews`). The call is an
attempt in the area's journal (`attempts.attempt`, mode `report-review`,
started on that fingerprint): the answer kept before it is read, the end
naming the record or why there is none — a review with a claim deleted
before the commit is named, where before nothing held the state once it
was gone (ninth haiku round, t5). report-check holds
a report with a discussion block until a review of exactly that state
names no claim (`report_hold.report_review_owed`); a claim holds the
state, and a later clean draw does not release it. On a state a review
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
A report that discusses no run is not reviewed — one that cites no run
at all is left out of reach of this review.

Exit codes (the state's, by the release rule report-check holds the
report to, `report_reviews.standing`; at the commit only the records the
index holds count): 0 the state is
released — a review that is no `--again` draw saw it and no review of it
named a claim (this call's, or one before it: nothing to do; the commit
counts the record once it is staged); 1 after a draw, the commit holds
the state — a claim on it, this draw's or an earlier one's, or only
`--again` draws saw it; 2 no review — no discussed run of the protocol
in the report, a discussed run with no `runs/<id>/`, a state with a
claim and no `--again` (refused, no call), the backend did not answer, or a reply
whose lines and closing count disagree.
"""

from __future__ import annotations

import re
from pathlib import Path

from labkit.checks.audit_binding import AuditError
from labkit.checks.report_blocks import Discussion, ReportBlockError, discussions
from labkit.formats import attempts, console, findings, report_reviews
from labkit.formats.report_reviews import ReportClaim, held_by
from labkit.checks.report_review_inputs import review_keys, review_pieces
from labkit.formats.repo import (
    ProtocolChoiceError,
    audit_command,
    layout_root,
    report_review_command,
    shown,
    the_protocol,
)
from labkit.formats.runs import run_path
from labkit.gates import audit
from labkit.run import llm, llm_backends

REPORT_REVIEW = "report"
#: the mode of its attempts in the area's journal (`attempts`)
ATTEMPT_MODE = "report-review"
#: a claim line of the reviewer's report
CLAIM = re.compile(
    r"^[\s>*`-]*\**CLAIM\s*#(\d+)\**\s*(?:·|—|–|:)\s*line\s*(\d+)\s*(?:·|—|–|:)\s*"
    r"\**(result|contradiction)\**\s*(?:·|—|–|:)\s*(.*?)\s*$",
    re.M,
)
VERDICT = re.compile(r"verdict:\s*(\d+)\s*claims?(?:\(s\))?", re.I)
INLINE_NOTE = (
    "Everything you are told to read is inlined below; each part starts with "
    "a `===== <label> =====` line. Nothing else is in scope."
)


def review_hint(text: str, report: Path, repo: Path) -> str | None:
    """The sentence that names the review for REPORT (its TEXT), or None when
    it discusses no run: per protocol a discussion block names whose area
    holds the discussed run (`runs/<id>/`), the command to run
    (`repo.audit_command`, `--protocol` where the area holds several),
    paths as `shown` from REPO. The hint the post-change hook gives (`claude_hooks.post_change`);
    it runs nothing — a model call is the agent's to start; report-check
    holds the report until the review is done (`report_hold.report_review_owed`).
    A discussed run no area holds names no command (report-check holds it
    as a cited run the repo lacks). Raises ReportBlockError on a block that
    does not read."""
    found = discussions(text)
    runs = list(dict.fromkeys(d.run_id for d in found))
    if not runs:
        return None
    root = repo.resolve()
    protocols = list(
        dict.fromkeys(
            p
            for d in found
            if (p := (report.parent / d.protocol).resolve()).is_file()
            and run_path(p.parent, d.run_id).is_dir()
        )
    )
    if not protocols:
        return None
    commands = [
        f"`{audit_command(p.parent, '--report-review', shown(report, root), protocol=p, base=root)}`"
        for p in protocols
    ]
    return (
        f"{shown(report, root)} discusses {', '.join(runs)} as not reported — "
        f"check that it states none of its numbers as results: "
        f"{'; '.join(commands)} (one model call; the commit holds until a "
        f"review of this state names no claim)"
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
    """(prompt, the discussion blocks under PROTOCOL, the pieces the
    prompt shows — `review_pieces`) for REPORT. Raises AuditError when the
    report discusses no run of PROTOCOL (nothing to review), a discussed
    run has no `runs/<id>/` in AREA, or a block does not read;
    FindingsError on an unreadable audit file."""
    text = report.read_text(encoding="utf-8")
    try:
        discussed = discussed_under(report, text, protocol)
    except ReportBlockError as exc:
        raise AuditError(f"{report.name}: {exc}") from exc
    if not discussed:
        raise AuditError(
            f"{report.name}: no discussion block of a run of {protocol.name} "
            f"(`protocol-fill … --discuss RUN --why … --into {report.name}`) — "
            f"the report review reads reports that discuss a run; nothing to review"
        )
    pieces = review_pieces(
        area, report, text, protocol, protocol.read_text(encoding="utf-8"), discussed
    )
    repo = layout_root(area)
    label, rules_text = audit.standard_excerpt(REPORT_REVIEW)
    shown_pieces = [*pieces, (f"FILE: {label}", rules_text)]
    body = "".join(f"===== {lbl} =====\n{txt}\n" for lbl, txt in shown_pieces)
    prompt = (
        f"{audit.instructions(REPORT_REVIEW)}\n\nMODE: report review · AREA: "
        f"{shown(area, repo)} · REPORT: {shown(report, repo)}\n\n{INLINE_NOTE}\n\n{body}"
    )
    return prompt, discussed, pieces


def parse_claims(report: str, n_lines: int) -> list[ReportClaim]:
    """The claims before the LAST closing line, each citing a line of a
    report of N_LINES, numbered 1, 2, … in order, and as many as the
    closing count says. Raises AuditError otherwise — a reply that
    disagrees with itself names nothing."""
    matches = list(VERDICT.finditer(report or ""))
    if not matches:
        raise AuditError("the reply has no readable `verdict:` line — not a review")
    last = matches[-1]
    found = list(CLAIM.finditer((report or "")[: last.start()]))
    numbers = [int(m.group(1)) for m in found]
    if numbers != list(range(1, len(found) + 1)):
        raise AuditError(
            f"the claims are numbered {numbers} — one CLAIM line each, #1, #2, … in order"
        )
    said = int(last.group(1))
    if said != len(found):
        raise AuditError(
            f"the closing line counts {said} claim(s), the lines above number "
            f"{len(found)} — nothing is named; run the review again"
        )
    claims = [ReportClaim(int(m.group(2)), m.group(3), m.group(4)) for m in found]
    outside = [c.line for c in claims if not 1 <= c.line <= n_lines]
    if outside:
        raise AuditError(
            f"claim(s) cite line(s) {outside}, the report has {n_lines} — "
            f"nothing is named"
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
        whole, parts = report_reviews.fingerprint(pieces)
        report_key, protocol_key = review_keys(area, report, chosen)
        standing = report_reviews.standing(
            report_reviews.area_report_reviews(area), report_key, protocol_key, whole
        )
        if not again and standing.claims:
            raise AuditError(
                f"{report_key}: this state is held by {held_by(standing)} — another "
                f"draw settles nothing; change the report, or a source the reviewer "
                f"read, so that the claim no longer holds, then run this command "
                f"again on that state (`--again` draws once more on this one: its "
                f"claims hold it too, and it releases nothing)"
            )
        if not again and standing.released:
            print(
                f"report review: {report_key} in this state is reviewed, no claim "
                f"({standing.on_state[-1].path.name}) — nothing to do"
            )
            return 0
        console.progress(
            "labkit-audit",
            f"report review · {report.name} · {len(discussed)} discussed run(s) · "
            f"{model} · {len(prompt) // 1000} kB",
        )
        # journaled like an audit, started on the inputs' fingerprint: a
        # review with claims deleted before the commit is noticed by the
        # attempt that names it (ninth haiku round, t5)
        with attempts.attempt(area, ATTEMPT_MODE, model, whole) as running:
            for note in running.notes:
                console.progress("labkit-audit", note)
            reply = llm.complete(
                model, prompt, timeout=timeout, max_tokens=audit._report_room(model)
            )
            running.keep_answer(reply)
            console.progress("labkit-audit", f"tokens · {llm.last_usage().describe()}")
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
    except (
        AuditError,
        ProtocolChoiceError,
        findings.FindingsError,
        report_reviews.ReportReviewError,
        llm_backends.BackendError,
        llm_backends.PromptTruncated,
        attempts.AttemptError,  # another attempt runs, or a record is gone
        RuntimeError,  # git failed while the attempt was checked
        KeyError,  # llm.resolve on an alias models.toml does not know
        FileNotFoundError,
    ) as exc:
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
        report_reviews.area_report_reviews(area), report_key, protocol_key, whole
    )


def state_line(
    standing: report_reviews.Standing, area: Path, report: Path, protocol: Path
) -> str:
    """STANDING in words, with the step that answers it: released, held by a
    claim — this draw's or an earlier one's on the same state — or owed a
    review that is no `--again` draw (the command for REPORT under PROTOCOL
    in AREA). Printed apart from the draw's own claims: a clean `--again`
    draw on a held state read as released while the commit stayed refused."""
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
