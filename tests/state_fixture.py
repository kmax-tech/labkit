"""An area's state and audit evidence built from data, for rule tests
(docs/notes/2026-11-10-test-model.md, step 1).

`area_state` and `area_evidence` build `AreaState` and `AreaEvidence` as
the test writes them: every field it names is taken as given, every field it
leaves out is empty (no run, no protocol, no record, no git repository).
Nothing is derived and nothing repaired — `measured` and `run_facts` stay
what the test gives, even where they contradict `runs`; a test of that
derivation calls `area_state.assemble`. A check under test sees exactly the
state its test wrote down.

`run_dir` and `audit_record` build the parts a state and the evidence hold;
the defaults they fill are named at each and bear on no condition a check of
runs or records decides. `checked` builds report-check's gate-layer context
(`report_context.Checked`) for its gate tests; a check never receives it.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

from labkit.formats import findings
from labkit.formats.answering_run import RunFacts
from labkit.formats.area_state import TREE, AreaState, FileState, Measured
from labkit.formats.evidence import AreaEvidence
from labkit.formats import protocol_block
from labkit.formats.runs import RUNS_DIR, RunConfig, RunDir
from labkit.gates.report_context import Checked
from protocol_fixture import PID

#: the area every built state lies in unless the test names another; a
#: relative path no check opens
AREA = Path("area")


def area_state(
    *,
    area: Path = AREA,
    repo: Path | None = None,
    file_state: FileState = TREE,
    protocols: Sequence[Path] = (),
    protocol_texts: Mapping[Path, str] | None = None,
    adoption_pending: Collection[Path] = (),
    runs: Sequence[RunDir] = (),
    deleted: Sequence[RunDir] = (),
    history_unread: str = "",
    lost: Mapping[str, str] | None = None,
    run_facts: Sequence[RunFacts] = (),
    measured: Mapping[str, Measured] | None = None,
) -> AreaState:
    """The `AreaState` with exactly these fields, in the order given; the
    empty value for each one left out."""
    return AreaState(
        area=area,
        repo=repo,
        file_state=file_state,
        protocols=tuple(protocols),
        protocol_texts=dict(protocol_texts or {}),
        adoption_pending=frozenset(adoption_pending),
        runs=tuple(runs),
        deleted=tuple(deleted),
        history_unread=history_unread,
        lost=dict(lost or {}),
        run_facts=tuple(run_facts),
        measured=dict(measured or {}),
    )


def area_evidence(
    *,
    records: Sequence[findings.Record] = (),
    gaps: Sequence[str] = (),
    unreadable: Sequence[str] = (),
    changes: Sequence[tuple[str, str]] = (),
    ignored: Sequence[str] = (),
) -> AreaEvidence:
    """The `AreaEvidence` with exactly these fields; no review, report review
    or handover record — the fields a check of those adds when it needs
    them."""
    return AreaEvidence(
        records=tuple(records),
        gaps=tuple(gaps),
        unreadable=tuple(unreadable),
        changes=tuple(changes),
        ignored=tuple(ignored),
    )


def run_dir(
    name: str,
    *,
    area: Path = AREA,
    config: RunConfig | None = None,
    error: str | None = None,
    from_commit: str | None = None,
) -> RunDir:
    """The `RunDir` of run NAME under AREA's `runs/`, its record CONFIG (None:
    the directory holds no config.json), ERROR and FROM_COMMIT as given."""
    return RunDir(area / RUNS_DIR / name, config, error, from_commit)


def audit_record(
    name: str,
    *,
    mode: str,
    run_id: str | None,
    found: Sequence[findings.Finding] = (),
    area: Path = AREA,
    protocol_id: str = PID,
) -> findings.Record:
    """The audit record `audits/NAME` of AREA in MODE, naming RUN_ID as the
    run it read (None for a preflight record, `findings.NO_RUN` for an
    analysis of no run), holding FOUND. The binding fields — date, model,
    the code, block and shown digests, the registration, the verdict — are
    fixed placeholders: what an audit was bound to bears on no check of
    which run a record names or which finding stands open."""
    return findings.Record(
        path=area / findings.DIR / name,
        date="2026-11-10",
        mode=mode,
        model="test-model",
        scope_sha="0" * 12,
        block_sha="0" * 12,
        registration=(),
        run_id=run_id,
        shown_sha=None if run_id is None else "0" * 12,
        verdict=(0, 0, 0),
        findings=tuple(found),
        protocol_id=protocol_id,
    )


def checked(
    text: str,
    *,
    run: Path | None,
    why: str = "",
    area: Path = AREA,
    protocol: str = "PROTOCOL-x.md",
    file_state: FileState = TREE,
    state: AreaState | None = None,
    evidence: AreaEvidence | None = None,
) -> Checked:
    """The `Checked` of one report check over the protocol TEXT in AREA
    (its head read from TEXT, `[result]` as TEXT declares it), the answering
    RUN or None with WHY, FILE_STATE, and STATE and EVIDENCE as given — the
    empty `area_state()` and `area_evidence()` when left out. Raises
    BlockError as `protocol_block.head` does for a head that does not read."""
    return Checked(
        area=area,
        repo=area,
        protocol=area / protocol,
        text=text,
        head=protocol_block.head(text),
        file_state=file_state,
        declared=protocol_block.declared_run(text),
        declaration_gap=None,
        run=run,
        why=why,
        area_state=state or area_state(area=area),
        evidence=evidence or area_evidence(),
    )
