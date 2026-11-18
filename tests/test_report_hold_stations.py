"""The report holds' branches no other test reached, as gate tests: what
`report_hold` makes of a block that does not read, a discussion of no
protocol, a review that cannot be told, a run whose protocol's head does
not read, and a replacement hint — each one finding with its way out."""

from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.checks import report_blocks
from labkit.checks.audit_binding import AuditError
from labkit.checks.report_review_inputs import review_keys
from labkit.formats import report_reviews
from labkit.formats.gate import BLOCKER, TECHNICAL_RULE
from labkit.gates import report_hold
from protocol_fixture import head
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
                TECHNICAL_RULE,
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
        self.assertEqual(gap.rule, TECHNICAL_RULE)

    def test_at_the_commit_a_decision_counts_only_with_its_confirmation_staged(self):
        """What the commit adds to the release of a decided claim: the
        review and the claim review that upholds its decision count only
        when the index holds their records — a confirmation left unstaged
        releases nothing the commit carries."""
        folder = self.area / "audits" / "report-reviews"
        claim = report_reviews.ReportClaim(
            3, "result", "reads as a result", "false-positive", "inside the block"
        )
        review = report_reviews.ReportReview(
            folder / "2026-11-12T10-00-review.toml",
            "2026-11-12T10:00",
            "m",
            *review_keys(self.area, self.report, self.area / "PROTOCOL-x.md"),
            "",
            {},
            False,
            (claim,),
        )
        confirmation = report_reviews.ClaimReview(
            folder / "2026-11-12T10-30-claim-review.toml",
            "2026-11-12T10:30",
            "m",
            review.path.name,
            "",
            False,
            (
                report_reviews.ClaimVerdict(
                    1, report_reviews.claim_decision_digest(claim), "upheld", "so"
                ),
            ),
        )

        def gap(indexed: list[Path]):
            held = dataclasses.replace(
                area_evidence(),
                report_reviews=(review,),
                claim_reviews=(confirmation,),
            )
            sources = report_hold.Sources.blank(
                self.repo,
                staged=True,
                states={self.area: area_state(area=self.area)},
                held={self.area: held},
            )
            with (
                mock.patch.object(report_hold, "staged_area_gap", return_value=None),
                mock.patch.object(report_hold, "review_pieces", return_value=[]),
                mock.patch.object(
                    report_hold, "review_fingerprint", return_value=("", {})
                ),
                mock.patch.object(report_hold, "indexed_files", return_value=indexed),
            ):
                return report_hold.review_gap(
                    self.report,
                    "REPORT.md",
                    "",
                    self.area / "PROTOCOL-x.md",
                    "",
                    [],
                    "owed",
                    sources,
                )

        self.assertIsNone(gap([review.path, confirmation.path]))
        unconfirmed = gap([review.path])
        assert unconfirmed is not None
        self.assertIn("not yet judged by a second reviewer", unconfirmed.text)
        unreviewed = gap([confirmation.path])
        assert unreviewed is not None
        self.assertIn("has no clean report review of this state", unreviewed.text)

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


RUN = "2026-10-07T10-00-00_ab12"


class AnAdoptionOutsideTheIndex(unittest.TestCase):
    """The run the working tree's head has adopted and the index's has not
    (`report_hold.adoption_outside_index`), read from the two texts: the
    commit's step (`result_outside_index`) and a report block's source
    (`_undeclared_source`) ask it alike. A `[result]` that does not read
    adopts nothing in either state and raises at neither site."""

    PLAIN = head(repeat_cost="low")
    ADOPTED = head(repeat_cost="low", result=RUN)
    TYPED = head(repeat_cost="low", result="typed")  # no run id runlog writes

    def setUp(self) -> None:
        self.repo = Path("/repo")
        self.area = self.repo / "experiments" / "01-x"
        self.protocol = self.area / "PROTOCOL-x.md"

    def both(self, tree: str | None, index: str | None) -> tuple[bool, str | None]:
        """(the commit's step sees a result outside the index, the run a
        block's source names as adopted in the tree) for the protocol's text
        in the TREE and in the INDEX, no run outside the index."""

        def state_text(repo: Path, path: Path, *, staged: bool) -> str | None:
            self.assertEqual((repo, path), (self.repo, self.protocol))
            return index if staged else tree

        sources = report_hold.Sources(self.repo, set(), {}, {}, {}, staged=True)
        with (
            mock.patch.object(report_hold, "state_text", state_text),
            mock.patch.object(report_hold, "runs_outside_index", return_value={}),
        ):
            outside = report_hold.result_outside_index(
                self.repo, self.area, self.protocol
            )
            source = report_hold._undeclared_source(self.protocol, sources)  # noqa: SLF001
            self.assertEqual(
                report_hold.adoption_outside_index(self.repo, self.protocol),
                source.tree_run,
            )
        return outside, source.tree_run

    def test_adopted_in_the_tree_only(self):
        self.assertEqual(self.both(self.ADOPTED, self.PLAIN), (True, RUN))
        # the index does not hold the protocol: its adoption is outside too
        self.assertEqual(self.both(self.ADOPTED, None), (True, RUN))

    def test_a_result_that_does_not_read_in_the_tree_adopts_nothing(self):
        self.assertEqual(self.both(self.TYPED, self.PLAIN), (False, None))

    def test_a_result_that_does_not_read_in_the_index_is_none_adopted_there(self):
        self.assertEqual(self.both(self.ADOPTED, self.TYPED), (True, RUN))

    def test_the_twins_nothing_outside(self):
        for name, tree, index in (
            ("adopted in both", self.ADOPTED, self.ADOPTED),
            ("adopted in neither", self.PLAIN, self.PLAIN),
            ("no file in the tree", None, self.PLAIN),
        ):
            with self.subTest(name):
                self.assertEqual(self.both(tree, index), (False, None))


class TheRuleAReviewHoldRecords(unittest.TestCase):
    """`review_hold`: which of its three causes holds the report decides the
    rule — lost evidence the technical contract, a named claim the rule
    whose text states that no further draw releases it, no clean review the
    rule that owes the review."""

    PROTOCOL = Path("experiments/01-x/PROTOCOL-x.md")

    def _review(
        self, *claims: report_reviews.ReportClaim
    ) -> report_reviews.ReportReview:
        return report_reviews.ReportReview(
            path=Path("audits/report-reviews/r1.toml"),
            date="2026-11-11",
            model="m",
            report="REPORT.md",
            protocol="PROTOCOL-x.md",
            fingerprint="aa",
            parts={"REPORT REPORT.md": "aa"},
            again=False,
            claims=claims,
        )

    def _hold(self, reviews: list, *, gaps: tuple[str, ...] = ()):
        stands = report_reviews.standing(
            reviews, "REPORT.md", "PROTOCOL-x.md", "aa", []
        )
        self.assertFalse(stands.released)
        return report_hold.review_hold(
            "REPORT.md",
            self.PROTOCOL,
            "discusses r1 as not reported",
            stands,
            {"REPORT REPORT.md": "aa"},
            "`labkit-audit --report-review`",
            area_evidence(gaps=gaps),
            "change the report, or decide the claim",
        )

    CLAIM = report_reviews.ReportClaim(
        3, report_reviews.CLAIM_KINDS[0], "reads as a result"
    )

    def test_a_named_claim_records_the_rule_that_states_no_draw_releases_it(self):
        f = self._hold([self._review(self.CLAIM)])
        self.assertEqual((f.grade, f.rule), (BLOCKER, report_hold.LAB_015))
        self.assertIn("the report review holds this state", f.text)
        self.assertIn("line 3", f.text)

    def test_no_review_of_this_state_records_the_rule_that_owes_it(self):
        f = self._hold([])
        self.assertEqual((f.grade, f.rule), (BLOCKER, report_hold.LAB_104))
        self.assertIn("has no clean report review of this state", f.text)

    def test_lost_evidence_comes_first_and_is_the_technical_contract(self):
        f = self._hold([self._review(self.CLAIM)], gaps=("audits/a.toml is gone",))
        self.assertEqual((f.grade, f.rule), (BLOCKER, TECHNICAL_RULE))
        self.assertIn("none can run", f.text)
