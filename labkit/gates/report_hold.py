"""report_hold — the reports a change reaches and what holds them.

Which Markdown files are reports and how the gate's state reads them
(through symbolic links, tree or index: `report_entry`, `held_place`,
`refused_link`), which reports a change reaches (`report_files`,
`committed_reports`, `reached_reports`, `discussing_reports`,
`reports_citing`), what the repo holds for them to cite (`repo_sources`),
and what holds one (`hold_report`: result blocks owed and current,
discussions, promotions, a report review owed). `report_check` is the
entry: `if_reported` decides the order and the conditions — the
protocols first, then every report — and calls into here. Split off
`report_check` (audit 2026-10-27, third, M3): the protocol's release
stations and the reports' holding shared only format imports.
"""

from __future__ import annotations

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.gate import GUARANTEED, STATIC_EVIDENCE
from labkit.formats.runs import run_dirs, run_path
from labkit.formats.gate import BLOCKER, WARNING, Findings, GateFinding
from labkit.formats import (
    findings,
    protocol_block,
    report_reviews,
)
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
                None, None, "it declares no result"
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
) -> list[str]:
    """Why REPORT owes a block it does not carry, one sentence each: for
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
        f"line {n}: cites run {run_id}, the declared result of {protocol}, without "
        f"its generated block — the number a report shows of a declared result is "
        f"the generated one: `{into_command(named[protocol], report)}` writes it"
        for n, run_id, protocol in report_blocks.blocks_owed(
            cited, declaring, {b.protocol for b in found}
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
        out.block(link_gap(rel, path, link_target, repo, staged=staged))
        return out.report("report-check", "reporting")
    try:
        found = report_blocks.blocks(text)
        discussed = report_blocks.discussions(text)
    except report_blocks.ReportBlockError as exc:
        out.block(f"{rel}: {exc}")
        return out.report("report-check", "reporting")
    for gap in report_blocks.block_gaps(
        found, block_sources(path, found, sources), path
    ):
        out.block(f"{rel}: {gap}")
    cited = report_blocks.cited_run_ids(text)
    for gap in report_blocks.cited_gaps(cited, sources.known):
        out.block(f"{rel}: {gap}")
    for gap in owed_blocks(path, text, found, sources):
        out.block(f"{rel}: {gap}")
    for gap in report_blocks.discussion_gaps(discussed):
        out.block(f"{rel}: {gap}")
    for gap in discussion_sources(path, discussed):
        out.block(f"{rel}: {gap}")
    out.take_all(report_review_owed(path, rel, text, discussed, sources, staged=staged))
    report_hints(out, rel, text, discussed)
    for line in replacement_hints(path, rel, text, repo, sources):
        out.warn(line, evidence_kind=STATIC_EVIDENCE)
    out.take_all(undeclared_findings(path, rel, cited, discussed, sources))
    return out.report("report-check", "reporting")


def link_gap(
    rel: str, path: Path, link_target: str, repo: Path, *, staged: bool
) -> str:
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
    return (
        f"{rel}: a symbolic link to {link_target} — a report is held as a file "
        f"at its own path, never through a link: the file a link points to can "
        f"lie where no report is held (under runs/ or data/, outside the repo); "
        f"put the file in its place: `{' && '.join(steps)}`"
    )


def discussion_sources(path: Path, found: list[report_blocks.Discussion]) -> list[str]:
    """Why a discussion block of FOUND, in the report at PATH, names no run
    it can discuss, one sentence each: its protocol (relative to the
    report) is no file, or the run is no `runs/<id>/` of that protocol's
    area. Exact."""
    gaps: list[str] = []
    for d in found:
        protocol = (path.parent / d.protocol).resolve()
        at = f"line {d.first}: the discussion of run {d.run_id}"
        if not protocol.is_file():
            gaps.append(f"{at} names {d.protocol}, and there is no such protocol")
        elif not run_path(protocol.parent, d.run_id).is_dir():
            gaps.append(
                f"{at}: {d.protocol}'s area has no runs/{d.run_id}/ — a "
                f"discussion names a run of its protocol's area"
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
    gate's state holds it) owes: per protocol its discussion blocks name,
    a review of exactly this state — the inputs the reviewer reads
    (`report_review_inputs.review_pieces`), the report and the protocol as the
    state holds them — that names no claim (`report_reviews.standing`).
    A BLOCKER per protocol without one, naming the command, the claims of
    this state, or what changed since the last review. Guaranteed: the
    records, their binding and their claim count are read exactly; whether
    a claim is right stays the reviewer's judgement. A discussion whose
    protocol or run is missing owes none here (`discussion_sources` names
    it). STAGED (the pre-commit): every input comes from the state the
    commit carries — the report and protocol from the index, and the
    area's tree must equal the index (its runs' metrics, audit records and
    review records are read from the tree), else a blocker; a review
    counts only when the index holds its record."""
    out: list[GateFinding] = []
    by_protocol: dict[Path, list[report_blocks.Discussion]] = {}
    for d in discussed:
        by_protocol.setdefault((path.parent / d.protocol).resolve(), []).append(d)
    for protocol, mine in by_protocol.items():
        area = protocol.parent
        protocol_text = sources.texts.get(protocol)
        if protocol_text is None or not all(
            run_path(area, d.run_id).is_dir() for d in mine
        ):
            continue
        command = f"`{report_review_command(area, path, protocol)}`"
        if staged:
            # the review reads the area's files (runs' metrics, audit records,
            # its own records) from the tree; the commit carries the index —
            # a release on bytes the commit does not hold is none
            differs = tree_differs(sources.repo, area)
            if differs:
                out.append(
                    GateFinding(
                        BLOCKER,
                        f"{rel}: its report review reads "
                        f"{shown(area, sources.repo)}, whose working tree differs "
                        f"from the index ({', '.join(differs)}) — the commit would "
                        f"not hold what the review saw; stage these too, or stash "
                        f"them",
                        evidence_kind=GUARANTEED,
                    )
                )
                continue
        try:
            pieces = review_pieces(area, path, text, protocol, protocol_text, mine)
            whole, parts = report_reviews.fingerprint(pieces)
            report_key, protocol_key = review_keys(area, path, protocol)
            found = report_reviews.area_report_reviews(area)
            if staged:
                carried = set(indexed_files(sources.repo))
                found = [r for r in found if r.path.resolve() in carried]
            stands = report_reviews.standing(found, report_key, protocol_key, whole)
        except (
            AuditError,
            findings.FindingsError,
            report_reviews.ReportReviewError,
            RuntimeError,
        ) as exc:
            out.append(
                GateFinding(
                    BLOCKER,
                    f"{rel}: its report review cannot be told — {exc}",
                    evidence_kind=GUARANTEED,
                )
            )
            continue
        if stands.released:
            continue
        runs_named = ", ".join(dict.fromkeys(d.run_id for d in mine))
        if stands.claims:
            out.append(
                GateFinding(
                    BLOCKER,
                    f"{rel}: the report review holds this state on the discussion "
                    f"of {runs_named} — {held_by(stands)}; change the "
                    f"report, or a source the reviewer read, so that no claim holds, "
                    f"then review that state: {command} (another draw on this state, "
                    f"`--again` included, releases nothing)",
                    evidence_kind=GUARANTEED,
                )
            )
            continue
        since = (
            f"; the last review ({stands.earlier.path.name}) read another state — "
            f"changed since: {', '.join(report_reviews.changed_parts(stands.earlier, parts))}"
            if stands.earlier is not None
            else ""
        )
        out.append(
            GateFinding(
                BLOCKER,
                f"{rel}: discusses {runs_named} as not reported and has no clean "
                f"report review of this state (one naming no claim){since} — a cold reader checks "
                f"that the report states none of their numbers as results: "
                f"{command} (one model call)",
                evidence_kind=GUARANTEED,
            )
        )
    return out


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
                GateFinding(
                    BLOCKER,
                    f"{rel}: line {d.first}: run {d.run_id} is discussed as not "
                    f"reported, but {named} declares it as its result — remove "
                    f"the discussion block; the generated result block shows the "
                    f"number",
                    evidence_kind=GUARANTEED,
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
            GateFinding(
                BLOCKER,
                f"{rel}: cites a run of a protocol whose head does not read — {exc}",
                evidence_kind=GUARANTEED,
            )
        ]
    for run_id, protocol in promoted:
        named = report_blocks.path_from_report(protocol, path)
        out.append(
            GateFinding(
                BLOCKER,
                f"{rel}: cites {run_id}, the answering run of {named}, which declares "
                f"no result — a full run's number leaves the area through "
                f"`{adopt_command(protocol, run_id)}` (it names what the "
                f"adoption still owes), then `--into {rel}` writes its block; a run "
                f"this report looks at without reporting it stands in a discussion "
                f"block: `{report_blocks.discuss_command(shown(protocol, Path.cwd()), run_id, rel)}`",
                evidence_kind=GUARANTEED,
            )
        )
    looked_at = [r for r in undeclared if r not in {r for r, _ in promoted}]
    if looked_at:
        out.append(
            GateFinding(
                WARNING,
                f"{rel}: cites {', '.join(looked_at)}, which no protocol declares as "
                f"its result — a reported number is declared by `protocol-fill "
                f"<PROTOCOL> --from-run`, and its block written by `--into {rel}`; "
                f"an exploration's run is cited, not reported",
                evidence_kind=GUARANTEED,
            )
        )
    return out


#: why a report is held though no path names it: it discusses a run of an
#: area the change touches, whose sources its review read
DISCUSSES_TOUCHED = "a report discussing a run of an area this change touches"


def discussing_reports(
    paths: list[Path], held: set[Path], repo: Path, *, staged: bool
) -> list[tuple[Path, str, str]]:
    """(path, text, why held) of every report git's index holds, not in
    HELD, with a discussion block whose protocol lies in an area PATHS
    touch (`areas_touched`): the review of such a report read that area's
    protocol, runs and audits, so a change there makes it stale though the
    report is untouched. Text as the state holds it (the index when
    STAGED; `report_entry`, through a symbolic link — `hold_report` refuses
    the link). A report whose blocks do not read is held too — the gate
    names the block. Empty outside a repository."""
    if git_root(repo) is None:
        return []
    areas = {a.resolve() for a in areas_touched(paths, repo)}
    if not areas:
        return []
    links = indexed_links(repo) if staged else None
    out: list[tuple[Path, str, str]] = []
    for full in indexed_files(repo):
        if (
            full in held
            or full.suffix != REPORT_SUFFIX
            or PROTOCOL_NAME.match(full.name)
        ):
            continue
        _, text = report_entry(repo, full, staged=staged, index_links=links)
        if text is None or report_blocks.DISCUSS_OPEN not in text:
            continue
        try:
            found = report_blocks.discussions(text)
        except report_blocks.ReportBlockError:
            out.append((full, text, DISCUSSES_TOUCHED))
            continue
        if any((full.parent / d.protocol).resolve().parent in areas for d in found):
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
                f"a committed report citing a run {', '.join(by)} newly declares "
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
