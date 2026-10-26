"""claude-hook — the three Claude Code hooks a lab repo installs.

    claude-hook pre-run       PreToolUse  (matcher: Bash)
    claude-hook post-change   PostToolUse (matcher: Bash|Write|Edit)
    claude-hook stop          Stop
    claude-hook undecided <paths…>        the pre-commit's half of the stop hook: an area a path
                                          touches holds an undecided audit BLOCKER → exit 1
    claude-hook sessions [--run RUN_ID]   the session log: which session, which transcript, which runs

The three hooks read the hook's JSON event on stdin and answer the way
Claude Code expects: `pre-run` and `stop` block with exit 2 (the stderr
text goes back to the agent), `post-change` is `additionalContext` on
stdout and exit 0.

A rule the agent has to remember is the weak layer; these hooks are the
layer that does not depend on remembering. Why each rule holds:
docs/notes/2026-10-19-hooks-and-report-check.md.

pre-run
    The command is a run start when it names a .py file that opens a run
    (`runlog.run(` / `runlog.Run(`) and is not one of the throwaway stages
    (`--show`, `--probe`, `--eval-only`). For that script's area (the
    nearest directory above it with a PROTOCOL-*.md) `preflight` runs:
      · protocol frozen (`frozen = true`) + blockers           → exit 2, blocked
      · protocol unfrozen (a pilot by declaration) + blockers  → context only
      · clean                                                   → one line
    `LABKIT_PREFLIGHT=skip` in the command string skips the gate; it is
    visible in the transcript, like `--no-verify` on a commit.
    The gate follows the cost tier (LAB-017 The number of audits follows the cost tier): at `repeat_cost = "low"` preflight
    does not run before a command — a rerun at low repeat cost is the probe — and
    the hook only says whether the success criterion is written, which is
    what `runlog` will demand of a full run there. A `high`/
    undeclared protocol keeps the gate above.

post-change
    Every file the repo now reports as changed (git status, untracked
    included) plus the tool's own file_path, filtered to PROTOCOL-*.md and
    notes/messung/*.md (not 00-*), is checked with protocol-check or
    notes-check. A changed Markdown report that discusses a run (a
    discussion block, `report_blocks.discussions`) gets the report review's command
    (`report_review.review_hint`) — a hint; the review is one model call
    and the agent's to start. A per-session cache of content hashes keeps a
    file that was already checked or hinted at this content from being
    reported after every later command.

stop
    Before the agent ends its turn: every protocol of an area a changed
    path lies in — changed in the tree (git status) or in a commit since
    the session's stop base — whose head declares a result (`[result] run`)
    goes through `report-check --if-reported` — a script edited under a
    reported number reopens it — the whole release check at every cost
    tier: the run bound to the protocol and declared, a full run (no probe, no
    acknowledged run), a decided analysis audit of code, promises and that
    run, the numbers recomputed by `02_analyze.py --check`; finalize is one
    of its stations. Blockers → exit 2, and the findings go back to the
    agent, which keeps working. The head's `[result] run` is the one
    declaration that a result is reported (`protocol_block.declared_run`); a
    protocol declaring none owes nothing — an exploration ends
    with "no reported result", probes in `runs/` or not. The stop base is
    the HEAD `pre-run` kept before the session's first Bash command
    (`keep_stop_base`, `<git dir>/labkit-stop-base/<session>`); it moves to
    HEAD only after a stop without a blocker, so a commit past the
    pre-commit (`--no-verify`) is held at every stop until it is fixed
    (eighth haiku round, t3). Once per turn: when the agent was already
    sent back in this turn (`stop_hook_active`), the checks still run and
    print, the base stays, and it may stop — no loop; the next turn's stop
    holds again.
    The same stop holds every area the session touched (a changed file
    under it, git status) to its audit records: a BLOCKER nobody decided →
    exit 2, naming file and finding (`undecided_blockers`). The pre-commit
    runs `claude-hook undecided` on the staged paths for the same rule. Deciding is cheap and visible: `accepted` with a reason is
    a documented deviation, which is what the gate is for; a hand-written
    `fixed` is a lie the next audit sees (LAB-015 Preflight audit before freezing).

session log
    Every stop also appends one line to the repo's `.git/labkit-sessions.jsonl`
    (inside .git: local, never committed): the session id, the transcript
    path, the time, and the runs whose run_id dates from after this
    session's previous stop (or its first transcript record). `claude-hook
    sessions --run RUN_ID` finds the session — and so the transcript — a run
    came from: what the agent read and decided before it, for debugging.

Exit codes, per subcommand — 2 is what Claude Code reads as "block", so
it means three things here: pre-run 0, or 2 to block the command; stop 0,
or 2 to keep the agent working; post-change 0; undecided 0, or 1 with
findings on stdout; sessions 0, or 1 when no session made the run; a usage
error (no event, no RUN_ID, no paths) 2 on stderr, as every labkit command
(`console.refuse`). An unexpected failure is a traceback, exit 1, never
swallowed.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from collections.abc import Callable
from pathlib import Path

from labkit.formats import (
    attempts,
    console,
    files,
    findings,
    jsonl,
    protocol_block,
    protocol_check,
    protocol_report,
    runs,
    standard_contract,
)
from labkit.formats.shell import segments
from labkit.checks import notes_check
from labkit.checks.report_blocks import ReportBlockError
from labkit.gates import preflight, report_check
from labkit.gates.report_review import review_hint
from labkit.formats.repo import (
    PROTOCOL_NAME,
    area_protocols,
    repo_protocols,
    find_area,
    fork_point,
    git_run,
    head_sha,
    paths_committed_since,
    shown,
    status_entries,
    touched_paths,
)
from labkit.formats.scope_sha import areas_touched, file_digest

# The template's throwaway stages: none of them opens a run, and the probe
# is what comes BEFORE preflight, so gating it would invert the order.
THROWAWAY_FLAGS = re.compile(r"(^|\s)--(show|probe|eval-only)\b")
PY_TOKEN = re.compile(r"[\w./~-]+\.py")
# A .py file is RUN when an interpreter precedes it (`python`, `python3.12`,
# `.venv/bin/python`, flags between allowed), when it starts a command
# command (`./x.py`, first in a `shell.segments` command, after
# `runlog start --`, `nohup`, `time`, `exec`), never when it is merely named (`sed -n 1,5p lib/x.py`, a path in
# a heredoc): uniagent 2026-10-10, 85 of 272 hook lines in one session said
# "opens a run" about a lib module someone was reading.
INTERPRETER = re.compile(r"(?:^|/)python[\d.]*$")
COMMAND_PREFIX = {"--", "nohup", "time", "exec"}
STRIP = "\"'`();"  # around a token: quotes, parentheses, a trailing ;
OPENS_RUN = re.compile(r"runlog\.(run|Run)\(")
PROTOCOL_IN_SCRIPT = re.compile(r"PROTOCOL-[\w.-]+\.md")
SKIP_TOKEN = "LABKIT_PREFLIGHT=skip"


def _read_event() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _context(event_name: str, text: str) -> None:
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


def _capture(fn: Callable[..., int], *args: object) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args)
    return rc, buf.getvalue().rstrip()


# ---------------------------------------------------------------- pre-run


def executed_py(words: list[str]) -> list[str]:
    """The .py paths one simple command (WORDS, a `shell.segments` entry)
    RUNS, in order: preceded by an interpreter (flags in between allowed),
    first in the command or after a prefix (`nohup`, `--`), or `./x.py`. A
    .py path that is only named — read, edited, inside a quoted `-c` string
    — is not among them."""
    tokens = words
    out: list[str] = []
    for i, raw in enumerate(tokens):
        tok = raw.strip(STRIP)
        if not PY_TOKEN.fullmatch(tok):
            continue
        j = i - 1
        while j >= 0 and tokens[j].startswith("-") and tokens[j] not in COMMAND_PREFIX:
            j -= 1  # interpreter flags: python -u x.py
        before = tokens[j].strip(STRIP) if j >= 0 else None
        runs = (
            tok.startswith("./")
            or before is None
            or before in COMMAND_PREFIX
            or INTERPRETER.search(before) is not None
        )
        if runs and (j == i - 1 or (before is not None and INTERPRETER.search(before))):
            out.append(tok)
    return out


def run_scripts(command: str, cwd: Path) -> list[Path]:
    """The .py files the command runs that open a run — resolved against the
    directory the command stands in at that point (a `cd` is followed) and
    existing; a segment with a throwaway flag (`--show`, `--probe`,
    `--eval-only`) opens no run. Each simple command of the line
    (`shell.segments`) is judged on its own: read as one, `cd AREA && python
    scripts/01_measure.py` found no script, and one `--probe` freed every
    command of the line (audit 2026-10-15)."""
    out = []
    here = cwd
    for seg in segments(command):
        if seg[0].strip(STRIP) == "cd":
            target = seg[1].strip(STRIP) if len(seg) > 1 else "~"
            here = here / os.path.expanduser(target)  # an absolute target replaces
            continue
        if THROWAWAY_FLAGS.search(" ".join(seg)):
            continue
        for tok in executed_py(seg):
            p = Path(os.path.expanduser(tok))
            if not p.is_absolute():
                p = here / p
            if not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if OPENS_RUN.search(text):
                out.append(p.resolve())
    return out


def protocol_named_in(script: Path, area: Path) -> Path | None:
    """The single PROTOCOL-*.md the script names, if it names exactly one
    and it exists in the area — the series case where preflight would
    otherwise refuse to pick."""
    names = sorted(set(PROTOCOL_IN_SCRIPT.findall(script.read_text(encoding="utf-8"))))
    if len(names) != 1:
        return None
    p = area / names[0]
    return p if p.is_file() else None


def pre_run(event: dict) -> int:  # noqa: C901 complexity baseline 2026-10-08
    """PreToolUse hook on Bash: the session's stop base is kept before its first command (`keep_stop_base`); a full measure run gets its area's preflight first; blockers refuse the command (exit 2)."""
    if event.get("tool_name", "Bash") != "Bash":
        return 0
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    keep_stop_base(Path(project or event.get("cwd") or os.getcwd()), event)
    command = (event.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0
    cwd = Path(event.get("cwd") or os.getcwd())
    scripts = run_scripts(command, cwd)
    if not scripts:
        return 0
    if SKIP_TOKEN in command:
        _context(
            "PreToolUse",
            f"claude-hook pre-run: {SKIP_TOKEN} — preflight "
            f"gate skipped on request; the transcript carries it.",
        )
        return 0

    project = os.environ.get("CLAUDE_PROJECT_DIR")
    stop = Path(project) if project else None
    blocked: list[str] = []
    notes: list[str] = []
    for script in scripts:
        area = find_area(script, stop)
        if area is None:
            notes.append(
                f"{script.name}: opens a run, but no PROTOCOL-*.md "
                f"above it — unbound runs keep no number (LAB-003 No run without an intent paragraph)."
            )
            continue
        protocol = protocol_named_in(script, area)
        texts = [
            p.read_text(encoding="utf-8")
            for p in ([protocol] if protocol else area_protocols(area))
        ]
        head = f"preflight {area.name}" + (
            f" --protocol {protocol.name}" if protocol else ""
        )
        try:
            heads = [protocol_block.head(t) for t in texts]
        except protocol_block.BlockError as exc:
            notes.append(f"{head}: protocol head unreadable — {exc}")
            continue
        # which gate stands before a full run is the lane's answer: the
        # registration (low) or preflight (`standard_contract.lane`)
        if all(standard_contract.lane(h.repeat_cost).registration for h in heads):
            missing = sorted(
                {m for t in texts for m in protocol_check.low_registration_missing(t)}
            )
            if not missing:
                notes.append(
                    f"{head}: repeat cost low — gate not run, the rerun is "
                    f"the probe; registration written (LAB-017 The number of audits follows the cost tier)."
                )
            else:
                notes.append(
                    f"{head}: repeat cost low, but {', '.join(missing)} still "
                    f"empty or a placeholder — runlog refuses a full run "
                    f"until the registration is written (LAB-003 No run without an intent paragraph, LAB-017 The number of audits follows the cost tier)."
                )
            continue
        rc, out = _capture(preflight.preflight_area, area, protocol)
        frozen = any(h.frozen for h in heads)
        if rc == 1 and frozen:
            blocked.append(
                f"{head}: BLOCKED — the protocol is frozen and "
                f"preflight reports blockers:\n{out}"
            )
        elif rc == 1:
            notes.append(
                f"{head}: blockers, protocol not frozen (pilot) — "
                f"the full run will not start until they are fixed:\n{out}"
            )
        elif rc == 2:
            notes.append(f"{head}: could not run preflight:\n{out}")
        else:
            notes.append(f"{head}: " + (out.splitlines()[-1] if out else "ok"))
    if blocked:
        sys.stderr.write("\n\n".join(blocked) + "\n")
        if notes:
            sys.stderr.write("\n" + "\n".join(notes) + "\n")
        return 2
    if notes:
        _context("PreToolUse", "\n\n".join(notes))
    return 0


# ------------------------------------------------------------ post-change


def _git_changed(repo: Path) -> list[Path]:
    """Every path git sees as changed, untracked included, deletions left
    out (`repo.status_entries`)."""
    return [repo / path for xy, path in status_entries(repo) if "D" not in xy]


def wants_check(path: Path) -> str | None:
    """Which checker a path belongs to: 'protocol', 'note' or None."""
    if PROTOCOL_NAME.match(path.name):
        return "protocol"
    parts = path.as_posix().split("/")
    # any `notes/messung/` pair on the way, not the first `notes`: a repo
    # under an ancestor directory named notes never had its notes checked
    under_messung = any(
        a == "notes" and b == "messung" for a, b in zip(parts, parts[1:])
    )
    if under_messung and path.suffix == ".md" and not path.name.startswith("00-"):
        return "note"
    return None


def _cache_path(session_id: str | None) -> Path | None:
    if not session_id:
        return None
    d = Path(tempfile.gettempdir()) / "labkit-claude-hook"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{session_id}.json"


def _load_cache(p: Path | None) -> dict:
    if p is None or not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _report_hint(text: str, path: Path, repo: Path) -> str | None:
    """The review's hint for the report at PATH (`review_hint`), or the
    sentence of a block in it that does not read — report-check blocks on
    it at the stop and the commit; the hook says it now."""
    try:
        return review_hint(text, path, repo)
    except ReportBlockError as exc:
        return f"{shown(path, repo)}: {exc}"


def post_change(event: dict) -> int:  # noqa: C901 complexity baseline 2026-10-08
    """PostToolUse hook: a protocol or a measurement note just written gets its checker; a changed report that discusses a run gets the report review's command (`report_review.review_hint`), once per text; the findings go back as context."""
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    repo = Path(project) if project else Path(event.get("cwd") or os.getcwd())
    candidates: list[Path] = []
    if (repo / ".git").exists():
        candidates.extend(_git_changed(repo))
    fp = (event.get("tool_input") or {}).get("file_path")
    if fp:
        candidates.append(Path(fp))
    seen: set[Path] = set()
    targets: list[tuple[str, Path]] = []
    for c in candidates:
        c = c.resolve()
        if c in seen or not c.is_file():
            continue
        seen.add(c)
        kind = wants_check(c)
        if kind:
            targets.append((kind, c))
    marked = [
        (path, hint)
        for path, text in report_check.report_files(sorted(seen), repo, staged=False)
        if (hint := _report_hint(text, path, repo))
    ]
    if not targets and not marked:
        return 0

    cache_file = _cache_path(event.get("session_id"))
    cache = _load_cache(cache_file)
    reports = []
    # once per report text: a hint repeated on every edit of the same state
    # is noise; a changed text is told again
    for path, hint in marked:
        key, digest = f"report-review:{path}", file_digest(path)
        if cache.get(key) != digest:
            cache[key] = digest
            reports.append(hint)
    for kind, path in targets:
        digest = file_digest(path)
        if cache.get(str(path)) == digest:
            continue
        cache[str(path)] = digest
        fn = protocol_report.main if kind == "protocol" else notes_check.main
        _, out = _capture(fn, [str(path)])
        # The checker gets the absolute path (the hook's cwd is wherever the
        # agent stood); the report shows it repo-relative, as pfad:zeile.
        out = out.replace(str(path), shown(path, repo))
        if out:
            reports.append(out)
    if cache_file is not None:
        cache_file.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    if reports:
        _context("PostToolUse", "\n".join(reports))
    return 0


def session_log(repo: Path) -> Path | None:
    """`.git/labkit-sessions.jsonl` of the repo (the common git dir, so a
    worktree logs into its main repo); None outside git."""
    r = git_run(["rev-parse", "--git-common-dir"], repo)
    if r.returncode != 0:
        return None
    common = Path(r.stdout.strip())
    return (common if common.is_absolute() else repo / common) / "labkit-sessions.jsonl"


def read_sessions(log: Path) -> list[dict]:
    """The log's records; a line that is not JSON names its number
    (`jsonl.objects`) and ends the command."""
    try:
        return jsonl.data_rows(log.read_text(encoding="utf-8"), str(log))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


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
    repo = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
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
    r = git_run(["rev-parse", "--git-dir"], repo)
    if r.returncode != 0:
        return None
    gitdir = Path(r.stdout.strip())
    return (
        (gitdir if gitdir.is_absolute() else repo / gitdir)
        / "labkit-stop-base"
        / session
    )


def keep_stop_base(repo: Path, event: dict) -> None:
    """Keep HEAD as the session's stop base when the session has none yet:
    called before every Bash command (`pre_run`), so before any commit the
    session makes. Nothing outside git or without a session id. "" stands
    for a HEAD not yet born: every commit counts."""
    session = event.get("session_id")
    if not session:
        return
    path = stop_base_file(repo, session)
    if path is None or path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    files.write_atomic(path, head_sha(repo) + "\n")


def committed_in_session(repo: Path, event: dict) -> tuple[list[Path], str]:
    """(paths, note): every path a commit since the session's stop base
    touched (`paths_committed_since`), and a sentence when that base no
    longer leads to HEAD — a rebase or a reset: then the commits since the
    newest shared one count, or none when git knows no shared one; said,
    never skipped in silence. ([], "") without a kept base."""
    session = event.get("session_id")
    path = stop_base_file(repo, session) if session else None
    if path is None or not path.is_file():
        return [], ""
    base = path.read_text(encoding="utf-8").strip()
    if not base:
        return paths_committed_since(repo, ""), ""
    start = fork_point(repo, base)
    if start == base:
        return paths_committed_since(repo, base), ""
    if start is None:
        return [], (
            f"the session's stop base {base[:12]} is no ancestor of HEAD and "
            f"shares no commit with it — the commits of this session are not "
            f"checked here; the commit gate still holds"
        )
    return paths_committed_since(repo, start), (
        f"the session's stop base {base[:12]} is no ancestor of HEAD (rebase "
        f"or reset) — the commits since {start[:12]}, the newest shared one, "
        f"are checked"
    )


def stop(event: dict) -> int:
    """Stop hook: a number written back or committed in this session gets report-check; blockers send the agent back (exit 2), once per turn."""
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    repo = Path(project) if project else Path(event.get("cwd") or os.getcwd())
    if not (repo / ".git").exists():
        return 0
    record_session(repo, event)
    # deletions and rename sources too: a script or result removed under a
    # reported number reopens it as an edit does; and what the session
    # committed — a commit, even past the pre-commit with --no-verify,
    # leaves the tree clean and the delivered state with the blocker
    # (eighth haiku round, t3)
    committed, note = committed_in_session(repo, event)
    changed = list(dict.fromkeys(touched_paths(repo) + committed))
    if note:
        print(f"claude-hook stop: {note}", file=sys.stderr)
    undecided = undecided_blockers(repo, changed)
    if undecided:
        print(
            "an audit of an area this session worked in found BLOCKER(s) nobody "
            "decided, or an audit record is gone — decide each (fixed / accepted / "
            "deferred / dismissed, with reason) in its audits/ file and restore a "
            "record that is gone before you stop; a number measured past them "
            "cannot be reported, and a commit would be refused the same way "
            "(LAB-015 Preflight audit before freezing):\n  " + "\n  ".join(undecided),
            file=sys.stderr,
        )
    rc = 0
    if changed:
        # every changed path, not only a protocol: a script edited after the
        # answer was written back reopens the area's reported numbers
        rc, out = _capture(
            lambda: report_check.if_reported(changed, repo, staged=False)
        )
        if rc != 0:
            print(
                "report-check reports blockers for a number written back or "
                "committed in this session — fix them before you stop (a commit "
                "would be refused the same way); a result not meant to be "
                "reported leaves the answer open:\n" + out,
                file=sys.stderr,
            )
    held = rc != 0 or bool(undecided)
    if not held:
        # the base moves only past a clean stop: a held commit is checked
        # again at the next turn's stop, never forgotten with the turn
        session = event.get("session_id")
        path = stop_base_file(repo, session) if session else None
        if path is not None and path.is_file():
            files.write_atomic(path, head_sha(repo) + "\n")
        return 0
    if event.get("stop_hook_active"):
        # sent back once in this turn already: no loop — the findings stand
        # on stderr, the base stays, the next turn's stop holds again
        print(
            "claude-hook stop: sent back once in this turn — stopping; the "
            "blockers above stand and the next stop holds them again",
            file=sys.stderr,
        )
        return 0
    return 2


def undecided_blockers(repo: Path, paths: list[Path]) -> list[str]:
    """Every audit BLOCKER still `open` in an area one of PATHS lies in — as
    `<area>: <file>: <text>`, each area once —, every audit record gone
    that the area's attempt journal or HEAD names (`attempts.area_gaps`),
    or the sentence of a record or journal nobody can read. BLOCKERs only, by intent (`findings.open_findings` has the
    table): the hook says what the commit would be refused for. The area is the nearest directory above the path with a
    PROTOCOL-*.md, inside REPO, and every area whose promises declare a
    changed path in their scope or whose code imports a changed shared
    helper (`scope_sha.areas_touched`, the stop's answer too). A
    path outside every area, and an area without audits/, contribute
    nothing: this holds the areas the session worked in, not the whole repo
    (A4, 2026-10-17: a repo's old areas must not block every stop)."""
    out = []
    for area in areas_touched(paths, repo):
        shown = area.relative_to(repo.resolve()).as_posix()
        try:
            out += [f"{shown}: {gap}" for gap in attempts.area_gaps(area).blockers]
        except attempts.AttemptError as exc:
            out.append(f"{shown}: {exc}")
        try:
            records = findings.area_records(area)
        except findings.FindingsError as exc:
            out.append(f"{shown}: {exc}")
            continue
        out += [
            f"{shown}: {u.line}"
            for u in findings.open_findings(records)
            if u.grade == "BLOCKER"
        ]
    return out


def undecided(argv: list[str]) -> int:
    """`claude-hook undecided <paths…>`: the pre-commit's gate — exit 1 and the
    findings on stdout when an area a path touches holds an undecided BLOCKER."""
    if not argv:
        console.refuse("claude-hook undecided", "name the paths (the staged files)")
        return 2
    repo = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    lines = undecided_blockers(repo, [repo / p for p in argv])
    if not lines:
        return 0
    print(
        "claude-hook: an audit of a staged area found BLOCKER(s) nobody decided, "
        "or an audit record is gone — decide each (fixed / accepted / deferred / "
        "dismissed, with reason) in its audits/ file and restore a record that is "
        "gone (LAB-015 Preflight audit before freezing):\n  " + "\n  ".join(lines)
    )
    return 1


# -------------------------------------------------------------------- cli


def main(argv: list[str]) -> int:
    """Command line of `claude-hook`: dispatch the hook named in argv, the event JSON on stdin."""
    if not argv or argv[0] in ("-h", "--help"):
        text = (
            (__doc__ or "").strip().splitlines()[0] + "\n"
            "usage: claude-hook pre-run | post-change | stop   (hook event JSON on stdin)\n"
            "       claude-hook undecided <paths…>\n"
            "       claude-hook sessions [--run RUN_ID]\n"
            "exit codes: pre-run 0 or 2 (block); stop 0 or 2 (keep working); "
            "post-change 0; undecided 0 or 1 (findings); sessions 0 or 1 (none "
            "made the run); usage error 2"
        )
        return console.usage("claude-hook", text, asked=bool(argv))
    if argv[0] == "sessions":
        return sessions(argv[1:])
    if argv[0] == "undecided":
        return undecided(argv[1:])
    event = _read_event()
    if argv[0] == "pre-run":
        return pre_run(event)
    if argv[0] == "post-change":
        return post_change(event)
    if argv[0] == "stop":
        return stop(event)
    console.refuse("claude-hook", f"unknown event {argv[0]!r}")
    return 2


def cli() -> None:
    """Console entry point of `claude-hook`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
