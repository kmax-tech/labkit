"""registered_report — what the report a protocol's head registers
(`[protocol] report`) owes: its result block or the protocol's handover
block once delivered (`report_owed`), the account of a measured run before
any adoption (`progress_account`), the duty to report that a commit
started once the area measured — hung on the protocol's id, free to move
to another file, not ended by removing the entry or the protocol
(`report_duty`, `report_binding_gap`, `orphaned_report_duties`) —, and a
report not written though the area measured or removed by a commit
(`missing_report`). Read-only; report-check, the stop and `labkit-next`
hold and name these. Reports outside the protocol: `report_hold`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from labkit.formats.commands import checkout_command
from labkit.gates.report_hold import Sources, review_gap
from labkit.formats.area_state import Measured
from labkit.formats.gate import OPEN_RULE, TECHNICAL_RULE
from labkit.formats.gate import GateFinding, blocker
from labkit.formats import (
    handovers,
    protocol_block,
    protocol_history,
)
from labkit.checks.audit_binding import (
    audited_run,
)
from labkit.checks import report_blocks
from labkit.formats.repo import (
    ever_committed,
    git_root,
    head_sha,
    own_path,
    protocols_in,
    report_place,
    shown,
    state_holds,
    state_text,
    text_at,
)
from labkit.formats.commands import (
    adopt_command,
    handover_command,
    into_command,
    step_command,
)


def report_file(root: Path, registered: str) -> Path:
    """The file the head's `report` field REGISTERED names, under the repo
    ROOT, at its own path (`repo.own_path`: a link is the link) — the one
    resolution every reader of the registered report asks."""
    return own_path(root / registered)


def report_owed(
    protocol: Path,
    text: str,
    declared: str | None,
    sources: Sources,
    *,
    review: bool = True,
) -> GateFinding | None:
    """Why PROTOCOL's registered report owes its result — one blocker with
    the three ways out — or None. SOURCES is the check run's cache: the
    repo, the file state, and the area's state (what it measured of the
    protocol, and the run that answers) and audit evidence, built once.

    The head's `report` names the file (`protocol_block.report_field`,
    relative to the repo); none registered: None. The file is read as the
    state holds it (`repo.state_text`: the index when staged, else the
    tree); not there: None — the obligation is on what is delivered, a
    report not yet written owes nothing, and one the commit does not carry
    is not delivered (the stop names a missing one, `agent_hooks.missing_reports`).
    Released by EITHER the protocol's result block
    showing DECLARED, the run the head declares (written by `protocol-fill
    --into`; where the report is among the paths its body is held to the
    rendering as well, `report_blocks.block_gaps`) OR the protocol's
    handover block as its record renders it (`handovers.block_mismatch`).
    Everything else is held: a number with no run id, a run id typed in
    without the block (the id itself is held by `report_blocks.cited_gaps`
    where the report is among the paths), a discussion block — `--discuss`
    says a run was looked at and closes nothing —, blocks that do not
    read, a report that is not UTF-8. The ways out name the run the gates
    hold the protocol to (`audit_binding.audited_run`: the newest kept one;
    DECLARED when declared) for the adoption and the discussion, and the
    handover. Why everything else is held: deleting the run id a refusal
    named must not release the report. Once released, and REVIEW,
    the report owes a clean report review of this state (`review_gap`):
    its prose may still present another run as the result — the block
    shows the adopted number, it cannot tell what the text around it
    claims. The progress account: while nothing is
    adopted, a discussion block of this protocol for the run the gates hold
    it to says what was measured and what is still open — an honest interim
    state; it passes at the commit, the stop and a check by hand alike,
    releasing nothing and owing no review yet. A run that exists forces
    neither an adoption nor a handover; the next step stays `labkit-next`'s
    to name. Before any measurement and without an answering run or adoption,
    a report draft owes no result block; it can be saved with registration.
    Malformed blocks still hold. Once a measurement exists, the progress,
    result or handover requirements apply."""
    head = protocol_block.head(text)
    if head.report is None:
        return None
    repo, staged = sources.repo, sources.staged
    state = sources.held_state(protocol.parent)
    root = repo.resolve()
    report = report_file(root, head.report)
    here = Path.cwd()
    name_p, name_r = shown(protocol, here), shown(report, here)
    why: list[str] = []
    # a report or blocks that do not read: what the report owes could not be
    # looked for, the technical contract; else the duty itself, which no
    # rule's sentence states for a written report (an open assignment)
    rule = OPEN_RULE
    try:
        written = state_text(repo, report, staged=staged)
    except UnicodeDecodeError as exc:
        written = ""
        why.append(f"it does not read: {exc}")
        rule = TECHNICAL_RULE
    if written is None:
        return None
    block_owner = report_blocks.path_from_report(protocol, report)
    try:
        blocks = report_blocks.blocks(written)
        handed = handovers.handover_blocks(written)
    except (report_blocks.ReportBlockError, handovers.HandoverError) as exc:
        blocks, handed = [], []
        why.append(f"its blocks do not read: {exc}")
        rule = TECHNICAL_RULE

    if declared is not None and any(
        b.protocol == block_owner and b.run_id == declared for b in blocks
    ):
        return (
            registered_review(report, written, protocol, text, sources)
            if review
            else None
        )
    # by the id its record names, so a protocol renamed since the handover
    # is still the one handed over (`handovers.owns_block`)
    own_handovers = (
        h
        for h in handed
        if head.id is not None
        and handovers.owns_block(h, block_owner, head.id, report, root, staged=staged)
    )
    for h in own_handovers:
        gap = handovers.block_mismatch(h, report, root, staged=staged)
        if gap is None:
            return (
                registered_review(report, written, protocol, text, sources)
                if review
                else None
            )
        why.append(f"its handover block at line {h.first} {gap}")
    run, _ = audited_run(state, protocol, text)
    if (
        declared is None
        and run is None
        and not why
        and head.id is not None
        and not state.measured_of(head.id).has_measured
    ):
        return None
    pending = None if declared is not None or run is None or why else run.name
    if pending is not None and progress_account(written, block_owner, pending):
        return None  # an honest interim state: saved, releasing nothing
    newest = declared or (run.name if run is not None else "<run_id>")
    what = (
        f"the result block of run {declared}, its adopted result"
        if declared is not None
        else "a result block (the head has adopted no result)"
    )
    # the adoption writes the registered report's block itself (tools.adopt)
    write_cmd = (
        into_command(protocol, report)
        if declared is not None
        else adopt_command(protocol, newest)
    )
    write = (
        f"`{write_cmd}` writes the result block"
        if declared is not None
        else f"`{write_cmd}` adopts the run"
        + (" (the newest kept one)" if run is not None else "")
        + " and writes its result block"
    )
    return blocker(
        f"{name_p} registers {name_r} as its report, and {name_r} carries "
        f"neither {what} nor the protocol's handover block"
        + "".join(f"; {w}" for w in why)
        + " — a registered report owes the result or an explicit end without "
        "one; a number with its run id removed, or a run id typed in, releases "
        "nothing",
        fix=f"{write}; "
        f"`{report_blocks.discuss_command(name_p, newest, name_r, report_blocks.WHY_PROGRESS)}` writes the "
        f"progress account of the run the gates hold it to — the commit takes it, "
        f"it releases nothing and the result or the handover stays owed; "
        f"`{handover_command(protocol, name_r)}` ends the protocol without a result",
        step=write_cmd,
        rule=rule,
    )


def progress_account(written: str, owner: str, run_id: str) -> bool:
    """Does the report text WRITTEN carry a discussion block of the
    protocol OWNER (its path relative to the report) for RUN_ID — the
    progress account `report_owed` accepts at the commit while nothing is
    adopted? A discussion that does not read is none: the report's own hold
    names it (`hold_report`). Pure."""
    try:
        found = report_blocks.discussions(written)
    except report_blocks.ReportBlockError:
        return False
    return any(
        (d.protocol, d.run_id) == (owner, run_id) and d.why.strip() for d in found
    )


@dataclass(frozen=True)
class BoundReports:
    """What the commits of a protocol's first measurements registered as its
    report (`committed_at`), on both lanes: REGISTERED run id → report path
    (None: none registered); UNREAD (run id, why) for a first measurement
    whose commit cannot be read."""

    registered: dict[str, str | None]
    unread: list[tuple[str, str]]


#: why a first measurement's commit cannot be read, by `committed_at` cause
_UNREAD = {
    protocol_history.NO_COMMIT: "it recorded no commit",
    protocol_history.UNKNOWN_COMMIT: "it recorded a commit this repository does "
    "not hold (a rewritten history, a shallow clone)",
    protocol_history.NOT_COMMITTED: "its commit does not hold the protocol",
    protocol_history.UNREADABLE_COMMIT: "git cannot read the protocol at its commit",
}


def bound_reports(protocol: Path, measured: Measured, root: Path) -> BoundReports:
    """The reports PROTOCOL registered before its first measurements
    (MEASURED, `area_state.Measured.firsts`), as each one's commit in
    the repository ROOT holds it (`protocol_history.committed_at`), at
    both repeat costs. A committed head that does not read is unread.
    Raises RuntimeError when git fails."""
    registered: dict[str, str | None] = {}
    unread: list[tuple[str, str]] = []
    for rd in measured.firsts:
        then = protocol_history.committed_at(protocol, rd, root)
        if then.text is None:
            why = _UNREAD[then.cause or ""]
            unread.append((then.run, f"{why} ({then.detail})" if then.detail else why))
            continue
        try:
            head = protocol_block.head(then.text)
        except protocol_block.BlockError as exc:
            unread.append((then.run, f"its committed head does not read ({exc})"))
            continue
        registered[then.run] = head.report
    return BoundReports(registered, unread)


def committed_report(root: Path, pid: str) -> str | None:
    """The report the protocol carrying the id PID registers in HEAD of the
    repository ROOT, found by its id (`protocol_history.protocol_path_at`:
    a rename keeps it); None when HEAD holds no such protocol, its head
    does not read or registers none, or there is no commit yet. Raises
    GitError when git cannot run."""
    if not head_sha(root):
        return None
    then = protocol_history.protocol_path_at(root, "HEAD", pid)
    text = text_at(root, then, "HEAD") if then is not None else None
    if text is None:
        return None
    try:
        return protocol_block.head(text).report
    except protocol_block.BlockError:
        return None


def report_duty(measured: Measured, pid: str, root: Path) -> tuple[str, str] | None:
    """The report the protocol with id PID owes by what git holds —
    (report, since when) — or None. The duty hangs on the id, not on a
    path: it starts with a commit, once the area has measured (MEASURED,
    `area_state.Measured.has_measured`) — a report committed before the
    first measurement binds at that measurement (`bound_reports`, read by
    id), one entered later binds with the commit that carries it
    (`committed_report`: read from HEAD, the last commit, each time). An
    edit of the working tree binds nothing. A first measurement whose
    commit cannot be read (`BoundReports.unread`) says nothing here; HEAD
    alone then decides. Not seen: a report committed after the first measurement and removed
    again by a later commit — the commit hook holds that removal while HEAD
    still registers it. Raises RuntimeError when git fails."""
    if not measured.has_measured:
        return None
    # no path of today: at a path the commit does not hold, `committed_at`
    # finds the protocol by the id the run recorded
    bound = bound_reports(root / "PROTOCOL-read-by-id.md", measured, root)
    for run, report in bound.registered.items():
        if report is not None:
            return report, f"before its first measurement {run}"
    late = committed_report(root, pid)
    if late is not None:
        return late, "in its last commit, after its first measurement"
    return None


def report_binding_gap(
    protocol: Path, text: str, *, measured: Measured
) -> GateFinding | None:
    """Why the report duty of PROTOCOL (its TEXT, as the state holds it) is
    dropped — one BLOCKER — or None. A protocol that owes a report
    (`report_duty`) registers one: its head may name another file than
    before, and the duty moves with it — the new target owes what the old
    one owed (`report_owed`, `missing_report`), and what the old file says
    stays held by the checks of every report. Only a head that registers
    none while the duty stands is held, with the ways out: restore the
    entry, name another file, or end the protocol by a handover. Nothing
    outside a repository, without a stamped id or before a measurement.
    Raises `protocol_block.BlockError` on a head that does not read,
    RuntimeError when git fails."""
    head = protocol_block.head(text)
    root = git_root(protocol)
    if root is None or not head.id or head.report is not None:
        return None
    owed = report_duty(measured, head.id, root)
    if owed is None:
        return None
    report, since = owed
    name_p = shown(protocol, Path.cwd())
    handover = handover_command(protocol, report)
    return blocker(
        f"{name_p} registered {report} as its report {since}, and its head now "
        f"registers none — the report a measurement took on is not ended by "
        f"removing the entry",
        fix=f'restore `report = "{report}"` in the head of {name_p}, or name '
        f"another file there (the duty moves with the entry), then "
        f"`{step_command(protocol.parent)}`; or end the protocol with "
        f"`{handover}` and register anew — its earlier runs, results and "
        f"findings stay",
        step=handover,
        rule=OPEN_RULE,
    )


def orphaned_report_duties(
    area: Path, measured: Mapping[str, Measured], carried: set[str], root: Path
) -> list[GateFinding]:
    """One BLOCKER per protocol id AREA measured (MEASURED, id → what it
    measured) that no protocol of the area carries now (CARRIED) while it
    owes a report (`report_duty`): deleting a protocol, or putting another
    in its place, does not end the report it owes. A measured id that owed
    no report is passed over — a run of a protocol that is gone is no
    finding by itself. The one way out is the protocol's return: no
    handover ends a protocol that is not there (`handovers`)."""
    out = []
    for pid in sorted(set(measured) - carried):
        owed = report_duty(measured[pid], pid, root)
        if owed is None:
            continue
        report, since = owed
        # `Measured.runs` holds every unreadable run of the area too
        runs = (
            ", ".join(
                rd.dir.name
                for rd in measured[pid].runs
                if rd.config is not None and rd.config.protocol.id == pid
            )
            or "a lost run"
        )
        out.append(
            blocker(
                f"{shown(area, Path.cwd())}: no protocol of the area carries the id "
                f"{pid}, under which it measured ({runs}); that protocol registered "
                f"{report} as its report {since} — removing or replacing the "
                f"protocol does not end the report it owes",
                fix=f"restore the protocol that carries {pid} from the commit "
                f"before its removal (`git log --diff-filter=D --name-only -- "
                f"{shown(area, Path.cwd())}` names it), then "
                f"`{step_command(area)}`",
                rule=OPEN_RULE,
            )
        )
    return out


def formerly_registering(paths: list[Path], repo: Path, sources: Sources) -> list[Path]:
    """The protocols of REPO whose first measurements registered a file
    among PATHS as their report (`bound_reports`) while their head, as the
    state holds it, registers another or none — the protocols a change of
    a dropped or moved report reaches (`registering_protocols` finds those
    whose head still names it). Read only when PATHS hold a Markdown file
    that is not a protocol. A protocol whose head does not read registers
    nothing here: its own hold names that where it is among the paths.
    Raises RuntimeError when git fails.
    SOURCES give the file state and the measured runs
    (`Sources.held_state`)."""
    root = repo.resolve()
    candidates = {
        own_path(p if p.is_absolute() else root / p)
        for p in paths
        if report_place(PurePosixPath(p.name))
    }
    gitroot = git_root(root)
    if not candidates or gitroot is None:
        return []
    staged = sources.staged
    protocols = protocols_in(repo, staged=staged)
    out: list[Path] = []
    for p in protocols:
        try:
            text = state_text(repo, p, staged=staged)
            head = protocol_block.head(text) if text is not None else None
        except (OSError, UnicodeError, protocol_block.BlockError):
            continue
        if head is None or not head.id:
            continue
        held = sources.held_state(p.parent).measured_of(head.id)
        for registered in bound_reports(p, held, gitroot).registered.values():
            if (
                registered is not None
                and registered != head.report
                and own_path(root / registered) in candidates
            ):
                out.append(p)
                break
    return out


def missing_report(
    protocol: Path,
    text: str,
    repo: Path,
    *,
    measured: Measured,
    staged: bool = False,
    declared: str | None = None,
) -> GateFinding | None:
    """Why PROTOCOL (its TEXT) is delivered incomplete: its head registers
    a report (`[protocol] report`, relative to REPO) that the state lacks —
    the working tree, or the index when STAGED —, while its area holds a
    measurement of it (MEASURED, `area_state.Measured`: present, held by a
    commit, or only in the local index). One blocker naming the two ways to
    write it:
    the adoption (its result block) and the handover (an end without a
    result). The finding says what was checked: the report is missing, and
    whether a commit of the available history contains it
    (`repo.ever_committed`). It records the open assignment either way: the
    standard names a report "never written", which no history shows, and
    states no duty for one written and removed. None when nothing is registered, the report is there, or
    nothing was measured — before a measurement a report owes nothing. At
    the commit (STAGED) a report not yet written is held only where the
    commit removes one HEAD holds or the head has adopted a result
    (DECLARED): a run committed before its progress account stays a
    checkpoint. Why: the registered report owes its review (`report_owed`);
    left unwritten, it would owe none, and an agent could end without one;
    a report deleted after the adoption would otherwise pass the commit,
    report-check and labkit-next. Raises
    `protocol_block.BlockError` on a head that does not read,
    `run_index.RunIndexError` on a run index that does not read."""
    head = protocol_block.head(text)
    if head.report is None or not head.id:
        return None
    report = report_file(repo.resolve(), head.report)
    if state_holds(repo, report, staged=staged):
        return None
    if not measured.has_measured:
        return None
    if staged and declared is None and text_at(repo, report, "HEAD") is None:
        return None
    here = Path.cwd()
    name_p, name_r = shown(protocol, here), shown(report, here)
    history = (
        "a commit contains it"
        if ever_committed(repo, report)
        else "no commit in the available history contains it"
    )
    what = (
        f"{name_p} registers {name_r} as its report; the report is missing "
        f"({history}), and its area holds a measurement of it — without its "
        f"registered report the delivery is incomplete"
    )
    if declared is not None:
        into = into_command(protocol, report)
        return blocker(
            what,
            fix=f"restore it (`{checkout_command(name_r)}` where the last commit "
            f"holds it), or `{into}` writes its result "
            f"block of {declared} again; then the report review it owes",
            step=into,
            rule=OPEN_RULE,
        )
    discuss = report_blocks.discuss_command(
        name_p, "<run_id>", name_r, report_blocks.WHY_PROGRESS
    )
    return blocker(
        what,
        fix=f"`{discuss}` writes "
        f"the progress account (the commit takes it, it releases nothing); "
        f"`{adopt_command(protocol)}` adopts a run and writes its result "
        f"block into {name_r}; `{handover_command(protocol, name_r)}` ends the "
        f"protocol without a result and writes that into it; then the report "
        f"review it owes",
        step=discuss,
        rule=OPEN_RULE,
    )


def registered_review(
    report: Path, written: str, protocol: Path, text: str, sources: Sources
) -> GateFinding | None:
    """The report review the registered REPORT (its WRITTEN text in the
    state) of PROTOCOL (its TEXT) owes once its result or handover block
    stands (`review_gap`, with the report's discussion blocks of PROTOCOL);
    None when a review of this state names no claim. A discussion block
    that does not read is a blocker of its own. SOURCES is the check
    run's cache (`review_gap`)."""
    here = Path.cwd()
    name_p, name_r = shown(protocol, here), shown(report, here)
    try:
        mine = [
            d
            for d in report_blocks.discussions(written)
            if (report.parent / d.protocol).resolve() == protocol.resolve()
        ]
    except report_blocks.ReportBlockError as exc:
        return blocker(
            f"{name_r}: its discussion blocks do not read — {exc}",
            fix="restore the block's comment lines as `protocol-fill` wrote "
            "them (`--discuss … --into` writes the block again)",
            rule=TECHNICAL_RULE,
        )
    return review_gap(
        report,
        name_r,
        written,
        protocol,
        text,
        mine,
        f"is the report {name_p} registers",
        sources,
    )
