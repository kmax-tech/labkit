"""The null lane moved — held over the run's kept rows, not in the script.

A cold agent deleted the estimator skeleton's own guard ("the null lane
predicts what the registered lane predicts on every item") before it first
ran (SAB-like apply case, 2026-10-27). finalize reads the rows the run
registered as its output and blocks a null lane that answers what the
registered lane answers on every item, gold included: such a null measures
no noise floor (LAB-034 Null condition in the same run). A fitted null that
predicts otherwise, or a local apply's null on permuted gold (`gold_of`),
moved.

    .venv/bin/python -m pytest tests/test_null_lane.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from labkit.checks import run_record_check
from labkit.formats.runs import OUTPUTS_FILE


def rows(null_pred, null_gold=None) -> list[dict]:
    """Two lanes over four items; the null lane's answer and gold as given."""
    gold = [0, 1, 0, 1]
    out = [
        {"lane": "registered", "item": str(i), "pred": g, "gold": g}
        for i, g in enumerate(gold)
    ]
    for i, g in enumerate(gold):
        out.append(
            {
                "lane": "null",
                "item": str(i),
                "pred": null_pred(i, g),
                "gold": g if null_gold is None else null_gold(i, g),
            }
        )
    return out


class NullLane(unittest.TestCase):
    def test_a_null_that_answers_the_registered_lane_did_not_move(self):
        self.assertTrue(run_record_check.null_lane_unmoved(rows(lambda i, g: g)))

    def test_a_fitted_null_that_predicts_otherwise_moved(self):
        self.assertFalse(run_record_check.null_lane_unmoved(rows(lambda i, g: 0)))

    def test_a_null_on_permuted_gold_moved(self):
        # the local apply's null: the same predictions, the gold permuted
        permuted = rows(lambda i, g: g, null_gold=lambda i, g: 1 - g)
        self.assertFalse(run_record_check.null_lane_unmoved(permuted))

    def test_rows_without_two_lanes_say_nothing(self):
        self.assertFalse(run_record_check.null_lane_unmoved([{"item": "1", "n": 3}]))

    def test_the_run_record_is_read_through_its_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "runs" / "2026-10-27T10-00-00_ab12"
            run.mkdir(parents=True)
            out = Path(d) / "output" / "rows.jsonl"
            out.parent.mkdir()
            kept = rows(lambda i, g: g)
            out.write_text("".join(json.dumps(r) + "\n" for r in kept))
            (run / OUTPUTS_FILE).write_text(
                json.dumps([{"path": str(out), "sha256": None, "lines": len(kept)}])
            )
            (line,) = run_record_check.null_lane_findings(run)
            self.assertIn(
                "rows.jsonl: the null lane answers what the registered", line.text
            )
            self.assertIn("permuted gold", line.fix or "")
            out.write_text("".join(json.dumps(r) + "\n" for r in rows(lambda i, g: 0)))
            self.assertEqual(run_record_check.null_lane_findings(run), [])


if __name__ == "__main__":
    unittest.main()
