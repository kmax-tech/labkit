"""Tests for the run's completion markers, its states, and the index lock.

Why this exists: a run directory used to say "finished" with metrics.json
alone, so a break between writing the numbers and writing the index row
looked exactly like a clean finish — and the index, which alone held `note`
and the end-of-run git state, could not be rebuilt from the directory. Since
2026-09-26 a v2 run is complete only with BOTH metrics.json and
completion.json, and every change to runs.tsv takes one lock.

The states under test: completed · running · unknown · crashed ·
unfinalized · corrupt · legacy. crashed/unfinalized/corrupt are failures;
`--wait` exits 2 on each. `unknown` is not a failure — it means liveness is
undecidable, and treating it as failed would hide a running run. `legacy`
(no `schema_version` >= 2) is never completed since labkit 0.48; such a run
is read with labkit 0.47.
"""

import contextlib
import io
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.run import runlog, runlog_command  # noqa: E402
from labkit.formats import runs, answering_run  # noqa: E402


def _dead_pid() -> int:
    """A pid that belonged to a process which has ended — pid 1 lives in
    many containers, so a fixture that means "dead" cannot use it
    (review 2026-10-08)."""
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


DEAD_PID = _dead_pid()


def _area(d) -> Path:
    area = Path(d)
    (area / "runs").mkdir(parents=True, exist_ok=True)
    return area


def _run_dir(
    area: Path,
    name: str,
    *,
    schema: int | None = 3,
    metrics=True,
    completion=True,
    pid=DEAD_PID,
    protocol_id=None,
) -> Path:
    d = area / "runs" / name
    d.mkdir(parents=True)
    cfg = {
        "experiment": "x",
        "script": "01_measure.py",
        "pid": pid,
        "data": {},
        "config": {},
    }
    if schema is not None:
        cfg["schema_version"] = schema
        cfg["run_kind"] = "measurement"
    if protocol_id is not None:
        cfg["protocol"] = {"id": protocol_id, "path": "PROTOCOL-x.md"}
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    if metrics:
        (d / "metrics.json").write_text('{"c1_pass": true}', encoding="utf-8")
    if completion:
        (d / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "run_kind": "measurement",
                    "finished": "2026-09-26T21:00:00",
                    "git": "abc1234",
                    "git_full": "abc1234def",
                    "note": "a note",
                }
            ),
            encoding="utf-8",
        )
    return d


def _state(d: Path, alive: bool | None = False) -> str:
    cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
    return runs.run_state(d, cfg, alive)


class TestStates(unittest.TestCase):
    def test_both_markers_is_completed(self):
        with tempfile.TemporaryDirectory() as t:
            d = _run_dir(_area(t), "r1")
            self.assertEqual(_state(d), "completed")

    def test_metrics_without_completion_is_unfinalized(self):
        with tempfile.TemporaryDirectory() as t:
            d = _run_dir(_area(t), "r1", completion=False)
            self.assertEqual(_state(d), "unfinalized")

    def test_completion_without_metrics_is_corrupt(self):
        """A completion record must not paper over results that are gone."""
        with tempfile.TemporaryDirectory() as t:
            d = _run_dir(_area(t), "r1", metrics=False)
            self.assertEqual(_state(d), "corrupt")

    def test_neither_marker_is_crashed_or_running(self):
        with tempfile.TemporaryDirectory() as t:
            d = _run_dir(_area(t), "r1", metrics=False, completion=False)
            self.assertEqual(_state(d, alive=False), "crashed")
            self.assertEqual(_state(d, alive=True), "running")

    def test_undecidable_liveness_is_unknown_not_crashed(self):
        """alive=None means ps could not decide. Claiming crashed hides a
        running run; unknown is the honest state."""
        with tempfile.TemporaryDirectory() as t:
            d = _run_dir(_area(t), "r1", metrics=False, completion=False)
            self.assertEqual(_state(d, alive=None), "unknown")

    def test_undecidable_liveness_v2_with_metrics_is_unknown(self):
        """Same for a v2 run that has metrics but no completion."""
        with tempfile.TemporaryDirectory() as t:
            d = _run_dir(_area(t), "r1", completion=False)
            self.assertEqual(_state(d, alive=None), "unknown")

    def test_unknown_is_not_a_failed_state(self):
        self.assertNotIn("unknown", runs.FAILED_STATES)

    def test_a_live_process_is_running_even_half_finalized(self):
        with tempfile.TemporaryDirectory() as t:
            d = _run_dir(_area(t), "r1", completion=False)
            self.assertEqual(_state(d, alive=True), "running")

    def test_a_run_without_schema_version_is_unreadable_never_completed(self):
        """labkit 0.48 dropped the metrics-only marker; 0.89.0 dropped the
        `legacy` state: a run without `schema_version` >= 2 is unreadable
        metadata whatever its files say — read it with labkit 0.47."""
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            cases = {
                "r1": {},
                "r2": {"completion": False},
                "r3": {"metrics": False, "completion": False},
            }
            for name, kwargs in cases.items():
                d = _run_dir(area, name, schema=None, **kwargs)
                with self.subTest(run=name):
                    with self.assertRaisesRegex(runs.RunConfigError, "labkit 0.47"):
                        runs.read_run_config(d)
            d = _run_dir(area, "r4", schema=1)
            with self.assertRaisesRegex(runs.RunConfigError, "below 2"):
                runs.read_run_config(d)
            self.assertEqual(
                getattr(answering_run.run_facts(d), "state", None), "unreadable"
            )


class TestActive(unittest.TestCase):
    def test_completed_runs_are_not_listed_and_states_are_carried(self):
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            _run_dir(area, "2026-01-01T00-00-00_aaaa")
            _run_dir(area, "2026-01-01T00-00-01_bbbb", completion=False)
            _run_dir(area, "2026-01-01T00-00-02_cccc", metrics=False)
            live = runlog.active(area)
        self.assertEqual([r["run_id"][-4:] for r in live], ["bbbb", "cccc"])
        self.assertEqual([r["state"] for r in live], ["unfinalized", "corrupt"])

    def test_wait_exits_2_on_every_failed_state(self):
        for kwargs, expected in (
            ({"completion": False}, "UNFINALIZED"),
            ({"metrics": False}, "CORRUPT"),
            ({"metrics": False, "completion": False}, "CRASHED"),
        ):
            with self.subTest(**kwargs), tempfile.TemporaryDirectory() as t:
                area = _area(t)
                _run_dir(area, "r1", **kwargs)
                r = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import sys; sys.path.insert(0, %r);"
                        "from labkit.run import runlog_command;"
                        "sys.exit(runlog_command.main([%r, '--wait', '--max-seconds', '0']))"
                        % (str(Path(runlog.__file__).parents[2]), str(area)),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn(expected, r.stdout)

    def test_finished_line_ignores_an_unfinalized_run(self):
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            _run_dir(area, "2026-01-01T00-00-00_aaaa")
            _run_dir(area, "2026-01-01T00-00-09_zzzz", completion=False)
            self.assertIn("aaaa", runlog_command._finished_line(area))


class TestReindex(unittest.TestCase):
    def test_a_completed_v2_run_is_rebuilt_in_full(self):
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            _run_dir(area, "r1", protocol_id="p-0123456789abcdef")
            self.assertEqual(runlog.reindex(area), 0)
            _, rows = runlog._read_index(area / "runs.tsv")
        self.assertEqual(len(rows), 1)
        row = dict(zip(runlog.RUN_INDEX_COLS, rows[0]))
        self.assertEqual(row["run_id"], "r1")
        self.assertEqual(row["git"], "abc1234")  # END state
        self.assertEqual(row["note"], "a note")
        self.assertEqual(row["protocol_id"], "p-0123456789abcdef")

    def test_an_existing_row_is_never_rewritten(self):
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            _run_dir(area, "r1")
            (area / "runs.tsv").write_text(
                "\t".join(runlog.RUN_INDEX_COLS)
                + "\n"
                + "r1\tOLD\ts.py\t{}\t{}\t{}\thand-written\t\n",
                encoding="utf-8",
            )
            runlog.reindex(area)
            _, rows = runlog._read_index(area / "runs.tsv")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][6], "hand-written")

    def test_incomplete_runs_are_reported_not_indexed(self):
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            _run_dir(area, "r1", completion=False)
            _run_dir(area, "r2", metrics=False)
            runlog.reindex(area)
            _, rows = runlog._read_index(area / "runs.tsv")
        self.assertEqual(rows, [])

    def test_pre_schema_runs_are_reported_not_invented(self):
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            _run_dir(area, "r1", schema=None, completion=False)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = runlog.reindex(area)
            _, rows = runlog._read_index(area / "runs.tsv")
        self.assertEqual(rows, [])
        self.assertEqual(code, 2)
        self.assertIn("NOT INDEXED", out.getvalue())

    def test_a_duplicate_run_id_in_the_index_is_an_error(self):
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            (area / "runs.tsv").write_text(
                "\t".join(runlog.RUN_INDEX_COLS)
                + "\n"
                + "r1\ta\ts\t{}\t{}\t{}\tn\t\n" * 2,
                encoding="utf-8",
            )
            self.assertEqual(runlog.reindex(area), 2)

    def test_an_unmigrated_index_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            (area / "runs.tsv").write_text(
                "run_id\tgit\tscript\tdata\tconfig\tmetrics\tnote\n", encoding="utf-8"
            )
            self.assertEqual(runlog.reindex(area), 2)


def _append_many(area_str, n):
    """Child process: n index rows, each taking the lock."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from labkit.run import runlog as rl

    area = Path(area_str)
    for i in range(n):
        with rl._index_lock(area):
            rl._append_row(
                area / "runs.tsv",
                [f"{os.getpid()}-{i}", "g", "s", "{}", "{}", "{}", "n", ""],
            )


class TestIndexLock(unittest.TestCase):
    """Every change to runs.tsv takes one lock: concurrent appends, each
    reading the header and appending, lose no row."""

    def test_concurrent_appends_lose_no_row(self):
        with tempfile.TemporaryDirectory() as t:
            area = _area(t)
            ctx = multiprocessing.get_context("spawn")
            procs = [
                ctx.Process(target=_append_many, args=(str(area), 20)) for _ in range(4)
            ]
            for p in procs:
                p.start()
            for p in procs:
                p.join(60)
            _, rows = runlog._read_index(area / "runs.tsv")
        self.assertEqual(len(rows), 80)
        self.assertEqual(len({r[0] for r in rows}), 80)


if __name__ == "__main__":
    unittest.main()


class TestDerivedRun(unittest.TestCase):
    """A derived run re-evaluates a parent's rows and says so (2026-10-05)."""

    def test_a_derived_run_records_its_parent(self):
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            _run_dir(area, "2026-10-05T10-00-00_aaaa")
            with runlog.run(
                "x", {}, base_dir=area, derived_from="2026-10-05T10-00-00_aaaa"
            ) as r:
                r.metrics(c1_pass=True)
            cfg = json.loads((r.dir / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["derived_from"], "2026-10-05T10-00-00_aaaa")

    def test_a_parent_without_metrics_is_refused_before_mkdir(self):
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            _run_dir(area, "2026-10-05T10-00-00_bbbb", metrics=False)
            with self.assertRaises(SystemExit):
                runlog.run(
                    "x", {}, base_dir=area, derived_from="2026-10-05T10-00-00_bbbb"
                )
            self.assertEqual(len(list((area / "runs").iterdir())), 1)

    def test_a_derived_run_records_no_model_resolution(self):
        """The rows are the parent's; resolving the alias under today's
        models.toml would be provenance the rows never had — the record
        stays empty and `answering_run.model_provenance_run` walks to the parent."""
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            parent = _run_dir(area, "2026-10-05T10-00-00_aaaa")
            cfg = json.loads((parent / "config.json").read_text(encoding="utf-8"))
            cfg["models_resolved"] = {"m": {"alias": "m", "model": "A"}}
            (parent / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            with mock.patch(
                "labkit.run.llm.resolve", return_value={"model": "B"}
            ) as res:
                with runlog.run(
                    "x", {"model": "m"}, base_dir=area, derived_from=parent.name
                ) as r:
                    r.metrics(c1_pass=True)
            res.assert_not_called()
            child = json.loads((r.dir / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(child["models_resolved"], {})
            self.assertEqual(answering_run.model_provenance_run(r.dir), parent)

    def test_an_ordinary_run_records_no_parent(self):
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            with runlog.run("x", {}, base_dir=area) as r:
                r.metrics(c1_pass=True)
            cfg = json.loads((r.dir / "config.json").read_text(encoding="utf-8"))
            self.assertIsNone(cfg["derived_from"])
