"""report_review_inputs — what a report review reads and how its record
names report and protocol, without a model call: the reviewer's prompt is
rendered from `review_pieces`, the record's fingerprint is taken over it,
and report-check takes it again to tell whether a review saw the state it
holds. Model-free, so the release gate reads it without loading a model
backend.
"""

from __future__ import annotations

from pathlib import Path

from labkit.checks.audit_binding import AuditError
from labkit.formats.area_state import AreaState, state_of
from labkit.formats.repo import path_kind
from labkit.formats.runs import metrics_text
from labkit.checks.report_blocks import Discussion, cited_run_ids
from labkit.formats import protocol_block
from labkit.formats import findings
from labkit.formats import failed_attempts
from labkit.formats.repo import layout_root, shown
from labkit.formats.runs import (
    MetricsError,
    RunConfig,
    as_stored,
    metrics_path,
    read_metrics,
    run_dirs,
    run_path,
    run_state,
)


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
    state: AreaState | None = None,
) -> list[tuple[str, str]]:
    """The (label, text) the reviewer reads of REPORT (its TEXT) under
    PROTOCOL (its PROTOCOL_TEXT) in AREA, in order: the report numbered,
    the run the protocol has adopted (or none), its DISCUSSED blocks (or
    none), the protocol, the `metrics.json` of every run of AREA the
    review concerns — the adopted one, each discussed one, each one the
    report cites — labelled with what it is (STATE, the area's state, is
    the caller's when it built one, else built here), every run of AREA in one line
    each (`runs_text`), the audits (`audits_text`).
    The one home of what a review saw: the prompt is rendered from it,
    the record's fingerprint is taken over it, and the gate takes it again
    to tell whether a review saw the state it holds. Raises AuditError
    when a discussed run has no `runs/<id>/` in AREA; FindingsError on an
    unreadable audit file; BlockError on a head that does not read."""
    repo = layout_root(area)
    adopted = protocol_block.declared_run(protocol_text)
    pieces: list[tuple[str, str]] = [
        (f"REPORT {shown(report, repo)}", numbered(text)),
        (
            "ADOPTED",
            f"run {adopted} — the protocol's adopted result"
            if adopted is not None
            else "none — the protocol has adopted no result",
        ),
        (
            "DISCUSSED",
            "\n".join(
                f"line {d.first}: run {d.run_id} — why: {d.why}" for d in discussed
            )
            or "none — the report discusses no run",
        ),
        (f"FILE: {shown(protocol, repo)}", protocol_text),
    ]
    held = state if state is not None else state_of(area)
    present = {rd.dir.name for rd in held.runs}
    for d in discussed:
        run_dir = run_path(area, d.run_id)
        if d.run_id not in present:
            raise AuditError(
                f"{report.name} discusses run {d.run_id}, and there is no "
                f"{run_dir.relative_to(area)}/ in {shown(area, repo)}",
                fix="discuss a run the area holds: `protocol-fill <PROTOCOL> "
                "--discuss <run> --why … --into <FILE>` writes the block again",
            )
    said = {d.run_id for d in discussed}
    runs = [adopted] if adopted is not None else []
    runs += [d.run_id for d in discussed]
    runs += [r for _, r in cited_run_ids(text) if r in present]
    for run_id in dict.fromkeys(runs):
        what = (
            "adopted"
            if run_id == adopted
            else "discussed"
            if run_id in said
            else "cited, not adopted"
        )
        run_dir = run_path(area, run_id)
        metrics = metrics_path(run_dir)
        shown_metrics = metrics_text(run_dir) if run_id in present else None
        pieces.append(
            (
                f"FILE: {shown(metrics, repo)} ({what})",
                shown_metrics
                if shown_metrics is not None
                else "no metrics.json in this run"
                if run_id in present
                else f"no {run_dir.relative_to(area)}/ — the run's directory is gone",
            )
        )
    cited = {r for _, r in cited_run_ids(text)}
    pieces.append(
        (
            "RUNS",
            runs_text(area, protocol_block.id_of(protocol_text), adopted, said, cited),
        )
    )
    pieces.append(("AUDITS", audits_text(area)))
    return pieces


#: how a setting a measurement's config lacks is shown and compared — not
#: `null`: a key left out and one set to null can mean different things
ABSENT = "absent"


def runs_text(
    area: Path,
    pid: str | None,
    adopted: str | None,
    discussed: set[str],
    cited: set[str],
) -> str:
    """Every run under AREA's `runs/`, oldest first, one line each: its
    state, kind, the protocol it was bound to (PID: this one), what the
    report makes of it (ADOPTED, DISCUSSED, CITED, or nothing), its commit
    and script, a repeat's or a derived run's parent, for a measurement the
    settings that vary across the measurements bound to PID, and its
    scalar metrics. The history
    a statement about "the" measurement is held against: a search the
    report does not name shows as runs of one protocol under varying
    settings, which a review that sees the adopted run alone lets pass. An
    unreadable run is a line saying so, never left out."""
    dirs = run_dirs(area)
    bound = [
        rd.config.config
        for rd in dirs
        if rd.config
        and rd.config.protocol.id == pid
        and rd.config.run_kind == "measurement"
    ]
    varying = sorted(
        k
        for k in {k for c in bound for k in c}
        if len({as_stored(c[k]) if k in c else ABSENT for c in bound}) > 1
    )
    lines: list[str] = []
    for rd in dirs:
        if rd.error is not None:
            lines.append(f"{rd.dir.name} · unreadable · {rd.error}")
        elif rd.config is not None:
            role = (
                "adopted"
                if rd.dir.name == adopted
                else "discussed"
                if rd.dir.name in discussed
                else "cited"
                if rd.dir.name in cited
                else "not in the report"
            )
            lines.append(_run_line(rd.dir, rd.config, pid, role, varying))
    return "\n".join(lines) or "no runs"


def _run_line(
    run_dir: Path, cfg: RunConfig, pid: str | None, role: str, varying: list[str]
) -> str:
    bound = cfg.protocol.id
    parts = [
        run_dir.name,
        run_state(run_dir, alive=False),
        cfg.run_kind,
        "this protocol"
        if bound == pid
        else f"bound to {bound}"
        if bound
        else "unbound",
        role,
        f"git {cfg.git}",
        cfg.script,
    ]
    if cfg.repeat_of is not None:
        parts.append(f"repeat of {cfg.repeat_of}")
    if cfg.derived_from is not None:
        parts.append(f"derived from {cfg.derived_from}")
    if cfg.run_kind == "measurement":
        settings = ", ".join(
            f"{k}={as_stored(cfg.config[k]) if k in cfg.config else ABSENT}"
            for k in varying
        )
        parts.append(
            f"settings varying across this protocol's measurements: {settings or 'none'}"
        )
    parts.append(_scalars(metrics_path(run_dir)))
    return " · ".join(parts)


def _scalars(metrics: Path) -> str:
    """The scalar entries of METRICS as `k=v` (`as_stored`), or why there
    are none."""
    if path_kind(metrics) != "file":
        return "no metrics.json"
    try:
        values = read_metrics(metrics)
    except MetricsError as exc:
        return f"metrics unreadable ({exc})"
    shown_values = ", ".join(
        f"{k}={as_stored(v)}"
        for k, v in values.items()
        if isinstance(v, (int, float, str))
    )
    return f"metrics: {shown_values or 'no scalar'}"
