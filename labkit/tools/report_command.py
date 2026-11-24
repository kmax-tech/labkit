"""report_command — the command line of `report-check` (`report_check`
holds the gate): the area form, and the hooks' form `--if-reported`, which
holds the paths and then prints `labkit-next`'s step for every protocol it
reaches (`next_step.steps_for`, reading the chains the hold ran). A tool,
so the gate does not import the step that reads it.
"""

from __future__ import annotations

from pathlib import Path

from labkit.formats import console
from labkit.formats.gate import EXIT_CONTRACT
from labkit.formats.repo import area_parser, git_root, resolve_area
from labkit.gates import report_check
from labkit.gates.next_step import steps_for


def main(argv: list[str]) -> int:
    """Command line of `report-check`."""
    if argv and argv[0] == "--if-reported":
        cwd = Path.cwd()
        rest = argv[1:]
        staged = bool(rest) and rest[0] == "--staged"
        paths = [Path(a) for a in (rest[1:] if staged else rest)]
        repo = git_root(cwd) or cwd
        reported = report_check.hold_reported(paths, repo, staged=staged)
        if reported.exit != 0:
            # what to do is `next`'s step, from the state this gate judged
            # and the chains it ran
            for step in steps_for(repo, paths, staged=staged, chains=reported.chains):
                print(step)
        return reported.exit
    # the hooks' form is parsed above, before argparse; it is still part of
    # this command's contract and stands in its --help
    ap = area_parser(
        "report-check",
        (report_check.__doc__ or "").split("\n\n")[0],
        epilog=(
            "report-check --if-reported [--staged] PATH ...\n"
            "    every protocol of an area a path touches whose head has adopted a\n"
            "    result, and every report among PATHS citing a run (the stop\n"
            "    hook; with --staged the pre-commit: the head and the report as\n"
            "    the index holds them, and the area's tree must equal the index)\n"
            f"{EXIT_CONTRACT}"
        ),
    )
    a = ap.parse_args(argv)
    try:
        area = resolve_area("report-check", a.area)
    except console.Refused as exc:
        console.refuse(exc.tool, exc.why)
        return 2
    return report_check.protocol_verdict(area.resolve(), a.protocol).exit


def cli() -> None:
    """Console entry point `report-check`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
