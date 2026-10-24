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

  0. protocol       choose the protocol; read its head, declaration and
                    answering run into Checked. No protocol or unreadable
                    context ends with exit 2.
  1. declaration    report an unreadable `[result]` as a blocker.
  2. registration   where the lane freezes: the flag, required fields and
                    promise tables must hold. Otherwise, where the lane
                    owes registration: check the commit of the first
                    measurement. At seconds no freeze or preflight audit
                    is owed (LAB-017 The number of audits follows the cost tier).
  3. finalize       run finalize and name its blockers.
  4. full run       with an answering run: require a measurement without
                    an unfrozen acknowledgement (`runs.unreportable`).
  5. analysis       where the lane owes an analysis audit: a decided record
                    must cover the current code, promises, answering run
                    and shown evidence. Check the generated Recorded results
                    and Limit lines against that run and those records.
  6. recomputation  always run `scripts/02_analyze.py --check` under the
                    repo's interpreter: its outputs, metrics and cited
                    result must agree (LAB-041 Generate numbers, don't retype them).
  7. decisions      where the lane owes an analysis audit: check reviews
                    of accepted `stands` decisions. An unconfirmed BLOCKER
                    blocks; an unconfirmed WARNING warns.
  8. summary        1 if any stage found a blocker, otherwise 0.

`report_check` lists the stages and their conditions in this order. A
blocker does not stop later applicable stages. It reads and runs checks;
it does not itself write the protocol or run records. Checked supplies
this gate's protocol text, head, declaration and selected answering run.
The nested finalize gate and the analysis script read their own inputs;
this is not a single file snapshot across all stages. The output names
the file state whose declaration was checked.

`--if-reported` is the gate that runs unasked: `claude-hook stop` runs it
on every changed path and sends the agent back once per stop (a hook that
never let a session end would trap it — `stop_hook_active`), the stamped
pre-commit runs it on every staged path and holds. So the commit is the
gate the agent cannot pass; the stop is the one it hears first. Both
select every protocol of every area one of those paths lies in
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
(`report_blocks.unsourced_numbers`, static evidence). The paths given,
and what a changed declaration reaches: a protocol among them whose
declaration differs from HEAD's (`newly_declared`) holds every committed
report citing that run (`committed_reports`, `reached_reports`) — the
number such a report shows became a declared result in this state, so it
owes its block now (the two-step commit of the sixth haiku round, t5,
2026-10-23). An old citation of a run whose declaration did not change
reopens nothing.

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

from labkit.formats.gate import GUARANTEED, STATIC_EVIDENCE
from labkit.formats.runs import run_dirs, run_path
from labkit.formats.gate import BLOCKER, EXIT_CONTRACT, WARNING, Findings, GateFinding
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
    adopt_command,
    area_path,
    area_protocols,
    choose_protocol,
    git_root,
    under_root,
    indexed_files,
    indexed_protocols,
    layout_root,
    no_such_area,
    PROTOCOL_NAME,
    repo_protocols,
    SKIP_DIRS,
    status_entries,
    text_at,
)
from labkit.formats.runs import read_run_config, recorded_commit, unreportable
from labkit.formats.scope_sha import areas_touched
from labkit.formats.standard_contract import (
    ANALYSIS_AUDIT,
    CHECK_SCRIPT,
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
    state. This gate's checks use the same declaration and run choice.
    The nested finalize gate and analysis script read their own inputs.

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
    """Why the freeze does not hold — the flag unset, or a must
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
    """The committed registration where the lane owes it instead of the freeze
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
        return [
            GateFinding(
                BLOCKER,
                f"{first.name}: no config.json — not a run",
                evidence_kind=GUARANTEED,
            )
        ]
    at = f"the first measurement {first.name}"
    if git_root(ctx.protocol) is None:
        return [
            GateFinding(
                WARNING,
                f"not a git repository — the registration cannot be held to the "
                f"commit of {at}",
                evidence_kind=GUARANTEED,
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
                evidence_kind=GUARANTEED,
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
                evidence_kind=GUARANTEED,
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
                evidence_kind=GUARANTEED,
            )
        ]
    return []


def analysis_audit_gap(ctx: Checked) -> str | None:
    """Why no decided analysis record covers the code, the promise
    block, the answering run and what the audit was shown of it as they are
    now, or None. Without an answering run there is nothing the audit could
    be held to."""
    if ctx.run is None:
        return f"no answering run to hold it to — {ctx.why}"
    try:
        sha, block_sha, run_id, shown_sha, registration = analysis_now(
            ctx.area, ctx.text, ctx.run
        )
        return findings.audit_coverage(
            ctx.area,
            sha,
            ANALYSIS_AUDIT,
            block_sha,
            run_id,
            shown_sha,
            registration=registration,
        )
    except AuditError as exc:  # a registered output is gone
        return f"the analysis audit cannot be held to the run: {exc}"
    except (FileNotFoundError, ValueError) as exc:
        # ValueError: nothing to stamp, a findings file or the promise block
        # unreadable (FindingsError, PromiseError)
        return f"the analysis audit cannot be held to the area: {exc}"


def limit_gaps(ctx: Checked) -> list[str]:
    """The generated results and limits: every accepted BLOCKER of the covering analysis
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
    """The decision reviews: every `stands` among the limits of the
    covering analysis records is upheld by a decision review
    (`reviews.upholding`: a review of that record, its code and its run as
    shown, under the claim the protocol makes now, of the decision as it
    stands now, every draw saying `upheld`). The grade follows the
    finding's: an accepted BLOCKER's `stands` no review upholds — never
    reviewed, rejected, insufficient, contested, or reviewed as another
    decision or claim — is a BLOCKER (a severe finding is not settled by
    a reason alone; decided 2026-10-22 after the fifth round's replay and
    the assessment of its fifteen decisions from their sources), an
    accepted WARNING's a WARNING for now (the release does not yet hang
    on every lesser limit). A finding a review of the record once did not
    uphold (`reviews.once_not_upheld`) and that is now `dismissed`, `fixed`
    or `deferred` (`findings.CLOSING`) is held the same way until a review
    upholds the new decision: closing it is not settling it (sixth haiku
    round, 2026-10-23, t5). Empty when no record covers the run
    (`analysis_audit_gap` names that), and silent on whether the verdict is
    right: that is the reviewer's judgement."""
    if ctx.run is None:
        return []
    try:
        records = covering_analysis(ctx.area, ctx.text, ctx.run)
    except (AuditError, FileNotFoundError, ValueError):
        return []  # ValueError: FindingsError — analysis_audit_gap names them
    out: list[GateFinding] = []
    try:
        found = reviews.area_reviews(ctx.area)
    except reviews.ReviewError as exc:
        # named, and the decisions are judged as unreviewed: a file nobody
        # can read must not hide a BLOCKER's unupheld `stands`
        out.append(
            GateFinding(
                WARNING, f"a review nobody can read: {exc}", evidence_kind=GUARANTEED
            )
        )
        found = []
    for r in records:
        for n, f in r.limits():
            if f.effect != findings.EFFECT_STANDS or reviews.upholding(
                r, n, found, ctx.text
            ):
                continue
            out.append(
                GateFinding(
                    BLOCKER if f.grade == "BLOCKER" else WARNING,
                    f"{findings.limit_label(r, n)}: `stands` on an accepted {f.grade} "
                    f"{reviews.state(r, n, found, ctx.text)} — no decision review "
                    f"upholds that the reported claim stands within this limit: "
                    f"`labkit-audit <area> --review --record {r.path.name}` asks a "
                    f"second auditor; after a rejection, decide again "
                    f"(LAB-015 Preflight audit before freezing)",
                    evidence_kind=GUARANTEED,
                )
            )
        for n, f in enumerate(r.findings, 1):
            if f.status not in findings.CLOSING:
                continue
            was = reviews.once_not_upheld(r, n, found)
            if was is None or reviews.upholding(r, n, found, ctx.text):
                continue
            out.append(
                GateFinding(
                    BLOCKER if f.grade == "BLOCKER" else WARNING,
                    f"audit {r.path.stem} #{n}: `{f.status}` on a {f.grade} a "
                    f"review said {was.verdict} on ({was.why}) — closing a finding "
                    f"a reviewer did not uphold settles nothing by itself; the new "
                    f"decision is {reviews.state(r, n, found, ctx.text)}: "
                    f"`labkit-audit <area> --review --record {r.path.name}` asks a "
                    f"second auditor whether the reason shows it {_closing_question(f.status)} "
                    f"(LAB-015 Preflight audit before freezing)",
                    evidence_kind=GUARANTEED,
                )
            )
    return out


def _closing_question(status: str) -> str:
    """What the reviewer is asked of a closed contested finding, by status."""
    return {
        "dismissed": "does not apply to the code and run as audited",
        "fixed": "gone in the files as audited",
        "deferred": "somebody else's task, not this result's limit",
    }[status]


def unreportable_gaps(ctx: Checked, freeze_owed: bool) -> list[str]:
    """Why the answering run's number cannot be reported
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
    """Finalize's blockers, each named here with
    its prefix — a hook that says "run it to see them" asks for a round
    trip the agent does not take. finalize runs on a silent collector
    (`Findings(tell=None)`): its findings arrive as data and nothing of its
    output reaches this gate's, so finalize puts every reason into the
    blocker itself (the runs it looked at, intent-check's lines, the test
    counts) and keeps its exit-2 reason (no protocol to hold) as a blocker
    too. A non-zero exit without a blocker is a bug in finalize, not a
    state to report around."""
    collected = Findings(tell=None)  # the data, not the console
    finalized = finalize_area(area, protocol, collected)
    if finalized == 0:
        return []
    if not collected.blocked:
        raise RuntimeError(
            f"finalize {area} exits {finalized} and kept no blocker — every "
            f"reason finalize has must be a finding"
        )
    return [f"finalize: {b}" for b in collected.blocked]


def analysis_findings(ctx: Checked, rule: str) -> list[GateFinding]:
    """Coverage and rendered-result blockers for an analysis stage already due.

    RULE is the lane's analysis-audit rule; the entry point decides whether
    this stage runs. Missing coverage and result differences are all kept.
    """
    out: list[GateFinding] = []
    gap = analysis_audit_gap(ctx)
    if gap:
        out.append(
            GateFinding(
                BLOCKER, f"analysis audit: {gap} ({rule})", evidence_kind=GUARANTEED
            )
        )
    # the rendered result section is held here too, named as what it is:
    # a cold reader took "analysis audit:" on a retyped Recorded results
    # line for a record problem (reading probe 2026-10-22)
    out.extend(
        GateFinding(BLOCKER, f"result section: {gap}", evidence_kind=GUARANTEED)
        for gap in limit_gaps(ctx)
    )
    return out


def recomputation_findings(area: Path, repo: Path) -> list[GateFinding]:
    """Run the analysis script's check and return its failure as a blocker."""
    failed = check_analysis_script(area, repo)
    return (
        [
            GateFinding(
                BLOCKER,
                f"{failed} (LAB-041 Generate numbers, don't retype them)",
                evidence_kind=GUARANTEED,
            )
        ]
        if failed
        else []
    )


def report_check(
    area: Path,
    protocol: Path | None = None,
    *,
    state: str = TREE,
    text: str | None = None,
) -> int:
    """Check AREA before reporting; 0 clean or warnings, 1 blocked, 2 no context.

    0. Choose the protocol and read Checked; missing or unreadable ends with 2.
    1. Declaration: an unreadable `[result]` blocks, later stages continue.
    2. Registration: check the freeze where the lane owes it; otherwise check
       the first measurement's committed registration where owed.
    3. Finalize: always collect its blockers.
    4. Full run: check reportability only when an answering run exists.
    5. Analysis: coverage and rendered results only where the lane owes it.
    6. Recomputation: always run the analysis script's `--check`.
    7. Decisions: review accepted `stands` only where analysis is owed.
    8. Summary: return 1 with any blocker, otherwise 0.

    Every applicable stage runs despite earlier blockers. STATE and TEXT
    name the declaration's file state: the tree by default, the index for
    the pre-commit, the written proposal for adoption. The nested finalize
    gate and analysis script read their own inputs.
    """
    # 0. protocol and context — the only early end
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
    ln = lane(ctx.head.cost)
    findings = Findings()

    # 1. declaration — a blocker does not stop the remaining stages
    if ctx.declaration_gap:
        findings.block(f"{chosen.name}: {ctx.declaration_gap}")

    # 2. registration — freeze or committed registration, as the lane owes
    if ln.freeze:
        findings.take_all(
            GateFinding(BLOCKER, gap, evidence_kind=GUARANTEED)
            for gap in freeze_gaps(ctx)
        )
    else:
        print(
            f'  {ctx.protocol.name}: cost = "{ctx.head.cost}" — no freeze and no preflight '
            f"audit owed (LAB-017 The number of audits follows the cost tier); the "
            f"registration as committed at the first measurement, the full run, "
            f"the analysis audit and the check are owed instead"
        )
        if ln.registration:
            findings.take_all(registration_gaps(ctx))

    # 3. finalize — always, with its blockers named
    findings.take_all(
        GateFinding(BLOCKER, gap, evidence_kind=GUARANTEED)
        for gap in finalize_gaps(ctx.area, ctx.protocol)
    )

    # 4. full run — only with an answering run; finalize names its absence
    if ctx.run is not None:
        findings.take_all(
            GateFinding(BLOCKER, gap, evidence_kind=GUARANTEED)
            for gap in unreportable_gaps(ctx, ln.freeze)
        )

    # 5. analysis — coverage and rendering where the lane owes the audit
    if ANALYSIS_AUDIT in ln.audits:
        findings.take_all(analysis_findings(ctx, ln.analysis_rule))

    # 6. recomputation — always, including after a failed earlier stage
    findings.take_all(recomputation_findings(ctx.area, ctx.repo))

    # 7. decisions — reviews where the lane owes the analysis audit
    if ANALYSIS_AUDIT in ln.audits:
        findings.take_all(review_findings(ctx))

    # 8. summary — 1 with a blocker, otherwise 0
    if not findings.blocked:
        held = ("frozen, " if ln.freeze else "") + "finalized, audited, checked"
        print(f"  {chosen.name}: {held}")
    return findings.report("report-check", "reporting")


def affected_protocols(
    paths: list[Path], repo: Path, *, staged: bool = False
) -> list[Path]:
    """Every protocol of every area PATHS touch, each once, by area: a
    changed script, run or audit record reopens the area's reported numbers
    as a changed protocol does, and so does a file its promises declare in
    scope, a shared helper its code imports, or the validation its
    `annotation_validity` binds (`scope_sha.areas_touched`,
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
    as deleted). PATH must lie under REPO (`repo.text_at`)."""
    return text_at(repo, path)


def state_text(repo: Path, path: Path, *, staged: bool) -> str | None:
    """PATH's content as the gate's state holds it: the index when STAGED
    (`index_text`), else the working tree; None when that state does not
    hold the file."""
    if staged:
        return index_text(repo, path)
    return path.read_text(encoding="utf-8") if path.is_file() else None


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
        if not under_root(root, full):
            continue  # outside the repo: no commit and no stop holds it
        if SKIP_DIRS & set(full.relative_to(root).parts):
            continue
        text = state_text(repo, full, staged=staged)
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
    with its text as the state holds it. The reports a changed declaration
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
    out: list[tuple[Path, str]] = []
    for full in candidates:
        text = state_text(repo, full, staged=staged)
        if text is None:
            continue
        if any(r in run_ids for _, r in report_blocks.cited_run_ids(text)):
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
        out.known.update(rd.dir.name for rd in run_dirs(p.parent))
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
    path: Path, text: str, repo: Path, sources: Sources, *, held_as: str = AMONG_PATHS
) -> int:
    """Hold one report: its blocks equal their protocols' rendering, every
    cited run id a run of the repo, every cited declared result shown in
    its protocol's block, a run cited as not reported says why, and the
    answering run of a protocol that declares no result is not cited
    unmarked (`promotions` — the number of a full run presented without
    the adoption; blockers); any other cited run no protocol declares a
    WARNING (guaranteed); the numbers outside every block, and those beside
    a run cited as not reported, a WARNING that is static evidence — a
    hint at where to look, not a check of them. HELD_AS says in the heading
    why this report is held. 0 clean or warnings only, 1 a blocker."""
    rel = path.relative_to(repo.resolve()).as_posix()
    print(f"═══ report-check {rel} ({held_as}) ═══")
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
    marked = report_blocks.not_reported(text)
    for gap in report_blocks.marker_gaps(marked):
        out.block(f"{rel}: {gap}")
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
    beside = report_blocks.numbers_beside_not_reported(text, marked)
    if beside:
        out.warn(
            f"{rel}: numbers on {len(beside)} line(s) beside a run cited as not "
            f"reported — a looked-at run's number in a report is a reported "
            f"number unless the sentence says what it is (a hint, not a check):",
            evidence_kind=STATIC_EVIDENCE,
        )
        for n, numbers in beside:
            out.note(f"    {rel}:{n}: {', '.join(numbers)}")
    out.take_all(undeclared_findings(path, rel, cited, marked, sources))
    return out.report("report-check", "reporting")


def undeclared_findings(
    path: Path,
    rel: str,
    cited: list[tuple[int, str]],
    marked: list[report_blocks.NotReported],
    sources: Sources,
) -> list[GateFinding]:
    """The findings on the runs the report at PATH (REL to the repo) cites
    that no protocol declares as its result (CITED: line and id; MARKED:
    the citations carrying the not-reported marker). Blockers: a marked run
    some protocol does declare — the marker is a false claim beside a
    shown result; the unmarked citation of a protocol's answering run that
    declares none (`promotions`), the sentence naming the adoption and the
    marker as the two ways out. A warning: any other undeclared run cited
    unmarked — an exploration's run is looked at. A marked run says so and
    gets no warning."""
    out: list[GateFinding] = []
    for m in marked:
        for protocol in sources.declaring(m.run_id):
            named = report_blocks.path_from_report(protocol, path)
            out.append(
                GateFinding(
                    BLOCKER,
                    f"{rel}: line {m.line}: run {m.run_id} is cited as not reported, "
                    f"but {named} declares it as its result — drop the marker; the "
                    f"generated block shows the number",
                    evidence_kind=GUARANTEED,
                )
            )
    said_so = {m.run_id for m in marked}
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
                f"this report looks at without reporting it is cited as such: "
                f"`{report_blocks.NOT_REPORTED_FORM.format(run_id=run_id)}`",
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
    A protocol among them whose declaration differs from HEAD's
    (`newly_declared`) reaches the committed reports citing that run
    (`committed_reports`): they are held as if changed, since the number
    they show became a declared result in this very state (the two-step
    commit of the sixth haiku round, 2026-10-23). Returns the worst exit
    code."""
    protocols = affected_protocols(paths, repo, staged=staged)
    reports = report_files(paths, repo, staged=staged)
    reached = reached_reports(protocols, reports, repo, staged=staged)
    sources = (
        repo_sources(repo, staged=staged)
        if reports or reached
        else Sources(repo.resolve(), set(), {}, {}, {})
    )
    for p in held_by_reports(reports + [(p, t) for p, t, _ in reached], sources):
        if p not in protocols:
            protocols.append(p)
    worst = 0
    for protocol in protocols:
        worst = max(worst, hold_declared(protocol, repo, staged=staged))
    for path, text in reports:
        worst = max(worst, hold_report(path, text, repo, sources))
    for path, text, held_as in reached:
        worst = max(worst, hold_report(path, text, repo, sources, held_as=held_as))
    return worst


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
        prog="report-check",
        description=(__doc__ or "").split("\n\n")[0],
        # the hooks' form is parsed above, before argparse; it is still part
        # of this command's contract and stands in its --help (audit 2026-10-23, C2)
        epilog=(
            "report-check --if-reported [--staged] PATH ...\n"
            "    every protocol of an area a path touches whose head declares a\n"
            "    result, and every report among PATHS citing a run (the stop\n"
            "    hook; with --staged the pre-commit: the head and the report as\n"
            "    the index holds them, and the area's tree must equal the index)\n"
            f"{EXIT_CONTRACT}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
