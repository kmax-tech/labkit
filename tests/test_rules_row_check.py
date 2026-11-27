"""Rule tests of `row_check`'s pure checks: each condition from typed data in
memory, its violation and its valid twin (docs/architecture.md, "Checks and
their tests"). The gate that composes them is finalize
(`tests/test_finalize_steps.py` for its stations); row provenance reads run
folders and is tested in `tests/test_row_provenance.py`.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest

from check_guards import pure_call
from labkit.checks.row_check import null_lane_findings
from labkit.formats.gate import (
    KNOWN_RULE,
    STATIC_EVIDENCE,
    WARNING,
    RuleAssignment,
)
from labkit.formats.runs import KeptRows, OutputEntry

pytestmark = pytest.mark.rule


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
