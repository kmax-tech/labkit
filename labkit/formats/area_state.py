"""area_state — the state of an experiment area, assembled once from the
formats' own readers and read by gates, checks and tools in place of each
reading the files itself (Phase 4 of
docs/notes/2026-11-04-one-explainer-plan.md). It opens no file of its own:
the run directories come from `runs.run_dirs` (the working tree) or from
git's index (`repo.files_at`, `repo.text_at`), the runs a commit once held
and the file state lacks from git's history (`committed_runs`), the local
run index from `run_index.indexed_bindings`.

The first field is what each protocol measured (`Measured`): has it
measured, and which measurements were first — one answer for the run's
start check, the registration comparison, the report gates, the handover
and `labkit-init --change-kind`, where each derived it before.

A file state names which state of the files a check judges: `TREE`, the
working tree; `INDEX`, git's index (what a commit now would carry);
`PROPOSED`, the working tree with a proposed protocol text in place of the
file (the adoption's check). It is named in the output, so a reader knows
what was held. Under `PROPOSED` the runs are the tree's.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from labkit.formats.runs import RUNS_DIR
from labkit.formats.commands import checkout_command
from labkit.formats import promises
from labkit.formats.gate import (
    GUARANTEED,
    NOT_EXECUTABLE,
    TECHNICAL_RULE,
    WARNING,
    GateFinding,
)
from labkit.formats.answering_run import (
    AnsweringRun,
    adopted_run,
    RunFacts,
    bound_answering_run,
    bound_runs,
    facts_of,
    first_measurement_groups,
    is_measurement,
)
from labkit.formats.repo import (
    rel_posix,
    INDEX_REV,
    area_protocols,
    pending_adoption,
    commit_of,
    files_at,
    git_root,
    git_run,
    head_sha,
    text_at,
)
from labkit.formats.run_index import RunIndexError, indexed_bindings
from labkit.formats.run_starts import RunStart, read_starts
from labkit.formats.runs import (
    COMPLETION_FILE,
    CONFIG_FILE,
    MEASUREMENT,
    RunDir,
    RunKind,
    run_dir_from_text,
    run_dirs,
    run_path,
    runs_path,
)

#: which files a check judges: the working tree, git's index (what the
#: next commit carries) or the tree with a proposed protocol text (an
#: adoption's check); a file reader takes the flag `staged` instead
#: (`staged_of`, `file_state_of`)
FileState = Literal["working tree", "index", "proposed protocol"]
TREE: FileState = "working tree"
INDEX: FileState = "index"
PROPOSED: FileState = "proposed protocol"


def staged_of(file_state: FileState) -> bool:
    """The flag a file reader takes for FILE_STATE: True (the index) for
    INDEX, False (the tree) for TREE and PROPOSED."""
    return file_state == INDEX


def file_state_of(*, staged: bool) -> FileState:
    """The file state a file reader's STAGED flag reads: INDEX or TREE."""
    return INDEX if staged else TREE


@dataclass(frozen=True)
class Measured:
    """What an area measured of one protocol, stamped id PID, as one file
    state holds it — the one answer to "has it measured, and which
    measurements were first".

    Attributes:
        area: The area, as the caller spelled it.
        pid: The protocol's stamped id.
        runs: Every run bound to PID — of any kind, a repeat too, finished
            or not — and every run whose record does not read and which its
            start file or the run index binds to PID (`assigned_to`),
            oldest first by name; as the file state holds them, or read back
            from git where a commit holds a run the state lacks
            (`RunDir.from_commit`).
        lost: The ids of the runs only the local run index lists: deleted,
            and never committed — finished, as the index says (`runlog
            reindex` indexes completed runs only), with nothing left to
            read back. Never an invented record. The index names no run
            kind: a run its start file lists as a probe or a preparation
            is left out (`AreaState.lost` keeps it), one without a start
            row counts, as it may have measured.
        first_groups: The first measurements — every run at each first
            position (`answering_run.first_measurement_groups`): a
            measurement among RUNS, no repeat, its record readable.
        run_facts: The facts of every present run of the area — not of PID
            alone: the choice names the runs bound elsewhere among its
            exclusions (`AreaState.run_facts`).
        unassigned: The ids of the area's runs whose record does not read
            and which neither a start file nor the run index names:
            which protocol each belongs to cannot be determined. The same
            for every PID; such a run is among no protocol's RUNS and
            counts for none — named where a check tells it
            (`measurements_without_record`), never read as a measurement
            and never as "no run".
        started_only: The ids of the measurements only a start file
            names, bound to PID there (its row says `run_kind =
            "measurement"`): started, with no directory in the working
            tree, no commit that holds it and no row in the run index — it
            broke off or was deleted before it finished. A probe or a
            preparation run in that state is not here
            (`AreaState.started_only` keeps it).
        started: Run id → its start in UTC, for the runs of PID the start
            record lists (RUNS, LOST and STARTED_ONLY): what orders two
            runs, and only where both have one.
        started_as: Run id → the run kind its start file names, for the
            same runs: what tells a probe whose record is gone or does not
            read from a measurement.
        conflicts: One clause per run whose protocol its start file, the
            run index and its own record name differently, PID among the
            ids named (`binding_conflicts`): which protocol it belongs to
            is contradicted, and no source is taken over another.
    """

    area: Path
    pid: str
    runs: tuple[RunDir, ...]
    lost: tuple[str, ...]
    first_groups: tuple[tuple[RunDir, ...], ...]
    run_facts: tuple[RunFacts, ...]
    unassigned: tuple[str, ...] = ()
    started_only: tuple[str, ...] = ()
    started: Mapping[str, datetime] = field(default_factory=dict)
    conflicts: tuple[str, ...] = ()
    started_as: Mapping[str, RunKind] = field(default_factory=dict)

    def answering(self, adopted: str | None) -> AnsweringRun:
        """The run every check holds PID to (`answering_run.bound_answering_run`
        over RUN_FACTS): the adopted one (ADOPTED, the head's `[result] run`),
        else the newest completed bound run that reports an intent key —
        with why every other run is left out, or why no choice stands. The
        one call of the choice; the runs' metrics are read here for the
        intent keys."""
        return bound_answering_run(self.area, self.pid, adopted, self.run_facts)

    def told(self, text: str) -> tuple[AnsweringRun, GateFinding | None, list[str]]:
        """The answering run for the protocol TEXT and its telling: the
        choice (`answering`, the adopted run read from TEXT,
        `answering_run.adopted_run`) and `AnsweringRun.explain` over whether
        TEXT registers promises (`promises.registers_promises`) — (the
        choice, the blocker or None, the lines that say what was looked
        at). The one place finalize, intent-check, recheck, params and the
        audit ask, so none tells it its own way."""
        choice = self.answering(adopted_run(text))
        blocker, lines = choice.explain(promises.registers_promises(text))
        return choice, blocker, lines

    def bound(self) -> tuple[list[RunFacts], list[RunFacts]]:
        """(the completed runs bound to PID, every other present run with
        why it is left out) — `answering_run.bound_runs` over RUN_FACTS."""
        return bound_runs(self.run_facts, self.pid)

    @property
    def has_measured(self) -> bool:
        """Did the area measure PID — a run among RUNS that declared itself
        a measurement or whose record does not read
        (`answering_run.is_measurement`), or a lost one? Before a
        measurement a report owes nothing and a report may still be
        registered; after it the registration stands. The one question
        behind "before the first measurement": a lost run, a run only a
        start file names and an unreadable record bound to PID count, as
        each may have been the first — `firsts` is no answer to it, it
        names only the measurements whose record reads. A record of
        UNASSIGNED does not count: its protocol is unknown, and it is held
        against none. Neither does a run its start file lists as a probe
        or a preparation, whatever became of its record
        (`may_have_measured`)."""
        return (
            bool(self.lost)
            or bool(self.started_only)
            or any(self.may_have_measured(rd) for rd in self.runs)
        )

    def may_have_measured(self, rd: RunDir) -> bool:
        """May the run RD of RUNS have measured PID? Its record's kind where
        the record reads (`answering_run.is_measurement`); where it does
        not, the kind its start file names, and yes without a start file —
        nothing says it was a probe."""
        if rd.error is None:
            return is_measurement(rd)
        return self.started_as.get(rd.dir.name, MEASUREMENT) == MEASUREMENT

    @property
    def firsts(self) -> tuple[RunDir, ...]:
        """One run per first position — the first by name of each group —
        sorted by name; () when PID has no measurement whose record reads."""
        return tuple(
            sorted((g[0] for g in self.first_groups), key=lambda rd: rd.dir.name)
        )

    @property
    def present(self) -> tuple[RunDir, ...]:
        """RUNS as the file state holds them."""
        return tuple(rd for rd in self.runs if rd.from_commit is None)

    @property
    def deleted(self) -> tuple[RunDir, ...]:
        """RUNS a commit holds and the file state lacks: `RunDir.from_commit`
        is the commit a checkout restores each from."""
        return tuple(rd for rd in self.runs if rd.from_commit is not None)


@dataclass(frozen=True)
class AreaState:
    """The state of one area as one file state holds it, built once
    (`state_of`) and read by every check of it.

    Attributes:
        area: The area, as the caller spelled it (its runs' paths keep that
            spelling: a caller compares them to its own).
        repo: The repository the area lies in (`repo.git_root`), None
            outside one.
        file_state: TREE, INDEX or PROPOSED.
        protocols: The area's protocol files as the file state holds them
            (`repo.area_protocols`; the index's under INDEX), sorted — a
            list, never a first hit: the caller chooses.
        protocol_texts: Each protocol's text as the file state holds it
            (`repo.text_at` under INDEX, the file otherwise); `text_of`
            reads one.
        adoption_pending: The protocols whose adoption was cut off during
            its check and whose proposal stands unchecked in the tree
            (`repo.pending_adoption`'s file exists); `adoption_pending_for`
            asks for one.
        runs: Every run directory the file state holds (`runs.run_dirs`,
            the index's `runs/<id>/config.json` entries under INDEX),
            oldest first by name, each record read once.
        deleted: The runs a commit holds and the file state lacks, read
            back from git (`committed_runs`; `RunDir.from_commit` the
            commit a checkout restores each from), oldest first by name;
            () when git could not list them (HISTORY_UNREAD).
        history_unread: Git's words when the runs a commit holds could not
            be listed (`committed_runs`: an object the repository lacks, a
            tree it cannot read), "" when they could — a damaged repository
            is told, never read as "no run was deleted"; the stations that
            read a commit name the damaged object themselves
            (`protocol_history.committed_at`).
        lost: Run id → protocol id of the runs only the local run index
            lists (`run_index.indexed_bindings`): deleted and never
            committed.
        run_facts: The facts of every present run (`answering_run.facts_of`:
            state, binding, repeat), read once — what the answering-run
            choice runs over.
        measured: Protocol id → what the area measured of it (`Measured`),
            for every id a run or the index names; `measured_of` answers
            for any id.
        indexed: The local run index as read, run id → protocol id in
            index order (`run_index.indexed_bindings`), the runs that
            stand included: which runs reached completion, and with the
            start files what binds a run without a record to a protocol
            (`assigned_to`). Its order tells nothing.
        starts: The start files as read, run id → what each holds
            (`run_starts.read_starts`): which run started with which
            protocol, when and as which kind.
        started_only: Run id → protocol id of the runs only the start
            record names, of every kind: no directory in the working tree,
            no commit and no index row holds them. `Measured.started_only`
            is the measurements among them.
        conflicts: Run id → the (source, protocol id) pairs of each run
            whose sources name different protocols (`binding_conflicts`).
    """

    area: Path
    repo: Path | None
    file_state: FileState
    protocols: tuple[Path, ...]
    protocol_texts: Mapping[Path, str]
    adoption_pending: frozenset[Path]
    runs: tuple[RunDir, ...]
    deleted: tuple[RunDir, ...]
    history_unread: str
    lost: Mapping[str, str]
    run_facts: tuple[RunFacts, ...]
    measured: Mapping[str, Measured]
    indexed: Mapping[str, str] = field(default_factory=dict)
    starts: Mapping[str, RunStart] = field(default_factory=dict)
    started_only: Mapping[str, str] = field(default_factory=dict)
    conflicts: Mapping[str, tuple[tuple[str, str], ...]] = field(default_factory=dict)

    def text_of(self, protocol: Path) -> str:
        """PROTOCOL's text as the file state holds it. Raises ValueError
        when the state does not hold PROTOCOL (not among `protocols`:
        deleted, or not in the index under INDEX)."""
        try:
            return self.protocol_texts[protocol.resolve()]
        except KeyError:
            raise ValueError(
                f"{protocol.name}: the {self.file_state} does not hold it"
            ) from None

    def adoption_pending_for(self, protocol: Path) -> bool:
        """Does an adoption's proposal of PROTOCOL stand unchecked in the
        tree (`repo.pending_adoption`)?"""
        return protocol.resolve() in self.adoption_pending

    def measured_of(self, pid: str | None) -> Measured:
        """What the area measured of protocol PID — an empty `Measured`
        (the unassigned records still named) for an id no run and no index
        row names, and for None (a head without a stamped id)."""
        if pid is not None and pid in self.measured:
            return self.measured[pid]
        return _measured(
            self.area,
            pid or "",
            [*self.runs, *self.deleted],
            (),
            self.repo,
            self.run_facts,
            self.indexed,
            self.starts,
            (),
            self.conflicts,
        )


def assemble(
    area: Path,
    repo: Path | None,
    file_state: FileState,
    runs: Sequence[RunDir],
    deleted: Sequence[RunDir],
    lost: Mapping[str, str],
    history_unread: str = "",
    protocols: Sequence[Path] = (),
    protocol_texts: Mapping[Path, str] | None = None,
    adoption_pending: Collection[Path] = (),
    indexed: Mapping[str, str] | None = None,
    starts: Mapping[str, RunStart] | None = None,
    started_only: Mapping[str, str] | None = None,
) -> AreaState:
    """The `AreaState` of AREA from what its readers found — RUNS the file
    state holds, DELETED the runs git holds back (HISTORY_UNREAD git's words
    when they could not be listed), LOST the index-only run ids with their
    protocol ids, PROTOCOLS the area's protocol files with PROTOCOL_TEXTS
    (resolved path → text) and ADOPTION_PENDING, INDEXED the run index as
    read (run id → protocol id, the runs that stand included), STARTS the
    start files as read and STARTED_ONLY the runs only they name with their
    protocol ids —, every derived field computed here once:
    the one assembly for `state_of` and for a test that builds a state
    without files. Pure but for git's ancestry questions in the first
    measurements' order (REPO None: none asked)."""
    records = sorted([*runs, *deleted], key=lambda rd: rd.dir.name)
    facts = tuple(
        f for rd in sorted(runs, key=lambda rd: rd.dir.name) if (f := facts_of(rd))
    )
    indexed = dict(indexed or {})
    starts = dict(starts or {})
    started_only = dict(started_only or {})
    conflicts = binding_conflicts(records, indexed, starts)
    pids = sorted(
        {
            rd.config.protocol.id
            for rd in records
            if rd.config is not None and rd.config.protocol.id
        }
        | set(lost.values())
        | {pid for pid in started_only.values() if pid}
        | {pid for rd in records if (pid := assigned_to(rd, indexed, starts))}
        | {pid for named in conflicts.values() for _, pid in named if pid}
    )
    measured = {
        pid: _measured(
            area,
            pid,
            records,
            tuple(
                r
                for r, p in lost.items()
                if p == pid and _started_as(r, starts) in (None, MEASUREMENT)
            ),
            repo,
            facts,
            indexed,
            starts,
            tuple(
                r
                for r, p in started_only.items()
                if p == pid and _started_as(r, starts) == MEASUREMENT
            ),
            conflicts,
        )
        for pid in pids
    }
    return AreaState(
        area=area,
        repo=repo,
        file_state=file_state,
        protocols=tuple(protocols),
        protocol_texts=dict(protocol_texts or {}),
        adoption_pending=frozenset(p.resolve() for p in adoption_pending),
        runs=tuple(sorted(runs, key=lambda rd: rd.dir.name)),
        deleted=tuple(sorted(deleted, key=lambda rd: rd.dir.name)),
        history_unread=history_unread,
        lost=dict(lost),
        run_facts=facts,
        measured=measured,
        indexed=indexed,
        starts=starts,
        started_only=started_only,
        conflicts=conflicts,
    )


def assigned_to(
    rd: RunDir, indexed: Mapping[str, str], starts: Mapping[str, RunStart]
) -> str | None:
    """The protocol id a run RD whose record does not read is assigned to:
    the one its start file (STARTS) or its row in the run index INDEXED
    names ("" for a run that started or was recorded unbound) — the
    evidence of a binding the record no longer gives. None for a record
    that reads (its own binding holds), for one neither file names
    (unassigned, `Measured.unassigned`) and for one the two name
    differently (`binding_conflicts` tells that; neither wins). Never from
    a time, and never from the number of protocols in the area. The one
    home of this assignment: what the area measured of a protocol, the
    report duty and the registration station all read it through
    `Measured`. Pure."""
    if rd.error is None:
        return None
    named = _named(rd.dir.name, indexed, starts)
    return next(iter(named.values())) if len(set(named.values())) == 1 else None


def _named(
    run: str, indexed: Mapping[str, str], starts: Mapping[str, RunStart]
) -> dict[str, str]:
    """Source → protocol id for RUN, of the two files that name a binding
    outside the run's own record: its start file, the run index."""
    named: dict[str, str] = {}
    if run in starts:
        named["its start file"] = starts[run].protocol_id
    if run in indexed:
        named["the run index"] = indexed[run]
    return named


def binding_conflicts(
    records: Sequence[RunDir],
    indexed: Mapping[str, str],
    starts: Mapping[str, RunStart],
) -> dict[str, tuple[tuple[str, str], ...]]:
    """Run id → ((source, protocol id), …) for every run whose sources name
    different protocols: its own record where it reads among RECORDS, its
    start file (STARTS), its row in the run index INDEXED ("" is
    unbound, and differs from an id). {} when every run's sources agree; a
    run one source names is no conflict. A contradiction is its own
    finding (`registration_hold.binding_conflict_hold`): which protocol the
    run belongs to cannot be told from files that disagree, and none of
    them is taken over the others. Pure."""
    own = {
        rd.dir.name: rd.config.protocol.id or ""
        for rd in records
        if rd.config is not None
    }
    out: dict[str, tuple[tuple[str, str], ...]] = {}
    for run in sorted({*own, *indexed, *starts}):
        named = _named(run, indexed, starts)
        if run in own:
            named = {"its record": own[run], **named}
        if len(set(named.values())) > 1:
            out[run] = tuple(named.items())
    return out


def _started_as(run: str, starts: Mapping[str, RunStart]) -> RunKind | None:
    """The run kind RUN's start file names; None without one."""
    return starts[run].run_kind if run in starts else None


def _measured(
    area: Path,
    pid: str,
    records: Sequence[RunDir],
    lost: tuple[str, ...],
    repo: Path | None,
    facts: tuple[RunFacts, ...],
    indexed: Mapping[str, str],
    starts: Mapping[str, RunStart],
    started_only: tuple[str, ...],
    conflicts: Mapping[str, tuple[tuple[str, str], ...]],
) -> Measured:
    """`Measured` of PID over RECORDS (present and deleted runs together):
    the runs bound to PID — by their record, or, where it does not read, by
    its start file or the run index (`assigned_to`) —, the first groups
    among them, FACTS of every present run for the choice, the unreadable
    records neither file names, the measurements only a start file
    names (STARTED_ONLY), the starts and the started kinds of all of
    these, and the contradicted bindings that name PID (CONFLICTS)."""
    ours = tuple(
        rd
        for rd in records
        if assigned_to(rd, indexed, starts) == pid
        or (rd.config is not None and rd.config.protocol.id == pid)
    )
    groups = first_measurement_groups(ours, pid, repo)
    unassigned = tuple(
        rd.dir.name
        for rd in records
        if rd.error is not None and not _named(rd.dir.name, indexed, starts)
    )
    of_pid = [*(rd.dir.name for rd in ours), *lost, *started_only]
    return Measured(
        area,
        pid,
        ours,
        lost,
        tuple(tuple(g) for g in groups),
        facts,
        unassigned,
        started_only,
        {run: starts[run].started for run in of_pid if run in starts},
        tuple(
            f"run {run}: "
            + ", ".join(
                f"{source} names {named or 'no protocol'}" for source, named in sources
            )
            for run, sources in conflicts.items()
            if pid in {named for _, named in sources}
        ),
        {run: starts[run].run_kind for run in of_pid if run in starts},
    )


def state_of(area: Path, *, file_state: FileState = TREE) -> AreaState:
    """The state of AREA as FILE_STATE holds it (`AreaState`): the runs of
    the working tree (TREE, PROPOSED) or of git's index (INDEX), the runs a
    commit holds and that state lacks, the index-only ones, the ones only
    a start file names. Raises `run_index.RunIndexError` on a run index
    that does not read and `run_starts.RunStartsError` on a start file
    that does not — whether a deleted run was measured or started cannot
    be told then —, GitError or RuntimeError when git fails."""
    repo = git_root(area)
    staged = staged_of(file_state)
    runs = present_run_dirs(area, repo=repo, file_state=file_state)
    if staged:
        assert repo is not None  # present_run_dirs refused the index without one
        protocols = area_protocols(area, staged=True)
        texts = {
            p.resolve(): t for p in protocols if (t := text_at(repo, p)) is not None
        }
    else:
        protocols = area_protocols(area)
        texts = {p.resolve(): p.read_text(encoding="utf-8") for p in protocols}
    pending = [p for p in protocols if pending_adoption(p).is_file()]
    held = {rd.dir.name for rd in runs}
    deleted: list[RunDir] = []
    unread = ""
    if repo is not None:
        try:
            deleted = committed_runs(repo, area, held)
        except HistoryUnread as exc:
            unread = str(exc)
    gone = held | {rd.dir.name for rd in deleted}
    indexed = indexed_bindings(area)
    lost = {r: p for r, p in indexed.items() if r not in gone}
    starts = read_starts(area)
    # against the working tree whatever the file state: a run that stands
    # in the tree and is not staged is not gone
    standing = gone if not staged else gone | {rd.dir.name for rd in run_dirs(area)}
    started_only = {
        r: s.protocol_id
        for r, s in starts.items()
        if r not in standing and r not in indexed
    }
    return assemble(
        area,
        repo,
        file_state,
        runs,
        deleted,
        lost,
        unread,
        protocols,
        texts,
        pending,
        indexed,
        starts,
        started_only,
    )


def index_names_gone_runs(area: Path) -> bool:
    """Does AREA's local run index list a run whose directory is gone, or
    does the index not read? The cheap question the post-change hook asks
    of every area before it builds a state for the ones that say yes."""
    try:
        return any(not run_path(area, r).is_dir() for r in indexed_bindings(area))
    except RunIndexError:
        return True


def starts_name_open_runs(area: Path) -> bool:
    """Does a start file of AREA name a run whose directory is gone
    or stands without its completion record, or does a start file not
    read? The cheap question the post-change hook asks beside
    `index_names_gone_runs`: a run that broke off, or was deleted before
    it finished, has no index row to be found by."""
    try:
        return any(
            not (run_path(area, r) / COMPLETION_FILE).is_file()
            for r in read_starts(area)
        )
    except RunIndexError:  # a start file that does not read
        return True


class HistoryUnread(RuntimeError):
    """Git could not list or read the runs a commit holds
    (`committed_runs`): its words, for `AreaState.history_unread`."""


def gone_run_restore(rd: RunDir) -> str:
    """How a run git holds back (RD, from `AreaState.deleted`) comes back:
    its checkout command in the area — the one sentence every gate prints
    for it (`checkout_command`)."""
    return (
        f"`{checkout_command(Path(RUNS_DIR) / rd.dir.name, rd.from_commit or '')}` "
        "in the area restores it"
    )


#: what a run only the index lists (`AreaState.lost`) has left: nothing git
#: holds — the one sentence every gate prints for it
LOST_RUN_SENTENCE = "its rows are lost; only git, where it holds the run, restores them"


def lost_in_the_tree_too(measured: Measured) -> list[str]:
    """MEASURED's lost runs that the working tree lacks as well. A state of
    the index calls a run lost that stands in the tree and is not staged;
    such a run is not gone, and the tree's own state reads it. Builds the
    tree's state (`state_of`) when MEASURED names a lost run."""
    if not measured.lost:
        return []
    tree = state_of(measured.area).measured_of(measured.pid).lost
    return [run for run in measured.lost if run in tree]


#: the assumption under which the starts of two start files order two
#: runs — the clause every message prints that takes a run as the later
#: one. A UTC time removes the zone from the question, not the clock.
CLOCKS_ASSUMED = (
    "assuming the clocks of the machines that started the runs were right, "
    "which labkit does not check"
)

#: what a record of unknown protocol leaves open for every protocol of
#: its area — the clause the run's start, the registration station and the
#: report duty's station print with it, so none reads as "no earlier
#: measurement"
UNASSIGNED_LEAVES_OPEN = (
    "whether it measured this protocol, and before the first measurement that "
    "reads, is unresolved: it is counted for no protocol, no hold follows from "
    "it, and it shows neither an earlier measurement nor that none came before"
)

#: the way back every warning about a run without a record names
RECORD_BACK = (
    "bring the run's directory with its config.json back from a commit, a clone "
    "or a copy that holds it (a record written anew from memory settles nothing)"
)


def unassigned_record_warning(unassigned: Sequence[str]) -> GateFinding | None:
    """The WARNING about the records of UNASSIGNED (`Measured.unassigned`:
    they do not read, and neither a start file nor the run index
    names them), None
    without one: which protocol each belongs to and what it means are
    unresolved, it is counted for no protocol and no hold follows from it
    (UNASSIGNED_LEAVES_OPEN), with the way back (RECORD_BACK) — a check
    not executable, never a silent pass. The one sentence every station
    prints for it: finalize's registration station
    (`registration_hold.lost_record_warnings`) and report-check's report
    duty (`registered_report.unassigned_record_note`). Pure."""
    if not unassigned:
        return None
    return GateFinding(
        WARNING,
        f"the record of run {', '.join(unassigned)} does not read, and neither "
        f"a start file nor the run index names it: which protocol it belongs "
        f"to cannot be determined — {UNASSIGNED_LEAVES_OPEN}",
        rule=TECHNICAL_RULE,
        fix=RECORD_BACK,
        evidence_kind=GUARANTEED,
        stated_outcome=NOT_EXECUTABLE,
    )


@dataclass(frozen=True)
class WithoutRecord:
    """The runs labkit still has evidence of and no record for, sorted by
    what that means for one protocol (`measurements_without_record`).

    Attributes:
        may_be_first: One clause per such run of the protocol that no
            measurement of it that reads is known to precede — none reads,
            or the start files put the run's start before every one that
            does: it may have been the first measurement, so what stood
            registered before the number is not told.
        unordered: One clause per such run of the protocol whose order
            against the measurements that read is unknown: the start
            record lacks the start of the run or of one of them, or two
            share a second. It may have been the first as well; the clause
            says what is missing.
        later: One clause per such run of the protocol that the start
            record puts after a measurement of it that reads: taken as
            started later under CLOCKS_ASSUMED, so the first measurement's
            registration is read without it.
        unassigned: The ids of the runs whose record does not read and
            which neither a start file nor the run index names
            (`Measured.unassigned`): which protocol each belongs to cannot
            be determined, so it counts for none.
    """

    may_be_first: tuple[str, ...]
    unordered: tuple[str, ...]
    later: tuple[str, ...]
    unassigned: tuple[str, ...]

    @property
    def held(self) -> tuple[str, ...]:
        """MAY_BE_FIRST and UNORDERED: the clauses of the runs that hold
        the protocol's numbers."""
        return self.may_be_first + self.unordered

    @property
    def of_protocol(self) -> tuple[str, ...]:
        """HELD and LATER: the clauses of the runs bound to the protocol."""
        return self.held + self.later


def measurements_without_record(
    measured: Measured, lost_in_tree: Sequence[str]
) -> WithoutRecord:
    """The runs without a record, as they bear on MEASURED's protocol
    (`WithoutRecord`): each run of LOST_IN_TREE (its directory gone, no
    commit holding it, the run index listing it), each measurement only
    a start file names (`Measured.started_only`) and each run among
    MEASURED's whose record does not read and which may have measured
    (`Measured.may_have_measured`: not one its start file lists as a probe
    or a preparation) — all bound to the protocol by the start
    record or the run index (`assigned_to`) —, and MEASURED's unassigned
    records. LOST_IN_TREE is the lost runs the working tree lacks too —
    `lost_in_the_tree_too(measured)` for a state of the index,
    `measured.lost` itself for a state of the working tree.

    Assignment first, order second: a file names the protocol, and only
    then a time says whether the run may have been its first measurement.
    The order of two runs is told only where start files hold a UTC
    start for both (`Measured.started`), against the measurements of the
    protocol whose record reads (no repeat, no probe; a run a commit holds
    back among them): after one of them, the run is LATER; before every
    one of them, or with none that reads, it MAY_BE_FIRST; with a start
    missing or shared to the second it is UNORDERED — unknown, said as
    such with what is missing, and held like the first. A run from before
    start files were written has none and is never ordered by its id, by
    its row's place in the index or by a commit. LATER rests on
    CLOCKS_ASSUMED, which nothing here checks.

    Everything empty when every measurement has its record. A run removed
    with its rows in both files leaves no evidence and is not seen. Pure.
    Read by the run's start (`start_check.earlier_measurement_note`) and
    the registration station (`registration_hold.lost_record_hold`,
    `lost_record_warnings`). Why, and what was rejected for the order:
    docs/notes/2026-11-18-lost-first-measurement.md."""
    reads = [
        rd.dir.name
        for rd in measured.runs
        if rd.config is not None
        and rd.config.run_kind == MEASUREMENT
        and rd.config.repeat_of is None
    ]
    started = measured.started
    gone = [
        (
            run,
            f"run {run} is gone (the run index lists it as measured, and it was "
            f"deleted before a commit held it)",
        )
        for run in lost_in_tree
    ] + [
        (
            run,
            f"run {run} is gone (its start file lists it as a measurement "
            f"that started; no directory, no commit and no row of the run index "
            f"holds it)",
        )
        for run in measured.started_only
    ]
    # the reason is `runlog <AREA>`'s to list: it carries the machine's path
    unread = [
        (rd.dir.name, f"the record of run {rd.dir.name} does not read")
        for rd in measured.runs
        # a record its start file lists as a probe or a preparation measured
        # nothing: it is `runlog <AREA>`'s to list, not a hold
        if rd.error is not None and measured.may_have_measured(rd)
    ]
    may_be_first: list[str] = []
    unordered: list[str] = []
    later: list[str] = []
    for run, clause in gone + unread:
        at = started.get(run)
        known = [started[r] for r in reads if r in started]
        if not reads:
            may_be_first.append(clause)
        elif at is not None and any(k < at for k in known):
            later.append(clause)
        elif at is not None and len(known) == len(reads) and all(k > at for k in known):
            may_be_first.append(clause)
        else:
            without = [r for r in (run, *reads) if r not in started]
            unordered.append(
                f"{clause}; whether it started before the measurements that read "
                f"is unknown — "
                + (
                    f"no start file holds a start for {', '.join(without)}"
                    if without
                    else "the start files give it the same second as one of them"
                )
            )
    return WithoutRecord(
        tuple(may_be_first), tuple(unordered), tuple(later), measured.unassigned
    )


def present_run_dirs(
    area: Path, *, repo: Path | None, file_state: FileState
) -> list[RunDir]:
    """AREA's present runs as FILE_STATE holds them: the index's
    (`indexed_run_dirs`, REPO the repository) for INDEX, the tree's
    (`runs.run_dirs`) otherwise — the one reader every gate asks, so the
    runs a commit carries are the ones its gate judges. Raises ValueError
    for INDEX outside a repository, GitError when git fails."""
    if file_state == INDEX:
        if repo is None:
            raise ValueError(f"{area}: the index of no repository cannot be read")
        return indexed_run_dirs(repo, area)
    return run_dirs(area)


def indexed_run_dirs(repo: Path, area: Path) -> list[RunDir]:
    """AREA's runs as git's index holds them (`repo.files_at`): one `RunDir`
    per `runs/<id>/config.json` entry, its record read from the index
    (`repo.text_at`), oldest first by name; [] when the index holds none.
    Raises GitError when git fails."""
    entries = files_at(repo, runs_path(area), INDEX_REV) or set()
    out: list[RunDir] = []
    for entry in sorted(entries):
        parts = entry.split("/")
        if len(parts) != 2 or parts[1] != CONFIG_FILE:
            continue
        d = run_path(area, parts[0])
        text = text_at(repo, d / CONFIG_FILE)
        if text is None:
            raise RuntimeError(
                f"{d / CONFIG_FILE}: listed by git's index, and not read from it"
            )
        out.append(run_dir_from_text(d, text))
    return out


def committed_runs(repo: Path, area: Path, held: Collection[str]) -> list[RunDir]:
    """The runs of AREA a commit under REPO once held whose ids are not in
    HELD (the run directories the file state holds), each read back from
    the last commit that held its record: HEAD when HEAD still holds it
    (deleted in the tree, the deletion not committed), else the deletion's
    parent — `RunDir.from_commit`, the commit a checkout restores it from.
    One `git log` over the area's `runs/` (the records' additions and
    deletions, newest first), one `git show` per run read back; [] before
    the first commit. The source of what a deleted measurement registered:
    the local run index knows only that it ran, and only on the machine it
    ran on. Raises HistoryUnread (a RuntimeError) with git's words when
    git cannot read the history — an object the repository lacks —, or
    when a record the history names cannot be read from the commit it
    says holds it; GitError when git cannot run."""
    if not head_sha(repo):
        return []
    rel = rel_posix(runs_path(area), repo)
    args = [
        "log",
        "--format=%x00%H",
        "--name-status",
        "--diff-filter=AD",
        "--no-renames",
        "--",
        f"{rel}/",
    ]
    r = git_run(args, repo)
    if r.returncode != 0:
        raise HistoryUnread(
            f"the runs git holds under {rel}/ cannot be listed: "
            f"{' '.join(r.stderr.split())} (`git fsck` names the damaged object)"
        )
    record = re.compile(re.escape(rel) + r"/([^/]+)/" + re.escape(CONFIG_FILE))
    newest: dict[str, tuple[str, str]] = {}  # run id → (A or D, commit), newest event
    for chunk in r.stdout.split("\0"):
        lines = [ln for ln in chunk.splitlines() if ln]
        if not lines:
            continue
        commit, *statuses = lines
        for status in statuses:
            fields = status.split("\t")
            m = record.fullmatch(fields[-1]) if len(fields) == 2 else None
            if m is not None and m.group(1) not in newest:
                newest[m.group(1)] = (fields[0][:1], commit)
    out: list[RunDir] = []
    for run_id, (status, commit) in sorted(newest.items()):
        if run_id in held:
            continue
        rev = "HEAD" if status == "A" else f"{commit}^"
        at = commit_of(repo, rev)
        d = run_path(area, run_id)
        text = text_at(repo, d / CONFIG_FILE, rev) if at is not None else None
        if at is None or text is None:
            raise HistoryUnread(
                f"{d / CONFIG_FILE}: git's history says {rev} holds it, and it "
                f"cannot be read from there (`git fsck` names the damaged object)"
            )
        out.append(run_dir_from_text(d, text, from_commit=at))
    return out
