"""The running audit counts; an audit that died or got no result refuses the full run (2026-10-17).

A1 sees only a finished record; ten seconds earlier and haiku t3 would have
passed. Now `labkit-audit` leaves a `.running` marker before its model call:
a marker with a live pid means wait, one with a dead pid means the audit
died — `unavailable`, like a record of a call that got no result — and the
full run is refused until a rerun gets a result (author's decision
2026-10-17: fail loud instead of marking silently). Probes run.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import findings, runlog, scope_sha  # noqa: E402
from protocol_fixture import head, scope_file  # noqa: E402


def free_pid() -> int:
    """A pid no process has — `is_alive` answers False without `ps`."""
    pid = 4_194_303
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            pass
        pid -= 1


class AuditRunning(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ.pop("LABKIT_UNFROZEN", None)
        os.environ.pop("CLAUDECODE", None)
        os.environ.pop(runlog.FOREGROUND_TIMEOUT_ENV, None)
        (self.tmp / "scripts").mkdir()
        (self.tmp / "scripts" / "m.py").write_text("x = 1\n")
        scope_file(self.tmp)
        self.sha = scope_sha.area_stamp(self.tmp)[0]
        findings.write(
            self.tmp, "preflight", "opus", self.sha, (0, 0, 0), [], now=1_700_000_000
        )
        self.frozen = head(
            cost="hours",
            frozen=True,
            preflight_audit=f"2026-10-07 · scope sha {self.sha} · 0 findings",
        )
        (self.tmp / "PROTOCOL-x.md").write_text(self.frozen, encoding="utf-8")

    def tearDown(self):
        os.environ.pop("LABKIT_UNFROZEN", None)

    def _start(self, long: bool):
        with contextlib.redirect_stdout(io.StringIO()):
            return runlog.Run("t", {}, self.tmp, long=long)

    def _refused(self) -> str:
        with self.assertRaises(SystemExit) as cm:
            self._start(long=True)
        self.assertFalse((self.tmp / "runs").exists())
        return str(cm.exception)

    def test_the_audited_frozen_protocol_starts(self):
        r = self._start(long=True)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_a_live_marker_says_wait(self):
        p = findings.mark_running(
            self.tmp, "preflight", "opus", self.sha, pid=4711, script="labkit-audit"
        )
        with mock.patch.object(findings, "is_alive", lambda pid, script: True):
            msg = self._refused()
        self.assertIn("audit running since", msg)
        self.assertIn(p.name, msg)
        self.assertIn("wait for its record", msg)

    def test_a_dead_marker_is_an_audit_that_died(self):
        os.environ["LABKIT_UNFROZEN"] = "1"  # not even the acknowledgement passes it
        p = findings.mark_running(
            self.tmp,
            "preflight",
            "opus",
            self.sha,
            pid=free_pid(),
            script="labkit-audit",
        )
        msg = self._refused()
        self.assertIn("audit died", msg)
        self.assertIn(p.name, msg)
        self.assertIn("rerun `labkit-audit <area> --mode preflight`", msg)
        self.assertIn("deleting it does not", msg)
        # a probe runs over it: the way to find out why it died
        r = self._start(long=False)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_an_unavailable_newest_record_refuses_until_a_result_comes(self):
        os.environ["LABKIT_UNFROZEN"] = "1"
        findings.write_unavailable(
            self.tmp,
            "preflight",
            "opus",
            self.sha,
            "claude-cli: not logged in",
            now=1_700_000_060,
        )
        msg = self._refused()
        self.assertIn("audit unavailable since", msg)
        self.assertIn("not logged in", msg)
        # the twin: the rerun got a result, nothing open — the full run starts
        findings.write(
            self.tmp, "preflight", "opus", self.sha, (0, 0, 0), [], now=1_700_000_120
        )
        r = self._start(long=True)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_a_marker_with_a_record_after_it_still_counts(self):
        """The record replaces the marker only when the audit removes it; a
        marker left behind is a died audit even if a later record exists."""
        findings.mark_running(
            self.tmp,
            "preflight",
            "opus",
            self.sha,
            pid=free_pid(),
            script="labkit-audit",
        )
        self.assertIn("audit died", self._refused())


if __name__ == "__main__":
    unittest.main()
