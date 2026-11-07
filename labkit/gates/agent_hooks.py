"""agent_hooks — the stop and the commit: the two gates of an agent session
the agent meets without calling them. The adapters (`claude_hooks`,
`codex_hooks`) read each harness's event and call one implementation; the
other two hooks stand in their own modules, and what a hook knows of its
session in `hook_session`.

    claude-hook pre-run       PreToolUse  (matcher: Bash)          `hook_pre_run`
    claude-hook post-change   PostToolUse (matcher: Bash|Write|Edit) `hook_post_change`
    claude-hook stop          Stop                                 here
    claude-hook pre-commit    run by the stamped .githooks/pre-commit  here
    claude-hook sessions [--run RUN_ID]   the session log          `hook_session`

The repository the hooks hold is the one the project directory lies in
(`hook_session.session_repo`). Outside every repository the stop cannot
tell what changed: it says so and holds, once per turn. A rule the agent
has to remember is the weak layer; these hooks are the layer that does
not depend on remembering. Why each rule holds:
docs/notes/2026-10-19-hooks-and-report-check.md.

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
    (`undecided.undecided_state`); a current handover of the area acknowledges
    the loss and the open BLOCKERs it records, and one that no longer
    matches says why.
    The commit holds the same rule on the index (`commit_gates`). Deciding is cheap and visible: `limitation` with a reason is
    a documented deviation, which is what the gate is for; a hand-written
    `fixed` is a lie the next audit sees (LAB-015 Preflight audit before freezing).

pre-commit
    `claude-hook pre-commit`, run by the stamped `.githooks/pre-commit`
    from the repository's root, holds the index the commit carries in one
    entry (`commit_gates`): the MUST fields of every protocol the commit
    adds or changes, report-check over every staged path
    (`report_check.hold_reported`), and the undecided state
    (`undecided.undecided_state`); then `labkit-next`'s step per protocol
    touched, from the chains the hold ran.

Exit codes: stop 0, or 2 to keep the agent working (2 is what Claude Code
reads as "block"); pre-commit 0, or 1 held; a usage error 2 on stderr, as
every labkit command (`console.refuse`). An unexpected failure is a
traceback, exit 1, never swallowed.
"""

from __future__ import annotations

import contextlib
from fnmatch import fnmatch
import os
import subprocess
import signal
import sys
from collections.abc import Iterator
from pathlib import Path
from types import FrameType

from labkit.gates import registered_report
from labkit.gates.hook_session import SessionCommits
from labkit.gates.hook_session import write_stop_base
from labkit.gates.hook_session import committed_in_session
from labkit.gates.hook_session import project_dir
from labkit.gates.hook_session import record_session
from labkit.gates.hook_session import session_repo
from labkit.gates.hook_session import state_fingerprint
from labkit.gates.hook_session import stop_base_file
from labkit.gates.hook_session import stop_held_file
from labkit.formats import (
    console,
    evidence,
    protocol_block,
)
from labkit.checks import protocol_report
from labkit.gates import report_check, report_hold
from labkit.gates.install_hooks import STOP_TIMEOUT_S
from labkit.gates.next_step import next_step, steps_for
from labkit.gates.undecided import undecided_state
from labkit.run.runlog import RunIndexError
from labkit.formats.repo import (
    PROTOCOL_GLOB,
    area_protocols,
    git_root,
    indexed_changes,
    head_sha,
    shown,
    touched_paths,
)
from labkit.formats.scope_sha import areas_touched


# ------------------------------------------------------------ post-change


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
    the direct child would leave them running on their own). The alarm and the
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
    """Stop hook: an area this session worked in is held to its audit
    evidence first (`undecided.undecided_state`, the session's own commits
    too), then a number written back or committed in this session gets
    report-check, and an area that measured owes its registered report
    (`missing_reports`); blockers, or checks that outrun the stop's budget,
    send the agent back (exit 2), once per turn."""
    repo = session_repo(event)
    if repo is None:
        # nothing tells the stop what the session changed or committed: a
        # check that cannot run holds, once per turn
        print(
            f"{event.get('hook_command', 'claude-hook')} stop: {project_dir(event)} lies in no git repository — "
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
            f"{event.get('hook_command', 'claude-hook')} stop: the checks did not end within {STOP_BUDGET_S:g} s "
            f"— the harness cancels the stop hook at {STOP_TIMEOUT_S} s, and a "
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
            write_stop_base(path, checked_head)
        return 0
    # the same checked state holds once per turn: the fingerprint of the
    # state held is kept per session, and a second stop in the turn lets
    # go only on that very state — a tree changed since (content, files
    # added or gone, HEAD) is a new state and holds again. Not "no loop":
    # an agent that changes something after every hold is held again
    session = event.get("session_id")
    held_file = stop_held_file(repo, session) if session else None
    now = state_fingerprint(repo)
    if event.get("stop_hook_active"):
        was = (
            held_file.read_text(encoding="utf-8").strip()
            if held_file and held_file.is_file()
            else None
        )
        if was is None or was == now:
            print(
                f"{event.get('hook_command', 'claude-hook')} stop: sent back once in this turn on this very "
                "state — stopping; the blockers above stand and the next stop holds them again",
                file=sys.stderr,
            )
            return 0
        print(
            f"{event.get('hook_command', 'claude-hook')} stop: sent back once in this turn already, and the "
            "state changed since — the blockers above stand on the new state",
            file=sys.stderr,
        )
    if held_file is not None:
        write_stop_base(held_file, now)
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
    in_tree = touched_paths(repo)
    session = committed_in_session(repo, event)
    changed = list(dict.fromkeys(in_tree + session.paths))
    if session.note:
        print(
            f"{event.get('hook_command', 'claude-hook')} stop: {session.note}",
            file=sys.stderr,
        )
    state = undecided_state(repo, changed)
    for line in state.acknowledged:
        print(
            f"{event.get('hook_command', 'claude-hook')} stop: {line}", file=sys.stderr
        )
    undecided = state.blockers + session_evidence(repo, changed, session)
    if undecided:
        # the hold and what holds; the step is `next`'s, printed below
        print(
            "an audit of an area this session worked in found BLOCKER(s) nobody "
            "decided, or evidence is gone, changed or does not read — the stop "
            "holds, and a commit would be refused the same way "
            "(LAB-015 Preflight audit before freezing):\n  " + "\n  ".join(undecided),
            file=sys.stderr,
        )
    missing = missing_reports(repo, changed)
    if missing:
        print(
            "a protocol of an area this session worked in registers a report "
            "that is not written — the stop holds:\n  " + "\n  ".join(missing),
            file=sys.stderr,
        )
    rc = 0
    chains: dict[Path, report_check.ReleaseChain] = {}
    if changed:
        # every changed path, not only a protocol: a script edited after the
        # answer was written back reopens the area's reported numbers; its
        # lines are kept to be told under the stop's own heading
        lines: list[str] = []
        try:
            reported = report_check.hold_reported(
                changed, repo, staged=False, tell=lines.append
            )
            rc, chains = reported.exit, reported.chains
        except RunIndexError as exc:
            # a run index that does not read: what is reported cannot be told
            rc, lines = 1, [f"  {exc.why}"]
        if rc != 0:
            print(
                "report-check holds a number written back or committed in this "
                "session — the stop holds, and a commit would be refused the same "
                "way:\n" + "\n".join(lines).rstrip(),
                file=sys.stderr,
            )
    if undecided or rc != 0:
        # what to do is `next`'s step per protocol touched, read from the tree
        # the stop judges and the chains report-check ran on it; the
        # missing-report lines above are that step already
        steps = [
            s
            for s in steps_for(repo, changed, staged=False, chains=chains)
            if s not in missing
        ]
        if steps:
            print("\n".join(steps), file=sys.stderr)
    # commits it could not read keep the base where it is: past them, no
    # later stop would check them
    return (
        rc != 0 or bool(undecided) or bool(missing) or session.hold,
        not in_tree and not session.unchecked,
        checked_head,
    )


def missing_reports(repo: Path, paths: list[Path]) -> list[str]:
    """Per protocol of every area PATHS touch (`areas_touched`), and every
    protocol whose head registers a file among PATHS as its report
    (`report_hold.registering_protocols`: a REPORT.md at the root touches no
    area), whose registered report is not written though the area measured
    (`registered_report.missing_report`): the hold, printed as `labkit-next`
    prints the step it names from that finding (`next_step.Step.render`).
    A head
    that does not read is left to the checks that hold it where it is
    touched; a run index that does not read is told, once per index
    (`runlog.RunIndexError`): whether a measurement owes the report cannot
    be told."""
    out: list[str] = []
    registering = report_hold.registering_protocols(paths, repo, staged=False)
    touched = list(areas_touched(paths, repo))
    touched = [a.resolve() for a in touched]
    touched += [
        p.parent.resolve() for p in registering if p.parent.resolve() not in touched
    ]
    for area in touched:
        for protocol in area_protocols(area):
            try:
                text = protocol.read_text(encoding="utf-8")
                gap = registered_report.missing_report(
                    protocol, text, repo, declared=protocol_block.declared_run(text)
                )
            except (OSError, UnicodeError, protocol_block.BlockError):
                continue  # held as a protocol where it is touched
            except RunIndexError as exc:
                # whether a measurement owes the report cannot be told; one
                # line per index, not per protocol reading it
                if exc.why not in out:
                    out.append(exc.why)
                continue
            if gap is not None:
                # the hold is the gate's finding; what to do is `next`'s step,
                # read from the same finding — one spelling, never two
                out.append(next_step(area, protocol).render(shown(area, Path.cwd())))
    return out


def session_evidence(
    repo: Path, paths: list[Path], session: SessionCommits
) -> list[str]:
    """What the session's own commits did to evidence and the tree has not
    undone: per area PATHS touch, every change a commit since
    `session.since` made against its parent (`evidence.commit_changes`, as
    `<area>: <sentence>`) — the pre-commit's rule for a commit past it —,
    and every closed run a commit HEAD's reflog held since `session.started`
    left behind (`evidence.orphaned_runs`, named by its own path). Nothing
    where the session cannot be told: `committed_in_session` says so and
    holds there itself."""
    out: list[str] = []
    if session.since is not None:
        for area in areas_touched(paths, repo):
            shown_area = area.relative_to(repo.resolve()).as_posix()
            out += [
                f"{shown_area}: {line}"
                for line in evidence.commit_changes(area, session.since)
            ]
    if session.started is not None:
        out += evidence.orphaned_runs(repo, session.started)
    return out


def commit_gates(argv: list[str]) -> int:
    """`claude-hook pre-commit`: the commit's gates on the index in one
    entry, run by the stamped `.githooks/pre-commit` from the repository's
    root — the MUST fields of every protocol the commit adds or changes
    (`protocol_report.check_files`, the index's text), `report-check
    --if-reported --staged` over every staged path, and the undecided
    state (`undecided_state`). Each gate tells its own findings; what to do
    is `next`'s step per protocol touched, printed once (`steps_for`), from
    the index the commit carries. Exit 0 when nothing holds, 1 held, 2
    outside a repository or with arguments (it reads the index itself)."""
    if argv:
        console.refuse(
            "claude-hook pre-commit", "takes no arguments: it reads the index"
        )
        return 2
    repo = git_root(Path.cwd())
    if repo is None:
        console.refuse(
            "claude-hook pre-commit",
            f"{Path.cwd()} lies in no git repository — run it in the repo whose "
            "index is committed, as the pre-commit does",
        )
        return 2
    staged = indexed_changes(repo)
    if not staged:
        return 0
    paths = [repo / p for p in staged]
    held = False
    protocols = [
        Path(p)
        for p in indexed_changes(repo, diff_filter="ACMR")
        if fnmatch(Path(p).name, PROTOCOL_GLOB)
    ]
    if protocols:
        template = protocol_report.template_lines(protocol_report.find_template(None))
        held = protocol_report.check_files(protocols, template, staged=True)
    reported = report_check.hold_reported(paths, repo, staged=True)
    held = reported.exit != 0 or held
    state = undecided_state(repo, paths, staged=True)
    for line in state.acknowledged:
        print(f"claude-hook pre-commit: {line}")
    if state.blockers:
        print(
            "claude-hook: an audit of a staged area found BLOCKER(s) nobody decided "
            "in the index, or evidence is gone, changed or does not read — the "
            "commit is refused; it carries the decision the index holds "
            "(LAB-015 Preflight audit before freezing):\n  "
            + "\n  ".join(state.blockers)
        )
        held = True
    if not held:
        return 0
    # what to do is `next`'s step, read from the index the commit judges
    # and the chains report-check ran on it
    for step in steps_for(repo, paths, staged=True, chains=reported.chains):
        print(step)
    return 1
