"""Rule test of what a second reviewer's draws release
(`reviews.released_by`, `reviews.first_not_upheld`, `reviews.counts_of`):
the one rule a decision on a finding (`reviews.upholding`) and a decision
on a report claim (`report_reviews.upheld`) are released by — from draws
in memory, each violation and the valid twin (docs/architecture.md,
"Checks and their tests"). That no second spelling of it stands in the
package: `tests/test_one_home.py`.
"""

from __future__ import annotations

import unittest

import pytest

from labkit.formats import report_reviews, reviews
from labkit.formats.reviews import INSUFFICIENT, REJECTED, UPHELD

pytestmark = pytest.mark.rule

FIRST, AGAIN = False, True


class WhatDrawsRelease(unittest.TestCase):
    def test_no_draw_releases_nothing(self):
        self.assertFalse(reviews.released_by([]))

    def test_an_again_draws_upheld_alone_releases_nothing(self):
        self.assertFalse(reviews.released_by([(AGAIN, UPHELD)]))
        self.assertFalse(reviews.released_by([(AGAIN, UPHELD), (AGAIN, UPHELD)]))

    def test_one_draw_not_upheld_among_upheld_releases_nothing(self):
        for verdict in (REJECTED, INSUFFICIENT):
            with self.subTest(verdict):
                draws = [(FIRST, UPHELD), (FIRST, verdict), (FIRST, UPHELD)]
                self.assertFalse(reviews.released_by(draws))

    def test_a_later_upheld_does_not_outvote(self):
        self.assertFalse(reviews.released_by([(FIRST, REJECTED), (FIRST, UPHELD)]))
        self.assertFalse(reviews.released_by([(FIRST, REJECTED), (AGAIN, UPHELD)]))

    def test_an_again_draw_not_upheld_holds_what_another_draw_upheld(self):
        self.assertFalse(reviews.released_by([(FIRST, UPHELD), (AGAIN, REJECTED)]))

    def test_the_twin_all_upheld_with_one_draw_that_is_no_again_draw_releases(self):
        self.assertTrue(reviews.released_by([(FIRST, UPHELD)]))
        self.assertTrue(reviews.released_by([(AGAIN, UPHELD), (FIRST, UPHELD)]))
        self.assertTrue(reviews.released_by([(FIRST, UPHELD), (AGAIN, UPHELD)]))


class WhichDrawContests(unittest.TestCase):
    def test_the_first_draw_that_did_not_uphold_is_named(self):
        verdicts = [UPHELD, INSUFFICIENT, REJECTED]
        self.assertEqual(reviews.first_not_upheld(verdicts), 1)

    def test_the_twin_draws_all_upheld_and_no_draw_name_none(self):
        self.assertIsNone(reviews.first_not_upheld([UPHELD, UPHELD]))
        self.assertIsNone(reviews.first_not_upheld([]))


class TheCountsOfVerdicts(unittest.TestCase):
    def test_each_verdict_is_counted_in_the_order_of_the_file(self):
        judged = [
            reviews.Decision(n, "sha", verdict, "why")
            for n, verdict in enumerate((REJECTED, UPHELD, REJECTED), start=1)
        ]
        self.assertEqual(reviews.counts_of(judged), (1, 2, 0))
        self.assertEqual(reviews.counts_of([]), (0, 0, 0))

    def test_a_claims_verdicts_are_counted_by_the_same_function(self):
        verdicts = [
            report_reviews.ClaimVerdict(1, "sha", INSUFFICIENT, "why"),
            report_reviews.ClaimVerdict(2, "sha", UPHELD, "why"),
        ]
        self.assertEqual(reviews.counts_of(verdicts), (1, 0, 1))


if __name__ == "__main__":
    unittest.main()
