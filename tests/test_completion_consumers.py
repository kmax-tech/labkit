"""Every consumer that picks or accepts a run asks `runs.completion_state`.

Review 2026-10-06: the contract says a v2 run is complete only with BOTH
metrics.json and completion.json (docs/protocol-run-binding.md), but
recheck, a derived run's parent check, intent-check's legacy choice and
the usability scorer looked at metrics.json alone — an unfinalized run
could be rechecked as a kept number and accepted as a parent. (The
legacy choice is gone since labkit 0.48: intent-check binds by protocol id,
and an unstamped protocol names its run with `--metrics`.)

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

from protocol_fixture import PID, head  # noqa: E402

from labkit import recheck, runlog, usability  # noqa: E402
from labkit.formats import runs  # noqa: E402

DONE = "2026-10-06T10-00-00_aaaa"
UNFINALIZED = "2026-10-06T11-00-00_bbbb"


def protocol(area: Path) -> Path:
    """The area's one protocol, stamped with PID — what recheck binds to."""
    p = area / "PROTOCOL-x.md"
    p.write_text(head(), encoding="utf-8")
    return p


def make_run(
    area: Path, name: str, *, completion: bool, schema: int | None = 2
) -> Path:
    d = area / "runs" / name
    d.mkdir(parents=True)
    cfg: dict = {
        "script": "01_measure.py",
        "pid": 1,
        "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
    }
    if schema is not None:
        cfg["schema_version"] = schema
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    (d / "metrics.json").write_text(json.dumps({"c1_pass": True}), encoding="utf-8")
    if completion:
        (d / "completion.json").write_text(
            json.dumps({"schema_version": 2}), encoding="utf-8"
        )
    return d


class Twin(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        self.protocol = protocol(self.area)
        self.done = make_run(self.area, DONE, completion=True)
        self.unfinalized = make_run(self.area, UNFINALIZED, completion=False)

    def test_states(self):
        self.assertEqual(runs.completion_state(self.done), "completed")
        self.assertEqual(runs.completion_state(self.unfinalized), "unfinalized")
        self.assertEqual(runs.completed_runs(self.area, with_repeats=True), [self.done])

    def test_recheck_picks_the_completed_run(self):
        self.assertEqual(recheck.run_dir(self.area, self.protocol), self.done)

    def test_recheck_refuses_a_named_unfinalized_run(self):
        with self.assertRaises(SystemExit) as cm:
            recheck.run_dir(self.area, self.protocol, UNFINALIZED)
        self.assertIn("unfinalized", str(cm.exception))
        self.assertEqual(recheck.run_dir(self.area, self.protocol, DONE), self.done)

    def test_derived_run_refuses_an_unfinalized_parent(self):
        os.environ.pop("LABKIT_UNFROZEN", None)
        os.environ.pop("CLAUDECODE", None)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                runlog.Run("t", {}, self.area, derived_from=UNFINALIZED)
            self.assertIn("unfinalized", str(cm.exception))
            run = runlog.Run("t", {}, self.area, derived_from=DONE)
        self.assertEqual(
            json.loads((run.dir / "config.json").read_text())["derived_from"], DONE
        )

    def test_usability_scorer_picks_the_completed_run(self):
        self.assertEqual(usability.latest_run(self.area), self.done)


class Edges(unittest.TestCase):
    def test_run_without_schema_is_unreadable_never_completed(self):
        """labkit 0.48: metrics.json alone no longer marks a finish; since
        0.89.0 a run without `schema_version >= 2` is unreadable metadata
        (read it with labkit 0.47), refused wherever a run is chosen."""
        area = Path(tempfile.mkdtemp())
        old = make_run(area, DONE, completion=True, schema=None)
        with self.assertRaisesRegex(runs.RunConfigError, "labkit 0.47"):
            runs.completion_state(old)
        with self.assertRaises(runs.RunConfigError):
            runs.completed_runs(area, with_repeats=True)
        with self.assertRaises(SystemExit) as cm:
            recheck.run_dir(area, protocol(area), DONE)
        self.assertIn("labkit 0.47", str(cm.exception))

    def test_run_dir_without_config_is_not_a_run(self):
        area = Path(tempfile.mkdtemp())
        d = area / "runs" / DONE
        d.mkdir(parents=True)
        (d / "metrics.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(runs.RunConfigError, "no config.json"):
            runs.completion_state(d)

    def test_unreadable_config_is_loud(self):
        area = Path(tempfile.mkdtemp())
        d = make_run(area, DONE, completion=True)
        (d / "config.json").write_text("{broken", encoding="utf-8")
        with self.assertRaises(runs.RunConfigError) as cm:
            runs.completed_runs(area, with_repeats=True)
        self.assertIn("config.json", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
