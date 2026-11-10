"""Rule tests of `run_record_check`'s pure checks: each condition from typed
data in memory, its violation and its valid twin (docs/notes/2026-11-10-test-model.md,
"The model"). The gate that composes them is finalize
(`tests/test_finalize_steps.py` for its stations).
"""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest

from check_guards import pure_call
from labkit.checks.run_record_check import (
    criterion_n_input_mismatches,
    criterion_ns,
    null_lane_findings,
)
from labkit.formats.gate import (
    KNOWN_RULE,
    OPEN_RULE,
    STATIC_EVIDENCE,
    WARNING,
    RuleAssignment,
)
from labkit.formats.runs import DataEntry, KeptRows, OutputEntry

pytestmark = pytest.mark.rule

ITEMS = DataEntry("items", "data/items.jsonl", "ab", 12)
ROWS = OutputEntry(Path("out.jsonl"), "cd", 12)


class ACriterionDenominatorIsAnInputCount(unittest.TestCase):
    """A `criterion_<i>_n` that matches no input count the run recorded is a
    warning, never a blocker (`criterion_n_input_mismatches`)."""

    def _held(self, metrics: dict[str, object], inputs=(ITEMS,), outputs=(ROWS,)):
        return pure_call(
            criterion_n_input_mismatches,
            pure_call(criterion_ns, metrics),
            list(inputs),
            list(outputs),
        )

    def test_a_shrunk_denominator_warns_naming_the_counts(self):
        # criterion_1_n = 7 against 12 recorded rows: the denominator shrank
        (f,) = self._held({"criterion_1_pass": True, "criterion_1_n": 7})
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (WARNING, STATIC_EVIDENCE, OPEN_RULE)
        )
        self.assertIn("criterion_1_n = 7", f.text)
        self.assertIn("data[items].rows = 12", f.text)
        self.assertIn("out.jsonl lines = 12", f.text)

    def test_a_denominator_without_any_recorded_count_warns(self):
        (f,) = self._held({"criterion_1_n": 12}, inputs=(), outputs=())
        self.assertIn(
            "criterion_1_n present, but the run recorded no input count", f.text
        )

    def test_the_twin_a_matching_denominator_passes(self):
        self.assertEqual(
            self._held({"criterion_1_pass": True, "criterion_1_n": 12}), []
        )

    def test_no_denominator_nothing_to_hold(self):
        self.assertEqual(self._held({"criterion_1_pass": True}), [])
        # an admissibility count is no criterion denominator
        self.assertEqual(self._held({"quality_check_1_n": 3}), [])

    def test_a_bool_is_no_count(self):
        self.assertEqual(pure_call(criterion_ns, {"criterion_1_n": True}), {})
        self.assertEqual(
            pure_call(criterion_ns, {"criterion_1_n": 12}), {"criterion_1_n": 12}
        )


def _lanes(null_pred) -> list[dict[str, object]]:
    """Two lanes over four items; the null lane's answer as given, gold kept."""
    gold = [0, 1, 0, 1]
    return [
        {"lane": "registered", "item": str(i), "pred": g, "gold": g}
        for i, g in enumerate(gold)
    ] + [
        {"lane": "null", "item": str(i), "pred": null_pred(g), "gold": g}
        for i, g in enumerate(gold)
    ]


class TheNullLaneMoved(unittest.TestCase):
    """LAB-034 Null condition in the same run: a kept output whose null lane
    answers what the registered lane answers on every item measures no noise
    floor — a warning, static evidence (`null_lane_findings`)."""

    AREA = Path("area")

    def _held(self, rows: list[dict[str, object]]):
        kept = [KeptRows(OutputEntry(Path("out/rows.jsonl"), None, len(rows)), rows)]
        return pure_call(null_lane_findings, kept, self.AREA)

    def test_an_unmoved_null_lane_warns(self):
        held = self._held(_lanes(lambda g: g))
        self.assertEqual(held.examined, 1)
        (f,) = held.unmoved
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule),
            (
                WARNING,
                STATIC_EVIDENCE,
                RuleAssignment(KNOWN_RULE, "LAB-034", "Null condition in the same run"),
            ),
        )
        self.assertTrue(
            f.text.startswith("rows.jsonl: the null lane's answer and gold equal")
        )
        self.assertIn("permuted gold", f.fix or "")

    def test_the_twin_a_moved_null_lane_passes(self):
        held = self._held(_lanes(lambda g: 0))
        self.assertEqual((held.examined, held.unmoved), (1, []))

    def test_an_output_without_both_lanes_is_not_examined(self):
        held = self._held([{"item": "1", "n": 3}])
        self.assertEqual((held.examined, held.unmoved), (0, []))


if __name__ == "__main__":
    unittest.main()
