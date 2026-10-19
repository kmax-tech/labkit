"""runs — the one walk over an area's `runs/`, and the atomic write.

`run_dirs` reads every directory's metadata once and hands the three cases
back as data (no run, a run, an unreadable run); the callers decide. The
walk used to stand six times with six decisions (audit 2026-10-13).
"""

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from labkit.formats import runs, answering_run

CONFIG = {"schema_version": 2, "run_id": "r", "protocol": {"id": "p-" + "0" * 16}}


class RunDirs(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        self.runs = self.area / "runs"
        self.runs.mkdir()

    def _run(
        self, name: str, config: dict | str | None = CONFIG, done: bool = False
    ) -> Path:
        d = self.runs / name
        d.mkdir()
        if isinstance(config, dict):
            (d / "config.json").write_text(json.dumps(config))
        elif isinstance(config, str):
            (d / "config.json").write_text(config)
        if done:
            (d / "metrics.json").write_text("{}")
            (d / "completion.json").write_text("{}")
        return d

    def test_no_runs_dir_is_an_empty_list(self):
        self.assertEqual(runs.run_dirs(Path(tempfile.mkdtemp())), [])

    def test_the_three_cases_come_back_as_data_in_name_order(self):
        self._run("2026-01-01T00-00-00_bbbb", done=True)
        self._run("2026-01-01T00-00-00_aaaa", config=None)
        self._run("2026-01-01T00-00-00_cccc", config="{not json")
        (self.runs / "stray.txt").write_text("")  # a file, not a run
        got = runs.run_dirs(self.area)
        self.assertEqual([rd.dir.name[-4:] for rd in got], ["aaaa", "bbbb", "cccc"])
        no_run, a_run, broken = got
        self.assertEqual((no_run.config, no_run.error), (None, None))
        self.assertEqual((a_run.config or {}).get("run_id"), "r")
        self.assertIsNone(a_run.error)
        self.assertIsNone(broken.config)
        self.assertIn("unreadable run metadata", broken.error or "")

    def test_completed_runs_refuses_an_unreadable_run(self):
        self._run("2026-01-01T00-00-00_aaaa", done=True)
        self.assertEqual(len(runs.completed_runs(self.area, with_repeats=True)), 1)
        self._run("2026-01-01T00-00-00_bbbb", config="{not json")
        with self.assertRaises(runs.RunConfigError):
            runs.completed_runs(self.area, with_repeats=True)

    def test_bound_runs_sees_the_same_three_cases(self):
        self._run("2026-01-01T00-00-00_aaaa", done=True)
        self._run("2026-01-01T00-00-00_bbbb", config=None)
        self._run("2026-01-01T00-00-00_cccc", config="{not json")
        taken, left = answering_run.bound_runs(self.area, CONFIG["protocol"]["id"])
        self.assertEqual([f["dir"].name[-4:] for f in taken], ["aaaa"])
        self.assertEqual(
            [(f["dir"].name[-4:], f["state"]) for f in left], [("cccc", "unreadable")]
        )


class RunIdShape(unittest.TestCase):
    def test_run_started_reads_the_time_and_refuses_other_names(self):
        started = runs.run_started("2026-10-13T14-00-57_071a")
        self.assertEqual(
            (started.year, started.hour, started.second) if started else None,
            (2026, 14, 57),
        )
        for name in (
            "output",
            "2026-10-13T14-00-57",
            "start-2026-10-13T14-00-57.log",
            "2026-02-30T12-00-00_abcd",  # the shape, not a date: the stop hook crashed on it
        ):
            with self.subTest(name):
                self.assertIsNone(runs.run_started(name))

    def test_run_id_finds_a_cited_run_in_prose(self):
        text = "0.91 (run 2026-10-07T10-00-00_aa11, derived 2026-10-07T11-00-00_bb22)"
        self.assertEqual(
            [m.group(0) for m in runs.RUN_ID.finditer(text)],
            ["2026-10-07T10-00-00_aa11", "2026-10-07T11-00-00_bb22"],
        )


class WriteAtomic(unittest.TestCase):
    def test_the_file_is_whole_and_no_temp_file_stays(self):
        d = Path(tempfile.mkdtemp())
        target = d / "lease.json"
        runs.write_atomic(target, "one")
        runs.write_atomic(target, "two")
        self.assertEqual(target.read_text(), "two")
        self.assertEqual([p.name for p in d.iterdir()], ["lease.json"])

    def test_a_reader_never_sees_a_partial_file(self):
        d = Path(tempfile.mkdtemp())
        target = d / "state.json"
        body_a, body_b = "a" * 200_000, "b" * 200_000
        runs.write_atomic(target, body_a)
        seen: set[int] = set()
        stop = threading.Event()

        def read() -> None:
            while not stop.is_set():
                seen.add(len(target.read_text()))

        t = threading.Thread(target=read)
        t.start()
        for _ in range(50):
            runs.write_atomic(target, body_b)
            runs.write_atomic(target, body_a)
        stop.set()
        t.join()
        self.assertEqual(seen, {200_000})
        self.assertFalse([p for p in d.iterdir() if f".tmp{os.getpid()}" in p.name])


if __name__ == "__main__":
    unittest.main()


class ScriptOnCommandLine(unittest.TestCase):
    """`is_alive` asks whether a live PID still runs the recorded script; a
    substring held `python not_01_measure.py` for `01_measure.py`."""

    def test_the_script_as_a_word_or_a_path_matches(self):
        for cmd in (
            "python 01_measure.py",
            "/u/.venv/bin/python /u/exp/01-x/scripts/01_measure.py --full",
            "python /Users/a b/scripts/01_measure.py",  # a space in the dir
        ):
            with self.subTest(cmd):
                self.assertTrue(runs.runs_script(cmd, "01_measure.py"))

    def test_another_name_containing_it_does_not(self):
        for cmd in (
            "python not_01_measure.py",
            "python 01_measure.py.bak",
            "python /x/01_measure.pyc",
        ):
            with self.subTest(cmd):
                self.assertFalse(runs.runs_script(cmd, "01_measure.py"))


class OutputPathsTravel(unittest.TestCase):
    """outputs.json recorded absolute paths: a cloud run's `/home/user/...`
    failed `02_analyze.py --check` in every other checkout (2026-10-14). A path
    inside the repo is recorded relative to its root and resolved on read."""

    def _repo(self, base: Path) -> Path:
        run = base / "experiments" / "01-x" / "runs" / "r1"
        run.mkdir(parents=True)
        (base / ".git").mkdir()
        return run

    def test_inside_the_repo_is_relative_outside_is_absolute(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._repo(Path(d))
            out = Path(d) / "experiments" / "01-x" / "output" / "rows.jsonl"
            self.assertEqual(
                runs.recorded_path(out, run),
                "experiments/01-x/output/rows.jsonl",
            )
            with tempfile.TemporaryDirectory() as other:
                elsewhere = Path(other) / "x.jsonl"
                self.assertEqual(
                    runs.recorded_path(elsewhere, run), str(elsewhere.resolve())
                )

    def test_a_relative_data_path_is_recorded_against_the_repo_not_the_cwd(self):
        """A `data=` path was kept as passed, relative to the working
        directory; it is recorded against the repo root and read back."""
        import os

        with tempfile.TemporaryDirectory() as d:
            run = self._repo(Path(d))
            area = Path(d) / "experiments" / "01-x"
            cwd = os.getcwd()
            try:
                os.chdir(area)
                rec = runs.recorded_path(Path("data/raw.jsonl"), run)
            finally:
                os.chdir(cwd)
            self.assertEqual(rec, "experiments/01-x/data/raw.jsonl")
            self.assertEqual(
                runs.resolve_recorded(rec, run),
                Path(d).resolve() / "experiments/01-x/data/raw.jsonl",
            )

    def test_a_clone_elsewhere_reads_its_own_copy(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._repo(Path(d) / "clone")
            (run / "outputs.json").write_text(
                json.dumps(
                    [
                        {
                            "path": "experiments/01-x/output/rows.jsonl",
                            "sha256": "ab",
                            "lines": 2,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (entry,) = runs.read_outputs(run) or []
            self.assertEqual(
                entry.path,
                (Path(d) / "clone").resolve() / "experiments/01-x/output/rows.jsonl",
            )
