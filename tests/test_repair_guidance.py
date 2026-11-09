"""The line under a `fixed` decision (`audit_decisions.repair_hint`)
explains what `fixed` means for the kind of repair and points to
`labkit-next` for the step it owes; it names no action of its own, so it
cannot contradict the step labkit-next names.

The states where an action of the line's own would contradict
labkit-next: "owes no new measurement" beside a code change, "measure
again" with the repair already measured, no withdrawal with run A adopted,
a third run with B already measured, "measure again" while the answering
run's choice is blocked, and a released field called refused. Through the
real commands; no model call."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import test_end_to_end as e2e
from labkit.gates import registration_hold
from labkit import PACKAGE_DIR
from labkit.formats import findings
from labkit.gates import audit_decisions
from labkit.gates import next_step

#: actions the decision's line must not prescribe — labkit-next names them
ACTIONS = (
    "measure again",
    "measure anew",
    "withdraw",
    "restore",
    "audit that run",
    "on that run",
    "the follow-up analysis audit on",
)


class Guidance(e2e.CorrectionCommands):
    """The correction fixture with the decision's line and labkit-next's
    step at hand. A base without tests of its own."""

    def next_(self) -> str:
        old = Path.cwd()
        os.chdir(self.lab.root)
        try:
            return next_step.next_step(self.area, self.protocol).next
        finally:
            os.chdir(old)

    def decided(self, record: Path, why: str) -> str:
        """The line under the decision `fixed` on RECORD's first finding."""
        lines = self.decide(record, 1, "fixed", why).splitlines()
        (at,) = [i for i, ln in enumerate(lines) if ln.startswith("fixed: ")]
        return lines[at + 1]

    def points_to_next(self, line: str) -> None:
        """LINE names no action of its own and points to labkit-next."""
        self.assertIn("labkit-next", line)
        self.assertIn("names the step this repair owes now", line)
        for action in ACTIONS:
            self.assertNotIn(action, line)

    def code_finding(self) -> Path:
        rc, out, _ = self.analysis(e2e.CorrectionThenNewRun.CODE_FINDING)
        self.assertEqual(rc, 1, out)
        assert self.record is not None
        return self.record

    def adopt_a(self) -> None:
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 0, out)
        self.lab.commit("adopt A")

    def released_for_a(self) -> Path:
        """Data / scope corrected for A and released by its follow-up."""
        blocking = self.audited("BLOCKER", "Data / scope")
        self.describe(self.RIGHT)
        self.decide(blocking, 1, "fixed", "Data / scope now says 3 documents")
        rc, out, _ = self.follow_up(blocking, "resolved", "3 documents, as A read")
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        return blocking


class TheLineExplainsAndPointsToNext(Guidance):
    """Each state where an action of the line's own would contradict
    labkit-next: the line names no action; labkit-next names the one the
    state owes."""

    def test_a_correction_beside_a_code_change_before_and_after_measuring(self):
        correction = self.audited("WARNING", "Data / scope")
        self.describe(self.RIGHT)
        self.change_code()
        line = self.decided(correction, "the count corrected, the code changed")
        self.points_to_next(line)
        self.assertIn("a correction of Data / scope in place", line)
        self.assertNotIn("owes no new measurement", line)
        self.assertIn("measure again", self.next_())
        run_b = self.measure()
        self.points_to_next(self.decided(correction, "the repaired code measured"))
        self.assertTrue(
            self.next_().startswith(f"the follow-up analysis audit on {run_b}"),
            self.next_(),
        )

    def test_a_code_finding_decided_after_its_repair_was_measured(self):
        code = self.code_finding()
        self.change_code()
        self.measure()
        self.points_to_next(self.decided(code, "the code repaired and measured"))
        self.assertTrue(self.next_().startswith("audit "), self.next_())

    def test_a_code_repair_measured_while_a_stands_adopted(self):
        """A case: labkit-next withdraws A first."""
        self.adopt_a()
        code = self.code_finding()
        self.change_code()
        self.measure()
        self.points_to_next(self.decided(code, "the code repaired and measured"))
        self.assertIn("--withdraw", self.next_())

    def test_a_correction_beside_a_measured_repair_while_a_stands_adopted(self):
        """A case: no third run is named; labkit-next withdraws first."""
        self.adopt_a()
        correction = self.audited("WARNING", "Data / scope")
        self.describe(self.RIGHT)
        self.change_code()
        self.measure()
        self.points_to_next(self.decided(correction, "corrected, repaired, measured"))
        self.assertIn("--withdraw", self.next_())

    def test_a_blocked_choice_of_the_answering_run(self):
        """A case: a newer run that does not read blocks the choice."""
        code = self.code_finding()
        self.change_code()
        run_b = self.measure()
        newer = self.area / "runs" / (run_b[:-4] + "zzzz")
        shutil.copytree(self.area / "runs" / run_b, newer)
        (newer / "config.json").write_text("{not json", encoding="utf-8")
        self.points_to_next(self.decided(code, "the code repaired"))

    def test_a_field_edited_after_the_new_run_then_released_on_it(self):
        """A case against the text B saw: Data / scope edited after B ran, the correction released on B; finalize holds it as B saw
        it, and the line names nothing that could contradict that hold."""
        correction = self.released_for_a()
        code = self.code_finding()
        self.change_code()
        self.decide(code, 1, "fixed", "rows() keeps the count alone again")
        self.measure()
        self.describe("data/raw/docs, the 3 documents, read directly")
        rc, out, _ = self.analysis(
            f"FIX · {code.name}#1 · resolved · judged on the run as it stands\n"
            f"FIX · {correction.name}#1 · resolved · judged on the run as it stands\n"
            f"\n{self.clean}"
        )
        later = self.code_finding()
        self.points_to_next(self.decided(later, "nothing changed yet"))

    def test_a_released_correction_is_not_called_refused(self):
        """A later `fixed` decision does not call the released field
        refused."""
        self.released_for_a()
        line = self.decided(self.code_finding(), "nothing changed yet")
        self.points_to_next(line)
        self.assertNotIn("Data / scope", line)

    def test_the_twin_a_description_alone_owes_no_measurement(self):
        """A correction in place with nothing else changed: the explanation
        states the release condition; labkit-next names no measurement."""
        correction = self.audited("WARNING", "Data / scope")
        self.describe(self.RIGHT)
        line = self.decided(correction, "the count corrected")
        self.points_to_next(line)
        self.assertIn("only a follow-up analysis audit's `resolved`", line)
        self.assertNotIn("measure again", self.next_())


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
