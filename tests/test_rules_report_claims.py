"""Rule tests of the decisions on a report review's claims
(`formats/report_reviews`, `formats/evidence`): which decision a claim
takes, what a decision is bound to, what releases a state, and which
change of a review record breaks no evidence rule — each condition from
records in memory, its violation and its valid twin (docs/architecture.md,
"Checks and their tests"). The commands that compose them are tested in
`tests/test_claim_review.py`.
"""

from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path

import pytest

from labkit.formats import evidence, report_reviews
from labkit.formats.report_reviews import (
    CONTRADICTION,
    FALSE_POSITIVE,
    RESULT,
    ClaimReview,
    ClaimVerdict,
    ReportClaim,
    ReportReview,
)

pytestmark = pytest.mark.rule

P = "experiments/01-x/PROTOCOL-x.md"
RECORD = "2026-11-12T10-00-review.toml"
OPEN = ReportClaim(11, RESULT, "AUROC of a discussed run in the summary")
DECIDED = dataclasses.replace(
    OPEN, status=FALSE_POSITIVE, reason="line 11 lies inside the discussion block"
)


def review(*claims: ReportClaim, name: str = RECORD, again: bool = False):
    return ReportReview(
        Path(f"audits/report-reviews/{name}"),
        "2026-11-12T10:00",
        "m",
        "REPORT.md",
        P,
        "f1",
        {"REPORT REPORT.md": "d1"},
        again,
        claims,
    )


def claim_review(
    of: ReportReview,
    verdict: str,
    *,
    n: int = 1,
    name: str = "2026-11-12T10-30-claim-review.toml",
    again: bool = False,
    decision_sha: str | None = None,
    fingerprint: str | None = None,
) -> ClaimReview:
    """A claim review of OF's claim N as it is decided, saying VERDICT."""
    sha = decision_sha or report_reviews.claim_decision_digest(of.claims[n - 1])
    return ClaimReview(
        Path(f"audits/report-reviews/{name}"),
        "2026-11-12T10:30",
        "m",
        of.path.name,
        fingerprint or of.fingerprint,
        again,
        (ClaimVerdict(n, sha, verdict, "the reviewer's sentence"),),
    )


def stands(reviews: list[ReportReview], confirmed: list[ClaimReview]):
    return report_reviews.standing(reviews, "REPORT.md", P, "f1", confirmed)


class WhichDecisionAClaimTakes(unittest.TestCase):
    def test_a_limitation_is_refused_on_either_kind_each_with_its_sentence(self):
        on_result = report_reviews.claim_refusal(RESULT, "limitation")
        on_contradiction = report_reviews.claim_refusal(CONTRADICTION, "limitation")
        assert on_result is not None and on_contradiction is not None
        self.assertIn("LAB-104 A number leaves the area only through its", on_result)
        self.assertIn("does not make the statement true", on_contradiction)

    def test_fixed_is_refused_naming_the_review_of_the_repaired_state(self):
        for kind in report_reviews.CLAIM_KINDS:
            refused = report_reviews.claim_refusal(kind, "fixed")
            assert refused is not None
            self.assertIn("review the repaired state", refused)

    def test_the_twin_open_and_false_positive_are_taken(self):
        for kind in report_reviews.CLAIM_KINDS:
            for status in report_reviews.CLAIM_STATUSES:
                self.assertIsNone(report_reviews.claim_refusal(kind, status))
        self.assertIsNone(
            report_reviews.claim_status_problem(RESULT, FALSE_POSITIVE, "line 11")
        )

    def test_a_false_positive_owes_its_reason_and_an_unknown_status_is_named(self):
        self.assertIn(
            "owes a reason",
            report_reviews.claim_status_problem(RESULT, FALSE_POSITIVE, "  ") or "",
        )
        self.assertIn(
            "one of open, false-positive",
            report_reviews.claim_status_problem(RESULT, "settled", "x") or "",
        )
        self.assertIn(
            "no limitation",
            report_reviews.claim_status_problem(RESULT, "limitation", "x") or "",
        )


class WhatADecisionIsBoundTo(unittest.TestCase):
    def test_a_changed_reason_is_another_decision(self):
        revised = dataclasses.replace(DECIDED, reason="the heading marks it")
        digest = report_reviews.claim_decision_digest
        self.assertNotEqual(digest(DECIDED), digest(revised))
        self.assertEqual(digest(DECIDED), digest(dataclasses.replace(DECIDED)))

    def test_a_verdict_on_another_record_or_another_state_says_nothing(self):
        r = review(DECIDED)
        other_record = claim_review(review(DECIDED, name="other-review.toml"), "upheld")
        other_state = claim_review(r, "upheld", fingerprint="f0")
        self.assertFalse(report_reviews.upheld(r, 1, [other_record, other_state]))
        self.assertTrue(report_reviews.upheld(r, 1, [claim_review(r, "upheld")]))


class WhatReleasesAState(unittest.TestCase):
    def test_an_open_claim_holds_and_a_clean_draw_does_not_outvote_it(self):
        held = stands([review(OPEN), review(name="2026-11-12T10-05-review.toml")], [])
        self.assertFalse(held.released)
        self.assertEqual([(h.n, h.state) for h in held.holding], [(1, "open")])

    def test_a_decision_alone_releases_nothing(self):
        held = stands([review(DECIDED)], [])
        self.assertFalse(held.released)
        self.assertIn("not yet judged by a second reviewer", held.holding[0].state)

    def test_a_decision_upheld_releases_and_its_twin_rejected_holds(self):
        r = review(DECIDED)
        self.assertTrue(stands([r], [claim_review(r, "upheld")]).released)
        for verdict in ("rejected", "insufficient"):
            held = stands([r], [claim_review(r, verdict)])
            self.assertFalse(held.released)
            self.assertIn(f"{verdict} by the second reviewer", held.holding[0].state)

    def test_no_further_draw_releases_a_decision_once_not_upheld(self):
        r = review(DECIDED)
        draws = [
            claim_review(r, "rejected"),
            claim_review(r, "upheld", name="2026-11-12T10-40-claim-review.toml"),
        ]
        self.assertFalse(stands([r], draws).released)
        self.assertIsNotNone(report_reviews.not_upheld(r, 1, draws))

    def test_an_again_draws_upheld_alone_releases_nothing(self):
        r = review(DECIDED)
        only_again = [claim_review(r, "upheld", again=True)]
        held = stands([r], only_again)
        self.assertFalse(held.released)
        self.assertIn("only by `--again` draws", held.holding[0].state)
        with_one = [*only_again, claim_review(r, "upheld", name="b-claim-review.toml")]
        self.assertTrue(stands([r], with_one).released)

    def test_a_revised_reason_owes_its_own_confirmation_and_names_the_rejection(self):
        rejected = claim_review(review(DECIDED), "rejected")
        revised = review(
            dataclasses.replace(DECIDED, reason="lines 9–13 are the discussion block")
        )
        held = stands([revised], [rejected])
        self.assertFalse(held.released)
        self.assertIn("not yet judged", held.holding[0].state)
        self.assertIn(
            f"an earlier decision on it was rejected ({rejected.path.name})",
            held.holding[0].state,
        )
        confirmed = claim_review(
            revised, "upheld", name="2026-11-12T11-00-claim-review.toml"
        )
        self.assertTrue(stands([revised], [rejected, confirmed]).released)

    def test_an_again_draws_claim_holds_a_state_another_review_released(self):
        clean = review()
        again = review(OPEN, name="2026-11-12T10-05-review.toml", again=True)
        self.assertTrue(stands([clean], []).released)
        held = stands([clean, again], [])
        self.assertFalse(held.released)
        self.assertEqual(held.holding[0].review, again)

    def test_every_claim_of_the_state_must_be_released(self):
        second = ReportClaim(14, CONTRADICTION, "says met, the record says not met")
        r = review(DECIDED, second)
        held = stands([r], [claim_review(r, "upheld")])
        self.assertEqual([h.n for h in held.holding], [2])

    def test_the_sentence_names_record_number_line_kind_and_state(self):
        told = report_reviews.held_by(stands([review(OPEN)], []))
        self.assertEqual(
            told,
            f"CLAIM #1 in {RECORD}, line 11 (result): AUROC of a discussed run in "
            f"the summary — open",
        )


RECORD_TEXT = """[report_review]
date = "2026-11-12T10:00"
model = "m"
report = "REPORT.md"
protocol = "experiments/01-x/PROTOCOL-x.md"
fingerprint = "f1"
again = false
claims = 1

[report_review.parts]
"REPORT REPORT.md" = "d1"

[[claim]]
line = 11
kind = "result"
why = "AUROC of a discussed run"
status = "open"
reason = ""
"""
UNDECIDED_FORMAT = RECORD_TEXT.replace('status = "open"\nreason = ""\n', "")
REVIEW_REL = f"audits/report-reviews/{RECORD}"
ASIDE_REL = f"audits/report-reviews/superseded/{RECORD}"


class WhichChangeOfAReviewRecordBreaksItsRule(unittest.TestCase):
    """`evidence.broken` on a report review: its claims' decision lines may
    change, nothing else; a record of the format without decisions may
    move into the folder of superseded reviews, no other may."""

    def broken(self, entries, before: str, after: str | None, *, deletions=True):
        audits, _ = evidence.broken(
            entries,
            set(),
            lambda rel: (before, after),
            lambda rel: False,
            deletions=deletions,
        )
        return audits

    def test_a_decision_on_a_claim_changes_no_evidence(self):
        decided = RECORD_TEXT.replace(
            'status = "open"\nreason = ""',
            'status = "false-positive"\nreason = "inside the block"',
        )
        self.assertEqual(self.broken([("M", REVIEW_REL)], RECORD_TEXT, decided), [])

    def test_the_twin_a_changed_claim_is_named(self):
        rewritten = RECORD_TEXT.replace("line = 11", "line = 12")
        self.assertEqual(
            self.broken([("M", REVIEW_REL)], RECORD_TEXT, rewritten),
            [(REVIEW_REL, "report review")],
        )

    def test_a_changed_claim_review_is_named_whole(self):
        rel = "audits/report-reviews/2026-11-12T10-30-claim-review.toml"
        self.assertFalse(evidence.is_report_review(rel))
        self.assertEqual(self.broken([("M", rel)], "a", "b"), [(rel, "changed")])

    def test_a_record_without_decisions_moved_aside_is_not_deleted(self):
        moved = [("D", REVIEW_REL), ("A", ASIDE_REL)]
        self.assertEqual(self.broken(moved, UNDECIDED_FORMAT, None), [])

    def test_the_twin_a_record_that_reads_moved_aside_is_deleted(self):
        moved = [("D", REVIEW_REL), ("A", ASIDE_REL)]
        self.assertEqual(
            self.broken(moved, RECORD_TEXT, None), [(REVIEW_REL, "deleted")]
        )

    def test_a_record_without_decisions_deleted_outright_is_deleted(self):
        self.assertEqual(
            self.broken([("D", REVIEW_REL)], UNDECIDED_FORMAT, None),
            [(REVIEW_REL, "deleted")],
        )

    def test_the_format_without_decisions_is_told_from_one_that_reads(self):
        self.assertTrue(report_reviews.is_undecided_format(UNDECIDED_FORMAT))
        self.assertFalse(report_reviews.is_undecided_format(RECORD_TEXT))
        # a review that named no claim reads in either format: it stays
        clean = RECORD_TEXT.split("[[claim]]")[0].replace("claims = 1", "claims = 0")
        self.assertFalse(report_reviews.is_undecided_format(clean))
        self.assertFalse(report_reviews.is_undecided_format("not = [toml"))

    def test_only_the_folder_of_superseded_reviews_names_a_place_moved_from(self):
        name = report_reviews.superseded_name
        self.assertEqual(
            name(f"report-reviews/superseded/{RECORD}"), f"report-reviews/{RECORD}"
        )
        self.assertIsNone(name(f"report-reviews/{RECORD}"))
        self.assertIsNone(name(f"superseded/{RECORD}"))


if __name__ == "__main__":
    unittest.main()
