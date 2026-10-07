"""Tests for intent-check's metrics choice: newest WITH intent keys.

Why this is tested: 2026-09-09, area 71 — the check defaulted to the newest
runs/*/metrics.json, which was the producer's, and reported every promise as
unimplemented. The fix must pick the newest metrics file that reports any
intent key, fall back to the newest overall when none does (the honest
"nothing implemented yet"), and say when it skipped newer runs. Since the
binding, the choice runs among the completed runs bound to the protocol's
id (`test_intent_check_binding.py`).
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test

from labkit import intent_check  # noqa: E402
from protocol_fixture import PID, head  # noqa: E402

CRITERION = "- **Success / failure criterion:** [C1] holds\n"


def _run(area: Path, rid: str, metrics: dict) -> Path:
    """A completed run bound to PID; returns its metrics.json."""
    rd = area / "runs" / rid
    rd.mkdir(parents=True)
    (rd / "config.json").write_text(json.dumps(
        {"script": "01_measure.py", "pid": 1, "schema_version": 2,
         "protocol": {"id": PID, "path": "PROTOCOL-x.md"}}), encoding="utf-8")
    (rd / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    (rd / "completion.json").write_text(json.dumps(
        {"schema_version": 2, "finished": "x", "git": "g", "git_full": "g",
         "note": ""}), encoding="utf-8")
    return rd / "metrics.json"


def _area(d, runs):
    """runs: {run_id: metrics dict} — run ids sort temporally."""
    area = Path(d)
    for rid, metrics in runs.items():
        _run(area, rid, metrics)
    proto = area / "PROTOCOL-x.md"
    proto.write_text(head() + CRITERION, encoding="utf-8")
    return proto


def _run_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = intent_check.main(argv)
    return code, buf.getvalue()


class TestMetricsChoice(unittest.TestCase):

    def test_newer_producer_metrics_do_not_shadow_the_gate_run(self):
        with tempfile.TemporaryDirectory() as d:
            proto = _area(d, {
                "2026-09-09T10-00-00_gate": {"c1": True},
                "2026-09-09T11-00-00_producer": {"calls": 1080},
            })
            code, out = _run_main([str(proto)])
            self.assertEqual(code, 0, out)
            self.assertIn("all report", out)
            self.assertIn("skipped 1 newer bound run(s)", out)

    def test_no_run_with_keys_falls_back_to_newest_and_reports_missing(self):
        with tempfile.TemporaryDirectory() as d:
            proto = _area(d, {
                "2026-09-09T10-00-00_a": {"calls": 5},
                "2026-09-09T11-00-00_b": {"calls": 9},
            })
            code, out = _run_main([str(proto)])
            self.assertEqual(code, 1)
            self.assertIn("no 'c1'", out)

    def test_explicit_metrics_argument_still_wins(self):
        with tempfile.TemporaryDirectory() as d:
            proto = _area(d, {
                "2026-09-09T10-00-00_gate": {"c1": True},
                "2026-09-09T11-00-00_other": {"calls": 1},
            })
            # the newest-with-keys rule would pick _gate and pass
            other = Path(d) / "runs/2026-09-09T11-00-00_other/metrics.json"
            code, out = _run_main([str(proto), "--metrics", str(other)])
            self.assertEqual(code, 1)
            self.assertIn("no 'c1'", out)


class TestSeriesArea(unittest.TestCase):
    """A series area (§4: PROTOCOL-s1-*, PROTOCOL-s2-*, ...) once made the
    automatic choice a guess that had to refuse (2026-09-26). The binding
    turns it into a filter; naming the run explicitly still works."""

    def test_explicit_metrics_works_in_a_series_area(self):
        with tempfile.TemporaryDirectory() as d:
            proto = _area(d, {"2026-09-09T10-00-00_gate": {"c1": True}})
            (Path(d) / "PROTOCOL-s2-later.md").write_text(
                head(id="p-bbbbbbbbbbbbbbbb") + CRITERION, encoding="utf-8")
            metrics = Path(d) / "runs/2026-09-09T10-00-00_gate/metrics.json"
            code, out = _run_main([str(proto), "--metrics", str(metrics)])
            self.assertEqual(code, 0, out)
            self.assertIn("all report", out)

    def test_a_second_protocol_does_not_block_the_bound_choice(self):
        with tempfile.TemporaryDirectory() as d:
            proto = _area(d, {"2026-09-09T10-00-00_gate": {"c1": True}})
            (Path(d) / "PROTOCOL-s2-later.md").write_text(
                head(id="p-bbbbbbbbbbbbbbbb") + CRITERION, encoding="utf-8")
            code, out = _run_main([str(proto)])
            self.assertEqual(code, 0, out)
            self.assertIn("all report", out)


if __name__ == "__main__":
    unittest.main()
