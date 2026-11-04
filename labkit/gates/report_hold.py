"""report_hold — the reports a change reaches and what holds them.

Which Markdown files are reports and how the gate's state reads them
(through symbolic links, tree or index: `report_entry`, `held_place`,
`refused_link`), which reports a change reaches (`report_files`,
`committed_reports`, `reached_reports`, `discussing_reports`,
`reports_citing`), what the repo holds for them to cite (`repo_sources`),
and what holds one (`hold_report`: result blocks owed and current,
discussions, promotions, a report review owed), and what a protocol's
registered report owes (`report_owed`: the file the head's `report`
names carries the result block of the declared run or the protocol's
handover block, once it exists; `registering_protocols` finds the
protocols a change of that file reaches). `report_check` is the
entry: `if_reported` decides the order and the conditions — the
protocols first, then every report — and calls into here. Split off
`report_check` (audit 2026-10-27, third, M3): the protocol's release
stations and the reports' holding shared only format imports.
"""

from __future__ import annotations

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, replace
from pathlib import Path

from labkit.formats.answering_run import bound_runs, first_measurements, is_measurement
from labkit.formats.runs import UNREADABLE
from labkit.run.runlog import indexed_runs
from labkit.formats.gate import GUARANTEED, STATIC_EVIDENCE
from labkit.formats.runs import run_dirs, run_path
from labkit.formats.gate import WARNING, Findings, GateFinding, blocker
from labkit.formats import (
    attempts,
    findings,
    handovers,
    protocol_block,
    protocol_history,
    report_reviews,
)
from labkit.gates.ways_out import report_way_while_lost
from labkit.checks.audit_binding import (
    AuditError,
    audited_run,
)
from labkit.checks import report_blocks
from labkit.checks.result_render import rendering
from labkit.checks.report_review_inputs import review_keys, review_pieces
from labkit.formats.report_reviews import held_by
from labkit.formats.repo import (
    REPORT_SUFFIX,
    adopt_command,
    audit_command,
    handover_command,
    into_command,
    git_root,
    under_root,
    indexed_files,
    touched_paths,
    indexed_links,
    indexed_protocols,
    own_path,
    protocol_links,
    report_review_command,
    PROTOCOL_NAME,
    repo_protocols,
    SKIP_DIRS,
    shown,
    state_text,
    status_entries,
    text_at,
)
from labkit.formats.runs import read_run_config, unreportable
from labkit.formats.scope_sha import areas_touched

#: which file state the declaration (the answer line) is read from — named
#: in the output, so a reader knows what was held. The stations read the
#: working tree in every case; the caller makes the tree that state: the
#: pre-commit holds the area's tree equal to the index (`tree_differs`), the
#: adoption writes the proposal into the tree and puts it back on refusal
#: (`protocol_fill.adopt`)


def state_link(
    repo: Path,
    path: Path,
    *,
    staged: bool,
    index_links: dict[Path, str] | None = None,
) -> str | None:
    """The target PATH (its own path, `repo.own_path`) stores when the
    gate's state holds it as a symbolic link — the index's when STAGED
    (`repo.indexed_links`; INDEX_LINKS when the caller listed them
    already), else the working tree's — None for a regular file or none.
    The gate's one answer to "is this report a link"."""
    if staged:
        links = index_links if index_links is not None else indexed_links(repo)
        return links.get(path)
    return os.readlink(path) if path.is_symlink() else None


def linked_file(path: Path, link_target: str) -> Path:
    """The file a symbolic link at PATH storing LINK_TARGET points to:
    LINK_TARGET read against PATH's directory, `..` taken by its text — as
    a checkout of the commit resolves it."""
    return Path(os.path.normpath(path.parent / link_target))


def link_end(
    repo: Path,
    path: Path,
    *,
    staged: bool,
    index_links: dict[Path, str] | None = None,
) -> Path | None:
    """The file a chain of symbolic links starting at PATH ends at: in the
    tree as the system follows it; STAGED, hop by hop through the index's
    links (INDEX_LINKS, `repo.indexed_links`) while the chain stays in REPO,
    then as the disk holds it. None when the chain runs in a circle."""
    if not staged:
        try:
            return Path(os.path.realpath(path, strict=True))
        except FileNotFoundError:  # a dangling link: where it points
            return Path(os.path.realpath(path))
        except OSError:  # a circle
            return None
    links = index_links if index_links is not None else indexed_links(repo)
    seen = {path}
    file = linked_file(path, links[path]) if path in links else path
    while file not in seen:
        if not under_root(repo, file) or file not in links:
            return file
        seen.add(file)
        file = linked_file(file, links[file])
    return None


def held_place(repo: Path, path: Path) -> bool:
    """Is PATH a place the gate holds a report at: inside REPO, a Markdown
    file, no protocol, under none of SKIP_DIRS (`runs/`, `data/`, …)?"""
    if path.suffix != REPORT_SUFFIX or PROTOCOL_NAME.match(path.name):
        return False
    if not under_root(repo, path):
        return False
    return not SKIP_DIRS & set(path.relative_to(repo.resolve()).parts)


def refused_link(repo: Path, path: Path, *, staged: bool) -> str | None:
    """The target PATH stores when it is a symbolic link the gate refuses as
    a report: one whose chain ends where no report is held (`held_place`:
    under `runs/` or `data/`, outside the repository, no Markdown file) or
    runs in a circle. None for a regular file, and for a link ending at a
    held place — that file is held where it lies, and the link reads as it
    does (`CLAUDE.md -> AGENTS.md`)."""
    target = state_link(repo, path, staged=staged)
    if target is None:
        return None
    end = link_end(repo, path, staged=staged)
    return None if end is not None and held_place(repo, end) else target


def report_entry(
    repo: Path,
    path: Path,
    *,
    staged: bool,
    index_links: dict[Path, str] | None = None,
) -> tuple[str | None, str | None]:
    """(the target PATH stores as a symbolic link, or None; what a reader of
    the gate's state sees at PATH). A regular file: its content
    (`state_text`). A link — or a chain of links (`link_end`) — the content
    of the file the chain ends at: from the index while STAGED and in
    REPO, else from the disk (no commit holds a file outside the repo).
    (None, None) for a link ending at a held place (`held_place`): the
    file it points to is the report, held where it lies. The text is None
    when the state holds nothing there or the chain runs in a circle.
    INDEX_LINKS: the index's links when the caller listed them already
    (`repo.indexed_links`). The one reading of a report for `report_files`,
    `committed_reports` and `discussing_reports`."""
    links = (
        index_links if index_links is not None or not staged else indexed_links(repo)
    )
    link_target = state_link(repo, path, staged=staged, index_links=links)
    if link_target is None:
        return None, state_text(repo, path, staged=staged)
    end = link_end(repo, path, staged=staged, index_links=links)
    if end is None:
        return link_target, None
    if held_place(repo, end):
        return None, None
    if not staged or not under_root(repo, end):
        return link_target, end.read_text(encoding="utf-8") if end.is_file() else None
    return link_target, text_at(repo, end)


def tree_differs(repo: Path, area: Path) -> list[str]:
    """The paths under AREA whose working tree differs from the index — a
    tracked file modified or deleted and not staged, an untracked file —
    relative to REPO. Empty when the tree under AREA is what the commit
    would hold."""
    rel = area.resolve().relative_to(repo.resolve()).as_posix()
    return [path for xy, path in status_entries(repo, (rel,)) if xy[1] != " "]


def reports_without_block(repo: Path, protocol: Path, run_id: str) -> list[Path]:
    """The reports under REPO (`held_place`) that cite RUN_ID, the run PROTOCOL
    has adopted, and carry no result block of PROTOCOL — what the stop and
    the commit refuse (`hold_report`), found before them: labkit-next said
    "nothing holds it" and labkit-adopt "none registered", and then the hook
    held REPORT.md (reference pilot 2026-11-01, tasks 21 and 34). A block
    that does not read counts as none."""
    out: list[Path] = []
    root = repo.resolve()
    for path in sorted(root.rglob(f"*{REPORT_SUFFIX}")):
        if not held_place(repo, path) or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if run_id not in {r for _, r in report_blocks.cited_run_ids(text)}:
            continue
        try:
            found = report_blocks.blocks(text)
        except report_blocks.ReportBlockError:
            found = []
        if not any(block_protocol(path, b) == protocol.resolve() for b in found):
            out.append(path)
    return out


def report_files(
    paths: list[Path], repo: Path, *, staged: bool
) -> list[tuple[Path, str]]:
    """(path, text) of every Markdown file among PATHS that cites a run
    (`report_blocks.cited_run_ids`) — not a protocol, not under SKIP_DIRS,
    both tested at its own path (`repo.own_path`): a symbolic link where it
    lies, not where it points — with its text as the state holds it
    (`report_entry`: the index when STAGED, else the tree; through a link,
    the file it points to). A link that reads as a report is among them,
    and `hold_report` refuses it. PATHS come as the repo names them: a
    caller that resolves a link hands in the file it points to, and that
    file is tested where it lies. A file the state does not hold (deleted,
    untracked at the commit) reports nothing. Only these paths: an old
    citation in a file nobody touched reopens nothing."""
    root = repo.resolve()
    links = indexed_links(repo) if staged else None
    out: list[tuple[Path, str]] = []
    for path in paths:
        full = own_path(path if path.is_absolute() else root / path)
        if full.suffix != REPORT_SUFFIX or PROTOCOL_NAME.match(full.name):
            continue
        if not under_root(root, full):
            continue  # outside the repo: no commit and no stop holds it
        if SKIP_DIRS & set(full.relative_to(root).parts):
            continue
        _, text = report_entry(repo, full, staged=staged, index_links=links)
        if text is not None and report_blocks.cited_run_ids(text):
            out.append((full, text))
    return out


def registering_protocols(paths: list[Path], repo: Path, *, staged: bool) -> list[Path]:
    """The protocols of REPO whose head registers a file among PATHS as
    their report (`protocol_block.Head.report`), in the repo's order — the
    protocols a change of the report reaches though no path lies in their
    area: REPORT.md at the repository root is the usual case. Reads every
    protocol's head as the state holds it (the index when STAGED,
    `repo.state_text`) only when PATHS hold a candidate, a Markdown file
    that is not a protocol. A protocol the state does not hold, a link, or
    a head that does not read registers nothing here: its own hold names
    the error where it is among the paths (`report_check.hold_declared`)."""
    root = repo.resolve()
    candidates = {
        own_path(p if p.is_absolute() else root / p)
        for p in paths
        if p.suffix == REPORT_SUFFIX and not PROTOCOL_NAME.match(p.name)
    }
    if not candidates:
        return []
    protocols = indexed_protocols(repo) if staged else repo_protocols(root)
    out: list[Path] = []
    for p in protocols:
        try:
            text = state_text(repo, p, staged=staged)
            registered = protocol_block.head(text).report if text is not None else None
        except (OSError, UnicodeError, protocol_block.BlockError):
            continue  # registers nothing; held as a protocol where it is touched
        if registered is not None and own_path(root / registered) in candidates:
            out.append(p)
    return out


def report_owed(
    protocol: Path,
    text: str,
    declared: str | None,
    repo: Path,
    *,
    staged: bool,
    review: bool = True,
    progress: bool = False,
) -> GateFinding | None:
    """Why PROTOCOL's registered report owes its result — one blocker with
    the three ways out — or None.

    The head's `report` names the file (`protocol_block.report_field`,
    relative to REPO); none registered: None. The file is read as the
    state holds it (`repo.state_text`: the index when STAGED, else the
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
    handover. Why (pressure pilot 2026-10-29, tasks 34, 15, 60): the hook
    refused a report citing a run that declares no result, the agents
    deleted the run id, and the commit passed. Once released, and REVIEW,
    the report owes a clean report review of this state (`review_gap`):
    its prose may still present another run as the result — the block
    shows the adopted number, it cannot tell what the text around it
    claims (reference pilot 2026-11-01, task 15: an older run's "PASS",
    no review owed or possible). The progress account: while nothing is
    adopted, a discussion block of this protocol for the run the gates hold
    it to says what was measured and what is still open; with PROGRESS (the
    commit) it passes — saved, releasing nothing, owing no review yet —,
    without (the stop, a check by hand) it is one blocker naming the next
    step: the adoption or the handover (labkit-paper area 17, 2026-11-02:
    five of six timed-out attempts left no report, the report being written
    last). Before any measurement and without an answering run or adoption,
    a report draft owes no result block; it can be saved with registration.
    Malformed blocks still hold. Once a measurement exists, the progress,
    result or handover requirements apply."""
    head = protocol_block.head(text)
    if head.report is None:
        return None
    root = repo.resolve()
    report = own_path(root / head.report)
    here = Path.cwd()
    name_p, name_r = shown(protocol, here), shown(report, here)
    why: list[str] = []
    try:
        written = state_text(repo, report, staged=staged)
    except UnicodeDecodeError as exc:
        written = ""
        why.append(f"it does not read: {exc}")
    if written is None:
        return None
    block_owner = report_blocks.path_from_report(protocol, report)
    try:
        blocks = report_blocks.blocks(written)
        handed = handovers.handover_blocks(written)
    except (report_blocks.ReportBlockError, handovers.HandoverError) as exc:
        blocks, handed = [], []
        why.append(f"its blocks do not read: {exc}")

    if declared is not None and any(
        b.protocol == block_owner and b.run_id == declared for b in blocks
    ):
        return (
            registered_review(report, written, protocol, text, repo, staged=staged)
            if review
            else None
        )
    own_handovers = (h for h in handed if h.protocol == block_owner)
    for h in own_handovers:
        gap = handovers.block_mismatch(h, report, root, staged=staged)
        if gap is None:
            return (
                registered_review(report, written, protocol, text, repo, staged=staged)
                if review
                else None
            )
        why.append(f"its handover block at line {h.first} {gap}")
    run, _ = audited_run(protocol.parent.resolve(), protocol, text)
    if (
        declared is None
        and run is None
        and not why
        and head.id is not None
        and not has_measured(protocol.parent, head.id)
    ):
        return None
    pending = None if declared is not None or run is None or why else run.name
    if pending is not None and progress_account(written, block_owner, pending):
        return progress_hold(protocol, name_r, pending, progress=progress)
    newest = declared or (run.name if run is not None else "<run_id>")
    what = (
        f"the result block of run {declared}, its adopted result"
        if declared is not None
        else "a result block (the head has adopted no result)"
    )
    # the adoption writes the registered report's block itself (tools.adopt)
    write = (
        f"`{into_command(protocol, report)}` writes the result block"
        if declared is not None
        else f"`{adopt_command(protocol, newest)}` adopts the run"
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
    )


def progress_hold(
    protocol: Path, name_r: str, run_id: str, *, progress: bool
) -> GateFinding | None:
    """`report_owed` on a registered report (NAME_R as shown) carrying the
    progress account of RUN_ID for PROTOCOL while nothing is adopted: None
    with PROGRESS (the commit: saved, releasing nothing), else one blocker
    naming the next step — the adoption or the handover."""
    if progress:
        return None
    here = Path.cwd()
    return blocker(
        f"{shown(protocol, here)}: {name_r} carries the progress account of run "
        f"{run_id} (its discussion block) and no result yet — the progress is "
        f"saved and may be committed; a result is released only by the adoption",
        fix=f"take the next step `labkit-next {shown(protocol.parent, here)}` "
        f"names — the analysis audit and its decisions, then "
        f"`{adopt_command(protocol, run_id)}`; or end without a result: "
        f"`{handover_command(protocol, name_r)}`",
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


def has_measured(area: Path, pid: str) -> bool:
    """Does AREA hold a measurement of protocol PID — a bound run that
    declared itself one (`answering_run.is_measurement`), present, or one
    `runs.tsv` lists whose directory is gone (`runlog.indexed_runs`)? A run
    whose config cannot be read counts, as `report_check.adoption_state`
    counts it: it may be one. What a registered report owes from
    (`missing_report`) and what binds the report registered before it
    (`protocol_fill`). Raises `runlog.RunIndexError` on a run index that
    does not read: whether a deleted run was measured cannot be told."""
    taken, rest = bound_runs(area, pid)
    ours = [f for f in rest if f.binding.id == pid or f.state == UNREADABLE]
    if any(is_measurement(f) for f in [*taken, *ours]):
        return True
    return any(not run_path(area, r).is_dir() for r in indexed_runs(area, pid))


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


def bound_reports(protocol: Path, pid: str, root: Path) -> BoundReports:
    """The reports PROTOCOL (stamped id PID) registered before its first
    measurements (`answering_run.first_measurements`), as each one's commit
    in the repository ROOT holds it (`protocol_history.committed_at`), at
    both repeat costs. A committed head that does not read is unread.
    Raises RuntimeError when git fails."""
    registered: dict[str, str | None] = {}
    unread: list[tuple[str, str]] = []
    for rd in first_measurements(protocol.parent, pid, root):
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


def report_binding_gap(
    protocol: Path, text: str, *, unread: bool
) -> GateFinding | None:
    """Why the report PROTOCOL's head (its TEXT, as the state holds it)
    registers now is not the one its first measurements stood under — one
    BLOCKER — or None. The report registered before the first measurement
    is bound to what that measurement's commit holds (`bound_reports`) at
    both repeat costs: added, dropped or moved since, held, with the way back (restore
    it) or the explicit end (the handover, then a new registration; the
    earlier results and findings stay); first measurements that registered
    different reports, held. UNREAD: a first measurement whose commit
    cannot be read holds too, while the head or a readable first
    measurement registers a report — whether one was dropped or moved
    cannot be told; the low lane's registration station names the same
    commits (`report_check.registration_gaps`), so the caller that runs it
    passes False. Nothing outside a repository, without a stamped id or a
    measurement. A lost first measurement cannot establish a report binding;
    a currently registered report is held until its evidence is restored.
    Guaranteed: paths compared as `report_field` normalizes
    them. Raises `protocol_block.BlockError` on a head that does not read,
    RuntimeError when git fails."""
    head = protocol_block.head(text)
    root = git_root(protocol)
    if root is None or not head.id:
        return None
    bound = bound_reports(protocol, head.id, root)
    here = Path.cwd()
    name_p = shown(protocol, here)
    anew = (
        f"end the protocol with `{handover_command(protocol, head.report or 'REPORT.md')}` "
        f"and register anew — its earlier runs, results and findings stay"
    )
    values = set(bound.registered.values())
    if unread and bound.unread and (head.report is not None or values - {None}):
        run, why = bound.unread[0]
        return blocker(
            f"{name_p}: which report its first measurement {run} stood under cannot "
            f"be read — {why}; a report dropped or moved since cannot be told",
            fix="fetch that commit from a clone that has it (`git fetch "
            "--unshallow` in a shallow clone), or restore the repository's missing "
            f"objects (`git fsck` names them); else {anew}",
        )
    if len(values) > 1:
        named = ", ".join(
            f"{run}: {report or 'none'}" for run, report in bound.registered.items()
        )
        return blocker(
            f"{name_p}: its first measurements registered different reports ({named}) "
            f"— which one stood before the number cannot be told",
            fix=anew,
        )
    if not values:
        if (
            head.report is not None
            and not bound.unread
            and has_measured(protocol.parent, head.id)
        ):
            return blocker(
                f"{name_p}: its first measurement is missing — the report binding cannot be read",
                fix=f"restore the missing run evidence, then `labkit-next {shown(protocol.parent, here)}`; or {anew}",
            )
        return None
    (registered,) = values
    if head.report == registered:
        return None
    run = next(iter(bound.registered))
    before = f"{registered} as its report" if registered is not None else "no report"
    restore = (
        f'restore `report = "{registered}"` in the head of {name_p}'
        if registered is not None
        else f"remove the late `report` entry from the head of {name_p}"
    )
    return blocker(
        f"{name_p} registered {before} before its first "
        f"measurement {run}, and its head now registers "
        f"{head.report or 'none'} — the report a measurement stood under is bound, "
        f"a report cannot be registered, dropped or moved after measurement",
        fix=f"{restore}, then `labkit-next {shown(protocol.parent, here)}`; or {anew}",
    )


def formerly_registering(paths: list[Path], repo: Path, *, staged: bool) -> list[Path]:
    """The protocols of REPO whose first measurements registered a file
    among PATHS as their report (`bound_reports`) while their head, as the
    state holds it, registers another or none — the protocols a change of
    a dropped or moved report reaches (`registering_protocols` finds those
    whose head still names it). Read only when PATHS hold a Markdown file
    that is not a protocol. A protocol whose head does not read registers
    nothing here: its own hold names that where it is among the paths.
    Raises RuntimeError when git fails."""
    root = repo.resolve()
    candidates = {
        own_path(p if p.is_absolute() else root / p)
        for p in paths
        if p.suffix == REPORT_SUFFIX and not PROTOCOL_NAME.match(p.name)
    }
    gitroot = git_root(root)
    if not candidates or gitroot is None:
        return []
    protocols = indexed_protocols(repo) if staged else repo_protocols(root)
    out: list[Path] = []
    for p in protocols:
        try:
            text = state_text(repo, p, staged=staged)
            head = protocol_block.head(text) if text is not None else None
        except (OSError, UnicodeError, protocol_block.BlockError):
            continue
        if head is None or not head.id:
            continue
        for registered in bound_reports(p, head.id, gitroot).registered.values():
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
    staged: bool = False,
    declared: str | None = None,
) -> GateFinding | None:
    """Why PROTOCOL (its TEXT) is delivered incomplete: its head registers
    a report (`[protocol] report`, relative to REPO) that the state lacks —
    the working tree, or the index when STAGED —, while its area holds a
    measurement of it — bound and present (`answering_run.bound_runs`,
    `is_measurement`) or listed in runs.tsv and deleted since
    (`runlog.indexed_runs`). One blocker naming the two ways to write it:
    the adoption (its result block) and the handover (an end without a
    result). None when nothing is registered, the report is there, or
    nothing was measured — before a measurement a report owes nothing. At
    the commit (STAGED) a report not yet written is held only where the
    commit removes one HEAD holds or the head has adopted a result
    (DECLARED): a run committed before its progress account stays a
    checkpoint. Why: the registered report owes its review (`report_owed`);
    left unwritten, it owed none, and an agent could end without one
    (reference pilot 2026-11-01); a report deleted after the adoption passed
    the commit, report-check and labkit-next (probe 2026-11-02,
    docs/notes/2026-11-02-repair-path-probe.md). Raises
    `protocol_block.BlockError` on a head that does not read,
    `runlog.RunIndexError` on a run index that does not read (`has_measured`)."""
    head = protocol_block.head(text)
    if head.report is None or not head.id:
        return None
    report = own_path(repo.resolve() / head.report)
    if (text_at(repo, report) is not None) if staged else report.exists():
        return None
    if not has_measured(protocol.parent, head.id):
        return None
    if staged and declared is None and text_at(repo, report, "HEAD") is None:
        return None
    here = Path.cwd()
    name_p, name_r = shown(protocol, here), shown(report, here)
    what = (
        f"{name_p} registers {name_r} as its report, which is not written, and "
        f"its area holds a measurement of it — without its registered report "
        f"the delivery is incomplete"
    )
    if declared is not None:
        return blocker(
            what,
            fix=f"restore it (`git checkout HEAD -- {name_r}` where the last commit "
            f"holds it), or `{into_command(protocol, report)}` writes its result "
            f"block of {declared} again; then the report review it owes",
        )
    return blocker(
        what,
        fix=f"`{report_blocks.discuss_command(name_p, '<run_id>', name_r, report_blocks.WHY_PROGRESS)}` writes "
        f"the progress account (the commit takes it, it releases nothing); "
        f"`{adopt_command(protocol)}` adopts a run and writes its result "
        f"block into {name_r}; `{handover_command(protocol, name_r)}` ends the "
        f"protocol without a result and writes that into it; then the report "
        f"review it owes",
    )


def registered_review(
    report: Path, written: str, protocol: Path, text: str, repo: Path, *, staged: bool
) -> GateFinding | None:
    """The report review the registered REPORT (its WRITTEN text in the
    state) of PROTOCOL (its TEXT) owes once its result or handover block
    stands (`review_gap`, with the report's discussion blocks of PROTOCOL);
    None when a review of this state names no claim. A discussion block
    that does not read is a blocker of its own."""
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
        )
    return review_gap(
        report,
        name_r,
        written,
        protocol,
        text,
        mine,
        repo,
        f"is the report {name_p} registers",
        staged=staged,
    )


def newly_declared(
    protocols: list[Path], repo: Path, *, staged: bool
) -> dict[str, list[Path]]:
    """The runs PROTOCOLS declare as their result in the gate's state that
    HEAD's version of the same protocol did not — run id → the protocols
    newly declaring it. A protocol HEAD does not hold declares everything
    newly; one whose head does not read in either state names nothing
    here (`hold_declared` holds it). Empty outside a repository or before
    the first commit: no committed state to differ from."""
    out: dict[str, list[Path]] = {}
    if git_root(repo) is None:
        return out
    for p in protocols:
        if not under_root(repo, p):
            continue  # outside the repo: no HEAD to differ from
        text = state_text(repo, p, staged=staged)
        if text is None:
            continue
        try:
            now = protocol_block.declared_run(text)
        except protocol_block.BlockError:
            continue
        if now is None:
            continue
        before = text_at(repo, p, "HEAD")
        try:
            was = None if before is None else protocol_block.declared_run(before)
        except protocol_block.BlockError:
            was = None
        if now != was:
            out.setdefault(now, []).append(p)
    return out


def committed_reports(
    run_ids: set[str], repo: Path, *, staged: bool
) -> list[tuple[Path, str]]:
    """(path, text) of every report git's index holds (`repo.indexed_files`,
    the Markdown files `report_files` would hold) citing a run of RUN_IDS,
    with its text as the state holds it (`report_entry`, through a symbolic
    link — `hold_report` refuses the link). The reports a changed declaration
    reaches without being changed themselves: sixth haiku round
    (2026-10-23, t5), REPORT.md citing the run was committed while the
    protocol stayed unstaged — the commit's protocol declared nothing and
    the hook warned of an exploration's citation; the next commit staged
    the declaration and held no report. The delivered state carried the
    blocker neither commit saw. Empty outside a repository."""
    if not run_ids or git_root(repo) is None:
        return []
    candidates = [
        p
        for p in indexed_files(repo)
        if p.suffix == REPORT_SUFFIX and not PROTOCOL_NAME.match(p.name)
    ]
    links = indexed_links(repo) if staged else None
    out: list[tuple[Path, str]] = []
    for full in candidates:
        _, text = report_entry(repo, full, staged=staged, index_links=links)
        if text is None:
            continue
        if any(r in run_ids for _, r in report_blocks.cited_run_ids(text)):
            out.append((full, text))
    return out


def reports_citing(run_id: str, repo: Path) -> list[Path]:
    """Every report in REPO's working tree, tracked (`indexed_files`) or
    new (`touched_paths`), that cites RUN_ID — under `report_files`' rules
    on protocols, SKIP_DIRS and links. The reports a withdrawn result leaves
    held at the stop and the commit until each citation is removed or
    discussed. Raises RuntimeError when git fails."""
    candidates = sorted({*indexed_files(repo), *touched_paths(repo)})
    return list(
        dict.fromkeys(
            path
            for path, text in report_files(candidates, repo, staged=False)
            if any(r == run_id for _, r in report_blocks.cited_run_ids(text))
        )
    )


@dataclass(frozen=True)
class Sources:
    """What the repo holds for a report to cite: the repo's root (REPO,
    resolved), every run directory's id (KNOWN), and per protocol its text as the state holds it (TEXTS) and
    the run its head declares (DECLARED: None for none; a head that does
    not read is in UNREADABLE with the reason instead)."""

    repo: Path
    known: set[str]
    texts: dict[Path, str]
    declared: dict[Path, str | None]
    unreadable: dict[Path, str]

    def declaring(self, run_id: str) -> list[Path]:
        """The protocols declaring RUN_ID as their result."""
        return [p for p, r in self.declared.items() if r == run_id]


def repo_sources(repo: Path, *, staged: bool) -> Sources:
    """The runs, texts and declarations of every protocol of REPO — the
    index's protocols and texts when STAGED."""
    protocols = indexed_protocols(repo) if staged else repo_protocols(repo.resolve())
    out = Sources(repo.resolve(), set(), {}, {}, {})
    out.unreadable.update(protocol_links(repo, protocols, staged=staged))
    for p in protocols:
        out.known.update(rd.dir.name for rd in run_dirs(p.parent))
        if p in out.unreadable:
            continue  # a link: no text to read, the refusal stands
        try:
            text = state_text(repo, p, staged=staged)
        except (OSError, UnicodeError) as exc:
            out.unreadable[p] = f"{p}: {exc}"
            continue
        if text is None:
            continue
        out.texts[p] = text
        try:
            out.declared[p] = protocol_block.declared_run(text)
        except protocol_block.BlockError as exc:
            out.unreadable[p] = str(exc)
    return out


def block_protocol(report: Path, block: report_blocks.Block) -> Path:
    """The protocol BLOCK of REPORT names, resolved against the report's directory."""
    return (report.parent / block.protocol).resolve()


def block_sources(
    report: Path, found: list[report_blocks.Block], sources: Sources
) -> dict[str, report_blocks.BlockSource]:
    """What each protocol a block of FOUND (in REPORT) names says now: the
    run it declares and the body it renders for it (`report_blocks.BlockSource`).
    The protocol is held by the stations as well (`held_by_reports`), so a
    block never shows a number its protocol's chain does not hold."""
    out: dict[str, report_blocks.BlockSource] = {}
    for b in found:
        if b.protocol in out:
            continue
        p = block_protocol(report, b)
        if p in sources.unreadable:
            out[b.protocol] = report_blocks.BlockSource(
                None, None, f"its head does not read: {sources.unreadable[p]}"
            )
        elif p not in sources.texts:
            out[b.protocol] = report_blocks.BlockSource(
                None, None, "no protocol of the repo there"
            )
        elif (run_id := sources.declared[p]) is None:
            out[b.protocol] = report_blocks.BlockSource(
                None, None, "it has adopted no result"
            )
        else:
            try:
                body = report_blocks.block_body(
                    rendering(p.parent, sources.texts[p], run_path(p.parent, run_id))
                )
                out[b.protocol] = report_blocks.BlockSource(run_id, body)
            except (OSError, ValueError) as exc:
                out[b.protocol] = report_blocks.BlockSource(
                    run_id, None, f"cannot be rendered from {p.name}: {exc}"
                )
    return out


def owed_blocks(
    report: Path, text: str, found: list[report_blocks.Block], sources: Sources
) -> list[GateFinding]:
    """Why REPORT owes a block it does not carry, one blocker each: for
    every run it cites that a protocol declares as its result, that
    protocol's block (`report_blocks.blocks_owed`), named as the report
    names it (`path_from_report`) so the sentence carries the command."""
    cited = report_blocks.cited_run_ids(text)
    named: dict[str, Path] = {}
    declaring: dict[str, list[str]] = {}
    for run_id in {r for _, r in cited}:
        for p in sources.declaring(run_id):
            name = report_blocks.path_from_report(p, report)
            named[name] = p
            declaring.setdefault(run_id, []).append(name)
    return [
        blocker(
            f"line {n}: cites run {run_id}, the adopted result of {protocol}, "
            f"without its generated block — the number a report shows of a "
            f"adopted result is the generated one",
            fix=f"`{into_command(named[protocol], report)}` writes it",
        )
        for n, run_id, protocol in report_blocks.blocks_owed(
            cited,
            declaring,
            # each block's protocol resolved and named as the owed ones are:
            # compared as written, `../work/experiments/…` was a block
            # missing and present at once (reference pilot 2026-11-01, 34)
            {
                report_blocks.path_from_report(block_protocol(report, b), report)
                for b in found
            },
        )
    ]


#: why a report is held, printed in its heading: it is among the paths, or
#: a protocol among them newly declares a run it cites
AMONG_PATHS = "a report citing runs"


def promotions(run_ids: list[str], sources: Sources) -> list[tuple[str, Path]]:
    """(run id, protocol) for every run of RUN_IDS that is the answering run
    of a protocol declaring no result — the run every gate would hold that
    protocol to (`audit_binding.audited_run`) — and could be reported
    (`runs.unreportable` empty). Cited in a report, that is the shape of the
    promotion without the adoption: a full run's number leaving the area
    with no chain held. A probe's or an acknowledged unfrozen run's
    citation is not one — nothing could be reported of it — nor is an older
    run's, or a run of a protocol that answers with another. Raises
    AuditError on a head whose id does not read."""
    out: list[tuple[str, Path]] = []
    for protocol, declared in sources.declared.items():
        if declared is not None:
            continue
        area = protocol.parent.resolve()
        mine = [r for r in run_ids if run_path(area, r).is_dir()]
        if not mine:
            continue
        run, _ = audited_run(area, protocol, sources.texts[protocol])
        if run is None or run.name not in mine:
            continue
        cfg = read_run_config(run)
        if cfg is None or unreportable(cfg):
            continue
        out.append((run.name, protocol))
    return out


def hold_report(
    path: Path,
    text: str,
    repo: Path,
    sources: Sources,
    *,
    held_as: str = AMONG_PATHS,
    staged: bool = False,
) -> int:
    """Hold one report. First: a report that is a symbolic link in the
    state, ending where no report is held (`refused_link`), is refused alone, one blocker naming the copy that
    replaces it (`link_gap`) — the checks below wait for that copy. Then:
    its result blocks equal their protocols' rendering,
    every cited run id a run of the repo, every cited declared result shown
    in its protocol's block, every discussion block says why, says it on
    its line as its head holds it, once per protocol and run, and names a
    run of its protocol's area (`discussion_sources`), and the answering
    run of a protocol that declares no result is not cited undiscussed
    (`promotions` — the number of a full run presented without the
    adoption; blockers); any other cited run no protocol declares a
    WARNING (guaranteed); the numbers outside every block, and those in and
    beside a discussion, a WARNING that is static evidence — a hint at
    where to look, not a check of them; a report discussing a run owes a
    report review of its state that names no claim (`report_review_owed`,
    a blocker; STAGED: only the review records the index holds count —
    the commit carries its evidence). PATH is the report's own path
    (`repo.own_path`). HELD_AS says in the heading why this report is held.
    0 clean or warnings only, 1 a blocker."""
    rel = path.relative_to(repo.resolve()).as_posix()
    print(f"═══ report-check {rel} ({held_as}) ═══")
    out = Findings()
    link_target = refused_link(repo, path, staged=staged)
    if link_target is not None:
        # alone: a block names its protocol from the report's directory,
        # which the link and the file it points to do not share — the other
        # checks read the copy once it is in place
        out.take(link_gap(rel, path, link_target, repo, staged=staged))
        return out.report("report-check", "reporting")
    try:
        found = report_blocks.blocks(text)
        discussed = report_blocks.discussions(text)
    except report_blocks.ReportBlockError as exc:
        out.block(
            f"{rel}: {exc}",
            fix="restore the block's comment lines as `protocol-fill` wrote them "
            "(`--into` for a result, `--discuss` for a discussion writes them again)",
        )
        return out.report("report-check", "reporting")

    def at_report(gaps: list[GateFinding]) -> list[GateFinding]:
        return [replace(g, text=f"{rel}: {g.text}") for g in gaps]

    out.take_all(
        at_report(
            report_blocks.block_gaps(found, block_sources(path, found, sources), path)
        )
    )
    cited = report_blocks.cited_run_ids(text)
    out.take_all(at_report(report_blocks.cited_gaps(cited, sources.known)))
    out.take_all(at_report(owed_blocks(path, text, found, sources)))
    out.take_all(at_report(report_blocks.discussion_gaps(discussed)))
    out.take_all(at_report(discussion_sources(path, discussed)))
    out.take_all(report_review_owed(path, rel, text, discussed, sources, staged=staged))
    report_hints(out, rel, text, discussed)
    for line in replacement_hints(path, rel, text, repo, sources):
        out.warn(line, evidence_kind=STATIC_EVIDENCE)
    out.take_all(undeclared_findings(path, rel, cited, discussed, sources))
    return out.report("report-check", "reporting")


def link_gap(
    rel: str, path: Path, link_target: str, repo: Path, *, staged: bool
) -> GateFinding:
    """Why the report at PATH (REL to REPO), a symbolic link storing
    LINK_TARGET, is refused, with the way out: the file it points to copied
    into its place. `rm` comes first — `cp` onto a link writes into the
    file it points to, or refuses it as the same file (macOS) — and STAGED
    adds `git add`: the commit holds the index, which still holds the link
    after the copy."""
    source = shown(linked_file(path, link_target), repo)
    steps = [f"rm {shlex.quote(rel)}", f"cp {shlex.quote(source)} {shlex.quote(rel)}"]
    if staged:
        steps.append(f"git add {shlex.quote(rel)}")
    return blocker(
        f"{rel}: a symbolic link to {link_target} — a report is held as a file "
        f"at its own path, never through a link: the file a link points to can "
        f"lie where no report is held (under runs/ or data/, outside the repo)",
        fix=f"put the file in its place: `{' && '.join(steps)}`",
    )


def discussion_sources(
    path: Path, found: list[report_blocks.Discussion]
) -> list[GateFinding]:
    """Why a discussion block of FOUND, in the report at PATH, names no run
    it can discuss, one sentence each: its protocol (relative to the
    report) is no file, or the run is no `runs/<id>/` of that protocol's
    area. Exact."""
    gaps: list[GateFinding] = []
    again = "write the block again with `protocol-fill <PROTOCOL> --discuss <run> --why … --into <FILE>`"
    for d in found:
        protocol = (path.parent / d.protocol).resolve()
        at = f"line {d.first}: the discussion of run {d.run_id}"
        if not protocol.is_file():
            gaps.append(
                blocker(
                    f"{at} names {d.protocol}, and there is no such protocol",
                    fix=f"{again}, the protocol named from the report",
                )
            )
        elif not run_path(protocol.parent, d.run_id).is_dir():
            gaps.append(
                blocker(
                    f"{at}: {d.protocol}'s area has no runs/{d.run_id}/ — a "
                    f"discussion names a run of its protocol's area",
                    fix=f"{again}, naming a run of that area",
                )
            )
    return gaps


def replacement_hints(
    path: Path, rel: str, text: str, repo: Path, sources: Sources
) -> list[str]:
    """Hints that a report changed which question it answers without the
    new protocol saying so (K1): the report at HEAD cited runs of protocol A,
    its TEXT now cites runs of protocol B and none of A's, and B declares no
    `[replaces]` of A — one sentence per such pair. Static evidence: a
    report may answer several independent questions, so a switched
    citation shows no succession; whether B is a concealed new attempt is
    the audit's question. Exact over git; [] outside a repository or for a
    report HEAD does not hold."""
    before = text_at(repo, path, "HEAD")
    if before is None:
        return []
    owner = _run_protocols(sources)
    then = {owner[r] for _, r in report_blocks.cited_run_ids(before) if r in owner}
    now = {owner[r] for _, r in report_blocks.cited_run_ids(text) if r in owner}
    out = []
    for b in sorted(now - then):
        try:
            declared = protocol_block.replaces(sources.texts[b])
        except protocol_block.BlockError:
            declared = None
        for a in sorted(then - now):
            aid = protocol_block.id_of(sources.texts[a])
            if declared is None or declared.protocol != aid:
                out.append(
                    f"{rel}: cited runs of {shown(a, repo)} at HEAD and now runs of "
                    f"{shown(b, repo)}, which declares no [replaces] of it — if it is "
                    f"a new attempt at that question, declare it ([replaces] protocol "
                    f'= "{aid}" with its changes); an independent question needs '
                    f"nothing (a hint: a citation shows no succession)"
                )
    return out


def _run_protocols(sources: Sources) -> dict[str, Path]:
    """Every run id of the repo's protocols, mapped to the protocol its
    record binds it to (`protocol.id`)."""
    out: dict[str, Path] = {}
    for p, text in sources.texts.items():
        pid = protocol_block.id_of(text)
        for rd in run_dirs(p.parent):
            if rd.config is not None and rd.config.protocol.id == pid:
                out[rd.dir.name] = p
    return out


def report_hints(
    out: Findings,
    rel: str,
    text: str,
    discussed: list[report_blocks.Discussion],
) -> None:
    """Tell OUT the hints on the report REL (its TEXT, its DISCUSSED runs):
    the numbers outside every block and those in and beside a discussion —
    WARNINGs that are static evidence, a place to look, not a check."""
    unsourced = report_blocks.unsourced_numbers(text)
    if unsourced:
        out.warn(
            f"{rel}: no assigned source found for the numbers on "
            f"{len(unsourced)} line(s) — they stand outside every generated "
            f"result block (a hint, not a check of the numbers):",
            evidence_kind=STATIC_EVIDENCE,
        )
        for n, numbers in unsourced:
            out.note(f"    {rel}:{n}: {', '.join(numbers)}")
    beside = report_blocks.numbers_beside_discussed(text, discussed)
    if beside:
        out.warn(
            f"{rel}: numbers on {len(beside)} line(s) in or beside a discussed "
            f"run — a discussed run's number in a report is a reported number "
            f"unless the sentence says what it is (a hint, not a check):",
            evidence_kind=STATIC_EVIDENCE,
        )
        for n, numbers in beside:
            out.note(f"    {rel}:{n}: {', '.join(numbers)}")


def report_review_owed(
    path: Path,
    rel: str,
    text: str,
    discussed: list[report_blocks.Discussion],
    sources: Sources,
    *,
    staged: bool = False,
) -> list[GateFinding]:
    """The report review the report at PATH (REL to the repo, TEXT as the
    gate's state holds it) owes for its discussion blocks (DISCUSSED): per
    protocol they name, a BLOCKER when no review of exactly this state
    names no claim (`review_gap`). A protocol whose head registers this
    report is left out here — its own hold owes the review of the whole
    report once the result or handover block stands (`report_owed`), and
    one blocker per protocol is enough. A discussion whose protocol or run
    is missing owes none here (`discussion_sources` names it)."""
    out: list[GateFinding] = []
    by_protocol: dict[Path, list[report_blocks.Discussion]] = {}
    for d in discussed:
        by_protocol.setdefault((path.parent / d.protocol).resolve(), []).append(d)
    registering = set(registering_protocols([path], sources.repo, staged=staged))
    for protocol, mine in by_protocol.items():
        protocol_text = sources.texts.get(protocol)
        if protocol in registering or protocol_text is None:
            continue
        if not all(run_path(protocol.parent, d.run_id).is_dir() for d in mine):
            continue
        runs_named = ", ".join(dict.fromkeys(d.run_id for d in mine))
        gap = review_gap(
            path,
            rel,
            text,
            protocol,
            protocol_text,
            mine,
            sources.repo,
            f"discusses {runs_named} as not reported",
            staged=staged,
        )
        if gap is not None:
            out.append(gap)
    return out


def review_gap(
    path: Path,
    rel: str,
    text: str,
    protocol: Path,
    protocol_text: str,
    discussed: list[report_blocks.Discussion],
    repo: Path,
    held_for: str,
    *,
    staged: bool,
) -> GateFinding | None:
    """The BLOCKER of the report at PATH (REL to REPO, TEXT as the gate's
    state holds it) under PROTOCOL (its PROTOCOL_TEXT, its DISCUSSED
    blocks) when no report review of exactly this state names no claim —
    the inputs the reviewer reads (`report_review_inputs.review_pieces`),
    the report and the protocol as the state holds them
    (`report_reviews.standing`); None when one does. HELD_FOR says why the
    report owes it, for the sentence. Guaranteed: the records, their
    binding and their claim count are read exactly; whether a claim is
    right stays the reviewer's judgement. STAGED (the pre-commit): every
    input comes from the state the commit carries — the report and
    protocol from the index, and the area's tree must equal the index (its
    runs' metrics, audit records and review records are read from the
    tree), else a blocker; a review counts only when the index holds its
    record."""
    area = protocol.parent
    command = f"`{report_review_command(area, path, protocol)}`"
    if staged:
        # the review reads the area's files (runs' metrics, audit records,
        # its own records) from the tree; the commit carries the index —
        # a release on bytes the commit does not hold is none
        differs = tree_differs(repo, area)
        if differs:
            return blocker(
                f"{rel}: its report review reads {shown(area, repo)}, whose "
                f"working tree differs from the index ({', '.join(differs)}) — "
                f"the commit would not hold what the review saw",
                fix=f"stage these too: `git add -- {shlex.quote(shown(area, repo))}`",
            )
    try:
        pieces = review_pieces(area, path, text, protocol, protocol_text, discussed)
        whole, parts = report_reviews.fingerprint(pieces)
        report_key, protocol_key = review_keys(area, path, protocol)
        found = report_reviews.area_report_reviews(area)
        if staged:
            carried = set(indexed_files(repo))
            found = [r for r in found if r.path.resolve() in carried]
        stands = report_reviews.standing(found, report_key, protocol_key, whole)
    except (
        AuditError,
        findings.FindingsError,
        report_reviews.ReportReviewError,
        protocol_block.BlockError,
        RuntimeError,
    ) as exc:
        return blocker(
            f"{rel}: its report review cannot be told — {exc}",
            fix=f"repair what the sentence names, then review this state: {command}",
        )
    if stands.released:
        return None
    # lost audit evidence, then claims, then no clean review (`review_hold`)
    return review_hold(rel, protocol, held_for, stands, parts, command)


@dataclass(frozen=True)
class LostEvidence:
    """Why no audit or review can start on an area now (CAUSE,
    `attempts.gone_line`) and the way out a report citing its runs has then
    (FIX, `ways_out.report_way_while_lost`)."""

    cause: str
    fix: str


def lost_evidence(protocol: Path) -> LostEvidence | None:
    """While the audit evidence of PROTOCOL's area is gone
    (`attempts.evidence_gaps`), the cause and the way out a report citing
    its runs has — `attempts.begin` refuses every audit and review then, so
    neither an adoption nor a discussion's review can pass; None while the
    evidence stands. The one selection the report holds, `--report-review`
    and protocol-fill's adoption and handover read. Raises RuntimeError
    when git fails."""
    area = protocol.parent
    gaps = attempts.evidence_gaps(area)
    if not gaps:
        return None
    return LostEvidence(
        attempts.gone_line(gaps),
        report_way_while_lost(audit_command(area, "--findings", protocol=protocol)),
    )


def review_hold(
    rel: str,
    protocol: Path,
    held_for: str,
    stands: report_reviews.Standing,
    parts: dict[str, str],
    command: str,
) -> GateFinding:
    """The BLOCKER of a report no review releases: first, while the area's
    audit evidence is gone, that no review can run and the way out that
    works (`lost_evidence` — before any claims of this state, since no
    review can answer them then); else the claims that hold this state;
    else that it has no clean review. REL is the report, HELD_FOR why it
    owes a review of PROTOCOL's area (its discussion, or the head
    registering it), STANDS where the report stands, PARTS the state's
    fingerprint parts, COMMAND the review to run."""
    # `--discuss` under a handover for a lost record had no exit: the
    # review it owes was refused (pilot of labkit-paper area 15, t60)
    lost = lost_evidence(protocol)
    if lost is not None:
        return blocker(
            f"{rel}: {held_for} and has no clean report review of this "
            f"state — and none can run: {lost.cause}",
            fix=lost.fix,
        )
    if stands.claims:
        return blocker(
            f"{rel}: the report review holds this state ({held_for}) — "
            f"{held_by(stands)}",
            fix=f"change the report, or a source the reviewer read, so that "
            f"no claim holds, then review that state: {command} (another "
            f"draw on this state, `--again` included, releases nothing)",
        )
    since = (
        f"; the last review ({stands.earlier.path.name}) read another state — "
        f"changed since: {', '.join(report_reviews.changed_parts(stands.earlier, parts))}"
        if stands.earlier is not None
        else ""
    )
    return blocker(
        f"{rel}: {held_for} and has no clean report review of this state "
        f"(one naming no claim){since} — a cold reader checks that it "
        f"presents nothing as a result the protocol has not adopted",
        fix=f"{command} (one model call) — last, after the report's text and "
        f"its blocks are final: a change after it owes another",
    )


def undeclared_findings(
    path: Path,
    rel: str,
    cited: list[tuple[int, str]],
    discussed: list[report_blocks.Discussion],
    sources: Sources,
) -> list[GateFinding]:
    """The findings on the runs the report at PATH (REL to the repo) cites
    that no protocol declares as its result (CITED: line and id; DISCUSSED:
    the discussion blocks). Blockers: a discussed run some protocol does
    declare — "not reported" is a false claim beside a shown result; the
    undiscussed citation of a protocol's answering run that declares none
    (`promotions`), the sentence naming the adoption and the discussion
    block as the two ways out. A warning: any other undeclared run cited
    undiscussed — an exploration's run is looked at. A discussed run says
    so and gets no warning."""
    out: list[GateFinding] = []
    for d in discussed:
        for protocol in sources.declaring(d.run_id):
            named = report_blocks.path_from_report(protocol, path)
            out.append(
                blocker(
                    f"{rel}: line {d.first}: run {d.run_id} is discussed as not "
                    f"reported, but {named} has adopted it as its result",
                    fix="remove the discussion block — the generated result block "
                    f"shows the number —, then `report-check --if-reported {rel}`",
                )
            )
    said_so = {d.run_id for d in discussed}
    undeclared = sorted(
        {
            r
            for _, r in cited
            if r in sources.known and r not in said_so and not sources.declaring(r)
        }
    )
    try:
        promoted = promotions(undeclared, sources)
    except AuditError as exc:
        return out + [
            blocker(
                f"{rel}: cites a run of a protocol whose head does not read — {exc.why}",
                fix=exc.fix
                or "repair the head as the sentence says (`protocol-check "
                "<PROTOCOL> --contract` shows its fields)",
            )
        ]
    for run_id, protocol in promoted:
        named = report_blocks.path_from_report(protocol, path)
        if adoption_unstaged(protocol, run_id, sources):
            out.append(
                blocker(
                    f"{rel}: cites {run_id}, the answering run of {named}, which "
                    f"adopts it in the working tree but not in the index — the "
                    f"adoption (`labkit-adopt`) wrote is not staged",
                    fix=f"`git add {named}` stages the protocol with its "
                    f"adoption; commit the report and the protocol together",
                )
            )
            continue
        # adoption and discussion both owe an audit or a review, which no
        # lost evidence lets start: then the way out is the restore or the
        # removal, in place of the blocker below
        lost = lost_evidence(protocol)
        if lost is not None:
            out.append(
                blocker(
                    f"{rel}: cites {run_id}, the answering run of {named}, which "
                    f"has adopted no result — and neither its adoption nor a "
                    f"discussion can pass: {lost.cause}",
                    fix=lost.fix,
                )
            )
            continue
        out.append(
            blocker(
                f"{rel}: cites {run_id}, the answering run of {named}, which has adopted "
                f"no result",
                fix=f"a full run's number leaves the area through "
                f"`{adopt_command(protocol, run_id)}` (it names what the "
                f"adoption still owes), then `--into {rel}` writes its block; a run "
                f"this report looks at without reporting it stands in a discussion "
                f"block: `{report_blocks.discuss_command(shown(protocol, Path.cwd()), run_id, rel)}`",
            )
        )
    looked_at = [r for r in undeclared if r not in {r for r, _ in promoted}]
    if looked_at:
        out.append(
            GateFinding(
                WARNING,
                f"{rel}: cites {', '.join(looked_at)}, which no protocol has adopted as "
                f"its result — a reported number is adopted by `labkit-adopt "
                f"<area> <run_id>`, and its block written by `protocol-fill "
                f"<PROTOCOL> --into {rel}`; an exploration's run is cited, not "
                f"reported",
                evidence_kind=GUARANTEED,
            )
        )
    return out


def adoption_unstaged(protocol: Path, run_id: str, sources: Sources) -> bool:
    """Does the working tree's PROTOCOL declare RUN_ID while SOURCES — the
    index, when the gate runs staged — do not? Then the adoption was written
    and not staged, and the hold names that instead of "declares no result"
    (the agent of task 34, 2026-10-29, read the latter as a rejected
    review's effect, withdrew the declaration and later deleted the run id).
    False when SOURCES declare it, when the tree's protocol is gone or does
    not read, or when the gate reads the tree itself."""
    if sources.declared.get(protocol) == run_id:
        return False
    try:
        return (
            protocol_block.declared_run(protocol.read_text(encoding="utf-8")) == run_id
        )
    except (OSError, UnicodeError, protocol_block.BlockError):
        return False


#: why a report is held though no path names it: it discusses a run of an
#: area the change touches, whose sources its review read
DISCUSSES_TOUCHED = "a report discussing a run of an area this change touches"


def discussing_candidates(
    repo: Path, *, staged: bool
) -> list[tuple[Path, str, list[report_blocks.Discussion] | None]]:
    """(path, text, its discussion blocks — None when they do not read) of
    every report of REPO that discusses a run, as the state holds it: in
    the tree every Markdown file at a held place (`held_place`: no
    protocol, not under SKIP_DIRS — the walk `reports_without_block`
    makes, no git needed), in the index every file it holds (STAGED; []
    outside a repository), each read through `report_entry`. The one scan
    behind `discussing_reports` and `discussion_review_findings`. Raises
    RuntimeError when git fails on the index."""
    root = repo.resolve()
    if staged:
        if git_root(repo) is None:
            return []
        candidates = [own_path(c) for c in indexed_files(repo)]
        links = indexed_links(repo)
    else:
        candidates = sorted(root.rglob(f"*{REPORT_SUFFIX}"))
        links = None
    out: list[tuple[Path, str, list[report_blocks.Discussion] | None]] = []
    for full in dict.fromkeys(candidates):
        if not held_place(repo, full):
            continue
        _, text = report_entry(repo, full, staged=staged, index_links=links)
        if text is None or report_blocks.DISCUSS_OPEN not in text:
            continue
        try:
            out.append((full, text, report_blocks.discussions(text)))
        except report_blocks.ReportBlockError:
            out.append((full, text, None))
    return out


def discussion_review_findings(
    protocol: Path, text: str, repo: Path, *, staged: bool
) -> list[GateFinding]:
    """The report reviews the reports of REPO owe for discussing a run of
    PROTOCOL (its TEXT as the state holds it): the findings `hold_report`
    holds each such report with (`report_review_owed`), read here per
    protocol so that `report_check.chain_gaps` — and through it
    `report-check AREA` and `labkit-next` — holds and names exactly what
    the stop and the commit hold (`report_check.if_reported`), one
    function for both. Only the discussion blocks naming PROTOCOL count; a
    report whose blocks do not read is left to its own hold (`hold_report`
    names the block). STAGED: the index's files and texts, [] outside a
    repository. Raises RuntimeError when git fails on the index."""
    root = repo.resolve()
    target = protocol.resolve()
    out: list[GateFinding] = []
    for full, report_text, found in discussing_candidates(repo, staged=staged):
        if found is None:
            continue
        mine = [d for d in found if (full.parent / d.protocol).resolve() == target]
        if not mine:
            continue
        sources = Sources(root, set(), {target: text}, {}, {})
        rel = full.relative_to(root).as_posix()
        out += report_review_owed(full, rel, report_text, mine, sources, staged=staged)
    return out


def discussing_reports(
    paths: list[Path], held: set[Path], repo: Path, *, staged: bool
) -> list[tuple[Path, str, str]]:
    """(path, text, why held) of every report the state holds
    (`discussing_candidates`), not in HELD, with a discussion block whose
    protocol lies in an area PATHS touch (`areas_touched`): the review of
    such a report read that area's protocol, runs and audits, so a change
    there makes it stale though the report is untouched. A report whose
    blocks do not read is held too — the gate names the block. Empty
    outside a repository."""
    areas = (
        {a.resolve() for a in areas_touched(paths, repo)} if git_root(repo) else set()
    )
    if not areas:
        return []
    out: list[tuple[Path, str, str]] = []
    for full, text, found in discussing_candidates(repo, staged=staged):
        if full in held:
            continue
        if found is None or any(
            (full.parent / d.protocol).resolve().parent in areas for d in found
        ):
            out.append((full, text, DISCUSSES_TOUCHED))
    return out


def reached_reports(
    protocols: list[Path],
    reports: list[tuple[Path, str]],
    repo: Path,
    *,
    staged: bool,
) -> list[tuple[Path, str, str]]:
    """(path, text, why held) of every committed report not among REPORTS
    that cites a run one of PROTOCOLS newly declares in the gate's state
    (`newly_declared`, `committed_reports`); the third element is the
    heading `hold_report` prints, naming the declaring protocol(s)."""
    declared = newly_declared(protocols, repo, staged=staged)
    held = {p for p, _ in reports}
    out: list[tuple[Path, str, str]] = []
    for path, text in committed_reports(set(declared), repo, staged=staged):
        if path in held:
            continue
        cited = {r for _, r in report_blocks.cited_run_ids(text)} & set(declared)
        by = sorted({p.name for run_id in cited for p in declared[run_id]})
        out.append(
            (
                path,
                text,
                f"a committed report citing a run {', '.join(by)} newly adopts "
                f"as its result",
            )
        )
    return out


def held_by_reports(reports: list[tuple[Path, str]], sources: Sources) -> list[Path]:
    """The protocols a report of REPORTS shows a result of, each once: the
    protocol a block names, and every protocol declaring a run the report
    cites in its prose — the result a changed report shows is held to its
    chain like a changed protocol. A block that does not read names none
    (`hold_report` names it)."""
    out: list[Path] = []
    for path, text in reports:
        try:
            named = [block_protocol(path, b) for b in report_blocks.blocks(text)]
        except report_blocks.ReportBlockError:
            named = []
        named += [
            p
            for _, run_id in report_blocks.cited_run_ids(text)
            for p in sources.declaring(run_id)
        ]
        out += [p for p in dict.fromkeys(named) if p in sources.texts and p not in out]
    return out
