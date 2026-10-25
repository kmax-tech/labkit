"""finalize station 5 (2026-10-05): a c<i>_n that matches no recorded input
count is a warning, never a blocker."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol_fixture import run_record  # noqa: E402
from labkit.checks import run_record_check  # noqa: E402


class CriterionN(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self._tmp.name) / "runs" / "r1"
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "config.json").write_text(
            json.dumps(
                run_record(
                    {
                        "schema_version": 4,
                        "run_kind": "measurement",
                        "data": {
                            "items": {
                                "path": "/x/items.jsonl",
                                "rows": 12,
                                "sha256": "ab",
                            }
                        },
                    }
                )
            )
        )
        (self.run_dir / "outputs.json").write_text(
            json.dumps([{"path": "/x/out.jsonl", "sha256": "cd", "lines": 12}])
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _metrics(self, m: dict) -> None:
        (self.run_dir / "metrics.json").write_text(json.dumps(m))

    def test_matching_n_is_silent(self):
        self._metrics({"c1_pass": True, "c1_n": 12})
        self.assertEqual(
            run_record_check.criterion_n_input_mismatches(self.run_dir), []
        )

    def test_shrunk_denominator_warns(self):
        # 2026-10-06 review: c1_n = 7 against 12 recorded rows went unwarned
        # while the check knew only the old letter
        self._metrics({"c1_pass": True, "c1_n": 7})
        w = run_record_check.criterion_n_input_mismatches(self.run_dir)
        self.assertEqual(len(w), 1)
        self.assertIn("c1_n = 7", w[0])
        self.assertIn("rows = 12", w[0])

    def test_admissibility_n_is_not_a_criterion_denominator(self):
        self._metrics({"a1_ok": True, "a1_n": 3})
        self.assertEqual(
            run_record_check.criterion_n_input_mismatches(self.run_dir), []
        )

    def test_no_n_keys_nothing_to_say(self):
        self._metrics({"c1_pass": True})
        self.assertEqual(
            run_record_check.criterion_n_input_mismatches(self.run_dir), []
        )


if __name__ == "__main__":
    unittest.main()
