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

This module holds the protocol's release stations and the entry points
(`if_reported`, `hold_declared`, `main`): the order and the conditions of
what runs stand here. The context every station reads is
`report_context.checked`; the replacement station lives in
`report_replacement`, the stations on the audit decisions (limits, reviews,
follow-up) in `report_decisions`. Finding the reports a change reaches and what holds
each lives in `report_hold`, which `if_reported` calls after the protocols.

`finalize` holds the run before the number is written back and comes
before the analysis audit; report-check comes last and holds the whole
chain, at every repeat cost (why each station holds what it holds:
docs/notes/2026-10-19-hooks-and-report-check.md):

  0. protocol       choose the protocol; read its head, declaration and
                    answering run into Checked. No protocol or unreadable
                    context ends with exit 2.
  1. declaration    report an unreadable `[result]` as a blocker.
  2. registration   where the lane freezes: the flag, required fields and
                    promise tables must hold. Otherwise, where the lane
                    owes registration: check the commit of the first
                    measurement. At low repeat cost no freeze or preflight audit
                    is owed (LAB-017 The number of audits follows the cost tier).
  3. finalize       run finalize and name its blockers.
  4. full run       with an answering run: require a measurement without
                    an unfrozen acknowledgement (`runs.unreportable`).
  5. analysis       where the lane owes an analysis audit: a decided record
                    must cover the current code, promises, answering run
                    and shown evidence; while the area's audit evidence is
                    gone the blocker names the loss and its restore, since
                    labkit-audit starts no audit then. Check the generated
                    Recorded results and Limitation lines against that run and
                    those records.
  6. recomputation  always run `scripts/02_analyze.py --check` under the
                    repo's interpreter: its outputs, metrics and cited
                    result must agree (LAB-041 Generate numbers, don't retype them).
  7. decisions      where the lane owes an analysis audit: check reviews
                    of accepted `stands` decisions. An unconfirmed BLOCKER
                    blocks; an unconfirmed WARNING warns.
  8. report         where the head registers a report file (`report`) and
                    that file is delivered: it carries the result block of
                    the declared run or the protocol's handover block
                    (`report_hold.report_owed`).
  9. summary        1 if any stage found a blocker, otherwise 0.

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
result owes nothing here but its registered report: an exploration ends
with no reported result, probes or not; a `[result]` that does not read
is held and blocks. A protocol whose head registers a report file
(`report = "REPORT.md"`) owes that file its result once the file is
delivered — in the tree at the stop, in the index at the commit —: the
result block of the declared run or the protocol's handover block,
declared or not (`report_hold.report_owed`, `hold_registered`); a
report with the run id removed, a run id typed in, or a discussion block
releases nothing (pressure pilot 2026-10-29: three of six agents deleted
the run id after the hook refused the citation, and the commit passed).
The protocols registering a file among the paths are selected too
(`report_hold.registering_protocols`): the report at the repository root
lies in no area.

A report outside the protocol — a Markdown file among the paths that
cites a run, not a protocol, not under `runs/` or `data/`, tested at its
own path (`report_files`) — is held too (`hold_report`): a report that is
a symbolic link, wherever it points, is refused alone, one blocker naming
the copy that replaces it (`link_gap`: the file a link points to can lie
where no report is held), and its other checks wait for that copy; else
each generated result block equals what the
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
(`repo.state_text` — an answer only the tree carries is not in the commit), and
an area whose tree differs from the index (`tree_differs`: a file modified
and not staged, or untracked) is a blocker before any station runs, since
the check would judge a state the commit does not hold.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
from dataclasses import replace
from pathlib import Path

from labkit.formats.gate import GUARANTEED
from labkit.formats.runs import RunDir
from labkit.formats.gate import (
    BLOCKER,
    EXIT_CONTRACT,
    WARNING,
    Findings,
    GateFinding,
    blocker,
)
from labkit.formats.answering_run import (
    bound_answering_run,
    bound_runs,
    first_measurements,
    is_measurement,
)
from labkit.formats.protocol_history import (
    registration_in_commit,
)
from labkit.formats import (
    attempts,
    audit_gaps,
    console,
    handovers,
    protocol_block,
    runs,
)
from labkit.checks.audit_binding import (
    AuditError,
    analysis_now,
    covering_analysis,
)
from labkit.gates.finalize import finalize_area
from labkit.gates.preflight import area_test_python, contract_hint
from labkit.gates import ways_out
from labkit.gates.report_hold import (
    Sources,
    discussing_reports,
    held_by_reports,
    hold_report,
    reached_reports,
    registering_protocols,
    repo_sources,
    report_files,
    report_owed,
    tree_differs,
)
from labkit.formats.protocol_check import check_fields
from labkit.formats.repo import (
    ADOPT_TOOL,
    adopt_command,
    area_path,
    area_protocols,
    audit_command,
    choose_protocol,
    commit_known,
    git_root,
    indexed_protocols,
    measure_command,
    no_such_area,
    protocol_links,
    shown,
    state_text,
    withdraw_command,
)
from labkit.formats.runs import read_run_config, recorded_commit, unreportable
from labkit.formats.scope_sha import areas_touched
from labkit.formats.standard_contract import (
    ANALYSIS_AUDIT,
    CHECK_FLAG,
    CHECK_SCRIPT,
    check_command,
    lane,
)
from labkit.gates.report_context import (
    Checked,
    INDEX,
    PROPOSED,
    TREE,
    checked,
    declaration,
)
from labkit.gates.report_decisions import followup_findings, limit_gaps, review_findings
from labkit.gates.report_replacement import replacement_gaps


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
            f"every skeleton stamps it (an area stamped at low repeat cost before 0.100.0 "
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


def freeze_gaps(ctx: Checked) -> list[GateFinding]:
    """Why the freeze does not hold — the flag unset, or a must
    gap protocol-check names (the stamp's `<…>` promise sentences among them)."""
    name = ctx.protocol.name
    fields = contract_hint(ctx.protocol)
    gaps = (
        []
        if ctx.head.frozen
        else [
            blocker(
                f"{name}: not `frozen = true` — a reported number owes the freeze",
                fix=f"freeze it: `preflight {shlex.quote(shown(ctx.area, Path.cwd()))}` "
                f"clean, the preflight audit run and decided "
                f"(`{audit_command(ctx.area, '--mode', 'preflight', protocol=ctx.protocol)}`), "
                f"then `frozen = true`",
            )
        ]
    )
    report = check_fields(ctx.text)
    gaps += [
        blocker(f"{name}: {label}", fix=f"write the field; {fields}")
        for label in report.missing_must
    ]
    # a must field still holding its `<…>` placeholder passed here while
    # protocol-check and preflight refused it (audit 2026-10-15)
    gaps += [
        blocker(
            f"{name}: line {n}: {label} still a placeholder",
            fix=f"replace it with this protocol's own text; {fields}",
        )
        for n, label in report.must_holes
    ]
    return gaps


def registration_gaps(ctx: Checked) -> list[GateFinding]:
    """The committed registration where the lane owes it instead of the freeze
    (seconds): the registration stood in the protocol as committed at the
    first measurement — the commit its record names (`runs.recorded_commit`)
    — at each run `answering_run.first_measurements` names: git's history
    orders the measurements, a run id (local time) only those at one
    commit; on diverged history, or for a run whose commit cannot be
    placed, more than one is first and each is held. Blockers per run: it
    recorded no commit, the repository does not hold that commit, the
    commit does not hold the protocol (nothing stood before the number),
    the fields the lane owes were not written there
    (`protocol_history.registration_in_commit`). runlog's start gate holds
    a first measurement to the same registration at HEAD
    (`start_check._committed_registration`), so this station catches what
    got past it — a commit rewritten after the run, a run started outside
    runlog; what stood before the number is what the commit holds. Outside a repository
    a warning, as the provenance station's (`run_record_check.provenance_findings`).
    Empty without a measurement (finalize names the missing run) and
    without a stamped id. Why (labkit-paper area 09, fifth haiku round,
    2026-10-22): none of the three labkit agents had committed criterion
    and quality check before the first measurement."""
    if ctx.head.id is None:
        return []
    root = git_root(ctx.protocol)
    first = first_measurements(ctx.area, ctx.head.id, root)
    if not first:
        return []
    if root is None:
        return [
            GateFinding(
                WARNING,
                "not a git repository — the registration cannot be held to the "
                "commit of the first measurement",
                evidence_kind=GUARANTEED,
            )
        ]
    return [gap for rd in first for gap in _registration_at(ctx, root, rd, len(first))]


def _registration_at(
    ctx: Checked, root: Path, rd: RunDir, held: int
) -> list[GateFinding]:
    """`registration_gaps` for RD, one of HELD first measurements, in the
    repository ROOT."""
    cfg = rd.config
    assert cfg is not None, "first_measurements names read runs only"
    at = f"the first measurement {rd.dir.name}"
    # several are first on diverged history or beside a run git cannot
    # place: without the why, a reader takes the second blocker for a bug
    among = "" if held == 1 else f"; one of {held} that git's history does not order"
    commit = recorded_commit(cfg)
    # what stood before the number cannot be repaired afterwards: a new
    # registration, committed before its own first run, or the handover
    anew = (
        "when the missing choices can be made on grounds the new registration "
        f"states, {ways_out.register_anew(str(ctx.head.id))}; else "
        f"{ways_out.HANDOVER}"
    )
    if commit is None:
        return [
            blocker(
                f"{at} recorded no commit ({cfg.git!r}{among}) — the registration "
                f"cannot be held to what stood before the number (LAB-003 No run "
                f"without an intent paragraph)",
                fix=anew,
            )
        ]
    if not commit_known(root, commit):
        return [
            blocker(
                f"{at} ({commit}{among}) recorded a commit this repository does not "
                f"hold (a rewritten history, a shallow clone) — neither its place "
                f"among the measurements nor the registration it stood on can be "
                f"read (LAB-003 No run without an intent paragraph)",
                fix="fetch that commit from a clone that has it (`git fetch "
                "--unshallow` in a shallow clone)",
            )
        ]
    missing = registration_in_commit(ctx.protocol, commit, ctx.head.kind)
    if missing is None:
        return [
            blocker(
                f"{ctx.protocol.name} was not committed at {at} ({commit[:12]}{among}) "
                f"— nothing stood before the number; the registration is what the "
                f"commit of the first measurement holds (LAB-003 No run without an "
                f"intent paragraph)",
                fix=anew,
            )
        ]
    if missing:
        return [
            blocker(
                f"the registration as committed at {at} ({commit[:12]}{among}) lacks "
                f"{', '.join(missing)} — the registration is what the commit of "
                f"the first measurement holds, not what the tree says now, so "
                f"that measurement is exploratory; a new run on the same data does "
                f"not restore what stood before the number (LAB-003 No run without "
                f"an intent paragraph)",
                fix=anew,
            )
        ]
    return []


def analysis_audit_gap(ctx: Checked) -> GateFinding | None:
    """Why no decided analysis record covers the code, the promise
    block, the answering run and what the audit was shown of it as they are
    now, as a blocker with its way out, or None. Without an answering run
    there is nothing the audit could be held to. When no record covers and
    the area's audit evidence is gone (`attempts.evidence_gaps`: a file an
    attempt of any mode ended with deleted, a journal cut), labkit-audit
    starts no audit (`attempts.begin`), so the blocker names the loss and
    its restore, or the handover, instead of an audit command; a covering
    record with findings open is decided, which needs no attempt."""
    audit = (
        f"audit the answering run as it stands: "
        f"`{audit_command(ctx.area, '--mode', 'analysis', protocol=ctx.protocol)}`, "
        f"then decide its findings"
    )
    if ctx.run is None:
        return blocker(
            f"no answering run to hold it to — {ctx.why}",
            fix=f"measure: `{measure_command(ctx.area)}`, then audit that run",
        )
    try:
        gap = audit_gaps.audit_coverage(
            ctx.area, ANALYSIS_AUDIT, analysis_now(ctx.area, ctx.text, ctx.run)
        )
        covering = covering_analysis(ctx.area, ctx.text, ctx.run)
    except AuditError as exc:  # a registered output is gone
        return blocker(
            f"the analysis audit cannot be held to the run: {exc.why}",
            fix=exc.fix or audit,
        )
    except (FileNotFoundError, ValueError) as exc:
        # ValueError: nothing to stamp, a findings file or the promise block
        # unreadable (FindingsError, PromiseError)
        return blocker(
            f"the analysis audit cannot be held to the area: {exc}",
            fix=f"repair what the sentence names, then {audit}",
        )
    if gap is None:
        return None
    # the way out is a new audit, and `attempts.begin` refuses every attempt
    # while one of these stands: "none has run yet" and `--mode analysis`
    # were printed after an audit's record was deleted (pilot t60)
    lost = attempts.evidence_gaps(ctx.area) if not covering else []
    if lost:
        findings_command = audit_command(ctx.area, "--findings", protocol=ctx.protocol)
        return blocker(
            f"no analysis audit covers the area as it is now, and none can run — "
            f"{attempts.gone_line(lost)}",
            fix=f"(a) bring the evidence back — the line names the first "
            f"restore, `{findings_command}` lists every loss with its restore —, "
            f"then {audit}; (b) where nothing restores it, no audit covers the "
            f"area and no number leaves it: {ways_out.HANDOVER}",
        )
    return blocker(gap, fix=audit)


def unreportable_gaps(ctx: Checked, freeze_owed: bool) -> list[GateFinding]:
    """Why the answering run's number cannot be reported
    (`runs.unreportable`), each a blocker. Without an answering run there is
    nothing to hold — finalize says so. FREEZE_OWED names the freeze in the
    sentence (high repeat cost); at low repeat cost a full run is owed, no freeze."""
    if ctx.run is None:
        return []
    measure = f"`{measure_command(ctx.area)}`"
    cfg = read_run_config(ctx.run)
    if cfg is None:
        return [
            blocker(
                f"{ctx.run.name}: no config.json — not a run",
                fix=f"measure through runlog: {measure}",
            )
        ]
    owed = "a full run (run_kind='measurement')" + (
        " on a frozen protocol" if freeze_owed else ""
    )
    return [
        blocker(
            f"the answering run {ctx.run.name}: {mark} — its number cannot be "
            f"reported; a reported number owes {owed}",
            fix=f"measure in full{' after the freeze' if freeze_owed else ''}: "
            f"{measure}, then audit that run",
        )
        for mark in unreportable(cfg)
    ]


def finalize_gaps(area: Path, protocol: Path) -> list[GateFinding]:
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
    return [
        replace(f, text=f"finalize: {f.text}")
        for f in collected.found
        if f.grade == BLOCKER
    ]


def analysis_findings(
    ctx: Checked, rule: str, *, result_section: bool = True
) -> list[GateFinding]:
    """Coverage and rendered-result blockers for an analysis stage already due.

    RULE is the lane's analysis-audit rule; the entry point decides whether
    this stage runs. Missing coverage and result differences are all kept;
    RESULT_SECTION False leaves the rendered result out (before an adoption,
    which writes it).
    """
    out: list[GateFinding] = []
    gap = analysis_audit_gap(ctx)
    if gap:
        out.append(replace(gap, text=f"analysis audit: {gap.text} ({rule})"))
    # the rendered result section is held here too, named as what it is:
    # a cold reader took "analysis audit:" on a retyped Recorded results
    # line for a record problem (reading probe 2026-10-22)
    if result_section:
        out.extend(
            replace(gap, text=f"result section: {gap.text}") for gap in limit_gaps(ctx)
        )
    return out


def recomputation_findings(area: Path, repo: Path) -> list[GateFinding]:
    """Run the analysis script's check and return its failure as a blocker."""
    failed = check_analysis_script(area, repo)
    return (
        [
            blocker(
                f"{failed} (LAB-041 Generate numbers, don't retype them)",
                fix=f"fix what the check names until `.venv/bin/python "
                f"{shlex.quote(shown(area / CHECK_SCRIPT, Path.cwd()))} {CHECK_FLAG}` "
                f"exits 0; a number in the protocol comes from `protocol-fill`, "
                f"never typed",
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
    8. Report: the registered report, only when the head names one and the
       file is delivered in STATE, carries the result block or the handover.
    9. Summary: return 1 with any blocker, otherwise 0.

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
        f"  {chosen.name}: read from the {ctx.state}; the head has adopted "
        f"{ctx.declared or 'no run'}; the answering run is "
        f"{ctx.run.name if ctx.run is not None else 'none — ' + ctx.why}"
    )
    ln = lane(ctx.head.repeat_cost)
    findings = Findings(
        area=shown(ctx.area, Path.cwd()),
        audit=audit_command(ctx.area, protocol=ctx.protocol),
    )
    if not ln.freeze:
        print(
            f'  {ctx.protocol.name}: repeat_cost = "{ctx.head.repeat_cost}" — no freeze and no preflight '
            f"audit owed (LAB-017 The number of audits follows the cost tier); the "
            f"registration as committed at the first measurement, the full run, "
            f"the analysis audit and the check are owed instead"
        )
    findings.take_all(report_gaps(ctx))
    # adoption last — an adoption line beside other blockers is the last
    # step, not the fix (stuck-state probe 2026-10-28)
    tell_adoption_order(findings)

    # 9. summary — 1 with a blocker, otherwise 0
    if not findings.blocked:
        held = ("frozen, " if ln.freeze else "") + "finalized, audited, checked"
        print(f"  {chosen.name}: {held}")
    return findings.report("report-check", "reporting")


def report_gaps(ctx: Checked, *, adoption_pending: bool = False) -> list[GateFinding]:
    """Every gap report-check holds CTX to, in the order of the chain — the
    one list `report_check` prints and `next_step` reads:

    1. Declaration: an unreadable `[result]` blocks; later stages continue.
    2. Registration: the freeze where the lane owes it, else the first
       measurement's committed registration where owed; a declared
       replacement's changes.
    3. Finalize: its blockers, always.
    4. Full run: reportability, only when an answering run exists.
    5. Analysis: coverage and rendered results where the lane owes it.
    6. Recomputation: the analysis script's `--check`, always.
    7. Decisions: reviews and follow-ups where the lane owes the analysis.
    8. Report: the registered report, once delivered in CTX's state.

    Every applicable stage runs despite earlier blockers; a declared run
    whose code changed puts the withdrawal before every later hold
    (`withdrawn_first`). ADOPTION_PENDING (no run adopted yet, the one a
    next step asks about): the stages the adoption writes and holds on its
    proposal — the result section (`report_decisions.limit_gaps`), the recomputation, the
    report — are left out, since the tree cannot pass them before the
    adoption writes them; `protocol_fill.adopt` checks the whole proposal.
    Prints nothing."""
    ln = lane(ctx.head.repeat_cost)
    out: list[GateFinding] = []
    # 1. declaration
    if ctx.declaration_gap:
        out.append(
            blocker(
                f"{ctx.protocol.name}: {ctx.declaration_gap}",
                fix=f"`{withdraw_command(ctx.protocol)}` removes it; audit the run "
                f"that answers, then `{adopt_command(ctx.protocol)}` writes the "
                f"`[result]` table for it",
            )
        )
    # 2. registration
    if ln.freeze:
        out += freeze_gaps(ctx)
    elif ln.registration:
        out += registration_gaps(ctx)
    out += replacement_gaps(ctx)
    # 3. finalize
    finalized = finalize_gaps(ctx.area, ctx.protocol)
    out += finalized
    held_by = held_declaration(ctx, finalized)
    # 4. full run
    if ctx.run is not None:
        out += withdrawn_first(unreportable_gaps(ctx, ln.freeze), held_by)
    # 5. analysis
    if ANALYSIS_AUDIT in ln.audits:
        analysis = analysis_findings(
            ctx, ln.analysis_rule, result_section=not adoption_pending
        )
        out += withdrawn_first(analysis, held_by)
    # 6. recomputation
    if not adoption_pending:
        out += withdrawn_first(recomputation_findings(ctx.area, ctx.repo), held_by)
    # 7. decisions
    if ANALYSIS_AUDIT in ln.audits:
        out += withdrawn_first(review_findings(ctx), held_by)
        out += withdrawn_first(followup_findings(ctx), held_by)
    # 8. report
    if not adoption_pending:
        out += report_findings(ctx)
    return out


def adoption_state(area: Path, protocol: Path, text: str) -> handovers.RunAccount:
    """Where PROTOCOL of AREA, as TEXT holds it, stands for an adoption —
    the account a handover records (`handovers.RunAccount`):

    - NOT_MEASURED: no measurement bound to it (completed or not) and none
      unreadable — a preparation or probe run measures nothing;
    - UNUSABLE: a measurement of it, and no number from it — the run choice
      holds (no completed run, an unreadable or same-second rival:
      `answering_run.bound_answering_run`), it chose a run that is no
      measurement, or the metrics.json does not read; the run is the newest
      measurement, WHY the sentences that put it there;
    - HELD: the answering run, and the blockers report-check holds its
      adoption with (`report_gaps`, the adoption pending; an audit that
      cannot be held to the run among them);
    - ADOPTABLE: the answering run, and nothing holds it.

    Prints nothing. Raises `protocol_block.BlockError` on a head that does
    not read, `runs.RunConfigError` from a run's config.json."""
    pid = protocol_block.head(text).id
    if not pid:
        return handovers.RunAccount(None, handovers.NOT_MEASURED, ())
    taken, rest = bound_runs(area, pid)
    ours = [f for f in rest if f.binding.id == pid or f.state == runs.UNREADABLE]
    measured = [f for f in [*taken, *ours] if is_measurement(f)]
    if not measured:
        return handovers.RunAccount(None, handovers.NOT_MEASURED, ())
    choice = bound_answering_run(area, pid)
    if choice.run_dir is None or not any(f.dir == choice.run_dir for f in measured):
        why = [f"{f.dir.name}: {f.why or f.state}" for f in measured if f in ours]
        why += [choice.blocker] if choice.blocker else []
        if choice.run_dir is not None:
            why.append(f"{choice.run_dir.name}, the run chosen, is no measurement")
        newest = max(f.dir.name for f in measured)
        return handovers.RunAccount(newest, handovers.UNUSABLE, tuple(why))
    run = choice.run_dir.name
    try:
        runs.read_metrics(runs.metrics_path(choice.run_dir))
    except runs.MetricsError as exc:
        return handovers.RunAccount(run, handovers.UNUSABLE, (str(exc),))
    try:
        ctx = checked(area, protocol, text=text)
    except AuditError as exc:
        # the audit cannot be held to the run: that holds the adoption too
        return handovers.RunAccount(run, handovers.HELD, (str(exc),))
    held = tuple(
        g.text
        for g in report_gaps(ctx, adoption_pending=ctx.declared is None)
        if g.grade == BLOCKER
    )
    state = handovers.HELD if held else handovers.ADOPTABLE
    return handovers.RunAccount(run, state, held)


def report_findings(ctx: Checked) -> list[GateFinding]:
    """The registered report's obligation (`report_hold.report_owed`): the
    file the head's `report` names, as the state holds it, carries the
    result block of the declared run or the protocol's handover block —
    else one blocker; nothing registered or not delivered: []. The file
    is read relative to the area's layout root (`Checked.repo`: the git
    repository where there is one), from the index when the state is the
    index. Not held on the PROPOSED state — the adoption's own check of the
    protocol it is about to write: the result block can only be written
    after the declaration (`--into`), so holding the report there held the
    adoption against itself (route probe, 2026-10-29: `--from-run` refused
    for the missing block, `--into` for the missing declaration); the stop
    and the commit hold the delivered report."""
    if ctx.state == PROPOSED:
        return []
    gap = report_owed(
        ctx.protocol, ctx.text, ctx.declared, ctx.repo, staged=ctx.state == INDEX
    )
    return [] if gap is None else [gap]


def adoption_order_note(blocked: list[str]) -> str | None:
    """The order to tell when BLOCKED (the blocker messages) names an adoption
    (a `labkit-adopt` line, `repo.ADOPT_TOOL`) beside blockers that are not
    themselves projections of one (an adoption, a `--from-run` or `--render`
    rewrite): adoption runs this check and is refused while any of them
    stands, so they come first. None otherwise — then the adoption line is
    the way out as printed. Why: printed bare, the adoption line beside an
    open BLOCKER on that run read as the fix to three of three Haiku readers
    (docs/usability/2026-10-28-haiku-stuck-reading.md)."""
    projections = (ADOPT_TOOL, "--from-run", "--render")
    adoption = [m for m in blocked if ADOPT_TOOL in m]
    other = [m for m in blocked if not any(p in m for p in projections)]
    if not adoption or not other:
        return None
    return (
        f"  adoption comes last: `{ADOPT_TOOL}` runs report-check itself and is "
        f"refused while any of the {len(other)} other blocker(s) above stands — "
        f"clear them first, or hand the area over; the `{ADOPT_TOOL}` line names "
        f"the last step, not the fix"
    )


def held_declaration(ctx: Checked, finalized: list[GateFinding]) -> Path | None:
    """The protocol of CTX when it declares the run that answers and
    finalize's blockers (FINALIZED) found that run's code changed since it
    ran (`changed since <run>`); None otherwise. While so, every later hold
    names the withdrawal first (`ways_out.declared_first`): the declared
    number no longer holds for the code, the commit hook holds the code to
    it, and an audit made while it stands declared does not cover the next
    run."""
    if ctx.run is None or ctx.declared != ctx.run.name:
        return None
    mark = f"changed since {ctx.declared}"
    return ctx.protocol if any(mark in f.text for f in finalized) else None


def withdrawn_first(
    found: list[GateFinding], held_by: Path | None
) -> list[GateFinding]:
    """FOUND, each blocker's way out after the withdrawal of HELD_BY's
    declaration when there is one (`held_declaration`)."""
    if held_by is None:
        return found
    return [ways_out.declared_first(f, held_by) for f in found]


def tell_adoption_order(findings: Findings) -> None:
    """Tell `adoption_order_note` through FINDINGS when it applies."""
    order = adoption_order_note(findings.blocked)
    if order:
        findings.note(order)


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


def if_reported(paths: list[Path], repo: Path, *, staged: bool) -> int:
    """`report-check` for every protocol of an area one of PATHS touches
    whose head declares a result, and for every report among PATHS
    (`report_files`): the gate at the stop and the commit. A result declared
    reported is held to the whole chain, a protocol declaring none is
    skipped (an exploration may end with no reported result). A report
    that is a symbolic link is refused alone, naming the copy that replaces
    it; its other checks wait for that copy. A report's generated blocks
    are held to the protocols they name, which the stations hold too, its
    cited run ids to the repo's runs; its other numbers are hints. STAGED
    (the pre-commit): declarations and reports are
    read from the index, and an area whose tree differs from the index is a
    blocker — the stations read the tree, the commit holds the index.
    A protocol among them whose declaration differs from HEAD's
    (`newly_declared`) reaches the committed reports citing that run
    (`committed_reports`): they are held as if changed, since the number
    they show became a declared result in this very state (the two-step
    commit of the sixth haiku round, 2026-10-23). A committed report that
    discusses a run of an area PATHS touch is held too
    (`discussing_reports`): its review read that area. A protocol whose
    head registers a file among PATHS as its report is held too
    (`registering_protocols`): the report lies in no area, and a change
    of it reaches the protocol that owes it its result
    (`report_hold.report_owed`, through `hold_declared`). Returns the worst
    exit code."""
    protocols = affected_protocols(paths, repo, staged=staged)
    for p in registering_protocols(paths, repo, staged=staged):
        if p not in protocols:
            protocols.append(p)
    reports = report_files(paths, repo, staged=staged)
    reached = reached_reports(protocols, reports, repo, staged=staged)
    held = {p for p, _ in reports} | {p for p, _, _ in reached}
    reached += discussing_reports(paths, held, repo, staged=staged)
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
        worst = max(worst, hold_report(path, text, repo, sources, staged=staged))
    for path, text, held_as in reached:
        worst = max(
            worst,
            hold_report(path, text, repo, sources, held_as=held_as, staged=staged),
        )
    return worst


def hold_declared(protocol: Path, repo: Path, *, staged: bool) -> int:
    """`report-check` on PROTOCOL when its head declares a result, as the
    state holds it (the index when STAGED); for an exploration only its
    registered report's obligation (`hold_registered`); 0 for a protocol
    the commit does not hold, 2 for one that cannot be read or is a
    symbolic link in that state (`repo.protocol_links`)."""
    link = protocol_links(repo, [protocol], staged=staged)
    if link:
        console.refuse("report-check", link[protocol])
        return 2
    try:
        text = state_text(repo, protocol, staged=staged)
    except (OSError, UnicodeError) as exc:  # a refusal, never a traceback
        console.refuse("report-check", f"{protocol}: {exc}")
        return 2
    if text is None:
        if staged:
            return 0  # not in the commit: nothing declared there
        console.refuse("report-check", f"{protocol}: no such file")
        return 2
    declared, gap = declaration(text)
    if declared is None and gap is None:
        # an exploration: nothing declared; its registered report, once
        # delivered, is owed the handover or the result all the same
        return hold_registered(protocol, text, repo, staged=staged)
    print(
        f"═══ report-check {protocol} (its head has adopted "
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


def hold_registered(protocol: Path, text: str, repo: Path, *, staged: bool) -> int:
    """The registered report's obligation of PROTOCOL, a protocol that
    declares no result (`report_hold.report_owed` with no declared run):
    0 when the head registers no report, the file is not delivered in the
    state, or it carries the protocol's handover block; 1 held, the
    blocker told under its own heading. Raises `protocol_block.BlockError`
    on a head that does not read — the caller read the declaration off
    the same text first."""
    gap = report_owed(protocol, text, None, repo, staged=staged)
    if gap is None:
        return 0
    print(
        f"═══ report-check {protocol} (its head has adopted no result; its "
        f"registered report is delivered) ═══"
    )
    out = Findings()
    out.take(gap)
    return out.report("report-check", "reporting")


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
            "    every protocol of an area a path touches whose head has adopted a\n"
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
