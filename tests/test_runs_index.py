"""`runs.tsv` is a local, rebuildable view of the run records.

The versioned records under `runs/<run_id>/` are the truth; the index is
git-ignored by the lab stamp and `runlog reindex` writes it back. This
holds the claim that makes ignoring it safe: the rebuilt index equals the
one the runs appended, row for row, and no reader needs it.
"""

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from labkit.run import runlog
from labkit.tools import scaffold
from protocol_fixture import head


class RebuiltIndex(unittest.TestCase):
    def test_reindex_writes_back_the_index_the_runs_appended(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(
                head(cost="seconds", promises=None)
                + "\n- **Question / hypothesis:** how many?\n",
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                for n in (1, 2):
                    with runlog.run("x", {"n": n}, area, run_kind="measurement") as run:
                        run.metrics(count=n)
            index = area / "runs.tsv"
            appended = index.read_text(encoding="utf-8")
            self.assertEqual(len(appended.splitlines()), 3)  # header + two runs
            index.unlink()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runlog.reindex(area), 0)
            rebuilt = index.read_text(encoding="utf-8").splitlines()
            # the header first; the rows as a set: two runs of one second
            # differ only in their random suffix, and no record holds which
            # of them started first (`runs.run_dirs`)
            self.assertEqual(rebuilt[0], appended.splitlines()[0])
            self.assertEqual(sorted(rebuilt[1:]), sorted(appended.splitlines()[1:]))


class IgnoredByTheStamp(unittest.TestCase):
    def test_a_stamped_lab_ignores_the_index(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lab"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(scaffold.main(["lab", str(root)]), 0)
            area = root / "experiments" / "01-x"
            area.mkdir(parents=True)
            (area / "runs.tsv").write_text("run_id\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", "experiments/01-x/runs.tsv"], cwd=root
            )
            self.assertEqual(ignored.returncode, 0, "runs.tsv is not ignored")


if __name__ == "__main__":
    unittest.main()
