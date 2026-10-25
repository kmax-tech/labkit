"""report_review — `labkit-audit AREA --report-review REPORT`: a cold reader
on a finished report that cites a run of AREA as not reported.

    labkit-audit <AREA> --report-review REPORT [--protocol FILE]
                 [--model ALIAS] [--timeout S] [--out FILE]

A mark `run <id> (not reported: <why>)` says the run's numbers did not
leave the area (`report_blocks.not_reported`). Whether the report keeps
them out is semantics: a number beside the mark may be the why or a
result, and a verdict may contradict an audit decision. The reviewer gets,
in one call: the report with its line numbers, the marked citations, the
protocol as it is now, each marked run's `metrics.json`, and every audit
record of the area with its decisions and every failed attempt.
Instructions: `report-review.agent.md`.

Agent audit, warning only: the claims it names are printed as WARNINGs
and recorded nowhere, and no gate reads them. Whether it ever holds a
report is decided after its catch rate, false alarms and cost are
measured (pilot: docs/usability/2026-10-25-report-review-pilot.md). A
report that marks no run is not reviewed — a report that
cites no run at all is left out of reach of this review.

Exit codes: 0 no claim, 1 at least one claim, 2 no review — no marked
run in the report, a marked run with no `runs/<id>/`, the backend did
not answer, or a report whose lines and closing count disagree.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from labkit.checks.audit_binding import AuditError
from labkit.checks.report_blocks import NotReported, not_reported
from labkit.formats import console, findings
from labkit.formats.repo import ProtocolChoiceError, layout_root, shown, the_protocol
from labkit.formats.runs import metrics_path, run_path
from labkit.gates import audit
from labkit.run import llm, llm_backends

REPORT_REVIEW = "report"
KINDS = ("result", "contradiction")
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


class Claim(NamedTuple):
    """One line the reviewer names: the report's LINE, the KIND (`KINDS`),
    WHY in its sentence."""

    line: int
    kind: str
    why: str


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


def gather_report(
    area: Path, report: Path, protocol: Path
) -> tuple[str, list[NotReported]]:
    """(prompt, marked citations) for REPORT. Raises AuditError when the
    report marks no run (nothing to review) or a marked run has no
    `runs/<id>/` in AREA; FindingsError on an unreadable audit file."""
    text = report.read_text(encoding="utf-8")
    marked = not_reported(text)
    if not marked:
        raise AuditError(
            f"{report.name}: no run cited as `(not reported: …)` — the report "
            f"review reads reports that mark a run; nothing to review"
        )
    repo = layout_root(area)
    pieces: list[tuple[str, str]] = [
        (f"REPORT {shown(report, repo)}", numbered(text)),
        (
            "MARKED",
            "\n".join(f"line {m.line}: run {m.run_id} — why: {m.why}" for m in marked),
        ),
        (f"FILE: {shown(protocol, repo)}", protocol.read_text(encoding="utf-8")),
    ]
    for run_id in dict.fromkeys(m.run_id for m in marked):
        run_dir = run_path(area, run_id)
        if not run_dir.is_dir():
            raise AuditError(
                f"{report.name} marks run {run_id}, and there is no "
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
    label, rules_text = audit.standard_excerpt(REPORT_REVIEW)
    pieces.append((f"FILE: {label}", rules_text))
    body = "".join(f"===== {lbl} =====\n{txt}\n" for lbl, txt in pieces)
    prompt = (
        f"{audit.instructions(REPORT_REVIEW)}\n\nMODE: report review · AREA: "
        f"{shown(area, repo)} · REPORT: {shown(report, repo)}\n\n{INLINE_NOTE}\n\n{body}"
    )
    return prompt, marked


def parse_claims(report: str, n_lines: int) -> list[Claim]:
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
    claims = [Claim(int(m.group(2)), m.group(3), m.group(4)) for m in found]
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
) -> int:
    """The command: gather, one call, parse, print the claims as WARNINGs and
    the call's cost. Exit 0 no claim, 1 a claim, 2 no review."""
    try:
        chosen = the_protocol(area, protocol)
        prompt, marked = gather_report(area, report, chosen)
        console.progress(
            "labkit-audit",
            f"report review · {report.name} · {len(marked)} marked citation(s) · "
            f"{model} · {len(prompt) // 1000} kB",
        )
        reply = llm.complete(
            model, prompt, timeout=timeout, max_tokens=audit._report_room(model)
        )
        console.progress("labkit-audit", f"tokens · {llm.last_usage().describe()}")
        claims = parse_claims(
            reply, len(report.read_text(encoding="utf-8").split("\n"))
        )
    except (
        AuditError,
        ProtocolChoiceError,
        findings.FindingsError,
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
        print(f"WARNING: {where}:{c.line}: {c.kind} — {c.why}")
    print(
        f"report review: {len(claims)} claim(s) — agent audit, a warning: it "
        f"blocks nothing and is recorded nowhere"
    )
    return 1 if claims else 0
