"""report_hold — the reports a change reaches and what holds them.

Which Markdown files are reports and how the gate's state reads them
(through symbolic links, tree or index: `report_entry`, `held_place`,
`refused_link`), which reports a change reaches (`report_files`,
`committed_reports`, `reached_reports`, `discussing_reports`,
`reports_citing`, `registering_protocols`), what the repo holds for them
to cite (`repo_sources`), and what holds one (`hold_report`: result blocks
owed and current, discussions, promotions, a report review owed). What
the report a protocol's head registers owes stands in `registered_report`.
`report_check` is the entry: `hold_reported` decides the order and the
conditions — the protocols first, then every report — and calls into here.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath

from labkit.checks.report_blocks import discuss_command
from labkit.formats.gate import OPEN_RULE
from labkit.formats.gate import TECHNICAL_RULE, cited_rule
from labkit.formats.gate import GUARANTEED, STATIC_EVIDENCE
from labkit.formats.runs import run_path
from labkit.formats.gate import WARNING, Findings, GateFinding, blocker
from labkit.formats import (
    attempts,
    findings,
    protocol_block,
    report_reviews,
)
from labkit.gates.ways_out import report_way_while_lost
from labkit.checks.audit_binding import (
    AuditError,
    audited_run,
)
from labkit.formats.area_state import AreaState, present_run_dirs, state_of
from labkit.formats.area_state import file_state_of
from labkit.formats import evidence
from labkit.checks import report_blocks
from labkit.checks.result_render import rendering
from labkit.checks.report_review_inputs import review_keys, review_pieces
from labkit.formats.report_reviews import held_by
from labkit.formats.repo import (
    PROTOCOL_NAME,
    REPORT_SUFFIX,
    file_text,
    git_root,
    indexed_files,
    indexed_links,
    markdown_files,
    own_path,
    path_kind,
    protocol_links,
    protocols_in,
    rel_posix,
    report_place,
    shown,
    state_text,
    status_entries,
    text_at,
    touched_paths,
    under_root,
    link_end,
    linked_file,
    state_link,
)
from labkit.formats.commands import (
    adopt_command,
    audit_command,
    into_command,
    report_review_command,
    stage_command,
)
from labkit.formats.runs import read_run_config, unreportable
from labkit.formats.scope_sha import areas_touched

LAB_003 = cited_rule("LAB-003 No run without an intent paragraph")
LAB_015 = cited_rule("LAB-015 Preflight audit before freezing")
LAB_104 = cited_rule("LAB-104 A number leaves the area only through its adoption")


def held_place(repo: Path, path: Path) -> bool:
    """Is PATH a place the gate holds a report at: inside REPO, a Markdown
    file, no protocol, under none of SKIP_DIRS (`runs/`, `data/`, …)?"""
    if not under_root(repo, path):
        return False
    rel = own_path(path).relative_to(repo.resolve())
    return report_place(PurePosixPath(rel.as_posix()))


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
        return link_target, file_text(end)
    return link_target, text_at(repo, end)


def tree_differs(repo: Path, area: Path) -> list[str]:
    """The paths under AREA whose working tree differs from the index — a
    tracked file modified or deleted and not staged, an untracked file —
    relative to REPO. Empty when the tree under AREA is what the commit
    would hold."""
    rel = rel_posix(area, repo)
    return [path for xy, path in status_entries(repo, (rel,)) if xy[1] != " "]


def staged_area_gap(repo: Path, area: Path, reads: str) -> GateFinding | None:
    """The pre-commit's BLOCKER while AREA's working tree differs from the
    index (`tree_differs`): the commit holds the index, and READS (who
    reads the tree: "the stations read", "the report review of REPORT.md
    reads") would judge bytes the commit does not hold. None when the tree
    is what the commit would hold. The one home of this hold for
    report-check's declared branch (`report_check.hold_declared`), the
    report review (`review_gap`) and `next --staged`'s row
    (`next_step._staged_area_step`), so the hold and the step agree; its
    step stages the whole area (`commands.stage_command`) — a partial staging
    takes more than the one file a reader has in mind."""
    differs = tree_differs(repo, area)
    if not differs:
        return None
    step = stage_command(area)
    return blocker(
        f"{shown(area, repo)}: the working tree differs from the index "
        f"({', '.join(differs)}) — {reads} the tree, the commit holds the index",
        fix=f"`{step}` stages the whole area ({len(differs)} file(s), listed "
        "above); stash what the commit must not hold",
        step=step,
        rule=TECHNICAL_RULE,
    )


def reports_without_block(
    repo: Path, protocol: Path, run_id: str, *, staged: bool = False
) -> list[Path]:
    """The reports of REPO, as the state holds them (`state_reports`: the
    index when STAGED, else the tree), that cite RUN_ID, the run PROTOCOL
    has adopted, and carry no result block of PROTOCOL — what the stop and
    the commit refuse (`hold_report`), found before them, so labkit-next and
    labkit-adopt name the report the hook will hold; read from the state
    the gate reads, so `next --staged` sees a report the index alone
    carries. A block that does not read counts as none."""
    out: list[Path] = []
    for path, text in state_reports(repo, staged=staged):
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
        if not held_place(root, full):
            continue  # outside the repo, or no place a report stands at
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
    protocols = protocols_in(repo, staged=staged)
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
    reaches without being changed themselves: a report committed before
    its protocol's declaration is held when the declaration is, so no
    delivered state carries a blocker no commit saw. Empty outside a
    repository."""
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
    """What the repo holds for a report to cite, as one file state holds it
    (STAGED: the index, what the commit carries; else the tree), and the
    cache of one check run: the repo's root (REPO, resolved), every run
    directory's id (KNOWN), per protocol its text (TEXTS) and the run its
    head declares (DECLARED: None for none; a head that does not read is in
    UNREADABLE with the reason instead); `held_state` and `held_evidence`
    build each area's state and audit evidence once, in STAGED's file state.

    Two forms, named by their constructors: `repo_sources` reads every
    protocol of the repo (KNOWN through `area_state.present_run_dirs`, the
    reader `held_state`'s runs come from too, so the two agree); `blank`
    carries the file state, the texts given and the cache alone — KNOWN,
    DECLARED and UNREADABLE empty — for a hold that checks no report's
    citations. The file state a hold judges is STAGED here, never a second
    flag beside it."""

    repo: Path
    known: set[str]
    texts: dict[Path, str]
    declared: dict[Path, str | None]
    unreadable: dict[Path, str]
    staged: bool = False  # the file state the sources were read from
    _states: dict[Path, AreaState] = field(
        default_factory=dict, repr=False, compare=False
    )
    _evidence: dict[Path, evidence.AreaEvidence] = field(
        default_factory=dict, repr=False, compare=False
    )

    def declaring(self, run_id: str) -> list[Path]:
        """The protocols declaring RUN_ID as their result."""
        return [p for p, r in self.declared.items() if r == run_id]

    @classmethod
    def blank(
        cls,
        repo: Path,
        *,
        staged: bool,
        texts: Mapping[Path, str] | None = None,
        states: Mapping[Path, AreaState] | None = None,
        held: Mapping[Path, evidence.AreaEvidence] | None = None,
    ) -> "Sources":
        """Sources of REPO in STAGED's file state with TEXTS and an empty
        KNOWN, DECLARED and UNREADABLE; STATES and HELD, by area, are the
        states and evidence a caller built already for this check run — the
        cache's from the start, so nothing is read twice."""
        out = cls(repo.resolve(), set(), dict(texts or {}), {}, {}, staged)
        out._states.update({a.resolve(): s for a, s in (states or {}).items()})
        out._evidence.update({a.resolve(): e for a, e in (held or {}).items()})
        return out

    def held_state(self, area: Path) -> AreaState:
        """AREA's state as the sources' file state holds it
        (`area_state.state_of`), built once per area for the whole hold:
        the one build the protocol's chain and every report's checks of
        this check run read."""
        key = area.resolve()
        if key not in self._states:
            self._states[key] = state_of(
                key, file_state=file_state_of(staged=self.staged)
            )
        return self._states[key]

    def held_evidence(self, area: Path) -> evidence.AreaEvidence:
        """AREA's audit evidence in the sources' file state
        (`evidence.read_evidence`), read once per area for the whole hold."""
        key = area.resolve()
        if key not in self._evidence:
            self._evidence[key] = evidence.read_evidence(key, staged=self.staged)
        return self._evidence[key]


def repo_sources(repo: Path, *, staged: bool) -> Sources:
    """The runs, texts and declarations of every protocol of REPO — the
    index's protocols, texts and runs when STAGED (what the commit
    carries), the tree's otherwise. KNOWN is read cheaply for every area
    (`area_state.present_run_dirs`); the areas' states build lazily, for
    the areas a report touches (`held_state`)."""
    protocols = protocols_in(repo, staged=staged)
    out = Sources.blank(repo, staged=staged)
    out.unreadable.update(protocol_links(repo, protocols, staged=staged))
    file_state = file_state_of(staged=staged)
    for p in protocols:
        out.known.update(
            rd.dir.name
            for rd in present_run_dirs(p.parent, repo=repo, file_state=file_state)
        )
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
                None,
                None,
                f"its head does not read: {sources.unreadable[p]}",
                TECHNICAL_RULE,
            )
        # LAB-104 A number leaves the area only through its adoption: "a
        # report shows a run's number only as the result a protocol adopted"
        elif p not in sources.texts:
            out[b.protocol] = report_blocks.BlockSource(
                None, None, "no protocol of the repo there", LAB_104
            )
        elif (run_id := sources.declared[p]) is None:
            out[b.protocol] = report_blocks.BlockSource(
                None, None, "it has adopted no result", LAB_104
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
    owed = report_blocks.blocks_owed(
        cited,
        declaring,
        # each block's protocol resolved and named as the owed ones are:
        # compared as written, one block could read as missing and present
        # at once
        {
            report_blocks.path_from_report(block_protocol(report, b), report)
            for b in found
        },
    )
    out: list[GateFinding] = []
    for n, run_id, protocol in owed:
        into = into_command(named[protocol], report)
        out.append(
            blocker(
                f"line {n}: cites run {run_id}, the adopted result of {protocol}, "
                f"without its generated block — the number a report shows of a "
                f"adopted result is the generated one",
                fix=f"`{into}` writes it",
                step=into,
                rule=LAB_104,
            )
        )
    return out


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
    AuditError on a head whose id does not read.
    SOURCES give each area's state (`Sources.held_state`)."""
    out: list[tuple[str, Path]] = []
    for protocol, declared in sources.declared.items():
        if declared is not None:
            continue
        area = protocol.parent.resolve()
        state = sources.held_state(area)
        present = {rd.dir.name for rd in state.runs}
        mine = [r for r in run_ids if r in present]
        if not mine:
            continue
        run, _ = audited_run(state, protocol, sources.texts[protocol])
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
    tell: Callable[[str], None] = print,
) -> int:
    """Hold one report, every line through TELL.

    First: a report that is a symbolic link in the
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
    staged = sources.staged
    rel = rel_posix(path, repo)
    tell(f"═══ report-check {rel} ({held_as}) ═══")
    out = Findings(tell)
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
            rule=report_blocks.unread_rule(exc),
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
    structured = report_blocks.structured_lines(found, discussed)
    out.take_all(at_report(report_blocks.cited_gaps(cited, sources.known, structured)))
    out.take_all(at_report(owed_blocks(path, text, found, sources)))
    out.take_all(at_report(report_blocks.discussion_gaps(discussed)))
    out.take_all(at_report(discussion_sources(path, discussed, sources)))
    out.take_all(report_review_owed(path, rel, text, discussed, sources))
    report_hints(out, rel, text, discussed)
    for line in replacement_hints(path, rel, text, repo, sources):
        out.warn(line, evidence_kind=STATIC_EVIDENCE, rule=LAB_003)
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
        rule=TECHNICAL_RULE,
    )


def discussion_sources(
    path: Path, found: list[report_blocks.Discussion], sources: Sources
) -> list[GateFinding]:
    """Why a discussion block of FOUND, in the report at PATH, names no run
    it can discuss, one sentence each: its protocol (relative to the
    report) is no file, or the run is no `runs/<id>/` of that protocol's
    area — in the file state SOURCES hold (the index at the commit, else
    the tree; `Sources.held_state`). Exact."""
    gaps: list[GateFinding] = []
    again = f"write the block again with `{discuss_command('<PROTOCOL>', '<run>', '<FILE>', '…')}`"
    for d in found:
        protocol = (path.parent / d.protocol).resolve()
        at = f"line {d.first}: the discussion of run {d.run_id}"
        area = protocol.parent
        state = sources.held_state(area) if path_kind(area) == "dir" else None
        if state is None or protocol not in state.protocols:
            gaps.append(
                blocker(
                    f"{at} names {d.protocol}, and there is no such protocol",
                    fix=f"{again}, the protocol named from the report",
                    rule=TECHNICAL_RULE,
                )
            )
        elif d.run_id not in {rd.dir.name for rd in state.runs}:
            gaps.append(
                blocker(
                    f"{at}: {d.protocol}'s area has no runs/{d.run_id}/ — a "
                    f"discussion names a run of its protocol's area",
                    fix=f"{again}, naming a run of that area",
                    rule=TECHNICAL_RULE,
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
    record binds it to (`protocol.id`), in the file state SOURCES hold. A
    run whose record does not read belongs to no protocol here —
    `Measured.runs` counts it for every protocol, since it may have
    measured any."""
    out: dict[str, Path] = {}
    for p, text in sources.texts.items():
        pid = protocol_block.id_of(text)
        for rd in sources.held_state(p.parent).runs:
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
            rule=LAB_104,
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
            rule=LAB_104,
        )
        for n, numbers in beside:
            out.note(f"    {rel}:{n}: {', '.join(numbers)}")


def report_review_owed(
    path: Path,
    rel: str,
    text: str,
    discussed: list[report_blocks.Discussion],
    sources: Sources,
) -> list[GateFinding]:
    """The report review the report at PATH (REL to the repo, TEXT as the
    gate's state holds it) owes for its discussion blocks (DISCUSSED): per
    protocol they name, a BLOCKER when no review of exactly this state
    names no claim (`review_gap`). A protocol whose head registers this
    report is left out here — its own hold owes the review of the whole
    report once the result or handover block stands (`report_owed`), and
    one blocker per protocol is enough. A discussion whose protocol or run
    is missing owes none here (`discussion_sources` names it)."""
    staged = sources.staged
    out: list[GateFinding] = []
    by_protocol: dict[Path, list[report_blocks.Discussion]] = {}
    for d in discussed:
        by_protocol.setdefault((path.parent / d.protocol).resolve(), []).append(d)
    registering = set(registering_protocols([path], sources.repo, staged=staged))
    for protocol, mine in by_protocol.items():
        protocol_text = sources.texts.get(protocol)
        if protocol in registering or protocol_text is None:
            continue
        area_state = sources.held_state(protocol.parent)
        held_runs = {rd.dir.name for rd in area_state.runs}
        if not all(d.run_id in held_runs for d in mine):
            continue
        runs_named = ", ".join(dict.fromkeys(d.run_id for d in mine))
        gap = review_gap(
            path,
            rel,
            text,
            protocol,
            protocol_text,
            mine,
            f"discusses {runs_named} as not reported",
            sources,
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
    owed_because: str,
    sources: Sources,
) -> GateFinding | None:
    """The BLOCKER of the report at PATH (REL to REPO, TEXT as the gate's
    state holds it) under PROTOCOL (its PROTOCOL_TEXT, its DISCUSSED
    blocks) when no report review of exactly this state names no claim —
    the inputs the reviewer reads (`report_review_inputs.review_pieces`),
    the report and the protocol as the state holds them
    (`report_reviews.standing`); None when one does. OWED_BECAUSE says why the
    report owes it, for the sentence. Guaranteed: the records, their
    binding and their claim count are read exactly; whether a claim is
    right stays the reviewer's judgement. SOURCES is the check run's cache:
    the repo, the file state and the area's state and audit evidence, read
    once. Staged (the pre-commit): every input comes from the state the
    commit carries — the report and protocol from the index, the audit
    records and reviews from the index's evidence, and the area's tree
    must equal the index (the runs' metrics and the review's failed
    attempts are read from the tree), else a blocker; a review counts only
    when the index holds its record."""
    area = protocol.parent
    repo, staged = sources.repo, sources.staged
    state, held = sources.held_state(area), sources.held_evidence(area)
    command = f"`{report_review_command(area, path, protocol)}`"
    if staged:
        # the review reads the area's files (runs' metrics, audit records,
        # its own records) from the tree; the commit carries the index —
        # a release on bytes the commit does not hold is none
        gap = staged_area_gap(repo, area, f"the report review of {rel} reads")
        if gap is not None:
            return gap
    try:
        pieces = review_pieces(
            area, path, text, protocol, protocol_text, discussed, state, held
        )
        whole, parts = review_fingerprint(pieces)
        report_key, protocol_key = review_keys(area, path, protocol)
        if held.report_reviews_unread:
            raise report_reviews.ReportReviewError(held.report_reviews_unread)
        found = list(held.report_reviews)
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
            rule=TECHNICAL_RULE,
        )
    if stands.released:
        return None
    # lost audit evidence, then claims, then no clean review (`review_hold`)
    return review_hold(rel, protocol, owed_because, stands, parts, command, held)


@dataclass(frozen=True)
class LostEvidence:
    """Why no audit or review can start on an area now (CAUSE,
    `attempts.gone_line`) and the way out a report citing its runs has then
    (FIX, `ways_out.report_way_while_lost`)."""

    cause: str
    fix: str


def lost_evidence(protocol: Path, held: evidence.AreaEvidence) -> LostEvidence | None:
    """While the audit evidence of PROTOCOL's area is gone (HELD, the
    area's evidence the caller read once: its `gaps`), the cause and the
    way out a report citing its runs has — `attempts.begin` refuses every
    audit and review then, so neither an adoption nor a discussion's
    review can pass; None while the evidence stands. The one selection the
    report holds, `--report-review` and protocol-fill's adoption and
    handover read."""
    area = protocol.parent
    gaps = list(held.gaps)
    if not gaps:
        return None
    return LostEvidence(
        attempts.gone_line(gaps),
        report_way_while_lost(
            audit_command(area, "--findings", protocol=protocol).line
        ),
    )


def review_hold(
    rel: str,
    protocol: Path,
    owed_because: str,
    stands: report_reviews.Standing,
    parts: dict[str, str],
    command: str,
    held: evidence.AreaEvidence,
) -> GateFinding:
    """The BLOCKER of a report no review releases: first, while the area's
    audit evidence is gone, that no review can run and the way out that
    works (`lost_evidence` — before any claims of this state, since no
    review can answer them then); else the claims that hold this state
    (LAB_015: no further draw releases it); else that it has no clean
    review (LAB_104). REL is the report, HELD_FOR why it
    owes a review of PROTOCOL's area (its discussion, or the head
    registering it), STANDS where the report stands, PARTS the state's
    fingerprint parts, COMMAND the review to run.
    HELD is the area's audit evidence, read once by the caller."""
    # first: under a handover for a lost record the review `--discuss`
    # owes is refused, and this way out is the one that works
    lost = lost_evidence(protocol, held)
    if lost is not None:
        return blocker(
            f"{rel}: {owed_because} and has no clean report review of this "
            f"state — and none can run: {lost.cause}",
            fix=lost.fix,
            rule=TECHNICAL_RULE,
        )
    if stands.claims:
        return blocker(
            f"{rel}: the report review holds this state ({owed_because}) — "
            f"{held_by(stands)}",
            fix=f"change the report, or a source the reviewer read, so that "
            f"no claim holds, then review that state: {command} (another "
            f"draw on this state, `--again` included, releases nothing)",
            # LAB_015's text states it: a claim the report review names
            # holds until the report or what it cites changes
            rule=LAB_015,
        )
    since = (
        f"; the last review ({stands.earlier.path.name}) read another state — "
        f"changed since: {', '.join(report_reviews.changed_parts(stands.earlier, parts))}"
        if stands.earlier is not None
        else ""
    )
    return blocker(
        f"{rel}: {owed_because} and has no clean report review of this state "
        f"(one naming no claim){since} — a cold reader checks that it "
        f"presents nothing as a result the protocol has not adopted",
        fix=f"{command} (one model call) — last, after the report's text and "
        f"its blocks are final: a change after it owes another",
        rule=LAB_104,
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
                    rule=OPEN_RULE,
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
                rule=TECHNICAL_RULE,
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
                    rule=TECHNICAL_RULE,
                )
            )
            continue
        # adoption and discussion both owe an audit or a review, which no
        # lost evidence lets start: then the way out is the restore or the
        # removal, in place of the blocker below
        lost = lost_evidence(protocol, sources.held_evidence(protocol.parent))
        if lost is not None:
            out.append(
                blocker(
                    f"{rel}: cites {run_id}, the answering run of {named}, which "
                    f"has adopted no result — and neither its adoption nor a "
                    f"discussion can pass: {lost.cause}",
                    fix=lost.fix,
                    rule=TECHNICAL_RULE,
                )
            )
            continue
        out.append(
            blocker(
                f"{rel}: cites {run_id}, the answering run of {named}, which has adopted "
                f"no result",
                step=adopt_command(protocol, run_id),
                fix=f"a full run's number leaves the area through "
                f"`{adopt_command(protocol, run_id)}` (it names what the "
                f"adoption still owes), then `--into {rel}` writes its block; a run "
                f"this report looks at without reporting it stands in a discussion "
                f"block: `{report_blocks.discuss_command(shown(protocol, Path.cwd()), run_id, rel)}`",
                rule=LAB_104,
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
                rule=LAB_104,
            )
        )
    return out


def adoption_unstaged(protocol: Path, run_id: str, sources: Sources) -> bool:
    """Does the working tree's PROTOCOL declare RUN_ID while SOURCES — the
    index, when the gate runs staged — do not? Then the adoption was written
    and not staged, and the hold names that instead of "declares no result",
    which would read as a rejected review's effect.
    False when SOURCES declare it, when the tree's protocol is gone or does
    not read, or when the gate reads the tree itself."""
    if sources.declared.get(protocol) == run_id:
        return False
    try:
        text = state_text(sources.repo, protocol, staged=False)
        return text is not None and protocol_block.declared_run(text) == run_id
    except (OSError, UnicodeError, ValueError, protocol_block.BlockError):
        return False


#: why a report is held though no path names it: it discusses a run of an
#: area the change touches, whose sources its review read
DISCUSSES_TOUCHED = "a report discussing a run of an area this change touches"


def state_reports(repo: Path, *, staged: bool) -> list[tuple[Path, str]]:
    """(path, text) of every Markdown file at a held place (`held_place`:
    no protocol, not under SKIP_DIRS) as the state holds it: in the tree
    every one under REPO (a walk, no git needed), in the index every file
    it holds (STAGED; [] outside a repository), each read through
    `report_entry`; one the state holds no text for is left out. The one
    scan of the reports a state holds, behind `discussing_candidates` and
    `reports_without_block`. Raises RuntimeError when git fails on the
    index."""
    root = repo.resolve()
    if staged:
        if git_root(repo) is None:
            return []
        candidates = [own_path(c) for c in indexed_files(repo)]
        links = indexed_links(repo)
    else:
        candidates = markdown_files(root)
        links = None
    out: list[tuple[Path, str]] = []
    for full in dict.fromkeys(candidates):
        if not held_place(repo, full):
            continue
        _, text = report_entry(repo, full, staged=staged, index_links=links)
        if text is not None:
            out.append((full, text))
    return out


def discussing_candidates(
    repo: Path, *, staged: bool
) -> list[tuple[Path, str, list[report_blocks.Discussion] | None]]:
    """(path, text, its discussion blocks — None when they do not read) of
    every report of REPO that discusses a run, as the state holds it
    (`state_reports`). The one scan behind `discussing_reports` and
    `discussion_review_findings`. Raises RuntimeError when git fails on
    the index."""
    out: list[tuple[Path, str, list[report_blocks.Discussion] | None]] = []
    for full, text in state_reports(repo, staged=staged):
        if report_blocks.DISCUSS_OPEN not in text:
            continue
        try:
            out.append((full, text, report_blocks.discussions(text)))
        except report_blocks.ReportBlockError:
            out.append((full, text, None))
    return out


def review_fingerprint(pieces: list[tuple[str, str]]) -> tuple[str, dict[str, str]]:
    """The fingerprint of a report review's state (`report_reviews.fingerprint`):
    the PIECES the reviewer read (`review_pieces`) and the brief it read
    them under (`audit_prompt.review_brief`). The one fingerprint the
    review writes and the gate compares. The brief is part of it, so a
    review that flagged under a rule since corrected does not hold the
    report, and `--report-review` may draw again."""
    from labkit.gates.audit_prompt import review_brief

    return report_reviews.fingerprint([*pieces, *review_brief()])


def discussion_review_findings(
    protocol: Path,
    text: str,
    repo: Path,
    *,
    staged: bool,
    state: AreaState,
    held: evidence.AreaEvidence,
) -> list[GateFinding]:
    """The report reviews the reports of REPO owe for discussing a run of
    PROTOCOL (its TEXT as the state holds it): the findings `hold_report`
    holds each such report with (`report_review_owed`), read here per
    protocol so that `report_check.chain_gaps` — and through it
    `report-check AREA` and `labkit-next` — holds and names exactly what
    the stop and the commit hold (`report_check.hold_reported`), one
    function for both. Only the discussion blocks naming PROTOCOL count; a
    report whose blocks do not read is left to its own hold (`hold_report`
    names the block). STAGED: the index's files and texts, [] outside a
    repository. STATE and HELD are the area's state and evidence the chain
    built once; every report's hold reads them (`Sources.blank`). Raises
    RuntimeError when git fails on the index."""
    root = repo.resolve()
    target = protocol.resolve()
    sources = Sources.blank(
        root,
        staged=staged,
        texts={target: text},
        states={target.parent: state},
        held={target.parent: held},
    )
    out: list[GateFinding] = []
    for full, report_text, found in discussing_candidates(repo, staged=staged):
        if found is None:
            continue
        mine = [d for d in found if (full.parent / d.protocol).resolve() == target]
        if not mine:
            continue
        rel = rel_posix(full, root)
        out += report_review_owed(full, rel, report_text, mine, sources)
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
        {a.resolve() for a in areas_touched(paths, repo, staged=staged)}
        if git_root(repo)
        else set()
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
