"""The suite never writes into the repo it runs from, even inside a git hook.

A git hook runs with GIT_DIR (and in a worktree more) exported; a test's
`git init` + `git config` on its temporary directory then rewrites the real
repo's config (2026-10-09: `core.bare = true`, a local user `t <t@t>`).
tests/conftest.py drops every GIT_* variable. The twin runs the same steps
without the conftest and must touch the decoy — otherwise the guarded run
would prove nothing.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CONFTEST = Path(__file__).resolve().parent / "conftest.py"

# what a test does to its own temporary repo
STEPS = """
import subprocess, sys
target = sys.argv[1]
subprocess.run(["git", "init", "-q", target], check=True)
subprocess.run(["git", "-C", target, "config", "user.email", "t@t"], check=True)
"""


def decoy_after(load_conftest: bool) -> str:
    """Run the steps with GIT_DIR on a decoy repo; the decoy's config afterwards."""
    with tempfile.TemporaryDirectory() as d:
        decoy, target = Path(d) / "decoy", Path(d) / "target"
        subprocess.run(["git", "init", "-q", str(decoy)], check=True)
        prelude = (
            f"import runpy; runpy.run_path({str(CONFTEST)!r})\n"
            if load_conftest
            else ""
        )
        env = {**os.environ, "GIT_DIR": str(decoy / ".git")}
        subprocess.run(
            [sys.executable, "-c", prelude + STEPS, str(target)], env=env, check=True
        )
        return (decoy / ".git" / "config").read_text(encoding="utf-8")


class GitEnvIsolation(unittest.TestCase):
    def test_no_git_variable_reaches_a_test(self):
        self.assertEqual([n for n in os.environ if n.startswith("GIT_")], [])

    def test_conftest_keeps_the_decoy_untouched(self):
        config = decoy_after(load_conftest=True)
        self.assertNotIn("t@t", config)
        self.assertNotIn("bare = true", config)

    def test_without_conftest_the_decoy_is_hit(self):
        self.assertIn("t@t", decoy_after(load_conftest=False))


if __name__ == "__main__":
    unittest.main()
