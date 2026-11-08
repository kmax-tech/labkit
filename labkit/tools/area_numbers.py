"""area_numbers — the number an experiment area carries, and whether one
number names two areas.

An area is `experiments/NN-<slug>` (`repo.AREA_NAME`); an archived one,
`experiments/_archiv/NN-<slug>`, keeps its number taken. A new area gets
one above every number this tree, every branch this clone knows and every
other worktree hold (`next_experiment_number`), so two branches never hand
out one number twice; `labkit-init numbers` (`number_check`) holds that
every number names one area, in the working tree or, `--staged`, in the
index the commit or merge carries. `scaffold` stamps an area with it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath

from labkit.formats import console
from labkit.formats.repo import (
    AREA_NAME,
    EXPERIMENTS,
    branch_refs,
    files_at,
    git_root,
    split_area_name,
    worktree_roots,
)


#: where an archived area lies under `experiments/`; its number stays taken
ARCHIVE_DIR = "_archiv"


def area_dirs_in(paths: Iterable[str]) -> set[str]:
    """The numbered areas PATHS lie in — paths relative to `experiments/`,
    `/`-separated, as `repo.files_at` lists a git state's files —: `NN-<slug>`
    for a living area, `_archiv/NN-<slug>` for an archived one."""
    out: set[str] = set()
    for path in paths:
        parts = path.split("/")
        if parts[0] == ARCHIVE_DIR:
            if len(parts) > 2 and AREA_NAME.match(parts[1]):
                out.add(f"{ARCHIVE_DIR}/{parts[1]}")
        elif len(parts) > 1 and AREA_NAME.match(parts[0]):
            out.add(parts[0])
    return out


def area_dirs_on_disk(experiments: Path) -> set[str]:
    """The numbered areas EXPERIMENTS holds as directories now, tracked or
    not, named as `area_dirs_in` names them."""
    return {
        f"{prefix}{p.name}"
        for d, prefix in (
            (experiments, ""),
            (experiments / ARCHIVE_DIR, f"{ARCHIVE_DIR}/"),
        )
        if d.is_dir()
        for p in d.iterdir()
        if p.is_dir() and AREA_NAME.match(p.name)
    }


def area_number(area_dir: str) -> int:
    """The number of an area as `area_dirs_in` names it. Raises ValueError
    for a name without an `NN-` prefix."""
    number, _ = split_area_name(PurePosixPath(area_dir).name)
    if number is None:
        raise ValueError(f"no area number in {area_dir!r}")
    return int(number)


def areas_elsewhere(experiments: Path) -> dict[str, set[str]]:
    """The numbered areas the repository holds outside this working tree,
    by where: `branch <name>` for each branch this clone knows, as
    committed (`repo.branch_refs`: local and remote-tracking), and
    `worktree <dir>` for each other worktree as its directory stands now,
    so an area stamped there and not yet committed counts. A place without
    areas is left out; {} outside a repository. A branch this clone never
    fetched is not seen — `labkit-init numbers --staged` in the hooks holds
    the merge that brings one in. Raises RuntimeError or GitError when git
    fails."""
    root = git_root(experiments)
    if root is None:
        return {}
    rel = experiments.resolve().relative_to(root.resolve())
    out: dict[str, set[str]] = {}
    for ref in branch_refs(root):
        name = ref.removeprefix("refs/heads/").removeprefix("refs/remotes/")
        out[f"branch {name}"] = area_dirs_in(files_at(root, experiments, ref) or set())
    for worktree in worktree_roots(root):
        if worktree.resolve() != root.resolve() and (worktree / rel).is_dir():
            out[f"worktree {worktree}"] = area_dirs_on_disk(worktree / rel)
    return {where: dirs for where, dirs in out.items() if dirs}


def next_experiment_number(here: set[str], elsewhere: Mapping[str, set[str]]) -> str:
    """Next free NN prefix ('01' when none is taken): one above every
    number an area carries HERE (this working tree, the archived areas
    among them) or ELSEWHERE (`areas_elsewhere`). A number another branch
    or worktree took is not handed out again: the merge would bring two
    areas of one number together."""
    used = {area_number(d) for d in here.union(*elsewhere.values())}
    return f"{max(used, default=0) + 1:02d}"


def numbers_taken_elsewhere(
    here: set[str], elsewhere: Mapping[str, set[str]]
) -> list[str]:
    """One log line per place in ELSEWHERE holding areas numbered above
    every area HERE — why a new area's number leaves a gap; [] when it
    leaves none."""
    top = max((area_number(d) for d in here), default=0)
    lines = []
    for where, dirs in sorted(elsewhere.items()):
        above = sorted(d for d in dirs if area_number(d) > top)
        if above:
            lines.append(f"  number taken   {', '.join(above)} on {where}")
    return lines


def shared_numbers(area_dirs: Iterable[str]) -> dict[int, list[str]]:
    """Every number more than one of AREA_DIRS carries, with those areas
    sorted; {} when each number names one area. A living and an archived
    area count alike: the archived one keeps its number taken."""
    by_number: dict[int, list[str]] = {}
    for d in sorted(area_dirs):
        by_number.setdefault(area_number(d), []).append(d)
    return {n: dirs for n, dirs in by_number.items() if len(dirs) > 1}


def number_check(root: Path, *, staged: bool) -> tuple[int, str]:
    """`labkit-init numbers`: does every area under ROOT's `experiments/`
    carry a number of its own — in the index with STAGED (what the commit
    or the merge commit carries; the hooks ask this), else in the working
    tree — and which number comes next (`next_experiment_number`)? Returns
    (exit code, report) for the caller to print: 0 and one line when each
    number names one area, 1 and one line per shared number plus the way
    out otherwise. Raises console.Refused when ROOT has no `experiments/`,
    and with STAGED when it lies in no git repository."""
    experiments = root / EXPERIMENTS
    if not experiments.is_dir():
        raise console.Refused(
            "labkit-init", f"{root} has no {EXPERIMENTS}/ — not a lab repo"
        )
    if staged:
        repo = git_root(root)
        files = files_at(repo, experiments) if repo is not None else None
        if files is None:
            raise console.Refused(
                "labkit-init",
                f"{root} is in no git repository — --staged has no index to read",
            )
        here, state = area_dirs_in(files), "the index"
    else:
        here, state = area_dirs_on_disk(experiments), "the working tree"
    nn = next_experiment_number(here, areas_elsewhere(experiments))
    shared = shared_numbers(here)
    if not shared:
        return 0, (
            f"labkit-init numbers: {len(here)} area(s) in {state}, each with a "
            f"number of its own; next free number {nn}"
        )
    lines = [
        f"labkit-init numbers: number {n:02d} is carried by {len(dirs)} areas in "
        f"{state}: {', '.join(f'experiments/{d}' for d in dirs)}"
        for n, dirs in sorted(shared.items())
    ]
    lines.append(
        f"  keep the number that commits and notes already cite; move the other "
        f"area to the next free number, {nn} — its directory, the README "
        f"heading and tests/test_<NN>_<name>.py"
    )
    return 1, "\n".join(lines)
