"""attempts — the journal of an area's audit attempts, so a record that
went missing is noticed.

`labkit-audit` (MODE preflight or analysis) appends to
`experiments/<NN>-<name>/audits/attempts.jsonl`, one JSON object per line,
never rewriting one:

    {"event": "started", "id": "2026-10-26T09-16-analysis-3f2a", "mode": "analysis",
     "model": "opus", "scope_sha": "fa45c7618423", "started": "2026-10-26T09:16:02",
     "host": "pcstein6"}
    {"event": "ended", "id": "2026-10-26T09-16-analysis-3f2a", "outcome": "failed",
     "file": "2026-10-26T09-16-analysis-failed.toml"}
    {"event": "interrupted", "id": "…", "found_by": "<the id of the next attempt>"}

An attempt is *running* while its process holds the attempt's lock,
*interrupted* when it started and holds no lock any more without an end
(killed, timed out in the agent's shell), *ended* with an outcome:
`record` and `failed` name the file under `audits/` that holds it, `none`
says why no file was written (an answer that did not read). Whether a
process still runs is told by a lock it holds (`fcntl.flock`, released by
the kernel when the process ends), never by a pid, which the system
reuses. A start is checked and written under one lock on the area: two
audits of one area cannot both see "none running" (`begin`).

What the journal gives the gates (`gaps`, a pure function): a file an
ended attempt names that is missing, a file under `audits/` HEAD holds
that is missing, and a journal that is no longer HEAD's plus new lines —
blockers, each naming the attempt or the file. A running, interrupted or
undecidable attempt (started on another host) is named, not held: a
timeout must not lock the area. Why (sixth haiku round, t3; eighth, t18):
agents ran `rm audits/*.toml` before a new attempt, and nothing noticed
that a failed or an earlier record was gone.

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
from labkit.formats.findings import DIR
from labkit.formats.repo import git_root, git_run, text_at
from labkit.formats.runs import now_stamp
from labkit.formats.scope_sha import digest

JOURNAL = "attempts.jsonl"
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
    end —, INTERRUPTED once a later attempt found it without one."""

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


def journal_path(area: Path) -> Path:
    """`AREA/audits/attempts.jsonl`."""
    return area / DIR / JOURNAL


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
) -> Gaps:
    """What the journal and the files say together. ATTEMPTS: the journal
    now; PRESENT, AT_HEAD: the paths under `audits/` (relative to it) in
    the tree and in HEAD; JOURNAL_NOW, JOURNAL_AT_HEAD: the journal's text
    in the tree and in HEAD (None: HEAD holds none); ALIVE: per attempt
    without an end, True running, False its lock is free, None
    undecidable (another host). Pure."""
    blockers: list[str] = []
    notes: list[str] = []
    for a in attempts:
        if a.outcome in ("record", "failed") and a.file not in present:
            blockers.append(
                f"attempt {a.id} ({a.mode}, {a.model}) ended as {a.outcome} in "
                f"{DIR}/{a.file}, and the file is gone — a record of an attempt is "
                f"evidence; restore it (`git checkout -- {DIR}/{a.file}` when "
                f"committed)"
            )
        if a.outcome or a.interrupted:
            continue
        state = alive.get(a.id)
        if state is True:
            notes.append(f"attempt {a.id} ({a.mode}) is running")
        elif state is False:
            notes.append(
                f"attempt {a.id} ({a.mode}, started {a.started}) ended without a "
                f"record — interrupted"
            )
        else:
            notes.append(
                f"attempt {a.id} ({a.mode}) started on {a.host} and has no end — "
                f"whether it runs is not known here"
            )
    for rel in sorted(at_head - present):
        if rel == JOURNAL:
            continue
        blockers.append(
            f"{DIR}/{rel} is committed and gone from the tree — a record of an "
            f"audit is evidence; restore it (`git checkout -- {DIR}/{rel}`)"
        )
    if journal_at_head is not None and not journal_now.startswith(journal_at_head):
        blockers.append(
            f"{DIR}/{JOURNAL} no longer starts with the lines HEAD holds — the "
            f"journal is appended to, never cut; restore it "
            f"(`git checkout -- {DIR}/{JOURNAL}`)"
        )
    return Gaps(blockers, notes)


# ------------------------------------------------------------- the edges


def _lock_dir(area: Path) -> Path:
    """Where the area's locks live: the git dir of its repository (local,
    never committed), else the system's temp dir."""
    root = git_root(area)
    if root is not None:
        r = git_run(["rev-parse", "--git-dir"], root)
        if r.returncode == 0:
            gitdir = Path(r.stdout.strip())
            return (
                gitdir if gitdir.is_absolute() else root / gitdir
            ) / "labkit-audit-locks"
    return Path(tempfile.gettempdir()) / "labkit-audit-locks"


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


def _head_paths(area: Path) -> tuple[set[str], str | None]:
    """(paths under AREA/audits/ that HEAD holds, relative to it; the
    journal's text at HEAD or None) — ({}, None) outside git or before
    the first commit. Raises RuntimeError when git fails."""
    root = git_root(area)
    if root is None:
        return set(), None
    folder = (area / DIR).resolve()
    rel = folder.relative_to(root.resolve()).as_posix()
    r = git_run(["ls-tree", "-r", "-z", "--name-only", "HEAD", "--", rel], root)
    if r.returncode != 0:
        # no HEAD yet, or a `.git` git does not take for a repository: no
        # committed state to compare against
        if any(
            m in r.stderr
            for m in ("Not a valid object name", "not a tree", "not a git repository")
        ):
            return set(), None
        raise RuntimeError(f"git ls-tree failed in {root}: {r.stderr.strip()}")
    held = {p[len(rel) + 1 :] for p in r.stdout.split("\0") if p.startswith(rel + "/")}
    return held, text_at(root, journal_path(area), "HEAD")


def read_journal(area: Path) -> list[Attempt]:
    """The attempts AREA's journal holds; [] without a journal. Raises
    AttemptError on a journal that does not read."""
    path = journal_path(area)
    if not path.is_file():
        return []
    return parse_journal(path.read_text(encoding="utf-8"), f"{DIR}/{JOURNAL}")


def area_gaps(area: Path) -> Gaps:
    """`gaps` for AREA as it is now: its journal, its files, HEAD. Raises
    AttemptError on a journal that does not read, RuntimeError when git
    fails."""
    attempts = read_journal(area)
    path = journal_path(area)
    now = path.read_text(encoding="utf-8") if path.is_file() else ""
    at_head, journal_at_head = _head_paths(area)
    return gaps(
        attempts,
        _paths_under(area / DIR),
        at_head,
        now,
        journal_at_head,
        alive_of(area, attempts),
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
                    [f"attempt {aid} of this area is running" for aid in running]
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
