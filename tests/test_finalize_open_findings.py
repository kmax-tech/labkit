"""finalize names open audit findings; report-check refuses the acknowledged pilot (2026-10-17).

Station 1b: an open BLOCKER in any `audits/` record, an audit without a
result or one still running is a blocker, an open WARNING a warning, and
the answering run's `unfrozen_ack` a warning in finalize and a blocker in
report-check. Haiku on bulk modulus (labkit-paper 09, Haiku round, t3-labkit-r1, 2026-10-16) wrote its number
over a BLOCKER no gate after runlog read; Sonnet in the round without auditor (v2) wrote numbers back
from runs the acknowledgement had made pilots.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from findings_fixture import decide  # noqa: E402
from labkit import findings, report_check  # noqa: E402
from labkit.finalize import unfrozen_run_warning  # noqa: E402
from protocol_fixture import PID  # noqa: E402
from test_finalize import CLEAN_METRICS, CLEAN_PROTOCOL, _run, _run_finalize  # noqa: E402

BLOCKER = (
    "BLOCKER",
    "BLOCKER · scripts/01_measure.py:9 · G_VRH determines K · · LAB-038 What the prompt demands · drop it",
)
WARNING = (
    "WARNING",
    "WARNING · scripts/01_measure.py:3 · x · y · LAB-019 The stamp covers everything · z",
)


def acknowledge(run: Path) -> None:
    cfg_file = run / "config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    cfg["unfrozen_ack"] = True
    cfg_file.write_text(json.dumps(cfg), encoding="utf-8")


class OpenFindings(unittest.TestCase):
    def _area(self, d: str) -> Path:
        area = Path(d)
        (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
        _run(area, "2026-10-07T10-00-00_meas", metrics=CLEAN_METRICS)
        return area

    def test_an_open_blocker_blocks_and_names_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d)
            p = findings.write(area, "preflight", "opus", "abc", (1, 0, 0), [BLOCKER])
            code, out = _run_finalize(area)
            self.assertEqual(code, 1, out)
            self.assertIn(f"audit BLOCKER still `open` in {p.name}", out)
            # the twin: decided, all clear
            decide(p, "accepted")
            code, out = _run_finalize(area)
            self.assertEqual(code, 0, out)
            self.assertIn("1 audit(s) recorded, nothing open", out)

    def test_an_audit_without_a_result_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d)
            findings.write_unavailable(
                area, "preflight", "opus", "abc", "claude-cli: not logged in"
            )
            code, out = _run_finalize(area)
            self.assertEqual(code, 1, out)
            self.assertIn("audit unavailable since", out)

    def test_an_open_warning_is_a_warning(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d)
            p = findings.write(area, "preflight", "opus", "abc", (0, 1, 0), [WARNING])
            code, out = _run_finalize(area)
            self.assertEqual(code, 0, out)
            self.assertIn(f"audit WARNING still `open` in {p.name}", out)
            self.assertNotIn("all clear", out)

    def test_no_audits_is_none_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run_finalize(self._area(d))
            self.assertEqual(code, 0, out)
            self.assertIn("none recorded", out)


class AcknowledgedPilot(unittest.TestCase):
    def test_finalize_warns_and_report_check_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            run = _run(area, "2026-10-07T10-00-00_meas", metrics=CLEAN_METRICS)
            self.assertIsNone(unfrozen_run_warning(run))  # the twin first
            self.assertIsNone(report_check.unfrozen_run_gap(area, PID))
            acknowledge(run)
            warning = unfrozen_run_warning(run)
            assert warning is not None
            self.assertIn("started on LABKIT_UNFROZEN=1", warning)
            code, out = _run_finalize(area)
            self.assertEqual(code, 0, out)
            self.assertIn("acknowledged unfrozen", out)
            gap = report_check.unfrozen_run_gap(area, PID)
            assert gap is not None
            self.assertIn("2026-10-07T10-00-00_meas", gap)
            self.assertIn("owes a frozen run", gap)

    def test_no_bound_run_or_no_id_is_no_gap_here(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            self.assertIsNone(report_check.unfrozen_run_gap(area, PID))
            self.assertIsNone(report_check.unfrozen_run_gap(area, None))


if __name__ == "__main__":
    unittest.main()
