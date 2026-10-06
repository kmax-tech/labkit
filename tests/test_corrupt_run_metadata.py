"""An unreadable run artefact is shown, never skipped (review 2026-10-06).

Before: an unreadable config.json made a run vanish from `runlog`'s open
runs, from `reindex` and from intent-check's listing, and an unreadable
metrics.json made intent-check fall back to the next older run as if the
newer had reported nothing. A damaged newer run let an older one stand in.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import intent_check, runlog  # noqa: E402

PID = "p-0123456789abcdef"
OLD = "2026-10-06T10-00-00_aaaa"
NEW = "2026-10-06T11-00-00_bbbb"


def make_run(area: Path, name: str) -> Path:
    d = area / "runs" / name
    d.mkdir(parents=True)
    (d / "config.json").write_text(json.dumps(
        {"schema_version": 2, "script": "01_measure.py", "pid": 1,
         "protocol": {"id": PID, "path": "PROTOCOL-x.md"}}), encoding="utf-8")
    (d / "metrics.json").write_text(json.dumps({"k1_pass": True}), encoding="utf-8")
    (d / "completion.json").write_text(json.dumps(
        {"schema_version": 2, "finished": "x", "git": "g", "git_full": "g", "note": ""}),
        encoding="utf-8")
    return d


def quiet(fn, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args)
    return rc, buf.getvalue()


class BrokenConfig(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        make_run(self.area, OLD)
        self.broken = make_run(self.area, NEW)
        (self.broken / "config.json").write_text("{broken", encoding="utf-8")

    def test_open_runs_list_it_as_corrupt_with_the_reason(self):
        live = runlog.active(self.area)
        self.assertEqual([r["run_id"] for r in live], [NEW])
        self.assertEqual(live[0]["state"], "corrupt")
        self.assertIn("config.json", live[0]["error"])

    def test_wait_exits_failed(self):
        rc, out = quiet(runlog._wait, str(self.area), 0, 0.01, False, False)
        self.assertEqual(rc, 2)
        self.assertIn("unreadable run metadata", out)

    def test_reindex_reports_and_fails(self):
        rc, out = quiet(runlog.reindex, self.area)
        self.assertEqual(rc, 2)
        self.assertIn("NOT INDEXED", out)
        self.assertIn(NEW, out)

    def test_intent_check_lists_it_and_never_chooses_it(self):
        taken, left = intent_check.bound_runs(self.area, PID)
        self.assertEqual([f["dir"].name for f in taken], [OLD])
        self.assertEqual(left[0]["state"], "corrupt")
        self.assertIn("unreadable run metadata", left[0]["why"])


class BrokenMetrics(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        make_run(self.area, OLD)
        broken = make_run(self.area, NEW)
        (broken / "metrics.json").write_text("{broken", encoding="utf-8")
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(f"- **Protocol id:** {PID}\n[K1] holds\n",
                                 encoding="utf-8")

    def test_newer_unreadable_metrics_is_not_skipped_for_the_older(self):
        rc, out = quiet(intent_check.main, [str(self.protocol)])
        self.assertEqual(rc, 2)
        self.assertIn("unreadable metrics", out)
        self.assertNotIn(OLD, out)


if __name__ == "__main__":
    unittest.main()
