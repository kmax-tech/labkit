"""LABKIT_UNFROZEN=1 passes a missing freeze, never an undecided BLOCKER (2026-10-17).

Haiku t3 (labkit-paper area 09, 2026-10-16): the preflight audit's BLOCKER
lay in `audits/` when the agent started the full run with the
acknowledgement; no gate read it. Now `runlog` refuses a full run while a
BLOCKER of any record is `open`, acknowledgement or not; a decided one, an
open WARNING (named in the acknowledgement line) and a probe pass.
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

from labkit import findings, runlog, scope_sha  # noqa: E402
from protocol_fixture import DEFAULT_BLOCK, head, scope_file  # noqa: E402

AUDIT = "2026-10-05 · scope sha abc · 0 findings"
UNFROZEN = head(
    cost="hours", frozen=False, preflight_audit=AUDIT, promises=DEFAULT_BLOCK
)
SECONDS = head(cost="seconds") + (
    "\n- **Model / tool:** haiku\n"
    "- **Question / hypothesis:** does the register beat the trivial decider?\n"
    "- **Success / failure criterion:** [C1] accuracy above the trivial decider\n"
    "- **Admissibility condition:** [A1] every case parsed\n"
)
BLOCKER = (
    "BLOCKER",
    "BLOCKER · scripts/01_measure.py:9 · G_VRH determines K · · LAB-038 What the prompt demands · drop it",
)
WARNING = (
    "WARNING",
    "WARNING · scripts/01_measure.py:3 · x · y · LAB-019 The stamp covers everything · z",
)


def decide(path: Path, status: str, reason: str = "seen and kept") -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace('status = "open"', f'status = "{status}"', 1).replace(
            'reason = ""', f'reason = "{reason}"', 1
        ),
        encoding="utf-8",
    )


class UnfrozenBlocker(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ.pop("LABKIT_UNFROZEN", None)
        os.environ.pop("CLAUDECODE", None)
        os.environ.pop(runlog.FOREGROUND_TIMEOUT_ENV, None)

    def tearDown(self):
        os.environ.pop("LABKIT_UNFROZEN", None)

    def _area(self, text: str) -> Path:
        (self.tmp / "PROTOCOL-x.md").write_text(text, encoding="utf-8")
        scope_file(self.tmp)
        return self.tmp

    def _start(self, text: str, long: bool):
        area = self._area(text)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = runlog.Run("t", {}, area, long=long)
        return r, buf.getvalue()

    def _refused(self, text: str, long: bool = True) -> str:
        area = self._area(text)
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                runlog.Run("t", {}, area, long=long)
        self.assertFalse((area / "runs").exists())
        return str(cm.exception)

    def test_an_open_blocker_is_not_passed_by_the_acknowledgement(self):
        os.environ["LABKIT_UNFROZEN"] = "1"
        p = findings.write(self.tmp, "preflight", "opus", "abc", (1, 0, 0), [BLOCKER])
        msg = self._refused(UNFROZEN)
        self.assertIn(p.name, msg)
        self.assertIn("G_VRH determines K", msg)
        self.assertIn("LABKIT_UNFROZEN=1 does not pass", msg)
        self.assertIn("A probe (long=False) runs", msg)

    def test_no_audits_at_all_keeps_the_acknowledged_pilot(self):
        """The twin of the refusal: nobody could start an audit (v2: the
        auditor backend was not logged in) — the pilot starts, recorded."""
        os.environ["LABKIT_UNFROZEN"] = "1"
        r, out = self._start(UNFROZEN, long=True)
        cfg = json.loads((r.dir / "config.json").read_text())
        self.assertTrue(cfg["unfrozen_ack"])
        self.assertIn("not `frozen = true`", out)
        self.assertNotIn("audit WARNING", out)

    def test_a_decided_blocker_lets_the_acknowledged_pilot_start(self):
        os.environ["LABKIT_UNFROZEN"] = "1"
        p = findings.write(self.tmp, "preflight", "opus", "abc", (1, 0, 0), [BLOCKER])
        decide(p, "accepted")
        r, _ = self._start(UNFROZEN, long=True)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_a_probe_runs_over_an_open_blocker(self):
        """Investigating a BLOCKER takes a probe; refusing it would leave
        deleting the record as the only way out."""
        findings.write(self.tmp, "preflight", "opus", "abc", (1, 0, 0), [BLOCKER])
        r, _ = self._start(UNFROZEN, long=False)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_an_open_warning_passes_and_is_named_in_the_acknowledgement(self):
        os.environ["LABKIT_UNFROZEN"] = "1"
        p = findings.write(self.tmp, "preflight", "opus", "abc", (0, 1, 0), [WARNING])
        r, out = self._start(UNFROZEN, long=True)
        self.assertTrue(json.loads((r.dir / "config.json").read_text())["unfrozen_ack"])
        self.assertIn(f"audit WARNING still `open` in {p.name}", out)

    def test_the_stop_holds_a_frozen_protocol_too(self):
        """Not an unfrozen-path rule: an analysis BLOCKER left open stops the
        full run of a frozen, audited protocol as well."""
        (self.tmp / "scripts").mkdir()
        (self.tmp / "scripts" / "m.py").write_text("x = 1\n")
        scope_file(self.tmp)
        sha = scope_sha.area_stamp(self.tmp)[0]
        findings.write(
            self.tmp, "preflight", "opus", sha, (0, 0, 0), [], now=1_700_000_000
        )
        p = findings.write(
            self.tmp, "analysis", "opus", sha, (1, 0, 0), [BLOCKER], now=1_700_000_060
        )
        frozen = head(
            cost="hours",
            frozen=True,
            preflight_audit=f"2026-10-07 · scope sha {sha} · 0 findings",
        )
        msg = self._refused(frozen)
        self.assertIn(p.name, msg)
        decide(p, "fixed", "")
        r, _ = self._start(frozen, long=True)
        self.assertFalse(
            json.loads((r.dir / "config.json").read_text())["unfrozen_ack"]
        )

    def test_at_seconds_the_gate_is_the_registration_not_the_audits(self):
        """LAB-017: no audit is owed at seconds, so none stands in the way."""
        findings.write(self.tmp, "preflight", "opus", "abc", (1, 0, 0), [BLOCKER])
        r, _ = self._start(SECONDS, long=True)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_an_unreadable_record_is_a_stop_not_no_findings(self):
        os.environ["LABKIT_UNFROZEN"] = "1"
        p = findings.write(self.tmp, "preflight", "opus", "abc", (0, 0, 0), [])
        p.write_text("[audit]\nmode = 'preflight'\n", encoding="utf-8")
        msg = self._refused(UNFROZEN)
        self.assertIn(p.name, msg)
        self.assertIn("not 'no findings'", msg)


if __name__ == "__main__":
    unittest.main()
