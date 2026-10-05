"""Tests for runlog's freeze gate (2026-10-05).

A full run (`long=True`) on a protocol that is not `Frozen before run: yes`,
or whose `Preflight audit:` field is still the placeholder, is refused
before any run directory exists. Pilots (`long=False`) pass; a long pilot
acknowledges with LABKIT_UNFROZEN=1 and the acknowledgement lands in
config.json. At `Cost: seconds` the gate is the written success criterion,
not the freeze (§2.A12); the tier lands in config.json as `cost_tier`.
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

from labkit import runlog  # noqa: E402

FROZEN = """\
- **Protocol id:** p-0123456789abcdef
- **Preflight audit:** 2026-10-05 · scope sha abc · 0 findings
- **Frozen before run:** yes
"""
UNFROZEN = FROZEN.replace("** yes", "** no")
PLACEHOLDER = FROZEN.replace(
    "2026-10-05 · scope sha abc · 0 findings", "<date · scope sha · N findings>")
NO_FIELD = "- **Protocol id:** p-0123456789abcdef\n- **Frozen before run:** yes\n"
SECONDS = """\
- **Protocol id:** p-0123456789abcdef
- **Success / failure criterion:** [K1] accuracy above the trivial decider
- **Cost:** seconds — deterministic
- **Preflight audit:** <date · scope sha · N findings>
- **Frozen before run:** no
"""
SECONDS_NO_CRITERION = SECONDS.replace(
    "[K1] accuracy above the trivial decider", "<the criterion>")
HOURS_UNFROZEN = SECONDS.replace("seconds — deterministic", "hours — 2k calls")
MEASUREMENT = """\
- **Protocol id:** p-0123456789abcdef
- **Type:** measurement
- **Question:** how many documents per case?
"""


class FreezeGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ.pop("LABKIT_UNFROZEN", None)
        os.environ.pop("CLAUDECODE", None)

    def _area(self, text: str) -> Path:
        (self.tmp / "PROTOCOL-x.md").write_text(text, encoding="utf-8")
        return self.tmp

    def _start(self, text: str, long: bool):
        area = self._area(text)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = runlog.Run("t", {}, area, long=long)
        return r, buf.getvalue()

    def test_full_run_on_frozen_protocol_starts(self):
        r, _ = self._start(FROZEN, long=True)
        self.assertTrue((r.dir / "config.json").is_file())
        self.assertFalse(json.loads((r.dir / "config.json").read_text())["unfrozen_ack"])

    def test_full_run_on_unfrozen_protocol_is_refused_before_mkdir(self):
        area = self._area(UNFROZEN)
        with self.assertRaises(SystemExit) as cm:
            runlog.Run("t", {}, area, long=True)
        self.assertIn("Frozen before run: yes", str(cm.exception))
        self.assertFalse((area / "runs").exists())

    def test_full_run_with_placeholder_audit_is_refused(self):
        area = self._area(PLACEHOLDER)
        with self.assertRaises(SystemExit) as cm:
            runlog.Run("t", {}, area, long=True)
        self.assertIn("Preflight audit", str(cm.exception))
        self.assertIn("placeholder", str(cm.exception))

    def test_protocol_without_audit_field_is_not_a_gap(self):
        r, _ = self._start(NO_FIELD, long=True)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_pilot_passes_unfrozen(self):
        r, _ = self._start(UNFROZEN, long=False)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_unbound_full_run_is_refused(self):
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                runlog.Run("t", {}, self.tmp, long=True)
        self.assertIn("unbound", str(cm.exception))

    def test_seconds_with_criterion_starts_unfrozen(self):
        r, _ = self._start(SECONDS, long=True)
        cfg = json.loads((r.dir / "config.json").read_text())
        self.assertEqual(cfg["cost_tier"], "seconds")
        self.assertFalse(cfg["unfrozen_ack"])

    def test_seconds_without_criterion_is_refused(self):
        area = self._area(SECONDS_NO_CRITERION)
        with self.assertRaises(SystemExit) as cm:
            runlog.Run("t", {}, area, long=True)
        self.assertIn("success criterion", str(cm.exception))
        self.assertIn("Cost: seconds", str(cm.exception))
        self.assertFalse((area / "runs").exists())

    def test_hours_keeps_the_freeze(self):
        area = self._area(HOURS_UNFROZEN)
        with self.assertRaises(SystemExit) as cm:
            runlog.Run("t", {}, area, long=True)
        self.assertIn("Frozen before run: yes", str(cm.exception))

    def test_measurement_short_form_needs_no_freeze(self):
        r, _ = self._start(MEASUREMENT, long=True)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_tier_is_recorded_for_pilots_too(self):
        r, _ = self._start(FROZEN, long=False)
        self.assertIsNone(json.loads((r.dir / "config.json").read_text())["cost_tier"])

    def test_acknowledged_long_pilot_is_recorded(self):
        os.environ["LABKIT_UNFROZEN"] = "1"
        try:
            r, out = self._start(UNFROZEN, long=True)
        finally:
            os.environ.pop("LABKIT_UNFROZEN", None)
        self.assertIn("LABKIT_UNFROZEN=1", out)
        self.assertTrue(json.loads((r.dir / "config.json").read_text())["unfrozen_ack"])


if __name__ == "__main__":
    unittest.main()
