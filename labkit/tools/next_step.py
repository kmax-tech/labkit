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
    a gap report-check holds     → its way out, the first in the chain's
                                   order (`report_check.report_gaps`)
    no adopted run               → `labkit-adopt AREA <run>` adopts the run
                                   that answers
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

from labkit import PACKAGE_DIR
from labkit.formats import console, handovers, protocol_block, protocol_check
from labkit.formats.gate import BLOCKER, Findings
from labkit.formats.repo import (
    area_path,
    audit_command,
    area_protocols,
    choose_protocol,
    no_such_area,
    shown,
)


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
    `report_check.checked` raises on a run choice that cannot be made."""
    from labkit.gates import report_check

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
    if report.missing_must:
        named = shown(protocol, Path.cwd())
        fill = _fill_line(named, report.missing_must[0])
        return Step(
            f"{protocol.name} lacks {len(report.missing_must)} MUST field(s): "
            + ", ".join(report.missing_must),
            (f"`{fill}` fills the first; " if fill else "")
            + f"`protocol-fill {named} --list` names every open field with its "
            f"values, `protocol-check {named} --contract` what each one owes",
            "the first measurement: fill and commit the registration first, "
            "because it cannot change after that run",
        )
    if handovers.protocol_handed_over(area, protocol):
        return Step(
            f"{protocol.name} is handed over: it ended without a result, its open "
            "findings recorded in the handover",
            "nothing — a new attempt at the question is a new registration",
            "",
        )
    ctx = report_check.checked(area, protocol)
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
            first.fix or "the line above names what holds",
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
    return Step(
        f"{protocol.name} has adopted {ctx.declared}; nothing holds it",
        "nothing — the number may be reported (`protocol-fill "
        f"{shown(protocol, Path.cwd())} --into REPORT.md` writes its result "
        "block into a report the head does not register)",
        "",
    )


def _fill_line(protocol: str, missing: str) -> str | None:
    """The `protocol-fill` line that fills MISSING, a MUST gap as
    `protocol_check.check_fields` names it — a field label, or a head key as
    `[protocol] <key>` with its allowed values (`protocol_fill.HEAD_KEYS`) —
    or None for a gap no single fill closes (a contradiction, a freeze key)."""
    from labkit.tools.protocol_fill import HEAD_KEYS

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
    if args.area is None:
        ap.error("an AREA, or --guide")
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
