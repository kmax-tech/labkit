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

The repository the hooks hold is the one the project directory
(`CLAUDE_PROJECT_DIR`, else the event's cwd) lies in, its root found from
a subdirectory too (`session_repo`). Outside every repository the stop
cannot tell what changed: it says so and holds, once per turn; post-change
checks only the tool's own file. `undecided` reads its paths against the
repository of the current directory, where git runs the pre-commit.

A rule the agent has to remember is the weak layer; these hooks are the
layer that does not depend on remembering. Why each rule holds:
docs/notes/2026-10-19-hooks-and-report-check.md.

pre-run
    The command is a run start when it names a .py file that opens a run
    (`runlog.run(` / `runlog.Run(`, or `lanes.Lanes(`, whose `main` opens
    it: the prompt skeleton) and is not one of the throwaway stages
    (`--show`, `--probe`, `--eval-only`). For that script's area (the
    nearest directory above it with a PROTOCOL-*.md) `preflight` runs:
      · protocol frozen (`frozen = true`) + blockers           → exit 2, blocked
      · protocol unfrozen (a pilot by declaration) + blockers  → context only
      · clean                                                   → one line
    `LABKIT_PREFLIGHT=skip` in the command string skips the gate; it is
    visible in the transcript, like `--no-verify` on a commit.
    The gate follows the cost tier (LAB-017 The number of audits follows the cost tier): at `repeat_cost = "low"` preflight
    does not run before a command — a rerun at low repeat cost is the probe — and
    the hook only says whether the registration is written
    (`protocol_check.low_registration_missing`: the question; for a fit or
    an apply also criterion, admissibility condition and null condition;
    with a model the data profile), which is
    what `runlog` will demand of a full run there. A `high`/
    undeclared protocol keeps the gate above.

post-change
    Every file the repo now reports as changed (git status, untracked
    included) plus the tool's own file_path, filtered to PROTOCOL-*.md and
    notes/messung/*.md (not 00-*), is checked with protocol-check or
    notes-check. A changed Markdown report that discusses a run (a
    discussion block, `report_blocks.discussions`) gets the report review's command
    (`report_review.review_hint`) — a hint; the review is one model call
    and the agent's to start. A report is read at its own path
    (`repo.own_path`), as the stop and the commit read it: one that is a
    symbolic link is told their refusal and its way out
    (`report_hold.link_gap`). A per-session cache of content hashes keeps a
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
    HEAD only after a stop without a blocker that found the working tree
    equal to HEAD (git status names nothing) — the checks read the tree,
    so only then did they check what HEAD holds. A commit past the
    pre-commit (`--no-verify`) is so checked at every stop, as the tree
    holds its areas, until a stop on a clean tree passes: a fix left
    uncommitted lets the turn end and keeps the base, and the stop after
    the fix is dropped holds again. The limit: the stop never checks HEAD
    apart from the tree — a session may end with the fault committed and
    its fix uncommitted; the commit of the fix meets the pre-commit.
    Without a base (removed, or a commit came before the first Bash
    command) the stop says so and holds the commits on HEAD's line dated
    since the transcript's first record (`committed_since_transcript`) —
    the session's commits, never every protocol of the repo; pre-run keeps
    no base past such a commit, and the stop keeps HEAD after a clean stop
    on a clean tree. A commit date is the commit's own word: that is the
    fallback's limit. The checks run within `STOP_BUDGET_S`, under the
    hook's timeout (`install_hooks.STOP_TIMEOUT_S`): past it the stop
    holds and says so, since a hook Claude Code cancels holds nothing. Once
    per turn: when the agent was already sent back in this turn
    (`stop_hook_active`), the checks still run and print, the base stays,
    and it may stop — no loop; the next turn's stop holds again.
    The same stop holds every area the session touched (a changed file
    under it, git status) to its audit records: a BLOCKER nobody decided,
    or audit evidence gone or unreadable → exit 2, naming file and finding
    (`undecided_blockers`); a current handover of the area acknowledges
    the loss, never the BLOCKER, and one that no longer matches says why.
    The pre-commit runs `claude-hook undecided` on the staged paths for the
    same rule. Deciding is cheap and visible: `accepted` with a reason is
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
from dataclasses import dataclass
import io
import json
import os
import subprocess
import re
import signal
import sys
import tempfile
from datetime import datetime
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NamedTuple
from types import FrameType

from labkit.formats import (
    attempts,
    console,
    files,
    findings,
    jsonl,
    protocol_block,
    protocol_check,
    runs,
    standard_contract,
)
from labkit.formats.gate import Findings
from labkit.formats.shell import segments
from labkit.formats import handovers
from labkit.checks import notes_check, protocol_report
from labkit.checks.report_blocks import ReportBlockError
from labkit.gates import preflight, report_check, report_hold
from labkit.gates.install_hooks import STOP_TIMEOUT_S
from labkit.gates.report_review import review_hint
from labkit.formats.repo import (
    PROTOCOL_NAME,
    area_protocols,
    repo_protocols,
    find_area,
    fork_point,
    git_dir_path,
    git_root,
    head_before,
    head_sha,
    own_path,
    paths_committed_since,
    shown,
    status_entries,
    touched_paths,
)
from labkit.formats.scope_sha import areas_touched, file_digest
from labkit.formats.scope_sha import digest as scope_digest

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
# A script opens a run when its text calls runlog, or builds the `lanes.Lanes`
# whose `main` opens it (`run/lanes.py`) — the prompt skeleton names no runlog
# call of its own.
OPENS_RUN = re.compile(r"runlog\.(run|Run)\(|lanes\.Lanes\(")
PROTOCOL_IN_SCRIPT = re.compile(r"PROTOCOL-[\w.-]+\.md")
SKIP_TOKEN = "LABKIT_PREFLIGHT=skip"


def _read_event() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _project_dir(event: dict | None = None) -> Path:
    """The directory Claude Code was started in (`CLAUDE_PROJECT_DIR`),
    else the event's cwd, else the process's."""
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(project or (event or {}).get("cwd") or os.getcwd())


def session_repo(event: dict | None = None) -> Path | None:
    """The repository the hooks hold: the git root (`repo.git_root`) of the
    project directory (`_project_dir`), found from a subdirectory too — a
    session started below the repo root has no `.git` of its own there.
    None outside every repository."""
    return git_root(_project_dir(event))


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


def before_run(script: Path, stop: Path | None) -> tuple[bool, str]:
    """What stands before SCRIPT opens a full run, as (blocks, line): the
    area above it (searched up to STOP), its protocol's head, then the
    lane's gate — the registration at low repeat cost
    (`_low_registration_line`), else preflight with the stations' findings
    as data. Blocks only a frozen protocol with preflight blockers; every
    other case is a note. One script per call: `pre_run` held all of this
    inline (audit 2026-10-27, third, M7)."""
    area = find_area(script, stop)
    if area is None:
        return False, (
            f"{script.name}: opens a run, but no PROTOCOL-*.md "
            f"above it — unbound runs keep no number (LAB-003 No run without an intent paragraph)."
        )
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
        return False, f"{head}: protocol head unreadable — {exc}"
    # which gate stands before a full run is the lane's answer: the
    # registration (low) or preflight (`standard_contract.lane`)
    if all(standard_contract.lane(h.repeat_cost).registration for h in heads):
        return False, _low_registration_line(head, texts)
    # the stations' findings as data (`preflight_area`'s collector), not
    # the printed report read back; stdout is kept off the hook's own
    found = Findings(tell=None)
    with contextlib.redirect_stdout(io.StringIO()):
        rc = preflight.preflight_area(area, protocol, found)
    said = "\n".join(found.summary("preflight", "freezing"))
    if rc == 1 and any(h.frozen for h in heads):
        return True, (
            f"{head}: BLOCKED — the protocol is frozen and "
            f"preflight reports blockers:\n{said}"
        )
    if rc == 1:
        return False, (
            f"{head}: blockers, protocol not frozen (pilot) — "
            f"the full run will not start until they are fixed:\n{said}"
        )
    if rc == 2:
        return (
            False,
            f"{head}: could not run preflight — no protocol to hold the area to",
        )
    return False, f"{head}: {said.splitlines()[0]}"


def _low_registration_line(head: str, texts: list[str]) -> str:
    """The note for a full run at low repeat cost: no gate runs, and runlog
    refuses the run while a registration field of TEXTS is open."""
    missing = sorted(
        {m for t in texts for m in protocol_check.low_registration_missing(t)}
    )
    if not missing:
        return (
            f"{head}: repeat cost low — gate not run, the rerun is "
            f"the probe; registration written (LAB-017 The number of audits follows the cost tier)."
        )
    return (
        f"{head}: repeat cost low, but {', '.join(missing)} still "
        f"empty or a placeholder — runlog refuses a full run "
        f"until the registration is written (LAB-003 No run without an intent paragraph, LAB-017 The number of audits follows the cost tier)."
    )


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


def pre_run(event: dict) -> int:
    """PreToolUse hook on Bash: the session's stop base is kept before its first command (`keep_stop_base`); a full measure run gets its area's preflight first; blockers refuse the command (exit 2)."""
    if event.get("tool_name", "Bash") != "Bash":
        return 0
    repo = session_repo(event)
    if repo is not None:
        keep_stop_base(repo, event)
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

    # the walk to an area ends at the repo root, not at the project
    # directory: a session started in `<area>/scripts` must still find the
    # area above its script
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    stop = repo if repo is not None else (Path(project) if project else None)
    blocked: list[str] = []
    notes: list[str] = []
    for script in scripts:
        blocks, line = before_run(script, stop)
        (blocked if blocks else notes).append(line)
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
    """The review's hint for the report at PATH, its own path
    (`repo.own_path`) — `review_hint` —, or what report-check refuses at
    the stop and the commit, said now: a report that is a symbolic link
    (`report_hold.link_gap`, with its way out), a block in it that does
    not read."""
    link_target = report_hold.refused_link(repo, path, staged=False)
    if link_target is not None:
        # named where it lies: `shown` resolves, which follows the link
        rel = path.relative_to(repo.resolve()).as_posix()
        return report_hold.link_gap(rel, path, link_target, repo, staged=False)
    try:
        return review_hint(text, path, repo)
    except ReportBlockError as exc:
        return f"{shown(path, repo)}: {exc}"


def post_change(event: dict) -> int:
    """PostToolUse hook: a protocol or a measurement note just written gets its checker; a changed report that discusses a run gets the report review's command (`report_review.review_hint`), once per text; the findings go back as context."""
    found = session_repo(event)
    # outside git only the tool's own file is checked, shown against the
    # project directory
    repo = found if found is not None else _project_dir(event)
    candidates: list[Path] = []
    if found is not None:
        candidates.extend(_git_changed(repo))
    fp = (event.get("tool_input") or {}).get("file_path")
    if fp:
        candidates.append(Path(fp))
    named, targets = _changed(candidates, repo)
    marked = [
        (path, hint)
        for path, text in report_hold.report_files(named, repo, staged=False)
        if (hint := _report_hint(text, path, repo))
    ]
    if not targets and not marked:
        return 0

    cache_file = _cache_path(event.get("session_id"))
    cache = _load_cache(cache_file)
    reports = _untold(cache, marked, targets, repo)
    if cache_file is not None:
        cache_file.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    if reports:
        _context("PostToolUse", "\n".join(reports))
    return 0


def _changed(
    candidates: list[Path], repo: Path
) -> tuple[list[Path], list[tuple[str, Path]]]:
    """Of CANDIDATES (relative to REPO or absolute): every path as the repo
    names it, a link kept where it lies (`repo.own_path`) — as the stop and
    the commit hold reports; resolved, a linked report would be read where
    it points —, and the (kind, file) pairs a checker wants
    (`wants_check`), each existing file once."""
    seen: set[Path] = set()
    named: list[Path] = []
    targets: list[tuple[str, Path]] = []
    for c in candidates:
        own = own_path(c if c.is_absolute() else repo / c)
        if own not in named:
            named.append(own)
        c = c.resolve()
        if c in seen or not c.is_file():
            continue
        seen.add(c)
        kind = wants_check(c)
        if kind:
            targets.append((kind, c))
    return named, targets


def _untold(
    cache: dict,
    marked: list[tuple[Path, str]],
    targets: list[tuple[str, Path]],
    repo: Path,
) -> list[str]:
    """What the post hook tells, each piece once per state (CACHE, updated
    in place): a report's review hint (MARKED) once per text and hint — a
    hint repeated on every edit of the same state is noise; a changed text,
    or another hint for the same bytes (a link replaced by its copy is then
    a report), is told again —, and each target's checker output once per
    file content."""
    reports = []
    for path, hint in marked:
        key = f"report-review:{path}"
        digest = f"{file_digest(path)}:{scope_digest(hint.encode('utf-8'))}"
        if cache.get(key) != digest:
            cache[key] = digest
            reports.append(hint)
    for kind, path in targets:
        digest = file_digest(path)
        if cache.get(str(path)) == digest:
            continue
        cache[str(path)] = digest
        fn = protocol_report.main if kind == "protocol" else notes_check.main
        # from the repo root with the repo-relative path (the hook's cwd is
        # wherever the agent stood): every line the checker writes names
        # the file as pfad:zeile itself — the hook rewrote the absolute
        # path in the printed text before (audit 2026-10-27, third, M4)
        with contextlib.chdir(repo):
            _, out = _capture(fn, [shown(path, repo)])
        if out:
            reports.append(out)
    return reports


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
    repo = _project_dir()
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


def _write_stop_base(path: Path, sha: str) -> None:
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
    _write_stop_base(path, head)


class SessionCommits(NamedTuple):
    """What the session committed, as the stop reads it: the PATHS the
    commits touched, a NOTE when the reading is not the plain one (a base
    gone or off HEAD's line), UNCHECKED when commits of the session may be
    among none of those paths — then the stop's base must not move past
    them, or no later stop would ever check them — and HOLD when no check
    of them could run at all: a check that cannot run is not clean."""

    paths: list[Path]
    note: str
    unchecked: bool = False
    hold: bool = False


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
    if not base:
        return SessionCommits(paths_committed_since(repo, ""), "")
    start = fork_point(repo, base)
    if start == base:
        return SessionCommits(paths_committed_since(repo, base), "")
    if start is None:
        return SessionCommits(
            [],
            f"the session's stop base {base[:12]} is no ancestor of HEAD and "
            f"shares no commit with it — the commits of this session are not "
            f"checked here, and the base stays; the commit gate still holds",
            unchecked=True,
        )
    return SessionCommits(
        paths_committed_since(repo, start),
        f"the session's stop base {base[:12]} is no ancestor of HEAD (rebase "
        f"or reset) — the commits since {start[:12]}, the newest shared one, "
        f"are checked",
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
        )
    base = head_before(repo, start)
    if base is None or base == head_sha(repo):
        return SessionCommits([], "")
    return SessionCommits(
        paths_committed_since(repo, base),
        (
            f"the session has no stop base (pre-run keeps one before the first Bash "
            f"command; removed, or a commit came first) — the commits on HEAD's line "
            f"dated since the transcript began ({start:%Y-%m-%d %H:%M:%S}) are "
            f"checked instead, since {base[:12] or 'the first commit'}"
        ),
    )


#: the stop's own limit, under the one Claude Code gives the hook
#: (`install_hooks.STOP_TIMEOUT_S`): checks still running then hold the stop
#: and say so, where a cancelled hook would hold nothing; the margin is for
#: the interpreter's start, the session log and git
STOP_BUDGET_S = STOP_TIMEOUT_S - 30


class _OverBudget(BaseException):
    """Raised by the stop's alarm inside whichever check runs — a
    BaseException, so that no `except Exception` on the way takes it."""


def _end_descendants() -> None:
    """SIGKILL every process below this one, children before their own
    children are read again (a process started meanwhile is caught by the
    next pass; three passes). `ps -A -o pid=,ppid=` reads the tree, as on
    macOS and Linux alike."""
    me = os.getpid()
    for _ in range(3):
        listed = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True
        ).stdout
        below: dict[int, list[int]] = {}
        for line in listed.splitlines():
            pid, ppid = (int(x) for x in line.split())
            below.setdefault(ppid, []).append(pid)
        found, todo = [], list(below.get(me, []))
        while todo:
            pid = todo.pop()
            found.append(pid)
            todo += below.get(pid, [])
        if not found:
            return
        for pid in found:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)


@contextlib.contextmanager
def _budget(seconds: float) -> Iterator[None]:
    """Raise _OverBudget in the main thread once SECONDS have passed
    (SIGALRM), after ending every process the checks started, at any depth
    (`_end_descendants`: a test runner's own children too — killing only
    the direct child left them running on their own). The alarm and the
    previous handler are restored whatever ends the block."""

    def ring(signum: int, frame: FrameType | None) -> None:
        _end_descendants()
        raise _OverBudget

    previous = signal.signal(signal.SIGALRM, ring)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def stop(event: dict) -> int:
    """Stop hook: a number written back or committed in this session gets report-check; blockers, or checks that outrun the stop's budget, send the agent back (exit 2), once per turn."""
    repo = session_repo(event)
    if repo is None:
        # nothing tells the stop what the session changed or committed: a
        # check that cannot run holds, once per turn
        print(
            f"claude-hook stop: {_project_dir(event)} lies in no git repository — "
            "the stop cannot tell what this session changed or committed and "
            "checks nothing; work inside the lab repo (`labkit-hooks install` "
            "set these hooks up in one)",
            file=sys.stderr,
        )
        return 0 if event.get("stop_hook_active") else 2
    try:
        with _budget(STOP_BUDGET_S):
            held, clean_tree, checked_head = _stop_checks(repo, event)
    except _OverBudget:
        print(
            f"claude-hook stop: the checks did not end within {STOP_BUDGET_S:g} s "
            f"— Claude Code cancels the stop hook at {STOP_TIMEOUT_S} s, and a "
            "cancelled stop holds nothing; so this stop holds, clears nothing "
            "and keeps its base. The pre-commit runs the same checks without "
            "that limit; `report-check --if-reported <path>…` runs them by hand",
            file=sys.stderr,
        )
        held, clean_tree, checked_head = True, False, ""
    if not held:
        # the base moves only past a clean stop that read what HEAD holds:
        # the checks read the tree, and a tree that differs from HEAD — a
        # fix not yet committed beside a commit past the pre-commit — keeps
        # the base, so the commit is checked again at every later stop
        session = event.get("session_id")
        path = stop_base_file(repo, session) if session else None
        if clean_tree and path is not None:
            _write_stop_base(path, checked_head)
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


def _stop_checks(repo: Path, event: dict) -> tuple[bool, bool, str]:
    """The stop's checks, their findings on stderr: (held, whether the base
    may move — the working tree equal to HEAD and every session commit
    read —, the HEAD checked)."""
    record_session(repo, event)
    checked_head = head_sha(repo)
    # deletions and rename sources too: a script or result removed under a
    # reported number reopens it as an edit does; and what the session
    # committed — a commit, even past the pre-commit with --no-verify,
    # leaves the tree clean and the delivered state with the blocker
    # (eighth haiku round, t3)
    in_tree = touched_paths(repo)
    session = committed_in_session(repo, event)
    changed = list(dict.fromkeys(in_tree + session.paths))
    if session.note:
        print(f"claude-hook stop: {session.note}", file=sys.stderr)
    state = undecided_state(repo, changed)
    for line in state.acknowledged:
        print(f"claude-hook stop: {line}", file=sys.stderr)
    undecided = state.blockers
    if undecided:
        print(
            "an audit of an area this session worked in found BLOCKER(s) nobody "
            "decided, or audit evidence is gone or does not read — "
            f"{UNDECIDED_WAY}; a number measured past them cannot be reported, "
            "and a commit would be refused the same way "
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
    # commits it could not read keep the base where it is: past them, no
    # later stop would check them
    return (
        rc != 0 or bool(undecided) or session.hold,
        not in_tree and not session.unchecked,
        checked_head,
    )


#: the way out the stop and the pre-commit print for `undecided_blockers`
UNDECIDED_WAY = (
    f"decide each BLOCKER ({findings.DECIDED_LIST}; accepted, deferred and "
    "dismissed owe a reason) with the `--decide` command `labkit-audit <AREA> "
    "--findings` prints for it (AREA: the path each line starts with), never by "
    "rewriting the record; restore evidence that is gone; when the area cannot "
    "be finished, hand it over with the `protocol-fill <PROTOCOL> --handover` "
    "command `--findings` prints (it acknowledges the loss at the stop and the "
    "commit only, never an open BLOCKER)"
)


@dataclass(frozen=True)
class Undecided:
    """What the stop and the commit hold (BLOCKERS) and what a current
    handover let pass (ACKNOWLEDGED: one line per area, the losses it
    acknowledges) — a pass that names no loss read as "nothing wrong"
    (audit 2026-10-27, third, K9)."""

    blockers: list[str]
    acknowledged: list[str]


def undecided_blockers(
    repo: Path, paths: list[Path], *, staged: bool = False
) -> list[str]:
    """The blockers of `undecided_state`."""
    return undecided_state(repo, paths, staged=staged).blockers


def undecided_state(
    repo: Path, paths: list[Path], *, staged: bool = False
) -> Undecided:
    """Every audit BLOCKER still `open` in an area one of PATHS lies in — as
    `<area>: <file>: <text>`, each area once —, every audit record gone
    that the area's attempt journal or HEAD names (`attempts.area_gaps`),
    or the sentence of a record or journal nobody can read. BLOCKERs only, by intent (`findings.open_findings` has the
    table): the hook says what the commit would be refused for. The area is the nearest directory above the path with a
    PROTOCOL-*.md, inside REPO, and every area whose promises declare a
    changed path in their scope or whose code imports a changed shared
    helper (`scope_sha.areas_touched`, the stop's answer too). A
    path outside every area contributes nothing, and so does an area with
    no audit record and no journal in the state checked or at HEAD — an
    audits/ gone from the tree but committed is a gap: this holds the areas
    the session worked in, not the whole repo
    (A4, 2026-10-17: a repo's old areas must not block every stop).
    STAGED (the pre-commit): the audit records with their decisions and
    the attempt journal as the index holds them (`attempts.area_integrity`)
    — what the commit carries, not the tree.
    A current handover may acknowledge integrity gaps for this stop/commit
    alone (`handovers.acknowledgement`); it never dismisses readable open
    BLOCKERs. At commit, its audit evidence must also match the working
    tree, so new unstaged evidence cannot borrow an earlier
    acknowledgement. Where the gaps stand and a handover record of the area
    does not count, a line per record says why (`handovers.mismatch`)."""
    out: list[str] = []
    acknowledged: list[str] = []
    for area in areas_touched(paths, repo):
        shown = area.relative_to(repo.resolve()).as_posix()
        # Only a current handover can acknowledge integrity gaps.
        # Open readable BLOCKERs remain owed independently below.
        handed_over = handovers.acknowledgement(area, staged=staged)
        state = attempts.area_integrity(area, staged=staged)
        if handed_over.valid and state.problems:
            acknowledged.append(
                f"{shown}: a handover acknowledges this loss — not restored, and "
                f"no audit or adoption passes on it: " + "; ".join(state.problems)
            )
        if not handed_over.valid and state.problems:
            out += [f"{shown}: {problem}" for problem in state.problems]
            # a handover written for this area that no longer counts says why
            out += [
                f"{shown}: the handover {name} no longer acknowledges this: {why}"
                for name, why in handed_over.refused.items()
            ]
        out += [f"{shown}: {u.line}" for u in findings.open_blockers(state.records)]
    return Undecided(out, acknowledged)


def undecided(argv: list[str]) -> int:
    """`claude-hook undecided <paths…>`: the pre-commit's gate — exit 1 and the
    findings on stdout when an area a path touches holds an undecided BLOCKER.
    PATHS are git's, relative to the root of the repository the current
    directory lies in — where git runs the pre-commit —, never to the
    session's project directory, which may lie below that root."""
    if not argv:
        console.refuse("claude-hook undecided", "name the paths (the staged files)")
        return 2
    repo = git_root(Path.cwd())
    if repo is None:
        console.refuse(
            "claude-hook undecided",
            f"{Path.cwd()} lies in no git repository — run it in the repo whose "
            "index is committed, as the pre-commit does",
        )
        return 2
    state = undecided_state(repo, [repo / p for p in argv], staged=True)
    for line in state.acknowledged:
        print(f"claude-hook undecided: {line}")
    lines = state.blockers
    if not lines:
        return 0
    print(
        "claude-hook: an audit of a staged area found BLOCKER(s) nobody decided "
        "in the index, or audit evidence is gone or does not read — "
        f"{UNDECIDED_WAY}; stage the decided record (the commit carries the "
        "decision the index holds) "
        "(LAB-015 Preflight audit before freezing):\n  " + "\n  ".join(lines)
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
