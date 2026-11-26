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
from dataclasses import dataclass
from collections.abc import Callable, Iterable

from pathlib import Path
from typing import NamedTuple

from labkit.formats.commands import repair_head_way
from labkit.formats.commands import (
    measure_anew,
    Command,
    checkout_command,
    handover_command,
    report_shown,
    register_anew,
)
from labkit.formats import digests
from labkit.formats import (
    audit_gaps,
    findings,
    required_check,
    followup,
    jsonl,
    promises,
    protocol_block,
    protocol_check,
    runs,
)
from labkit.checks.origin_check import origin_piece
from labkit.checks.protocol_runs import (
    NOT_SHOWN,
    label_check,
    protocol_runs_pieces,
)
from labkit.formats.area_state import AreaState, gone_run_restore
from labkit.formats.evidence import AreaEvidence
from labkit.formats.gate import LAB_015
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    TECHNICAL_RULE,
    WARNING,
    GateFinding,
    blocker,
    with_way_out,
)
from labkit.formats.protocol_then import as_measured, bound_protocol_file
from labkit.formats.repo import (
    git_root,
    layout_root,
    only_protocol,
    path_kind,
    rel_posix,
    shown,
)
from labkit.formats.runs import read_outputs
from labkit.formats.scope_sha import area_stamp
from labkit.formats.standard_contract import ANALYSIS_AUDIT

ROWS_HEAD, ROWS_TAIL = 50, 20  # what the instructions tell the auditor to read
ROW_WIDTH = 2000  # a longer row (a trace) is cut, marked, never dropped


#: the way out of a run's metrics.json that does not read: it is the run's own
_METRICS_AS_WRITTEN = (
    f"restore it as the run wrote it (`{checkout_command('<path>')}` where git "
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


def audited_run(state: AreaState, protocol: Path, text: str) -> tuple[Path | None, str]:
    """The run an analysis audit reads and its record is bound to — the
    answering run (`area_state.Measured.answering`, the one choice every
    gate holds the protocol to; STATE the area's state, built once by the
    caller) read off the protocol file (or TEXT, the protocol as the
    caller's file state holds it), or `(None, why)`: no protocol id, no
    completed bound run, a blocker of the choice. Raises AuditError on a
    head it cannot read. report-check holds the record to the same choice
    (`report_context.checked`)."""
    try:
        pid = protocol_block.head(text).id
    except protocol_block.BlockError as exc:
        raise AuditError(
            f"{protocol.name}: head unreadable — {exc}",
            fix=repair_head_way(protocol),
        ) from exc
    if pid is None:
        return None, "the protocol id is still a placeholder"
    choice, blocker, _ = state.measured_of(pid).told(text)
    if blocker or choice.run_dir is None:
        return None, blocker.text if blocker else "no completed bound run"
    return choice.run_dir, ""


def run_rows(
    area: Path,
    run_dir: Path | None,
    why: str,
    requests: Iterable[followup.DiffAsked] = (),
) -> list[tuple[str, str]]:
    """What MODE analysis is told to read of RUN_DIR, the answering run as
    `audited_run` chose it ONCE for both the prompt and the record: `(label,
    text)` per piece — the first ROWS_HEAD and last ROWS_TAIL lines of every
    output the run registered, numbered as `<n>: <row>`, its metrics.json,
    its declared dependencies (`dependency_pieces`), its input origins
    with their state now (`origin_check.origin_piece`) and the protocol each
    origin run was bound to as it saw it then
    (`source_protocol_pieces`), and every run of those protocols with the
    diffs REQUESTS asks for (`protocol_runs_pieces`). The dependency, origin and source protocol
    pieces are absent when RUN_DIR's input record does not read: the record
    checks name that, so absent here is no "nothing to judge". One `(label, note)`
    pair says why there is nothing: WHY (no protocol id, no completed bound
    run), or no registered output."""
    repo = layout_root(area)
    if run_dir is None:
        return [("ROWS", f"no rows: {why}")]
    registered = read_outputs(run_dir)
    out: list[tuple[str, str]] = []
    rel_run = rel_posix(run_dir, repo)
    if not registered:
        out.append((f"ROWS {rel_run}", "no rows: the run registered no output file"))
    for entry in registered or []:
        path = Path(entry.path)
        path = path if path.is_absolute() else repo / path
        if path_kind(path) != "file":
            raise AuditError(
                f"{run_dir.name} registered {entry.path}, which is gone",
                fix=_METRICS_AS_WRITTEN,
            )
        name = shown(path, repo)
        out.append(rows_excerpt(path, name))
    shown_metrics = runs.metrics_text(run_dir)
    if shown_metrics is not None:
        out.append((metrics_label(rel_run), shown_metrics))
    out += dependency_pieces(run_dir)
    out += origin_piece(area, run_dir)
    out += source_protocol_pieces(area, run_dir)
    out += protocol_runs_pieces(area, run_dir, requests)
    return out


def metrics_label(rel_run: str) -> str:
    """The label of the piece that shows a run's metrics.json, REL_RUN the
    run's directory as the prompt names it. `is_metrics_label` finds the
    piece again by it."""
    return f"FILE: {rel_run}/{runs.METRICS_FILE}"


def is_metrics_label(label: str) -> bool:
    """Whether LABEL is a `metrics_label` — the piece `RunShown.metrics`
    reads the shown metrics from."""
    return label.startswith("FILE: ") and label.endswith(f"/{runs.METRICS_FILE}")


#: how the label of the piece MODE analysis shows of one origin run's
#: protocol opens — the protocol an input's source was measured under, the
#: source being its origin run (`origin_check`); the run's id follows
#: (`source_protocol_pieces`)
SOURCE_PROTOCOL_LABEL = "SOURCE PROTOCOL "

#: what a source protocol shown is, and what it is not
SOURCE_THEN = (
    "the question, criteria and method this origin run was measured under, as "
    "they stood when it started — evidence of the input's source, not the "
    "conclusion of the run audited here (its own protocol states that), and "
    "not the origin run's protocol as it reads today"
)
#: what a source protocol shown for a preparation origin is: context, not
#: what the preparation was measured under — it reports no result and owes
#: none of the text's promises (LAB-043 Runs go through `runlog`)
PREPARATION_THEN = (
    "the text this preparation run was bound to, as it stood when it started — "
    "context only: a preparation reports no result and is held to none of its "
    "promises; not the conclusion of the run audited here (its own protocol "
    "states that), and not the protocol as it reads today"
)

#: how a source protocol that cannot be read back is told
NOT_RECONSTRUCTED = "not reconstructable:"
NO_TEXT_IN_ITS_PLACE = (
    "today's text is not shown in its place; a judgement that needs the origin "
    "run's question, criteria or method names it as missing"
)
#: the same for a preparation origin: it owes none of its text's promises,
#: so no judgement waits on the text (PREPARATION_THEN)
NO_TEXT_OF_A_PREPARATION = (
    "today's text is not shown in its place; a preparation reports no result "
    "and owes none of its text's promises, so no judgement waits on that text"
)


def source_protocol_pieces(area: Path, run_dir: Path) -> list[tuple[str, str]]:
    """What MODE analysis shows of the protocol each origin run of RUN_DIR's
    inputs was bound to: one `(label, text)` piece per origin run, in
    the inputs' order — the protocol as that run saw it when it started,
    its recorded commit with its uncommitted.patch (`source_protocol_then`),
    marked as the origin run's then (SOURCE_THEN; for a preparation
    PREPARATION_THEN, context it owes nothing of), never the protocol as it
    reads now and never a newer run's; the text once, a later origin run
    that saw the same text pointing to it. Where it cannot be read back the
    piece says why (NOT_RECONSTRUCTED) and shows no other text, with what
    that leaves the judgement (NO_TEXT_IN_ITS_PLACE, for a preparation
    NO_TEXT_OF_A_PREPARATION) — a
    preparation still named one (`SourceProtocolThen.role`), so a missing
    text never turns it into a measured source —, the same
    diagnosis whether finalize holds the run for it
    (`source_protocol_finding`) or not. [] for a run without an input from
    an origin run, or whose input record does not read (the record checks
    name that). Reads files and git, writes nothing."""
    try:
        entries = runs.read_data(run_dir) or []
    except runs.ArtefactError:
        return []  # a record that does not read: the record checks name it
    origins = dict.fromkeys(e.origin_run for e in entries if e.origin_run is not None)
    root = git_root(area)
    # a text shown → the origin run it was shown for, and whether a preparation
    first_with: dict[str, tuple[str, bool]] = {}
    out: list[tuple[str, str]] = []
    for run_id in origins:
        then = source_protocol_then(area, run_id, root)
        label = f"{SOURCE_PROTOCOL_LABEL}{run_id}"
        what = PREPARATION_THEN if then.preparation else SOURCE_THEN
        if then.text is None:
            missing = (
                NO_TEXT_OF_A_PREPARATION if then.preparation else NO_TEXT_IN_ITS_PLACE
            )
            out.append((label, f"{NOT_RECONSTRUCTED} {then.where} — {missing}"))
        elif then.text in first_with:
            first, first_preparation = first_with[then.text]
            same = (
                f"{then.where}: the same text as under {SOURCE_PROTOCOL_LABEL}{first}"
            )
            # the first piece's sentence names that run's role; a run of the
            # other role (preparation or not) says its own
            differs = then.preparation != first_preparation
            out.append((label, f"{same} — {what}" if differs else same))
        else:
            first_with[then.text] = (run_id, then.preparation)
            out.append((label, f"{then.where} — {what}\n\n{then.text}"))
    return out


@dataclass(frozen=True)
class SourceProtocolThen:
    """The protocol an origin run was bound to, as it saw it when it
    started (`source_protocol_then`).

    Attributes:
        run_id: The origin run.
        bound: True when the run recorded a protocol id, so its question,
            criteria and method were registered and their text then is
            owed; False when it recorded none — no protocol was registered
            for it; None when its record does not
            stand or read, so whether one is owed is unknown (the origin
            check names that record, `origin_check.origin_gap`).
        preparation: True when the run's record says `run_kind =
            "preparation"`: it reports no result and owes none of its
            text's promises, bound or not (LAB-043 Runs go through
            `runlog`); its text is still read back. False when the record
            names another kind, and when it does not stand or read
            (`bound` None: the kind is unknown, and every sentence says
            so rather than calling it a measurement).
        text: The protocol's text then; None when it cannot be read back.
        where: Where TEXT was read from, or why it cannot be; it names the
            run by its `role`.
    """

    run_id: str
    bound: bool | None
    preparation: bool
    text: str | None
    where: str

    @property
    def role(self) -> str:
        """How every sentence names the run (`origin_role`)."""
        return origin_role(self.preparation)

    @property
    def basis(self) -> str:
        """What the text is to the run (`origin_basis`)."""
        return origin_basis(self.preparation)


def origin_role(preparation: bool) -> str:
    """How every sentence about an origin run names it: "preparation run"
    for a PREPARATION, else "origin run" — a preparation stays recognisable
    where its text is missing."""
    return "preparation run" if preparation else "origin run"


def origin_basis(preparation: bool) -> str:
    """What its bound text is to an origin run: "bound to" for a
    PREPARATION, which was measured under nothing; else "measured under"."""
    return "bound to" if preparation else "measured under"


def source_protocol_then(
    area: Path, run_id: str, root: Path | None
) -> SourceProtocolThen:
    """The protocol origin run RUN_ID of AREA was bound to, as it saw it
    when it started (`protocol_then.as_measured`: its recorded commit
    with its uncommitted.patch, held to the promise block it recorded),
    found by the run's protocol id — the protocol carrying it now, else the
    path the run recorded, and at that commit by the id again. No text, the
    reason in WHERE: no directory of that id, a record that does not read
    or is missing, a run bound to no protocol, AREA in no repository (ROOT
    None), or `as_measured`'s causes — a run started from a changed tree
    whose uncommitted.patch is gone among them. Never the protocol's text
    as it stands. Reads files and git. Raises RuntimeError when git
    fails."""
    run_dir = runs.runs_path(area) / run_id
    if path_kind(run_dir) != "dir":
        return SourceProtocolThen(
            run_id,
            None,
            False,
            None,
            f"origin run {run_id} is gone (no run of that id under runs/)",
        )
    rd = runs.read_run_dir(run_dir)
    if rd.error is not None:
        return SourceProtocolThen(
            run_id, None, False, None, f"origin run {run_id} does not read: {rd.error}"
        )
    if rd.config is None:  # the directory stands, its config.json does not
        return SourceProtocolThen(
            run_id,
            None,
            False,
            None,
            f"origin run {run_id} has no record (no config.json in runs/{run_id}/)",
        )
    binding = rd.config.protocol
    preparation = rd.config.run_kind == runs.PREPARATION
    role = origin_role(preparation)
    if binding.id is None:
        return SourceProtocolThen(
            run_id,
            False,
            preparation,
            None,
            f"{role} {run_id} was started bound to no protocol: no question, "
            f"criteria or method was registered for it",
        )
    if root is None:
        return SourceProtocolThen(
            run_id,
            True,
            preparation,
            None,
            f"{role} {run_id}: the area lies in no git repository, so no "
            f"commit holds what it was {origin_basis(preparation)}",
        )
    protocol = bound_protocol_file(area, binding.id, binding.path)
    text, where = as_measured(protocol, rd, root, role=role)
    return SourceProtocolThen(run_id, True, preparation, text, where)


def source_protocol_finding(then: SourceProtocolThen, area: Path) -> GateFinding | None:
    """The blocker when the protocol a bound origin run was bound to
    cannot be read back (THEN, `source_protocol_then`): the audit of a run
    of AREA computed from it cannot be shown the source's text, and
    today's text does not stand in. None when the text reads, and
    for a run that recorded no protocol (`bound` False) — nothing was
    registered to read back, so it owes none; a run whose
    record does not stand (`bound` None) is held, since whether a text is
    owed is unknown. The auditor is told either way
    (`source_protocol_pieces`). The way out restores the evidence or
    measures anew; a technical contract of the record, a guaranteed
    blocker."""
    if then.text is not None or then.bound is False:
        return None
    # a record that does not stand leaves the run's kind unknown: say that,
    # not what the text would have been to it
    told = (
        f"the record of origin run {then.run_id} does not stand, so whether it "
        f"owes a protocol text, and which, is unknown — {then.where}"
        if then.bound is None
        else f"the protocol {then.role} {then.run_id} was {then.basis} cannot be "
        f"read back — {then.where}"
    )
    return blocker(
        told,
        fix=f"restore what holds it — the commit (`git fetch`), the run's "
        f"uncommitted.patch or the protocol's history, from git or a backup — "
        f"or, with the right sources, {measure_anew(area)}; never show or "
        f"write today's text in its place",
        rule=TECHNICAL_RULE,
    )


#: how large a declared dependency may be to be shown whole: a JSON model of
#: a few weights is read, a pickled forest is named by its digest
DEPENDENCY_SHOW_MAX = 64_000


#: how a dependency piece's label opens; a piece not shown whole opens
#: with NOT_SHOWN, as a requested diff's does
DEPENDENCY_LABEL = "DEPENDENCY "


def shown_files(pieces: Iterable[tuple[str, str]]) -> dict[str, str]:
    """`file:<recorded path>` → its piece's label, for every dependency piece
    of PIECES (`dependency_pieces`) shown whole — what a required `check:
    file:<path>` is found in —, and `diff:<old>..<new>[:<path>]` → its
    label for every requested diff shown (`protocol_runs.requested_pieces`).
    A file or diff named but not shown is not there."""
    out: dict[str, str] = {}
    for label, text in pieces:
        if text.startswith(NOT_SHOWN):
            continue
        if label.startswith(DEPENDENCY_LABEL):
            recorded = label.removeprefix(DEPENDENCY_LABEL).split(" (", 1)[0]
            out[f"{required_check.FILE_CHECK}{recorded}"] = label
        elif (asked := label_check(label)) is not None:
            out[asked] = label
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
    with its digest and why it is not shown — so a repair can be confirmed
    against the file itself (a model.json). [] for a run without such
    inputs or a record that does not read (the record checks name that)."""
    try:
        entries = runs.read_data(run_dir) or []
    except runs.ArtefactError:
        return []  # a record that does not read: the record checks name it
    out: list[tuple[str, str]] = []
    for entry in sorted(entries, key=lambda e: e.key):
        if entry.rows is not None:
            continue  # a text input: its rows stand in the ROWS pieces
        recorded, digest = entry.recorded, entry.sha256
        label = (
            f"{DEPENDENCY_LABEL}{recorded} ({entry.key}, the run recorded sha {digest})"
        )
        path = runs.resolve_recorded(recorded, run_dir)
        kind = path_kind(path)
        if kind != "file":
            why = "a directory" if kind == "dir" else "gone from the tree"
            out.append((label, f"{NOT_SHOWN} {why}"))
            continue
        now = digests.file_digest(path)[: len(digest)]
        if now != digest:
            out.append(
                (
                    label,
                    f"{NOT_SHOWN} changed since the run (sha {now} now), so not "
                    f"what the run read",
                )
            )
            continue
        data = digests.file_bytes(path)
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
    output rows changed after the audit owe a new one (the run id alone
    cannot tell)."""

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
            if is_metrics_label(label):
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
    while the first adoption of the run audited moves nothing (without the
    piece, a BLOCKER on the declared run that re-adopting fixes stays held
    in an unchanged state)."""
    shown = run_dir.name if run_dir is not None else None
    if declared is None or declared == shown:
        return []
    return [
        (
            DECLARED_LABEL,
            f"the protocol's [result] names {declared}, not the run shown "
            f"here ({shown or 'none'})",
        )
    ]


def run_shown(
    area: Path,
    run_dir: Path | None,
    why: str,
    text: str,
    also: Iterable[findings.FixVerdict] = (),
) -> RunShown:
    """`run_rows` of RUN_DIR and the declared run of the protocol TEXT
    (`declared_piece`) as one snapshot, its digest taken over those pieces
    and the protocol's audited prose (`protocol_check.audited_texts`). The
    prose is not a piece: the prompt inlines the protocol whole. Binding it
    makes a corrected description (a count in Data / scope) a new state the
    next audit follows earlier findings up in; the fields written after the
    audit are not in it. The diffs the protocol's decided findings ask for
    (`followup.diff_requests`) are among the pieces, so deciding one makes
    the state the follow-up shows them in; ALSO are the verdicts of a
    record about to be written, which binds the state after them (a
    request it judged no longer shown whole). Raises AuditError when the
    area's records do not read."""
    pid = protocol_block.id_of(text)  # None asks for nothing
    try:
        requests = followup.diff_requests(followup.protocol_records(area, pid), also)
    except findings.FindingsError as exc:
        raise AuditError(str(exc), fix=findings.record_way(area)) from exc
    pieces = tuple(
        [
            *run_rows(area, run_dir, why, requests),
            *declared_piece(run_dir, protocol_block.declared_run_shown(text)),
        ]
    )
    bound = runs.as_stored(pieces) + "\n" + protocol_check.audited_texts(text)
    return RunShown(pieces, digests.digest(bound.encode("utf-8")))


def rows_excerpt(path: Path, name: str) -> tuple[str, str]:
    """`(label, text)` of one output file: its first ROWS_HEAD and last
    ROWS_TAIL lines as `<line>: <row>`, a gap marked by its size, a row
    longer than ROW_WIDTH cut and marked — never silently dropped."""
    lines = jsonl.lines_of(path)
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
    return audit_gaps.covering_records(records, analysis_now(area, text, run))


#: the word after an open audit finding's line, in a gate finding and in
#: finalize's note on a NOTE, and the rule that owes the decision: the
#: finding records it, the note cites it with `gate.with_rule`
UNDECIDED = "undecided"
UNDECIDED_RULE = LAB_015


def check_audit_records_read(
    state: AreaState, *, evidence: AreaEvidence
) -> list[GateFinding]:
    """A blocker per audit record of EVIDENCE that does not read
    (`AreaEvidence.unreadable`, its sentence): a record nobody can read is not
    "no findings". The way out restores it or audits again
    (`findings.record_way` for the area of STATE). [] when every record
    reads. That a record reads is its format's condition, not the
    standard's (TECHNICAL_RULE)."""
    return [
        blocker(why, fix=findings.record_way(state.area), rule=TECHNICAL_RULE)
        for why in evidence.unreadable
    ]


def check_audit_findings_decided(
    evidence: AreaEvidence,
    *,
    protocol_id: str | None,
    way_out_of: Callable[[findings.OpenFinding], str],
) -> list[GateFinding]:
    """finalize's row of `findings.open_findings`' table: every finding
    still `open`, any mode, in those of EVIDENCE's records that audited the
    protocol with stamped id PROTOCOL_ID (`followup.records_of`; None, a
    head without one, has no record), as a gate finding of its record's
    grade (LAB-015 Preflight audit before freezing) — a BLOCKER blocks with
    the way out WAY_OUT_OF gives for it, a WARNING warns. A NOTE is no gate
    finding and gives none: the gate tells it. [] when every finding of
    them is decided. A finding on another protocol of the area is that
    protocol's to decide and holds nothing here; a change of the area's
    code is held for every protocol by its own audit coverage, not by this.

    The station hands the way out in (`findings.decide_way` for its area and
    protocol): the printed `--decide` line names the protocol where the
    area holds several, and `commands.audit_command`, the one home of that
    choice, lists the area to know."""
    out: list[GateFinding] = []
    own = followup.records_of(evidence.records, protocol_id)
    for u in findings.open_findings(own):
        line = f"{u.line} — {UNDECIDED}"
        if u.grade == BLOCKER:
            out.append(blocker(line, fix=way_out_of(u), rule=UNDECIDED_RULE))
        elif u.grade == WARNING:
            out.append(
                GateFinding(
                    WARNING, line, rule=UNDECIDED_RULE, evidence_kind=GUARANTEED
                )
            )
    return out


def check_audited_runs_kept(
    state: AreaState, *, evidence: AreaEvidence
) -> list[GateFinding]:
    """A blocker per analysis record of EVIDENCE that names a run STATE no
    longer holds (`audit_gaps.records_of_gone_runs` over `state.runs`): the
    record refers to a run that cannot be read, a technical contract — no
    rule of the standard states that an audited run is kept —, and the
    record of a run deleted after its audit would otherwise read as
    "every finding decided". [] when every named run stands; a record of no
    run (`findings.NO_RUN`) and a preflight record name none. The way out is
    `gone_run_way`'s. Pure: reads STATE and EVIDENCE only — but the way out
    names the protocol as the working directory reaches it (`repo.shown`
    resolves the path)."""
    known = {rd.dir.name for rd in state.runs}
    out: list[GateFinding] = []
    for rec in audit_gaps.records_of_gone_runs(list(evidence.records), known):
        assert rec.run_id is not None  # records_of_gone_runs keeps only named runs
        way, handover = gone_run_way(state, rec.run_id)
        out.append(
            blocker(
                f"{rec.path.name}: names {rec.run_id} as the run it read, and "
                f"there is no runs/{rec.run_id}/ in this area — the run the "
                f"record refers to cannot be read",
                fix=way,
                step=handover,
                rule=TECHNICAL_RULE,
            )
        )
    return out


def gone_run_way(state: AreaState, run_id: str) -> tuple[str, Command]:
    """The way out of an audit record whose run RUN_ID is gone from the area
    of STATE, and the handover it names as the finding's step: put it back
    where git holds it (STATE's `deleted`: the commit that held it last,
    `area_state.gone_run_restore`), else hand the area over naming the
    loss, or register anew. Measuring again lifts nothing — the record
    stays and names the gone run —, so the way out never offers it. The
    handover goes into the report the protocol's head registers, read from
    STATE's text of it (a pure check opens no file), else `REPORT.md`."""
    protocol = only_protocol(state.protocols) or state.area / "PROTOCOL-<name>.md"
    try:
        text = state.text_of(protocol)  # keyed by the resolved path
    except ValueError:
        text = None  # no protocol, or several: the placeholder's default
    report = (
        report_shown(text, state.repo)
        if text is not None and state.repo is not None
        else None
    )
    handover = handover_command(protocol, report or "REPORT.md")
    held_back = next((rd for rd in state.deleted if rd.dir.name == run_id), None)
    put_back = (
        f"put it back where git holds it ({gone_run_restore(held_back)}); else"
        if held_back is not None
        else "no commit holds it:"
    )
    return (
        f"{put_back} it is lost, and a new run "
        f"does not lift this — hand the area over naming the loss "
        f"(`{handover}`), or {register_anew()}"
    ), handover
