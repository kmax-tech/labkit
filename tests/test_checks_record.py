""".githooks/checks: a whole run that passed is reused on the same state; a
changed file, other packages, a red or fast run and a state changed during
the run are not."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from repo_fixture import git

CHECKS = Path(__file__).resolve().parents[1] / ".githooks" / "checks"

# Stand-ins for the venv's tools: each call of pytest leaves a line in
# CALLS, its exit is PYTEST_EXIT, and with TOUCH set it rewrites that file
# while it "runs"; pip freeze prints PACKAGES.
PYTHON_STUB = """#!/bin/sh
case "$1" in
    -V) echo "Python 3.12.0" ;;
    -m)
        case "$2" in
            pip) printf '%s\\n' "${PACKAGES:-pkg==1}" ;;
            pytest)
                echo pytest >> "$CALLS"
                [ -n "${TOUCH:-}" ] && echo changed > "$TOUCH"
                exit "${PYTEST_EXIT:-0}" ;;
        esac ;;
esac
"""


class Record(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        git(self.repo, "init", "-q")
        bin_ = self.repo / ".venv" / "bin"
        bin_.mkdir(parents=True)
        for name, text in (
            ("python", PYTHON_STUB),
            ("ruff", "#!/bin/sh\n"),
            ("pyright", "#!/bin/sh\n"),
        ):
            (bin_ / name).write_text(text)
            (bin_ / name).chmod(0o755)
        hooks = self.repo / ".githooks"
        hooks.mkdir()
        shutil.copy(CHECKS, hooks / "checks")
        (self.repo / ".gitignore").write_text(".venv/\n")
        (self.repo / "code.py").write_text("x = 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "start")
        self.calls = self.repo.parent / f"{self.repo.name}-calls"
        self.addCleanup(lambda: self.calls.unlink(missing_ok=True))

    def checks(self, tier: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sh", ".githooks/checks", tier],
            cwd=self.repo,
            env={**os.environ, "CALLS": str(self.calls), **env},
            capture_output=True,
            text=True,
        )

    def pytest_runs(self) -> int:
        return len(self.calls.read_text().splitlines()) if self.calls.exists() else 0

    def test_a_green_full_run_stands_for_the_next_full_and_fast_run(self):
        self.assertEqual(self.checks("full").returncode, 0)
        again, fast = self.checks("full"), self.checks("fast")
        self.assertEqual((again.returncode, fast.returncode), (0, 0))
        self.assertIn("not run again", again.stdout)
        log = self.repo / ".git" / "labkit-checks-fast.log"
        self.assertIn("not run again", log.read_text())
        self.assertEqual(self.pytest_runs(), 1)

    def test_the_release_commit_of_the_checked_tree_reuses_the_record(self):
        (self.repo / "code.py").write_text("x = 2\n")  # the release's edit
        self.assertEqual(self.checks("full").returncode, 0)
        git(self.repo, "commit", "-q", "-am", "release")
        self.assertEqual(self.checks("full").returncode, 0)
        self.assertEqual(self.pytest_runs(), 1)

    def test_a_changed_tracked_or_untracked_file_runs_again(self):
        self.checks("full")
        (self.repo / "code.py").write_text("x = 2\n")
        self.checks("full")
        (self.repo / "new_test.py").write_text("")
        self.checks("full")
        self.assertEqual(self.pytest_runs(), 3)

    def test_other_installed_packages_run_again(self):
        self.checks("full")
        self.checks("full", PACKAGES="pkg==2")
        self.assertEqual(self.pytest_runs(), 2)

    def test_a_failed_or_fast_run_records_nothing(self):
        self.assertEqual(self.checks("full", PYTEST_EXIT="1").returncode, 1)
        self.assertEqual(self.checks("fast").returncode, 0)
        self.checks("fast")
        self.assertEqual(self.pytest_runs(), 3)

    def test_a_state_changed_during_the_run_records_nothing(self):
        done = self.checks("full", TOUCH=str(self.repo / "code.py"))
        self.assertEqual(done.returncode, 0)
        self.assertIn("no record", done.stderr)
        self.checks("full")
        self.assertEqual(self.pytest_runs(), 2)


if __name__ == "__main__":
    unittest.main()
