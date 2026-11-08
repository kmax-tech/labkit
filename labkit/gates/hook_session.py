"""hook_session — what the agent hooks know of their session and how they
answer the harness: the repository the hooks hold (`project_dir`,
`session_repo`: the adapter's explicit project directory, else
`CLAUDE_PROJECT_DIR`, else the event's cwd, its root found from a
subdirectory too), the additional context a hook returns
(`tell_context`), the stop's base and held files under the git directory
(`keep_stop_base`, `stop_base_file`, `stop_held_file`,
`state_fingerprint`), the commits a session made (`committed_in_session`)
and the session log.

session log
    Every stop also appends one line to the repo's `.git/labkit-sessions.jsonl`
    (inside .git: local, never committed): the session id, the transcript
    path, the time, and the runs whose run_id dates from after this
    session's previous stop (or its first transcript record). `claude-hook
    sessions --run RUN_ID` finds the session — and so the transcript — a run
    came from: what the agent read and decided before it, for debugging.

`claude-hook sessions` exits 0, or 1 when no session made the run.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from labkit.formats import (
    console,
    files,
    jsonl,
    runs,
)
from labkit.formats.repo import (
    rel_posix,
    repo_protocols,
    fork_point,
    git_dir_path,
    git_root,
    head_before,
    head_sha,
    paths_committed_since,
    touched_paths,
)
from labkit.formats.digests import file_digest
from labkit.formats.digests import digest as scope_digest


def project_dir(event: dict | None = None) -> Path:
    """The explicit project_dir, else CLAUDE_PROJECT_DIR, event cwd or process cwd.

    Codex supplies project_dir so an inherited Claude environment cannot
    select another repository. Claude Code uses its project environment.
    """
    project = (event or {}).get("project_dir") or os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(project or (event or {}).get("cwd") or os.getcwd())


def session_repo(event: dict | None = None) -> Path | None:
    """The repository the hooks hold: the git root (`repo.git_root`) of the
    project directory (`project_dir`), found from a subdirectory too — a
    session started below the repo root has no `.git` of its own there.
    None outside every repository."""
    return git_root(project_dir(event))


def tell_context(event_name: str, text: str) -> None:
    """Hand text back to the agent as additionalContext."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": text,
                }
            },
            ensure_ascii=False,
        )
    )


def session_log(repo: Path) -> Path | None:
    """`.git/labkit-sessions.jsonl` of the repo (the common git dir, so a
    worktree logs into its main repo); None outside git."""
    return git_dir_path(repo, "labkit-sessions.jsonl", common=True)


def read_sessions(log: Path) -> list[dict]:
    """The log's records; a line that is not JSON names its number
    (`jsonl.objects`) and ends the command."""
    try:
        return jsonl.data_rows(log.read_text(encoding="utf-8"), str(log))
    except ValueError as exc:
        raise console.Refused("claude-hook", str(exc)) from exc


def _transcript_start(transcript: str | None) -> datetime | None:
    """The first record's timestamp, in local time (run_ids are local)."""
    if not transcript or not Path(transcript).is_file():
        return None
    with open(transcript, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                # the first record of a transcript that may be hundreds of
                # megabytes, never the whole; home: jsonl.objects
                stamp = json.loads(line).get("timestamp")
                if isinstance(stamp, str):
                    utc = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                    return utc.astimezone().replace(tzinfo=None)
                return None
    return None


def record_session(repo: Path, event: dict, now: datetime | None = None) -> dict | None:
    """Append this stop to the session log; returns the record (None without
    a session id or outside git)."""
    session = event.get("session_id")
    log = session_log(repo)
    if not session or log is None:
        return None
    now = now or datetime.now()
    earlier = (
        [r for r in read_sessions(log) if r.get("session") == session]
        if log.is_file()
        else []
    )
    since = (
        datetime.fromisoformat(earlier[-1]["stopped"])
        if earlier
        else _transcript_start(event.get("transcript_path"))
    )
    # every area's runs through the one walk (`runs.run_dirs`); the areas
    # are where the protocols are (`repo_protocols` skips .venv and data)
    session_runs = sorted(
        str(rd.dir.relative_to(repo))
        for area in {p.parent for p in repo_protocols(repo)}
        for rd in runs.run_dirs(area)
        if (started := runs.run_started(rd.dir.name)) is not None
        and (since is None or started >= since.replace(microsecond=0))
        and started <= now
    )
    record = {
        "session": session,
        "transcript": event.get("transcript_path"),
        "stopped": now.strftime(runs.RECORD_TIME),
        "runs": session_runs,
    }
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def sessions(argv: list[str]) -> int:
    """Print the session log, or the session(s) a run came from."""
    if "--run" in argv and argv.index("--run") + 1 >= len(argv):
        console.refuse("claude-hook sessions", "--run needs a RUN_ID")
        return 2
    run = argv[argv.index("--run") + 1] if "--run" in argv else None
    repo = project_dir()
    log = session_log(repo)
    if log is None or not log.is_file():
        console.refuse(
            "claude-hook sessions",
            f"no session log in {repo} — no session has stopped here yet",
        )
        return 2
    hits = [
        r
        for r in read_sessions(log)
        if run is None or any(Path(x).name == run for x in r.get("runs", []))
    ]
    for r in hits:
        print(
            f"{r['stopped']}  {r['session']}  {r.get('transcript')}  runs: {', '.join(r.get('runs') or []) or '—'}"
        )
    if run is not None and not hits:
        print(f"claude-hook: no logged session made run {run}")
        return 1
    return 0


#: a session id as a file name: what Claude Code writes (a UUID), nothing
#: that could leave the directory
_SESSION_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def stop_base_file(repo: Path, session: str) -> Path | None:
    """`<git dir>/labkit-stop-base/<SESSION>` — this worktree's git dir, as
    each worktree has its own HEAD — holding the commit the session's
    stop compares against; None outside git or for a session id that is
    no file name."""
    if not _SESSION_FILE.match(session):
        return None
    base = git_dir_path(repo, "labkit-stop-base")
    return None if base is None else base / session


def stop_held_file(repo: Path, session: str) -> Path | None:
    """`<git dir>/labkit-stop-held/<SESSION>`: the fingerprint of the state
    the session's stop last held (`state_fingerprint`); None outside git
    or for a session id that is no file name."""
    if not _SESSION_FILE.match(session):
        return None
    base = git_dir_path(repo, "labkit-stop-held")
    return None if base is None else base / session


def state_fingerprint(repo: Path) -> str:
    """One digest of the state the stop judges: HEAD and, for every path
    `git status` names under REPO (`touched_paths`), its content digest
    or `gone` — the content, not git's status lines, which say that a
    file changed and not what it holds. Raises RuntimeError when git
    fails."""
    lines = [head_sha(repo)]
    for p in sorted(set(touched_paths(repo))):
        digest = file_digest(p) if p.is_file() else "gone"
        lines.append(f"{rel_posix(p, repo)} {digest}")
    return scope_digest("\n".join(lines).encode("utf-8"), None)


def write_stop_base(path: Path, sha: str) -> None:
    """Write SHA as the stop base at PATH (`stop_base_file`), its directory
    made when missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    files.write_atomic(path, sha + "\n")


def keep_stop_base(repo: Path, event: dict) -> None:
    """Keep HEAD as the session's stop base when the session has none yet:
    called before every Bash command (`pre_run`), so before any commit the
    session makes. Not while HEAD's line holds a commit dated since the
    session's transcript began (`repo.head_before`): a base gone after a
    commit is not kept again past it — the stop checks the commits since
    the transcript start instead, says so (`committed_in_session`), and
    keeps HEAD itself after a clean stop on a clean tree. Nothing outside
    git or without a session id. "" stands for a HEAD not yet born: every
    commit counts."""
    session = event.get("session_id")
    if not session:
        return
    path = stop_base_file(repo, session)
    if path is None or path.exists():
        return
    head = head_sha(repo)
    start = _transcript_start(event.get("transcript_path"))
    if start is not None and head_before(repo, start) not in (head, None):
        return
    write_stop_base(path, head)


class SessionCommits(NamedTuple):
    """What the session committed, as the stop reads it: the PATHS the
    commits touched, a NOTE when the reading is not the plain one (a base
    gone or off HEAD's line), UNCHECKED when commits of the session may be
    among none of those paths — then the stop's base must not move past
    them, or no later stop would ever check them — and HOLD when no check
    of them could run at all: a check that cannot run is not clean. SINCE
    is the commit the session's commits come after ("" from the first
    commit; None when none are told), STARTED when the session began —
    its stop base kept, else its transcript's first record; None unknown
    (`session_evidence` reads both)."""

    paths: list[Path]
    note: str
    unchecked: bool = False
    hold: bool = False
    since: str | None = None
    started: datetime | None = None


def committed_in_session(repo: Path, event: dict) -> SessionCommits:
    """Every path a commit since the session's stop base touched
    (`paths_committed_since`), and a sentence when that base no longer
    leads to HEAD — a rebase or a reset: then the commits since the newest
    shared one count, or none when git knows no shared one; said, never
    skipped in silence, and UNCHECKED. Without a kept base the commits
    since the transcript start stand in (`committed_since_transcript`)."""
    session = event.get("session_id")
    path = stop_base_file(repo, session) if session else None
    if path is None or not path.is_file():
        return committed_since_transcript(repo, event)
    base = path.read_text(encoding="utf-8").strip()
    # the base is kept before the session's first Bash command
    began = datetime.fromtimestamp(path.stat().st_mtime)
    if not base:
        return SessionCommits(
            paths_committed_since(repo, ""), "", since="", started=began
        )
    start = fork_point(repo, base)
    if start == base:
        return SessionCommits(
            paths_committed_since(repo, base), "", since=base, started=began
        )
    if start is None:
        return SessionCommits(
            [],
            f"the session's stop base {base[:12]} is no ancestor of HEAD and "
            f"shares no commit with it — the commits of this session are not "
            f"checked here, and the base stays; the commit gate still holds",
            unchecked=True,
            since=None,
            started=began,
        )
    return SessionCommits(
        paths_committed_since(repo, start),
        f"the session's stop base {base[:12]} is no ancestor of HEAD (rebase "
        f"or reset) — the commits since {start[:12]}, the newest shared one, "
        f"are checked",
        since=start,
        started=began,
    )


def committed_since_transcript(repo: Path, event: dict) -> SessionCommits:
    """`committed_in_session` for a session without a stop base: every path the
    commits on HEAD's line dated since the transcript's first record
    touched (`repo.head_before`, `paths_committed_since`), with a sentence
    saying so whenever there is such a commit — the base was removed, or a
    commit came before the session's first Bash command. Only the session's
    commits, never every protocol of the repo: an old area must not hold
    every stop. ([], "") when nothing is dated since: nothing was missed.
    No transcript to date the session by: none checked, said, UNCHECKED
    and HOLD — the stop holds, once per turn, with the way out. The limit: a
    commit date is the commit's own word."""
    start = _transcript_start(event.get("transcript_path"))
    if start is None:
        return SessionCommits(
            [],
            "the session has no stop base and no transcript start to stand in "
            "for it — its commits cannot be checked, and a check that cannot run "
            "is not clean: check the files your commits touched by hand "
            "(`report-check --if-reported <path>…`; `git log --name-only` lists "
            "them), then any Bash command keeps a stop base for the next stop",
            unchecked=True,
            hold=True,
            since=None,
            started=None,
        )
    base = head_before(repo, start)
    if base is None or base == head_sha(repo):
        return SessionCommits([], "", since=None, started=start)
    return SessionCommits(
        paths_committed_since(repo, base),
        (
            f"the session has no stop base (pre-run keeps one before the first Bash "
            f"command; removed, or a commit came first) — the commits on HEAD's line "
            f"dated since the transcript began ({start:%Y-%m-%d %H:%M:%S}) are "
            f"checked instead, since {base[:12] or 'the first commit'}"
        ),
        since=base,
        started=start,
    )
