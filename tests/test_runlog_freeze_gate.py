"""Tests for runlog's freeze gate (2026-10-05).

A full run (`long=True`) on a protocol whose head is not `frozen = true`,
or whose `preflight_audit` is still empty, is refused before any run
directory exists. Pilots (`long=False`) pass; a long pilot acknowledges
with LABKIT_UNFROZEN=1 and the acknowledgement lands in config.json. At
`cost = "seconds"` the gate is the written registration (question,
criterion, admissibility condition), not the freeze (§2.A12); the tier
lands in config.json as `cost_tier`.
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
from protocol_fixture import head  # noqa: E402

AUDIT = "2026-10-05 · scope sha abc · 0 findings"
FROZEN = head(cost="hours", frozen=True, preflight_audit=AUDIT)
UNFROZEN = head(cost="hours", frozen=False, preflight_audit=AUDIT)
PLACEHOLDER = head(cost="hours", frozen=True,
                   preflight_audit="<date · scope sha · N findings>")
NO_FIELD = FROZEN.replace(f'preflight_audit = "{AUDIT}"\n', "")
REGISTRATION = """
- **Question / hypothesis:** does the register beat the trivial decider?
- **Success / failure criterion:** [C1] accuracy above the trivial decider
- **Admissibility condition:** [A1] every case parsed
"""
SECONDS = head(cost="seconds") + REGISTRATION
SECONDS_NO_CRITERION = SECONDS.replace(
    "[C1] accuracy above the trivial decider", "<the criterion>")
HOURS_UNFROZEN = head(cost="hours") + REGISTRATION
PROSE_HEAD = """\
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
        self.assertIn("not `frozen = true`", str(cm.exception))
        self.assertFalse((area / "runs").exists())

    def test_full_run_with_placeholder_audit_is_refused(self):
        area = self._area(PLACEHOLDER)
        with self.assertRaises(SystemExit) as cm:
            runlog.Run("t", {}, area, long=True)
        self.assertIn("`preflight_audit` is empty", str(cm.exception))
        self.assertFalse((area / "runs").exists())

    def test_protocol_without_audit_field_is_refused_before_mkdir(self):
        """`preflight_audit` is a head field: leaving it out is a malformed
        head naming the field, not a protocol that skips the audit."""
        area = self._area(NO_FIELD)
        with self.assertRaises(SystemExit) as cm:
            runlog.Run("t", {}, area, long=True)
        self.assertIn("preflight_audit", str(cm.exception))
        self.assertFalse((area / "runs").exists())

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
        self.assertIn("Success / failure criterion", str(cm.exception))
        self.assertIn('cost = "seconds"', str(cm.exception))
        self.assertFalse((area / "runs").exists())

    def test_hours_keeps_the_freeze(self):
        area = self._area(HOURS_UNFROZEN)
        with self.assertRaises(SystemExit) as cm:
            runlog.Run("t", {}, area, long=True)
        self.assertIn("not `frozen = true`", str(cm.exception))

    def test_prose_head_is_refused_before_mkdir(self):
        """The measurement short form (`Type: measurement`, prose head) is
        gone: such a protocol is a loud refusal, even for a pilot (TODO 8)."""
        area = self._area(PROSE_HEAD)
        with self.assertRaises(SystemExit) as cm:
            runlog.Run("t", {}, area, long=False)
        self.assertIn("no [protocol] table", str(cm.exception))
        self.assertFalse((area / "runs").exists())

    def test_seconds_runs_in_a_claude_foreground_shell(self):
        os.environ["CLAUDECODE"] = "1"
        try:
            r, _ = self._start(SECONDS, long=True)
            self.assertTrue((r.dir / "config.json").is_file())
            with self.assertRaises(SystemExit) as cm:
                self._start(FROZEN, long=True)
            self.assertIn("foreground", str(cm.exception))
        finally:
            os.environ.pop("CLAUDECODE", None)

    def test_tier_is_recorded_for_pilots_too(self):
        r, _ = self._start(FROZEN, long=False)
        self.assertEqual(json.loads((r.dir / "config.json").read_text())["cost_tier"], "hours")

    def test_unfilled_tier_is_recorded_as_none_and_keeps_the_freeze(self):
        text = head(cost="<seconds | minutes | hours>")
        r, _ = self._start(text, long=False)
        self.assertIsNone(json.loads((r.dir / "config.json").read_text())["cost_tier"])
        with self.assertRaises(SystemExit) as cm:
            self._start(text, long=True)
        self.assertIn("not `frozen = true`", str(cm.exception))

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
