"""The report holds' branches no other test reached, as gate tests: what
`report_hold` makes of a block that does not read, a discussion of no
protocol, a review that cannot be told, a run whose protocol's head does
not read, and a replacement hint — each one finding with its way out."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.checks import report_blocks
from labkit.checks.audit_binding import AuditError
from labkit.formats.gate import BLOCKER, OPEN_RULE, cited_rule
from labkit.gates import report_hold
from state_fixture import area_evidence, area_state


class AReportHold(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name).resolve()
        self.report = self.repo / "REPORT.md"
        self.area = self.repo / "experiments" / "01-x"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _sources(self, known: set[str] | None = None) -> report_hold.Sources:
        """Sources of the tree knowing the run ids KNOWN, nothing else."""
        return report_hold.Sources(self.repo, known or set(), {}, {}, {})

    def _hold(self, text: str) -> tuple[int, list[str]]:
        told: list[str] = []
        code = report_hold.hold_report(
            self.report, text, self.repo, self._sources(), tell=told.append
        )
        return code, told

    def test_a_block_that_does_not_read_is_held_alone(self):
        code, told = self._hold(report_blocks.CLOSE + "\n")
        self.assertEqual(code, 1)
        self.assertTrue(
            any(
                "REPORT.md: line 1:" in t and "closes no result block" in t
                for t in told
            ),
            told,
        )

    def test_a_replacement_hint_is_told_as_a_warning(self):
        with mock.patch.object(
            report_hold, "replacement_hints", return_value=["a hint"]
        ):
            code, told = self._hold("# Report\n")
        self.assertEqual(code, 0)
        self.assertTrue(
            any(t.strip().startswith("WARNING") and "a hint" in t for t in told), told
        )

    def test_a_discussion_of_no_protocol_blocks(self):
        found = [
            report_blocks.Discussion(
                "experiments/01-x/PROTOCOL-x.md", "r1", "why", 1, 3, ""
            )
        ]
        (gap,) = report_hold.discussion_sources(self.report, found, self._sources())
        self.assertEqual(
            (gap.grade, gap.rule),
            (
                BLOCKER,
                cited_rule(
                    "LAB-104 A number leaves the area only through its adoption"
                ),
            ),
        )
        self.assertIn(
            "names experiments/01-x/PROTOCOL-x.md, and there is no such protocol",
            gap.text,
        )

    def test_a_review_that_cannot_be_told_blocks_naming_why(self):
        sources = report_hold.Sources.blank(
            self.repo,
            staged=False,
            states={self.area: area_state(area=self.area)},
            held={self.area: area_evidence()},
        )
        with mock.patch.object(
            report_hold,
            "review_pieces",
            side_effect=AuditError("an output is gone", fix=None),
        ):
            gap = report_hold.review_gap(
                self.report,
                "REPORT.md",
                "",
                self.area / "PROTOCOL-x.md",
                "",
                [],
                "owed",
                sources,
            )
        assert gap is not None
        self.assertEqual(
            gap.text, "REPORT.md: its report review cannot be told — an output is gone"
        )
        self.assertEqual(gap.rule, OPEN_RULE)

    def test_a_run_of_a_protocol_whose_head_does_not_read_blocks(self):
        sources = self._sources(known={"r1"})
        with mock.patch.object(
            report_hold,
            "promotions",
            side_effect=AuditError("PROTOCOL-x.md: no head", fix=None),
        ):
            (gap,) = report_hold.undeclared_findings(
                self.report, "REPORT.md", [(3, "r1")], [], sources
            )
        self.assertEqual(
            gap.text,
            "REPORT.md: cites a run of a protocol whose head does not read — PROTOCOL-x.md: no head",
        )
        self.assertIn("--contract", gap.fix or "")


if __name__ == "__main__":
    unittest.main()
