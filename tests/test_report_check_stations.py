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
    cited_rule,
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
                self.assertEqual((gap.outcome, gap.rule), (outcome, TECHNICAL_RULE))

    def test_the_twin_no_run_names_the_measurement(self):
        gap = report_check.analysis_audit_gap(
            checked(TEXT, run=None, why="nothing measured")
        )
        assert gap is not None
        self.assertEqual(gap.text, "no answering run to hold it to — nothing measured")


class AMissingAnalysisAuditRecordsTheRuleOfTheLane(unittest.TestCase):
    """`analysis_audit_gap`: where no decided record covers the area, the
    blocker records the lane's rule — at low LAB-017 The number of audits
    follows the cost tier, which owes this one audit at the promotion of
    the number; else LAB-050 Analysis audit before reporting — and the
    station's line cites it from that datum."""

    def _gap(self, repeat_cost: str):
        ctx = checked(head(repeat_cost=repeat_cost), run=AREA / "runs" / "r1")
        with (
            mock.patch.object(report_check, "analysis_now"),
            mock.patch.object(report_check, "covering_analysis", return_value=[]),
            mock.patch.object(
                report_check.audit_gaps, "audit_coverage", return_value="none saw it"
            ),
        ):
            (f,) = report_check.analysis_findings(ctx, result_section=False)
        return f

    def test_each_lane_cites_its_own_rule(self):
        for repeat_cost, rule in (
            ("low", "LAB-017 The number of audits follows the cost tier"),
            ("high", "LAB-050 Analysis audit before reporting"),
        ):
            with self.subTest(repeat_cost=repeat_cost):
                f = self._gap(repeat_cost)
                self.assertEqual((f.grade, f.rule), (BLOCKER, cited_rule(rule)))
                self.assertEqual(f.text, "analysis audit: none saw it")
                self.assertIn(f"analysis audit: none saw it ({rule}). Next: ", f.line)

    def test_the_twin_an_audit_that_cannot_be_held_cites_none(self):
        ctx = checked(TEXT, run=AREA / "runs" / "r1")
        gone = AuditError("out.jsonl is gone", fix="restore it")
        with mock.patch.object(report_check, "analysis_now", side_effect=gone):
            (f,) = report_check.analysis_findings(ctx, result_section=False)
        self.assertEqual(f.rule, TECHNICAL_RULE)
        self.assertEqual(
            f.line,
            "BLOCKER: analysis audit: the analysis audit cannot be held to the run: "
            "out.jsonl is gone. Next: restore it",
        )


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


class TheDecisionStationsLeaveUnreadableCoverageToTheAuditGap(unittest.TestCase):
    """The three decision stations (`report_decisions.limit_gaps`,
    `review_findings`, `followup_findings`) give [] when the analysis
    coverage cannot be read — their docstrings name `analysis_audit_gap` as
    the station that tells it. That dependency is documented, not enforced
    by an interface; this test holds it: on one area whose coverage does
    not read, the three are silent and the audit gap is the blocker, so
    their silence releases nothing."""

    RUN_ID = "2026-11-10T10-00-00_ab12"
    RESULT = head(repeat_cost="low", result=RUN_ID)

    def _ctx(self, area: Path):
        run = area / "runs" / self.RUN_ID
        run.mkdir(parents=True)
        (area / "audits").mkdir()
        (area / "audits" / "2026-11-12T10-00-analysis.toml").write_text(
            "no = [toml\n", encoding="utf-8"
        )
        return checked(self.RESULT, run=run, area=area)

    def test_the_stations_are_silent_and_the_audit_gap_blocks(self):
        from labkit.gates import report_decisions

        with tempfile.TemporaryDirectory() as d:
            ctx = self._ctx(Path(d))
            self.assertEqual(report_decisions.limit_gaps(ctx), [])
            self.assertEqual(report_decisions.review_findings(ctx), [])
            self.assertEqual(report_decisions.followup_findings(ctx), [])
            gap = report_check.analysis_audit_gap(ctx)
        assert gap is not None
        self.assertEqual(gap.grade, BLOCKER)
        self.assertIn("the analysis audit cannot be held to", gap.text)

    def test_the_twin_without_a_run_the_gap_names_the_measurement(self):
        """No run, nothing to cover: the stations are silent for that reason,
        and the gap names the missing measurement, not an unreadable area."""
        from labkit.gates import report_decisions

        ctx = checked(self.RESULT, run=None, why="nothing measured")
        self.assertEqual(report_decisions.followup_findings(ctx), [])
        gap = report_check.analysis_audit_gap(ctx)
        assert gap is not None
        self.assertNotIn("cannot be held to", gap.text)
