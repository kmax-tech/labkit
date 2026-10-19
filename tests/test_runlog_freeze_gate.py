"""Tests for runlog's freeze gate (2026-10-05).

A full run (`long=True`) on a protocol whose head is not `frozen = true`,
or whose `preflight_audit` is still empty, is refused before any run
directory exists. Probes (`long=False`) pass; a full run acknowledges
with LABKIT_UNFROZEN=1 over an audit the backend refused (the failed
attempt `labkit-audit` wrote, 0.99.0) and the acknowledgement lands in
config.json with that attempt; `long` is recorded for every run. At
`cost = "seconds"` the gate is the written registration (question,
criterion, admissibility condition), not the freeze (LAB-017 The number of audits follows the cost tier); the tier
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

from labkit.formats import findings, promises, scope_sha  # noqa: E402
from labkit.run import runlog  # noqa: E402
from protocol_fixture import DEFAULT_BLOCK, head, scope_file  # noqa: E402

AUDIT = "2026-10-05 · scope sha abc · 0 findings"
FROZEN = head(cost="hours", frozen=True, preflight_audit=AUDIT)
UNFROZEN = head(
    cost="hours", frozen=False, preflight_audit=AUDIT, promises=DEFAULT_BLOCK
)
PLACEHOLDER = head(
    cost="hours", frozen=True, preflight_audit="<date · scope sha · N findings>"
)
NO_FIELD = FROZEN.replace(f'preflight_audit = "{AUDIT}"\n', "")
REGISTRATION = """
- **Model / tool:** haiku
- **Question / hypothesis:** does the register beat the trivial decider?
- **Success / failure criterion:** [C1] accuracy above the trivial decider
- **Admissibility condition:** [A1] every case parsed
"""
# a count: no model, no id, the question only — the gate owes nothing more (0.87.1)
SECONDS_COUNT = (
    head(cost="seconds", promises=None)
    + "\n- **Question / hypothesis:** how many documents per case?\n"
)
SECONDS = head(cost="seconds") + REGISTRATION
SECONDS_NO_CRITERION = SECONDS.replace(
    "[C1] accuracy above the trivial decider", "<the criterion>"
)
HOURS_UNFROZEN = head(cost="hours", promises=DEFAULT_BLOCK) + REGISTRATION
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
        os.environ.pop(runlog.FOREGROUND_TIMEOUT_ENV, None)

    def _area(self, text: str) -> Path:
        (self.tmp / "PROTOCOL-x.md").write_text(text, encoding="utf-8")
        scope_file(self.tmp)  # the frozen fixture's block names it
        return self.tmp

    def _start(self, text: str, long: bool):
        area = self._area(text)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = runlog.Run("t", {}, area, long=long)
        return r, buf.getvalue()

    def _audited(self, record: bool = True) -> str:
        """A frozen protocol whose audit line carries the area's real stamp,
        and (RECORD) the decided preflight audit record of that stamp."""
        (self.tmp / "scripts").mkdir(exist_ok=True)
        (self.tmp / "scripts" / "m.py").write_text("x = 1\n")
        scope_file(self.tmp)  # part of the stamped code, written before the stamp
        sha = scope_sha.area_stamp(self.tmp)[0]
        text = head(
            cost="hours",
            frozen=True,
            preflight_audit=f"2026-10-07 · scope sha {sha} · 0 findings",
        )
        if record:
            findings.write(
                self.tmp,
                "preflight",
                "opus",
                sha,
                promises.block_stamp(text),
                (0, 0, 0),
                [],
            )
        return text

    def test_full_run_on_frozen_protocol_starts(self):
        r, _ = self._start(self._audited(), long=True)
        self.assertTrue((r.dir / "config.json").is_file())
        self.assertFalse(
            json.loads((r.dir / "config.json").read_text())["unfrozen_ack"]
        )

    def test_an_audit_line_of_other_code_is_refused(self):
        """Twin of the start above: the code changed after the audit, so the
        line's stamp no longer covers it (review 2026-10-07: a hand-written
        line was never checked against anything)."""
        text = self._audited()
        (self.tmp / "scripts" / "m.py").write_text("x = 2\n")
        area = self._area(text)
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                runlog.Run("t", {}, area, long=True)
        self.assertIn("changed after the audit", str(cm.exception))
        self.assertFalse((area / "runs").exists())

    def test_a_stamp_no_audit_record_saw_is_refused(self):
        """The line's sha is the code's now, but no preflight audit saw that
        code: after fixing the findings a cold agent stamped the new sha
        without a second audit (cloud judge probe, 2026-10-14)."""
        area = self._area(self._audited(record=False))
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                runlog.Run("t", {}, area, long=True)
        self.assertIn("no preflight audit saw the area as it is now", str(cm.exception))
        findings.write(area, "preflight", "opus", "0123456789ab", "b", (0, 0, 0), [])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                runlog.Run("t", {}, area, long=True)
        self.assertIn(
            "audited: code 0123456789ab, promises b", str(cm.exception)
        )  # the old audit, named

    def test_a_promise_rewritten_after_the_audit_is_refused(self):
        """The code is the audited code, the record is decided — and a
        promise sentence changed after the audit: the record named the
        code only, and the run started (review 2026-10-18)."""
        text = self._audited()
        area = self._area(
            text.replace("the criterion holds", "the criterion holds twice")
        )
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                runlog.Run("t", {}, area, long=True)
        self.assertIn("no preflight audit saw the area as it is now", str(cm.exception))
        self.assertIn("promises ", str(cm.exception))
        self.assertFalse((area / "runs").exists())

    def test_an_open_finding_of_the_covering_audit_is_refused(self):
        text = self._audited(record=False)
        sha = scope_sha.area_stamp(self.tmp)[0]
        findings.write(
            self.tmp,
            "preflight",
            "opus",
            sha,
            promises.block_stamp(text),
            (0, 1, 0),
            [("WARNING", "WARNING · x")],
        )
        area = self._area(text)
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                runlog.Run("t", {}, area, long=True)
        self.assertIn("still `open`", str(cm.exception))

    def test_an_audit_line_without_a_stamp_is_refused(self):
        area = self._area(FROZEN)  # "scope sha abc" is no stamp
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                runlog.Run("t", {}, area, long=True)
        self.assertIn("names no `scope sha", str(cm.exception))

    def test_a_waived_audit_is_refused_at_hours_and_names_the_honest_ways(self):
        """Until 0.99.0 `n/a — <reason>` passed as a visible decision; third
        haiku round, t18: the agent waived its own audit. The refusal names
        labkit-audit and the failed attempt, and offers no word to write."""
        text = head(
            cost="hours",
            frozen=True,
            preflight_audit="n/a — decided with the supervisor",
        )
        with self.assertRaises(SystemExit) as cm:
            self._start(text, long=True)
        msg = str(cm.exception)
        self.assertIn("nobody waives their own", msg)
        self.assertIn("labkit-audit <area> --mode preflight", msg)
        self.assertIn("the cost tier is wrong, not the line", msg)
        self.assertFalse((self.tmp / "runs").exists())

    def test_a_waived_audit_at_seconds_is_no_finding(self):
        """Twin: at seconds no audit is owed before the run; the line is not read."""
        text = head(cost="seconds", preflight_audit="n/a — seconds") + REGISTRATION
        r, _ = self._start(text, long=True)
        self.assertTrue((r.dir / "config.json").is_file())

    def test_full_run_on_an_unstamped_id_is_refused_before_mkdir(self):
        """Twin of the frozen start above: same protocol, id not stamped — the
        number would be bound to nothing (review 2026-10-07), at every tier."""
        for text in (
            head(id="<protocol-id>", cost="hours", frozen=True, preflight_audit=AUDIT),
            head(id="<protocol-id>", cost="seconds") + REGISTRATION,
        ):
            area = self._area(text)
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stdout(io.StringIO()):
                    runlog.Run("t", {}, area, long=True)
            self.assertIn("id is not stamped", str(cm.exception))
            self.assertFalse((area / "runs").exists())

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
        # a probe too: at seconds every run is the full run (the lane's
        # answer, `every_run_full`), and the refusal says so
        with self.assertRaises(SystemExit) as cm:
            runlog.Run("t", {}, area, long=False)
        self.assertIn("where every run is the full run", str(cm.exception))
        self.assertIn("Success / failure criterion", str(cm.exception))
        self.assertFalse((area / "runs").exists())

    def test_a_count_at_seconds_starts_without_criterion_or_tables(self):
        r, _ = self._start(SECONDS_COUNT, long=True)
        cfg = json.loads((r.dir / "config.json").read_text())
        self.assertEqual(cfg["cost_tier"], "seconds")
        self.assertIsNone(cfg.get("promises"))  # nothing registered, nothing recorded

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

    def test_any_agent_names_its_foreground_limit(self):
        """Under Codex or another agent the gate asked only for CLAUDECODE
        and let a long run die with that harness's timeout (TODO item 6).
        The variable names the limit for any agent; 0 says there is none,
        even under Claude Code."""
        env = runlog.FOREGROUND_TIMEOUT_ENV
        frozen = self._audited()  # passes every gate but this one
        try:
            os.environ[env] = "300"
            with self.assertRaises(SystemExit) as cm:
                self._start(frozen, long=True)
            self.assertIn(f"after 300 s ({env})", str(cm.exception))
            os.environ["CLAUDECODE"] = "1"
            os.environ[env] = "0"
            r, _ = self._start(frozen, long=True)
            self.assertTrue((r.dir / "config.json").is_file())
            os.environ[env] = "ten minutes"
            with self.assertRaises(SystemExit) as cm:
                runlog.foreground_timeout()
            self.assertIn("not a number of seconds", str(cm.exception))
        finally:
            os.environ.pop(env, None)
            os.environ.pop("CLAUDECODE", None)

    def test_tier_is_recorded_for_pilots_too(self):
        r, _ = self._start(FROZEN, long=False)
        self.assertEqual(
            json.loads((r.dir / "config.json").read_text())["cost_tier"], "hours"
        )

    def test_unfilled_tier_is_recorded_as_none_and_keeps_the_freeze(self):
        text = head(cost="<seconds | minutes | hours>", promises=DEFAULT_BLOCK)
        r, _ = self._start(text, long=False)
        self.assertIsNone(json.loads((r.dir / "config.json").read_text())["cost_tier"])
        with self.assertRaises(SystemExit) as cm:
            self._start(text, long=True)
        self.assertIn("not `frozen = true`", str(cm.exception))

    def _audit_failed(self, text: str) -> Path:
        """The failed preflight attempt at this code and these promises that a
        acknowledgement rests on (0.99.0)."""
        scope_file(self.tmp)
        return findings.write_failed(
            self.tmp,
            "preflight",
            "opus",
            scope_sha.area_stamp(self.tmp)[0],
            promises.block_stamp(text),
            findings.ATTEMPT_TIMEOUT_S,
            "claude-cli exit 1: ",
            "labkit-audit x --mode preflight",
        )

    def test_the_acknowledged_full_run_is_recorded(self):
        tried = self._audit_failed(UNFROZEN)
        os.environ["LABKIT_UNFROZEN"] = "1"
        try:
            r, out = self._start(UNFROZEN, long=True)
        finally:
            os.environ.pop("LABKIT_UNFROZEN", None)
        self.assertIn("LABKIT_UNFROZEN=1", out)
        self.assertIn(f"rests on the audit that could not run: {tried.name}", out)
        cfg = json.loads((r.dir / "config.json").read_text())
        self.assertTrue(cfg["unfrozen_ack"])
        self.assertTrue(cfg["long"])
        self.assertEqual(cfg["audit_failed"], tried.name)

    def test_the_acknowledgement_without_a_failed_audit_is_refused(self):
        """Second haiku round on 0.98.0: no agent started an audit, and the
        hatch asked for nothing. It acknowledges an audit that could not run."""
        os.environ["LABKIT_UNFROZEN"] = "1"
        try:
            with self.assertRaises(SystemExit) as cm:
                self._start(UNFROZEN, long=True)
        finally:
            os.environ.pop("LABKIT_UNFROZEN", None)
        self.assertIn("not one nobody ran", str(cm.exception))
        self.assertIn("attempts: none", str(cm.exception))
        self.assertFalse((self.tmp / "runs").exists())

    def test_a_full_run_records_long_and_a_probe_records_not(self):
        r, _ = self._start(self._audited(), long=True)
        self.assertTrue(json.loads((r.dir / "config.json").read_text())["long"])
        self.tmp = Path(tempfile.mkdtemp())
        r, _ = self._start(UNFROZEN, long=False)
        cfg = json.loads((r.dir / "config.json").read_text())
        self.assertFalse(cfg["long"])
        self.assertFalse(cfg["unfrozen_ack"])
        self.assertIsNone(cfg["audit_failed"])


if __name__ == "__main__":
    unittest.main()
