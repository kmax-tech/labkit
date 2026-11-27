"""run_code — a run's code as it started, and how two runs' code differ.

A run records the commit it started at and, from a changed tree, its
`uncommitted.patch`; together they are the tracked tree it ran from
(`code_then`). Two runs of one area are compared within `code_scope`: the
area's Python files outside its run directories and the repository's `lib/`
and `src/`: the code. Outputs, data and prompts are not in it; the
protocols' texts are compared as registrations. Files git did not track
when a run started are in neither tree; the run's `script-source` copy and `code.json` keep
those. Reads files and git, writes only git objects (the trees).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labkit.formats import runs
from labkit.formats.scope_sha import LOCAL_ROOTS
from labkit.formats.repo import (
    GitError,
    rel_posix,
    tree_diff,
    tree_then,
)


@dataclass(frozen=True)
class CodeThen:
    """The tracked tree a run started from (`code_then`).

    Attributes:
        run_id: The run.
        tree: The tree's id in the repository's object store; None when it
            cannot be read back.
        where: What the tree is — the commit, and the patch where one was
            applied — or why it cannot be read back.
    """

    run_id: str
    tree: str | None
    where: str


def code_then(rd: runs.RunDir, root: Path | None) -> CodeThen:
    """The tree run RD started from: its recorded commit with its
    `uncommitted.patch` applied (`repo.tree_then`). No tree, the reason in
    WHERE: every reason the run's start point does not read back
    (`runs.start_point`: no record, no commit, no repository, a patch
    gone, a patch beside a record of a clean tree, a commit this clone
    does not hold), a run gone from the tree
    that started from a changed tree (its patch is read from its directory
    only), or a patch that does not apply. Never the tree as it stands now."""
    name = rd.dir.name
    # before `runs.start_point`: a run gone from the tree, read at a commit,
    # has no directory to read its patch from, and `runs.patch_lost` would
    # call the patch lost; this sentence says how to get it back instead
    if (
        rd.config is not None
        and runs.recorded_commit(rd.config) is not None
        and root is not None
        and rd.from_commit is not None
        and rd.config.git.endswith(runs.DIRTY_MARK)
    ):
        return CodeThen(
            name,
            None,
            f"run {name} is gone from the tree and started from a tree with "
            f"changes; its uncommitted.patch is read from its directory only — "
            f"restore the directory from {rd.from_commit[:12]} to compare",
        )
    start = runs.start_point(rd, root, subject=f"run {name}")
    if isinstance(start, str):
        return CodeThen(name, None, start)
    commit = start.commit
    patch = runs.patch_text(rd.dir) if start.changed_tree else ""
    try:
        tree = tree_then(start.root, commit, patch)
    except GitError as exc:
        return CodeThen(name, None, f"run {name}: {exc}")
    patched = " with its uncommitted.patch" if patch.strip() else ""
    return CodeThen(name, tree, f"{commit[:12]}{patched}")


def code_scope(area: Path, root: Path) -> list[str]:
    """The pathspecs two runs of AREA are compared within: every Python
    file of AREA outside its `runs/`, and ROOT's shared code folders
    (`scope_sha.LOCAL_ROOTS`) — the code `scope_sha` stamps, not the area's outputs,
    data, prompts or protocols. AREA lies under ROOT."""
    rel = rel_posix(area, root)
    base = "" if rel in ("", ".") else f"{rel}/"
    return [
        f":(glob){base}**/*.py",
        *LOCAL_ROOTS,
        f":(exclude){base}{runs.RUNS_DIR}",
    ]


@dataclass(frozen=True)
class CodeDifference:
    """How one run's code differs from another's (`code_difference`).

    Attributes:
        stat: Git's per-file summary, every file listed.
        diff: The whole unified diff; "" when the code is the same.
    """

    stat: str
    diff: str


def code_difference(root: Path, scope: list[str], old: str, new: str) -> CodeDifference:
    """How tree NEW differs from tree OLD within SCOPE (`code_scope`), both
    `CodeThen.tree` of runs of one repository ROOT. Raises GitError when git
    fails."""
    return CodeDifference(
        tree_diff(root, old, new, scope, stat=True),
        tree_diff(root, old, new, scope),
    )
