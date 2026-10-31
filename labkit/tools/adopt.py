"""labkit-adopt — adopt a run as the protocol's result, in one step.

    labkit-adopt <AREA> [RUN_ID] [--protocol FILE]

The steps a person runs one by one, in order, stopping at the first that
does not pass:

    1. adopt   `protocol-fill PROTOCOL --from-run RUN_ID`: the number into
               the protocol, kept only when report-check passes on the
               written proposal (finalize's checks among them)
    2. report  `protocol-fill PROTOCOL --into REPORT`: the result block into
               the report the head registers (`[protocol] report`); no
               report registered, no step
    3. check   `report-check AREA`: the tree as it now stands, report
               included

RUN_ID omitted: the run the gates hold the protocol to (`--from-run`
without a value, `recheck.chosen_run`). A run the protocol has already
adopted skips step 1, so a call after step 2 or 3 refused resumes there:
the adoption stands, and the refusal says so with the line to run again.
Exit 0 when every step passed, else the failing step's exit code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from labkit.checks import recheck
from labkit.formats import console, protocol_block
from labkit.formats.gate import with_way_out
from labkit.formats.repo import (
    area_path,
    choose_protocol,
    layout_root,
    no_such_area,
    own_path,
    shown,
)


def adopt_in_one_step(area: Path, protocol: Path, run_id: str | None) -> int:
    """Run the module's three steps for RUN_ID (None: the answering run) on
    PROTOCOL of AREA; each step prints its own lines. Returns 0 when all
    passed, else the exit code of the first that did not."""
    from labkit.gates import report_check
    from labkit.tools import protocol_fill

    text = protocol.read_text(encoding="utf-8")
    declared = protocol_block.declared_run(text)
    wanted = run_id
    if wanted is None and declared is not None:
        wanted = recheck.chosen_run(area, text).name
    if declared is not None and declared == wanted:
        print(f"labkit-adopt: 1. {protocol.name} has adopted {declared} already")
    else:
        print("labkit-adopt: 1. adopt")
        rc = protocol_fill.main([str(protocol), "--from-run", run_id or "newest"])
        if rc != 0:
            return rc
        text = protocol.read_text(encoding="utf-8")
    adopted = protocol_block.declared_run(text)
    again = f"labkit-adopt {shown(area, Path.cwd())} {adopted}"
    report = protocol_block.head(text).report
    if report is None:
        print("labkit-adopt: 2. report — none registered in the head")
    else:
        path = own_path(layout_root(area).resolve() / report)
        print(f"labkit-adopt: 2. report — {shown(path, Path.cwd())}")
        rc = protocol_fill.main([str(protocol), "--into", str(path)])
        if rc != 0:
            _resumes(adopted, 2, again)
            return rc
    print("labkit-adopt: 3. check")
    rc = report_check.report_check(area, protocol)
    if rc != 0:
        _resumes(adopted, 3, again)
    return rc


def _resumes(adopted: str | None, step: int, again: str) -> None:
    """Say, after STEP refused, that the adoption of ADOPTED stands and that
    AGAIN resumes at step 2 once what is named is repaired."""
    console.refuse(
        "labkit-adopt",
        with_way_out(
            f"step {step} refused; {adopted} stays adopted",
            f"repair what is named above, then `{again}` resumes at step 2",
        ),
    )


def main(argv: list[str]) -> int:
    """Command line of `labkit-adopt`."""
    ap = argparse.ArgumentParser(
        prog="labkit-adopt",
        description=(__doc__ or "").splitlines()[0],
    )
    ap.add_argument("area", type=area_path)
    ap.add_argument("run_id", nargs="?", default=None, metavar="RUN_ID")
    ap.add_argument("--protocol", type=Path, default=None)
    args = ap.parse_args(argv)
    area: Path = args.area
    if not area.is_dir():
        console.refuse("labkit-adopt", no_such_area(area))
        return 2
    protocol = choose_protocol(area, args.protocol, "labkit-adopt")
    if protocol is None:
        return 2
    return adopt_in_one_step(area, protocol, args.run_id)


def cli() -> None:
    """Console-script entry point."""
    console.exit_with(main)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
