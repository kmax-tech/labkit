"""labkit-next — the one next step of an area, and what is held until it is taken.

    labkit-next <AREA> [--protocol FILE]

Reads what the gates already compute and adds no check of its own; the
first that applies is the step:

    no protocol in the area      → `labkit-init exp …` registers the question
    a MUST field still unfilled  → `protocol-fill …` fills it
                                   (`protocol_check.check_fields`)
    a current handover           → nothing: the protocol ended without a
                                   result (`handovers.valid`)
    a gap report-check holds     → its way out, the first in the chain's
                                   order (`report_check.report_gaps`)
    no adopted run               → `protocol-fill … --from-run <run>` adopts
                                   the run that answers
    adopted, nothing held        → nothing: the number may be reported

Prints where the area stands, the next step, and what is held until it is
taken. Exit 0 when a step is named or nothing is owed; 2 on no such area,
no protocol to choose, or a protocol whose head does not read.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import console, handovers, protocol_block, protocol_check
from labkit.formats.gate import BLOCKER
from labkit.formats.repo import (
    adopt_command,
    area_path,
    area_protocols,
    choose_protocol,
    no_such_area,
    shown,
)


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
    `report_check.checked` raises on a run choice that cannot be made."""
    from labkit.gates import report_check

    if protocol is None:
        return Step(
            f"{shown(area, Path.cwd())} holds no protocol: nothing is registered",
            "`labkit-init exp <name> --kind compute|fit|apply` stamps the area "
            "and its protocol; `labkit-init exp --help` names the options",
            "every run and every check: there is no question to hold a number to",
        )
    text = protocol.read_text(encoding="utf-8")
    report = protocol_check.check_fields(text)
    if report.head_error:
        raise protocol_block.BlockError(report.head_error)
    if report.missing_must:
        first = report.missing_must[0]
        return Step(
            f"{protocol.name} lacks {len(report.missing_must)} MUST field(s): "
            + ", ".join(report.missing_must),
            f'`protocol-fill {shown(protocol, Path.cwd())} "{first}=<value>"` fills '
            f"the first; `protocol-check {shown(protocol, Path.cwd())} --contract` "
            "names what each one owes",
            "the first measurement: what the registration lacks then cannot be "
            "added in place",
        )
    if handovers.valid(area):
        return Step(
            f"{protocol.name} is handed over: it ended without a result, its open "
            "findings recorded in the handover",
            "nothing — a new attempt at the question is a new registration",
            "",
        )
    ctx = report_check.checked(area, protocol)
    pending = ctx.declared is None and ctx.run is not None
    gaps = report_check.report_gaps(ctx, adoption_pending=pending)
    held = [g for g in gaps if g.grade == BLOCKER]
    if held:
        first = held[0]
        return Step(
            first.text,
            first.fix or "the line above names what holds",
            f"reporting and the adoption — {len(held)} blocker(s) in report-check",
        )
    if ctx.declared is None:
        run = ctx.run.name if ctx.run is not None else "<run_id>"
        return Step(
            f"nothing holds the answering run {run}; no run is adopted yet",
            f"`{adopt_command(protocol, run)}` adopts it: it writes the result "
            "and checks it whole — a refusal names its step",
            "the number in any report: a number no protocol adopted is not reported",
        )
    return Step(
        f"{protocol.name} has adopted {ctx.declared}; nothing holds it",
        "nothing — the number may be reported (`protocol-fill … --into "
        "REPORT.md` writes its result block into a report)",
        "",
    )


def main(argv: list[str]) -> int:
    """Command line of `labkit-next`: print the next step of an area."""
    ap = argparse.ArgumentParser(
        prog="labkit-next",
        description=(__doc__ or "").splitlines()[0],
    )
    ap.add_argument("area", type=area_path)
    ap.add_argument("--protocol", type=Path, default=None)
    args = ap.parse_args(argv)
    area: Path = args.area
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
