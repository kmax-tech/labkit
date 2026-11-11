"""preflight's stations as gate tests, below the whole command
(tests/test_preflight.py runs that): a head nobody can read ends the gate
with one blocker; an audit record that does not read blocks; a record or a
handover of another area that does not read warns."""

from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.formats import findings as audit_findings
from labkit.formats.gate import OPEN_RULE
from labkit.formats.gate import (
    BLOCKER,
    WARNING,
    Findings,
    TECHNICAL_RULE,
)
from labkit.gates import preflight
from state_fixture import area_evidence, audit_record


class PreflightStations(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.area = Path(self._tmp.name) / "experiments" / "01-x"
        self.area.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_head_nobody_can_read_is_the_one_early_end(self):
        (self.area / "PROTOCOL-x.md").write_text(
            "# Experiment protocol: x\n\nno head\n"
        )
        found = Findings(tell=None)
        self.assertEqual(preflight.preflight_area(self.area, findings=found), 1)
        (f,) = found.found
        self.assertTrue(f.text.startswith("HEAD (must): "), f.text)
        self.assertEqual((f.grade, f.rule), (BLOCKER, OPEN_RULE))

    def test_an_audit_record_that_does_not_read_blocks(self):
        (self.area / audit_findings.DIR).mkdir()
        (self.area / audit_findings.DIR / "2026-11-10T10-00-preflight.toml").write_text(
            "no = [toml\n"
        )
        found = Findings(tell=None)
        self.assertEqual(
            preflight.check_audit_records(found, self.area, frozen=False), []
        )
        (f,) = found.found
        self.assertEqual((f.grade, f.rule), (BLOCKER, TECHNICAL_RULE))
        self.assertIn("not TOML", f.text)

    RECORD = "2026-11-10T10-00-preflight.toml"

    def _coverage(self, *, frozen: bool) -> Findings:
        found = Findings(tell=None)
        preflight.check_audit_coverage(found, self.area, self.RECORD, "", frozen=frozen)
        return found

    def test_a_named_record_that_is_not_there_breaks_the_audit_rule(self):
        for frozen, grade in ((True, BLOCKER), (False, WARNING)):
            with self.subTest(frozen=frozen):
                (f,) = self._coverage(frozen=frozen).found
                self.assertEqual((f.grade, f.rule), (grade, preflight.LAB_015))
                self.assertIn("there is no such record", f.text)

    def test_a_named_record_that_does_not_read_is_the_technical_contract(self):
        (self.area / audit_findings.DIR).mkdir()
        (self.area / audit_findings.DIR / self.RECORD).write_text("no = [toml\n")
        (f,) = self._coverage(frozen=True).found
        self.assertEqual((f.grade, f.rule), (BLOCKER, TECHNICAL_RULE))

    def test_no_test_file_breaks_the_resolution_check_rule(self):
        tests = preflight.AreaTests("tests/test_01_x.py", [], "none", [])
        for frozen, grade in ((True, BLOCKER), (False, WARNING)):
            with self.subTest(frozen=frozen):
                found = Findings(tell=None)
                preflight.check_tests_owed(found, tests, frozen=frozen)
                (f,) = found.found
                self.assertEqual((f.grade, f.rule), (grade, preflight.LAB_016))

    def test_failing_tests_break_the_rule_the_gate_names(self):
        tests = preflight.AreaTests(
            "tests/test_01_x.py", [Path("test_01_x.py")], "failed", ["1 failed"]
        )
        found = Findings(tell=None)
        preflight.check_tests_owed(found, tests, frozen=False)
        (f,) = found.found
        self.assertEqual((f.grade, f.rule), (BLOCKER, preflight.LAB_016))

    def test_the_twin_no_record_blocks_nothing(self):
        found = Findings(tell=None)
        self.assertEqual(
            preflight.check_audit_records(found, self.area, frozen=True), []
        )
        self.assertEqual(found.found, [])

    def test_records_or_handovers_elsewhere_that_do_not_read_warn(self):
        found = Findings(tell=None)
        with mock.patch.object(
            preflight.audit_findings,
            "open_elsewhere",
            side_effect=audit_findings.FindingsError("02-y/audits/a.toml: not TOML"),
        ):
            preflight.check_handed_over_elsewhere(found, self.area, [])
        other = self.area.parent / "02-y"
        finding = audit_findings.Finding(
            "BLOCKER", "BLOCKER · x · statement · new class · y", "open", ""
        )
        record = audit_record(
            "a.toml", mode="preflight", run_id=None, area=other, found=[finding]
        )
        unread = dataclasses.replace(
            area_evidence(), handovers_unread="02-y/handovers.toml: not TOML"
        )
        with (
            mock.patch.object(
                preflight.audit_findings,
                "open_elsewhere",
                return_value=[(other, record, finding)],
            ),
            mock.patch.object(preflight.evidence, "read_evidence", return_value=unread),
        ):
            preflight.check_handed_over_elsewhere(found, self.area, [])
        self.assertEqual(
            [(f.grade, f.rule, f.text) for f in found.found],
            [
                (WARNING, TECHNICAL_RULE, "02-y/audits/a.toml: not TOML"),
                (WARNING, TECHNICAL_RULE, "02-y/handovers.toml: not TOML"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
