"""exploration_state — the state of an exploration a confirmation names
(`[explored_in]`), as the area stamp follows it: which runs the named run
rests on (`basis_closure`: the origin runs of its inputs and, through each
run's step, its basis — transitively), the three parts a confirming audit
binds (`named_state`: that basis, the exploratory protocol's adoption and
its Conclusion), which input digests a run of the confirmation shares
with a run of the exploration's area (`shared_inputs`), and which of those an audit was not shown, by its start
(`not_shown_since`). What the stamp covers (`scope_sha.exploration_basis`),
the confirming audit is shown (`audit_prompt.exploration_evidence`) and
report-check warns of after it (`report_exploration.later_use_findings`).

Whether a link is valid is `exploration_link`'s, not asked here: the state
is read for any pair a head names. Read-only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from labkit.formats import protocol_block, protocol_fields, protocol_then, runs
from labkit.formats.protocol_block import ExploredIn
from labkit.formats.protocol_then import StepThen
from labkit.formats.repo import git_root
from labkit.formats.runs import RunDir


@dataclass(frozen=True)
class ClosureRun:
    """One run the state a link names rests on (`basis_closure`).

    Attributes:
        run_id: The run.
        reached: How the closure reached it: "the named run", "origin of
            <run> (<input key>)" or "basis of <run>".
        rd: The run as its directory reads now.
        protocol: The protocol of its area it is bound to; None for a run
            bound to none (a preparation), one whose record does not read,
            and one whose protocol is not found.
        then: Its own text and step (`protocol_then.step_then`); None
            without PROTOCOL.
        unread: What of it could not be read, one sentence each — the
            record, its inputs, its protocol, its own text or step. The
            closure stops at what it cannot read and says so; it never
            reads a missing step as no step.
    """

    run_id: str
    reached: str
    rd: RunDir
    protocol: Path | None
    then: StepThen | None
    unread: tuple[str, ...]


def basis_closure(area: Path, run_id: str) -> list[ClosureRun]:
    """RUN_ID of AREA and every run its state rests on, the named run
    first, each once in the order reached: per run, the origin runs its
    inputs recorded (`runs.DataEntry.origin_run`; origins are looked up
    within the area) and the basis its own step names (`[builds_on] run`,
    read from the run's own text) — transitively. Narrower than every run
    of the protocol: an independent side run is not in it. A run, text or
    step that cannot be read stays in the list with why (`ClosureRun.unread`).
    Raises RuntimeError when git fails."""
    root = git_root(area)
    out: list[ClosureRun] = []
    queue = [(run_id, "the named run")]
    seen: set[str] = set()
    while queue:
        rid, reached = queue.pop(0)
        if rid in seen:
            continue
        seen.add(rid)
        member, further = _closure_run(area, rid, reached, root)
        out.append(member)
        queue += further
    return out


def _closure_run(
    area: Path, run_id: str, reached: str, root: Path | None
) -> tuple[ClosureRun, list[tuple[str, str]]]:
    """(the closure's entry for RUN_ID of AREA, the runs it leads on to as
    (run id, how reached)): its origins from its record, its basis from its
    own text. Raises RuntimeError when git fails."""
    rd = runs.read_run_dir(runs.run_path(area, run_id))
    if rd.config is None:
        why = f"run {run_id} does not read: {rd.error or 'no record'}"
        return ClosureRun(run_id, reached, rd, None, None, (why,)), []
    unread: list[str] = []
    further: list[tuple[str, str]] = []
    try:
        entries = runs.data_entries(rd.config.data, str(rd.dir / runs.CONFIG_FILE))
    except runs.ArtefactError as exc:
        entries = []
        unread.append(f"run {run_id}: its inputs do not read ({exc})")
    further += [
        (e.origin_run, f"origin of {run_id} ({e.key})")
        for e in entries
        if e.origin_run is not None
    ]
    pid = rd.config.protocol.id
    if pid is None:
        return ClosureRun(run_id, reached, rd, None, None, tuple(unread)), further
    try:
        protocol = protocol_block.find_by_id(area, pid)
    except protocol_block.BlockError as exc:
        unread.append(f"run {run_id}: its protocol is not found ({exc})")
        return ClosureRun(run_id, reached, rd, None, None, tuple(unread)), further
    then = protocol_then.step_then(protocol, rd, root)
    if then.unknown is not None:
        unread.append(then.unknown)
    elif then.step is not None:
        further.append((then.step.run, f"basis of {run_id}"))
    return ClosureRun(run_id, reached, rd, protocol, then, tuple(unread)), further


@dataclass(frozen=True)
class NamedState:
    """The state of an exploration a link names, as it stands now — the
    three parts a confirming audit binds (`named_state`).

    Attributes:
        protocol: The exploratory protocol.
        text: Its text as the working tree holds it.
        adopted: The selection: the run it adopts now (`[result] run`, or
            the sentence of a table that does not read —
            `protocol_block.declared_run_shown`); None once withdrawn or
            never adopted.
        conclusion: Its Conclusion field as it stands; None where the
            protocol holds no one such field.
        closure: The basis: the named run and every run it rests on
            (`basis_closure`).
    """

    protocol: Path
    text: str
    adopted: str | None
    conclusion: str | None
    closure: tuple[ClosureRun, ...]


def named_state(protocol: Path, link: ExploredIn) -> NamedState:
    """The state LINK names of the exploratory PROTOCOL — the one protocol
    of the repo carrying LINK's id —, read from the working tree: what the
    area stamp covers (`scope_sha.exploration_basis`) and the confirming
    audit is shown (`audit_prompt.exploration_evidence`), so both follow
    the same three parts. Raises OSError when PROTOCOL does not read,
    RuntimeError when git fails."""
    text = protocol.read_text(encoding="utf-8")
    return NamedState(
        protocol,
        text,
        protocol_block.declared_run_shown(text),
        protocol_fields.named_value(text, protocol_fields.CONCLUSION_LABEL),
        tuple(basis_closure(protocol.parent, link.run)),
    )


@dataclass(frozen=True)
class SharedInput:
    """One input of a confirming run whose recorded sha256 a run of the
    exploration's area recorded too (`shared_inputs`): the same bytes.

    Attributes:
        exploring_run: The run of the exploration's area.
        exploring_key: Its input key.
        confirming_run: The run of the confirmation.
        confirming_key: Its input key.
        sha256: The digest both records hold.
        in_closure: Is EXPLORING_RUN one of the runs the named state rests
            on (`basis_closure`)? Outside it, the confirming audit's stamp
            does not follow the run.
    """

    exploring_run: str
    exploring_key: str
    confirming_run: str
    confirming_key: str
    sha256: str
    in_closure: bool


def shared_inputs(
    confirming: Sequence[RunDir], exploring: Sequence[RunDir], closure: set[str]
) -> list[SharedInput]:
    """Every pair of an input a run of CONFIRMING recorded and an input a
    run of EXPLORING recorded with the same sha256, the exploring runs in
    the order given; CLOSURE the ids of the runs the named state rests on.
    A run of CONFIRMING that EXPLORING holds too — both protocols in one
    area — is no exploring run and pairs with nothing as one.
    Static evidence of further data use, never a proof either way: an
    equal digest is byte-identical content (a copy or a renamed file too),
    while a subset, a re-encoded file or
    the same items under another name carry another digest. A run whose
    record or inputs do not read contributes nothing here — the audit's
    input listing names it. Pure."""
    theirs = [(rd.dir.name, e) for rd in confirming for e in _inputs(rd)]
    own = {rd.dir for rd in confirming}
    return [
        SharedInput(rd.dir.name, e.key, run, c.key, e.sha256, rd.dir.name in closure)
        for rd in exploring
        if rd.dir not in own
        for e in _inputs(rd)
        for run, c in theirs
        if c.sha256 == e.sha256
    ]


def not_shown_since(
    shared: Sequence[SharedInput], began: datetime | None
) -> list[SharedInput]:
    """The entries of SHARED whose exploring run an audit begun at BEGAN
    (local time) was not shown, in SHARED's order: the run's id carries a
    start at or after BEGAN (`runs.run_started`), or no time — a run that
    cannot be ordered is not taken as seen. Every entry when BEGAN is None:
    an audit whose start is unknown has seen no run for certain. The order
    of a run and an audit rests on the clocks that wrote both
    (`area_state.CLOCKS_ASSUMED`). Pure."""
    if began is None:
        return list(shared)
    out: list[SharedInput] = []
    for s in shared:
        started = runs.run_started(s.exploring_run)
        if started is None or started >= began:
            out.append(s)
    return out


def _inputs(rd: RunDir) -> list[runs.DataEntry]:
    """The inputs RD's record names; [] where the record or its `data`
    table does not read."""
    if rd.config is None:
        return []
    try:
        return runs.data_entries(rd.config.data, str(rd.dir / runs.CONFIG_FILE))
    except runs.ArtefactError:
        return []
