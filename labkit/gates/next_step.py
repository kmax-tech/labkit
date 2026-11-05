"""next_step — the one next step of an area, read from the gates, and what is
held until it is taken.

The order, the first that applies is the step (`next_step`):

    no protocol in the area      → `labkit-init exp …` registers the question
    a MUST field absent or still → `protocol-fill …` fills a placeholder;
      a placeholder                an absent † field comes with
                                   `labkit-init exp … --report`
                                   (`protocol_check.check_fields`)
    the index's head declares a   → `git add -- AREA` stages the whole area
      result and the area's tree    (`report_hold.staged_area_gap`, the
      differs from the index        commit's hold before any station reads;
      (the pre-commit's state)      the index alone)
    committed evidence changed   → its restore, the first of report-check's
      against HEAD                 first station (`evidence.change_blockers`),
                                   before a handover can say "nothing"
    a current handover of it     → nothing: the protocol ended without a
                                   result (`handovers.protocol_handed_over`)
    a run still open             → `runlog … --wait`
    a measured run, nothing adopted, → the progress account: `protocol-fill
      the registered report without     … --discuss RUN --why … --into REPORT`
      its account of that run           (`report_hold.progress_account`), before
                                        any gap — saved first, released by nothing;
                                        a registered report not written at all
                                        is this state too: the stop holds it
                                        (`report_hold.missing_report`) and
                                        prints this step
    a gap report-check holds     → its way out, the first in the chain's
                                   order (`report_check.chain_gaps`; the
                                   review a report owes for discussing a
                                   run of it is among them) — but the
                                   withdrawal alone where the holds name
                                   it first (`report_check.held_declaration`),
                                   and for a measurement runlog's start gate
                                   would refuse: that refusal's first step
                                   (`start_check.measurement_refusal`)
    an audit BLOCKER nobody      → decide it by the `--decide` command
      decided, a record or the     `--findings` prints, restore, or hand over
      journal lost or unreadable,  (`agent_hooks.undecided_state`: the hold of
      and the chain carries no     the stop and the commit, which print this
      gap for it                   step; a loss a current handover
                                   acknowledges is not held). After the
                                   chain's gaps: the chain's order stands
                                   (the way back of a rewritten registration
                                   before a decision on it, probe 2026-11-02)
    the adoption would leave a   → fill it first (`check_fields` with
      MUST field open                `adopting`: the frozen protocol's †
                                   result fields; `labkit-adopt` would
                                   refuse the written result)
    no adopted run               → `labkit-adopt AREA <run>` adopts the run
                                   that answers
    adopted, nothing held        → nothing: the number may be reported

Before the first measurement of a protocol whose head registers no report,
the step adds how to register one (`protocol-fill … report=REPORT.md`):
labkit cannot tell whether the task asks for a report file, and after the
first measurement the registration is refused.

The step is read from a file state (`report_context.TREE` or `INDEX`), the
one the caller judges: the console and the stop the tree, the pre-commit
the index. `Step.render` is the one spelling of a step, for `labkit-next`
(`tools.next_command`) and for the hooks that print it. This module adds
no check of its own: every hold it names is a gate's finding.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from labkit.formats import (
    evidence,
    findings,
    handovers,
    protocol_block,
    protocol_check,
)
from labkit.formats.standard_contract import ANALYSIS_AUDIT
from labkit.formats.gate import BLOCKER, Findings, GateFinding
from labkit.formats.repo import (
    MEASURE,
    RESTORE,
    area_protocols,
    audit_command,
    decide_command,
    layout_root,
    report_fields_command,
    shown,
    state_text,
    withdraw_command,
)
from labkit.gates.report_context import INDEX, TREE

if TYPE_CHECKING:
    from labkit.gates.report_context import Checked


@dataclass(frozen=True)
class Step:
    """The next step of an area: where it stands (WHERE, one sentence), what
    to do next (NEXT, a command or a sentence) and what is held until then
    (HELD; "" when nothing is)."""

    where: str
    next: str
    held: str

    def render(self, area: str) -> str:
        """The step as `labkit-next` prints it for AREA (as the reader names
        it): the heading line, where, next, and held when something is —
        the one spelling, for the console and for a hook that prints it."""
        lines = [
            f"labkit-next: {area}",
            f"  where: {self.where}",
            f"  next:  {self.next}",
        ]
        if self.held:
            lines.append(f"  held:  {self.held}")
        return "\n".join(lines)


def next_step(area: Path, protocol: Path | None, *, state: str = TREE) -> Step:
    """The next step of AREA under PROTOCOL (`Step`), in the module's order,
    read from STATE — the working tree (TREE) or the index (INDEX), the
    state the caller judges: a hook that holds the index names a step from
    the index. PROTOCOL None and no protocol in AREA is the first step;
    PROTOCOL must otherwise be the one the caller chose
    (`repo.choose_protocol`). Raises `protocol_block.BlockError` on a head
    that does not read, ValueError for INDEX on a protocol the index does
    not hold, and whatever `report_context.checked` raises on a run choice
    that cannot be made."""
    from labkit.gates import report_check, report_context

    if protocol is None:
        return Step(
            f"{shown(area, Path.cwd())} holds no protocol: nothing is registered",
            "`labkit-init exp <name> --kind compute|fit|apply` stamps the area "
            "and its protocol; `labkit-init exp --help` names the options",
            "every run: a run needs a registered question",
        )
    staged = state == INDEX
    text = _protocol_text(area, protocol, staged=staged)
    report = protocol_check.check_fields(text)
    if report.head_error:
        raise protocol_block.BlockError(report.head_error)
    hint = _report_hint(area, protocol, text)
    before = _before_the_chain(area, protocol, text, report, hint, staged=staged)
    if before is not None:
        return before
    # a run still going comes first, as `runlog --wait` sees it: read as
    # nothing, an open run sent agents to measure again beside it (reference
    # pilot 2026-11-01, task 15), a detached start before its record a
    # second time after it (2026-11-04, case A of the liveness note)
    from labkit.run.runlog import busy

    still = busy(area)
    if still:
        names = ", ".join(
            [r.run_id for r in still.runs]
            + [f"pid {s.pid} (started by runlog start)" for s in still.unopened]
        )
        many = len(still.runs) + len(still.unopened) > 1
        return Step(
            f"{names} {'are' if many else 'is'} still running in "
            f"{shown(area, Path.cwd())}",
            f"`runlog {shown(area, Path.cwd())} --wait` waits for it; then "
            f"`labkit-next` again",
            "every step on its rows: a second measurement beside it must wait — "
            "runlog refuses one beside an open run, not yet beside a start whose "
            "run has not opened",
        )
    ctx = report_context.checked(area, protocol, state=state, text=text)
    account = _progress_step(ctx)
    if account is not None:
        return account
    pending = ctx.declared is None and ctx.run is not None
    gaps, held_by = report_check.chain_gaps(ctx, adoption_pending=pending)
    # the area slot a check leaves (`gate.AREA_SLOT`) filled as a gate fills it
    filled = Findings(
        None,
        area=shown(area, Path.cwd()),
        audit=audit_command(area, protocol=protocol).line,
    )
    filled.take_all(g for g in gaps if g.grade == BLOCKER)
    held = filled.found
    if held:
        return _held_step(ctx, held, held_by, hint if ctx.run is None else "")
    # the stop's and the commit's own hold the chain carries no gap for
    undecided = _undecided_step(area, protocol, staged=staged)
    if undecided is not None:
        return undecided
    return _closing_step(ctx, protocol, text)


def _closing_step(ctx: Checked, protocol: Path, text: str) -> Step:
    """The steps past the chain and the undecided row: what the adoption
    would still owe (`_adoption_owes`), the adoption, a report citing the
    adopted run without its block, and nothing."""
    if ctx.declared is None:
        run = ctx.run.name if ctx.run is not None else "<run_id>"
        owed_then = _adoption_owes(protocol, text, run)
        if owed_then is not None:
            return owed_then
        return Step(
            f"nothing holds the answering run {run}; no run is adopted yet",
            f"`labkit-adopt {shown(ctx.area, Path.cwd())} {run}` adopts it: it writes "
            "the result and the report's block and checks them — a refusal "
            "names its step",
            "the number in any report: report only an adopted number",
        )
    from labkit.formats.repo import into_command
    from labkit.gates.report_hold import reports_without_block

    unblocked = reports_without_block(ctx.repo, protocol, ctx.declared)
    if unblocked:
        first = unblocked[0]
        return Step(
            f"{shown(first, Path.cwd())} cites {ctx.declared}, the adopted result, "
            "without its generated block",
            f"`{into_command(protocol, first)}` writes it",
            "the commit and the stop: they hold a report that cites an adopted "
            "run without its block",
        )
    report = _registered_report(ctx)
    finished = (
        f"nothing — the number may be reported in {shown(report, Path.cwd())}, "
        "the report registered in the head"
        if report is not None
        else "nothing — the number may be reported (`protocol-fill "
        f"{shown(protocol, Path.cwd())} --into REPORT.md` writes its result "
        "block into a report the head does not register)"
    )
    return Step(
        f"{protocol.name} has adopted {ctx.declared}; nothing holds it",
        finished,
        "",
    )


def steps_for(repo: Path, paths: list[Path], *, staged: bool) -> list[str]:
    """Per protocol of every area PATHS touch (`scope_sha.areas_touched`,
    and the area of a protocol registering one of PATHS as its report),
    `labkit-next`'s step for the state the caller judges — the index when
    STAGED (the commit's gates), else the tree (the stop) — as the console
    prints it (`Step.render`): the one action the stop, the commit's
    undecided gate and report-check's hook entry name beside what they
    hold; none composes a step of its own. A head that does not read, or a
    protocol the index does not hold, is told in one line in the step's
    place; a run index that does not read once per index."""
    from labkit.formats.scope_sha import areas_touched
    from labkit.gates.report_hold import registering_protocols
    from labkit.run.runlog import RunIndexError

    # the areas the paths lie in, and the area of every protocol whose head
    # registers a path among them as its report (a REPORT.md at the root
    # lies in no area; report-check's hook entry reaches it the same way)
    areas = [a.resolve() for a in areas_touched(paths, repo)]
    for p in registering_protocols(paths, repo, staged=staged):
        if p.parent.resolve() not in areas:
            areas.append(p.parent.resolve())
    out: list[str] = []
    for area in areas:
        named = shown(area, Path.cwd())
        for protocol in area_protocols(area):
            try:
                step = next_step(area, protocol, state=INDEX if staged else TREE)
            except RunIndexError as exc:  # a ValueError too: before it
                if exc.why not in out:
                    out.append(exc.why)
                continue
            except (protocol_block.BlockError, ValueError) as exc:
                out.append(f"{named}: {protocol.name}: {exc}")
                continue
            out.append(step.render(named))
    return out


def _before_the_chain(
    area: Path,
    protocol: Path,
    text: str,
    report: protocol_check.FieldReport,
    hint: str,
    *,
    staged: bool,
) -> Step | None:
    """The steps before report-check's chain, the first that applies: a
    MUST field unfilled (`_field_step`), committed evidence changed against
    HEAD (`_restore_step`), a current handover (`_handed_over`). None when
    none applies."""
    return (
        _field_step(protocol, report, hint)
        or _staged_area_step(area, text, staged=staged)
        or _restore_step(area, staged=staged)
        or _handed_over(area, protocol, text, staged=staged)
    )


def _staged_area_step(area: Path, text: str, *, staged: bool) -> Step | None:
    """The commit's hold while the index's head declares a result and the
    area's tree differs from the index (`report_hold.staged_area_gap`, the
    hold of report-check's declared branch): the step stages the whole
    area. None in the tree, for an undeclared head, or when the tree is
    what the commit would hold. Before the restore: report-check holds it
    before any station reads."""
    from labkit.gates.report_hold import staged_area_gap

    if not staged or protocol_block.declared_run(text) is None:
        return None
    gap = staged_area_gap(layout_root(area), area, "the stations read")
    if gap is None:
        return None
    return Step(
        gap.text,
        gap.fix or "the line above names what holds",
        "the commit: it holds the index, and the stations read the tree",
    )


def _protocol_text(area: Path, protocol: Path, *, staged: bool) -> str:
    """PROTOCOL of AREA as the state holds it: the index's text when STAGED
    (`repo.state_text`), else the working tree's. Raises ValueError when
    the index does not hold the protocol."""
    if not staged:
        return protocol.read_text(encoding="utf-8")
    held = state_text(layout_root(area), protocol, staged=True)
    if held is None:
        raise ValueError(f"{protocol.name}: the index does not hold it")
    return held


def _restore_step(area: Path, *, staged: bool) -> Step | None:
    """The restore of AREA's committed evidence changed against HEAD as the
    step (`evidence.change_blockers`, report-check's first station; the
    index's change when STAGED), or None. It comes before the handover: a handover's report is released by
    the report reviews here, and a handover acknowledges no change git can
    undo."""
    changed = evidence.change_blockers(area, staged=staged)
    if not changed:
        return None
    return Step(
        changed[0].text,
        changed[0].fix or "the line above names what holds",
        f"every release from this area: {len(changed)} change(s) of its "
        "committed evidence stand, and this is the first",
    )


def _undecided_step(area: Path, protocol: Path, *, staged: bool) -> Step | None:
    """The step while AREA holds an audit BLOCKER nobody decided, a record
    or the attempt journal lost or unreadable, or evidence changed against
    HEAD, in the state judged (`agent_hooks.undecided_state`, read for
    PROTOCOL's area: the stop's and the commit's own hold, a loss a current
    handover acknowledges not among them); None when nothing holds. Read
    after report-check's chain: a gap there names its own step first (the
    way back of a rewritten registration before a decision on it), this
    row catches the holds the chain carries no gap for. The way is the one
    the stop and the commit printed themselves until 0.108.0: decide by the
    command, never by editing the record (ninth haiku round, t5, rewrote
    records field by field); an outdated record stays and is decided too
    (fourth SAB-like draw: "stale, let me remove"); restore from git; or
    hand over."""
    from labkit.formats import findings
    from labkit.gates.agent_hooks import undecided_state

    held = undecided_state(layout_root(area), [protocol], staged=staged).blockers
    if not held:
        return None
    named = shown(area, Path.cwd())
    return Step(
        f"{named} holds {len(held)} audit BLOCKER(s) nobody decided, or evidence "
        f"gone, changed or unreadable; the first: {held[0]}",
        f"`labkit-audit {named} --findings` prints the `--decide` command for "
        f"each open BLOCKER ({findings.DECIDED_LIST}; limitation and "
        "false-positive owe a reason): decide by it, never by rewriting or "
        "deleting the record — one a later change made outdated stays and is "
        "decided too, `fixed` naming the change where it repaired the fault; a "
        "line that names its `git checkout` restores evidence from git; when "
        "the area cannot be finished, hand it over with the `protocol-fill "
        "<PROTOCOL> --handover` command `--findings` prints: the BLOCKERs stay "
        "open and the handover records them",
        "the stop and the commit: a number measured past them cannot be reported",
    )


def _handed_over(area: Path, protocol: Path, text: str, *, staged: bool) -> Step | None:
    """The step of a PROTOCOL (its TEXT) a current handover ended
    (`handovers.protocol_handed_over`), else None: the review its
    registered report owes once the handover block stands
    (`report_hold.report_owed`, read from the index when STAGED), else nothing — a new attempt is a new
    registration. It said "nothing" while the commit held the report for
    its review (probe 2026-11-02, docs/notes/2026-11-02-repair-path-probe.md)."""
    from labkit.gates.report_hold import report_owed

    if not handovers.protocol_handed_over(area, protocol):
        return None

    owed = report_owed(protocol, text, None, layout_root(area), staged=staged)
    if owed is not None:
        return Step(
            f"{protocol.name} is handed over, and {owed.text}",
            owed.fix or f"`labkit-audit {area} --report-review <REPORT>`",
            "the commit and the stop: the report's final text is reviewed once",
        )
    return Step(
        f"{protocol.name} is handed over: it ended without a result, its open "
        "findings recorded in the handover",
        "nothing — a new attempt at the question is a new registration",
        "",
    )


def _held_step(
    ctx: "Checked", held: list[GateFinding], held_by: Path | None, hint: str
) -> Step:
    """The step while report-check holds CTX with HELD, its blockers in the
    chain's order: the first one's way out, HINT added. Two exceptions:

    - HELD_BY, the protocol whose adopted run's code or declared scope
      changed since it ran (`report_check.held_declaration`; the later
      holds name its withdrawal first): the withdrawal alone, then
      `labkit-next` again — the holds are read anew against the run that
      answers after it. The first hold's own way out told an agent who had
      already measured the repaired code to measure a third time into a
      renamed output (probe 2026-11-02, case 5).
    - a measurement runlog would refuse: the refusal's first step
      (`_refused_measurement`)."""
    first = held[0]
    if held_by is not None:
        return Step(
            f"{held_by.name} has adopted {ctx.declared}, and the code or a declared "
            f"scope changed since that run — the holds read the area against that "
            f"adoption until it is withdrawn; the first: {first.text}",
            f"`{withdraw_command(held_by)}` withdraws the adoption; then "
            "`labkit-next` again: the holds are read anew against the run that "
            f"answers then. Only when the change was not meant: restore it as "
            f"{ctx.declared} ran it",
            f"the adoption and any report of the number: {len(held)} blocker(s) stand",
        )
    refused = _refused_measurement(ctx, first)
    if refused is not None:
        return replace(refused, next=refused.next + hint)
    return Step(
        first.text,
        (first.fix or "the line above names what holds")
        + _finding_on_the_field(ctx, first)
        + hint,
        f"the adoption and any report of the number: {len(held)} "
        "blocker(s) stand, and this is the first",
    )


def _finding_on_the_field(ctx: "Checked", first: GateFinding) -> str:
    """One sentence more on a restore step (`repo.RESTORE`, a registered
    field changed after the first measurement) while an analysis finding
    still open names the protocol as its place: the decision that goes with
    the restore — `limitation`, the registered text stands and what the
    finding names is reported — or `fixed` for a correction a follow-up
    audit's `resolved` releases. "" otherwise, or when the records do not
    read (the undecided row says so). An agent between the auditor's
    "misdescribed" and the gate's "restore" rewrote the field five times
    (labkit-paper's t34-r3, 2026-11-04)."""
    if first.step is None or first.step.name != RESTORE:
        return ""
    try:
        records = findings.area_records(ctx.area)
    except findings.FindingsError:
        return ""
    for u in findings.open_findings(records, mode=ANALYSIS_AUDIT):
        place = u.finding.place
        if place is not None and place[0] == ctx.protocol.name:
            decide = decide_command(
                ctx.area,
                u.number,
                "limitation",
                "<the registered text stands; what the finding names is a limit>",
                shown(u.record.path, Path.cwd()),
                protocol=ctx.protocol,
            )
            return (
                f"; finding {u.number} of {u.record.path.name} names this protocol — "
                f"after the restore decide it (`{decide}`), or `fixed` for a "
                "correction a follow-up audit's `resolved` releases"
            )
    return ""


def _registered_report(ctx: "Checked") -> Path | None:
    """The report CTX's head registers, as a path; None without one."""
    from labkit.formats.repo import own_path

    rel = ctx.head.report
    return own_path(ctx.repo.resolve() / rel) if rel is not None else None


def _refused_measurement(ctx: "Checked", first: GateFinding) -> Step | None:
    """The step when FIRST, CTX's first hold, names a measurement as its
    step (`GateFinding.step`, `repo.MEASURE`) before any run answers and
    runlog's start gate would refuse it now
    (`start_check.measurement_refusal`): the refusal's own first step.
    None otherwise — with a stamped id only, the one a run binds to. It
    named "measure" over an uncommitted registration, and runlog refused
    (probe 2026-11-02, docs/notes/2026-11-02-repair-path-probe.md)."""
    from labkit.run import start_check

    if ctx.run is not None or ctx.head.id is None:
        return None
    if first.step is None or first.step.name != MEASURE:
        return None
    gaps, first_step = start_check.measurement_refusal(ctx.area, ctx.protocol)
    if not gaps:
        return None
    return Step(
        f"a measurement would be refused now: {gaps[0]}",
        first_step,
        "the first measurement: runlog refuses it until then",
    )


def _field_step(
    protocol: Path, report: protocol_check.FieldReport, hint: str
) -> Step | None:
    """The step the field report of PROTOCOL asks for first: a bound field
    written more than once (`FieldReport.repeated`), then the missing MUST
    fields; None when neither. HINT closes the way (`_report_hint`)."""
    named = shown(protocol, Path.cwd())
    if report.repeated:
        return Step(
            f"{protocol.name} writes a field more than once: "
            + "; ".join(report.repeated),
            f"{protocol_check.REPEATED_WAY_OUT}; then `protocol-check {named}`" + hint,
            "every comparison and audit binding of the registration: which "
            "copy is registered cannot be told",
        )
    if report.missing_must:
        fill = _fill_line(
            named, report.missing_must[0], absent=True, area=protocol.parent
        )
        return Step(
            f"{protocol.name} lacks {len(report.missing_must)} MUST field(s): "
            + ", ".join(report.missing_must),
            (f"{fill}; " if fill else "")
            + f"`protocol-fill {named} --list` names every open field with its "
            f"values, `protocol-check {named} --contract` what each one owes" + hint,
            "the first measurement: fill and commit the registration first, "
            "because it cannot change after that run",
        )
    if report.must_holes:
        # a MUST field stamped and never written: protocol-check holds it
        # (PLACEHOLDER ONLY), so the row names it — a should field is one
        # once frozen (the repair probe's base8, 2026-11-05)
        labels = [label for _, label in report.must_holes]
        fill = _fill_line(named, labels[0], absent=False, area=protocol.parent)
        return Step(
            f"{protocol.name}: {len(labels)} MUST field(s) still a placeholder: "
            + ", ".join(labels),
            (f"{fill}; " if fill else "")
            + f"`protocol-fill {named} --list` names every open field with its "
            f"values" + hint,
            "the commit and every gate that reads the fields: a placeholder is "
            "not a registration",
        )
    return None


def _report_hint(area: Path, protocol: Path, text: str) -> str:
    """The sentence a step before the first measurement adds when the head
    registers no report: how to register one — labkit cannot tell whether
    the task asks for a report file, and once the area measured the
    registration is refused (`protocol_fill.report_bound`). "" otherwise."""
    from labkit.gates.report_hold import has_measured

    head = protocol_block.head(text)
    if head.report is not None or not head.id or has_measured(area, head.id):
        return ""
    return (
        f"; if the task asks for a report file, register it now: `protocol-fill "
        f"{shown(protocol, Path.cwd())} report=REPORT.md` — before the first "
        f"measurement only"
    )


def _progress_step(ctx: "Checked") -> Step | None:
    """The progress account as the step, or None: the head registers a
    report, the gates hold the protocol to a measured run, nothing is
    adopted, and the report does not yet carry its discussion of that run
    (`report_hold.progress_account`). It comes before every gap: the account
    is saved first and releases nothing, so a gap that holds — a change
    since the run, the audit still owed — is named on the next call. A
    registered report not written at all is the same state: the stop holds
    the protocol with the gate's finding (`report_hold.missing_report`,
    `agent_hooks.missing_reports`) and prints this step — the hold is the
    finding, the action is this one concrete command."""
    from labkit.checks import report_blocks
    from labkit.gates.report_hold import progress_account

    report = _registered_report(ctx)
    if report is None or ctx.declared is not None or ctx.run is None:
        return None
    if ctx.state == INDEX:
        written = state_text(ctx.repo, report, staged=True) or ""
    else:
        written = report.read_text(encoding="utf-8") if report.is_file() else ""
    owner = report_blocks.path_from_report(ctx.protocol, report)
    if progress_account(written, owner, ctx.run.name):
        return None
    here = Path.cwd()
    return Step(
        f"run {ctx.run.name} is measured, and {shown(report, here)} carries no "
        f"account of it yet",
        f"`{report_blocks.discuss_command(shown(ctx.protocol, here), ctx.run.name, shown(report, here), report_blocks.WHY_PROGRESS)}`"
        f" writes it, saved before the checks (replace the placeholder after "
        f"--why); then `labkit-next` again",
        "the result: only the adoption releases it, after the checks it owes",
    )


def _adoption_owes(protocol: Path, text: str, run: str) -> Step | None:
    """The step while adopting RUN would leave a MUST field open: the fields
    the adoption's state owes (`protocol_check.check_fields` with
    `adopting`, the same question report-check's field station asks of the
    written result, so `labkit-adopt` would refuse) that the state as it
    stands does not — a frozen protocol's † result fields. None when the
    adoption owes nothing more. The one state `labkit-next` named a step its
    command refused (labkit-paper's tassay-r2, 2026-11-04; the repair
    probe's c8)."""
    now = protocol_check.check_fields(text)
    then = protocol_check.check_fields(text, adopting=True)
    absent = [f for f in then.missing_must if f not in now.missing_must]
    holes = [label for _, label in then.must_holes if (_, label) not in now.must_holes]
    if not absent and not holes:
        return None
    named = shown(protocol, Path.cwd())
    first = absent[0] if absent else holes[0]
    fill = _fill_line(named, first, absent=bool(absent), area=protocol.parent)
    return Step(
        f"adopting {run} would owe {len(absent) + len(holes)} field(s) still open: "
        + ", ".join(absent + holes),
        (f"{fill}; " if fill else "")
        + f"`protocol-check {named} --contract` names what the adoption owes; then "
        "`labkit-next` again",
        "the adoption: labkit-adopt refuses the written result while a field it "
        "owes is open",
    )


def _fill_line(protocol: str, missing: str, *, absent: bool, area: Path) -> str | None:
    """The sentence with the command that closes MISSING, a MUST gap as
    `protocol_check.check_fields` names it: a head key as `[protocol] <key>`
    with its allowed values (`protocol_block.FILLABLE_HEAD_KEYS`), or a
    field label — a placeholder (ABSENT False) is filled by `protocol-fill`;
    a field ABSENT from the text is not (protocol-fill knows no field it
    cannot see): a † field, one `--report` stamps (`Field.level` should or
    report), comes with `labkit-init exp AREA --report`, written as a
    Command; any other absent field is a line to write by hand. None for a
    gap no single step closes (a contradiction, a freeze key)."""
    if missing.startswith("[protocol] "):
        key = missing.removeprefix("[protocol] ")
        for label, (head_key, choices) in protocol_block.FILLABLE_HEAD_KEYS.items():
            if head_key == key:
                value = "|".join(choices) if choices else "value"
                return f'`protocol-fill {protocol} "{label}=<{value}>"` fills the first'
        return None
    if missing.startswith("[") or "(" in missing:
        return None
    if not absent:
        return f'`protocol-fill {protocol} "{missing}=<value>"` fills the first'
    field = next(
        (f for f in protocol_check.FIELDS if f.label.casefold() == missing.casefold()),
        None,
    )
    if field is not None and field.level in ("should", "report"):
        return (
            f"`{report_fields_command(area)}` appends the † fields "
            f"({missing} among them) to the protocol, each in its section; "
            "then `protocol-fill` fills them"
        )
    return (
        f"write the line `- **{missing}:** …` into the protocol — protocol-fill "
        "fills a field it sees, not one that is absent"
    )
