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

from labkit import runs

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
        self.assertEqual(len(runs.completed_runs(self.area)), 1)
        self._run("2026-01-01T00-00-00_bbbb", config="{not json")
        with self.assertRaises(runs.RunConfigError):
            runs.completed_runs(self.area)

    def test_bound_runs_sees_the_same_three_cases(self):
        self._run("2026-01-01T00-00-00_aaaa", done=True)
        self._run("2026-01-01T00-00-00_bbbb", config=None)
        self._run("2026-01-01T00-00-00_cccc", config="{not json")
        taken, left = runs.bound_runs(self.area, CONFIG["protocol"]["id"])
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
        for name in ("output", "2026-10-13T14-00-57", "start-2026-10-13T14-00-57.log"):
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
