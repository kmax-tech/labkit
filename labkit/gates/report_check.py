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
(`hold_reported`, `hold_declared`; the command line is `tools.report_command`): the order and the conditions of
what runs stand here. The context every station reads is
`report_context.checked`; the replacement station lives in
`report_replacement`, the stations on the audit decisions (limits, reviews,
follow-up) in `report_decisions`. Finding the reports a change reaches and what holds
each lives in `report_hold`, which `hold_reported` calls after the protocols.

`finalize` holds the run before the number is written back and comes
before the analysis audit; report-check comes last and holds the whole
chain, at every repeat cost (why each station holds what it holds:
docs/notes/2026-10-19-hooks-and-report-check.md). The stations, their
order and every condition under which one runs stand in one place,
`chain_gaps` — its docstring is the plan, its body keeps each `if` —; it
is the one list `report_check` prints and `next_step` reads. A blocker
does not stop later stations. The gate reads and runs checks; it does not
itself write the protocol or run records.

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
declared or not (`registered_report.report_owed`, `hold_registered`); a
report with the run id removed, a run id typed in, or a discussion block
releases nothing.
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
owes its block now. An old citation of a run whose declaration did not change
reopens nothing.

`--staged` is the pre-commit's form. The commit holds the index, the
stations read the working tree: so the declaration is read from the index
(`repo.state_text` — an answer only the tree carries is not in the commit), and
an area whose tree differs from the index (`report_hold.staged_area_gap`: a file modified
and not staged, or untracked) is a blocker before any station runs, since
the check would judge a state the commit does not hold.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from labkit.formats import commands
from labkit.formats.gate import GUARANTEED
from labkit.formats.runs import RunDir
from labkit.formats.gate import (
    BLOCKER,
    WARNING,
    Findings,
    GateFinding,
    blocker,
    outcome_of_failed_read,
    withdrawn_first,
)
from labkit.formats.answering_run import (
    adopted_run,
    is_measurement,
)
from labkit.formats.area_state import (
    FileState,
    file_state_of,
    AreaState,
    LOST_RUN_SENTENCE,
    PROPOSED,
    TREE,
    gone_run_restore,
    state_of,
)
from labkit.formats.repo import pending_adoption
from labkit.formats import evidence
from labkit.formats.protocol_history import (
    NO_COMMIT,
    UNKNOWN_COMMIT,
    UNREADABLE_COMMIT,
    committed_at,
    registration_missing,
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
from labkit.gates.finalize import finalize_area, unreportable_warnings
from labkit.gates.preflight import area_test_python, contract_hint
from labkit.gates import ways_out
from labkit.gates.report_hold import (
    Sources,
    discussing_reports,
    discussion_review_findings,
    held_by_reports,
    hold_report,
    reached_reports,
    registering_protocols,
    repo_sources,
    report_files,
    staged_area_gap,
)
from labkit.gates.registered_report import (
    formerly_registering,
    missing_report,
    report_binding_gap,
    report_owed,
)
from labkit.formats.protocol_check import REPEATED_WAY_OUT, check_fields
from labkit.formats.repo import (
    area_protocols,
    choose_protocol,
    git_root,
    protocol_links,
    protocols_in,
    shown,
    state_text,
)
from labkit.formats.commands import (
    ADOPT,
    ADOPT_TOOL,
    RENDER,
    adopt_command,
    audit_command,
    freeze_command,
    gate_command,
    measure_command,
    withdraw_command,
)
from labkit.formats.runs import read_run_config, unreportable
from labkit.formats.scope_sha import area_files, areas_touched
from labkit.formats.standard_contract import (
    ANALYSIS_AUDIT,
    CHECK_FLAG,
    CHECK_SCRIPT,
    check_command,
    lane,
)
from labkit.gates.report_context import (
    Checked,
    checked,
    declaration,
)
from labkit.gates.report_decisions import followup_findings, limit_gaps, review_findings
from labkit.gates.report_replacement import replacement_gaps


#: how long `--check` may take inside the gate
CHECK_TIMEOUT_S = 300.0


def check_analysis_script(area: Path, repo: Path) -> str | None:
    """Why the area's check (`standard_contract.check_command`: the analysis
    script's `--check`, stamped by every skeleton) does not pass, or None:
    no script, or a nonzero exit with the last lines it printed."""
    script = CHECK_SCRIPT
    if area / script not in area_files(area):
        return (
            f"no {script} — the check that holds the note to the run is owed; "
            f"copy it from labkit/templates/: analyze-quick-script.py.template "
            f"for a computation, analyze-script.py.template for a fit or an "
            f"apply, as {script}"
        )
    try:
        r = subprocess.run(
            [area_test_python(repo), *check_command(area)],
            cwd=repo,
            capture_output=True,
            text=True,
            errors="replace",  # the tail is quoted, not parsed: a byte no
            # codec reads must not raise out of the gate
            timeout=CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"{script} --check did not finish in {CHECK_TIMEOUT_S:g} s"
    if r.returncode == 0:
        return None
    tail = (r.stderr.strip() or r.stdout.strip() or "no output").splitlines()[-3:]
    return f"{script} --check exits {r.returncode}: " + " | ".join(tail)


def freeze_gaps(ctx: Checked, *, repeated: bool) -> list[GateFinding]:
    """Why the freeze does not hold — the flag unset, or a must
    gap protocol-check names (the stamp's `<…>` promise sentences among them);
    REPEATED: a bound field written more than once too (`repeated_gaps`)."""
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
                f"then `{freeze_command(ctx.protocol)}`",
                step=freeze_command(ctx.protocol),
            )
        ]
    )
    report = check_fields(ctx.text)
    gaps += [
        blocker(f"{name}: {label}", fix=f"write the field; {fields}")
        for label in report.missing_must
    ]
    # a must field still holding its `<…>` placeholder blocks here as
    # protocol-check and preflight refuse it
    gaps += [
        blocker(
            f"{name}: line {n}: {label} still a placeholder",
            fix=f"replace it with this protocol's own text; {fields}",
        )
        for n, label in report.must_holes
    ]
    return gaps + (repeated_gaps(ctx) if repeated else [])


def repeated_gaps(ctx: Checked) -> list[GateFinding]:
    """A blocker per bound field CTX's text writes more than once
    (`protocol_check.FieldReport.repeated`): which copy is registered
    cannot be told."""
    return [
        blocker(
            f"{ctx.protocol.name}: {twice}",
            fix=f"{REPEATED_WAY_OUT}; then `{gate_command('protocol-check', ctx.protocol)}`",
        )
        for twice in check_fields(ctx.text).repeated
    ]


def registration_gaps(ctx: Checked) -> list[GateFinding]:
    """The committed registration where the lane owes it instead of the freeze
    (seconds): the registration stood in the protocol as committed at the
    first measurement — the commit its record names (`runs.recorded_commit`)
    — at each run `area_state.Measured.firsts` names: git's history
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
    without a stamped id."""
    if ctx.head.id is None:
        return []
    root = git_root(ctx.protocol)
    first = ctx.area_state.measured_of(ctx.head.id).firsts
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
    assert cfg is not None, "the first measurements are read runs only"
    at = f"the first measurement {rd.dir.name}"
    # several are first on diverged history or beside a run git cannot
    # place: without the why, a reader takes the second blocker for a bug
    among = "" if held == 1 else f"; one of {held} that git's history does not order"
    then = committed_at(ctx.protocol, rd, root)
    commit = then.commit
    # what stood before the number cannot be repaired afterwards: a new
    # registration, committed before its own first run, or the handover
    anew = (
        "when the missing choices can be made on grounds the new registration "
        f"states, {commands.register_anew(str(ctx.head.id))}; else "
        f"{ways_out.HANDOVER}"
    )
    if then.cause == NO_COMMIT:
        return [
            blocker(
                f"{at} recorded no commit ({cfg.git!r}{among}) — the registration "
                f"cannot be held to what stood before the number (LAB-003 No run "
                f"without an intent paragraph)",
                fix=anew,
            )
        ]
    if then.cause == UNKNOWN_COMMIT:
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
    assert commit is not None, "a recorded commit the repository holds"
    if then.cause == UNREADABLE_COMMIT:
        return [
            blocker(
                f"{ctx.protocol.name} at {at} ({commit[:12]}{among}) cannot be read: "
                f"{then.detail} — the registration that stood before the number "
                f"cannot be told (LAB-003 No run without an intent paragraph)",
                fix=f"make it readable: restore the repository's missing objects "
                f"(`git fsck` names them) or fetch them from a clone that has them "
                f"(`git fetch`), then `{gate_command('report-check', ctx.area)}`; "
                f"where they are lost, {anew}",
            )
        ]
    if then.text is None:
        return [
            blocker(
                f"{ctx.protocol.name} was not committed at {at} ({commit[:12]}{among}) "
                f"— nothing stood before the number; the registration is what the "
                f"commit of the first measurement holds (LAB-003 No run without an "
                f"intent paragraph)",
                fix=anew,
            )
        ]
    missing = registration_missing(then.text, ctx.head.kind)
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
            step=measure_command(ctx.area),
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
            check_outcome=outcome_of_failed_read(exc),
        )
    if gap is None:
        return None
    # the way out is a new audit, and `attempts.begin` refuses every attempt
    # while one of these stands, so the blocker names the loss, never
    # "none has run yet" or `--mode analysis`
    lost = list(ctx.evidence.gaps) if not covering else []
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
    run = measure_command(ctx.area)
    measure = f"`{run}`"
    cfg = read_run_config(ctx.run)
    if cfg is None:
        return [
            blocker(
                f"{ctx.run.name}: no config.json in this file state — the run's "
                f"record cannot be checked",
                fix=f"measure through runlog: {measure}",
                step=run,
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


#: what names a finding of the nested finalize in this gate's output
FINALIZE = "finalize: "


#: where a gate's lines go as they are found: `print` on the console; a
#: hook that tells them elsewhere passes its own (`hold_reported`)
Tell = Callable[[str], None]


@dataclass(frozen=True)
class ProtocolVerdict:
    """report-check's verdict on one protocol: EXIT (0 clean or warnings
    only, 1 a blocker, 2 no context) and CHAIN, what the chain found
    (`ReleaseChain`) — None where it did not run: an early end, a staged
    area whose tree differs from the index, a protocol that declares no
    result."""

    exit: int
    chain: ReleaseChain | None


def protocol_verdict(
    area: Path,
    protocol: Path | None = None,
    *,
    file_state: FileState = TREE,
    text: str | None = None,
    review: bool = True,
    tell: Tell = print,
    area_state: AreaState | None = None,
    area_evidence: evidence.AreaEvidence | None = None,
) -> ProtocolVerdict:
    """Check AREA before reporting (`ProtocolVerdict`: the exit code and what the
    chain found), every line through TELL.

    0. Choose the protocol and read Checked; missing or unreadable ends with 2
       — the only early end.
    1. The chain (`chain_gaps`: its stations, their order and conditions),
       every finding told; an adoption named beside other blockers is told
       as the last step (`tell_adoption_order`).
    2. Summary: 1 with any blocker, otherwise 0.

    FILE_STATE and TEXT name the declaration's file state: the tree by default,
    the index for the pre-commit, the written proposal for adoption. REVIEW
    false leaves the registered report's review out — `labkit-adopt`'s own
    check right after it wrote the block: the review reads the final text,
    which comes after. The nested finalize reads the context's state and
    evidence (`finalize_findings`); the analysis script reads its own
    inputs. AREA_STATE and AREA_EVIDENCE, when a hold over several paths
    built them (`report_hold.Sources`), are the context's
    (`report_context.checked`). A refusal before the chain goes to stderr
    (`console.refuse`), not through TELL.
    """
    # 0. protocol and context — the only early end
    chosen = choose_protocol(area, protocol, "report-check")
    if chosen is None:
        return ProtocolVerdict(2, None)
    try:
        ctx = checked(
            area,
            chosen,
            file_state=file_state,
            text=text,
            area_state=area_state,
            area_evidence=area_evidence,
        )
    except (protocol_block.BlockError, AuditError) as exc:
        console.refuse("report-check", f"{chosen.name}: {exc}")
        return ProtocolVerdict(2, None)
    tell(
        f"  {chosen.name}: read from the {ctx.file_state}; the head has adopted "
        f"{ctx.declared or 'no run'}; the answering run is "
        f"{ctx.run.name if ctx.run is not None else 'none — ' + ctx.why}"
    )
    ln = lane(ctx.head.repeat_cost)
    findings = Findings(
        tell,
        area=shown(ctx.area, Path.cwd()),
        audit=audit_command(ctx.area, protocol=ctx.protocol).line,
    )
    if not ln.freeze:
        tell(
            f'  {ctx.protocol.name}: repeat_cost = "{ctx.head.repeat_cost}" — no freeze and no preflight '
            f"audit owed (LAB-017 The number of audits follows the cost tier); the "
            f"registration as committed at the first measurement, the full run, "
            f"the analysis audit and the check are owed instead"
        )
    # 1. the chain
    chain = chain_gaps(ctx, review=review)
    findings.take_all(chain.found)
    # adoption last — an adoption line beside other blockers is the last
    # step, not the fix
    tell_adoption_order(findings)

    # 2. summary — 1 with a blocker, otherwise 0
    if not findings.blocked:
        held = ("frozen, " if ln.freeze else "") + "finalized, audited, checked"
        tell(f"  {chosen.name}: {held}")
    return ProtocolVerdict(findings.report("report-check", "reporting"), chain)


def without_unreportable_warnings(
    finalized: list[GateFinding], run: Path | None
) -> list[GateFinding]:
    """FINALIZED, finalize's findings (`finalize_findings`), without the
    warnings it tells for RUN's marks that make its number unreportable
    (`finalize.unreportable_warnings`, the one spelling) — the full-run
    station holds the same marks as blockers. FINALIZED as it is without a
    run."""
    if run is None:
        return finalized
    told = {FINALIZE + line for line in unreportable_warnings(run)}
    return [f for f in finalized if not (f.grade == WARNING and f.text in told)]


def cut_off_adoption_gaps(ctx: Checked) -> list[GateFinding]:
    """A blocker while an adoption was cut off during its check: the head may
    hold a proposal no check passed (`repo.pending_adoption`);
    never on the proposal itself, which that adoption is checking."""
    if ctx.file_state == PROPOSED or not ctx.area_state.adoption_pending_for(
        ctx.protocol
    ):
        return []
    return [
        blocker(
            f"{ctx.protocol.name}: an adoption was cut off during its check — "
            f"the protocol may hold a proposal no check passed "
            f"({pending_adoption(ctx.protocol).name} keeps it as it was before)",
            fix=f"`{adopt_command(ctx.protocol)}` puts it back first and adopts again",
            step=adopt_command(ctx.protocol),
        )
    ]


def declaration_gaps(ctx: Checked) -> list[GateFinding]:
    """A blocker when CTX's `[result]` table does not read
    (`Checked.declaration_gap`)."""
    if not ctx.declaration_gap:
        return []
    return [
        blocker(
            f"{ctx.protocol.name}: {ctx.declaration_gap}",
            fix=f"`{withdraw_command(ctx.protocol)}` removes it; audit the run "
            f"that answers, then `{adopt_command(ctx.protocol)}` writes the "
            f"`[result]` table for it",
            step=withdraw_command(ctx.protocol),
        )
    ]


def report_binding_gaps(ctx: Checked, *, unread: bool) -> list[GateFinding]:
    """The report CTX's head registers against the one its first
    measurements stood under (`registered_report.report_binding_gap`, UNREAD
    passed on), as a list."""
    gap = report_binding_gap(
        ctx.protocol,
        ctx.text,
        measured=ctx.area_state.measured_of(ctx.head.id),
        unread=unread,
    )
    return [] if gap is None else [gap]


def finalize_findings(
    area: Path, protocol: Path, state: AreaState, held: evidence.AreaEvidence
) -> list[GateFinding]:
    """Finalize's blockers and warnings, each named here with its prefix
    (`FINALIZE`) — a hook that says "run it to see them" asks for a round
    trip the agent does not take, and a warning dropped here would reach
    no one who ran report-check, the stop or the commit. finalize runs on a
    silent collector (`Findings(tell=None)`): its findings arrive as data
    and its headers and notes reach nothing, so finalize puts every reason
    into the finding itself (the runs it looked at, intent-check's lines,
    the test counts) and keeps its exit-2 reason (no protocol to hold) as a
    blocker too. A non-zero exit without a blocker is a bug in finalize,
    not a state to report around. STATE and HELD, the area's state and
    audit evidence the check built once, are finalize's too."""
    collected = Findings(tell=None)  # the data, not the console
    finalized = finalize_area(area, protocol, collected, state=state, held=held)
    if finalized != 0 and not collected.blocked:
        raise RuntimeError(
            f"finalize {area} exits {finalized} and kept no blocker — every "
            f"reason finalize has must be a finding"
        )
    return [replace(f, text=FINALIZE + f.text) for f in collected.found]


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
    # under "analysis audit:" a retyped Recorded results line reads as a
    # record problem
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


@dataclass(frozen=True)
class ReleaseChain:
    """What report-check's chain found for one protocol in one file state
    (`chain_gaps`): FOUND, every blocker and warning in the chain's order;
    HELD_BY, the protocol whose declaration every later hold withdraws
    first (`held_declaration`; None when none does)."""

    found: list[GateFinding]
    held_by: Path | None

    @property
    def blockers(self) -> list[GateFinding]:
        """The blockers of FOUND, in the chain's order."""
        return [f for f in self.found if f.grade == BLOCKER]


def chain_gaps(
    ctx: Checked, *, undeclared: bool = False, review: bool = True
) -> ReleaseChain:
    """Every finding report-check holds CTX to, in the order of the chain —
    the one list `report_check` prints and `next_step` reads (`ReleaseChain`):

    0. Evidence: an adoption cut off during its check, then a change of the
       area's committed evidence that breaks its rule
       (`evidence.change_blockers`; in the index for INDEX, else in the
       tree) — its restore comes before any other step.
    1. Declaration: an unreadable `[result]` blocks.
    2. Registration: the freeze where the lane owes it, else the first
       measurement's committed registration where the lane owes that; a
       declared replacement's changes; the report registered before the
       first measurement (`registered_report.report_binding_gap`).
    3. Finalize: its blockers and warnings, always (`finalize_findings`).
    4. Full run: reportability, only when an answering run exists.
    5. Analysis: coverage and rendered results where the lane owes it,
       with an answering run — without one (where finalize reads CTX's
       text) finalize's run choice is the one blocker.
    6. Recomputation: the analysis script's `--check`, always.
    7. Decisions: reviews and follow-ups where the lane owes the analysis.
    8. Report: the registered report, once delivered in CTX's state, and
       the review every report discussing a run of the protocol owes
       (`report_hold.discussion_review_findings` — the hold the stop and
       the commit hold such a report with, named here so that `next`
       names the same step; REVIEW False leaves it out).

    Every applicable station runs despite earlier blockers; a declared run
    whose code changed puts the withdrawal before every later hold
    (`withdrawn_first`). One cause is one blocker: where finalize reads the
    text CTX holds (every state but the adoption's proposal, `same_text`),
    a cause finalize already holds is not held a second time — no answering
    run (left out of station 5), a field written twice (left out of station
    2), the marks that make a run unreportable (finalize's warning left out
    beside station 4's blocker). Finalize's own stations are named by what
    they check, never by number, here.
    UNDECLARED (no run adopted yet, the one a next step asks about):
    the stations the adoption writes and holds on its proposal — the result
    section (`report_decisions.limit_gaps`), the recomputation, the report —
    are left out, since the tree cannot pass them before the adoption
    writes them; `protocol_fill.adopt` checks the whole proposal. Prints
    nothing."""
    ln = lane(ctx.head.repeat_cost)
    # finalize reads the protocol as the tree holds it — the text CTX holds
    # in every state but the proposal an adoption checks: for INDEX the
    # tree equals the index, since `hold_declared` and `next_step` hold an
    # area whose tree differs from it before the chain (`staged_area_gap`)
    same_text = ctx.file_state != PROPOSED
    # 0. evidence — an adoption cut off, then committed evidence changed
    out = cut_off_adoption_gaps(ctx)
    out += ctx.evidence.change_blockers()
    # 1. declaration
    out += declaration_gaps(ctx)
    # 2. registration — the freeze where the lane owes it, else the
    # committed registration where the lane owes that
    if ln.freeze:
        # a field written twice: finalize's open-fields station holds it on
        # the text it reads
        out += freeze_gaps(ctx, repeated=not same_text)
    elif ln.registration:
        out += registration_gaps(ctx)
    out += replacement_gaps(ctx)
    # the commits the registration station names unreadable are its to name
    # where it ran (`report_binding_gap`'s UNREAD)
    out += report_binding_gaps(ctx, unread=not ln.registration)
    # 3. finalize — always; the unreportable marks this chain's full-run
    # station holds as blockers are not told again as finalize's warnings
    # where it read this text
    finalized = finalize_findings(ctx.area, ctx.protocol, ctx.area_state, ctx.evidence)
    if same_text:
        finalized = without_unreportable_warnings(finalized, ctx.run)
    out += finalized
    held_by = held_declaration(ctx, finalized)
    # while the declared run's code changed, every later hold names the
    # withdrawal first (`gate.withdrawn_first`, the datum `withdraw_first`)
    withdrawal = withdraw_command(held_by) if held_by is not None else None
    # 4. full run — only with an answering run
    if ctx.run is not None:
        out += withdrawn_first(unreportable_gaps(ctx, ln.freeze), withdrawal)
    # 5. analysis — where the lane owes it and an answering run exists;
    # without one, finalize's run-choice station holds it where it reads
    # this text
    if ANALYSIS_AUDIT in ln.audits and (ctx.run is not None or not same_text):
        analysis = analysis_findings(
            ctx, ln.analysis_rule, result_section=not undeclared
        )
        out += withdrawn_first(analysis, withdrawal)
    # 6. recomputation — always, unless `undeclared`
    if not undeclared:
        out += withdrawn_first(recomputation_findings(ctx.area, ctx.repo), withdrawal)
    # 7. decisions — where the lane owes the analysis
    if ANALYSIS_AUDIT in ln.audits:
        out += withdrawn_first(review_findings(ctx), withdrawal)
        out += withdrawn_first(followup_findings(ctx), withdrawal)
    # 8. report — unless `undeclared`; its review not on the proposal:
    # its text is in every review's fingerprint, so the adoption would hold
    # itself (`report_findings` says why)
    if not undeclared:
        out += report_findings(ctx, review=review)
    if review and ctx.file_state != PROPOSED:
        out += discussion_review_findings(
            ctx.protocol,
            ctx.text,
            ctx.repo,
            staged=ctx.staged,
            state=ctx.area_state,
            held=ctx.evidence,
        )
    return ReleaseChain(out, held_by)


def adoption_state(area: Path, protocol: Path, text: str) -> handovers.RunAccount:
    """Where PROTOCOL of AREA, as TEXT holds it, stands for an adoption —
    the account a handover records (`handovers.RunAccount`):

    - NOT_MEASURED: no measurement bound to it (completed or not) and none
      unreadable (`area_state.Measured`) — a preparation or probe run
      measures nothing;
    - UNUSABLE: a measurement of it, and no number from it — the run choice
      holds (no completed run, an unreadable or same-second rival:
      `answering_run.bound_answering_run`), it chose a run that is no
      measurement, the metrics.json does not read, or every measurement's
      directory is gone (a commit holds it, or only the local index names
      it); the run is the newest measurement, WHY the sentences that put
      it there;
    - HELD: the answering run, and the blockers report-check holds its
      adoption with (`chain_gaps`, the adoption pending; an audit that
      cannot be held to the run among them);
    - ADOPTABLE: the answering run, and nothing holds it.

    Prints nothing. Raises `protocol_block.BlockError` on a head that does
    not read, `runs.RunConfigError` from a run's config.json,
    `run_index.RunIndexError` from a run index that does not read."""
    pid = protocol_block.head(text).id
    if not pid:
        return handovers.RunAccount(None, handovers.NOT_MEASURED, ())
    state = state_of(area)
    held = state.measured_of(pid)
    measured = [rd for rd in held.present if is_measurement(rd)]
    if not measured:
        # measured and deleted since: git or the index keeps them, so a
        # handover never says "no run of it was measured" over deleted runs
        gone = {
            rd.dir.name: f"{rd.dir.name}: measured, and runs/{rd.dir.name}/ is gone — "
            f"{gone_run_restore(rd)}"
            for rd in held.deleted
            if is_measurement(rd)
        } | {
            r: f"{r}: measured (runs.tsv lists it), and runs/{r}/ is gone — "
            f"{LOST_RUN_SENTENCE}"
            for r in held.lost
        }
        if gone:
            return handovers.RunAccount(
                max(gone), handovers.UNUSABLE, tuple(gone[r] for r in sorted(gone))
            )
        return handovers.RunAccount(None, handovers.NOT_MEASURED, ())
    choice = held.answering(adopted_run(text))
    if choice.run_dir is None or not any(rd.dir == choice.run_dir for rd in measured):
        # why each measurement was left out of the choice
        _, left = held.bound()
        ours = {rd.dir for rd in measured}
        why = [f"{f.dir.name}: {f.why or f.state}" for f in left if f.dir in ours]
        why += [choice.blocker] if choice.blocker else []
        if choice.run_dir is not None:
            why.append(f"{choice.run_dir.name}, the run chosen, is no measurement")
        newest = max(rd.dir.name for rd in measured)
        return handovers.RunAccount(newest, handovers.UNUSABLE, tuple(why))
    run = choice.run_dir.name
    try:
        runs.read_metrics(runs.metrics_path(choice.run_dir))
    except runs.MetricsError as exc:
        return handovers.RunAccount(run, handovers.UNUSABLE, (str(exc),))
    try:
        ctx = checked(area, protocol, text=text, area_state=state)
    except AuditError as exc:
        # the audit cannot be held to the run: that holds the adoption too
        return handovers.RunAccount(run, handovers.HELD, (str(exc),))
    held = tuple(
        g.text
        for g in chain_gaps(ctx, undeclared=ctx.declared is None, review=False).blockers
    )
    state = handovers.HELD if held else handovers.ADOPTABLE
    return handovers.RunAccount(run, state, held)


def report_findings(ctx: Checked, *, review: bool = True) -> list[GateFinding]:
    """The registered report's obligation (`registered_report.report_owed`): the
    file the head's `report` names, as the state holds it, carries the
    result block of the declared run or the protocol's handover block —
    else one blocker; nothing registered: []. Not delivered: held where a
    result is adopted, or where the commit removes a report HEAD holds
    (`registered_report.missing_report`); else [] — before the adoption the stop
    names a report not yet written. The file is read relative to the area's layout root (`Checked.repo`: the git
    repository where there is one), from the index when the state is the
    index. Not held on the PROPOSED state — the adoption's own check of the
    protocol it is about to write: the result block can only be written
    after the declaration (`--into`), so holding the report there would
    hold the adoption against itself; the stop and the commit hold the
    delivered report. REVIEW: the released report
    owes a clean report review of its state too (`report_owed`)."""
    if ctx.file_state == PROPOSED:
        return []
    # before the adoption the tree's missing report is the stop's to name
    # (`agent_hooks.missing_reports`); a commit removing it is held here
    staged = ctx.staged
    gone = (
        missing_report(
            ctx.protocol,
            ctx.text,
            ctx.repo,
            measured=ctx.area_state.measured_of(ctx.head.id),
            staged=staged,
            declared=ctx.declared,
        )
        if staged or ctx.declared is not None
        else None
    )
    if gone is not None:
        return [gone]
    gap = report_owed(
        ctx.protocol,
        ctx.text,
        ctx.declared,
        Sources.blank(
            ctx.repo,
            staged=staged,
            states={ctx.area: ctx.area_state},
            held={ctx.area: ctx.evidence},
        ),
        review=review,
    )
    return [] if gap is None else [gap]


def adoption_order_note(blockers: list[GateFinding]) -> str | None:
    """The order to tell when BLOCKERS name an adoption (a finding whose
    step is `commands.ADOPT`) beside blockers that are not themselves
    projections of one (an adoption, or a rewrite of the result section,
    step `commands.RENDER`): adoption runs this check and is refused while any
    of them stands, so they come first. None otherwise — then the adoption
    line is the way out as printed. Printed bare, the adoption line beside
    an open BLOCKER on that run reads as the fix. Read from the steps,
    never from the words."""
    adoption = [f for f in blockers if f.step is not None and f.step.name == ADOPT]
    other = [
        f for f in blockers if f.step is None or f.step.name not in (ADOPT, RENDER)
    ]
    if not adoption or not other:
        return None
    return (
        f"  adoption comes last: `{ADOPT_TOOL}` runs report-check itself and is "
        f"refused while any of the {len(other)} other blocker(s) above stands — "
        f"clear them first, or hand the area over; the `{ADOPT_TOOL}` line names "
        f"the last step, not the fix"
    )


def held_declaration(ctx: Checked, finalized: list[GateFinding]) -> Path | None:
    """The protocol of CTX when it declares the run that answers and one of
    finalize's blockers (FINALIZED) found the code of that run, or of a run
    it derives from, or a declared scope changed since it ran
    (`GateFinding.changed_since`, the comparison's own datum, never its
    words; code that could not be compared sets none); None otherwise.
    While so, every later hold
    names the withdrawal first (`gate.withdrawn_first`): the declared
    number no longer holds for the code, the commit hook holds the code to
    it, and an audit made while it stands declared does not cover the next
    run. Not on the PROPOSED state: the adoption's own check sees its
    proposal declare the run, and "withdraw the adoption first" would name
    an adoption that does not stand."""
    if ctx.file_state == PROPOSED or ctx.run is None or ctx.declared != ctx.run.name:
        return None
    held = any(f.changed_since is not None for f in finalized)
    return ctx.protocol if held else None


def tell_adoption_order(findings: Findings) -> None:
    """Tell `adoption_order_note` through FINDINGS when it applies."""
    order = adoption_order_note([f for f in findings.found if f.grade == BLOCKER])
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
    areas = areas_touched(paths, repo, staged=staged)
    if not staged:
        # the tree's protocols in the form the area was reached in: the
        # stations compare them with the paths as given, not resolved
        return [p for area in sorted(areas) for p in area_protocols(area)]
    indexed = protocols_in(repo, staged=True)
    return [p for area in sorted(areas) for p in indexed if p.parent == area]


@dataclass(frozen=True)
class Touched:
    """What the state a change holds reaches (`reached_by`): PROTOCOLS,
    each once; REPORTS, the (path, text) of every report among the changed
    paths (`report_hold.report_files`); SOURCES, the repo's protocols and
    runs read for them (`repo_sources`; empty when no report is among the
    paths)."""

    protocols: list[Path]
    reports: list[tuple[Path, str]]
    sources: Sources


def reached_by(paths: list[Path], repo: Path, *, staged: bool) -> Touched:
    """Every protocol the state PATHS change reaches, each once, with the
    reports among PATHS and the sources read for them (`Touched`): the
    protocols of the areas PATHS touch (`affected_protocols`), those whose
    head registers a path among them as their report
    (`report_hold.registering_protocols`), those whose first measurements
    did (`formerly_registering`), and those a report among PATHS shows a
    result of (`held_by_reports`: a block names it, or its prose cites a
    run the protocol declares) — the index's when STAGED, the tree's
    otherwise. The one reader for the gate (`hold_reported`) and for the
    step printed beside its hold (`next_step.steps_for`): read apart, a
    protocol the index holds and the tree deleted, or a report at the root
    citing an adopted run, would be held with no step beside it."""
    protocols = affected_protocols(paths, repo, staged=staged)
    reports = report_files(paths, repo, staged=staged)
    sources = (
        repo_sources(repo, staged=staged)
        if reports
        else Sources.blank(repo, staged=staged)
    )
    for p in [
        *registering_protocols(paths, repo, staged=staged),
        *formerly_registering(paths, repo, sources),
    ]:
        if p not in protocols:
            protocols.append(p)
    for p in held_by_reports(reports, sources):
        if p not in protocols:
            protocols.append(p)
    return Touched(protocols, reports, sources)


@dataclass(frozen=True)
class HoldVerdict:
    """What `hold_reported` found: EXIT, the worst exit code of every hold;
    CHAINS, per protocol whose chain ran (a declared result), what it found
    — the chain a step printed beside the hold reads instead of running it
    again (`next_step.steps_for`)."""

    exit: int
    chains: dict[Path, ReleaseChain]


def hold_reported(
    paths: list[Path], repo: Path, *, staged: bool, tell: Tell = print
) -> HoldVerdict:
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
    they show became a declared result in this very state. A committed report that
    discusses a run of an area PATHS touch is held too
    (`discussing_reports`): its review read that area. A protocol whose
    head registers a file among PATHS as its report is held too
    (`registering_protocols`): the report lies in no area, and a change
    of it reaches the protocol that owes it its result
    (`registered_report.report_owed`, through `hold_declared`). Every line goes
    through TELL. Returns the worst exit code and the chains that ran
    (`HoldVerdict`)."""
    touched = reached_by(paths, repo, staged=staged)
    protocols, reports = touched.protocols, touched.reports
    reached = reached_reports(protocols, reports, repo, staged=staged)
    held = {p for p, _ in reports} | {p for p, _, _ in reached}
    reached += discussing_reports(paths, held, repo, staged=staged)
    # touched.sources is blank when no report is among PATHS (`reached_by`);
    # the reports reached then need every protocol's citations read
    sources = (
        repo_sources(repo, staged=staged)
        if reached and not reports
        else touched.sources
    )
    for p in held_by_reports([(p, t) for p, t, _ in reached], sources):
        if p not in protocols:
            protocols.append(p)
    worst = 0
    chains: dict[Path, ReleaseChain] = {}
    for protocol in protocols:
        released = hold_declared(protocol, repo, sources, tell=tell)
        worst = max(worst, released.exit)
        if released.chain is not None:
            chains[protocol] = released.chain
    for path, text in reports:
        worst = max(worst, hold_report(path, text, repo, sources, tell=tell))
    for path, text, held_as in reached:
        worst = max(
            worst,
            hold_report(path, text, repo, sources, held_as=held_as, tell=tell),
        )
    return HoldVerdict(worst, chains)


def hold_declared(
    protocol: Path, repo: Path, sources: Sources, *, tell: Tell = print
) -> ProtocolVerdict:
    """`report-check` on PROTOCOL when its head declares a result, as the
    state holds it (the index when STAGED); for an exploration only its
    registered report's obligation (`hold_registered`); exit 0 for a
    protocol the commit does not hold, 2 for one that cannot be read or is
    a symbolic link in that state (`repo.protocol_links`). Every line goes
    through TELL, a refusal to stderr. The chain is the declared branch's
    (`protocol_verdict`), None on every other. SOURCES carry the file
    state (`Sources.staged`) and the area's state and evidence the chain
    reads too (`Sources.held_state`): one build per area and check run."""
    staged = sources.staged
    link = protocol_links(repo, [protocol], staged=staged)
    if link:
        console.refuse("report-check", link[protocol])
        return ProtocolVerdict(2, None)
    try:
        text = state_text(repo, protocol, staged=staged)
    except (OSError, UnicodeError) as exc:  # a refusal, never a traceback
        console.refuse("report-check", f"{protocol}: {exc}")
        return ProtocolVerdict(2, None)
    if text is None:
        if staged:
            return ProtocolVerdict(0, None)  # not in the commit: nothing declared there
        console.refuse("report-check", f"{protocol}: no such file")
        return ProtocolVerdict(2, None)
    declared, gap = declaration(text)
    if declared is None and gap is None:
        # an exploration: nothing declared; its registered report, once
        # delivered, is owed the handover or the result all the same
        try:
            return ProtocolVerdict(
                hold_registered(protocol, text, repo, sources, tell=tell),
                None,
            )
        except protocol_block.BlockError as exc:  # a refusal, never a traceback
            console.refuse("report-check", f"{protocol}: {exc}")
            return ProtocolVerdict(2, None)
    tell(
        f"═══ report-check {protocol} (its head has adopted "
        f"{declared or 'a result that does not read'}) ═══"
    )
    area = protocol.parent.resolve()
    if staged:
        # the one hold of this state, `next --staged`'s row too
        gap = staged_area_gap(repo, area, "the stations read")
        if gap is not None:
            tell(f"  {gap.line}")
            return ProtocolVerdict(1, None)
    return protocol_verdict(
        area,
        protocol,
        file_state=file_state_of(staged=staged),
        text=text,
        tell=tell,
        area_state=sources.held_state(area),
        area_evidence=sources.held_evidence(area),
    )


def hold_registered(
    protocol: Path, text: str, repo: Path, sources: Sources, *, tell: Tell = print
) -> int:
    """The registered report's obligation of PROTOCOL, a protocol that
    declares no result (`registered_report.report_owed` with no declared run):
    0 when the head registers no report, the file is not delivered in the
    state (but for a commit that removes one HEAD holds,
    `registered_report.missing_report`), or it carries the protocol's handover block; 1 held, the
    blocker told under its own heading. The area's committed evidence
    changed against HEAD holds first (`evidence.change_blockers`): the
    report of a handover is released by the report reviews of that area.
    A current handover ends the report-path obligation without releasing
    a result; the report it delivers still owes its review. Raises `protocol_block.BlockError` on a head that does not read — the
    caller read the declaration off the same text first."""
    staged = sources.staged
    state = sources.held_state(protocol.parent)
    held = sources.held_evidence(protocol.parent)
    changed = held.change_blockers()
    measured = state.measured_of(protocol_block.head(text).id)
    ended = handovers.protocol_handed_over(
        protocol.parent, protocol, state, staged=staged
    )
    binding = (
        None
        if ended
        else report_binding_gap(protocol, text, measured=measured, unread=True)
    )
    # the commit lacks the registered report while the area measured: that
    # is the finding, and report_owed finds no file to read
    missing = (
        missing_report(protocol, text, repo, measured=measured, staged=True)
        if staged
        else None
    )
    owed = missing or report_owed(protocol, text, None, sources, progress=staged)
    gaps = changed + [g for g in (binding, owed) if g is not None]
    if not gaps:
        return 0
    why = (
        "its area's committed evidence changed"
        if changed
        else "its registered report is delivered"
    )
    tell(f"═══ report-check {protocol} (its head has adopted no result; {why}) ═══")
    out = Findings(tell)
    out.take_all(gaps)
    return out.report("report-check", "reporting")
