"""LABKIT_UNFROZEN=1 acknowledges an audit that could not run, not one nobody ran.

Second haiku round on labkit 0.98.0 (labkit-paper area 09, 2026-10-18): no
labkit agent started an audit, so the refusal over an open BLOCKER never
fired; t5 measured with long=True and LABKIT_UNFROZEN=1, and the hatch asked
for nothing. Since 0.99.0 the hatch at `minutes`/`hours` rests on the failed
attempt `labkit-audit` writes when the backend does not answer
(`audits/<date>-preflight-failed.toml`): at the code as it stamps now, the
promises as they read now, with the default timeout at least. An attempt at
other code, other promises, in another mode, or with a short timeout is not
one; a file nobody can read is loud. At `cost = "seconds"` no audit is owed
before the run, so the hatch there is unchanged.
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

from labkit.formats import findings, promises, scope_sha  # noqa: E402
from labkit.run import runlog  # noqa: E402
from protocol_fixture import DEFAULT_BLOCK, head, scope_file  # noqa: E402

UNFROZEN = head(cost="minutes", frozen=False, promises=DEFAULT_BLOCK)
REGISTRATION = """
- **Model / tool:** haiku
- **Question / hypothesis:** does the register beat the trivial decider?
- **Success / failure criterion:** [C1] accuracy above the trivial decider
- **Admissibility condition:** [A1] every case parsed
"""
SECONDS_NO_CRITERION = (head(cost="seconds") + REGISTRATION).replace(
    "[C1] accuracy above the trivial decider", "<the criterion>"
)


class FailedAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "PROTOCOL-x.md").write_text(UNFROZEN, encoding="utf-8")
        scope_file(self.tmp)
        os.environ["LABKIT_UNFROZEN"] = "1"
        os.environ.pop("CLAUDECODE", None)
        os.environ.pop(runlog.FOREGROUND_TIMEOUT_ENV, None)

    def tearDown(self):
        os.environ.pop("LABKIT_UNFROZEN", None)

    def _failed(
        self,
        *,
        mode: str = "preflight",
        sha: str | None = None,
        block: str | None = None,
        timeout: int = findings.ATTEMPT_TIMEOUT_S,
        now: float | None = None,
    ) -> Path:
        return findings.write_failed(
            self.tmp,
            mode,
            "opus",
            sha or scope_sha.area_stamp(self.tmp)[0],
            block or promises.block_stamp(UNFROZEN),
            timeout,
            "claude-cli exit 1: ",
            "labkit-audit x --mode preflight",
            now=now,
        )

    def _start(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = runlog.Run("t", {}, self.tmp, long=True)
        return r, buf.getvalue()

    def _refused(self) -> str:
        with self.assertRaises(SystemExit) as cm:
            self._start()
        self.assertFalse((self.tmp / "runs").exists())
        return str(cm.exception)

    def test_the_fitting_attempt_lets_the_acknowledged_run_start_and_is_recorded(self):
        tried = self._failed()
        r, out = self._start()
        self.assertIn(f"rests on the audit that could not run: {tried.name}", out)
        self.assertIn("claude-cli exit 1", out)
        cfg = json.loads((r.dir / "config.json").read_text(encoding="utf-8"))
        self.assertTrue(cfg["unfrozen_ack"])
        self.assertEqual(cfg["audit_failed"], tried.name)

    def test_no_attempt_refuses_and_says_what_is_owed(self):
        msg = self._refused()
        self.assertIn("not one nobody ran", msg)
        self.assertIn("attempts: none", msg)
        self.assertIn("labkit-audit", msg)
        self.assertIn(findings.FAILED_SUFFIX, msg)

    def test_an_attempt_at_other_code_is_not_one(self):
        self._failed(sha="000000000000")
        msg = self._refused()
        self.assertIn("code 000000000000", msg)  # listed, so the reader sees why

    def test_an_attempt_at_other_promises_is_not_one(self):
        self._failed(block="000000000000")
        self.assertIn("promises 000000000000", self._refused())

    def test_an_analysis_attempt_is_not_a_preflight_one(self):
        self._failed(mode="analysis")
        self.assertIn("not one nobody ran", self._refused())

    def test_an_attempt_given_too_little_time_is_not_one(self):
        """`--timeout 1` is the cheap forgery: the call cannot have been tried."""
        self._failed(timeout=findings.ATTEMPT_TIMEOUT_S - 1)
        msg = self._refused()
        self.assertIn(f"at least {findings.ATTEMPT_TIMEOUT_S} s", msg)
        self.assertIn(f"{findings.ATTEMPT_TIMEOUT_S - 1} s)", msg)

    def test_a_longer_timeout_counts_and_the_newest_fitting_is_named(self):
        self._failed(timeout=findings.ATTEMPT_TIMEOUT_S + 600, now=1_700_000_000)
        newer = self._failed(now=1_700_000_060)
        r, _ = self._start()
        cfg = json.loads((r.dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["audit_failed"], newer.name)

    def test_a_hand_written_file_without_the_table_is_loud(self):
        (self.tmp / findings.DIR).mkdir()
        (self.tmp / findings.DIR / f"x-preflight{findings.FAILED_SUFFIX}").write_text(
            "[audit]\nmode = 'preflight'\n", encoding="utf-8"
        )
        self.assertIn("no [failed] table", self._refused())

    def test_the_attempt_does_not_read_as_a_findings_record(self):
        """`area_records` sees the records only: the attempt is not an audit."""
        self._failed()
        self.assertEqual(findings.area_records(self.tmp), [])
        self.assertEqual(len(findings.failed_attempts(self.tmp)), 1)

    def test_at_seconds_the_hatch_owes_no_attempt(self):
        (self.tmp / "PROTOCOL-x.md").write_text(SECONDS_NO_CRITERION, encoding="utf-8")
        r, out = self._start()
        self.assertIn("acknowledged", out)
        cfg = json.loads((r.dir / "config.json").read_text(encoding="utf-8"))
        self.assertTrue(cfg["unfrozen_ack"])
        self.assertIsNone(cfg["audit_failed"])

    def test_without_the_acknowledgement_nothing_changes(self):
        os.environ.pop("LABKIT_UNFROZEN")
        self._failed()
        self.assertIn("not `frozen = true`", self._refused())


if __name__ == "__main__":
    unittest.main()
