"""Branches of code-check and notes-check no test reached, as tests of the
function that holds them: a scope file that does not parse leaves the
quality-check read check undone (a warning, not executed); the bundle
names a file it could not read; a note that cannot be opened warns,
check not executable."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import json

from labkit.checks import code_check, notes_check, protocol_report, run_record_check
from labkit.formats import audit_gaps, promises, protocol_block, protocol_history
from labkit.formats.standard_contract import ANALYSIS_AUDIT, PREFLIGHT_AUDIT
from labkit.gates import audit
from labkit.formats.gate import (
    GUARANTEED,
    NOT_EXECUTABLE,
    TECHNICAL_RULE,
    VIOLATED,
    WARNING,
    Findings,
    GateFinding,
)
from protocol_fixture import PID, head, run_record


class QualityCheckReadsNotDone(unittest.TestCase):
    def test_a_file_that_does_not_parse_leaves_the_check_undone(self):
        block = promises.parse_block(head(repeat_cost="low"))
        assert block is not None
        key = next(p.key for p in block.promises if p.kind == "quality-check")
        with (
            mock.patch.object(code_check, "area_files", return_value=[Path("x.py")]),
            mock.patch.object(code_check, "imported_repo_helpers", return_value=[]),
            mock.patch.object(
                code_check, "_key_reads", side_effect=ValueError("x.py: invalid syntax")
            ),
        ):
            (f,) = code_check.quality_check_reads(
                Path("area"),
                Path("area/PROTOCOL-x.md"),
                block,
                {key: ("scripts/01_measure.py:3",)},
            )
        self.assertEqual(
            (f.grade, f.outcome, f.rule), (WARNING, VIOLATED, TECHNICAL_RULE)
        )
        self.assertIn(
            "quality-check keys: read check not done — x.py: invalid syntax", f.text
        )

    def test_the_twin_no_quality_check_key_written_owes_nothing(self):
        block = promises.parse_block(head(repeat_cost="low"))
        assert block is not None
        self.assertEqual(
            code_check.quality_check_reads(Path("area"), Path("area/P.md"), block, {}),
            [],
        )


class TheBundleNamesWhatItCouldNotRead(unittest.TestCase):
    def test_an_unreadable_file_of_the_bundle_warns_at_the_command(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(head(repeat_cost="low"))
            bundle = area / "bundle.md"
            bundle.write_text("x")
            with (
                mock.patch.object(code_check, "code_findings", return_value=[]),
                mock.patch.object(
                    code_check, "write_bundle", return_value=(1, ["scripts/x.py"])
                ),
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                code_check.main([str(area), "--bundle", str(bundle)])
        self.assertIn(
            "bundle: scripts/x.py could not be read — the reader sees", out.getvalue()
        )


class ANoteThatCannotBeOpened(unittest.TestCase):
    def test_it_warns_not_executable_and_the_others_are_checked(self):
        told: list[str] = []
        with mock.patch.object(
            notes_check, "check_file", side_effect=PermissionError("refused")
        ):
            code = notes_check.check_notes([Path("notes/a.md")], tell=told.append)
        self.assertEqual(code, 0)
        self.assertTrue(
            any("notes/a.md: not readable (refused)" in t for t in told), told
        )
        found = Findings(tell=None)
        with (
            mock.patch.object(notes_check, "Findings", return_value=found),
            mock.patch.object(
                notes_check, "check_file", side_effect=PermissionError("refused")
            ),
        ):
            notes_check.check_notes([Path("notes/a.md")], tell=lambda _: None)
        (f,) = found.found
        self.assertEqual(
            (f.grade, f.outcome, f.rule),
            (WARNING, NOT_EXECUTABLE, TECHNICAL_RULE),
        )


class TheSofterLinesOfANoteWarn(unittest.TestCase):
    """`check_notes` tells each softer warning `check_file` returns as it
    was built, its rule the cause's, and tells the note `OK` only when
    neither a gap nor a softer warning stands — what the caller adds to the
    note's own checks (tests/test_read_causes.py, `NoteConventions`)."""

    def checked(self, softer: list[GateFinding]) -> tuple[Findings, list[str]]:
        found, told = Findings(tell=None), []
        with (
            mock.patch.object(notes_check, "Findings", return_value=found),
            mock.patch.object(notes_check, "check_file", return_value=([], softer)),
        ):
            code = notes_check.check_notes([Path("notes/a.md")], tell=told.append)
        self.assertEqual(code, 0)
        return found, told

    def test_a_softer_warning_is_told_with_its_rule(self):
        built = GateFinding(
            WARNING,
            "notes/a.md: line 3: a count without its run",
            rule=notes_check.LAB_082,
            evidence_kind=GUARANTEED,
        )
        found, told = self.checked([built])
        self.assertEqual(found.found, [built])
        self.assertNotIn("notes/a.md: OK", told)

    def test_the_twin_a_clean_note_is_told_ok(self):
        found, told = self.checked([])
        self.assertEqual((found.found, told), ([], ["notes/a.md: OK"]))


class AProtocolIdChangedAgainstHead(unittest.TestCase):
    """`protocol_history.check_protocol_id`: an id that differs from the
    one git's HEAD holds warns — the runs bound to the old id are no
    longer this protocol's; the same id passes."""

    def _found(self, was: str | None):
        text = head(repeat_cost="low")
        with mock.patch.object(protocol_history, "id_in_git_head", return_value=was):
            return protocol_history.check_protocol_id(
                Path("area/PROTOCOL-x.md"), protocol_block.head(text), {}
            )

    def test_a_changed_id_warns(self):
        (f,) = self._found("p-ffffffffffffffff")
        self.assertEqual((f.grade, f.rule), (WARNING, TECHNICAL_RULE))
        self.assertIn(
            "protocol id changed against HEAD (p-ffffffffffffffff -> ", f.text
        )

    def test_the_twin_the_same_id_passes(self):
        self.assertEqual(self._found(PID), [])


class AnAuditBeforeTheTierAsksForIt(unittest.TestCase):
    """`audit.early_for_tier`: at repeat cost low and no completed run, a
    preflight audit comes earlier than the tier asks (LAB-017); an analysis
    audit there is the one owed."""

    def test_a_preflight_audit_before_the_first_run_warns(self):
        with tempfile.TemporaryDirectory() as d:
            protocol = Path(d) / "PROTOCOL-x.md"
            protocol.write_text(head(repeat_cost="low"))
            (f,) = audit.early_for_tier(Path(d), protocol, PREFLIGHT_AUDIT)
            self.assertEqual(
                (f.grade, f.rule.rule_id if f.rule else None), (WARNING, "LAB-017")
            )
            self.assertEqual(
                audit.early_for_tier(Path(d), protocol, ANALYSIS_AUDIT), []
            )


class ADataEntryThatDoesNotRead(unittest.TestCase):
    """`run_record_check.provenance_findings`: a `data=` entry of the run's
    record that names no path blocks where the record is read."""

    def test_an_entry_naming_no_path_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "runs" / "r1"
            run.mkdir(parents=True)
            cfg = run_record(data={"broken": {"sha256": "ab", "rows": 1}})
            (run / "config.json").write_text(json.dumps(cfg))
            blockers, _, _ = run_record_check.provenance_findings(Path(d), run)
        (f,) = blockers
        self.assertIn("data['broken'] in the run's record names no path", f.text)
        self.assertEqual(f.rule, TECHNICAL_RULE)


class ProtocolCheckTellsItsWarnings(unittest.TestCase):
    """`protocol_report.print_report` prints protocol-check's own WARNING
    lines: a head's `preflight_audit` record that covers no full run, with
    its way out, and a registered constant nothing names."""

    def _told(self, **fields: object) -> list[str]:
        told: list[str] = []
        report = protocol_report.FileReport(Path("area/PROTOCOL-x.md"), None, **fields)  # type: ignore[arg-type] — the fields a case sets
        protocol_report.print_report(report, tell=told.append)
        return told

    def test_a_record_that_covers_no_full_run_warns_with_its_way_out(self):
        gap = audit_gaps.RecordGap(
            "the record saw scope sha 000000000000", "audit again", audit_gaps.LAB_015
        )
        told = self._told(audit_drift=gap)
        self.assertIn(
            "area/PROTOCOL-x.md: WARNING: preflight_audit: the record saw scope sha "
            "000000000000. Next: audit again",
            told,
        )

    def test_an_unmentioned_constant_warns(self):
        told = self._told(
            unmentioned_constants=["[criterion-1] threshold = 0.5 is named nowhere"]
        )
        self.assertIn(
            "area/PROTOCOL-x.md: WARNING: [criterion-1] threshold = 0.5 is named nowhere",
            told,
        )

    def test_the_twin_a_clean_report_tells_no_warning(self):
        self.assertFalse(any("WARNING" in t for t in self._told()))


if __name__ == "__main__":
    unittest.main()
