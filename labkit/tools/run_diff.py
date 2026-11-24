"""labkit-run-diff — the full code difference of two runs of one area.

    labkit-run-diff <AREA> <OLD_RUN> <NEW_RUN>

Each run's code is its tracked tree when it started: its recorded commit
with its `uncommitted.patch` (`run_code.code_then`), compared within the
area's code (`run_code.code_scope`: the area without runs, audit records
and protocols, and the repository's lib/ and src/). Prints git's per-file
summary, then the whole unified diff, uncut — what an audit's piece of the
protocol's runs shows cut (`protocol_runs`). Exit 0 when both trees read
(the same code prints that), 2 when a run or its code cannot be read back,
with the reason. Writes only git objects (the trees).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from labkit.formats import console, runs
from labkit.formats.repo import GitError, area_parser, git_root, resolve_area
from labkit.formats.run_code import code_difference, code_scope, code_then

TOOL = "labkit-run-diff"


def main(argv: list[str]) -> int:
    """Command line: the difference of NEW_RUN's code from OLD_RUN's.
    Raises console.Refused on an area, a run or a tree that do not read;
    a command line argparse cannot read ends with its usage, exit 2."""
    ap = area_parser(TOOL, (__doc__ or "").strip().splitlines()[0], protocol=False)
    ap.add_argument("old_run", metavar="OLD_RUN", help="the earlier run's id")
    ap.add_argument("new_run", metavar="NEW_RUN", help="the later run's id")
    args = ap.parse_args(argv)
    area = resolve_area(TOOL, args.area)
    root = git_root(area)
    if root is None:
        raise console.Refused(TOOL, f"{area}: no git repository holds a run's commit")
    old, new = (_code_of(area, root, run_id) for run_id in (args.old_run, args.new_run))
    try:
        diff = code_difference(root, code_scope(area, root), old.tree, new.tree)
    except GitError as exc:
        raise console.Refused(TOOL, str(exc)) from exc
    print(f"{old.run_id}: {old.where}")
    print(f"{new.run_id}: {new.where}")
    if not diff.diff:
        print("the same code")
        return 0
    print(diff.stat.rstrip("\n"))
    print(diff.diff.rstrip("\n"))
    return 0


class _Read(NamedTuple):
    run_id: str
    tree: str
    where: str


def _code_of(area: Path, root: Path, run_id: str) -> _Read:
    """RUN_ID's code then (`run_code.code_then`). Raises console.Refused
    when the run or its tree cannot be read back."""
    run_dir = runs.run_path(area, run_id)
    if not run_dir.is_dir():
        raise console.Refused(
            TOOL, f"{run_id}: no run of that id under {run_dir.parent}"
        )
    code = code_then(runs.read_run_dir(run_dir), root)
    if code.tree is None:
        raise console.Refused(TOOL, code.where)
    return _Read(code.run_id, code.tree, code.where)


def cli() -> None:
    """Console entry point of `labkit-run-diff`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
