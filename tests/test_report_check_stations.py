"""report-check's stations as gate tests: what each makes of its inputs,
from a context built in memory (`state_fixture.checked`) — the composition,
not the whole command (tests/test_report_check.py runs that)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.checks.audit_binding import AuditError
from labkit.formats.gate import (
    BLOCKER,
    NOT_EXECUTABLE,
    VIOLATED,
    TECHNICAL_RULE,
)
from labkit.gates import report_check
from protocol_fixture import head
from state_fixture import AREA, checked

TEXT = head(repeat_cost="low")


class TheAnalysisAuditCannotBeHeld(unittest.TestCase):
    """`analysis_audit_gap`: when what the audit would be held to cannot be
    read, that is one blocker naming why — never a pass, never a crash."""

    def _gap(self, raised: BaseException):
        ctx = checked(TEXT, run=AREA / "runs" / "r1")
        with mock.patch.object(report_check, "analysis_now", side_effect=raised):
            return report_check.analysis_audit_gap(ctx)

    def test_a_registered_output_gone_holds_it_to_the_run(self):
        gap = self._gap(AuditError("out.jsonl is gone", fix="restore it"))
        assert gap is not None
        self.assertEqual((gap.grade, gap.rule), (BLOCKER, TECHNICAL_RULE))
        self.assertEqual(
            gap.text, "the analysis audit cannot be held to the run: out.jsonl is gone"
        )
        self.assertEqual(gap.fix, "restore it")

    def test_an_area_that_does_not_read_holds_it_to_the_area(self):
        # a missing file or a malformed one is a defect found; a refused
        # access leaves the check not executed
        for raised, outcome in (
            (ValueError("the promise block does not read"), VIOLATED),
            (FileNotFoundError("scripts/01_measure.py"), VIOLATED),
            (PermissionError("scripts/ refused"), NOT_EXECUTABLE),
        ):
            with self.subTest(raised=type(raised).__name__):
                gap = self._gap(raised)
                assert gap is not None
                self.assertTrue(
                    gap.text.startswith(
                        "the analysis audit cannot be held to the area: "
                    )
                )
                self.assertEqual(
                    (gap.check_outcome, gap.rule), (outcome, TECHNICAL_RULE)
                )

    def test_the_twin_no_run_names_the_measurement(self):
        gap = report_check.analysis_audit_gap(
            checked(TEXT, run=None, why="nothing measured")
        )
        assert gap is not None
        self.assertEqual(gap.text, "no answering run to hold it to — nothing measured")


class AnAnsweringRunWithoutItsRecord(unittest.TestCase):
    """`unreportable_gaps`: an answering run whose config.json the file
    state lacks cannot be held to what it was; a run that reads and is a
    full run gives nothing."""

    def test_no_record_is_one_blocker_naming_runlog(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "runs" / "r1"
            run.mkdir(parents=True)
            (f,) = report_check.unreportable_gaps(
                checked(TEXT, run=run), freeze_owed=False
            )
        self.assertEqual(
            f.text,
            "r1: no config.json in this file state — the run's record cannot be checked",
        )
        self.assertIn("measure through runlog", f.fix or "")
        self.assertEqual(f.rule, TECHNICAL_RULE)

    def test_the_twin_without_a_run_nothing_is_held(self):
        self.assertEqual(
            report_check.unreportable_gaps(checked(TEXT, run=None), freeze_owed=False),
            [],
        )


class AReportedNumberOwesTheFreeze(unittest.TestCase):
    """`freeze_gaps`: a protocol whose reported run required the freeze
    still carries `frozen = true` (LAB-104 A number leaves the area only
    through its adoption)."""

    def _unfrozen(self, frozen: bool):
        ctx = checked(head(repeat_cost="high", frozen=frozen), run=None)
        return [
            gap
            for gap in report_check.freeze_gaps(ctx, repeated=False)
            if "not `frozen = true`" in gap.text
        ]

    def test_a_head_without_the_flag_is_held_by_the_adoption_rule(self):
        (gap,) = self._unfrozen(False)
        self.assertEqual((gap.grade, gap.rule), (BLOCKER, report_check.LAB_104))

    def test_the_twin_a_frozen_head_is_not_held_for_the_flag(self):
        self.assertEqual(self._unfrozen(True), [])


if __name__ == "__main__":
    unittest.main()
