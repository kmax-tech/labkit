"""protocol_then — a protocol as one run saw it.

The text a run started under is its recorded commit's protocol with the
part of its `uncommitted.patch` that touches the protocol, held to the
promise block the run recorded (`as_measured`), and the step it made is that text's `[builds_on]`
(`step_then`); the file is found by the
id the run is bound to, now (`bound_protocol_file`) and in that commit
(`protocol_path_at`). Mechanics only — what a difference between two such
texts means is `protocol_history`'s and the gates'. A protocol the
working tree no longer holds is found by its id in the last commit that
held its file (`last_held_with_id`). Read-only; git is asked through
`repo`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import promises, protocol_block, runs
from labkit.formats.area_state import last_committed
from labkit.formats.repo import (
    PROTOCOL_FILE,
    SKIP_DIRS,
    is_protocol_name,
    protocol_file_name,
    GitError,
    blob_text,
    blobs_then,
    commit_known,
    git_run,
    rel_posix,
    repo_protocols,
    text_at,
)
from labkit.formats.runs import RunDir


def bound_protocol_file(area: Path, pid: str, recorded: str | None) -> Path:
    """The protocol file of AREA that a run bound to PID was measured
    under, to read its text then from (`as_measured`):
    the one carrying PID now, else the path the run RECORDED, else the
    stamped name — at the run's commit `as_measured` finds the file by the
    id again. The one finding of a run's protocol by its binding."""
    try:
        return protocol_block.find_by_id(area, pid)
    except protocol_block.BlockError:
        if recorded and not Path(recorded).is_absolute():
            return area / recorded
        return area / protocol_file_name(pid)


def protocol_path_at(root: Path, commit: str, pid: str) -> Path | None:
    """Where the protocol carrying id PID stood in COMMIT of the repository
    ROOT — the `PROTOCOL-*.md` whose head names PID, outside SKIP_DIRS
    (`runs/`, `data/`, `.venv/` …), as `repo.repo_protocols` reads —, or
    None when no file there does. The id is the binding and survives a
    rename or a move (docs/protocol-run-binding.md); the head is read as
    TOML only, since an
    older commit holds an older standard `protocol_block.head` refuses.
    Raises GitError when git cannot run."""
    listed = git_run(["ls-tree", "-r", "-z", "--name-only", commit], root)
    if listed.returncode != 0:
        raise GitError(f"git ls-tree {commit[:12]} in {root}: {listed.stderr.strip()}")
    names = [n for n in listed.stdout.split("\0") if n]
    # the files a repo-wide scan reads (`repo.repo_protocols`): a copy such
    # as PROTOCOL-a.txt or one under runs/ with the same id would sort
    # first and be read as the protocol
    candidates = (
        n
        for n in names
        if is_protocol_name(Path(n).name) and not SKIP_DIRS & set(Path(n).parts[:-1])
    )
    for rel in sorted(candidates):
        text = text_at(root, root / rel, commit)
        if text is not None and _id_then(text) == pid:
            return root / rel
    return None


def _id_then(text: str) -> object:
    """The id the head of a committed protocol TEXT names; None where its
    block names none or does not parse — no id to bind. The head is read
    as TOML only, since an older commit holds an older standard
    `protocol_block.head` refuses."""
    try:
        table = protocol_block.parse_toml_block(text).get("protocol", {})
    except protocol_block.BlockError:
        return None
    return table.get("id") if isinstance(table, dict) else None


def last_held_with_id(root: Path, pid: str) -> list[tuple[Path, str]]:
    """(path, commit) for each protocol file the working tree under the
    repository ROOT lacks whose head named PID in the last commit that
    held the file — HEAD while its deletion is not committed, else the
    deletion's parent (`area_state.last_committed`) —, sorted by path:
    `git checkout COMMIT -- PATH` brings a protocol carrying PID back.
    Among the files a repo-wide scan reads (`repo.repo_protocols`:
    `PROTOCOL-*.md` outside SKIP_DIRS). [] when no commit held such a
    file: the protocol was never committed, or its id was changed in a
    file that still stands, which this does not look into. Raises
    HistoryUnread (a RuntimeError) when git cannot list or read the
    history, GitError when git cannot run."""
    skipped = "|".join(re.escape(d) for d in sorted(SKIP_DIRS))
    name = rf"((?:(?!(?:{skipped})/)[^/]+/)*{PROTOCOL_FILE})"
    standing = {rel_posix(p, root) for p in repo_protocols(root)}
    return [
        (root / rel, commit)
        for rel, text, commit in last_committed(root, root, name, standing)
        if _id_then(text) == pid
    ]


#: the role under which `as_measured` names a run unless the caller gives
#: another
FIRST_MEASUREMENT = "its first measurement"


def as_measured(
    protocol: Path,
    rd: "RunDir",
    root: Path | None,
    *,
    role: str = FIRST_MEASUREMENT,
) -> tuple[str | None, str]:
    """(text, where): PROTOCOL as run RD saw it — its recorded commit's text
    with the part of the run's `uncommitted.patch` that touches the protocol
    applied (`repo.blobs_then`), held to the promise block the run recorded.
    TEXT None, WHERE then saying why and what brings it back, when that
    cannot be read: no recorded commit, a commit this clone does not hold
    (`git fetch` brings it), git unable to read that commit's tree or the
    blob, or a patch that does not apply (git's own error), a tree without
    the protocol (untracked when the run started), a text whose block is
    not the one the run recorded, a run started from a changed tree whose
    uncommitted.patch is gone (`runs.patch_lost`: the commit alone is not what
    it saw). A comparison that needs the text holds on None
    (`unread_measurements`), never reads it as no change. ROLE opens each
    WHERE sentence before RD's id: "its first measurement" (the default),
    "run" or "origin run"."""
    commit = runs.recorded_commit(rd.config) if rd.config is not None else None
    if commit is None or root is None:
        return None, f"{role} {rd.dir.name} recorded no commit"
    if rd.config is not None and runs.patch_lost(rd):
        return None, (
            f"{role} {rd.dir.name} started from a tree with changes "
            f"({rd.config.git}), and its uncommitted.patch is gone: the commit "
            f"alone is not what it saw"
        )
    if not commit_known(root, commit):
        return None, (
            f"{role} {rd.dir.name} started at {commit[:12]}, a commit "
            f"this clone does not hold — `git fetch` brings it"
        )
    patch_file = runs.patch_path(rd.dir)
    patch = patch_file.read_text(encoding="utf-8") if patch_file.is_file() else ""
    pid = rd.config.protocol.id if rd.config is not None else None
    try:
        blob = blobs_then(root, commit, patch, [protocol])[protocol]
        then = protocol_path_at(root, commit, pid) if blob is None and pid else None
        if then is not None:  # renamed or moved since: found by its id
            blob = blobs_then(root, commit, patch, [then])[then]
    except GitError as exc:
        return None, f"{role} {rd.dir.name}: {exc}"
    if blob is None:
        return None, (
            f"{role} {rd.dir.name} ran with the protocol untracked: "
            f"no commit holds what it registered"
        )
    try:
        text = blob_text(root, blob)
    except RuntimeError as exc:  # `git cat-file` could not read the blob
        return None, f"{role} {rd.dir.name}: {exc}"
    patched = " with its uncommitted.patch" if patch.strip() else ""
    recorded = (rd.config.promises or {}).get("block_sha") if rd.config else None
    if recorded is not None and block_sha_of(text) != recorded:
        return None, (
            f"{role} {rd.dir.name} recorded block {recorded}, and "
            f"{commit[:12]}{patched} gives {block_sha_of(text)}: what it registered "
            f"cannot be read back"
        )
    return (
        text,
        f"as {role} {rd.dir.name} saw it ({commit[:12]}{patched})",
    )


@dataclass(frozen=True)
class StepThen:
    """The step a run made, read from its own protocol text (`step_then`).

    Attributes:
        run_id: The run.
        text: The protocol as the run saw it, None when it cannot be read
            back.
        step: Its `[builds_on]` then, None when it declared none — or when
            the step cannot be told (UNKNOWN set).
        where: Where TEXT was read from, or why it cannot be.
        unknown: Why the step cannot be told — the text cannot be read back,
            or its `[builds_on]` does not read; None when it can.
    """

    run_id: str
    text: str | None
    step: protocol_block.BuildsOn | None
    where: str
    unknown: str | None


def step_then(protocol: Path, rd: RunDir, root: Path | None) -> StepThen:
    """The step run RD of PROTOCOL made, as its own text holds it
    (`as_measured`): the one reconstruction every consumer of a run's basis
    shares — the basis is stored only there, never in the run record. When
    it cannot be read back the step is unknown and says why; nothing is
    invented in its place. RD's config must read. Raises RuntimeError when
    git fails."""
    text, where = as_measured(protocol, rd, root, role="run")
    if text is None:
        return StepThen(rd.dir.name, None, None, where, where)
    try:
        step = protocol_block.builds_on(text)
    except protocol_block.BlockError as exc:
        why = f"run {rd.dir.name}: its [builds_on] then does not read — {exc}"
        return StepThen(rd.dir.name, text, None, where, why)
    return StepThen(rd.dir.name, text, step, where, None)


def block_sha_of(text: str) -> str | None:
    """The digest of TEXT's promise block; None without one or unreadable."""
    try:
        block = promises.parse_block(text)
    except promises.PromiseError:
        return None
    return block.sha if block is not None else None
