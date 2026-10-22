"""decision_review — `labkit-audit AREA --review [--record FILE]`: a second,
cold auditor on the `stands` decisions of one analysis record.

    labkit-audit <AREA> --review [--record FILE] [--protocol FILE]
                 [--model ALIAS] [--timeout S] [--out FILE]

An accepted finding whose effect is `stands` claims that the verdicts hold,
read within the limit (`findings.EFFECT_STANDS`). The reviewer gets, in one
call: every such decision of the record (the finding, the person's
reason), the protocol as it is now (the registration and the reported
claim — Conclusion, Recorded results, Limit lines), the files the findings
name as the record's auditor read them (the area snapshot, held to the
record's `scope_sha`), and what the auditor was shown of the run (the
rows' excerpts and metrics.json, held to the record's `shown_sha`). The
finding and the reason alone would only test whether the reason sounds
plausible; the claim and the evidence are what it is tested against.
Instructions: `decision-review.agent.md`.

The verdicts are written beside the records (`formats/reviews`,
`audits/<minute>-review.toml`), bound to the record, its code, its run as
shown, the claim as judged (`reviews.claim_digest`: Conclusion, Recorded
results, Limit lines) and each decision as it stood
(`findings.decision_digest`). Only `upheld` releases a decision;
`rejected` and `insufficient` do not, nor does a review of a decision or
a claim since changed. After `rejected` the person decides again first —
limits the claim, changes the effect to `not assessable`, or fixes the
fault; a new audit is due when its basis changes or the finding is
disputed, and does not by itself settle the rejection. After
`insufficient` the missing evidence is supplied and the review run again. The gate: report-check names
every `stands` no review upholds — a warning while this check is an
exploration (TODO 2026-10-22: replay the fifth round's decisions first),
a blocker afterwards.

Exit codes: 0 every decision upheld, 1 at least one not upheld, 2 no
review — no record, nothing to review in it, the code or the run not what
the record's auditor saw (the decisions were made on that state; review
them there or audit again), a decision already reviewed as decided and
claimed now and not upheld (another draw settles nothing; `--again` draws
once more as a measurement, which never releases), the backend did not
answer, or a report whose lines and closing counts disagree (nothing is
recorded).

Why (labkit-paper area 09, fifth haiku round, 2026-10-22): 28 audit
findings, 15 accepted with no action; t5 accepted three BLOCKERs and six
WARNINGs with `stands`, six of them with the reason "Finding noted"; t18
closed a BLOCKER on group selection with a false "verified". Of four
findings at decision points, one was fixed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

from labkit.checks.audit_binding import AuditError, run_shown
from labkit.formats import console, findings, reviews
from labkit.formats.findings import EFFECT_STANDS
from labkit.formats.repo import ProtocolChoiceError, layout_root, shown, the_protocol
from labkit.formats.scope_sha import Snapshot, area_snapshot
from labkit.gates import audit
from labkit.run import llm, llm_backends

REVIEW = "review"
#: a decision line of the reviewer's report
DECISION = re.compile(
    r"^[\s>*`-]*\**DECISION\s*#(\d+)\**\s*(?:·|—|–|:)\s*\**"
    r"(upheld|rejected|insufficient)\**\s*(?:·|—|–|:)\s*(.*?)\s*$",
    re.M,
)
VERDICT = re.compile(
    r"verdict:\s*(\d+)\s*upheld,\s*(\d+)\s*rejected,\s*(\d+)\s*insufficient", re.I
)
DECISIONS_LABEL = (
    "DECISIONS — the accepted findings under review, each with the reason given"
)


def reviewable(record: findings.Record) -> list[tuple[int, findings.Finding]]:
    """(number, finding) of every decision of RECORD a review asks about: a
    limit of the result (`Record.limits`: an accepted BLOCKER, an accepted
    WARNING naming an effect) whose effect is `stands`. `not assessable`
    leaves the promise unjudged and claims nothing to review."""
    return [(n, f) for n, f in record.limits() if f.effect == EFFECT_STANDS]


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


def decisions_text(decided: list[tuple[int, findings.Finding]]) -> str:
    """The decisions as the reviewer reads them: number, grade, finding
    text, the reason, the effect."""
    blocks = [
        f"#{n} · {f.grade} · {f.text}\n   reason: {f.reason}\n   effect: {f.effect}"
        for n, f in decided
    ]
    return "\n\n".join(blocks)


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
    decided = reviewable(record)
    if not decided:
        raise AuditError(
            f"{record.path.name}: no accepted finding with effect `stands` — nothing "
            f"to review"
        )
    repo = layout_root(area)
    text = protocol.read_text(encoding="utf-8")
    snap: Snapshot = area_snapshot(area)
    if snap.sha != record.scope_sha:
        raise AuditError(
            f"the code stamps {snap.sha} now, the record's auditor read "
            f"{record.scope_sha} — the decisions were made on that code; review them "
            f"on it, or audit the code as it is now and decide again"
        )
    run_dir: Path | None = None
    if record.run_id is not None and record.run_id != findings.NO_RUN:
        run_dir = area / "runs" / record.run_id
        if not run_dir.is_dir():
            raise AuditError(
                f"{record.path.name} names run {record.run_id}, and there is no "
                f"runs/{record.run_id}/ in this area"
            )
    seen = run_shown(
        area, run_dir, "no completed bound run when the record was written"
    )
    if seen.sha != record.shown_sha:
        raise AuditError(
            f"the run shows {seen.sha} now, the record's auditor was shown "
            f"{record.shown_sha} — rows or metrics changed after the audit; audit "
            f"again and decide again"
        )
    label, rules_text = audit.standard_excerpt(REVIEW)
    pieces: list[tuple[str, str]] = [
        (DECISIONS_LABEL, decisions_text(decided)),
        (f"FILE: {shown(protocol, repo)}", text),
    ]
    for f in named_files(decided, repo, area):
        if f.resolve() in snap.contents:
            pieces.append((f"FILE: {shown(f, repo)}", snap.text(f)))
    pieces += list(seen.pieces)
    pieces.append((f"FILE: {label}", rules_text))
    body = "".join(f"===== {lbl} =====\n{txt}\n" for lbl, txt in pieces)
    prompt = (
        f"{audit.instructions(REVIEW)}\n\nMODE: {REVIEW} · AREA: {shown(area, repo)} · "
        f"RECORD: {record.path.name}\n\n{audit.INLINE_NOTE}\n\n{body}"
    )
    return Evidence(
        prompt, snap.sha, seen.sha, reviews.claim_digest(text), [n for n, _ in decided]
    )


def parse_review(report: str, numbers: list[int]) -> list[tuple[int, str, str]]:
    """(number, verdict, why) per decision line before the LAST closing
    line, held to NUMBERS: every number once, no other, and the closing
    counts equal to the lines. Raises AuditError otherwise — nothing is
    recorded from a report that disagrees with itself."""
    matches = list(VERDICT.finditer(report or ""))
    if not matches:
        raise AuditError("the report has no readable `verdict:` line — not a review")
    m = matches[-1]
    body = (report or "")[: m.start()]
    lines = [
        (int(d.group(1)), d.group(2), d.group(3).strip())
        for d in DECISION.finditer(body)
    ]
    got = [n for n, _, _ in lines]
    if sorted(got) != sorted(numbers) or len(set(got)) != len(got):
        raise AuditError(
            f"the report decides on findings {got}, the record asked about {numbers} "
            f"— one DECISION line per finding under review, no other"
        )
    counts = tuple(
        sum(1 for _, v, _ in lines if v == verdict) for verdict in reviews.VERDICTS
    )
    said = tuple(int(m.group(i)) for i in (1, 2, 3))
    if counts != said:
        raise AuditError(
            f"the closing line counts {said} (upheld, rejected, insufficient), the "
            f"lines above count {counts} — nothing is recorded; run the review again"
        )
    return lines


def _record(area: Path, record: Path | None) -> findings.Record:
    """RECORD read, or the area's newest analysis record; FindingsError when
    there is none."""
    if record is not None:
        return findings.read(record)
    analysis = [r for r in findings.area_records(area) if r.mode == "analysis"]
    if not analysis:
        raise findings.FindingsError(f"{area}: no analysis record — nothing to review")
    return analysis[-1]


def contested_gap(area: Path, protocol: Path, record: findings.Record) -> str | None:
    """Why another draw on RECORD's decisions settles nothing, or None: a
    review of a decision as decided and claimed now already said
    `rejected` or `insufficient` (`reviews.contested`). The sentence names
    the way out — deciding again — not another call."""
    text = protocol.read_text(encoding="utf-8")
    found = reviews.area_reviews(area)
    held = [
        n for n, _ in reviewable(record) if reviews.contested(record, n, found, text)
    ]
    if not held:
        return None
    return (
        f"{record.path.name}: finding(s) {', '.join(map(str, held))} were reviewed as "
        f"decided and claimed now and not upheld — another draw settles nothing; "
        f"decide again (`--decide N …`, the reason naming the evidence, or the "
        f"effect `not assessable`) or limit the claim, then review; `--again` "
        f"draws once more as a measurement and never releases"
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
    verdicts. Exit 0 every decision upheld, 1 not every one, 2 no review —
    among the refusals a contested state (`contested_gap`) unless AGAIN."""
    try:
        chosen = the_protocol(area, protocol)
        rec = _record(area, record)
        if not again:
            held = contested_gap(area, chosen, rec)
            if held:
                raise AuditError(held)
        evidence = gather_review(area, chosen, rec)
        print(
            f"labkit-audit: review · {rec.path.name} · {len(evidence.numbers)} "
            f"decision(s) · {model} · {len(evidence.prompt) // 1000} kB",
            file=sys.stderr,
        )
        report = llm.complete(
            model,
            evidence.prompt,
            timeout=timeout,
            max_tokens=audit._report_room(model),
        )
        print(f"labkit-audit: tokens · {llm.last_usage().describe()}", file=sys.stderr)
        lines = parse_review(report, evidence.numbers)
    except (
        AuditError,
        ProtocolChoiceError,
        findings.FindingsError,
        reviews.ReviewError,
        llm_backends.BackendError,
        llm_backends.PromptTruncated,
        KeyError,  # llm.resolve on an alias models.toml does not know
        FileNotFoundError,
        ValueError,  # nothing to stamp
    ) as exc:
        console.refuse("labkit-audit", str(exc).strip(chr(39)))
        return 2
    print(report)
    if out:
        out.write_text(report, encoding="utf-8")
    decisions = [
        reviews.Decision(n, findings.decision_digest(rec.findings[n - 1]), verdict, why)
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
    )
    u, r, i = reviews.counts_of(decisions)
    print()
    print(
        f"review: {shown(written, Path.cwd())} — {u} upheld, {r} rejected, "
        f"{i} insufficient; only `upheld` releases a `stands`."
    )
    if r:
        print(
            "  rejected: decide the finding again first — limit the claim (the "
            'Conclusion), change the effect (`--decide N accepted "REASON" --effect '
            '"<ID> not assessable"`) or fix the fault; a new audit only when its '
            "basis changes or the finding itself is disputed — auditing again does "
            "not settle a rejection"
        )
    if i:
        print(
            "  insufficient: supply the evidence the reviewer names (in the "
            "protocol or the run's outputs) and review again"
        )
    return 0 if r == 0 and i == 0 else 1
