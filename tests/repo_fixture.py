"""A temporary git repository for test fixtures: the one git runner and the
one setup.

One home for "run git in a test's repository" and for "make this directory a
repository that can commit", so a test file states what it commits and not
how git is called (`tests/test_one_home.py` holds a second runner or setup
out). A runner that differs on purpose — it returns the process, or
tolerates a failing git — stays in its file and is named there.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

#: the committer every fixture commit carries, given on the command line: a
#: repository needs no `git config` call before its first commit, and one
#: that sets the same identity in its config (as a command under test may
#: need it) is not changed by it
NAME, EMAIL = "t", "t@t"
IDENTITY = ("-c", f"user.name={NAME}", "-c", f"user.email={EMAIL}")


def git(root: Path, *args: str) -> str:
    """Run `git ARGS` in ROOT as the fixture identity; its stdout, stripped.

    Raises:
        subprocess.CalledProcessError: git exited non-zero; its stderr is on
            the exception.
    """
    return subprocess.run(
        ["git", *IDENTITY, *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def init_repo(root: Path) -> None:
    """Make ROOT a git repository whose config carries the fixture identity:
    a command under test that commits there itself finds one. No commit is
    made.

    Side effects:
        Creates ROOT/.git and writes `user.email` and `user.name` into its
        config.
    """
    git(root, "init", "-q")
    git(root, "config", "user.email", EMAIL)
    git(root, "config", "user.name", NAME)
