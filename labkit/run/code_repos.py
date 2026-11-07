"""code_repos — the code a run imported, per git repository.

A run's result belongs to the code that produced it, and that code is not
only the lab repo's: labkit, a framework installed editable and a topic
package each live in a checkout of their own. The lab repo's commit and
patch say nothing about them, and an editable install's metadata names a
path, not a commit. This module finds every repository that holds a module
the process imported — from each module's source path — and records per
repository its HEAD, its tracked changes as a patch, and the imported files
git does not track, copied as they were:

    runs/<run_id>/code.json             one entry per repository (`write_code`)
    runs/<run_id>/code/<name>.patch     `git diff HEAD` of a repository with
                                        tracked changes
    runs/<run_id>/code/<name>/<rel>     an imported file git does not track

Not a repository's code: what lies under an install prefix (the stdlib,
site-packages, a venv inside a repository — `env_state` in `provenance`
records the environment) and a file git ignores. A source file outside
both, on a `sys.path` entry that is no checkout, is listed with its digest
under `outside_git`, not copied. The entry script is the run's
`script-source` copy, not listed here.

Read twice: at the start, before the run directory exists (`read_code`), and at
a clean finish, for modules imported during the run — a framework that
imports the topic its config names. A repository first seen at the finish
is recorded as it stood then (`read_at: "end"`); an untracked file first
imported then is copied then. A tracked file edited after the start and
imported later is not seen: the start's patch holds the tree as it was.
"""

from __future__ import annotations

import json
import os
import site
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import repo
from labkit.formats.files import write_atomic, write_atomic_bytes
from labkit.formats.gate import with_way_out
from labkit.formats.runs import CODE_DIR, CODE_FILE, RECORD_SHA_CHARS, RUN_SCHEMA
from labkit.formats.digests import file_digest

#: an imported file above this size is not copied, and a measurement
#: refuses to start on it (`require_recordable`): a "source file" that
#: large is data or generated code, and the record would carry it per run
COPY_CAP = 2 * 1024 * 1024


@dataclass(frozen=True)
class RepoCode:
    """One repository's part of the imported code, as read at one moment.

    Attributes:
        root: The checkout's top directory, resolved.
        origin: `git remote get-url origin`, None without that remote.
        commit: HEAD's full commit; "" before the first commit.
        patch: The tracked changes against HEAD (`repo.tree_patch`), ""
            when there are none or HEAD is unborn.
        untracked: The imported files git does not track, relative to
            ROOT — every imported file when HEAD is unborn.
        too_large: The part of UNTRACKED above `COPY_CAP`, not copied.
    """

    root: Path
    origin: str | None
    commit: str
    patch: str
    untracked: tuple[str, ...]
    too_large: tuple[str, ...]


@dataclass(frozen=True)
class CodeScan:
    """What `read_code` found: the repositories and, outside any, the source
    files with their digest (path → sha256)."""

    repos: tuple[RepoCode, ...]
    outside_git: tuple[tuple[str, str], ...]


def install_prefixes() -> tuple[str, ...]:
    """The directories that hold installed code, each as given and
    resolved, with a closing separator: the interpreter's and the venv's
    prefixes and the site-packages directories."""
    found = {
        sys.prefix,
        sys.base_prefix,
        sys.exec_prefix,
        sys.base_exec_prefix,
        *site.getsitepackages(),
        site.getusersitepackages(),
    }
    both = {*found, *(str(Path(p).resolve()) for p in found)}
    return tuple(sorted(os.path.join(p, "") for p in both))


def imported_files(modules: Iterable[object]) -> list[Path]:
    """The resolved source files of MODULES (each module's `__file__`) that
    exist and lie under no install prefix, `__main__` excepted, sorted.
    A path is held to the prefixes as given and again resolved — most
    modules are installed ones, and resolving each cost more than the
    rest of the scan."""
    prefixes = install_prefixes()
    out: set[Path] = set()
    for module in modules:
        if getattr(module, "__name__", None) == "__main__":
            continue
        name = getattr(module, "__file__", None)
        if not isinstance(name, str) or name.startswith(prefixes):
            continue
        path = Path(name).resolve()
        if str(path).startswith(prefixes) or not path.is_file():
            continue
        out.add(path)
    return sorted(out)


def read_code(modules: Iterable[object]) -> CodeScan:
    """The repositories holding the source files of MODULES
    (`imported_files`), each read as it stands now, and the source files
    outside any repository. Reads git and the files; writes nothing.
    Raises `repo.GitError` when git fails inside a repository."""
    by_root: dict[Path, list[Path]] = {}
    outside: list[tuple[str, str]] = []
    roots: dict[Path, Path | None] = {}  # directory → its checkout, looked up once
    for path in imported_files(modules):
        if path.parent not in roots:
            roots[path.parent] = repo.git_root(path.parent)
        root = roots[path.parent]
        if root is None:
            outside.append((str(path), file_digest(path)[:RECORD_SHA_CHARS]))
        else:
            by_root.setdefault(root, []).append(path)
    repos = [_repo_code(root, files) for root, files in sorted(by_root.items())]
    return CodeScan(tuple(r for r in repos if r is not None), tuple(outside))


def _repo_code(root: Path, files: list[Path]) -> RepoCode | None:
    """ROOT's state and the part of FILES it holds; None when git ignores
    every one of them (a build directory inside the checkout)."""
    rel = {f.relative_to(root).as_posix() for f in files}
    tracked, others = _ls_files(root)
    tracked, untracked = rel & tracked, rel & others
    if not tracked and not untracked:
        return None
    commit = repo.head_sha(root)
    if not commit:  # unborn HEAD: nothing is in a commit yet
        untracked |= tracked
    origin = repo.git_run(["remote", "get-url", "origin"], root)
    ordered = tuple(sorted(untracked))
    return RepoCode(
        root=root,
        origin=origin.stdout.strip() if origin.returncode == 0 else None,
        commit=commit,
        patch=repo.tree_patch(root) if commit else "",
        untracked=ordered,
        too_large=tuple(r for r in ordered if (root / r).stat().st_size > COPY_CAP),
    )


def _ls_files(root: Path) -> tuple[set[str], set[str]]:
    """(the files git tracks, the files it neither tracks nor ignores) at
    ROOT, relative to it — one `git ls-files -t` call."""
    r = repo.git_run(
        ["ls-files", "-z", "-t", "--cached", "--others", "--exclude-standard"], root
    )
    if r.returncode != 0:
        raise repo.GitError(f"git ls-files in {root}: {r.stderr.strip()}")
    tracked: set[str] = set()
    others: set[str] = set()
    for item in filter(None, r.stdout.split("\0")):
        tag, path = item[:2], item[2:]
        (others if tag == "? " else tracked).add(path)
    return tracked, others


def require_recordable(found: CodeScan) -> None:
    """Refuse a measurement whose imported code cannot all be recorded: an
    untracked file above `COPY_CAP` is in no commit and would not be
    copied. Raises SystemExit naming each file and the way out."""
    unrecorded = [str(r.root / rel) for r in found.repos for rel in r.too_large]
    if unrecorded:
        raise SystemExit(
            with_way_out(
                "runlog: the run imports untracked code it cannot record (above "
                f"{COPY_CAP // (1024 * 1024)} MB, in no commit):\n  "
                + "\n  ".join(unrecorded),
                "commit these files in their repository, then start the run again",
            )
        )


def write_code(run_dir: Path, start: CodeScan, end: CodeScan | None = None) -> None:
    """Write RUN_DIR's `code.json`, the patches and the copies of untracked
    files: the repositories of START (`read_at: "start"`) and, given END
    (the scan at a clean finish), those it adds (`read_at: "end"`) and the
    untracked files it adds to a start repository, copied now. A file
    above `COPY_CAP` is listed under `not_copied`. Raises OSError when a
    file cannot be read or written."""
    names: dict[Path, str] = {}
    entries: list[dict] = []
    for read_at, found in (("start", start), ("end", end)):
        if found is None:
            continue
        for code in found.repos:
            if code.root in names and read_at == "end":
                entry = next(e for e in entries if e["root"] == str(code.root))
                new = [r for r in code.untracked if r not in entry["untracked"]]
                _copy(run_dir, names[code.root], code, new)
                entry["untracked"].update({r: "end" for r in new})
                entry["not_copied"] += [r for r in code.too_large if r in new]
                continue
            name = _name(code.root, names)
            names[code.root] = name
            patch = None
            if code.patch:
                patch = f"{CODE_DIR}/{name}.patch"
                (run_dir / CODE_DIR).mkdir(exist_ok=True)
                write_atomic(run_dir / patch, code.patch)
            _copy(run_dir, name, code, list(code.untracked))
            entries.append(
                {
                    "root": str(code.root),
                    "origin": code.origin,
                    "commit": code.commit,
                    "dirty": bool(code.patch),
                    "patch": patch,
                    "untracked": {r: read_at for r in code.untracked},
                    "copies": f"{CODE_DIR}/{name}" if code.untracked else None,
                    "not_copied": list(code.too_large),
                    "read_at": read_at,
                }
            )
    outside = dict(start.outside_git)
    if end is not None:
        outside.update((p, d) for p, d in end.outside_git if p not in outside)
    write_atomic(
        run_dir / CODE_FILE,
        json.dumps(
            {"schema_version": RUN_SCHEMA, "repos": entries, "outside_git": outside},
            ensure_ascii=False,
            indent=2,
        ),
    )


def _name(root: Path, taken: dict[Path, str]) -> str:
    """ROOT's directory name, numbered when another repository has it."""
    name, n = root.name, 2
    while name in taken.values():
        name, n = f"{root.name}-{n}", n + 1
    return name


def _copy(run_dir: Path, name: str, code: RepoCode, rels: list[str]) -> None:
    """Copy each of RELS within CODE's root, except the too large, to
    `code/<NAME>/<rel>` in RUN_DIR."""
    for rel in rels:
        if rel in code.too_large:
            continue
        dest = run_dir / CODE_DIR / name / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_atomic_bytes(dest, (code.root / rel).read_bytes())
