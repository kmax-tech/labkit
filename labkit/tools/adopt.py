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
without a value). A run the protocol has already adopted skips step 1.
Exit 0 when every step passed, else the failing step's exit code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from labkit.formats import console, protocol_block
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
    if run_id is not None and declared == run_id:
        print(f"labkit-adopt: 1. {protocol.name} has adopted {run_id} already")
    else:
        print("labkit-adopt: 1. adopt")
        rc = protocol_fill.main([str(protocol), "--from-run", run_id or "newest"])
        if rc != 0:
            return rc
        text = protocol.read_text(encoding="utf-8")
    report = protocol_block.head(text).report
    if report is None:
        print("labkit-adopt: 2. report — none registered in the head")
    else:
        path = own_path(layout_root(area).resolve() / report)
        print(f"labkit-adopt: 2. report — {shown(path, Path.cwd())}")
        rc = protocol_fill.main([str(protocol), "--into", str(path)])
        if rc != 0:
            return rc
    print("labkit-adopt: 3. check")
    return report_check.report_check(area, protocol)


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
