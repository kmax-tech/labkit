"""report-check — the gate after the last step, before a number leaves the area.

    report-check <AREA> [--protocol PROTOCOL-*.md]
    report-check --if-reported [--staged] PATH ...  every protocol of an area
                                                    a path touches whose head
                                                    declares a result, and every
                                                    report among PATHS citing a
                                                    run (the stop hook; with
                                                    --staged the pre-commit: the
                                                    head and the report as the
                                                    index holds them, and the
                                                    area's tree must equal the
                                                    index)

Exit codes: 0 clean, 1 a blocker, 2 usage error.

`finalize` holds the run before the number is written back and comes
before the analysis audit; report-check comes last and holds the whole
chain, at every cost tier (why each station holds what it holds:
docs/notes/2026-10-19-hooks-and-report-check.md):

  0. protocol      the named PROTOCOL-*.md or the area's only one
  1. frozen        at `minutes`/`hours`: `frozen = true`, and the freeze
                   holds: no must gap `protocol-check` names
                   (`check_fields`) — the [[promise]] tables written, not
                   the stamp's `<…>` sentences. At `cost = "seconds"` no
                   freeze and no preflight audit are owed
                   (LAB-017 The number of audits follows the cost tier), so
                   this station is skipped and says so
  2. finalize      `finalize_area` clean — its blockers are named here —
                   so the answering run is bound to this protocol and the
                   head declares it; and that run is a full run: `run_kind='measurement'`,
                   not acknowledged unfrozen (`runs.unreportable`) — a
                   reported number owes a full run (frozen at
                   minutes/hours); a probe's or an acknowledged run's number
                   cannot be reported
  3. analysis audit  a record `audits/*-analysis.toml` whose `scope_sha` is
                   the area's stamp now, whose `block_sha` is the promise
                   block now and whose `run_id` is the answering run, every
                   finding decided (`findings.audit_coverage`) — code or
                   promises changed after the analysis audit, or a later
                   run, owe a new one (LAB-050 Analysis audit before
                   reporting; at seconds the lane's one audit,
                   LAB-017 The number of audits follows the cost tier)
  4. the check     `scripts/02_analyze.py --check` exits 0 under the repo's
                   interpreter: the rows recompute to the run's metrics and
                   the note it names carries every number and the run_id
                   (`recheck.holds`; LAB-041 Generate numbers, don't retype
                   them). One command for every skeleton: the count stamps
                   its own `02_analyze.py` too

Every station runs; the blockers are summed at the end. It reads and runs,
never writes. The stations read one context (`Checked`, built once by
`checked`): the protocol text as the named file state holds it, its head,
the run the head declares, and the answering run chosen once
(`audit_binding.audited_run`, through `answering_run.bound_answering_run`, the one choice
every gate holds a protocol to) — no station reads the file or chooses the
run for itself, and the output names the state that was held.

`--if-reported` is the gate the agent cannot choose: `claude-hook stop`
runs it on every changed path, the stamped pre-commit on every staged one,
and selects every protocol of every area one of those paths lies in
(`affected_protocols`). It checks those whose head declares a result
(`[result] run`, `protocol_block.declared_run`), written by
`protocol-fill --from-run`. The area, not the protocol
alone: a script edited after the answer was written back changes what the
analysis audit saw and what `--check` recomputes. A protocol declaring no
result owes nothing here: an exploration ends with no reported result,
probes or not; a `[result]` that does not read is held and blocks.

A report outside the protocol — a Markdown file among the paths that
cites a run, not a protocol, not under `runs/` or `data/` (`report_files`)
— is held too (`hold_report`): each generated result block equals what the
protocol it names declares now — the block's run — and renders for it
(`report_blocks.block_gaps`, written by
`protocol-fill --into`), each token that reads as a run id names a run of
the repo (`report_blocks.cited_gaps`) — blockers; the protocol declaring a
cited run joins the protocols the stations hold (`held_by_reports`); a
number outside every block is a warning, no source being assigned to it
(`report_blocks.unsourced_numbers`, static evidence). Only the paths
given: an old citation in a file nobody touched reopens nothing.

`--staged` is the pre-commit's form. The commit holds the index, the
stations read the working tree: so the declaration is read from the index
(`index_text` — an answer only the tree carries is not in the commit), and
an area whose tree differs from the index (`tree_differs`: a file modified
and not staged, or untracked) is a blocker before any station runs, since
the check would judge a state the commit does not hold.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.gate import BLOCKER, WARNING, Findings, GateFinding
from labkit.formats.answering_run import first_measurement
from labkit.formats.protocol_history import registration_in_commit
from labkit.formats import console, findings, protocol_block, reviews
from labkit.checks.audit_binding import (
    AuditError,
    analysis_now,
    audited_run,
    covering_analysis,
)
from labkit.checks import report_blocks
from labkit.checks.result_render import render_gaps, rendering
from labkit.gates.finalize import finalize_area
from labkit.gates.preflight import area_test_python
from labkit.formats.protocol_check import check_fields
from labkit.formats.repo import (
    area_path,
    area_protocols,
    choose_protocol,
    git_root,
    git_run,
    indexed_protocols,
    layout_root,
    no_such_area,
    PROTOCOL_NAME,
    repo_protocols,
    SKIP_DIRS,
    status_entries,
)
from labkit.formats.runs import read_run_config, recorded_commit, unreportable
from labkit.formats.scope_sha import areas_touched
from labkit.formats.standard_contract import (
    ANALYSIS_AUDIT,
    CHECK_SCRIPT,
    Lane,
    check_command,
    lane,
)

#: which file state the declaration (the answer line) is read from — named
#: in the output, so a reader knows what was held. The stations read the
#: working tree in every case; the caller makes the tree that state: the
#: pre-commit holds the area's tree equal to the index (`tree_differs`), the
#: adoption writes the proposal into the tree and puts it back on refusal
#: (`protocol_fill.adopt`)
TREE = "working tree"
INDEX = "index"
PROPOSED = "proposed protocol"


@dataclass(frozen=True)
class Checked:
    """The context of one check, built once (`checked`) and read by every
    station: one protocol text, one head, one answering run, one named file
    state — so the declaration, the audit record and the check are held to
    the same run and the same text, and no station chooses for itself.

    Attributes:
        area: The area, resolved.
        repo: Where the area's layout starts (`repo.layout_root`).
        protocol: The protocol file.
        text: The protocol as STATE holds it — the declaration is read here.
        head: Its TOML head.
        state: TREE, INDEX or PROPOSED.
        declared: The run the head declares as the reported result
            (`protocol_block.declared_run`, `[result] run`), None for an
            exploration — or for a `[result]` that does not read, which
            `declaration_gap` then names (a blocker: the commit must not
            carry it).
        declaration_gap: Why the declaration does not read, or None.
        run: The answering run (`audit_binding.audited_run`, through
            `answering_run.bound_answering_run`: the one choice every gate holds the
            protocol to), or None.
        why: Why there is no answering run, when RUN is None.
    """

    area: Path
    repo: Path
    protocol: Path
    text: str
    head: protocol_block.Head
    state: str
    declared: str | None
    declaration_gap: str | None
    run: Path | None
    why: str


def checked(
    area: Path, protocol: Path, *, state: str = TREE, text: str | None = None
) -> Checked:
    """The context of one check: TEXT is the protocol as STATE holds it
    (the working tree when None). Raises `protocol_block.BlockError` on an
    unreadable head, `AuditError` out of the run choice."""
    if text is None:
        text = protocol.read_text(encoding="utf-8")
    head = protocol_block.head(text)
    declared, declaration_gap = _declaration(text)
    run, why = audited_run(area, protocol, text)
    return Checked(
        area=area.resolve(),
        repo=layout_root(area),
        protocol=protocol,
        text=text,
        head=head,
        state=state,
        declared=declared,
        declaration_gap=declaration_gap,
        run=run,
        why=why,
    )


#: how long `--check` may take inside the gate (audit 2026-10-15: no limit)
CHECK_TIMEOUT_S = 300.0


def check_analysis_script(area: Path, repo: Path) -> str | None:
    """Why the area's check (`standard_contract.check_command`: the analysis
    script's `--check`, stamped by every skeleton) does not pass, or None:
    no script, or a nonzero exit with the last lines it printed."""
    script = CHECK_SCRIPT
    if not (area / script).is_file():
        return (
            f"no {script} — the check that holds the note to the run is owed; "
            f"every skeleton stamps it (an area stamped at seconds before 0.100.0 "
            f"carried the check inside 01_measure.py: stamp "
            f"labkit/templates/analyze-quick-script.py.template beside it)"
        )
    try:
        r = subprocess.run(
            [area_test_python(repo), *check_command(area)],
            cwd=repo,
            capture_output=True,
            text=True,
            errors="replace",  # the tail is quoted, not parsed: a byte no
            # codec reads must not raise out of the gate (audit 2026-10-19)
            timeout=CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"{script} --check did not finish in {CHECK_TIMEOUT_S:g} s"
    if r.returncode == 0:
        return None
    tail = (r.stderr.strip() or r.stdout.strip() or "no output").splitlines()[-3:]
    return f"{script} --check exits {r.returncode}: " + " | ".join(tail)


def _declaration(text: str) -> tuple[str | None, str | None]:
    """(the declared run, None) or (None, why the `[result]` table does not read)."""
    try:
        return protocol_block.declared_run(text), None
    except protocol_block.BlockError as exc:
        return None, str(exc)


def freeze_gaps(ctx: Checked) -> list[str]:
    """Station 1: why the freeze does not hold — the flag unset, or a must
    gap protocol-check names (the stamp's `<…>` promise sentences among them)."""
    gaps = (
        []
        if ctx.head.frozen
        else ["not `frozen = true` — a reported number owes the freeze"]
    )
    report = check_fields(ctx.text)
    gaps += report.missing_must
    # a must field still holding its `<…>` placeholder passed here while
    # protocol-check and preflight refused it (audit 2026-10-15)
    gaps += [f"line {n}: {label} still a placeholder" for n, label in report.must_holes]
    return [f"{ctx.protocol.name}: {g}" for g in gaps]


def registration_gaps(ctx: Checked) -> list[GateFinding]:
    """Station 1 where the lane owes the registration instead of the freeze
    (seconds): the registration stood in the protocol as committed at the
    first measurement — the oldest full run bound to this protocol
    (`answering_run.first_measurement`) and the commit its record names
    (`runs.recorded_commit`). Blockers: the run recorded no commit, the
    commit does not hold the protocol (nothing stood before the number),
    the fields the lane owes were not written there
    (`protocol_history.registration_in_commit`). runlog's start gate reads
    the tree, which a line written a minute before the run passes; what
    stood before the number is what the commit holds. Outside a repository
    a warning, as the provenance station's (`run_record_check.provenance_findings`).
    Empty without a first measurement (finalize names the missing run) and
    without a stamped id. Why (labkit-paper area 09, fifth haiku round,
    2026-10-22): none of the three labkit agents had committed criterion
    and admissibility condition before the first measurement."""
    if ctx.head.id is None:
        return []
    first = first_measurement(ctx.area, ctx.head.id)
    if first is None:
        return []
    cfg = read_run_config(first)
    if cfg is None:
        return [GateFinding(BLOCKER, f"{first.name}: no config.json — not a run")]
    at = f"the first measurement {first.name}"
    if git_root(ctx.protocol) is None:
        return [
            GateFinding(
                WARNING,
                f"not a git repository — the registration cannot be held to the "
                f"commit of {at}",
            )
        ]
    commit = recorded_commit(cfg)
    if commit is None:
        return [
            GateFinding(
                BLOCKER,
                f"{at} recorded no commit ({cfg.git!r}) — the registration cannot be "
                f"held to what stood before the number (LAB-003 No run without an "
                f"intent paragraph)",
            )
        ]
    missing = registration_in_commit(ctx.protocol, commit)
    if missing is None:
        return [
            GateFinding(
                BLOCKER,
                f"{ctx.protocol.name} was not committed at {at} ({commit}) — nothing "
                f"stood before the number; the registration is what the commit of "
                f"the first measurement holds (LAB-003 No run without an intent "
                f"paragraph)",
            )
        ]
    if missing:
        return [
            GateFinding(
                BLOCKER,
                f"the registration as committed at {at} ({commit}) lacks "
                f"{', '.join(missing)} — the registration is what the commit of "
                f"the first measurement holds, not what the tree says now "
                f"(LAB-003 No run without an intent paragraph)",
            )
        ]
    return []


def analysis_audit_gap(ctx: Checked) -> str | None:
    """Station 3: why no decided analysis record covers the code, the promise
    block, the answering run and what the audit was shown of it as they are
    now, or None. Without an answering run there is nothing the audit could
    be held to."""
    if ctx.run is None:
        return f"no answering run to hold it to — {ctx.why}"
    try:
        sha, block_sha, run_id, shown_sha = analysis_now(ctx.area, ctx.text, ctx.run)
        return findings.audit_coverage(
            ctx.area, sha, ANALYSIS_AUDIT, block_sha, run_id, shown_sha
        )
    except AuditError as exc:  # a registered output is gone
        return f"the analysis audit cannot be held to the run: {exc}"
    except (FileNotFoundError, ValueError) as exc:
        # ValueError: nothing to stamp, a findings file or the promise block
        # unreadable (FindingsError, PromiseError)
        return f"the analysis audit cannot be held to the area: {exc}"


def limit_gaps(ctx: Checked) -> list[str]:
    """Station 3, the limits: every accepted BLOCKER of the covering analysis
    records has its effect decided, and the result section says exactly
    what those records and the run render (`result_render.render_gaps`):
    the Recorded results line with its note, one Limit line per decided limit, none
    that no record decides. Exact in what it holds — equality with the
    rendering — and silent on whether a limit is enough: that is the
    audit's question. Empty when no covering record exists
    (`analysis_audit_gap` names that), and the rendering is not owed while
    the head declares no result."""
    if ctx.run is None:
        return []
    try:
        records = covering_analysis(ctx.area, ctx.text, ctx.run)
    except (AuditError, FileNotFoundError, ValueError):
        return []
    gaps: list[str] = []
    for r in records:
        for n, f in r.limits():
            if not f.effect:
                gaps.append(
                    f"{findings.limit_label(r, n)}: an accepted BLOCKER owes its effect "
                    f'on the verdicts — `labkit-audit <area> --decide {n} accepted "REASON" '
                    f'--effect stands|"<ID> not assessable" --record {r.path.name}`'
                )
    if ctx.declared is None:
        return gaps  # nothing reported: the result section is not owed yet
    try:
        expected = rendering(ctx.area, ctx.text, ctx.run)
    except (OSError, ValueError) as exc:
        return gaps + [f"the result cannot be rendered from {ctx.run.name}: {exc}"]
    return gaps + render_gaps(ctx.text, expected)


def review_findings(ctx: Checked) -> list[GateFinding]:
    """Station 3, the decisions: every `stands` among the limits of the
    covering analysis records is upheld by a decision review
    (`reviews.upholding`: a review of that record, its code and its run as
    shown, of the decision as it stands now, saying `upheld`). A WARNING
    per decision no review upholds, with its state — an exploration of the
    check (TODO 2026-10-22: the fifth round's decisions are replayed
    first; a blocker afterwards). Empty when no record covers the run
    (`analysis_audit_gap` names that), and silent on whether the verdict is
    right: that is the reviewer's judgement."""
    if ctx.run is None:
        return []
    try:
        records = covering_analysis(ctx.area, ctx.text, ctx.run)
        found = reviews.area_reviews(ctx.area)
    except (AuditError, FileNotFoundError, ValueError):
        return []  # ValueError: FindingsError, ReviewError — station 3 names them
    out: list[GateFinding] = []
    for r in records:
        for n, f in r.limits():
            if f.effect != findings.EFFECT_STANDS or reviews.upholding(r, n, found):
                continue
            out.append(
                GateFinding(
                    WARNING,
                    f"{findings.limit_label(r, n)}: `stands` {reviews.state(r, n, found)} "
                    f"— no decision review upholds that the reported claim stands "
                    f"within this limit: `labkit-audit <area> --review --record "
                    f"{r.path.name}` asks a second auditor (a warning while the check "
                    f"is explored)",
                )
            )
    return out


def unreportable_gaps(ctx: Checked, freeze_owed: bool) -> list[str]:
    """Station 2, the run: why the answering run's number cannot be reported
    (`runs.unreportable`), each a blocker. Without an answering run there is
    nothing to hold — finalize says so. FREEZE_OWED names the freeze in the
    sentence (minutes/hours); at seconds a full run is owed, no freeze."""
    if ctx.run is None:
        return []
    cfg = read_run_config(ctx.run)
    if cfg is None:
        return [f"{ctx.run.name}: no config.json — not a run"]
    owed = "a full run (run_kind='measurement')" + (
        " on a frozen protocol" if freeze_owed else ""
    )
    return [
        f"the answering run {ctx.run.name}: {mark} — its number cannot be "
        f"reported; a reported number owes {owed}"
        for mark in unreportable(cfg)
    ]


def finalize_gaps(area: Path, protocol: Path) -> list[str]:
    """Station 2, the gate before: finalize's blockers, each named here with
    its prefix — a hook that says "run it to see them" asks for a round
    trip the agent does not take. finalize runs on a silent collector
    (`Findings(tell=None)`): its findings arrive as data and nothing of its
    output reaches this gate's. Exit 2 (no protocol to hold) is one blocker."""
    collected = Findings(tell=None)  # the data, not the console
    finalized = finalize_area(area, protocol, collected)
    if finalized == 0:
        return []
    if collected.blocked:
        return [f"finalize: {b}" for b in collected.blocked]
    return [f"finalize {area} exits {finalized} — run it to see why"]


def later_gaps(ctx: Checked, ln: Lane) -> list[str]:
    """Stations 2–4: finalize clean and its run a full run, the analysis
    audit where the lane LN owes it (`Lane.audits`; every lane of the
    standard does), the check. The freeze names itself in station 2's
    sentence where the lane owes it."""
    out = finalize_gaps(ctx.area, ctx.protocol)
    out += unreportable_gaps(ctx, ln.freeze)
    if ANALYSIS_AUDIT in ln.audits:
        gap = analysis_audit_gap(ctx)
        if gap:
            out.append(f"analysis audit: {gap} ({ln.analysis_rule})")
        out += [f"analysis audit: {g}" for g in limit_gaps(ctx)]
    failed = check_analysis_script(ctx.area, ctx.repo)
    if failed:
        out.append(f"{failed} (LAB-041 Generate numbers, don't retype them)")
    return out


def report_check(
    area: Path,
    protocol: Path | None = None,
    *,
    state: str = TREE,
    text: str | None = None,
) -> int:
    """Run the stations on AREA; 0 clean, 1 a blocker, 2 no protocol to hold.
    STATE and TEXT name the file state the declaration is read from
    (`checked`): the tree by default, the index for the pre-commit, the
    written proposal for the adoption."""
    chosen = choose_protocol(area, protocol, "report-check")
    if chosen is None:
        return 2
    try:
        ctx = checked(area, chosen, state=state, text=text)
    except (protocol_block.BlockError, AuditError) as exc:
        console.refuse("report-check", f"{chosen.name}: {exc}")
        return 2
    print(
        f"  {chosen.name}: read from the {ctx.state}; the head declares "
        f"{ctx.declared or 'no run'}; the answering run is "
        f"{ctx.run.name if ctx.run is not None else 'none — ' + ctx.why}"
    )
    # what the release owes at this tier is the contract's answer: the freeze
    # or the registration (station 1) and the audits follow the lane;
    # finalize, the full run and the check are owed at every tier
    ln = lane(ctx.head.cost)
    findings = Findings()
    if ctx.declaration_gap:
        findings.block(f"{chosen.name}: {ctx.declaration_gap}")
    for finding in station_one(ctx, ln):
        findings.take(finding)
    for b in later_gaps(ctx, ln):
        findings.block(b)
    if ANALYSIS_AUDIT in ln.audits:
        for finding in review_findings(ctx):
            findings.take(finding)
    if not findings.blocked:
        held = ("frozen, " if ln.freeze else "") + "finalized, audited, checked"
        print(f"  {chosen.name}: {held}")
    return findings.report("report-check", "reporting")


def station_one(ctx: Checked, ln: Lane) -> list[GateFinding]:
    """Station 1 as the lane LN owes it: the freeze (`freeze_gaps`, each a
    blocker) where the lane freezes, else the registration as committed
    at the first measurement (`registration_gaps`), said so on the way."""
    if ln.freeze:
        return [GateFinding(BLOCKER, g) for g in freeze_gaps(ctx)]
    print(
        f'  {ctx.protocol.name}: cost = "{ctx.head.cost}" — no freeze and no preflight '
        f"audit owed (LAB-017 The number of audits follows the cost tier); the "
        f"registration as committed at the first measurement, the full run, "
        f"the analysis audit and the check are"
    )
    return registration_gaps(ctx) if ln.registration else []


def affected_protocols(
    paths: list[Path], repo: Path, *, staged: bool = False
) -> list[Path]:
    """Every protocol of every area PATHS touch, each once, by area: a
    changed script, run or audit record reopens the area's reported numbers
    as a changed protocol does, and so does a file its promises declare in
    scope or a shared helper its code imports (`scope_sha.areas_touched`,
    the stop and the commit's undecided gate read the same answer). STAGED:
    areas and protocols are the index's (`repo.indexed_protocols`) — a
    protocol deleted only in the tree is still in the commit."""
    if not staged:
        return [
            p
            for area in sorted(areas_touched(paths, repo))
            for p in area_protocols(area)
        ]
    indexed = indexed_protocols(repo)
    areas = areas_touched(paths, repo, indexed)
    return [p for area in sorted(areas) for p in indexed if p.parent == area]


def index_text(repo: Path, path: Path) -> str | None:
    """PATH's content as git's index holds it — what a commit now would
    carry — or None when the index does not hold it (untracked, or staged
    as deleted). PATH must lie under REPO."""
    rel = path.resolve().relative_to(repo.resolve()).as_posix()
    r = git_run(["show", f":{rel}"], repo)
    return r.stdout if r.returncode == 0 else None


def tree_differs(repo: Path, area: Path) -> list[str]:
    """The paths under AREA whose working tree differs from the index — a
    tracked file modified or deleted and not staged, an untracked file —
    relative to REPO. Empty when the tree under AREA is what the commit
    would hold."""
    rel = area.resolve().relative_to(repo.resolve()).as_posix()
    return [path for xy, path in status_entries(repo, (rel,)) if xy[1] != " "]


#: the files a report lives in; a protocol is held by the stations instead
REPORT_SUFFIX = ".md"


def report_files(
    paths: list[Path], repo: Path, *, staged: bool
) -> list[tuple[Path, str]]:
    """(path, text) of every Markdown file among PATHS that cites a run
    (`report_blocks.cited_run_ids`) — not a protocol, not under SKIP_DIRS —
    with its text as the state holds it: the index when STAGED, else the
    tree. A file the state does not hold (deleted, untracked at the commit)
    reports nothing. Only these paths: an old citation in a file nobody
    touched reopens nothing."""
    root = repo.resolve()
    out: list[tuple[Path, str]] = []
    for path in paths:
        full = (path if path.is_absolute() else root / path).resolve()
        if full.suffix != REPORT_SUFFIX or PROTOCOL_NAME.match(full.name):
            continue
        try:
            rel = full.relative_to(root)
        except ValueError:
            continue  # outside the repo: no commit and no stop holds it
        if SKIP_DIRS & set(rel.parts):
            continue
        if staged:
            text = index_text(repo, full)
        else:
            text = full.read_text(encoding="utf-8") if full.is_file() else None
        if text is not None and report_blocks.cited_run_ids(text):
            out.append((full, text))
    return out


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
    for p in protocols:
        runs_dir = p.parent / "runs"
        if runs_dir.is_dir():
            out.known.update(d.name for d in runs_dir.iterdir() if d.is_dir())
        text = index_text(repo, p) if staged else p.read_text(encoding="utf-8")
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
        if p not in sources.texts:
            out[b.protocol] = report_blocks.BlockSource(
                None, None, "no protocol of the repo there"
            )
        elif p in sources.unreadable:
            out[b.protocol] = report_blocks.BlockSource(
                None, None, f"its head does not read: {sources.unreadable[p]}"
            )
        elif (run_id := sources.declared[p]) is None:
            out[b.protocol] = report_blocks.BlockSource(
                None, None, "it declares no result"
            )
        else:
            try:
                body = report_blocks.block_body(
                    rendering(p.parent, sources.texts[p], p.parent / "runs" / run_id)
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
    declaring = {
        run_id: [report_blocks.path_from_report(p, report) for p in protocols]
        for run_id in {r for _, r in cited}
        if (protocols := sources.declaring(run_id))
    }
    rel = report.relative_to(sources.repo).as_posix()
    return [
        f"line {n}: cites run {run_id}, the declared result of {protocol}, without "
        f"its generated block — the number a report shows of a declared result is "
        f"the generated one: `protocol-fill {protocol} --into {rel}` writes it"
        for n, run_id, protocol in report_blocks.blocks_owed(
            cited, declaring, {b.protocol for b in found}
        )
    ]


def hold_report(path: Path, text: str, repo: Path, sources: Sources) -> int:
    """Hold one report: its blocks equal their protocols' rendering, every
    cited run id a run of the repo, every cited declared result shown in
    its protocol's block (blockers); every number outside a block a hint,
    a cited run no protocol declares a warning (static evidence). 0 clean
    or hints only, 1 a blocker."""
    rel = path.relative_to(repo.resolve()).as_posix()
    print(f"═══ report-check {rel} (a report citing runs) ═══")
    out = Findings()
    try:
        found = report_blocks.blocks(text)
    except report_blocks.ReportBlockError as exc:
        out.block(f"{rel}: {exc}")
        return out.report("report-check", "reporting")
    for gap in report_blocks.block_gaps(found, block_sources(path, found, sources)):
        out.block(f"{rel}: {gap}")
    cited = report_blocks.cited_run_ids(text)
    for gap in report_blocks.cited_gaps(cited, sources.known):
        out.block(f"{rel}: {gap}")
    for gap in owed_blocks(path, text, found, sources):
        out.block(f"{rel}: {gap}")
    unsourced = report_blocks.unsourced_numbers(text)
    if unsourced:
        out.warn(
            f"{rel}: no assigned source found for the numbers on "
            f"{len(unsourced)} line(s) — they stand outside every generated "
            f"result block (a hint, not a check of the numbers):"
        )
        for n, numbers in unsourced:
            out.note(f"    {rel}:{n}: {', '.join(numbers)}")
    undeclared = sorted(
        {r for _, r in cited if r in sources.known and not sources.declaring(r)}
    )
    if undeclared:
        out.warn(
            f"{rel}: cites {', '.join(undeclared)}, which no protocol declares as "
            f"its result — a reported number is declared by `protocol-fill "
            f"<PROTOCOL> --from-run`, and its block written by `--into {rel}`; "
            f"an exploration's run is cited, not reported"
        )
    return out.report("report-check", "reporting")


def if_reported(paths: list[Path], repo: Path, *, staged: bool) -> int:
    """`report-check` for every protocol of an area one of PATHS touches
    whose head declares a result, and for every report among PATHS
    (`report_files`): the gate at the stop and the commit. A result declared
    reported is held to the whole chain, a protocol declaring none is
    skipped (an exploration may end with no reported result). A report's
    generated blocks are held to the protocols they name, which the
    stations hold too, its cited run ids to the repo's runs; its other
    numbers are hints. STAGED (the pre-commit): declarations and reports are
    read from the index, and an area whose tree differs from the index is a
    blocker — the stations read the tree, the commit holds the index.
    Returns the worst exit code."""
    reports = report_files(paths, repo, staged=staged)
    sources = (
        repo_sources(repo, staged=staged)
        if reports
        else Sources(repo.resolve(), set(), {}, {}, {})
    )
    protocols = affected_protocols(paths, repo, staged=staged)
    for p in held_by_reports(reports, sources):
        if p not in protocols:
            protocols.append(p)
    worst = 0
    for protocol in protocols:
        worst = max(worst, hold_declared(protocol, repo, staged=staged))
    for path, text in reports:
        worst = max(worst, hold_report(path, text, repo, sources))
    return worst


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


def hold_declared(protocol: Path, repo: Path, *, staged: bool) -> int:
    """`report-check` on PROTOCOL when its head declares a result, as the
    state holds it (the index when STAGED); 0 for an exploration or a
    protocol the commit does not hold, 2 for one that cannot be read."""
    if staged:
        text = index_text(repo, protocol)
        if text is None:
            return 0  # not in the commit: nothing declared there
    else:
        try:
            text = protocol.read_text(encoding="utf-8")
        except OSError as exc:
            console.refuse("report-check", f"{protocol}: {exc}")
            return 2
    declared, gap = _declaration(text)
    if declared is None and gap is None:
        return 0  # an exploration: nothing declared, nothing owed
    print(
        f"═══ report-check {protocol} (its head declares "
        f"{declared or 'a result that does not read'}) ═══"
    )
    area = protocol.parent.resolve()
    if staged:
        differs = tree_differs(repo, area)
        if differs:
            print(
                f"  {area.relative_to(repo.resolve()).as_posix()}: the working "
                f"tree differs from the index ({', '.join(differs)}) — the "
                f"stations read the tree, the commit holds the index; stage "
                f"these too, or stash them, so the commit holds what the "
                f"check sees"
            )
            return 1
    return report_check(area, protocol, state=INDEX if staged else TREE, text=text)


def main(argv: list[str]) -> int:
    """Command line of `report-check`."""
    if argv and argv[0] == "--if-reported":
        cwd = Path.cwd()
        rest = argv[1:]
        staged = bool(rest) and rest[0] == "--staged"
        paths = [Path(a) for a in (rest[1:] if staged else rest)]
        return if_reported(paths, git_root(cwd) or cwd, staged=staged)
    ap = argparse.ArgumentParser(
        prog="report-check", description=(__doc__ or "").split("\n\n")[0]
    )
    ap.add_argument("area", type=area_path)
    ap.add_argument("--protocol", type=Path, default=None)
    a = ap.parse_args(argv)
    if not a.area.is_dir():
        console.refuse("report-check", no_such_area(a.area))
        return 2
    return report_check(a.area.resolve(), a.protocol)


def cli() -> None:
    """Console entry point `report-check`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
