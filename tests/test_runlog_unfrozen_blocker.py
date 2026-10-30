"""runlog refuses a full run over an undecided audit BLOCKER, acknowledged or not.

labkit-paper area 09, haiku round (2026-10-17): the preflight audit wrote its
BLOCKER to audits/ before the first run; the agent took a killed second call
for a failed audit and ran four full runs with LABKIT_UNFROZEN=1. The
acknowledgement is for an unfrozen protocol a run may be acknowledged on,
not for a finding nobody read. Without a record the acknowledged run stays
possible over a failed
audit attempt (0.99.0); a decided BLOCKER starts; a probe (run_kind='probe') runs so the BLOCKER can be examined;
open WARNINGs ride in the acknowledgement's warning line.
"""

from __future__ import annotations

from labkit.formats.runs import RunKind

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import findings, promises, scope_sha  # noqa: E402
from labkit.run import runlog, start_check  # noqa: E402
from protocol_fixture import registration_of, DEFAULT_BLOCK, head, scope_file  # noqa: E402

UNFROZEN = head(
    repeat_cost="high",
    frozen=False,
    preflight_audit="2026-10-05 · scope sha abc · 0 findings",
    promises=DEFAULT_BLOCK,
)
BLOCKER = (
    "BLOCKER",
    "BLOCKER · scripts/01_measure.py:3 · G_VRH and poisson_ratio determine K in "
    "closed form · LAB-038 What the prompt demands · the target leaks",
)
WARNING = ("WARNING", "WARNING · scripts/01_measure.py:9 · the seed is not recorded")


class UnfrozenBlocker(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "PROTOCOL-x.md").write_text(UNFROZEN, encoding="utf-8")
        scope_file(self.tmp)
        os.environ.pop("LABKIT_UNFROZEN", None)
        os.environ.pop("CLAUDECODE", None)
        os.environ.pop(start_check.FOREGROUND_TIMEOUT_ENV, None)

    def tearDown(self):
        os.environ.pop("LABKIT_UNFROZEN", None)

    def _record(self, rows) -> Path:
        return findings.write(
            self.tmp,
            "preflight",
            "haiku",
            "0123456789ab",
            promises.block_stamp(UNFROZEN),
            (
                sum(g == "BLOCKER" for g, _ in rows),
                sum(g == "WARNING" for g, _ in rows),
                0,
            ),
            rows,
            registration=registration_of(self.tmp),
        )

    def _audit_failed(self) -> Path:
        """The failed attempt the acknowledgement rests on (0.99.0)."""
        return findings.write_failed(
            self.tmp,
            "preflight",
            "haiku",
            scope_sha.area_stamp(self.tmp)[0],
            promises.block_stamp(UNFROZEN),
            findings.ATTEMPT_TIMEOUT_S,
            "claude-cli exit 1: ",
            "labkit-audit x --mode preflight",
            cause="unavailable",
        )

    def _start(self, run_kind: RunKind):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = runlog.Run("t", {}, self.tmp, run_kind=run_kind)
        return r, buf.getvalue()

    def test_an_open_blocker_refuses_the_acknowledged_full_run(self):
        self._record([BLOCKER])
        os.environ["LABKIT_UNFROZEN"] = "1"
        with self.assertRaises(SystemExit) as cm:
            self._start(run_kind="measurement")
        msg = str(cm.exception)
        self.assertIn("BLOCKER(s) nobody decided", msg)
        self.assertIn("LABKIT_UNFROZEN=1 does not pass it", msg)
        self.assertIn("-preflight.toml: BLOCKER · scripts/01_measure.py:3", msg)
        self.assertFalse((self.tmp / "runs").exists())

    def test_without_a_record_the_acknowledged_run_starts_over_a_failed_audit(self):
        """No findings record, but the audit was tried and the backend did not
        answer (0.98.0 let the run through without any attempt)."""
        tried = self._audit_failed()
        os.environ["LABKIT_UNFROZEN"] = "1"
        r, out = self._start(run_kind="measurement")
        self.assertIn("acknowledged", out)
        cfg = json.loads((r.dir / "config.json").read_text(encoding="utf-8"))
        self.assertTrue(cfg["unfrozen_ack"])
        self.assertEqual(cfg["audit_failed"], tried.name)

    def test_a_decided_blocker_starts_and_an_open_warning_is_said(self):
        path = self._record([BLOCKER, WARNING])
        text = path.read_text(encoding="utf-8")
        first, rest = text.split("[[finding]]", 1)
        blocker_tbl, warning_tbl = rest.split("[[finding]]")
        decided = blocker_tbl.replace('status = "open"', 'status = "limit"').replace(
            'reason = ""', 'reason = "the leak is the measured quantity"'
        )
        path.write_text(first + "[[finding]]" + decided + "[[finding]]" + warning_tbl)
        self._audit_failed()  # the protocol is still unfrozen: the hatch owes it
        os.environ["LABKIT_UNFROZEN"] = "1"
        _, out = self._start(run_kind="measurement")
        self.assertIn("acknowledged", out)
        self.assertIn("undecided WARNING(s) / NOTE(s) of the preflight audits", out)
        self.assertIn("the seed is not recorded", out)

    def test_a_probe_runs_over_an_open_blocker(self):
        """The BLOCKER has to be examined, and a probe is how (run_kind='probe')."""
        self._record([BLOCKER])
        r, _ = self._start(run_kind="probe")
        self.assertTrue((r.dir / "config.json").is_file())

    def test_the_refusal_holds_without_the_acknowledgement_too(self):
        self._record([BLOCKER])
        with self.assertRaises(SystemExit) as cm:
            self._start(run_kind="measurement")
        self.assertIn("BLOCKER(s) nobody decided", str(cm.exception))

    def test_an_unreadable_record_refuses_loudly(self):
        (self.tmp / findings.DIR).mkdir()
        (self.tmp / findings.DIR / "2026-10-17T10-00-preflight.toml").write_text(
            "not = [toml\n", encoding="utf-8"
        )
        os.environ["LABKIT_UNFROZEN"] = "1"
        with self.assertRaises(SystemExit) as cm:
            self._start(run_kind="measurement")
        self.assertIn("not TOML", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
