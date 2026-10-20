"""runs — the one walk over an area's `runs/`, and the atomic write.

`run_dirs` reads every directory's metadata once and hands the three cases
back as data (no run, a run, an unreadable run); the callers decide. The
walk used to stand six times with six decisions (audit 2026-10-13).
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from labkit.formats import runs, answering_run

CONFIG = {
    "schema_version": 3,
    "run_kind": "measurement",
    "run_id": "r",
    "protocol": {"id": "p-" + "0" * 16},
}


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
        self.assertEqual([f.dir.name[-4:] for f in taken], ["aaaa"])
        self.assertEqual(
            [(f.dir.name[-4:], f.state) for f in left], [("cccc", "unreadable")]
        )


class TypedRecords(unittest.TestCase):
    """The run record is checked once, where the file is read, and handed on
    as types: a run's facts and its binding are dataclasses, its state one
    of a closed set — no reader guesses a dict's keys again (2026-10-20)."""

    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        (self.area / "runs").mkdir()

    def _run(self, name: str, config: dict | str | None) -> Path:
        d = self.area / "runs" / name
        d.mkdir()
        if isinstance(config, dict):
            (d / "config.json").write_text(json.dumps(config))
        elif isinstance(config, str):
            (d / "config.json").write_text(config)
        return d

    def test_no_run_an_unreadable_run_and_a_run_are_three_results(self):
        none = self._run("2026-01-01T00-00-00_aaaa", None)
        broken = self._run("2026-01-01T00-00-00_bbbb", "{not json")
        read = self._run("2026-01-01T00-00-00_cccc", CONFIG)
        self.assertIsNone(answering_run.run_facts(none))
        bad = answering_run.run_facts(broken)
        assert bad is not None
        self.assertEqual(bad.state, "unreadable")
        self.assertEqual(bad.binding, runs.ProtocolBinding(None, None))
        self.assertIn("unreadable run metadata", bad.why or "")
        good = answering_run.run_facts(read)
        assert good is not None
        self.assertEqual(good.binding.id, CONFIG["protocol"]["id"])
        self.assertIsNone(good.why)
        self.assertEqual(good.metrics, read / "metrics.json")

    def test_a_left_out_run_carries_its_reason(self):
        self._run(
            "2026-01-01T00-00-00_aaaa", {**CONFIG, "protocol": {"id": "p-" + "1" * 16}}
        )
        self._run("2026-01-01T00-00-00_bbbb", {**CONFIG, "protocol": None})
        _, left = answering_run.bound_runs(self.area, CONFIG["protocol"]["id"])
        # neither is completed: the state is the reason
        self.assertEqual([f.why for f in left], ["crashed", "crashed"])

    def test_a_record_is_read_or_unreadable_never_both(self):
        d = self.area / "runs" / "x"
        with self.assertRaises(ValueError):
            runs.RunDir(d, dict(CONFIG), "unreadable run metadata")
        runs.RunDir(d, dict(CONFIG), None)  # the twins: each alone is a record
        runs.RunDir(d, None, "unreadable run metadata")
        runs.RunDir(d, None, None)

    def test_the_binding_is_held_to_its_shape(self):
        self.assertEqual(runs.binding_of({}), runs.ProtocolBinding(None, None))
        self.assertEqual(
            runs.binding_of({"protocol": {"id": "p-x", "path": "PROTOCOL-a.md"}}),
            runs.ProtocolBinding("p-x", "PROTOCOL-a.md"),
        )
        for bad, field in (({"id": 7}, "protocol.id"), ("p-x", "protocol =")):
            with self.subTest(bad=bad):
                with self.assertRaises(runs.RunConfigError) as cm:
                    runs.binding_of({"protocol": bad})
                self.assertIn(field, str(cm.exception))
        # the reader refuses the same shape, with the same sentence
        d = self._run("2026-01-01T00-00-00_dddd", {**CONFIG, "protocol": {"id": 7}})
        with self.assertRaises(runs.RunConfigError) as cm:
            runs.read_run_config(d)
        self.assertIn("protocol.id = 7, not a string", str(cm.exception))


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


class NowStamp(unittest.TestCase):
    def test_the_record_time_is_local_seconds_and_reads_back(self):
        from datetime import datetime

        stamp = runs.now_stamp()
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
        read = datetime.fromisoformat(stamp)
        self.assertLess(abs((datetime.now() - read).total_seconds()), 5)
