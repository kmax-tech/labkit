"""attempts — the journal of an area's audit attempts, so a record that
went missing is noticed.

Every model call of `labkit-audit` is an attempt: an audit (`--mode
preflight` or `analysis`), a decision review (`--review`, mode `review`)
and a report review (`--report-review`, mode `report-review`). Each
appends to `experiments/<NN>-<name>/audits/attempts.jsonl`, one JSON
object per line, never rewriting one:

    {"event": "started", "id": "2026-10-26T09-16-analysis-3f2a", "mode": "analysis",
     "model": "opus", "scope_sha": "fa45c7618423", "started": "2026-10-26T09:16:02",
     "host": "pcstein6"}
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
reader saw). It is evidence, and no gate reads it.

The journal starts with the attempts made since it was introduced; a
record older than its journal is named by none, and none is added for it
afterwards — an entry written later would claim a start nobody saw.

Limit: an attempt never committed whose journal line was removed with it
cannot be told from one that never happened — a local check has no
witness beyond the repository.
"""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import json
import os
import secrets
import socket
import tempfile
import time
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from labkit.formats import jsonl
from labkit.formats.files import write_atomic
from labkit.formats.findings import DIR
from labkit.formats.repo import INDEX_REV, files_at, git_dir_path, git_root, text_at
from labkit.formats.runs import now_stamp
from labkit.formats.scope_sha import digest

JOURNAL = "attempts.jsonl"
#: the folder under audits/ that keeps each answer, named by its attempt
ANSWERS = "answers"
EVENTS = ("started", "ended", "interrupted")
#: how an attempt ended: the record, the evidence of a failed call, or no file
OUTCOMES = ("record", "failed", "none")


class AttemptError(ValueError):
    """A journal line that does not read, or an attempt refused: another
    audit of the area is running, or the journal names a missing file."""


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
        raise AttemptError(str(exc)) from exc
    for n, row in rows:
        at = f"{where}:{n}"
        if not isinstance(row, dict) or row.get("event") not in EVENTS:
            raise AttemptError(f"{at}: an event is one of {', '.join(EVENTS)}")
        event, aid = row["event"], row.get("id")
        if not isinstance(aid, str) or not aid:
            raise AttemptError(f"{at}: an event names its attempt (`id`)")
        if event == "started":
            if aid in started:
                raise AttemptError(f"{at}: attempt {aid} started twice")
            started[aid] = _started(aid, row, at)
            continue
        if aid not in started:
            raise AttemptError(f"{at}: {event} of attempt {aid}, never started")
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
        )
    except KeyError as exc:
        raise AttemptError(f"{at}: a start holds {exc.args[0]}") from exc


def _after(was: Attempt, event: str, row: dict, at: str) -> Attempt:
    """WAS after EVENT (`ended` or `interrupted`, ROW at AT). An end after
    an interruption stands: the attempt did finish. Raises AttemptError on
    a second end, an outcome none of OUTCOMES, or `record`/`failed`
    without its file."""
    if was.outcome:
        raise AttemptError(f"{at}: attempt {was.id} ended before")
    if event == "interrupted":
        return dataclasses.replace(was, interrupted=True)
    outcome = row.get("outcome")
    if outcome not in OUTCOMES:
        raise AttemptError(f"{at}: an outcome is one of {', '.join(OUTCOMES)}")
    if outcome != "none" and not row.get("file"):
        raise AttemptError(f"{at}: outcome {outcome} names its file")
    return dataclasses.replace(
        was,
        outcome=outcome,
        file=str(row.get("file") or ""),
        error=str(row.get("error") or ""),
        answer=str(row.get("answer") or ""),
    )


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
    restores a record HEAD lost passes. Raises AttemptError on a HEAD
    journal that does not read. Pure."""
    blockers = [
        f"attempt {a.id} ({a.mode}, {a.model}) ended as {a.outcome} {how} "
        f"{DIR}/{rel}, and the file is gone from the {state} — a record of an "
        f"attempt is evidence; restore it (`git checkout HEAD -- {DIR}/{rel}` "
        f"when committed, `git add` when only unstaged)"
        for a, rel, how in _ended_without(attempts, present)
    ]
    if hold_head and journal_at_head is not None:
        head = parse_journal(journal_at_head, f"HEAD:{DIR}/{JOURNAL}")
        blockers += [
            f"attempt {a.id} ({a.mode}, {a.model}) ended as {a.outcome} {how} "
            f"{DIR}/{rel}, and HEAD's journal names it while HEAD lacks the "
            f"file — the delivered state lost its evidence; restore and commit it"
            for a, rel, how in _ended_without(head, at_head)
        ]
    notes = _open_notes(attempts, alive)
    for rel in sorted(at_head - present):
        if rel == JOURNAL:
            continue
        blockers.append(
            f"{DIR}/{rel} is committed and gone from the {state} — a record of an "
            f"audit is evidence; restore it (`git checkout HEAD -- {DIR}/{rel}`)"
        )
    if journal_at_head is not None and not journal_now.startswith(journal_at_head):
        blockers.append(
            f"{DIR}/{JOURNAL} no longer starts with the lines HEAD holds — the "
            f"journal is appended to, never cut; restore it "
            f"(`git checkout -- {DIR}/{JOURNAL}`)"
        )
    return Gaps(blockers, notes)


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
    never committed), else the system's temp dir."""
    root = git_root(area)
    locks = None if root is None else git_dir_path(root, "labkit-audit-locks")
    return locks or Path(tempfile.gettempdir()) / "labkit-audit-locks"


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
    return held, text_at(root, journal_path(area), rev)


def read_journal(area: Path) -> list[Attempt]:
    """The attempts AREA's journal holds; [] without a journal. Raises
    AttemptError on a journal that does not read."""
    path = journal_path(area)
    if not path.is_file():
        return []
    return parse_journal(path.read_text(encoding="utf-8"), f"{DIR}/{JOURNAL}")


def area_gaps(area: Path, *, staged: bool = False) -> Gaps:
    """`gaps` for AREA: its journal and files in the tree — or, STAGED (the
    pre-commit), as the index holds them: a record removed from the index
    (`git rm --cached`) is gone from the commit though it stays on disk,
    and a record HEAD lost but the index restores is delivered again —
    and HEAD. Raises AttemptError on a journal that does not read,
    RuntimeError when git fails."""
    if staged:
        present, in_index = _git_paths(area, INDEX_REV)
        now = in_index or ""
        attempts = parse_journal(now, f":{DIR}/{JOURNAL}")
    else:
        path = journal_path(area)
        now = path.read_text(encoding="utf-8") if path.is_file() else ""
        attempts = read_journal(area)
        present = _paths_under(area / DIR)
    at_head, journal_at_head = _git_paths(area, "HEAD")
    return gaps(
        attempts,
        present,
        at_head,
        now,
        journal_at_head,
        alive_of(area, attempts),
        "index" if staged else "tree",
        hold_head=not staged,
    )


def _append(area: Path, event: dict[str, str]) -> None:
    """Append EVENT as one line to AREA's journal (one write, flushed)."""
    path = journal_path(area)
    path.parent.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


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
            raise AttemptError(f"attempt {self.id}: its answer is kept already")
        folder = self.area / DIR / ANSWERS
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self.id}.txt"
        write_atomic(path, text)
        self.answer = f"{ANSWERS}/{path.name}"
        return path

    def end(self, outcome: str, *, file: str = "", error: str = "") -> None:
        """Write the attempt's end — OUTCOME with the FILE under audits/
        that holds it, or `none` with the ERROR — and give its lock back.
        Raises AttemptError on an outcome that is none of OUTCOMES, or
        `record`/`failed` without its file."""
        if outcome not in OUTCOMES or (outcome != "none" and not file):
            raise AttemptError(
                f"attempt {self.id}: outcome {outcome!r} — one of "
                f"{', '.join(OUTCOMES)}, record and failed with their file"
            )
        event = {"event": "ended", "id": self.id, "outcome": outcome}
        if file:
            event["file"] = file
        if error:
            event["error"] = error
        if self.answer:
            event["answer"] = self.answer
        with _area_lock(self.area):
            _append(self.area, event)
        self.ended = True
        self._release()

    def _release(self) -> None:
        """Give the attempt's lock back and remove its file."""
        path = Path(self._lock.name)
        fcntl.flock(self._lock, fcntl.LOCK_UN)
        self._lock.close()
        path.unlink(missing_ok=True)


def begin(area: Path, mode: str, model: str, scope_sha: str) -> Running:
    """Start an attempt of MODE on AREA: under the area's lock, read the
    journal and the files, refuse when another attempt runs or a file is
    gone (`gaps`), mark every attempt without an end whose lock is free as
    interrupted (named in `Running.notes`), take the new attempt's lock and
    write its start. Raises AttemptError on a refusal or a journal that
    does not read, RuntimeError when git fails."""
    with _area_lock(area):
        found = area_gaps(area)
        attempts = read_journal(area)
        alive = alive_of(area, attempts)
        running = [aid for aid, state in alive.items() if state is True]
        if running or found.blockers:
            raise AttemptError(
                "; ".join(
                    [
                        f"attempt {aid} of this area is running — wait for it to "
                        f"end, then run this again"
                        for aid in running
                    ]
                    + found.blockers
                )
            )
        stamp = time.strftime("%Y-%m-%dT%H-%M")
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
    running = begin(area, mode, model, scope_sha)
    try:
        yield running
    except BaseException as exc:
        if not running.ended:
            running.end("none", error=f"{type(exc).__name__}: {exc}")
        raise
    if not running.ended:
        running.end("none", error="the command ended before the record")
