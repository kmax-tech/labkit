"""labkit-next — the one next step of an area, and what is held until it is taken.

    labkit-next <AREA> [--protocol FILE]
    labkit-next --guide

`--guide` prints the agent guide (`labkit/docs/agent-guide.md`): the
workflow the stamped `AGENTS.md` keeps short, in full, with the reason
for each rule.

Reads what the gates already compute and adds no check of its own; the
first that applies is the step:

    no protocol in the area      → `labkit-init exp …` registers the question
    a MUST field still unfilled  → `protocol-fill …` fills it
                                   (`protocol_check.check_fields`)
    a current handover of it     → nothing: the protocol ended without a
                                   result (`handovers.protocol_handed_over`)
    a measured run, nothing adopted, → the progress account: `protocol-fill
      the registered report without     … --discuss RUN --why … --into REPORT`
      its account of that run           (`report_hold.progress_account`), before
                                        any gap — saved first, released by nothing
    a gap report-check holds     → its way out, the first in the chain's
                                   order (`report_check.report_gaps`) — a
                                   committed record changed against HEAD
                                   first, with its restore
    no adopted run               → `labkit-adopt AREA <run>` adopts the run
                                   that answers
    adopted, nothing held        → nothing: the number may be reported

Before the first measurement of a protocol whose head registers no report,
the step adds how to register one (`protocol-fill … report=REPORT.md`):
labkit cannot tell whether the task asks for a report file, and after the
first measurement the registration is refused.

Prints where the area stands, the next step, and what is held until it is
taken. Exit 0 when a step is named or nothing is owed; 2 on no such area,
no protocol to choose, or a protocol whose head does not read.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from labkit import PACKAGE_DIR
from labkit.formats import console, handovers, protocol_block, protocol_check
from labkit.formats.gate import BLOCKER, Findings
from labkit.formats.repo import (
    area_path,
    audit_command,
    area_protocols,
    choose_protocol,
    layout_root,
    no_such_area,
    shown,
    stamped_areas,
)


if TYPE_CHECKING:
    from labkit.gates.report_context import Checked

#: the workflow in full, which `AGENTS.md` keeps short
GUIDE = PACKAGE_DIR / "docs" / "agent-guide.md"


@dataclass(frozen=True)
class Step:
    """The next step of an area: where it stands (WHERE, one sentence), what
    to do next (NEXT, a command or a sentence) and what is held until then
    (HELD; "" when nothing is)."""

    where: str
    next: str
    held: str


def next_step(area: Path, protocol: Path | None) -> Step:
    """The next step of AREA under PROTOCOL (`Step`), in the module's order.
    PROTOCOL None and no protocol in AREA is the first step; PROTOCOL must
    otherwise be the one the caller chose (`repo.choose_protocol`). Raises
    `protocol_block.BlockError` on a head that does not read and whatever
    `report_context.checked` raises on a run choice that cannot be made."""
    from labkit.gates import report_check, report_context

    if protocol is None:
        return Step(
            f"{shown(area, Path.cwd())} holds no protocol: nothing is registered",
            "`labkit-init exp <name> --kind compute|fit|apply` stamps the area "
            "and its protocol; `labkit-init exp --help` names the options",
            "every run: a run needs a registered question",
        )
    text = protocol.read_text(encoding="utf-8")
    report = protocol_check.check_fields(text)
    if report.head_error:
        raise protocol_block.BlockError(report.head_error)
    hint = _report_hint(area, protocol, text)
    if report.missing_must:
        named = shown(protocol, Path.cwd())
        fill = _fill_line(named, report.missing_must[0])
        return Step(
            f"{protocol.name} lacks {len(report.missing_must)} MUST field(s): "
            + ", ".join(report.missing_must),
            (f"`{fill}` fills the first; " if fill else "")
            + f"`protocol-fill {named} --list` names every open field with its "
            f"values, `protocol-check {named} --contract` what each one owes" + hint,
            "the first measurement: fill and commit the registration first, "
            "because it cannot change after that run",
        )
    if handovers.protocol_handed_over(area, protocol):
        return _handed_over(area, protocol, text)
    # a run still open comes first: read as nothing, it sent agents to
    # measure again beside it (reference pilot 2026-11-01, task 15)
    from labkit.run.runlog import open_runs

    still = open_runs(area)
    if still:
        names = ", ".join(r.run_id for r in still)
        return Step(
            f"{names} {'is' if len(still) == 1 else 'are'} still running in "
            f"{shown(area, Path.cwd())}",
            f"`runlog {shown(area, Path.cwd())} --wait` waits for it; then "
            f"`labkit-next` again",
            "every step on its rows: a second measurement beside it is refused",
        )
    ctx = report_context.checked(area, protocol)
    account = _progress_step(ctx)
    if account is not None:
        return account
    pending = ctx.declared is None and ctx.run is not None
    gaps = report_check.report_gaps(ctx, adoption_pending=pending)
    # the area slot a check leaves (`gate.AREA_SLOT`) filled as a gate fills it
    filled = Findings(
        None,
        area=shown(area, Path.cwd()),
        audit=audit_command(area, protocol=protocol),
    )
    filled.take_all(g for g in gaps if g.grade == BLOCKER)
    held = filled.found
    if held:
        first = held[0]
        return Step(
            first.text,
            (first.fix or "the line above names what holds")
            + (hint if ctx.run is None else ""),
            f"the adoption and any report of the number: {len(held)} "
            "blocker(s) stand, and this is the first",
        )
    if ctx.declared is None:
        run = ctx.run.name if ctx.run is not None else "<run_id>"
        return Step(
            f"nothing holds the answering run {run}; no run is adopted yet",
            f"`labkit-adopt {shown(area, Path.cwd())} {run}` adopts it: it writes "
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
    return Step(
        f"{protocol.name} has adopted {ctx.declared}; nothing holds it",
        "nothing — the number may be reported (`protocol-fill "
        f"{shown(protocol, Path.cwd())} --into REPORT.md` writes its result "
        "block into a report the head does not register)",
        "",
    )


def _handed_over(area: Path, protocol: Path, text: str) -> Step:
    """The step of a PROTOCOL (its TEXT) a current handover ended: the
    review its registered report owes once the handover block stands
    (`report_hold.report_owed`), else nothing — a new attempt is a new
    registration. It said "nothing" while the commit held the report for
    its review (probe 2026-11-02, docs/notes/2026-11-02-repair-path-probe.md)."""
    from labkit.gates.report_hold import report_owed

    owed = report_owed(protocol, text, None, layout_root(area), staged=False)
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
    since the run, the audit still owed — is named on the next call."""
    from labkit.checks import report_blocks
    from labkit.formats.repo import own_path
    from labkit.gates.report_hold import progress_account

    report_rel = ctx.head.report
    if report_rel is None or ctx.declared is not None or ctx.run is None:
        return None
    report = own_path(ctx.repo.resolve() / report_rel)
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


def _fill_line(protocol: str, missing: str) -> str | None:
    """The `protocol-fill` line that fills MISSING, a MUST gap as
    `protocol_check.check_fields` names it — a field label, or a head key as
    `[protocol] <key>` with its allowed values (`protocol_edit.HEAD_KEYS`) —
    or None for a gap no single fill closes (a contradiction, a freeze key)."""
    from labkit.tools.protocol_edit import HEAD_KEYS

    if missing.startswith("[protocol] "):
        key = missing.removeprefix("[protocol] ")
        for label, (head_key, choices) in HEAD_KEYS.items():
            if head_key == key:
                value = "|".join(choices) if choices else "value"
                return f'protocol-fill {protocol} "{label}=<{value}>"'
        return None
    if missing.startswith("[") or "(" in missing:
        return None
    return f'protocol-fill {protocol} "{missing}=<value>"'


#: the step before any area: the command that creates one, as AGENTS.md's
#: "Choose the experiment" gives it
CREATE_AREA = (
    "`labkit-init exp <name> --kind <compute|fit|apply> --repeat-cost <low|high>` "
    'creates the area and its protocol (AGENTS.md, "Choose the experiment")'
)


def only_area(cwd: Path) -> Path | None:
    """The area `labkit-next` without an argument speaks of: the one area of
    CWD's repository. None when there is none — the step printed is the one
    that creates an area — or several, refused naming each. Prints what it
    says (round 2: fourteen bare `labkit-next` calls met the usage line, the
    loop's first step before an area exists)."""
    areas = stamped_areas(layout_root(cwd))
    if len(areas) == 1:
        return areas[0]
    if not areas:
        print("labkit-next: no experiment area yet")
        print(f"  next:  {CREATE_AREA}")
        return None
    named = ", ".join(shown(a, cwd) for a in areas)
    console.refuse(
        "labkit-next",
        f"{len(areas)} areas — name one: `labkit-next <area>` with one of {named}",
    )
    return None


def main(argv: list[str]) -> int:
    """Command line of `labkit-next`: print the next step of an area."""
    ap = argparse.ArgumentParser(
        prog="labkit-next",
        description=(__doc__ or "").splitlines()[0],
    )
    ap.add_argument("area", type=area_path, nargs="?", default=None)
    ap.add_argument("--protocol", type=Path, default=None)
    ap.add_argument(
        "--guide", action="store_true", help="print the workflow in full and exit"
    )
    args = ap.parse_args(argv)
    if args.guide:
        print(GUIDE.read_text(encoding="utf-8"), end="")
        return 0
    area = args.area if args.area is not None else only_area(Path.cwd())
    if area is None:
        return 0 if not stamped_areas(layout_root(Path.cwd())) else 2
    if not area.is_dir():
        console.refuse("labkit-next", no_such_area(area))
        return 2
    protocol = None
    if args.protocol is not None or area_protocols(area):
        protocol = choose_protocol(area, args.protocol, "labkit-next")
        if protocol is None:
            return 2
    try:
        step = next_step(area, protocol)
    except (protocol_block.BlockError, ValueError) as exc:
        console.refuse("labkit-next", f"{protocol.name if protocol else area}: {exc}")
        return 2
    print(f"labkit-next: {shown(area, Path.cwd())}")
    print(f"  where: {step.where}")
    print(f"  next:  {step.next}")
    if step.held:
        print(f"  held:  {step.held}")
    return 0


def cli() -> None:
    """Console-script entry point."""
    sys.exit(main(sys.argv[1:]))
