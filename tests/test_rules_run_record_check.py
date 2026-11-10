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
from labkit.checks.run_record_check import criterion_n_input_mismatches, criterion_ns
from labkit.formats.gate import OPEN_RULE, STATIC_EVIDENCE, WARNING
from labkit.formats.runs import DataEntry, OutputEntry

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


if __name__ == "__main__":
    unittest.main()
