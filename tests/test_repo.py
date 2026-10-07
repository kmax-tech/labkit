"""labkit.repo — repo root, an area's protocols and git, answered once.

Before 2026-10-06 two private `_git` helpers turned every git failure into
"", which preflight read as "working tree clean". Now outside a repo is
None, a failure inside one is loud, and an exit code that IS the answer
goes through git_run.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import repo, runlog  # noqa: E402


def make_repo(commit: bool = True) -> Path:
    d = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    if commit:
        (d / "f.txt").write_text("x")
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "x"], cwd=d, check=True)
    return d


class Layout(unittest.TestCase):
    def test_area_protocols_is_the_sorted_list(self):
        area = Path(tempfile.mkdtemp())
        for n in ("PROTOCOL-s10-b.md", "PROTOCOL-s1-a.md", "notes.md"):
            (area / n).write_text("")
        self.assertEqual([p.name for p in repo.area_protocols(area)],
                         ["PROTOCOL-s1-a.md", "PROTOCOL-s10-b.md"])

    def test_roots(self):
        plain = Path(tempfile.mkdtemp())
        self.assertIsNone(repo.git_root(plain))
        (plain / "tests").mkdir()
        area = plain / "experiments" / "01"
        area.mkdir(parents=True)
        self.assertEqual(repo.layout_root(area), plain.resolve())   # stamped tree, no git
        self.assertEqual(repo.layout_root(Path(".")), repo.layout_root(Path.cwd()))  # "." climbs too
        r = make_repo()
        (r / "a").mkdir()
        self.assertEqual(repo.git_root(r / "a"), r.resolve())
        self.assertEqual(repo.layout_root(r / "a"), r.resolve())


class Git(unittest.TestCase):
    def test_outside_a_repo_is_none(self):
        self.assertIsNone(repo.git(["status", "--porcelain"], Path(tempfile.mkdtemp())))

    def test_failure_inside_a_repo_is_loud(self):
        with self.assertRaises(repo.GitError) as cm:
            repo.git(["rev-parse", "--verify", "no-such-ref"], make_repo())
        self.assertIn("failed", str(cm.exception))

    def test_exit_code_as_answer(self):
        r = make_repo()
        self.assertEqual(repo.git_run(["ls-files", "--error-unmatch", "f.txt"], r).returncode, 0)
        self.assertNotEqual(repo.git_run(["ls-files", "--error-unmatch", "nope"], r).returncode, 0)

    def test_clean_and_dirty(self):
        r = make_repo()
        self.assertEqual(repo.git(["status", "--porcelain"], r), "")
        (r / "g.txt").write_text("y")
        self.assertIn("g.txt", repo.git(["status", "--porcelain"], r) or "")


class RunlogGitState(unittest.TestCase):
    def test_unborn_head_is_a_state_not_an_error(self):
        self.assertEqual(runlog._git_state(make_repo(commit=False)), "no-git")

    def test_committed_and_dirty(self):
        r = make_repo()
        clean = runlog._git_state(r)
        self.assertNotIn("+dirty", clean)
        (r / "g.txt").write_text("y")
        self.assertEqual(runlog._git_state(r), clean + "+dirty")


if __name__ == "__main__":
    unittest.main()
