"""decision_review — `labkit-audit AREA --review [--record FILE]`: a second,
cold auditor on the `stands` decisions of one analysis record.

    labkit-audit <AREA> --review [--record FILE] [--protocol FILE]
                 [--model ALIAS] [--timeout S] [--out FILE]

A finding decided `limitation` whose effect is `stands` claims that the verdicts hold,
read within the limit (`findings.EFFECT_STANDS`). The reviewer gets, in one
call: every such decision of the record (the finding, the person's
reason), the protocol as it is now (the registration and the reported
claim — Conclusion, Recorded results, Limitation lines), the files the findings
name as the record's auditor read them (the area snapshot, held to the
record's `scope_sha`), and what the auditor was shown of the run (the
rows' excerpts and metrics.json, held to the record's `shown_sha`). The
finding and the reason alone would only test whether the reason sounds
plausible; the claim and the evidence are what it is tested against.
Instructions: `decision-review.agent.md`.

The verdicts are written beside the records (`formats/reviews`,
`audits/<minute>-review.toml`), bound to the record, its code, its run as
shown, the claim as judged (`reviews.claim_digest`: the Conclusion; the
Recorded results and Limitation lines are shown as they render and are bound
through the record and the run) and each decision as it stood
(`findings.decision_digest`). Only `upheld` releases a decision;
`rejected` and `insufficient` do not, nor does a review of a decision or
a claim since changed. The call is an attempt in the area's journal
(`attempts.attempt`, mode `review`): the answer kept before it is read,
the end naming the review file or why there is none — so a review
deleted before the commit is named. After `rejected` the person decides
again within the decisions the finding's subject allows
(`findings.allowed_decisions`, `rejected_way`): repair or supply
counter-evidence, or hand over; a permitted limitation may narrow the
claim or leave a registered promise not assessable. A new audit is due
when its basis changes or the finding is
disputed, and does not by itself settle the rejection. After
`insufficient` the missing evidence is supplied and the review run again.
Closing the finding instead — `false-positive`, `fixed`
(`findings.CLOSING`) — is a decision like any other once a review did
not uphold one on that finding: it is under review too
(`reviews.once_not_upheld`), and the reviewer is asked whether the
reason shows the finding inapplicable, the fault gone in the files as
audited, or the task somebody else's; a reason alone releases nothing
(sixth haiku round, 2026-10-23, t5). The gate: report-check blocks on an
accepted BLOCKER's `stands` no review upholds, and on a closed contested
BLOCKER, and warns on a WARNING's (`report_decisions.review_findings`).

Exit codes: 0 every decision upheld, 1 at least one not upheld, 2 no
review — no record, nothing to review in it (no `stands`, no closed
contested finding, no carried finding closed), the code or the run not what
the record's auditor saw (the decisions were made on that state; review
them there or audit again), a decision already reviewed as decided and
claimed now and not upheld (another draw settles nothing; `--again` draws
once more — its verdicts count, and it never releases a contested
decision), the backend did not answer, or a report whose lines and
closing counts disagree (nothing is recorded).

History: docs/notes/2026-10-23-decision-review-history.md.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from labkit.formats.runs import run_path
from labkit.checks.audit_binding import AuditError, run_shown
from labkit.checks.run_record_check import script_as_run
from labkit.checks.result_render import rendering
from labkit.formats import attempts, console, findings, reviews
from labkit.formats.findings import EFFECT_STANDS
from labkit.formats.protocol_check import conclusion_written
from labkit.formats.repo import audit_command, layout_root, shown, the_protocol
from labkit.formats.scope_sha import Snapshot, area_snapshot, validation_note
from labkit.formats.prompts import prompt_body
from labkit.formats.standard_contract import ANALYSIS_AUDIT
from labkit.gates import audit, audit_decisions, audit_prompt, audit_reply
from labkit.gates.ways_out import ANSWER_AGAIN

#: the review's mode: its instructions, the prompt's MODE line and its
#: attempts in the area's journal (`attempts`)
REVIEW = "review"
#: a decision line of the reviewer's report
DECISION = re.compile(
    findings.LEAD + r"\**DECISION\s*#(\d+)\**\s*" + findings.SEP + r"\s*\**"
    r"(upheld|rejected|insufficient)\**\s*" + findings.SEP + r"\s*(.*?)\s*$",
    re.M,
)
VERDICT = re.compile(
    r"verdict:\s*(\d+)\s*upheld,\s*(\d+)\s*rejected,\s*(\d+)\s*insufficient", re.I
)
DECISIONS_LABEL = (
    "DECISIONS — the decisions under review, each with the reason given: an "
    "finding decided `limitation` with effect `stands`, or a finding closed after a review "
    "did not uphold a decision on it"
)
RESULT_LABEL = (
    "RESULT — the Recorded results line and the Limitation lines as `protocol-fill "
    "--from-run` renders them for this run and these decisions (the protocol "
    "above may not carry them yet)"
)


def rendered_result(area: Path, text: str, run_dir: Path | None) -> str:
    """The result section as it renders for RUN_DIR under the decisions as
    they stand (`result_render.rendering`): what the reviewer judges the
    Conclusion against, since `--from-run` writes these lines after the
    decision. A sentence instead when nothing renders (no run, or no
    metrics)."""
    if run_dir is None:
        return "no run: nothing renders"
    try:
        r = rendering(area, text, run_dir)
    except (OSError, ValueError) as exc:
        return f"nothing renders: {exc}"
    return "\n".join(
        [
            f"- **Recorded results:** {r.recorded_results}",
            *(f"- **{lbl}:** {value}" for lbl, value in r.limits),
        ]
    )


def reviewable(
    record: findings.Record, found: list[reviews.Review]
) -> list[tuple[int, findings.Finding]]:
    """(number, finding) of every decision of RECORD a review asks about,
    in the record's order: a limitation of the result (`Record.limits`: a
    BLOCKER or WARNING decided `limitation`) whose effect is `stands`, and a
    finding closed (`findings.CLOSING`: false-positive, fixed) after a review
    among FOUND did not uphold a decision on it (`reviews.once_not_upheld`),
    a carried finding (`carries`: a follow-up did not find it resolved) now
    `false-positive` —
    report-check holds it until a review upholds that
    (`report_decisions.followup_findings`) —, a BLOCKER `dismissed`, its
    first dismissal too (`findings.false_positive_blocker`), and a BLOCKER
    on the Conclusion decided `fixed` (`findings.fixed_claim`: no follow-up
    audit is shown a repaired claim). `not assessable`
    leaves the promise unjudged and claims nothing to review."""
    stands = {n for n, f in record.limits() if f.effect == EFFECT_STANDS}
    return [
        (n, f)
        for n, f in enumerate(record.findings, 1)
        if n in stands
        or findings.carried_and_closed(f)
        or findings.false_positive_blocker(f)
        or findings.fixed_claim(f)
        or (
            f.status in findings.CLOSING
            and reviews.once_not_upheld(record, n, found) is not None
        )
    ]


def named_files(
    decided: list[tuple[int, findings.Finding]], repo: Path, area: Path
) -> list[Path]:
    """The files the findings' second field names (`<file>:<line>`, the
    path's first word), resolved against the repo root, else the area,
    each once in order, existing files only. A finding naming the protocol
    or a data file adds nothing here: the protocol is inlined anyway, and
    the snapshot holds code."""
    out: list[Path] = []
    for _, f in decided:
        # the second field stands on the grade line, the finding's first
        fields = f.text.split(" · ")
        if len(fields) < 2:
            continue
        word = fields[1].strip().split()[0] if fields[1].strip() else ""
        name = word.split(":")[0].strip("`'\"()")
        if not name:
            continue
        for base in (repo, area):
            p = (base / name).resolve()
            if p.is_file() and p not in out:
                out.append(p)
                break
    return out


def decisions_text(
    record: findings.Record,
    decided: list[tuple[int, findings.Finding]],
    found: list[reviews.Review],
    metrics: dict | None,
) -> str:
    """The decisions of RECORD under review, as the reviewer reads them:
    number, grade, finding text, the status, the reason, the effect
    (accepted only), the finding's required check with its value in
    METRICS — the run's snapshot the prompt shows — or that it is missing
    (`audit_prompt.required_check_line`), so a reason resting on the check
    meets what the run records beside it (round 2, t21 r10: "verified: one
    feature" against a run that never counted them, judged
    `insufficient`) — and, for a finding closed after a review did not
    uphold a decision on it, that earlier verdict with its sentence
    (`reviews.once_not_upheld`), so the reviewer knows what the new
    decision answers to."""
    blocks: list[str] = []
    for n, f in decided:
        lines = [
            f"#{n} · {f.grade} · {f.text}",
            f"   status: {f.status}",
            f"   reason: {f.reason}",
        ]
        if f.effect:
            lines.append(f"   effect: {f.effect}")
        check = audit_prompt.required_check_line(f, metrics)
        if check:
            lines.append(f"   {check}")
        was = reviews.once_not_upheld(record, n, found)
        if f.status in findings.CLOSING and was is not None:
            lines.append(
                f"   decided again after a review said {was.verdict}: {was.why}"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


#: the piece that says why the reviewed run's measuring script is not shown
SCRIPT_NOT_SHOWN = "MEASURING SCRIPT — not inlined"


def measuring_script(
    area: Path, run_dir: Path, snap: Snapshot
) -> list[tuple[str, str]]:
    """The piece the review shows of the script RUN_DIR ran, when no
    finding under review names a code file — a finding placed in the
    protocol left the reviewer no code (round 2, t34 r1: a Unit finding on
    band powers, judged without the call that computed them). The script
    as the run ran it (`run_record_check.script_as_run`): the area's file
    from SNAP when its digest is the one the run recorded, else the run's
    own copy, labelled as such; else one piece saying why none is shown. A
    script changed since the run never stands in for the one it ran.
    Read-only."""
    script, note = script_as_run(area, run_dir)
    repo = layout_root(area)
    if script is None:
        return [(SCRIPT_NOT_SHOWN, note)]
    if not note:
        if script.resolve() not in snap.contents:
            return [
                (SCRIPT_NOT_SHOWN, f"{script.name} is not in the area's code stamp")
            ]
        return [(f"FILE: {shown(script, repo)}", snap.text(script))]
    return [
        (f"FILE: {shown(script, repo)} ({note})", script.read_text(encoding="utf-8"))
    ]


class Evidence(NamedTuple):
    """What one review call rests on: the prompt, the record's code stamp
    (the snapshot's sha, equal by construction), what was shown of the
    run (its sha, equal by construction), the numbers under review."""

    prompt: str
    scope_sha: str
    shown_sha: str
    claim_sha: str  # the claim the prompt carries (`reviews.claim_digest`)
    numbers: list[int]


def gather_review(area: Path, protocol: Path, record: findings.Record) -> Evidence:
    """The prompt for RECORD's `stands` decisions, from one reading: the
    area snapshot must stamp what the record names and the run must show
    what the record's auditor saw, else AuditError — the decisions were
    made on that state. AuditError too when the record holds nothing to
    review, or names a run that is gone."""
    found = reviews.area_reviews(area)
    decided = reviewable(record, found)
    if not decided:
        raise AuditError(
            f"{record.path.name}: no finding decided `limitation` with effect `stands`, no "
            f"finding closed after a review did not uphold it, no carried finding "
            f"closed false-positive, no BLOCKER decided false-positive and no "
            f"BLOCKER on the Conclusion decided fixed — nothing to review",
            fix=f"`{audit_command(area, '--findings', protocol=protocol)}` "
            f"shows what the area's records still owe",
        )
    repo = layout_root(area)
    text = protocol.read_text(encoding="utf-8")
    if not conclusion_written(text):
        raise AuditError(
            f"{protocol.name}: the Conclusion is not written yet — the review judges "
            f"the claim, and a review made before it is written goes stale the moment "
            f"it is (judge-2 on 86e38bc paid a second review for that)",
            fix="write the Conclusion, then review",
        )
    snap: Snapshot = area_snapshot(area)
    if snap.sha != record.scope_sha:
        raise AuditError(
            f"the code stamps {snap.sha} now, the record's auditor read "
            f"{record.scope_sha} — the decisions were made on that code"
            f"{validation_note(area)}",
            fix="review them on it, or audit the code as it is now and decide again",
        )
    run_dir: Path | None = None
    if record.run_id is not None and record.run_id != findings.NO_RUN:
        run_dir = run_path(area, record.run_id)
        if not run_dir.is_dir():
            raise AuditError(
                f"{record.path.name} names run {record.run_id}, and there is no "
                f"{run_dir.relative_to(area)}/ in this area",
                fix="measure again under a new run, audit that and decide its findings",
            )
    seen = run_shown(
        area,
        run_dir,
        "no completed bound run when the record was written",
        text,
    )
    if seen.sha != record.shown_sha:
        raise AuditError(
            f"the run shows {seen.sha} now, the record's auditor was shown "
            f"{record.shown_sha} — rows, metrics, the adopted run or the audited "
            f"protocol text changed after the audit",
            fix="audit again and decide again",
        )
    label, rules_text = audit_prompt.standard_excerpt(REVIEW)
    pieces: list[tuple[str, str]] = [
        (DECISIONS_LABEL, decisions_text(record, decided, found, seen.evidence())),
        (f"FILE: {shown(protocol, repo)}", text),
        (RESULT_LABEL, rendered_result(area, text, run_dir)),
    ]
    code = [f for f in named_files(decided, repo, area) if f.resolve() in snap.contents]
    for f in code:
        pieces.append((f"FILE: {shown(f, repo)}", snap.text(f)))
    if not code and run_dir is not None:
        pieces += measuring_script(area, run_dir, snap)
    pieces += list(seen.pieces)
    pieces.append((f"FILE: {label}", rules_text))
    body = prompt_body(pieces)
    prompt = (
        f"{audit_prompt.instructions(REVIEW)}\n\nMODE: {REVIEW} · AREA: {shown(area, repo)} · "
        f"RECORD: {record.path.name}\n\n{audit_prompt.INLINE_NOTE}\n\n{body}"
    )
    return Evidence(
        prompt, snap.sha, seen.sha, reviews.claim_digest(text), [n for n, _ in decided]
    )


def parse_review(report: str, numbers: list[int]) -> list[tuple[int, str, str]]:
    """(number, verdict, why) per decision line before the LAST closing
    line, held to NUMBERS: every number once, no other, and the closing
    counts equal to the lines. Raises AuditError otherwise — nothing is
    recorded from a report that disagrees with itself."""
    m = audit_reply.last_verdict(VERDICT, report, "the report", "a review")
    body = (report or "")[: m.start()]
    lines = [
        (int(d.group(1)), d.group(2), d.group(3).strip())
        for d in DECISION.finditer(body)
    ]
    got = [n for n, _, _ in lines]
    if sorted(got) != sorted(numbers) or len(set(got)) != len(got):
        raise AuditError(
            f"the report decides on findings {got}, the record asked about {numbers} "
            f"— one DECISION line per finding under review, no other",
            fix=ANSWER_AGAIN,
        )
    counts = tuple(
        sum(1 for _, v, _ in lines if v == verdict) for verdict in reviews.VERDICTS
    )
    said = tuple(int(m.group(i)) for i in (1, 2, 3))
    if counts != said:
        raise AuditError(
            f"the closing line counts {said} (upheld, rejected, insufficient), the "
            f"lines above count {counts} — nothing is recorded",
            fix=ANSWER_AGAIN,
        )
    return lines


def _record(area: Path, record: Path | None) -> findings.Record:
    """RECORD read, or the area's newest analysis record; FindingsError when
    there is none."""
    if record is not None:
        return findings.read(audit_decisions.record_path(area, record))
    analysis = [r for r in findings.area_records(area) if r.mode == ANALYSIS_AUDIT]
    if not analysis:
        raise findings.FindingsError(f"{area}: no analysis record — nothing to review")
    return analysis[-1]


def contested_gap(
    area: Path, protocol: Path, record: findings.Record
) -> AuditError | None:
    """Why another draw on RECORD's decisions settles nothing, as the refusal
    to raise, or None: a review of a decision as decided and claimed now
    already said `rejected` or `insufficient` (`reviews.contested`). Its way
    out is deciding again, not another call."""
    text = protocol.read_text(encoding="utf-8")
    found = reviews.area_reviews(area)
    held = [
        n
        for n, _ in reviewable(record, found)
        if reviews.contested(record, n, found, text)
    ]
    if not held:
        return None
    promised = audit_decisions.may_leave_unassessed(area, protocol)
    decide_again = "; ".join(
        f"finding #{n}: {rejected_way(record.findings[n - 1], promised)}" for n in held
    )
    return AuditError(
        f"{record.path.name}: finding(s) {', '.join(map(str, held))} were reviewed as "
        f"decided and claimed now and not upheld — another draw settles nothing",
        fix=f"{decide_again}; `--again` draws once more: its verdicts count, and it "
        "never releases this state",
    )


def review(
    area: Path,
    protocol: Path | None,
    record: Path | None,
    model: str,
    timeout: int,
    out: Path | None,
    *,
    again: bool = False,
) -> int:
    """The command: gather, one call, parse, write the review, print the
    draw's verdicts and, apart, the state they leave (`held_after`). The
    exit says the state, not the draw: 0 every decision reviewed is
    released (`reviews.upholding`), 1 not every one — a verdict of this or
    an earlier draw holds it, or only `--again` draws said upheld —, 2 no
    review; among the refusals a contested state (`contested_gap`) unless
    AGAIN, whose draw counts and releases nothing."""
    try:
        chosen = the_protocol(area, protocol)
        rec = _record(area, record)
        if not again:
            held = contested_gap(area, chosen, rec)
            if held:
                raise held
        evidence = gather_review(area, chosen, rec)
        console.progress(
            "labkit-audit",
            f"review · {rec.path.name} · {len(evidence.numbers)} "
            f"decision(s) · {model} · {len(evidence.prompt) // 1000} kB",
        )
        # journaled like an audit: a review deleted before the commit is
        # noticed by the attempt that names it (ninth haiku round, t5)
        with audit.journaled_answer(
            area, REVIEW, model, evidence.scope_sha, evidence.prompt, timeout
        ) as (running, report):
            lines = parse_review(report, evidence.numbers)
            print(report)
            if out:
                out.write_text(report, encoding="utf-8")
            decisions = [
                reviews.Decision(
                    n, findings.decision_digest(rec.findings[n - 1]), verdict, why
                )
                for n, verdict, why in lines
            ]
            written = reviews.write_review(
                area,
                model,
                rec.path.name,
                evidence.scope_sha,
                evidence.shown_sha,
                evidence.claim_sha,
                decisions,
                again=again,
            )
            running.end("record", file=attempts.under_audits(area, written))
    except audit.REFUSAL_ERRORS as exc:
        console.refuse("labkit-audit", str(exc).strip(chr(39)))
        return 2
    u, r, i = reviews.counts_of(decisions)
    held = held_after(area, chosen, rec, [d.finding for d in decisions])
    print()
    print(
        f"review: this draw{' (--again, it releases nothing)' if again else ''} "
        f"— {u} upheld, {r} rejected, {i} insufficient, recorded in "
        f"{shown(written, Path.cwd())}"
    )
    print(
        "review state: "
        + (
            f"held — finding(s) {', '.join(map(str, held))} not released"
            if held
            else "every decision reviewed is released"
        )
    )
    if r:
        promised = audit_decisions.may_leave_unassessed(area, chosen)
        for d in decisions:
            if d.verdict == "rejected":
                print(
                    f"  rejected: {rejected_way(rec.findings[d.finding - 1], promised)} "
                    f"(finding #{d.finding})"
                )
    if i:
        print(
            "  insufficient: supply the evidence the reviewer names (in the "
            "protocol or the run's outputs) and review again"
        )
    return 1 if held else 0


def rejected_way(finding: findings.Finding, promised: bool) -> str:
    """What a reviewed decision on FINDING owes first, within its allowed
    decisions (`findings.allowed_decisions`). A permitted limitation may
    leave a promise not assessable only when PROMISED. No state is read
    or written; another draw alone settles nothing."""
    if "limitation" not in findings.allowed_decisions(finding):
        routes = (
            "complete the repair or required check the finding names, supply "
            "counter-evidence for `false-positive`, or hand the protocol over "
            "with the finding open (`protocol-fill <PROTOCOL> --handover`)"
        )
    elif promised:
        routes = (
            "limit the claim (the Conclusion), change the effect (`--decide N limitation "
            '--why "REASON" --not-assessable <ID>`) or fix the fault'
        )
    else:
        routes = (
            "limit the claim (the Conclusion) or fix the fault — or hand the "
            "protocol over (no promise is registered to leave not assessable)"
        )
    return (
        f"decide the finding again first — {routes}; a new audit only when its "
        "basis changes or the finding itself is disputed — auditing again does "
        "not settle a rejection"
    )


def held_after(
    area: Path, protocol: Path, record: findings.Record, numbers: list[int]
) -> list[int]:
    """The findings among NUMBERS of RECORD the area's reviews, read back,
    do not release (`reviews.upholding`, under the claim PROTOCOL makes
    now) — every draw on the state counted, an `--again` draw releasing
    nothing."""
    text = protocol.read_text(encoding="utf-8")
    found = reviews.area_reviews(area)
    return [n for n in numbers if not reviews.upholding(record, n, found, text)]
