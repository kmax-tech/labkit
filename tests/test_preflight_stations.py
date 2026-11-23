"""preflight's stations as gate tests, below the whole command
(tests/test_preflight.py runs that): a head nobody can read ends the gate
with one blocker; an audit record that does not read blocks; a record or a
handover of another area that does not read warns."""

from __future__ import annotations

import dataclasses
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.formats import findings as audit_findings
from labkit.formats import protocol_block, protocol_check
from labkit.formats.gate import (
    BLOCKER,
    OPEN_RULE,
    WARNING,
    Findings,
    TECHNICAL_RULE,
)
from labkit.formats.scope_sha import NothingToStamp, area_stamp
from labkit.gates import preflight
from protocol_fixture import declared_scope_area, head
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
        self.assertEqual((f.grade, f.rule), (BLOCKER, preflight.LAB_011))

    def test_a_head_that_does_not_parse_is_the_technical_contract(self):
        (self.area / "PROTOCOL-x.md").write_text(
            "# Experiment protocol: x\n\n```toml\n[protocol\n```\n"
        )
        found = Findings(tell=None)
        self.assertEqual(preflight.preflight_area(self.area, findings=found), 1)
        (f,) = found.found
        self.assertEqual((f.grade, f.rule), (BLOCKER, TECHNICAL_RULE))

    def _field_findings(self, text: str | None = None, **lists: list) -> Findings:
        """Station 1 on a field report holding only LISTS, over TEXT (a bare
        head when None)."""
        text = head() if text is None else text
        protocol = self.area / "PROTOCOL-x.md"
        protocol.write_text(text, encoding="utf-8")
        parsed = protocol_block.head(text)
        report = protocol_check.FieldReport(
            parsed,
            None,
            None,
            must_gaps=[],
            missing_should=lists.get("missing_should", []),
            must_holes=lists.get("must_holes", []),
            soft_holes=lists.get("soft_holes", []),
            repeated=[],
        )
        found = Findings(tell=None)
        preflight.check_protocol_fields(found, protocol, text, report, parsed)
        return found

    def test_a_field_not_owed_as_a_must_warns_as_an_open_assignment(self):
        found = self._field_findings(
            missing_should=["Problem in one sentence"], soft_holes=[(7, "Unit")]
        )
        self.assertEqual(
            [(f.grade, f.rule) for f in found.found], [(WARNING, OPEN_RULE)] * 2
        )

    def test_a_should_field_under_its_earlier_label_is_renamed_not_added(self):
        """A label the migration renames still stands: the warning's way is
        renaming that line; the twin, no earlier label, names no way."""
        text = head() + "\n- **Noise ceiling → threshold:** spread 0.02\n"
        line = (
            text.splitlines().index("- **Noise ceiling → threshold:** spread 0.02") + 1
        )
        (f,) = self._field_findings(
            text, missing_should=["Noise floor → threshold"]
        ).found
        self.assertEqual(f.grade, WARNING)
        self.assertIn(f"rename the label on line {line} from", f.fix or "")
        (twin,) = self._field_findings(missing_should=["Noise floor → threshold"]).found
        self.assertIsNone(twin.fix)

    def test_the_twin_a_must_placeholder_breaks_the_required_field_rule(self):
        (f,) = self._field_findings(must_holes=[(7, "Unit")]).found
        self.assertEqual((f.grade, f.rule), (BLOCKER, preflight.LAB_011))

    def test_an_audit_record_that_does_not_read_blocks(self):
        (self.area / audit_findings.DIR).mkdir()
        (self.area / audit_findings.DIR / "2026-11-10T10-00-preflight.toml").write_text(
            "no = [toml\n"
        )
        found = Findings(tell=None)
        self.assertIsNone(preflight.check_audit_records(found, self.area, frozen=False))
        (f,) = found.found
        self.assertEqual((f.grade, f.rule), (BLOCKER, TECHNICAL_RULE))
        self.assertIn("not TOML", f.text)

    def _closing_lines(self, records: list[audit_findings.Record] | None) -> list[str]:
        """Station 3's closing lines for RECORDS, nothing open elsewhere."""
        told: list[str] = []
        with mock.patch.object(
            preflight.audit_findings, "open_elsewhere", return_value=[]
        ):
            preflight.check_handed_over_elsewhere(
                Findings(tell=told.append), self.area, records
            )
        return told

    def test_records_that_did_not_read_are_not_told_as_none(self):
        self.assertEqual(self._closing_lines(None), [])

    def test_the_twin_no_records_are_told_as_none(self):
        self.assertEqual(self._closing_lines([]), ["  none recorded"])

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


class ScopeStampStation(unittest.TestCase):
    """Station 5 tells the stamp, or why it cannot stamp. A file that stands
    and does not open blocks always; a cause station 4 blocks (a missing
    declared scope file, a script that does not read) is told here while
    any earlier blocker stands, once; with none standing — a cause station
    4 does not read (a sibling protocol, a module only a declared scope
    file imports) — it blocks here. Nothing to stamp is told. It does not
    end the gate."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = declared_scope_area(Path(tmp.name))

    def stamp_station(self, held: bool = True) -> tuple[list[str], list[str]]:
        """(lines told, blockers) of station 5 alone; HELD: an earlier
        station's blocker already stands (left out of the result)."""
        told: list[str] = []
        found = Findings(tell=told.append)
        if held:
            found.block("an earlier station's blocker", fix="`x`", rule=TECHNICAL_RULE)
            told.clear()
        preflight.check_scope_stamp(found, self.area, self.area / "PROTOCOL-x.md")
        return told, found.blocked[1:] if held else found.blocked

    def script(self, text: str) -> Path:
        """A script under the area's scripts/ holding TEXT."""
        path = self.area / "scripts" / "measure.py"
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
        return path

    def test_its_way_out_names_the_protocol_where_the_area_holds_several(self):
        # preflight refuses to choose there: a line without it would refuse
        self.script("def broken(:\n")
        (self.area / "PROTOCOL-y.md").write_text("# y\n")
        found = Findings(tell=None)
        preflight.check_scope_stamp(found, self.area, self.area / "PROTOCOL-x.md")
        (fix,) = [f.fix for f in found.found if f.fix]
        self.assertIn("--protocol", fix)
        self.assertIn("PROTOCOL-x.md", fix)

    def test_the_twin_with_one_protocol_its_way_out_names_none(self):
        self.script("def broken(:\n")
        found = Findings(tell=None)
        preflight.check_scope_stamp(found, self.area, self.area / "PROTOCOL-x.md")
        (fix,) = [f.fix for f in found.found if f.fix]
        self.assertIn("`preflight ", fix)
        self.assertNotIn("--protocol", fix)

    def test_a_script_that_does_not_parse_cannot_stamp(self):
        self.script("def broken(:\n")
        (line,), blocked = self.stamp_station()
        self.assertTrue(line.startswith("  cannot stamp: "), line)
        self.assertIn("measure.py", line)
        self.assertEqual(blocked, [])

    @unittest.skipIf(os.geteuid() == 0, "root reads a file of mode 0")
    def test_the_whole_gate_blocks_a_script_that_does_not_read_once(self):
        script = self.script("print('criterion_1_pass')\n")
        script.chmod(0)
        self.addCleanup(script.chmod, 0o644)
        found = Findings(tell=None)
        self.assertEqual(preflight.preflight_area(self.area, findings=found), 1)
        named = [m for m in found.blocked if "measure.py" in m]
        self.assertEqual(len(named), 1, found.blocked)
        self.assertIn("cannot be read", named[0])

    @unittest.skipIf(os.geteuid() == 0, "root reads a file of mode 0")
    def test_without_lib_a_script_that_does_not_read_blocks_once(self):
        # no lib/ or src/: the stamp parses nothing and meets the script in
        # its byte read, which must tell it like station 4's parse does
        shutil.rmtree(self.area.parent.parent / "lib")
        script = self.script("print('criterion_1_pass')\n")
        script.chmod(0)
        self.addCleanup(script.chmod, 0o644)
        found = Findings(tell=None)
        self.assertEqual(preflight.preflight_area(self.area, findings=found), 1)
        named = [m for m in found.blocked if "measure.py" in m]
        self.assertEqual(len(named), 1, found.blocked)
        self.assertIn("cannot be read", named[0])

    def test_with_no_blocker_standing_a_stamp_that_fails_blocks(self):
        self.script("def broken(:\n")
        _, blocked = self.stamp_station(held=False)
        self.assertEqual(len(blocked), 1, blocked)
        self.assertTrue(blocked[0].startswith("cannot stamp the area's scope: "))
        self.assertIn("measure.py", blocked[0])

    def test_the_twin_with_no_blocker_a_stamp_that_computes_passes(self):
        sha = area_stamp(self.area)[0]
        self.assertEqual(self.stamp_station(held=False), ([f"  {sha}"], []))

    def test_a_module_only_a_declared_file_imports_is_blocked_here(self):
        # station 4 does not read lib/deep.py: no earlier blocker names it
        (self.area.parent.parent / "lib" / "deep.py").write_text("def x(:\n")
        _, blocked = self.stamp_station(held=False)
        self.assertEqual(len(blocked), 1, blocked)
        self.assertIn("deep.py", blocked[0])

    def test_a_sibling_protocols_missing_scope_file_is_blocked_here(self):
        block = (
            '[[promise]]\nid = "criterion-1"\nkey = "criterion_1_pass"\n'
            'sentence = "s"\nscope = ["nothere.py"]\n'
        )
        (self.area / "PROTOCOL-y.md").write_text("# y\n" + head(promises=block))
        _, blocked = self.stamp_station(held=False)
        self.assertEqual(len(blocked), 1, blocked)
        self.assertIn("nothere.py", blocked[0])

    def raising(self, exc: Exception, held: bool) -> tuple[list[str], list[str]]:
        """Station 5 when the stamp raises EXC (see `stamp_station`)."""
        with mock.patch.object(preflight, "area_stamp", side_effect=exc):
            return self.stamp_station(held=held)

    def test_a_file_that_does_not_open_blocks_beside_any_blocker(self):
        _, blocked = self.raising(PermissionError("rows.jsonl: denied"), held=True)
        self.assertEqual(len(blocked), 1, blocked)
        self.assertIn("rows.jsonl", blocked[0])

    def test_any_other_unread_record_blocks_when_nothing_else_does(self):
        _, blocked = self.raising(ValueError("x.toml: not TOML"), held=False)
        self.assertEqual(len(blocked), 1, blocked)
        self.assertIn("x.toml", blocked[0])

    def test_the_twin_beside_a_blocker_it_is_told(self):
        told, blocked = self.raising(ValueError("x.toml: not TOML"), held=True)
        self.assertEqual((told, blocked), (["  cannot stamp: x.toml: not TOML"], []))

    def test_nothing_to_stamp_is_told_not_blocked(self):
        told, blocked = self.raising(NothingToStamp("no scope files"), held=False)
        self.assertEqual(blocked, [])
        self.assertTrue(told[0].startswith("  no scripts matching"), told)

    def test_the_whole_gate_tells_it_beside_the_blockers_it_has(self):
        # the fixture's head lacks required fields: the gate is blocked
        # already, so the cause is told, and the exit stays 1
        (self.area.parent.parent / "lib" / "deep.py").write_text("def x(:\n")
        told: list[str] = []
        found = Findings(tell=told.append)
        self.assertEqual(preflight.preflight_area(self.area, findings=found), 1)
        self.assertTrue(
            any(
                line.startswith("  cannot stamp: ") and "deep.py" in line
                for line in told
            ),
            told,
        )


if __name__ == "__main__":
    unittest.main()
