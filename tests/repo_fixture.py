"""A temporary git repository for test fixtures: the one git runner.

One home for "run git in a test's repository", so a test file states what it
commits and not how git is called (`tests/test_one_home.py` holds a second
runner out). A runner that differs on purpose — it returns the process, or
tolerates a failing git — stays in its file and is named there.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

#: the committer every fixture commit carries, given on the command line: a
#: repository needs no `git config` call before its first commit, and one
#: that sets the same identity in its config (as a command under test may
#: need it) is not changed by it
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@t")


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
