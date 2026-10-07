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
    base = (path if path.is_dir() else path.parent).resolve()   # "." has no parents
    for parent in [base, *base.parents]:
        if (parent / "CLAUDE.md").is_file() or (parent / "tests").is_dir():
            return parent
    return base


def git_run(args: list[str], cwd: Path,
            timeout: float = GIT_TIMEOUT_S) -> subprocess.CompletedProcess[str]:
    """Run git; the caller reads the exit code. Raises GitError only when
    git itself cannot run (missing binary, timeout)."""
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=timeout)
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
        raise GitError(f"git {' '.join(args)} in {cwd} failed "
                       f"(exit {r.returncode}): {r.stderr.strip()}")
    return r.stdout.strip()
