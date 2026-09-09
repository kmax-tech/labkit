"""Tests for intent-check's metrics choice: newest WITH intent keys.

Why this is tested: 2026-09-09, area 71 — the check defaulted to the newest
runs/*/metrics.json, which was the producer's, and reported every promise as
unimplemented. The fix must pick the newest metrics file that reports any
intent key, fall back to the newest overall when none does (the honest
"nothing implemented yet"), and say when it skipped newer runs.
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


def _area(d, runs):
    """runs: {run_id: metrics dict} — run ids sort temporally."""
    area = Path(d)
    for rid, metrics in runs.items():
        rd = area / "runs" / rid
        rd.mkdir(parents=True)
        (rd / "metrics.json").write_text(json.dumps(metrics),
                                         encoding="utf-8")
    proto = area / "PROTOCOL-x.md"
    proto.write_text("- criterion [K1] holds\n", encoding="utf-8")
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
                "2026-09-09T10-00-00_gate": {"k1": True},
                "2026-09-09T11-00-00_producer": {"calls": 1080},
            })
            code, out = _run_main([str(proto)])
            self.assertEqual(code, 0, out)
            self.assertIn("all report", out)
            self.assertIn("skipped 1 newer run(s)", out)

    def test_no_run_with_keys_falls_back_to_newest_and_reports_missing(self):
        with tempfile.TemporaryDirectory() as d:
            proto = _area(d, {
                "2026-09-09T10-00-00_a": {"calls": 5},
                "2026-09-09T11-00-00_b": {"calls": 9},
            })
            code, out = _run_main([str(proto)])
            self.assertEqual(code, 1)
            self.assertIn("no 'k1'", out)

    def test_explicit_metrics_argument_still_wins(self):
        with tempfile.TemporaryDirectory() as d:
            proto = _area(d, {"2026-09-09T10-00-00_gate": {"k1": True}})
            other = Path(d) / "other.json"
            other.write_text('{"calls": 1}', encoding="utf-8")
            code, out = _run_main([str(proto), "--metrics", str(other)])
            self.assertEqual(code, 1)
            self.assertIn("no 'k1'", out)


if __name__ == "__main__":
    unittest.main()
