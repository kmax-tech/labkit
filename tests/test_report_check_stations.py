"""report-check's stations as gate tests: what each makes of its inputs,
from a context built in memory (`state_fixture.checked`) — the composition,
not the whole command (tests/test_report_check.py runs that)."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from labkit.checks.audit_binding import AuditError
from labkit.formats import runs
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    NOT_EXECUTABLE,
    OPEN_RULE,
    VIOLATED,
    WARNING,
    TECHNICAL_RULE,
    GateFinding,
    blocker,
    cited_rule,
)
from labkit.gates import finalize, report_check
from labkit.gates.report_context import Checked
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


def as_finalize_tells(found: list[GateFinding], words: str) -> list[GateFinding]:
    """FOUND as report-check's finalize station passes it on (the prefix
    `report_check.FINALIZE`), its sentence replaced by WORDS."""
    return [replace(f, text=report_check.FINALIZE + words) for f in found]


class FinalizeFindingsTheChainHoldsItself(unittest.TestCase):
    """`without_unreportable_warnings`, `without_declaration_blocker`: what
    the chain holds at a station of its own is left out of finalize's
    findings by the finding's name (`GateFinding.known_as`), whatever its sentence says; a finding
    known as nothing stays, and so does the finding where the chain's
    own station does not hold it."""

    RUN = AREA / "runs" / "r1"
    OTHER = GateFinding(
        WARNING,
        report_check.FINALIZE + "one draw only",
        rule=OPEN_RULE,
        evidence_kind=GUARANTEED,
    )
    TYPED = TEXT.replace(
        'preflight_audit = ""\n',
        'preflight_audit = ""\n\n[result]\nrun = "2026-10-07T10-00-00_final"\n',
    )

    def _unreportable(self) -> list[GateFinding]:
        marks = [runs.Unreportable(runs.UNFROZEN_ACK, "acknowledged while unfrozen")]
        with (
            mock.patch.object(finalize, "read_run_config", return_value=object()),
            mock.patch.object(finalize, "unreportable", return_value=marks),
        ):
            return finalize.unreportable_warnings(self.RUN)

    def _without_unreportable(
        self, finalized: list[GateFinding], run: Path | None
    ) -> list[GateFinding]:
        # the run's marks read as when finalize told them: a filter that
        # spells the sentence again spells the unchanged one
        marks = [runs.Unreportable(runs.UNFROZEN_ACK, "acknowledged while unfrozen")]
        with (
            mock.patch.object(finalize, "read_run_config", return_value=object()),
            mock.patch.object(finalize, "unreportable", return_value=marks),
        ):
            return report_check.without_unreportable_warnings(finalized, run)

    def test_an_unreportable_warning_in_other_words_is_left_out(self):
        (told,) = as_finalize_tells(self._unreportable(), "the mark in other words")
        self.assertEqual(told.grade, WARNING)
        self.assertEqual(
            self._without_unreportable([told, self.OTHER], self.RUN), [self.OTHER]
        )

    def test_a_warning_with_its_words_and_no_name_stays(self):
        (told,) = as_finalize_tells(self._unreportable(), "the mark in other words")
        same_words = replace(self.OTHER, text=told.text)
        self.assertEqual(
            self._without_unreportable([same_words], self.RUN), [same_words]
        )

    def test_without_an_answering_run_the_warning_stays(self):
        # no full-run station runs then: finalize's warning is the one telling
        found = as_finalize_tells(self._unreportable(), "the mark in other words")
        self.assertEqual(self._without_unreportable(found, None), found)

    def _unread_table(self) -> tuple[Checked, list[GateFinding]]:
        (why,) = finalize.declared_run_gaps(self.TYPED, AREA / "PROTOCOL-x.md")
        ctx = replace(
            checked(TEXT, run=None), text=self.TYPED, declaration_gap=why.text
        )
        return ctx, [why]

    def test_a_result_table_blocker_in_other_words_is_left_out(self):
        ctx, found = self._unread_table()
        (told,) = as_finalize_tells(found, "the table in other words")
        self.assertEqual(told.grade, BLOCKER)
        self.assertEqual(
            report_check.without_declaration_blocker([told, self.OTHER], ctx),
            [self.OTHER],
        )

    def test_a_blocker_known_as_nothing_stays(self):
        ctx, found = self._unread_table()
        (told,) = as_finalize_tells(found, "the table in other words")
        other = blocker(told.text, fix="`x`", rule=TECHNICAL_RULE)
        self.assertEqual(
            report_check.without_declaration_blocker([other], ctx), [other]
        )

    def test_where_the_table_reads_here_the_blocker_stays(self):
        # the declaration station holds nothing then
        _, found = self._unread_table()
        told = as_finalize_tells(found, "the table in other words")
        reads = checked(TEXT, run=None)
        self.assertEqual(report_check.without_declaration_blocker(told, reads), told)


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
