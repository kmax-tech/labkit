"""Every consumer that picks or accepts a run asks `runlog.completion_state`.

Review 2026-10-06: the contract says a v2 run is complete only with BOTH
metrics.json and completion.json (docs/protocol-run-binding.md), but
recheck, a derived run's parent check, intent-check's legacy choice and
the usability scorer looked at metrics.json alone — an unfinalized run
could be rechecked as a kept number and accepted as a parent.

The fixture is a twin pair in one area: an older completed run and a NEWER
unfinalized one with the same metrics. Picking by metrics.json chooses the
newer; picking by the contract chooses the older.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import intent_check, recheck, runlog, usability  # noqa: E402

DONE = "2026-10-06T10-00-00_aaaa"
UNFINALIZED = "2026-10-06T11-00-00_bbbb"


def make_run(area: Path, name: str, *, completion: bool, schema: int | None = 2) -> Path:
    d = area / "runs" / name
    d.mkdir(parents=True)
    cfg: dict = {"script": "01_measure.py", "pid": 1}
    if schema is not None:
        cfg["schema_version"] = schema
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    (d / "metrics.json").write_text(json.dumps({"k1_pass": True}), encoding="utf-8")
    if completion:
        (d / "completion.json").write_text(json.dumps({"schema_version": 2}),
                                           encoding="utf-8")
    return d


class Twin(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        self.done = make_run(self.area, DONE, completion=True)
        self.unfinalized = make_run(self.area, UNFINALIZED, completion=False)

    def test_states(self):
        self.assertEqual(runlog.completion_state(self.done), "completed")
        self.assertEqual(runlog.completion_state(self.unfinalized), "unfinalized")
        self.assertEqual(runlog.completed_runs(self.area), [self.done])

    def test_recheck_picks_the_completed_run(self):
        self.assertEqual(recheck.run_dir(self.area), self.done)

    def test_recheck_refuses_a_named_unfinalized_run(self):
        with self.assertRaises(SystemExit) as cm:
            recheck.run_dir(self.area, UNFINALIZED)
        self.assertIn("unfinalized", str(cm.exception))
        self.assertEqual(recheck.run_dir(self.area, DONE), self.done)

    def test_derived_run_refuses_an_unfinalized_parent(self):
        os.environ.pop("LABKIT_UNFROZEN", None)
        os.environ.pop("CLAUDECODE", None)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                runlog.Run("t", {}, self.area, derived_from=UNFINALIZED)
            self.assertIn("unfinalized", str(cm.exception))
            run = runlog.Run("t", {}, self.area, derived_from=DONE)
        self.assertEqual(json.loads((run.dir / "config.json").read_text())["derived_from"],
                         DONE)

    def test_intent_check_legacy_choice_picks_the_completed_run(self):
        path, skipped = intent_check.gate_metrics(self.area)
        self.assertEqual(path, self.done / "metrics.json")
        self.assertEqual(skipped, 0)

    def test_usability_scorer_picks_the_completed_run(self):
        self.assertEqual(usability.latest_run(self.area), self.done)


class Edges(unittest.TestCase):
    def test_legacy_run_without_schema_completes_on_metrics(self):
        area = Path(tempfile.mkdtemp())
        legacy = make_run(area, DONE, completion=False, schema=None)
        self.assertEqual(runlog.completed_runs(area), [legacy])

    def test_run_dir_without_config_is_legacy(self):
        area = Path(tempfile.mkdtemp())
        d = area / "runs" / DONE
        d.mkdir(parents=True)
        (d / "metrics.json").write_text("{}", encoding="utf-8")
        self.assertEqual(runlog.completion_state(d), "completed")

    def test_unreadable_config_is_loud(self):
        area = Path(tempfile.mkdtemp())
        d = make_run(area, DONE, completion=True)
        (d / "config.json").write_text("{broken", encoding="utf-8")
        with self.assertRaises(runlog.RunConfigError) as cm:
            runlog.completed_runs(area)
        self.assertIn("config.json", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
