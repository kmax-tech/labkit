"""The exploration station of `report_check`: for a confirmation that names
its exploration (`[explored_in]`), the runs of the exploration's area that
recorded an input digest a run of the confirmation recorded too and that
the covering analysis audit was not shown, because they started after it
began (`later_use_findings`). Static evidence, warnings only: an equal
digest is byte-identical content, never a proof that the confirmation depends on
the run — and no shared digest is no proof that it does not.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from labkit.formats import attempts, findings, protocol_block
from labkit.formats.area_state import CLOCKS_ASSUMED, AreaState, state_of
from labkit.formats.commands import audit_command
from labkit.formats.exploration_state import (
    SharedInput,
    basis_closure,
    not_shown_since,
    shared_inputs,
)
from labkit.formats.gate import STATIC_EVIDENCE, WARNING, GateFinding, cited_rule
from labkit.checks.audit_binding import covering_analysis
from labkit.gates.report_context import Checked


LAB_050 = cited_rule("LAB-050 Analysis audit before reporting")


def audit_began(
    records: Sequence[findings.Record], journal: Sequence[attempts.Attempt]
) -> datetime | None:
    """When the latest of RECORDS' audits began (local time): the start of
    the attempt of JOURNAL whose end names the record's file, the latest
    over RECORDS. None when JOURNAL names no attempt for any of them, or
    names one whose start does not read as a time. An audit's attempt
    states the time its command began reading the area, before the prompt
    was built (`audit.main`), so a run started at or after it is taken as
    not shown — also one the prompt happened to hold. The bound is a time,
    not the audit's documents: a run takes its id's time before runlog
    writes its record, and an audit that begins reading between the two
    was not shown the run although the run's time lies before. Pure."""
    by_file = {a.file: a.started for a in journal if a.file}
    began: list[datetime] = []
    for r in records:
        started = by_file.get(r.path.name)
        if started is None:
            continue
        try:
            began.append(datetime.fromisoformat(started))
        except ValueError:
            return None
    return max(began, default=None)


def use_after_audit_findings(ctx: Checked) -> list[GateFinding]:
    """`later_use_findings` for CTX, a protocol whose result an analysis
    audit covers: against the start of the latest covering record's
    attempt (`audit_began`; a journal that does not read gives none, and
    then no run is taken as shown). [] without `[explored_in]` or an
    answering run. Raises BlockError on an `[explored_in]` that does not
    read, what `covering_analysis` raises, RuntimeError when git fails."""
    if ctx.run is None or protocol_block.explored_in(ctx.text) is None:
        return []
    covering = covering_analysis(ctx.area, ctx.text, ctx.run)
    try:
        journal = attempts.read_journal(ctx.area)
    except attempts.AttemptError:
        journal = []  # no start reads: `audit_began` gives None
    began = audit_began(covering, journal)
    return later_use_findings(ctx.area, ctx.protocol, ctx.text, ctx.area_state, began)


def later_use_findings(
    area: Path,
    protocol: Path,
    text: str,
    state: AreaState,
    began: datetime | None,
) -> list[GateFinding]:
    """One warning per run of the exploration's area that shares an input
    digest with a run of the confirmation PROTOCOL of AREA (its text TEXT,
    the area's state STATE) and that an audit begun at BEGAN was not shown
    (`exploration_state.not_shown_since`; BEGAN None: no run is taken as
    seen). The search is the audit's own (`exploration_state.shared_inputs`
    over the runs of the exploration's area, read from the working tree),
    so a new analysis audit is shown every run named here — the way out.
    [] without `[explored_in]`, without a stamped id, and for a link whose
    id names no one protocol of the repo (the area stamp says that).
    Raises BlockError on an `[explored_in]` that does not read,
    RuntimeError when git fails."""
    link = protocol_block.explored_in(text)
    pid = protocol_block.head(text).id
    if link is None or pid is None:
        return []
    hits = protocol_block.repo_protocol_ids(area).get(link.protocol, [])
    if len(hits) != 1:
        return []
    theirs = hits[0].parent
    shared = shared_inputs(
        state.measured_of(pid).runs,
        state_of(theirs).runs,
        {m.run_id for m in basis_closure(theirs, link.run)},
    )
    by_run: dict[str, list[SharedInput]] = {}
    for s in not_shown_since(shared, began):
        by_run.setdefault(s.exploring_run, []).append(s)
    audit = audit_command(area, "--mode", "analysis", protocol=protocol)
    since = (
        f"started after the analysis audit that covers this result began "
        f"({began.isoformat(timespec='seconds')}; {CLOCKS_ASSUMED})"
        if began is not None
        else "the attempt journal gives no start of the analysis audit that "
        "covers this result (no entry names its record, or the journal or the "
        "time does not read), so no run is taken as shown to it"
    )
    return [
        GateFinding(
            WARNING,
            f"data use after the audit: run {run} of {theirs.name} recorded "
            f"{_same_files(pairs)} — {since}. The run is taken as not shown to that audit. "
            f"An equal sha256 is byte-identical content, not necessarily the same "
            f"file or origin; whether the confirmation is "
            f"independent of that run is not decided here, either way",
            fix=f"have the auditor judge it: `{audit}` shows every input digest "
            f"a run of that area shares with a run of this protocol",
            evidence_kind=STATIC_EVIDENCE,
            rule=LAB_050,
        )
        for run, pairs in by_run.items()
    ]


def _same_files(pairs: Sequence[SharedInput]) -> str:
    """The inputs of one exploring run that PAIRS name, each with the
    confirming run's input holding the same bytes."""
    return "; ".join(
        f"its input {s.exploring_key} with the sha256 of {s.confirming_key} "
        f"of run {s.confirming_run} ({s.sha256[:12]})"
        for s in pairs
    )
