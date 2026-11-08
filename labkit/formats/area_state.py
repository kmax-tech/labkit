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
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.answering_run import (
    AnsweringRun,
    RunFacts,
    bound_answering_run,
    bound_runs,
    facts_of,
    first_measurement_groups,
    is_measurement,
)
from labkit.formats.repo import (
    INDEX_REV,
    area_protocols,
    indexed_protocols,
    pending_adoption,
    commit_of,
    files_at,
    git_root,
    git_run,
    head_sha,
    text_at,
)
from labkit.formats.run_index import RunIndexError, indexed_bindings
from labkit.formats.runs import (
    CONFIG_FILE,
    RunDir,
    run_dir_from_text,
    run_dirs,
    run_path,
    runs_path,
)

TREE = "working tree"
INDEX = "index"
PROPOSED = "proposed protocol"


@dataclass(frozen=True)
class Measured:
    """What an area measured of one protocol, stamped id PID, as one file
    state holds it — the one answer to "has it measured, and which
    measurements were first".

    Attributes:
        area: The area, as the caller spelled it.
        pid: The protocol's stamped id.
        runs: Every run bound to PID — of any kind, a repeat too, finished
            or not — and every run whose record does not read (its binding
            is unknowable: it may be one), oldest first by name; as the
            file state holds them, or read back from git where a commit
            holds a run the state lacks (`RunDir.from_commit`).
        lost: The ids of the runs only the local run index lists: deleted,
            and never committed — measured to the end, as the index says
            (`runlog reindex` indexes completed runs only), with nothing
            left to read back. Never an invented record.
        first_groups: The first measurements — every run at each first
            position (`answering_run.first_measurement_groups`): a
            measurement among RUNS, no repeat, its record readable.
        run_facts: The facts of every present run of the area — not of PID
            alone: the choice names the runs bound elsewhere among its
            exclusions (`AreaState.run_facts`).
    """

    area: Path
    pid: str
    runs: tuple[RunDir, ...]
    lost: tuple[str, ...]
    first_groups: tuple[tuple[RunDir, ...], ...]
    run_facts: tuple[RunFacts, ...]

    def answering(self, adopted: str | None) -> AnsweringRun:
        """The run every check holds PID to (`answering_run.bound_answering_run`
        over RUN_FACTS): the adopted one (ADOPTED, the head's `[result] run`),
        else the newest completed bound run that reports an intent key —
        with why every other run is left out, or why no choice stands. The
        one call of the choice; the runs' metrics are read here for the
        intent keys."""
        return bound_answering_run(self.area, self.pid, adopted, self.run_facts)

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
        registered; after it the registration stands."""
        return bool(self.lost) or any(is_measurement(rd) for rd in self.runs)

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
        evidence: The area's audit evidence as the file state holds it
            (`Evidence`): records, gaps, changes, ignored files.
        measured: Protocol id → what the area measured of it (`Measured`),
            for every id a run or the index names; `measured_of` answers
            for any id.
    """

    area: Path
    repo: Path | None
    file_state: str
    protocols: tuple[Path, ...]
    protocol_texts: Mapping[Path, str]
    adoption_pending: frozenset[Path]
    runs: tuple[RunDir, ...]
    deleted: tuple[RunDir, ...]
    history_unread: str
    lost: Mapping[str, str]
    run_facts: tuple[RunFacts, ...]
    measured: Mapping[str, Measured]

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
        (the unreadable runs still counted) for an id no run and no index
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
        )


def assemble(
    area: Path,
    repo: Path | None,
    file_state: str,
    runs: Sequence[RunDir],
    deleted: Sequence[RunDir],
    lost: Mapping[str, str],
    history_unread: str = "",
    protocols: Sequence[Path] = (),
    protocol_texts: Mapping[Path, str] | None = None,
    adoption_pending: Collection[Path] = (),
) -> AreaState:
    """The `AreaState` of AREA from what its readers found — RUNS the file
    state holds, DELETED the runs git holds back (HISTORY_UNREAD git's words
    when they could not be listed), LOST the index-only run ids with their
    protocol ids, PROTOCOLS the area's protocol files with PROTOCOL_TEXTS
    (resolved path → text) and ADOPTION_PENDING —, every derived field
    computed here once:
    the one assembly for `state_of` and for a test that builds a state
    without files. Pure but for git's ancestry questions in the first
    measurements' order (REPO None: none asked)."""
    records = sorted([*runs, *deleted], key=lambda rd: rd.dir.name)
    facts = tuple(
        f for rd in sorted(runs, key=lambda rd: rd.dir.name) if (f := facts_of(rd))
    )
    pids = sorted(
        {
            rd.config.protocol.id
            for rd in records
            if rd.config is not None and rd.config.protocol.id
        }
        | set(lost.values())
    )
    measured = {
        pid: _measured(
            area,
            pid,
            records,
            tuple(r for r, p in lost.items() if p == pid),
            repo,
            facts,
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
    )


def _measured(
    area: Path,
    pid: str,
    records: Sequence[RunDir],
    lost: tuple[str, ...],
    repo: Path | None,
    facts: tuple[RunFacts, ...],
) -> Measured:
    """`Measured` of PID over RECORDS (present and deleted runs together):
    the runs bound to PID and the unreadable ones, the first groups among
    them, FACTS of every present run for the choice."""
    ours = tuple(
        rd
        for rd in records
        if rd.error is not None
        or (rd.config is not None and rd.config.protocol.id == pid)
    )
    groups = first_measurement_groups(ours, pid, repo)
    return Measured(area, pid, ours, lost, tuple(tuple(g) for g in groups), facts)


def state_of(area: Path, *, file_state: str = TREE) -> AreaState:
    """The state of AREA as FILE_STATE holds it (`AreaState`): the runs of
    the working tree (TREE, PROPOSED) or of git's index (INDEX), the runs a
    commit holds and that state lacks, the index-only ones. Raises
    `run_index.RunIndexError` on a run index that does not read — whether
    a deleted run was measured cannot be told then —, GitError or
    RuntimeError when git fails."""
    repo = git_root(area)
    staged = file_state == INDEX
    if staged:
        if repo is None:
            raise ValueError(f"{area}: the index of no repository cannot be read")
        runs = indexed_run_dirs(repo, area)
        protocols = sorted(
            p for p in indexed_protocols(repo) if p.parent == area.resolve()
        )
        texts = {
            p.resolve(): t for p in protocols if (t := text_at(repo, p)) is not None
        }
    else:
        runs = run_dirs(area)
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
    lost = {r: p for r, p in indexed_bindings(area).items() if r not in gone}
    return assemble(
        area, repo, file_state, runs, deleted, lost, unread, protocols, texts, pending
    )


def index_names_gone_runs(area: Path) -> bool:
    """Does AREA's local run index list a run whose directory is gone, or
    does the index not read? The cheap question the post-change hook asks
    of every area before it builds a state for the ones that say yes."""
    try:
        return any(not run_path(area, r).is_dir() for r in indexed_bindings(area))
    except RunIndexError:
        return True


class HistoryUnread(RuntimeError):
    """Git could not list or read the runs a commit holds
    (`committed_runs`): its words, for `AreaState.history_unread`."""


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
    rel = runs_path(area).resolve().relative_to(repo.resolve()).as_posix()
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
