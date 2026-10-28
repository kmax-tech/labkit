"""attempts — the journal of an area's audit attempts, so a record that
went missing is noticed.

Every model call of `labkit-audit` is an attempt: an audit (`--mode
preflight` or `analysis`), a decision review (`--review`, mode `review`)
and a report review (`--report-review`, mode `report-review`). Each
appends to `experiments/<NN>-<name>/audits/attempts.jsonl`, one JSON
object per line, never rewriting one:

    {"event": "started", "id": "2026-10-26T09-16-analysis-3f2a", "mode": "analysis",
     "model": "opus", "scope_sha": "fa45c7618423", "block_sha": "0c1d2e3f4a5b",
     "protocol": "PROTOCOL-x.md", "started": "2026-10-26T09:16:02", "host": "pcstein6"}
    {"event": "ended", "id": "2026-10-26T09-16-analysis-3f2a", "outcome": "failed",
     "file": "2026-10-26T09-16-analysis-failed.toml"}
    {"event": "interrupted", "id": "…", "found_by": "<the id of the next attempt>"}

The model's answer is kept before anything reads it, as
`audits/answers/<attempt id>.txt`, and the end names it (`"answer":
"answers/<id>.txt"`) — also when the answer does not read and no record is
written (second fixed-followup pilot: six answers refused on one field,
kept only because the pilot's runner passed `--out`). A kept answer
releases nothing; it is evidence of what the auditor said.

An attempt is *running* while its process holds the attempt's lock,
*interrupted* when it started and holds no lock any more without an end
(killed, timed out in the agent's shell), *ended* with an outcome:
`record` and `failed` name the file under `audits/` that holds it, `none`
says why no file was written (an answer that did not read); an end after
an answer names the kept answer too. Whether a
process still runs is told by a lock it holds (`fcntl.flock`, released by
the kernel when the process ends), never by a pid, which the system
reuses. A start is checked and written under one lock on the area: two
audits of one area cannot both see "none running" (`begin`).

What the journal gives the gates (`gaps`, a pure function): a file an
ended attempt names that is missing (its record, failed attempt or kept
answer), a file under `audits/` HEAD holds
that is missing, and a journal that is no longer HEAD's plus new lines —
blockers, each naming the attempt or the file. A running, interrupted or
undecidable attempt (started on another host) is named, not held: a
timeout must not lock the area. Why (sixth haiku round, t3; eighth, t18):
agents ran `rm audits/*.toml` before a new attempt, and nothing noticed
that a failed or an earlier record was gone; the reviews joined the
journal after the ninth (t5 deleted a report review that named two
claims, and only HEAD would have noticed).

`scope_sha` in a start is the digest of what the attempt was given to
read: the area's stamp for an audit and a decision review, the
fingerprint of its inputs for a report review (`report_reviews.fingerprint`
— an area without scripts has no stamp, and the inputs are what the
reader saw). An audit's start also names the promise block it read
(`block_sha`, `promises.block_stamp`) and the protocol it audited (its
file name in the area, `protocol`); a review's names neither. With the
journal's order they tell whether a later audit supersedes a failed
call (`superseding_record`), which only `labkit-audit --findings` reads.

The journal starts with the attempts made since it was introduced; a
record older than its journal is named by none, and none is added for it
afterwards — an entry written later would claim a start nobody saw.

Every line is also written to a copy outside the working tree, in the
repository's git directory, one file per branch and area
(`journal_copy`); the tree check holds the journal to it: a line the copy
keeps that the journal lacks is a lost attempt, and a file its end names
that is gone is lost evidence (`copy_gaps`). Why: agents deleted
`audits/` whole, journal included, before a first commit (ninth haiku
round t5; first SAB-like draw, 2026-10-27), and then nothing in the tree
was left to notice. The guarantee is exactly that: an attempt made in
this repository on a branch, its journal line or files deleted in the
working tree. Not covered: a detached HEAD (no copy is kept), a fresh
clone, a deleted git directory, attempts made before the copy existed. A
branch deleted and made again under its old name keeps the old copy, and
its lines are then named as lost: remove that copy file. Per branch, so a
switch to a branch with a shorter journal is held to its own copy; held
as a set of lines, so a merge that interleaves two branches' lines and a
journal older than its copy both pass.

Limit: an attempt never committed whose journal line was removed with it
on a detached HEAD, or with the git directory, cannot be told from one
that never happened — a local check has no witness beyond the repository.
"""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import json
import os
import secrets
import shlex
import socket
from urllib.parse import quote
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from labkit.formats import findings, jsonl
from labkit.formats import handovers
from labkit.formats.files import write_atomic, write_atomic_bytes
from labkit.formats.findings import DIR
from labkit.formats.gate import with_way_out
from labkit.formats.repo import (
    INDEX_REV,
    audit_command,
    files_at,
    git_dir_path,
    git_root,
    git_run,
    local_dir,
    text_at,
)
from labkit.formats.runs import name_minute, now_stamp
from labkit.formats.scope_sha import digest

JOURNAL = "attempts.jsonl"
#: the folder under audits/ that keeps each answer, named by its attempt
ANSWERS = "answers"
EVENTS = ("started", "ended", "interrupted")
#: how an attempt ended: the record, the evidence of a failed call, or no file
OUTCOMES = ("record", "failed", "none")


class AttemptError(ValueError):
    """A journal line that does not read, or an attempt refused: another
    audit of the area is running, or the journal names a missing file. WHY
    is the cause, FIX the way out (required where it is raised; None only
    at a site `tests/test_ways_out_data.py` exempts, with its reason); the
    message joins them as a gate line does (`gate.with_way_out`)."""

    def __init__(self, why: str, *, fix: str | None) -> None:
        super().__init__(with_way_out(why, fix))
        self.why = why
        self.fix = fix


#: the way out of a journal that does not read: labkit appends to it and
#: keeps every line in its copy (`journal_copy`)
JOURNAL_WAY = (
    "the journal is appended to, never edited — restore it as labkit wrote it: "
    "from its copy in the git directory (`<git dir>/labkit-attempts/<branch>/"
    "<area>.jsonl`) or as committed (`git checkout HEAD -- <area>/audits/"
    "attempts.jsonl`)"
)


def _copy_way(copy: Path) -> str:
    """The way out of the journal's COPY when it does not read: the copy is
    labkit's own, written beside every journal line, so it is written again
    from the journal."""
    return (
        "the copy is labkit's own, written beside every journal line: write it "
        "again from the journal (`cp <area>/audits/attempts.jsonl "
        f"{shlex.quote(str(copy))}`)"
    )


@dataclass(frozen=True)
class Attempt:
    """One attempt as the journal holds it: its ID, MODE, MODEL, the
    SCOPE_SHA it was started on, when (STARTED) and on which HOST; its
    OUTCOME and FILE (or ERROR) once ended — OUTCOME "" while it has no
    end —, the kept ANSWER when the model answered, INTERRUPTED once a
    later attempt found it without one."""

    id: str
    mode: str
    model: str
    scope_sha: str
    started: str
    host: str
    outcome: str = ""
    file: str = ""
    error: str = ""
    interrupted: bool = False
    answer: str = ""  # the kept answer under audits/, once ended after one
    # the promise block an audit was started on (`promises.NO_BLOCK` for a
    # protocol that declares none, compared like any block) and the protocol
    # it audited, by file name in the area; "" where the start names none —
    # a review's (`begin(block_sha=None, protocol=None)`), or an audit's
    # written by labkit 0.103.0 or earlier: a historical call
    # (`historical_call`), never compared on them
    block_sha: str = ""
    protocol: str = ""


def journal_path(area: Path) -> Path:
    """`AREA/audits/attempts.jsonl`."""
    return area / DIR / JOURNAL


def under_audits(area: Path, path: Path) -> str:
    """PATH as an end names it: relative to `AREA/audits/`, `/`-separated
    (`report-reviews/<minute>-review.toml` for a report review). Raises
    ValueError when PATH lies outside that folder."""
    return path.resolve().relative_to((area / DIR).resolve()).as_posix()


def parse_journal(text: str, where: str) -> list[Attempt]:
    """The attempts of a journal TEXT, in the order they started. Raises
    AttemptError naming WHERE and the line on a line that is no event, an
    end or interruption of an attempt never started, or a second end."""
    started: dict[str, Attempt] = {}
    try:
        rows = jsonl.objects(text, where)
    except ValueError as exc:
        raise AttemptError(str(exc), fix=JOURNAL_WAY) from exc
    for n, row in rows:
        at = f"{where}:{n}"
        if not isinstance(row, dict) or row.get("event") not in EVENTS:
            raise AttemptError(
                f"{at}: an event is one of {', '.join(EVENTS)}", fix=JOURNAL_WAY
            )
        event, aid = row["event"], row.get("id")
        if not isinstance(aid, str) or not aid:
            raise AttemptError(
                f"{at}: an event names its attempt (`id`)", fix=JOURNAL_WAY
            )
        if event == "started":
            if aid in started:
                raise AttemptError(
                    f"{at}: attempt {aid} started twice", fix=JOURNAL_WAY
                )
            started[aid] = _started(aid, row, at)
            continue
        if aid not in started:
            raise AttemptError(
                f"{at}: {event} of attempt {aid}, never started", fix=JOURNAL_WAY
            )
        started[aid] = _after(started[aid], event, row, at)
    return list(started.values())


def _started(aid: str, row: dict, at: str) -> Attempt:
    """The attempt a start ROW (at AT) opens. Raises AttemptError on a key
    it lacks."""
    try:
        return Attempt(
            aid,
            str(row["mode"]),
            str(row["model"]),
            str(row["scope_sha"]),
            str(row["started"]),
            str(row["host"]),
            # a review's start names no block and no protocol, nor an audit's
            # written by 0.103.0 or earlier: such a start reads as it stands, a
            # historical call (`historical_call`), and neither is supplied
            block_sha=str(row.get("block_sha") or ""),
            protocol=str(row.get("protocol") or ""),
        )
    except KeyError as exc:
        raise AttemptError(
            f"{at}: a start holds {exc.args[0]}", fix=JOURNAL_WAY
        ) from exc


def _after(was: Attempt, event: str, row: dict, at: str) -> Attempt:
    """WAS after EVENT (`ended` or `interrupted`, ROW at AT). An end after
    an interruption stands: the attempt did finish. Raises AttemptError on
    a second end, an outcome none of OUTCOMES, or `record`/`failed`
    without its file."""
    if was.outcome:
        raise AttemptError(f"{at}: attempt {was.id} ended before", fix=JOURNAL_WAY)
    if event == "interrupted":
        return dataclasses.replace(was, interrupted=True)
    outcome = row.get("outcome")
    if outcome not in OUTCOMES:
        raise AttemptError(
            f"{at}: an outcome is one of {', '.join(OUTCOMES)}", fix=JOURNAL_WAY
        )
    if outcome != "none" and not row.get("file"):
        raise AttemptError(f"{at}: outcome {outcome} names its file", fix=JOURNAL_WAY)
    return dataclasses.replace(
        was,
        outcome=outcome,
        file=str(row.get("file") or ""),
        error=str(row.get("error") or ""),
        answer=str(row.get("answer") or ""),
    )


def historical_call(at: int | None, block_sha: str, protocol: str) -> bool:
    """Is a failed audit call historical — one whose binding or order the
    journal cannot give: an attempt whose start names no promise block or
    no protocol (BLOCK_SHA or PROTOCOL "", a start written by labkit
    0.103.0 or earlier), or a `-failed.toml` no attempt of the journal
    names (AT None)?"""
    return at is None or not block_sha or not protocol


def superseding_record(
    journal: list[Attempt],
    at: int | None,
    records: Mapping[str, findings.Record],
    mode: str,
    protocol: str,
    block_sha: str,
) -> findings.Record | None:
    """The record that supersedes the failed audit call JOURNAL holds at AT
    (None: no attempt names it) — of MODE, on the PROTOCOL (file name) and
    the promise block BLOCK_SHA it audited — or None. Superseded means: a
    later completed audit of the same mode and the same protocol with the
    same promise block took the call's place, also after a code change.
    The call and its kept answer stay as they are; nothing is confirmed —
    neither the call's content nor the repair of any finding (a recorded
    BLOCKER stays under the follow-up rule, `followup`). Two cases:

    - a historical call (`historical_call`): a later audit of its MODE
      alone, started in the current format (its start names a block and a
      protocol) — the old call cannot be held to a binding or an order the
      journal never named, and none is supplied after the fact; that is
      the documented way from the old format to the new;
    - any other call: a record of the same mode and promise block that a
      later attempt of JOURNAL, started on the same protocol, ended with.

    PROTOCOL is the file name in the area, not the head's `id` (a protocol
    without one must be nameable): a file renamed since counts as another
    protocol, and its earlier calls stay named until it is renamed back and
    audited, or the area is handed over (Max, 2026-10-28).

    RECORDS are the area's records of findings by file name under audits/;
    one no attempt names supersedes nothing, nor does an earlier one. The
    call's BLOCK_SHA is its own: a `-failed.toml` carries it in its file,
    an attempt that ended without a record in its start. The first
    superseding record is returned. Pure."""
    # a file no attempt names (a historical call) has no place in the
    # journal: every attempt of it counts as later
    later = journal if at is None else journal[at + 1 :]
    historical = historical_call(at, block_sha, protocol)
    for a in later:
        r = records.get(a.file) if a.outcome == "record" else None
        if r is None or r.mode != mode:
            continue
        if historical:
            if a.block_sha != "" and a.protocol != "":  # the current format
                return r
        elif a.protocol == protocol and r.block_sha == block_sha:
            return r
    return None


@dataclass(frozen=True)
class Gaps:
    """What `gaps` found: BLOCKERS (a missing file, a journal cut against
    HEAD) and NOTES (running, interrupted, undecidable attempts), one
    sentence each."""

    blockers: list[str]
    notes: list[str]


def gaps(
    attempts: list[Attempt],
    present: set[str],
    at_head: set[str],
    journal_now: str,
    journal_at_head: str | None,
    alive: dict[str, bool | None],
    state: str = "tree",
    *,
    hold_head: bool = True,
    in_tree: frozenset[str] | set[str] = frozenset(),
    kept: Mapping[str, Path] | None = None,
) -> Gaps:
    """What the journal and the files say together. ATTEMPTS: the journal
    in the STATE checked (`tree`, or `index` at the commit); PRESENT,
    AT_HEAD: the paths under `audits/` (relative to it) in that state and
    in HEAD; JOURNAL_NOW, JOURNAL_AT_HEAD: the journal's text in that
    state and in HEAD (None: HEAD holds none); ALIVE: per attempt without
    an end, True running, False its lock is free, None undecidable
    (another host). Each journal is held to its own state: what the
    journal now names to PRESENT, and with HOLD_HEAD what HEAD's journal
    names to HEAD's files — a record dropped from a commit while it stays
    on disk is gone from what was delivered. Without HOLD_HEAD (the
    commit) the state checked is what will be delivered: its journal,
    which must start with HEAD's, is held to its files, so a commit that
    restores a record HEAD lost passes. Each gone file names the restore
    that works for it (`restore_way`): IN_TREE, the files on disk when the
    state checked is the index; KEPT, the files the branch's evidence copy
    holds (`kept_files`). Raises AttemptError on a HEAD journal that does
    not read. Pure."""
    kept = kept or {}
    blockers = [
        f"attempt {a.id} ({a.mode}, {a.model}) ended as {a.outcome} {how} "
        f"{DIR}/{rel}, and the file is gone from the {state} — a record of an "
        f"attempt is evidence; "
        + restore_way(rel, at_head=at_head, in_tree=in_tree, kept=kept)
        for a, rel, how in _ended_without(attempts, present)
    ]
    if hold_head and journal_at_head is not None:
        head = parse_journal(journal_at_head, f"HEAD:{DIR}/{JOURNAL}")
        blockers += [
            f"attempt {a.id} ({a.mode}, {a.model}) ended as {a.outcome} {how} "
            f"{DIR}/{rel}, and HEAD's journal names it while HEAD lacks the "
            f"file — the delivered state lost its evidence; "
            + _commit_way(rel, on_disk=present, kept=kept)
            for a, rel, how in _ended_without(head, at_head)
        ]
    notes = _open_notes(attempts, alive)
    for rel in sorted(at_head - present):
        if rel == JOURNAL:
            continue
        blockers.append(
            f"{DIR}/{rel} is committed and gone from the {state} — a record of an "
            f"audit is evidence; "
            + restore_way(rel, at_head=at_head, in_tree=in_tree, kept=kept)
        )
    if journal_at_head is not None and not journal_now.startswith(journal_at_head):
        blockers.append(
            f"{DIR}/{JOURNAL} no longer starts with the lines HEAD holds — the "
            f"journal is appended to, never cut; restore it "
            f"(`git checkout -- {DIR}/{JOURNAL}`)"
        )
    return Gaps(blockers, notes)


def _commit_way(rel: str, *, on_disk: set[str], kept: Mapping[str, Path]) -> str:
    """How `audits/REL`, which HEAD's journal names and HEAD lacks, gets back
    into a commit: staged when ON_DISK holds it, restored from the evidence
    copy (KEPT); LOST_WAY when nothing keeps it. Reached in the tree state
    only (`gaps` holds HEAD's journal there, not at the commit), so ON_DISK
    is the state's own files, and HEAD by definition cannot restore it."""
    way = restore_command(rel, at_head=set(), in_tree=on_disk, kept=kept)
    return f"bring it back and commit it — {way}" if way else LOST_WAY


def _ended_without(
    attempts: list[Attempt], files: set[str]
) -> list[tuple[Attempt, str, str]]:
    """(attempt, path, how the end names it) for every file an ended attempt
    of ATTEMPTS names — its record or failed attempt (`record`, `failed`),
    its kept answer — that is not among FILES."""
    out: list[tuple[Attempt, str, str]] = []
    for a in attempts:
        named = [(a.file, "in")] if a.outcome in ("record", "failed") else []
        named += [(a.answer, "with its answer kept in")] if a.answer else []
        out += [(a, rel, how) for rel, how in named if rel not in files]
    return out


def _open_notes(attempts: list[Attempt], alive: dict[str, bool | None]) -> list[str]:
    """A sentence per attempt of ATTEMPTS without an end: running,
    interrupted (its lock free) or undecidable (another host), by ALIVE."""
    notes: list[str] = []
    for a in attempts:
        if a.outcome or a.interrupted:
            continue
        running = alive.get(a.id)
        if running is True:
            notes.append(f"attempt {a.id} ({a.mode}) is running")
        elif running is False:
            notes.append(
                f"attempt {a.id} ({a.mode}, started {a.started}) ended without a "
                f"record — interrupted"
            )
        else:
            notes.append(
                f"attempt {a.id} ({a.mode}) started on {a.host} and has no end — "
                f"whether it runs is not known here"
            )
    return notes


# ------------------------------------------------------------- the edges


def _lock_dir(area: Path) -> Path:
    """Where the area's locks live: the git dir of its repository (local,
    never committed), else the system's temp dir (`repo.local_dir`)."""
    return local_dir(area, "labkit-audit-locks")


def _lock_file(area: Path, name: str) -> Path:
    """The lock file NAME of AREA: `<lock dir>/<area digest>-<name>.lock`."""
    key = digest(str(area.resolve()).encode())
    folder = _lock_dir(area)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{key}-{name}.lock"


def _is_free(path: Path) -> bool:
    """Can the lock at PATH be taken now? (taken and given back at once)
    A missing lock file is free."""
    if not path.exists():
        return True
    with path.open("a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(fh, fcntl.LOCK_UN)
        return True


def alive_of(area: Path, attempts: list[Attempt]) -> dict[str, bool | None]:
    """Per attempt of AREA without an end: True while its process holds
    its lock, False when the lock is free, None when it started on another
    host. Reads lock files only."""
    here = socket.gethostname()
    out: dict[str, bool | None] = {}
    for a in attempts:
        if a.outcome or a.interrupted:
            continue
        out[a.id] = None if a.host != here else not _is_free(_lock_file(area, a.id))
    return out


#: what a gone file's line says when nothing restores it
NOTHING_KEEPS = "no commit and no copy keeps it: it is lost"
LOST_WAY = f"{NOTHING_KEEPS} — acknowledge the loss in a handover"


def restore_way(
    rel: str,
    *,
    at_head: set[str],
    in_tree: frozenset[str] | set[str],
    kept: Mapping[str, Path],
) -> str:
    """How the evidence file `audits/REL` comes back (`restore_command`), or
    LOST_WAY when nothing restores it."""
    return restore_command(rel, at_head=at_head, in_tree=in_tree, kept=kept) or LOST_WAY


def restore_command(
    rel: str,
    *,
    at_head: set[str],
    in_tree: frozenset[str] | set[str],
    kept: Mapping[str, Path],
) -> str | None:
    """How the evidence file `audits/REL` comes back, the one way that works
    here: staged when it is still on disk (IN_TREE), checked out when HEAD
    holds it (AT_HEAD), copied from the branch's evidence copy when that
    keeps it (KEPT, `kept_files`); None when nothing keeps it — never a
    restore that cannot work: a record deleted before it was ever staged
    was offered `git checkout` and `git add`, and neither could bring it
    back (fourth SAB-like draw, 2026-10-28). Commands run in the area."""
    path = f"{DIR}/{rel}"
    if rel in in_tree:
        return f"stage it (`git add {shlex.quote(path)}`)"
    if rel in at_head:
        return f"restore it (`git checkout HEAD -- {shlex.quote(path)}`)"
    if rel in kept:
        folder = shlex.quote(str(Path(path).parent))
        return (
            f"restore it as the audit wrote it (`mkdir -p {folder} && cp "
            f"{shlex.quote(str(kept[rel]))} {shlex.quote(path)}`, in the area), then "
            f"decide its findings again where they were decided — never "
            f"delete a record, an outdated one included"
        )
    return None


def _paths_under(folder: Path) -> set[str]:
    """Every file under FOLDER, relative to it, `/`-separated."""
    if not folder.is_dir():
        return set()
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}


def _git_paths(area: Path, rev: str) -> tuple[set[str], str | None]:
    """(paths under AREA/audits/ that REV holds — "HEAD", or INDEX_REV for
    the index —, relative to it; the journal's text there or None) —
    ({}, None) outside git or before the first commit. Raises RuntimeError
    when git fails."""
    root = git_root(area)
    held = None if root is None else files_at(root, area / DIR, rev)
    if root is None or held is None:
        # no repository git takes, or no HEAD yet: no committed state to
        # compare against
        return set(), None
    try:
        text = text_at(root, journal_path(area), rev)
    except UnicodeError as exc:
        raise AttemptError(
            f"{rev}:{DIR}/{JOURNAL}: journal is not UTF-8: {exc}", fix=JOURNAL_WAY
        ) from exc
    return held, text


def _tree_journal(area: Path) -> str:
    """AREA's journal text in the working tree, "" without a journal.
    Raises AttemptError when its bytes are not UTF-8."""
    path = journal_path(area)
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise AttemptError(
            f"{DIR}/{JOURNAL}: journal is not UTF-8: {exc}", fix=JOURNAL_WAY
        ) from exc


def read_journal(area: Path) -> list[Attempt]:
    """The attempts AREA's journal holds; [] without a journal. Raises
    AttemptError on a journal that does not read."""
    return parse_journal(_tree_journal(area), f"{DIR}/{JOURNAL}")


def expected_evidence(area: Path) -> tuple[set[str], list[str]]:
    """Known audit paths and explicit unreadable-journal errors for a handover.

    Take the available tree, HEAD and parseable journals; retain errors
    instead of pretending an unreadable journal names no evidence.
    """
    root = git_root(area)
    expected = _paths_under(area / DIR)
    if root is not None:
        expected |= files_at(root, area / DIR, "HEAD") or set()
    errors: list[str] = []
    for revision in (None, "HEAD"):
        try:
            if revision is None:
                known = read_journal(area)
            else:
                text = text_at(root, journal_path(area), revision) if root else None
                known = parse_journal(text or "", f"{revision}:{DIR}/{JOURNAL}")
            for attempt in known:
                if attempt.file:
                    expected.add(attempt.file)
                if attempt.answer:
                    expected.add(attempt.answer)
        except (AttemptError, UnicodeError) as exc:
            errors.append(str(exc))
    for path in handovers.record_paths(area):
        try:
            expected.update(handovers.read_handover(path).expected)
        except handovers.HandoverError as exc:
            errors.append(str(exc))
    return expected, errors


def area_gaps(area: Path, *, staged: bool = False) -> Gaps:
    """`gaps` for AREA: its journal and files in the tree — or, STAGED (the
    pre-commit), as the index holds them: a record removed from the index
    (`git rm --cached`) is gone from the commit though it stays on disk,
    and a record HEAD lost but the index restores is delivered again —
    and HEAD; in the tree, not STAGED, also the journal's copy in the git
    directory (`journal_copy`, `copy_gaps`); STAGED, also every file the
    tree's journal or the copy names that neither the index nor the tree
    holds (`unstaged_losses`); then the paths a handover record keeps owed
    (`handovers.missing_paths`). Each gone file names its restore
    (`restore_way`, from the evidence copy where it keeps one; a loss a
    handover recorded its `restore_command`, or NOTHING_KEEPS — the
    handover is written already). A handover record that does not read
    is one more blocker beside the others, never in their place. Raises
    AttemptError on a journal that does not read, RuntimeError when git
    fails."""
    if staged:
        present, in_index = _git_paths(area, INDEX_REV)
        now = in_index or ""
        attempts = parse_journal(now, f":{DIR}/{JOURNAL}")
    else:
        now = _tree_journal(area)
        attempts = parse_journal(now, f"{DIR}/{JOURNAL}")
        present = _paths_under(area / DIR)
    at_head, journal_at_head = _git_paths(area, "HEAD")
    kept = kept_files(area)
    in_tree = _paths_under(area / DIR) if staged else set()
    copy = journal_copy(area)
    copy_text = _copy_text(copy)
    if staged:
        # the commit carries what is staged; a file the tree's journal or the
        # copy names and neither the index nor the tree holds is gone from it
        # all the same — a record deleted before it was ever staged passed the
        # commit (fourth SAB-like draw, 2026-10-28)
        lost_here = unstaged_losses(
            attempts,
            parse_journal(_tree_journal(area), f"{DIR}/{JOURNAL}"),
            copy_ends(copy_text, copy) if copy is not None else [],
            present | in_tree | at_head,
            kept,
        )
    else:
        # the tree: the stop and the next audit hold the journal to its copy
        lost_here = (
            copy_gaps(now, copy_text, copy, present, at_head=at_head, kept=kept)
            if copy is not None and copy_text is not None
            else []
        )
    found = gaps(
        attempts,
        present,
        at_head,
        now,
        journal_at_head,
        alive_of(area, attempts),
        "index" if staged else "tree",
        hold_head=not staged,
        in_tree=in_tree,
        kept=kept,
    )
    try:
        lost = [
            f"{DIR}/{name}: lost, as a handover recorded — "
            + (
                f"{way}; until it is back audits and adoption stay refused"
                if (
                    way := restore_command(
                        name, at_head=at_head, in_tree=in_tree, kept=kept
                    )
                )
                else f"{NOTHING_KEEPS}, and audits and adoption stay refused"
            )
            + " (a current handover lets only the stop and the commit pass)"
            for name in handovers.missing_paths(area, present, staged=staged)
        ]
    except handovers.HandoverError as exc:
        # raised as AttemptError it replaced every gap found above (audit
        # 2026-10-27, third, K1)
        lost = [str(exc)]
    return Gaps([*found.blockers, *lost_here, *lost], found.notes)


def _copy_text(copy: Path | None) -> str | None:
    """The text of the journal's COPY, None where there is none. Raises
    AttemptError when its bytes are not UTF-8."""
    if copy is None or not copy.is_file():
        return None
    try:
        return copy.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise AttemptError(
            f"{copy}: the journal's copy is not UTF-8: {exc}", fix=_copy_way(copy)
        ) from exc


def copy_ends(copy_text: str | None, copy: Path) -> list[dict]:
    """The `ended` events of the journal's copy (its text COPY_TEXT), [] for
    none. Raises AttemptError on a line that is not a JSON object, naming
    the copy's line."""
    if copy_text is None:
        return []
    try:
        parsed = jsonl.objects(copy_text, str(copy))
    except ValueError as exc:
        raise AttemptError(str(exc), fix=_copy_way(copy)) from exc
    out = []
    for n, event in parsed:
        if not isinstance(event, dict):
            raise AttemptError(f"{copy}:{n}: not a JSON object", fix=_copy_way(copy))
        if event.get("event") == "ended":
            out.append(event)
    return out


def unstaged_losses(
    staged: list[Attempt],
    tree: list[Attempt],
    copied: list[dict],
    held: set[str],
    kept: Mapping[str, Path],
) -> list[str]:
    """At the commit: every file an ended attempt of the TREE's journal or
    of the copy's ended events COPIED names, that no ended attempt of the
    STAGED journal names already (`gaps` says those) and that HELD (index,
    tree and HEAD together) lacks — gone before it was staged. Each with
    its restore (`restore_way`). Pure."""
    told = {(a.id, rel) for a, rel, _ in _ended_without(staged, set())}
    named: dict[tuple[str, str], str] = {}
    for a, rel, _ in _ended_without(tree, set()):
        named.setdefault((a.id, rel), f"{a.id} ({a.mode}, {a.model})")
    for e in copied:
        for rel in (e.get("file"), e.get("answer")):
            if isinstance(rel, str) and rel:
                named.setdefault((str(e.get("id", "?")), rel), str(e.get("id", "?")))
    return [
        f"attempt {who} ended naming {DIR}/{rel}, and the file is in neither the "
        f"tree nor the index — the commit would deliver the area without it, a "
        f"record of an attempt is evidence; "
        + restore_way(rel, at_head=set(), in_tree=set(), kept=kept)
        for (aid, rel), who in named.items()
        if (aid, rel) not in told and rel not in held
    ]


@dataclass(frozen=True)
class Integrity:
    """An area's audit evidence as one state holds it: the records that
    read, and every problem that keeps the rest from counting."""

    records: list[findings.Record]
    problems: list[str]


def area_integrity(area: Path, *, staged: bool = False) -> Integrity:
    """AREA's readable audit records and its integrity problems in the tree
    or, STAGED, the index: every record or attempt that is gone
    (`area_gaps`), a journal that does not read, and each record that does
    not read (`findings.record_status`) — a broken file hides no other
    record. The one assembly the stop/commit, `labkit-audit --findings` and
    the handover read. Raises RuntimeError when git fails."""
    status = findings.record_status(area, staged=staged)
    return Integrity(
        status.records, [*evidence_gaps(area, staged=staged), *status.errors]
    )


def evidence_gaps(area: Path, *, staged: bool = False) -> list[str]:
    """Why AREA's audit evidence does not stand in the tree or, STAGED, the
    index, one sentence each with its restore: every file gone
    (`area_gaps`), or the journal that does not read. In the tree these are
    what `begin` refuses every new attempt on — an audit, a decision review
    and a report review alike — so a gate whose way out is such an attempt
    names them instead. Raises RuntimeError when git fails."""
    try:
        return area_gaps(area, staged=staged).blockers
    except AttemptError as exc:
        return [str(exc)]


def gone_line(gaps: list[str]) -> str:
    """The sentence that labkit-audit starts no audit or review while the
    area's audit evidence is gone — the cause a gate names when its way out
    needs such an attempt (`begin`): GAPS (`evidence_gaps`, not empty), the
    first with its restore, how many more `labkit-audit <area> --findings`
    lists."""
    more = f" (and {len(gaps) - 1} more)" if len(gaps) > 1 else ""
    return (
        "labkit-audit starts no audit or review while the area's audit "
        f"evidence is gone: {gaps[0]}{more}"
    )


def _append(area: Path, event: dict[str, str]) -> None:
    """Append EVENT as one line to AREA's journal and to its copy in the
    git directory (`journal_copy`, none on a detached HEAD or outside
    git) — each one write, flushed. Raises OSError when either cannot be
    written: an attempt the copy misses is one the check cannot see."""
    line = json.dumps(event, ensure_ascii=False) + "\n"
    path = journal_path(area)
    path.parent.mkdir(exist_ok=True)
    copy = journal_copy(area)
    if copy is not None:
        copy.parent.mkdir(parents=True, exist_ok=True)
    for target in (path, *([copy] if copy is not None else [])):
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())


#: the folder in the repository's common git directory that keeps the
#: journal copies, one file per branch and area (`journal_copy`)
COPY_DIR = "labkit-attempts"


def journal_copy(area: Path) -> Path | None:
    """Where AREA's journal is copied:
    `<common git dir>/labkit-attempts/<branch>/<area>.jsonl`, the branch and
    the area's path from the repository root each quoted to one file name.
    None outside a repository and on a detached HEAD: a copy belongs to a
    branch, so a switch to a branch with a shorter journal meets that
    branch's copy. Raises GitError when git cannot run."""
    root = git_root(area)
    if root is None:
        return None
    branch = git_run(["symbolic-ref", "--short", "-q", "HEAD"], root)
    base = git_dir_path(root, COPY_DIR, common=True)
    if branch.returncode != 0 or base is None:
        return None
    rel = area.resolve().relative_to(root.resolve()).as_posix()
    return base / quote(branch.stdout.strip(), safe="") / f"{quote(rel, safe='')}.jsonl"


def evidence_copy(area: Path) -> Path | None:
    """Where the files AREA's attempts end with are copied as written —
    their record or failed attempt and their kept answer: the directory
    beside the journal's copy (`journal_copy` without `.jsonl`), each file
    under its path below `audits/`. None where no journal copy is kept.
    The copy restores a file deleted before it was ever staged; it is no
    check of a record's content — `--decide` rewrites a record, its copy
    stays as the audit wrote it."""
    copy = journal_copy(area)
    return None if copy is None else copy.with_suffix("")


def kept_files(area: Path) -> dict[str, Path]:
    """The files AREA's evidence copy keeps (`evidence_copy`), by their path
    below `audits/`; {} without one."""
    base = evidence_copy(area)
    if base is None or not base.is_dir():
        return {}
    return {p.relative_to(base).as_posix(): p for p in base.rglob("*") if p.is_file()}


def _keep(area: Path, rels: list[str]) -> None:
    """Copy the files `audits/<rel>` of AREA for each of RELS into its
    evidence copy (`evidence_copy`), each written whole. Nothing where no
    copy is kept. Raises OSError when a file cannot be read or written: an
    attempt's file the copy misses cannot be restored from it."""
    base = evidence_copy(area)
    if base is None:
        return
    for rel in rels:
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        write_atomic_bytes(target, (area / DIR / rel).read_bytes())


def copy_gaps(
    journal_now: str,
    copy_text: str,
    copy: Path,
    present: set[str],
    *,
    at_head: set[str] | None = None,
    kept: Mapping[str, Path] | None = None,
) -> list[str]:
    """What the tree lost against the journal's COPY (its text COPY_TEXT):
    every attempt with a line the copy keeps and JOURNAL_NOW lacks, and
    every file an end among those lines names that PRESENT (the paths under
    `audits/`) lacks. The journal is held to the copy as a set of lines — a
    merge may interleave two branches' lines, and lines older than the copy
    are the journal's own; each gone file names its restore (`restore_way`,
    AT_HEAD and KEPT as `gaps` takes them). Pure; a lost copy line that is
    not a JSON object raises AttemptError naming the copy and its line — the stop reports it
    as a problem (`area_integrity`), it does not end in a traceback."""
    in_journal = set(journal_now.splitlines())
    lines = jsonl.record_lines(copy_text)
    try:
        parsed = jsonl.objects(copy_text, str(copy))  # names the copy's own line
    except ValueError as exc:
        raise AttemptError(str(exc), fix=_copy_way(copy)) from exc
    lost: list[str] = []
    events: list[dict] = []
    for n, event in parsed:
        if lines[n - 1] in in_journal:
            continue
        if not isinstance(event, dict):
            raise AttemptError(f"{copy}:{n}: not a JSON object", fix=_copy_way(copy))
        lost.append(lines[n - 1])
        events.append(event)
    if not lost:
        return []
    ids = list(dict.fromkeys(str(e.get("id", "?")) for e in events))
    out = [
        f"{DIR}/{JOURNAL} lost {len(lost)} line(s) of attempt(s) {', '.join(ids)} that "
        f"this branch's copy keeps ({copy}) — the journal is appended to, never "
        f"cut; restore them: `mkdir -p {DIR} && touch {DIR}/{JOURNAL} && grep -vxFf "
        f"{DIR}/{JOURNAL} {copy} >> {DIR}/{JOURNAL}` (in the area)"
    ]
    for e in events:
        if e.get("event") != "ended":
            continue
        for rel in (e.get("file"), e.get("answer")):
            if isinstance(rel, str) and rel and rel not in present:
                out.append(
                    f"attempt {e.get('id', '?')} ended naming {DIR}/{rel}, and the file "
                    f"is gone from the tree with its journal line — a record of an "
                    f"attempt is evidence; "
                    + restore_way(
                        rel, at_head=at_head or set(), in_tree=set(), kept=kept or {}
                    )
                )
    return out


@contextlib.contextmanager
def _area_lock(area: Path) -> Generator[None]:
    """Hold AREA's lock: the check and the start of an attempt, an end."""
    with _lock_file(area, "area").open("a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


class Running:
    """An attempt begun by this process: holds its lock until `end`. The
    lock lives with this object — dropped unended, it is collected and
    the lock freed, and the next attempt reads this one as interrupted;
    keep it until the attempt ends."""

    def __init__(self, area: Path, aid: str, lock: IO[str], notes: list[str]) -> None:
        self.area, self.id, self._lock, self.notes = area, aid, lock, notes
        self.ended = False
        self.answer = ""  # the kept answer under audits/, once `keep_answer` ran

    def keep_answer(self, text: str) -> Path:
        """Keep the model's answer TEXT, unchanged, as
        `audits/answers/<attempt id>.txt` before anything reads it, and
        remember it for the end. Returns the path. Side effect: the file;
        a second answer for one attempt raises AttemptError."""
        if self.answer:
            raise AttemptError(
                f"attempt {self.id}: its answer is kept already", fix=None
            )
        folder = self.area / DIR / ANSWERS
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self.id}.txt"
        write_atomic(path, text)
        self.answer = f"{ANSWERS}/{path.name}"
        return path

    def end(self, outcome: str, *, file: str = "", error: str = "") -> None:
        """Write the attempt's end — OUTCOME with the FILE under audits/
        that holds it, or `none` with the ERROR — and give its lock back.
        The FILE and the kept answer go into the evidence copy first
        (`evidence_copy`).
        Raises AttemptError on an outcome that is none of OUTCOMES, or
        `record`/`failed` without its file."""
        if outcome not in OUTCOMES or (outcome != "none" and not file):
            raise AttemptError(
                f"attempt {self.id}: outcome {outcome!r} — one of "
                f"{', '.join(OUTCOMES)}, record and failed with their file",
                fix=None,
            )
        event = {"event": "ended", "id": self.id, "outcome": outcome}
        if file:
            event["file"] = file
        if error:
            event["error"] = error
        if self.answer:
            event["answer"] = self.answer
        with _area_lock(self.area):
            # the files before the line that names them: a journal line
            # whose file the copy lacks could not be restored from it
            _keep(self.area, [rel for rel in (file, self.answer) if rel])
            _append(self.area, event)
        self.ended = True
        self._release()

    def _release(self) -> None:
        """Give the attempt's lock back and remove its file."""
        path = Path(self._lock.name)
        fcntl.flock(self._lock, fcntl.LOCK_UN)
        self._lock.close()
        path.unlink(missing_ok=True)


def begin(
    area: Path,
    mode: str,
    model: str,
    scope_sha: str,
    *,
    block_sha: str | None,
    protocol: str | None,
) -> Running:
    """Start an attempt of MODE on AREA: under the area's lock, read the
    journal and the files, refuse when another attempt runs or a file is
    gone (`gaps`), mark every attempt without an end whose lock is free as
    interrupted (named in `Running.notes`), take the new attempt's lock and
    write its start — with BLOCK_SHA, the promise block an audit reads, and
    PROTOCOL, the file name of the protocol it audits (None for a review,
    which binds neither of its own; the start then names none and reads
    back as "", as a start of labkit 0.103.0 or earlier does:
    `historical_call`). Raises AttemptError on a refusal or a journal that
    does not read, RuntimeError when git fails."""
    with _area_lock(area):
        found = area_gaps(area)
        attempts = read_journal(area)
        alive = alive_of(area, attempts)
        running = [aid for aid, state in alive.items() if state is True]
        if running or found.blockers:
            raise AttemptError(
                "; ".join(
                    [f"attempt {aid} of this area is running" for aid in running]
                    + found.blockers
                ),
                fix="; ".join(
                    (["wait for it to end, then run this again"] if running else [])
                    + (
                        [
                            f"`{audit_command(area, '--findings')}` names each "
                            f"with what restores it, and the handover"
                        ]
                        if found.blockers
                        else []
                    )
                ),
            )
        stamp = name_minute()
        aid = f"{stamp}-{mode}-{secrets.token_hex(2)}"
        for a in attempts:
            if alive.get(a.id) is False:
                _append(area, {"event": "interrupted", "id": a.id, "found_by": aid})
        lock = _lock_file(area, aid).open("a")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _append(
            area,
            {
                "event": "started",
                "id": aid,
                "mode": mode,
                "model": model,
                "scope_sha": scope_sha,
                **({"block_sha": block_sha} if block_sha is not None else {}),
                **({"protocol": protocol} if protocol is not None else {}),
                "started": now_stamp(),
                "host": socket.gethostname(),
            },
        )
        return Running(area, aid, lock, found.notes)


@contextlib.contextmanager
def attempt(area: Path, mode: str, model: str, scope_sha: str) -> Generator[Running]:
    """`begin` an attempt of MODE on AREA for a call that starts and ends in
    one block, and make sure it ends: the block ends it with its record
    (`Running.end`); a block that raises ends it `none` with the
    exception's words, one that returns without an end with "the command
    ended before the record". The decision and the report review use it;
    the analysis audit ends its attempt across two steps itself
    (`gates.audit`). Raises what `begin` raises, before any call."""
    # reviews only: they bind no promise block or protocol of their own
    running = begin(area, mode, model, scope_sha, block_sha=None, protocol=None)
    try:
        yield running
    except BaseException as exc:
        if not running.ended:
            running.end("none", error=f"{type(exc).__name__}: {exc}")
        raise
    if not running.ended:
        running.end("none", error="the command ended before the record")
