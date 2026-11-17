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
from labkit.formats.repo import (
    GitError,
    commit_known,
    rel_posix,
    tree_diff,
    tree_then,
)

#: the repository folders beside the area whose modules an area imports
#: (`scope_sha`: the repo-local helpers)
SHARED_CODE = ("lib", "src")


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
    WHERE: a record that does not read, no recorded commit or no
    repository (ROOT None), a commit this clone does not hold, a run
    started from a changed tree whose patch is gone (the commit alone is
    not what it ran), or a patch that does not apply. Never the tree as it
    stands now."""
    name = rd.dir.name
    if rd.config is None:
        return CodeThen(name, None, f"run {name} has no readable record")
    commit = runs.recorded_commit(rd.config)
    if commit is None or root is None:
        return CodeThen(name, None, f"run {name} recorded no commit")
    dirty = rd.config.git.endswith(runs.DIRTY_MARK)
    if rd.from_commit is not None and dirty:
        return CodeThen(
            name,
            None,
            f"run {name} is gone from the tree and started from a tree with "
            f"changes; its uncommitted.patch is read from its directory only — "
            f"restore the directory from {rd.from_commit[:12]} to compare",
        )
    if rd.from_commit is None and runs.patch_lost(rd):
        return CodeThen(
            name,
            None,
            f"run {name} started from a tree with changes and its "
            f"uncommitted.patch is gone: the commit alone is not what it ran",
        )
    if not commit_known(root, commit):
        return CodeThen(
            name,
            None,
            f"run {name} started at {commit[:12]}, a commit this clone does "
            f"not hold — `git fetch` brings it",
        )
    patch = runs.patch_text(rd.dir) if dirty else ""
    try:
        tree = tree_then(root, commit, patch)
    except GitError as exc:
        return CodeThen(name, None, f"run {name}: {exc}")
    patched = " with its uncommitted.patch" if patch.strip() else ""
    return CodeThen(name, tree, f"{commit[:12]}{patched}")


def code_scope(area: Path, root: Path) -> list[str]:
    """The pathspecs two runs of AREA are compared within: every Python
    file of AREA outside its `runs/`, and ROOT's shared code folders
    (SHARED_CODE) — the code `scope_sha` stamps, not the area's outputs,
    data, prompts or protocols. AREA lies under ROOT."""
    rel = rel_posix(area, root)
    base = "" if rel in ("", ".") else f"{rel}/"
    return [
        f":(glob){base}**/*.py",
        *SHARED_CODE,
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
