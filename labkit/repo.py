"""repo — where things are: repo root, an area's protocols, git.

Small questions every gate asks, answered once. Before 2026-10-06 they were
answered five times: each module globbed `PROTOCOL-*.md` itself, three
functions found the repo root by three different rules, and two private
`_git` helpers turned EVERY git failure into an empty string — so a git that
failed to run read as "working tree clean".

Two git calls, by what a non-zero exit means:

    git(args, cwd)      the output; None outside a repo; GitError otherwise
    git_run(args, cwd)  the completed process, for commands whose exit code
                        IS the answer (`ls-files --error-unmatch`,
                        `rev-parse --verify`, `show HEAD:path`)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

GIT_TIMEOUT_S = 20


class GitError(RuntimeError):
    """git could not be run, or failed inside a repository."""


def area_path(arg: str) -> Path:
    """The area a command argument names: a directory as given, else the
    bare name as `labkit-init exp` prints it — `01-<name>` or `<name>` — under
    `experiments/` of the working directory or of its repository. Returns
    the argument unchanged when nothing (or more than one area) matches, so
    the caller's "no such area" still speaks (2026-10-07: two agents passed
    `01-docs-per-case` to code-check and were refused)."""
    given = Path(arg)
    if given.is_dir() or given.is_absolute() or "/" in arg:
        return given
    hits: set[Path] = set()
    for base in {Path.cwd(), git_root(Path.cwd()) or Path.cwd()}:
        exp = base / "experiments"
        if (exp / arg).is_dir():
            hits.add((exp / arg).resolve())
        hits.update(p.resolve() for p in exp.glob(f"[0-9]*-{arg}") if p.is_dir())
    return hits.pop() if len(hits) == 1 else given


def no_such_area(area: Path) -> str:
    """The sentence for an area path that is not a directory. A relative
    path resolves against the working directory, so the sentence names it
    (2026-10-07: an agent called code-check from inside the area with the
    repo-relative path and tried four spellings)."""
    where = "" if area.is_absolute() else f" (relative to {Path.cwd()})"
    return (
        f"no such area: {area}{where} — give the area's path or its name "
        f"as `labkit-init exp` printed it (01-<name>)"
    )


def area_protocols(area: Path) -> list[Path]:
    """Every protocol in the area (`PROTOCOL-*.md` directly in it),
    lexicographic — a list, not a first hit.

    The series rule gives every follow-up its own `PROTOCOL-s<N>-<slug>.md`,
    so an area legitimately holds many. Returning `sorted(...)[0]` picked
    one of them wordlessly, and lexicographic order is not temporal order:
    in an area running s1..s13 the pick was always s1. A green check against
    the wrong protocol is worse than no check, so the caller must choose
    (2026-09-26).
    """
    return sorted(area.glob("PROTOCOL-*.md"))


def git_root(path: Path) -> Path | None:
    """The nearest ancestor (or `path`) holding `.git`; None outside a repo."""
    base = path if path.is_dir() else path.parent
    for parent in [base.resolve(), *base.resolve().parents]:
        if (parent / ".git").exists():
            return parent
    return None


def layout_root(path: Path) -> Path:
    """Where an area's repo layout starts: the git root, else the nearest
    ancestor with `CLAUDE.md` or `tests/` (a freshly stamped tree before
    `git init`), else `path` itself."""
    root = git_root(path)
    if root is not None:
        return root
    base = (path if path.is_dir() else path.parent).resolve()  # "." has no parents
    for parent in [base, *base.parents]:
        if (parent / "CLAUDE.md").is_file() or (parent / "tests").is_dir():
            return parent
    return base


def git_run(
    args: list[str], cwd: Path, timeout: float = GIT_TIMEOUT_S
) -> subprocess.CompletedProcess[str]:
    """Run git; the caller reads the exit code. Raises GitError only when
    git itself cannot run (missing binary, timeout)."""
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError(f"git {' '.join(args)} in {cwd}: {exc}") from exc


def git(args: list[str], cwd: Path, timeout: float = GIT_TIMEOUT_S) -> str | None:
    """git's stripped output; None when `cwd` is not inside a repository.

    Any other failure raises GitError with git's own message — an empty
    string here used to mean "clean" whether or not git had run.
    """
    if git_root(cwd) is None:
        return None
    r = git_run(args, cwd, timeout)
    if r.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} in {cwd} failed "
            f"(exit {r.returncode}): {r.stderr.strip()}"
        )
    return r.stdout.strip()


def choose_protocol(area: Path, protocol: Path | None, tool: str) -> Path | None:
    """The protocol a command holds the area to: the named one, else the
    area's only one. Prints why (prefixed with `tool`) and returns None when
    there is none, or several and none is named — a gate never guesses."""
    if protocol is not None:
        if not protocol.is_file():
            print(f"{tool}: no such protocol: {protocol}")
            return None
        return protocol
    protocols = area_protocols(area)
    if not protocols:
        print(f"{tool}: no PROTOCOL-*.md in {area}")
        return None
    if len(protocols) > 1:
        print(
            f"{tool}: {len(protocols)} protocols in {area} — name one with --protocol FILE:"
        )
        for p in protocols:
            print(f"  {p}")
        return None
    return protocols[0]
