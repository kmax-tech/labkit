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
fingerprint of the inputs it read (`report_reviews`). report-check holds
a report with a discussion block until a review of exactly that state
names no claim (`report_check.report_review_owed`); a claim holds the
state, and a later clean draw does not release it. On a state a review
already judged the command makes no new call: after a claim, change the
report or a source the reviewer read; after a clean review there is
nothing to do. `--again` draws once more as a measurement and releases
nothing. Nothing starts the review but this command: the hooks name it.
A report that discusses no run is not reviewed — one that cites no run
at all is left out of reach of this review.

Exit codes: 0 no claim (or this state already reviewed clean), 1 at least
one claim, 2 no review — no discussed run of the protocol in the report,
a discussed run with no `runs/<id>/`, a state with a claim and no
`--again`, the backend did not answer, or a reply whose lines and closing
count disagree.
"""

from __future__ import annotations

import re
from pathlib import Path

from labkit.checks.audit_binding import AuditError
from labkit.checks.report_blocks import Discussion, ReportBlockError, discussions
from labkit.formats import console, findings, report_reviews
from labkit.formats.report_reviews import ReportClaim
from labkit.formats.repo import (
    ProtocolChoiceError,
    layout_root,
    repo_protocols,
    shown,
    the_protocol,
)
from labkit.formats.runs import metrics_path, run_path
from labkit.gates import audit
from labkit.run import llm, llm_backends

REPORT_REVIEW = "report"
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
    it discusses no run: per area of REPO holding a discussed run
    (`runs/<id>/` beside a protocol), the command to run, paths as `shown`
    from REPO. The hint the post-change hook gives (`claude_hooks.post_change`);
    it runs nothing — a model call is the agent's to start; report-check
    holds the report until the review is done (`report_check.report_review_owed`).
    A discussed run no area holds names no command (report-check holds it
    as a cited run the repo lacks). Raises ReportBlockError on a block that
    does not read."""
    runs = list(dict.fromkeys(d.run_id for d in discussions(text)))
    if not runs:
        return None
    root = repo.resolve()
    areas = list(
        dict.fromkeys(
            p.parent
            for p in repo_protocols(root)
            for r in runs
            if run_path(p.parent, r).is_dir()
        )
    )
    if not areas:
        return None
    commands = [
        f"`labkit-audit {shown(a, root)} --report-review {shown(report, root)}`"
        for a in areas
    ]
    return (
        f"{shown(report, root)} discusses {', '.join(runs)} as not reported — "
        f"check that it states none of its numbers as results: "
        f"{'; '.join(commands)} (one model call; the commit holds until a "
        f"review of this state names no claim)"
    )


def review_keys(area: Path, report: Path, protocol: Path) -> tuple[str, str]:
    """(report, protocol) as a review record names them: relative to the
    repo AREA lies in (`layout_root`)."""
    root = layout_root(area)
    return shown(report, root), shown(protocol, root)


def discussed_under(report: Path, text: str, protocol: Path) -> list[Discussion]:
    """The discussion blocks of REPORT (its TEXT) that name PROTOCOL.
    Raises ReportBlockError on a block that does not read."""
    target = protocol.resolve()
    return [
        d for d in discussions(text) if (report.parent / d.protocol).resolve() == target
    ]


def numbered(text: str) -> str:
    """TEXT with each line as `<line>: <text>` — the numbers a claim cites."""
    return "\n".join(f"{n}: {line}" for n, line in enumerate(text.split("\n"), 1))


def audits_text(area: Path) -> str:
    """Every audit record of AREA with its findings and decisions, then every
    failed attempt with the backend's words — what the reviewer holds the
    report's statements against. Raises FindingsError on a file nobody can
    read."""
    blocks: list[str] = []
    for r in findings.area_records(area):
        lines = [f"{r.path.name} · {r.mode} · run {r.run_id or 'none'}"]
        for n, f in enumerate(r.findings, 1):
            lines.append(f"  #{n} · {f.grade} · {f.text}")
            lines.append(
                f"     status: {f.status}"
                + (f" · effect: {f.effect}" if f.effect else "")
            )
            if f.reason:
                lines.append(f"     reason: {f.reason}")
        if not r.findings:
            lines.append("  no findings")
        blocks.append("\n".join(lines))
    for f in findings.failed_attempts(area):
        blocks.append(
            f"{f.path.name} · {f.mode} · FAILED ({f.cause}) · {f.model}\n"
            f"  error: {f.error}"
        )
    return "\n\n".join(blocks) or "no audit records and no failed attempts"


def review_pieces(
    area: Path,
    report: Path,
    text: str,
    protocol: Path,
    protocol_text: str,
    discussed: list[Discussion],
) -> list[tuple[str, str]]:
    """The (label, text) the reviewer reads of REPORT (its TEXT) under
    PROTOCOL (its PROTOCOL_TEXT) in AREA, in order: the report numbered,
    its DISCUSSED blocks, the protocol, each discussed run's
    `metrics.json`, the audits (`audits_text`). The one home of what a
    review saw: the prompt is rendered from it, the record's fingerprint
    is taken over it, and the gate takes it again to tell whether a review
    saw the state it holds. Raises AuditError when a discussed run has no
    `runs/<id>/` in AREA; FindingsError on an unreadable audit file."""
    repo = layout_root(area)
    pieces: list[tuple[str, str]] = [
        (f"REPORT {shown(report, repo)}", numbered(text)),
        (
            "DISCUSSED",
            "\n".join(
                f"line {d.first}: run {d.run_id} — why: {d.why}" for d in discussed
            ),
        ),
        (f"FILE: {shown(protocol, repo)}", protocol_text),
    ]
    for run_id in dict.fromkeys(d.run_id for d in discussed):
        run_dir = run_path(area, run_id)
        if not run_dir.is_dir():
            raise AuditError(
                f"{report.name} discusses run {run_id}, and there is no "
                f"{run_dir.relative_to(area)}/ in {shown(area, repo)}"
            )
        metrics = metrics_path(run_dir)
        pieces.append(
            (
                f"FILE: {shown(metrics, repo)}",
                metrics.read_text(encoding="utf-8")
                if metrics.is_file()
                else "no metrics.json in this run",
            )
        )
    pieces.append(("AUDITS", audits_text(area)))
    return pieces


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
    cost. Exit 0 no claim (or this state already reviewed clean), 1 a
    claim, 2 no review."""
    try:
        chosen = the_protocol(area, protocol)
        prompt, discussed, pieces = gather_report(area, report, chosen)
        whole, parts = report_reviews.fingerprint(pieces)
        report_key, protocol_key = review_keys(area, report, chosen)
        stands = report_reviews.standing(
            report_reviews.area_report_reviews(area), report_key, protocol_key, whole
        )
        if not again and stands.claims:
            raise AuditError(
                f"{report_key}: a review of this state named "
                f"{len(stands.claims)} claim(s) ({stands.claims[0][0].path.name}) — "
                f"another draw settles nothing; change the report, or a source the "
                f"reviewer read, and review that state (`--again` draws as a "
                f"measurement and releases nothing)"
            )
        if not again and stands.released:
            print(
                f"report review: {report_key} in this state is reviewed, no claim "
                f"({stands.on_state[-1].path.name}) — nothing to do"
            )
            return 0
        console.progress(
            "labkit-audit",
            f"report review · {report.name} · {len(discussed)} discussed run(s) · "
            f"{model} · {len(prompt) // 1000} kB",
        )
        reply = llm.complete(
            model, prompt, timeout=timeout, max_tokens=audit._report_room(model)
        )
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
    except (
        AuditError,
        ProtocolChoiceError,
        findings.FindingsError,
        report_reviews.ReportReviewError,
        llm_backends.BackendError,
        llm_backends.PromptTruncated,
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
    held = (
        "the commit holds until the report, or a source the reviewer read, "
        "changes and a review of that state names no claim"
        if claims
        else "this state is released"
    )
    print(
        f"report review: {len(claims)} claim(s), recorded in "
        f"{shown(written, Path.cwd())}"
        + (" (--again: a measurement, it releases nothing)" if again else "")
        + f" — {held}"
    )
    return 1 if claims else 0
