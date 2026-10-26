"""audit_binding — what an analysis audit is held to: the answering run it
reads, what it was shown of that run, and which records saw the area as it
is now.

Two questions every caller must answer the same way, so they have one home
below the gates: `labkit-audit` chooses the run and takes the snapshot the
prompt renders and the record carries (`audited_run`, `run_shown`);
report-check and `protocol-fill --from-run` ask which analysis records
cover the code, the promise block, that run and that snapshot now
(`covering_analysis`, `analysis_now`). The digest is recomputed, never
copied: a metrics.json or output rows changed after the audit owe a new one.
Reads only; the records themselves are `findings`'.
"""

from __future__ import annotations

import json

from pathlib import Path
from typing import NamedTuple

from labkit.formats import (
    findings,
    promises,
    protocol_block,
    protocol_check,
    runs,
    scope_sha,
)
from labkit.formats.answering_run import bound_answering_run
from labkit.formats.repo import layout_root, shown
from labkit.formats.runs import read_outputs
from labkit.formats.scope_sha import area_stamp
from labkit.formats.standard_contract import ANALYSIS_AUDIT

ROWS_HEAD, ROWS_TAIL = 50, 20  # what the instructions tell the auditor to read
ROW_WIDTH = 2000  # a longer row (a trace) is cut, marked, never dropped


class AuditError(RuntimeError):
    """No audit could be made, or none can be held to the area — the cause is
    in the message."""


def audited_run(
    area: Path, protocol: Path, text: str | None = None
) -> tuple[Path | None, str]:
    """The run an analysis audit reads and its record is bound to — the
    answering run (`answering_run.bound_answering_run`, the one choice every gate
    holds the protocol to) read off the protocol file (or TEXT, the
    protocol as the caller's file state holds it), or `(None, why)`: no
    protocol id, no completed bound run, a blocker of the choice. Raises
    AuditError on a head it cannot read. report-check holds the record to
    the same choice (`report_check.checked`)."""
    if text is None:
        text = protocol.read_text(encoding="utf-8")
    try:
        pid = protocol_block.head(text).id
    except protocol_block.BlockError as exc:
        raise AuditError(f"{protocol.name}: head unreadable — {exc}") from exc
    if pid is None:
        return None, "the protocol id is still a placeholder"
    choice = bound_answering_run(area, pid)
    blocker, _ = choice.explain(promises.registers_ids(text))
    if blocker or choice.run_dir is None:
        return None, blocker or "no completed bound run"
    return choice.run_dir, ""


def run_rows(area: Path, run_dir: Path | None, why: str) -> list[tuple[str, str]]:
    """What MODE analysis is told to read of RUN_DIR, the answering run as
    `audited_run` chose it ONCE for both the prompt and the record: `(label,
    text)` per piece — the first ROWS_HEAD and last ROWS_TAIL lines of every
    output the run registered, numbered as `<n>: <row>`, and its
    metrics.json. One `(label, note)` pair says why there is nothing: WHY
    (no protocol id, no completed bound run), or no registered output."""
    repo = layout_root(area)
    if run_dir is None:
        return [("ROWS", f"no rows: {why}")]
    registered = read_outputs(run_dir)
    out: list[tuple[str, str]] = []
    rel_run = run_dir.resolve().relative_to(repo.resolve()).as_posix()
    if not registered:
        out.append((f"ROWS {rel_run}", "no rows: the run registered no output file"))
    for entry in registered or []:
        path = Path(entry.path)
        path = path if path.is_absolute() else repo / path
        if not path.is_file():
            raise AuditError(f"{run_dir.name} registered {entry.path}, which is gone")
        name = shown(path, repo)
        out.append(rows_excerpt(path, name))
    metrics = runs.metrics_path(run_dir)
    if metrics.is_file():
        out.append(
            (f"FILE: {rel_run}/metrics.json", metrics.read_text(encoding="utf-8"))
        )
    return out


class RunShown(NamedTuple):
    """What MODE analysis shows of the answering run, taken once: the
    pieces the prompt renders (`run_rows`) and their digest, which the record
    carries as `shown_sha` and report-check recomputes — a metrics.json or
    output rows changed after the audit owe a new one (review 2026-10-20:
    the run id alone could not tell)."""

    pieces: tuple[tuple[str, str], ...]
    sha: str

    def metrics(self) -> dict | None:
        """The run's metrics.json as this snapshot shows it — the very text
        the prompt renders, never the file read again — or None when the
        run showed none. Raises AuditError on a shown text that is no JSON
        object."""
        for label, text in self.pieces:
            if label.startswith("FILE: ") and label.endswith("/metrics.json"):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise AuditError(f"{label[6:]}: not JSON ({exc})") from exc
                if not isinstance(data, dict):
                    raise AuditError(f"{label[6:]}: not a JSON object")
                return data
        return None


def run_shown(area: Path, run_dir: Path | None, why: str) -> RunShown:
    """`run_rows` of RUN_DIR as one snapshot with its digest."""
    pieces = tuple(run_rows(area, run_dir, why))
    return RunShown(pieces, scope_sha.digest(runs.as_stored(pieces).encode("utf-8")))


def rows_excerpt(path: Path, name: str) -> tuple[str, str]:
    """`(label, text)` of one output file: its first ROWS_HEAD and last
    ROWS_TAIL lines as `<line>: <row>`, a gap marked by its size, a row
    longer than ROW_WIDTH cut and marked — never silently dropped."""
    lines = path.read_text(encoding="utf-8").splitlines()
    n = len(lines)
    shown = (
        range(n)
        if n <= ROWS_HEAD + ROWS_TAIL
        else [*range(ROWS_HEAD), *range(n - ROWS_TAIL, n)]
    )
    body: list[str] = []
    last = -1
    for i in shown:
        if i != last + 1:
            body.append(f"… {i - last - 1} line(s) not shown …")
        row = lines[i]
        if len(row) > ROW_WIDTH:
            row = row[:ROW_WIDTH] + f" … [{len(lines[i]) - ROW_WIDTH} more chars]"
        body.append(f"{i + 1}: {row}")
        last = i
    label = f"ROWS {name} ({n} line(s); the first {ROWS_HEAD} and last {ROWS_TAIL} are shown)"
    return label, "\n".join(body)


def analysis_now(
    area: Path, text: str, run: Path
) -> tuple[str, str, str, str, dict[str, str]]:
    """(code stamp, promise block stamp, run id, shown sha, registration) of
    AREA, the promises and the registration of TEXT and RUN as they are now
    — what an analysis record must carry to cover them. Raises AuditError (a
    registered output is gone), FileNotFoundError or ValueError (nothing to
    stamp, a promise block or a head unreadable)."""
    return (
        area_stamp(area)[0],
        promises.block_stamp(text),
        run.name,
        run_shown(area, run, "").sha,
        protocol_check.registration_stamp(text),
    )


def covering_analysis(area: Path, text: str, run: Path) -> list[findings.Record]:
    """The analysis records that saw AREA's code, the promises of TEXT and
    RUN (its rows and metrics as shown) as they are now (`analysis_now`).
    Raises what `analysis_now` raises, and FindingsError (a ValueError) on a
    findings file it cannot read."""
    records = [r for r in findings.area_records(area) if r.mode == ANALYSIS_AUDIT]
    return findings.covering_records(records, *analysis_now(area, text, run))
