"""labkit-next — the one next step of an area, printed.

    labkit-next <AREA> [--protocol FILE] [--staged]
    labkit-next --guide

The step itself is the gates' (`gates.next_step`): this module chooses the
area and the protocol, reads the flags and prints. `--guide` prints the
agent guide (`labkit/docs/agent-guide.md`): the workflow the stamped
`AGENTS.md` keeps short, in full, with the reason for each rule. `--staged`
reads the index, the state the commit carries and the pre-commit judges
(`report_context.INDEX`); the working tree otherwise. Exit 0 when a step
is named or nothing is owed; 2 on no such area, no protocol to choose, a
protocol whose head does not read, or `--staged` on a protocol the index
does not hold.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import console, protocol_block
from labkit.formats.repo import (
    area_path,
    area_protocols,
    choose_protocol,
    layout_root,
    no_such_area,
    shown,
    experiment_areas,
)
from labkit.gates.next_step import Step, next_step  # noqa: F401 — the tool's names
from labkit.gates.report_context import INDEX, TREE

#: the workflow in full, which `AGENTS.md` keeps short
GUIDE = PACKAGE_DIR / "docs" / "agent-guide.md"

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
    says: a bare `labkit-next` is the loop's first step before an area
    exists, so it names a step, not the usage line."""
    areas = experiment_areas(layout_root(cwd))
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
    ap.add_argument(
        "--staged",
        action="store_true",
        help="read the index, the state the commit carries, not the working tree",
    )
    args = ap.parse_args(argv)
    if args.guide:
        print(GUIDE.read_text(encoding="utf-8"), end="")
        return 0
    area = args.area if args.area is not None else only_area(Path.cwd())
    if area is None:
        return 0 if not experiment_areas(layout_root(Path.cwd())) else 2
    if not area.is_dir():
        console.refuse("labkit-next", no_such_area(area))
        return 2
    protocol = None
    if args.protocol is not None or area_protocols(area):
        protocol = choose_protocol(area, args.protocol, "labkit-next")
        if protocol is None:
            return 2
    try:
        step = next_step(area, protocol, state=INDEX if args.staged else TREE)
    except (protocol_block.BlockError, ValueError) as exc:
        console.refuse("labkit-next", f"{protocol.name if protocol else area}: {exc}")
        return 2
    print(step.render(shown(area, Path.cwd())))
    return 0


def cli() -> None:
    """Console-script entry point; a refusal raised on the way (a detached
    start's record that does not read) exits 2 (`console.exit_with`)."""
    console.exit_with(main)
