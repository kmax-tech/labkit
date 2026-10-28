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
                head(repeat_cost="low", promises=None)
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
            # the reading writes nothing; reindex appends what it found
            # (audit 2026-10-27, third, M4)
            found = runlog.unindexed(area, set())
            self.assertEqual((len(found.rows), found.unreadable), (2, []))
            # a folder without config.json was dropped without a word
            # (audit 2026-10-28, C4)
            stray = area / "runs" / "2026-10-28T10-00-00_abcd"
            stray.mkdir()
            self.assertEqual(runlog.unindexed(area, set()).no_record, [stray.name])
            stray.rmdir()
            self.assertFalse(index.exists())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runlog.reindex(area), 0)
            rebuilt = index.read_text(encoding="utf-8").splitlines()
            # the header first; the rows as a set: two runs of one second
            # differ only in their random suffix, and no record holds which
            # of them started first (`runs.run_dirs`)
            self.assertEqual(rebuilt[0], appended.splitlines()[0])
            self.assertEqual(sorted(rebuilt[1:]), sorted(appended.splitlines()[1:]))


class IndexRefusal(unittest.TestCase):
    def test_a_run_listed_twice_is_refused_old_columns_too(self):
        row = ["2026-10-27T10-00-00_ab12"] + [""] * (len(runlog.RUN_INDEX_COLS) - 1)
        index = Path("runs.tsv")
        why = runlog.index_refusal(index, runlog.RUN_INDEX_COLS, [row, row])
        self.assertIn("more than once", why or "")
        # one sentence for the run's start and reindex (audit 2026-10-28, H4)
        self.assertIn(
            "don't match this runlog", runlog.index_refusal(index, ["run_id"], []) or ""
        )
        self.assertIsNone(runlog.index_refusal(index, runlog.RUN_INDEX_COLS, [row]))


class IgnoredByTheStamp(unittest.TestCase):
    def test_a_stamped_lab_ignores_the_index(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lab"
            with contextlib.redirect_stdout(io.StringIO()):
                scaffold.stamp_lab(root, root.name)
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
