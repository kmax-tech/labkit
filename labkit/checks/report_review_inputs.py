"""report_review_inputs — what a report review reads and how its record
names report and protocol, without a model call: the reviewer's prompt is
rendered from `review_pieces`, the record's fingerprint is taken over it,
and report-check takes it again to tell whether a review saw the state it
holds. Model-free, so the release gate reads it without loading a model
backend (audit 2026-10-27, third, M1).
"""

from __future__ import annotations

from pathlib import Path

from labkit.checks.audit_binding import AuditError
from labkit.checks.report_blocks import Discussion
from labkit.formats import findings
from labkit.formats import failed_attempts
from labkit.formats.repo import layout_root, shown
from labkit.formats.runs import metrics_path, run_path


def review_keys(area: Path, report: Path, protocol: Path) -> tuple[str, str]:
    """(report, protocol) as a review record names them: relative to the
    repo AREA lies in (`layout_root`)."""
    root = layout_root(area)
    return shown(report, root), shown(protocol, root)


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
    for f in failed_attempts.failed_attempts(area):
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
                f"{run_dir.relative_to(area)}/ in {shown(area, repo)}",
                fix="discuss a run the area holds: `protocol-fill <PROTOCOL> "
                "--discuss <run> --why … --into <FILE>` writes the block again",
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
