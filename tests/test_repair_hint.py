"""Which explanation the line under a `fixed` decision gives
(`audit_decisions.repair_hint`), read from the finding's place and the
standard's field sets alone: a correction in place, the question as
registered, or any other repair. The line in the state the area is in, and
the step labkit-next names beside it: tests/test_repair_guidance.py."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from labkit.gates import registration_hold
from labkit import PACKAGE_DIR
from labkit.formats import findings
from labkit.gates import audit_decisions


class TheBranchFollowsTheFindingAndTheStandard(unittest.TestCase):
    """Which explanation a `fixed` finding gets is read from its place and
    the standard's field sets, never from the area's state: only a field of what the number is about is a correction in
    place, the question stands as registered, both only after the first
    measurement; every other place is "any other repair"."""

    def setUp(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        self.area = tmp / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        template = PACKAGE_DIR / "templates" / "experiment-protocol.md.template"
        (self.area / "PROTOCOL-x.md").write_text(
            template.read_text(encoding="utf-8"), encoding="utf-8"
        )
        self.record = self.area / "audits" / "2026-11-03T10-00-analysis.toml"

    def line(self, place: str, grade: str = "WARNING") -> str:
        decided = findings.Finding(
            grade, f"{grade} · {place} · statement · something is wrong", "fixed", "why"
        )
        return audit_decisions.repair_hint(self.area, self.record, None, decided)

    def test_a_field_of_what_the_number_is_about_is_a_correction_after_the_first_run(
        self,
    ):
        line = self.line("PROTOCOL-x.md:Unit")
        self.assertIn("a correction of Unit in place", line)
        self.assertIn("after the first measurement only a follow-up", line)

    def test_the_question_stands_as_registered_after_the_first_run(self):
        line = self.line("PROTOCOL-x.md:Question / hypothesis")
        self.assertIn("after the first measurement it has no correction in place", line)
        # it explains the condition and names no way of its own: the
        # correction route is not offered for the question
        self.assertIn("names the step this repair owes now", line)
        self.assertNotIn("a correction in place", line)
        self.assertNotIn("misdescribing the unchanged run", line)

    def test_other_fields_and_places_are_any_other_repair(self):
        for place in (
            "PROTOCOL-x.md:Conclusion",
            "PROTOCOL-x.md:Inference criterion",
            "PROTOCOL-x.md:42",
            "scripts/01_measure.py:12",
        ):
            with self.subTest(place=place):
                line = self.line(place)
                self.assertTrue(line.startswith("any other repair"), line)
                self.assertNotIn("a correction of", line)

    def test_a_start_of_one_label_is_that_field(self):
        line = self.line("PROTOCOL-x.md:Uni")
        self.assertIn("a correction of Unit in place", line)

    def test_a_start_several_labels_share_is_said_and_binds_nothing(self):
        # `Data` begins Data / scope, Data preparation and Data profile
        line = self.line("PROTOCOL-x.md:Data")
        self.assertIn("its place names no one field of the protocol", line)
        self.assertIn("'Data' begins 3 fields", line)
        self.assertNotIn("a correction of", line)

    def test_finalize_holds_a_correction_whose_field_cannot_be_told(self):
        """finalize releases a correction by its field: a place several
        labels begin is a blocker with its reason, never a silent miss."""
        from labkit.checks.audit_binding import AuditError
        from labkit.gates import ways_out

        protocol = self.area / "PROTOCOL-x.md"
        text = protocol.read_text(encoding="utf-8")
        decided = findings.Finding(
            "WARNING",
            "WARNING · PROTOCOL-x.md:Data · statement · LAB-015 Preflight audit before freezing · x",
            "fixed",
            "why",
        )
        with self.assertRaises(AuditError) as caught:
            registration_hold._correction_field(decided, protocol, text)
        self.assertIn("'Data' begins 3 fields", caught.exception.why)
        self.assertEqual(caught.exception.fix, ways_out.PLACE_UNCLEAR_WAY)
        # the twin: a start of one label is that field
        unit = findings.Finding(
            "WARNING",
            "WARNING · PROTOCOL-x.md:Uni · statement · LAB-015 Preflight audit before freezing · x",
            "fixed",
            "why",
        )
        self.assertEqual(
            registration_hold._correction_field(unit, protocol, text), "unit"
        )

    def test_several_protocols_keep_the_line_one_line(self):
        (self.area / "PROTOCOL-y.md").write_text(
            (self.area / "PROTOCOL-x.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        line = self.line("PROTOCOL-x.md:Unit")
        self.assertNotIn("\n", line)
        self.assertIn("could not be read", line)
