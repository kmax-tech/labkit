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
from collections.abc import Iterable

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
from labkit.formats.gate import with_way_out
from labkit.formats.repo import layout_root, shown
from labkit.formats.runs import read_outputs
from labkit.formats.scope_sha import area_stamp
from labkit.formats.standard_contract import ANALYSIS_AUDIT

ROWS_HEAD, ROWS_TAIL = 50, 20  # what the instructions tell the auditor to read
ROW_WIDTH = 2000  # a longer row (a trace) is cut, marked, never dropped


#: the way out of a run's metrics.json that does not read: it is the run's own
_METRICS_AS_WRITTEN = (
    "restore it as the run wrote it (`git checkout HEAD -- <path>` where git "
    "holds it), or measure anew and audit that run"
)


class AuditError(RuntimeError):
    """No audit could be made, or none can be held to the area. WHY is the
    cause, FIX the way out (required where it is raised; None only at a
    site `tests/test_ways_out_data.py` exempts, with its reason); the
    message joins them as a gate line does (`gate.with_way_out`)."""

    def __init__(self, why: str, *, fix: str | None) -> None:
        super().__init__(with_way_out(why, fix))
        self.why = why
        self.fix = fix


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
        raise AuditError(
            f"{protocol.name}: head unreadable — {exc}",
            fix=f"repair the head as the sentence says (`protocol-check "
            f"{shown(protocol, Path.cwd())} --contract` shows its fields)",
        ) from exc
    if pid is None:
        return None, "the protocol id is still a placeholder"
    choice = bound_answering_run(area, pid)
    blocker, _ = choice.explain(promises.registers_ids(text))
    if blocker or choice.run_dir is None:
        return None, blocker.text if blocker else "no completed bound run"
    return choice.run_dir, ""


def run_rows(area: Path, run_dir: Path | None, why: str) -> list[tuple[str, str]]:
    """What MODE analysis is told to read of RUN_DIR, the answering run as
    `audited_run` chose it ONCE for both the prompt and the record: `(label,
    text)` per piece — the first ROWS_HEAD and last ROWS_TAIL lines of every
    output the run registered, numbered as `<n>: <row>`, its metrics.json,
    and its declared dependencies (`dependency_pieces`). One `(label, note)`
    pair says why there is nothing: WHY (no protocol id, no completed bound
    run), or no registered output."""
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
            raise AuditError(
                f"{run_dir.name} registered {entry.path}, which is gone",
                fix="restore it as the run wrote it (`git checkout HEAD -- <path>` "
                "where git holds it), or measure anew and audit that run",
            )
        name = shown(path, repo)
        out.append(rows_excerpt(path, name))
    metrics = runs.metrics_path(run_dir)
    if metrics.is_file():
        out.append(
            (f"FILE: {rel_run}/metrics.json", metrics.read_text(encoding="utf-8"))
        )
    out += dependency_pieces(run_dir)
    return out


#: how large a declared dependency may be to be shown whole: a JSON model of
#: a few weights is read, a pickled forest is named by its digest
DEPENDENCY_SHOW_MAX = 64_000


#: how a dependency piece's label opens, and how a piece not shown whole opens
DEPENDENCY_LABEL = "DEPENDENCY "
NOT_SHOWN = "not shown:"


def shown_files(pieces: Iterable[tuple[str, str]]) -> dict[str, str]:
    """`file:<recorded path>` → its piece's label, for every dependency piece
    of PIECES (`dependency_pieces`) shown whole — what a required `check:
    file:<path>` is found in. A file named but not shown is not there."""
    out: dict[str, str] = {}
    for label, text in pieces:
        if label.startswith(DEPENDENCY_LABEL) and not text.startswith(NOT_SHOWN):
            recorded = label.removeprefix(DEPENDENCY_LABEL).split(" (", 1)[0]
            out[f"{findings.FILE_CHECK}{recorded}"] = label
    return out


def check_evidence(
    metrics: dict | None, pieces: Iterable[tuple[str, str]]
) -> dict | None:
    """Where a finding's required check is looked up: METRICS (the run's
    metrics.json) and the files of PIECES shown whole (`shown_files`) —
    None when there is neither. One home for MODE analysis and
    report-check, so both find a check in the same place."""
    files = shown_files(pieces)
    if metrics is None and not files:
        return None
    return {**(metrics or {}), **files}


def dependency_pieces(run_dir: Path) -> list[tuple[str, str]]:
    """RUN_DIR's declared dependencies — its `data=` inputs recorded without
    rows (`provenance.BinaryInput`: a predictor, its weights) — as MODE
    analysis shows them: a UTF-8 file of at most DEPENDENCY_SHOW_MAX bytes
    whole while its digest is the one the run recorded; any other named
    with its digest and why it is not shown. In the repair case
    (2026-10-28) the follow-up could not confirm a repair against
    model.json, which no piece showed, and three decision reviews said
    insufficient. [] for a run without such inputs or a record that does
    not read (the record checks name that)."""
    cfg = runs.read_run_config(run_dir)
    if cfg is None:
        return []
    out: list[tuple[str, str]] = []
    for key, entry in sorted(cfg.data.items()):
        if (
            not isinstance(entry, dict)
            or "rows" not in entry
            or entry["rows"] is not None
        ):
            continue
        recorded, digest = str(entry.get("path")), str(entry.get("sha256"))
        label = f"{DEPENDENCY_LABEL}{recorded} ({key}, the run recorded sha {digest})"
        path = runs.resolve_recorded(recorded, run_dir)
        if not path.is_file():
            why = "a directory" if path.is_dir() else "gone from the tree"
            out.append((label, f"{NOT_SHOWN} {why}"))
            continue
        now = scope_sha.file_digest(path)[: len(digest)]
        if now != digest:
            out.append(
                (
                    label,
                    f"{NOT_SHOWN} changed since the run (sha {now} now), so not "
                    f"what the run read",
                )
            )
            continue
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            out.append((label, f"{NOT_SHOWN} not text — named by its digest"))
            continue
        if len(data) > DEPENDENCY_SHOW_MAX:
            out.append(
                (label, f"{NOT_SHOWN} {len(data)} bytes, above {DEPENDENCY_SHOW_MAX}")
            )
            continue
        out.append((label, text))
    return out


class RunShown(NamedTuple):
    """What MODE analysis shows of the answering run, taken once: the
    pieces the prompt renders (`run_rows`) and their digest, which the record
    carries as `shown_sha` and report-check recomputes — a metrics.json or
    output rows changed after the audit owe a new one (review 2026-10-20:
    the run id alone could not tell)."""

    pieces: tuple[tuple[str, str], ...]
    sha: str

    def evidence(self) -> dict | None:
        """Where this snapshot holds a required check (`check_evidence`):
        its metrics and its dependencies shown whole. Raises AuditError
        like `metrics`."""
        return check_evidence(self.metrics(), self.pieces)

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
                    raise AuditError(
                        f"{label[6:]}: not JSON ({exc})", fix=_METRICS_AS_WRITTEN
                    ) from exc
                if not isinstance(data, dict):
                    raise AuditError(
                        f"{label[6:]}: not a JSON object", fix=_METRICS_AS_WRITTEN
                    )
                return data
        return None


#: the label of the piece MODE analysis shows when the protocol declares
#: another run than the one it shows (`declared_piece`)
DECLARED_LABEL = "DECLARED RUN"


def declared_piece(run_dir: Path | None, declared: str | None) -> list[tuple[str, str]]:
    """What MODE analysis shows of the protocol's `[result] run` (DECLARED,
    `protocol_block.declared_run_shown`) beside RUN_DIR, the run it shows:
    nothing when the protocol declares none or that very run, else one
    piece naming the run declared. So a record binds a wrong declaration,
    and re-adopting moves the state the next audit follows a finding up in,
    while the first adoption of the run audited moves nothing (file-check
    case, 2026-10-28: a BLOCKER on the declared run, fixed by re-adopting,
    stayed held as fixed in the same state)."""
    shown = run_dir.name if run_dir is not None else None
    if declared is None or declared == shown:
        return []
    return [
        (
            DECLARED_LABEL,
            f"the protocol's [result] declares {declared}, not the run shown "
            f"here ({shown or 'none'})",
        )
    ]


def run_shown(area: Path, run_dir: Path | None, why: str, text: str) -> RunShown:
    """`run_rows` of RUN_DIR and the declared run of the protocol TEXT
    (`declared_piece`) as one snapshot, its digest taken over those pieces
    and the protocol's audited prose (`protocol_check.audited_texts`). The
    prose is not a piece: the prompt inlines the protocol whole. Binding it
    makes a corrected description (a count in Data / scope) a new state the
    next audit follows earlier findings up in; the fields written after the
    audit are not in it."""
    pieces = tuple(
        [
            *run_rows(area, run_dir, why),
            *declared_piece(run_dir, protocol_block.declared_run_shown(text)),
        ]
    )
    bound = runs.as_stored(pieces) + "\n" + protocol_check.audited_texts(text)
    return RunShown(pieces, scope_sha.digest(bound.encode("utf-8")))


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


def analysis_now(area: Path, text: str, run: Path) -> findings.AuditedState:
    """The state of AREA, the promises, the registration and the declared
    run of TEXT, and RUN as they are now (`findings.AuditedState`) — what
    an analysis record must bind to cover them. Raises AuditError (a
    registered output is gone), FileNotFoundError or ValueError (nothing to
    stamp, a promise block or a head unreadable)."""
    return findings.AuditedState(
        area_stamp(area)[0],
        promises.block_stamp(text),
        protocol_check.registration_stamp(text),
        run.name,
        run_shown(area, run, "", text).sha,
    )


def covering_analysis(area: Path, text: str, run: Path) -> list[findings.Record]:
    """The analysis records that saw AREA's code, the promises of TEXT and
    RUN (its rows and metrics as shown) as they are now (`analysis_now`).
    Raises what `analysis_now` raises, and FindingsError (a ValueError) on a
    findings file it cannot read."""
    records = [r for r in findings.area_records(area) if r.mode == ANALYSIS_AUDIT]
    return findings.covering_records(records, analysis_now(area, text, run))
