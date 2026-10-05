"""Tests for runlog's freeze gate (2026-10-05).

A full run (`long=True`) on a protocol that is not `Frozen before run: yes`,
or whose `Preflight audit:` field is still the placeholder, is refused
before any run directory exists. Pilots (`long=False`) pass; a long pilot
acknowledges with LABKIT_UNFROZEN=1 and the acknowledgement lands in
config.json.
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
