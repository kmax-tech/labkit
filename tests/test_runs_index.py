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

from labkit.gates import hook_post_change
from labkit.formats import run_index
from labkit.formats.area_state import state_of
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
            found = runlog.unindexed(area, set())
            self.assertEqual((len(found.rows), found.unreadable), (2, []))
            # a folder without config.json is named, never dropped without a word
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
        row = ["2026-10-27T10-00-00_ab12"] + [""] * (len(run_index.RUN_INDEX_COLS) - 1)
        index = Path("runs.tsv")
        why = run_index.index_refusal(index, [row, row])
        self.assertIn("more than once", why or "")
        self.assertIsNone(run_index.index_refusal(index, [row]))
        # old columns: one sentence for every reader and writer, raised where
        # the index is read
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "runs.tsv"
            old.write_text("run_id\n", encoding="utf-8")
            with self.assertRaises(run_index.RunIndexError) as cm:
                run_index.read_index(old)
            self.assertIn("don't match this runlog", cm.exception.why)


class IndexRead(unittest.TestCase):
    """The index is read as it is written (`run_index.read_index`): the current
    columns, every row whole. A short row is refused with its line, never
    read as no measurement: a row holding only its run id would drop a
    measured run from `has_measured`."""

    PID = "p-0123456789abcdef"

    def area_with(self, d: str, *lines: str) -> Path:
        area = Path(d)
        (area / run_index.RUN_INDEX).write_text(
            "".join(f"{ln}\n" for ln in lines), encoding="utf-8"
        )
        return area

    def row(self, run_id: str) -> str:
        return "\t".join(
            [run_id, "abc1234", "01_measure.py", "{}", "{}", "{}", "", self.PID]
        )

    def test_a_valid_index_lists_a_run_whose_folder_is_gone(self):
        with tempfile.TemporaryDirectory() as d:
            area = self.area_with(
                d,
                "\t".join(run_index.RUN_INDEX_COLS),
                self.row("2026-01-01T00-00-00_0001"),
            )
            self.assertEqual(
                run_index.indexed_runs(area, self.PID), ["2026-01-01T00-00-00_0001"]
            )
            self.assertEqual(run_index.indexed_runs(area, "p-other"), [])

    def test_a_short_row_is_refused_with_its_line(self):
        with tempfile.TemporaryDirectory() as d:
            area = self.area_with(
                d,
                "\t".join(run_index.RUN_INDEX_COLS),
                self.row("2026-01-01T00-00-00_0001"),
                "2026-01-01T00-00-00_0002",
            )
            for pid in (self.PID, None):
                with self.subTest(pid=pid):
                    with self.assertRaises(run_index.RunIndexError) as cm:
                        run_index.indexed_runs(area, pid)
                    self.assertIn("runs.tsv:3", str(cm.exception))
                    self.assertIn("1 of 8 tab-separated columns", str(cm.exception))

    def test_an_old_header_is_refused_as_the_writer_refuses_it(self):
        with tempfile.TemporaryDirectory() as d:
            area = self.area_with(d, "run_id\tprotocol_id", f"r1\t{self.PID}")
            with self.assertRaises(run_index.RunIndexError) as cm:
                run_index.indexed_runs(area, self.PID)
            self.assertEqual(
                cm.exception.why, run_index.header_refusal(["run_id", "protocol_id"])
            )

    def test_the_evidence_hook_tells_a_damaged_index_instead_of_failing(self):

        with tempfile.TemporaryDirectory() as d:
            header = "\t".join(run_index.RUN_INDEX_COLS)
            area = self.area_with(d, header, "2026-01-01T00-00-00_0002")
            with self.assertRaises(run_index.RunIndexError) as cm:
                state_of(area)
            self.assertIn("runs.tsv:2", cm.exception.why)
            # the twin: a whole row of a run whose folder is gone is told as gone
            self.area_with(d, header, self.row("2026-01-01T00-00-00_0001"))
            (line,) = hook_post_change.index_problems(state_of(area))
            self.assertIn("2026-01-01T00-00-00_0001: its directory is gone", line)

    def test_a_run_does_not_start_on_a_short_row(self):
        with tempfile.TemporaryDirectory() as d:
            area = self.area_with(
                d, "\t".join(run_index.RUN_INDEX_COLS), "2026-01-01T00-00-00_0002"
            )
            (area / "PROTOCOL-x.md").write_text(
                head(repeat_cost="low", promises=None)
                + "\n- **Question / hypothesis:** how many?\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, r"runs\.tsv:2"):
                with contextlib.redirect_stdout(io.StringIO()):
                    with runlog.run("x", {}, area, run_kind="measurement"):
                        pass
            self.assertFalse((area / "runs").exists())

    def test_an_empty_index_gets_its_header_before_the_first_row(self):
        with tempfile.TemporaryDirectory() as d:
            index = Path(d) / run_index.RUN_INDEX
            index.write_text("", encoding="utf-8")
            run_index.append_row(
                index, [self.row("2026-01-01T00-00-00_0001")][0].split("\t")
            )
            header, rows = run_index.read_index(index)
            self.assertEqual(header, run_index.RUN_INDEX_COLS)
            self.assertEqual(len(rows), 1)

    def test_reindex_refuses_a_short_row_too(self):
        with tempfile.TemporaryDirectory() as d:
            area = self.area_with(
                d, "\t".join(run_index.RUN_INDEX_COLS), "2026-01-01T00-00-00_0002"
            )
            err = io.StringIO()
            with (
                contextlib.redirect_stderr(err),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(runlog.reindex(area), 2)
            self.assertIn("runs.tsv:2", err.getvalue())


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
