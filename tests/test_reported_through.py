"""A measurement protocol whose runs are reported through an adopted
analysis: the statement read from the analysis run's record and adoption
(`report_hold.stated_through`), the block held to it (`through_gap`), the
registered report it releases (`registered_report.report_owed`), the
writer (`protocol-fill --reported-through`) and what the report reviewer
is told. The block as text: tests/test_report_blocks_text.py. The whole
gate on a real repository, with real commands: tests/test_origin_scenario.py."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from labkit.checks import report_blocks, report_review_inputs
from labkit.formats.area_state import state_of
from labkit.formats.evidence import read_evidence
from labkit.formats.gate import TECHNICAL_RULE
from labkit.gates import registered_report, report_hold
from labkit.tools import protocol_fill
from protocol_fixture import C1_BLOCK, C1_PROSE, PID, completed_run, head

COMPARED = "p-00000000000c0c0c"
A0, A1 = "2026-01-01T00-00-01_a0a0", "2026-01-01T00-00-02_a1a1"
OTHER = "2026-01-01T00-00-03_0e0e"
C = "2026-01-01T00-00-05_c0c0"
P, THROUGH = "experiments/01-x/PROTOCOL-x.md", "experiments/01-x/PROTOCOL-compared.md"


def _input(origin: str | None) -> dict:
    """One `data=` entry of a run record, the output of ORIGIN (None: a
    plain input)."""
    return {
        "path": "out.jsonl",
        "sha256": "ab" * 8,
        "rows": 1,
        "origin_run": origin,
        "origin_chosen": False,
        "origin_unreadable_runs": [],
    }


class Area(unittest.TestCase):
    """The layout the block is for: PROTOCOL-x.md measures (runs A0 and
    A1, no result adopted, REPORT.md registered), PROTOCOL-compared.md
    computes run C from A0's and A1's outputs and a plain file, and has
    adopted C. A run of a third protocol id stands beside them."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.area = self.root / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        self.protocol = self.area / "PROTOCOL-x.md"
        self.compared = self.area / "PROTOCOL-compared.md"
        self.report = self.root / "REPORT.md"
        self.write_measurement()
        for run in (A0, A1):
            completed_run(self.area, run)
        completed_run(self.area, OTHER, pid="p-other")
        completed_run(self.area, C, pid=COMPARED)
        self.inputs_of_c(a=A0, plain=None, b=A1, again=A0)
        self.write_compared(result=C)

    def write_measurement(self, result: str | None = None) -> None:
        self.protocol.write_text(
            head(
                repeat_cost="low", promises=C1_BLOCK, report="REPORT.md", result=result
            )
            + C1_PROSE,
            encoding="utf-8",
        )

    def write_compared(self, result: str | None) -> None:
        self.compared.write_text(
            head(id=COMPARED, repeat_cost="low", promises=C1_BLOCK, result=result)
            + C1_PROSE,
            encoding="utf-8",
        )

    def inputs_of_c(self, **origins: str | None) -> None:
        """C's record reading one input per ORIGINS entry, in that order."""
        cfg_file = self.area / "runs" / C / "config.json"
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        cfg["data"] = {key: _input(origin) for key, origin in origins.items()}
        cfg_file.write_text(json.dumps(cfg), encoding="utf-8")

    def sources(self) -> report_hold.Sources:
        return report_hold.Sources.blank(self.root, staged=False)

    def stated(self, run_id: str = C) -> report_blocks.Through:
        return report_hold.stated_through(
            self.protocol, self.report, run_id, self.sources()
        )

    def block_text(self) -> str:
        return report_blocks.with_through("# Report\n", self.stated())


class Stated(Area):
    def test_the_statement_names_the_adopting_protocol_and_this_protocols_runs(self):
        """Each origin run bound to this protocol once, in the inputs'
        order; the plain input and no run of another protocol among them."""
        self.inputs_of_c(a=A0, plain=None, other=OTHER, b=A1, again=A0)
        self.assertEqual(
            self.stated(),
            report_blocks.Through(P, PID, THROUGH, COMPARED, C, (A0, A1)),
        )

    def refusal(self, run_id: str = C) -> str:
        with self.assertRaises(report_hold.ThroughRefused) as cm:
            self.stated(run_id)
        return str(cm.exception)

    def test_an_analysis_no_protocol_adopted_is_refused(self):
        self.write_compared(result=None)
        self.assertIn(f"no protocol of 01-x has adopted run {C}", self.refusal())
        self.assertIn("an analysis is adopted first", self.refusal())

    def test_a_run_of_its_own_is_no_analysis_it_is_reported_through(self):
        """A0 is adopted by no other protocol — and were it adopted by this
        one, its result block reports it."""
        self.assertIn(f"has adopted run {A0}", self.refusal(A0))
        self.write_measurement(result=A0)
        self.assertIn(
            f"PROTOCOL-x.md has adopted run {A0} as its own result", self.refusal()
        )

    def test_an_analysis_reading_none_of_its_runs_is_refused(self):
        self.inputs_of_c(plain=None, other=OTHER)
        self.assertIn(
            f"no input of run {C} is the output of a run of {PID}", self.refusal()
        )

    def test_a_record_that_does_not_read_is_named_not_skipped(self):
        (self.area / "runs" / A1 / "config.json").write_text("{", encoding="utf-8")
        self.assertIn("a run record does not read", self.refusal())

    def test_no_protocol_there_is_refused(self):
        with self.assertRaises(report_hold.ThroughRefused) as cm:
            report_hold.stated_through(
                self.area / "PROTOCOL-gone.md", self.report, C, self.sources()
            )
        self.assertIn("there is no protocol", str(cm.exception))


class Gap(Area):
    def gap(self, text: str):
        (block,) = report_blocks.through_blocks(text)
        return report_hold.through_gap(block, self.report, self.sources())

    def test_the_block_as_written_stands(self):
        self.assertIsNone(self.gap(self.block_text()))

    def test_a_block_edited_by_hand_is_a_stale_rendering(self):
        gap = self.gap(self.block_text().replace("reports no result", "passed"))
        assert gap is not None
        self.assertEqual(gap.rule, TECHNICAL_RULE)
        self.assertIn("differs from what the analysis run's record", gap.text)
        self.assertIn(f"--reported-through {C} --into", gap.fix or "")

    def test_the_analysis_reads_another_run_since_and_the_block_is_stale(self):
        text = self.block_text()
        self.inputs_of_c(a=A0)
        gap = self.gap(text)
        assert gap is not None
        self.assertEqual(gap.rule, TECHNICAL_RULE)

    def test_an_adoption_withdrawn_since_holds_the_block_under_lab_104(self):
        text = self.block_text()
        self.write_compared(result=None)
        gap = self.gap(text)
        assert gap is not None
        self.assertEqual(gap.rule, report_hold.LAB_104)
        self.assertIn(f"no protocol of 01-x has adopted run {C}", gap.text)

    def test_a_second_block_of_one_protocol_is_a_gap(self):
        text = self.block_text()
        twice = text + text.split("# Report\n", 1)[1]
        gaps = report_hold.through_gaps(
            self.report, report_blocks.through_blocks(twice), self.sources()
        )
        self.assertEqual(len(gaps), 1, gaps)
        self.assertIn("one block per protocol", gaps[0].text)


class RegisteredReportReleased(Area):
    def owed(self, *, review: bool = False):
        return registered_report.report_owed(
            self.protocol,
            self.protocol.read_text(encoding="utf-8"),
            None,
            self.sources(),
            review=review,
        )

    def test_without_the_block_the_hold_names_it_with_its_command(self):
        self.report.write_text("# Report\n\nmean = 0.69\n", encoding="utf-8")
        gap = self.owed()
        assert gap is not None
        self.assertIn(
            "nor the block saying its runs are reported through the adopted "
            f"analysis run {C}",
            gap.text,
        )
        self.assertIn(f"--reported-through {C} --into", gap.fix or "")
        self.assertIn("whose result block carries the numbers", gap.fix or "")

    def test_the_twin_no_adopted_analysis_names_no_such_way(self):
        self.write_compared(result=None)
        self.report.write_text("# Report\n\nmean = 0.69\n", encoding="utf-8")
        gap = self.owed()
        assert gap is not None
        self.assertNotIn("reported through", gap.text)
        self.assertNotIn("--reported-through", gap.fix or "")

    def test_the_standing_block_releases_the_report_and_owes_its_review(self):
        self.report.write_text(self.block_text(), encoding="utf-8")
        self.assertIsNone(self.owed())
        gap = self.owed(review=True)
        assert gap is not None
        self.assertIn("no clean report review", gap.text)
        self.assertNotIn("carries neither", gap.text)

    def test_a_block_that_does_not_stand_releases_nothing(self):
        self.report.write_text(self.block_text(), encoding="utf-8")
        self.write_compared(result=None)
        gap = self.owed()
        assert gap is not None
        self.assertIn("carries neither", gap.text)
        self.assertIn("its reported-through block does not stand", gap.text)

    def test_beside_an_adopted_result_of_its_own_the_block_releases_nothing(self):
        """The head adopted A0: its result block is owed, and a
        reported-through block written before says something false now."""
        self.report.write_text(self.block_text(), encoding="utf-8")
        self.write_measurement(result=A0)
        gap = registered_report.report_owed(
            self.protocol,
            self.protocol.read_text(encoding="utf-8"),
            A0,
            self.sources(),
            review=False,
        )
        assert gap is not None
        self.assertIn(f"neither the result block of run {A0}", gap.text)


class Written(Area):
    def fill(self, *args: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = protocol_fill.main([str(self.protocol), *args])
        return rc, out.getvalue() + err.getvalue()

    def test_the_command_writes_the_block_once_and_leaves_the_prose(self):
        self.report.write_text("# Report\n\nProse.\n", encoding="utf-8")
        rc, out = self.fill("--reported-through", C, "--into", str(self.report))
        self.assertEqual(rc, 0, out)
        self.assertIn("written", out)
        text = self.report.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Report\n\nProse.\n"), text)
        self.assertIn(
            f"Reported through {COMPARED}, run {C}, adopted there: runs {A0}, {A1} "
            f"of {PID} are inputs of that analysis; {PID} reports no result of "
            "its own.",
            text,
        )
        rc, out = self.fill("--reported-through", C, "--into", str(self.report))
        self.assertEqual(rc, 0, out)
        self.assertIn("unchanged", out)
        self.assertEqual(self.report.read_text(encoding="utf-8"), text)

    def test_a_statement_that_cannot_be_made_writes_nothing(self):
        self.report.write_text("# Report\n", encoding="utf-8")
        rc, out = self.fill("--reported-through", A0, "--into", str(self.report))
        self.assertEqual(rc, 2, out)
        self.assertIn("no reported-through block written", out)
        self.assertEqual(self.report.read_text(encoding="utf-8"), "# Report\n")

    def test_it_goes_with_into_only(self):
        for args in (
            ("--reported-through", C),
            ("--reported-through", C, "--into", "R.md", "--why", "x"),
            ("--reported-through", C, "--into", "R.md", "--render"),
        ):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                self.fill(*args)


class ReviewerTold(Area):
    def pieces(self, text: str) -> dict[str, str]:
        self.report.write_text(text, encoding="utf-8")
        return dict(
            report_review_inputs.review_pieces(
                self.area,
                self.report,
                text,
                self.protocol,
                self.protocol.read_text(encoding="utf-8"),
                [],
                state_of(self.area),
                read_evidence(self.area, staged=False),
            )
        )

    def test_the_reviewer_is_told_what_the_block_says_and_what_it_does_not(self):
        told = self.pieces(self.block_text())["REPORTED THROUGH"]
        self.assertIn(f"lines 3–10: {A0}, {A1} of the protocol under review", told)
        self.assertIn(f"inputs of run {C}, which {THROUGH} adopted", told)
        self.assertIn("reports no result of its own", told)

    def test_the_twin_a_report_without_the_block_reads_as_before(self):
        self.assertNotIn("REPORTED THROUGH", self.pieces("# Report\n"))


if __name__ == "__main__":
    unittest.main()
