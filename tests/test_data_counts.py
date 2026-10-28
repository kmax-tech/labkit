"""The counts of a preparation run as Data / scope carries them
(`labkit.checks.data_counts`): counted from the items, rendered from the
run's record, written as the field's end, held to the run.

    .venv/bin/python -m pytest tests/test_data_counts.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import run_record  # noqa: E402
from labkit.checks import data_counts

RUN = "2026-01-01T00-00-00_0001"


class Counts(unittest.TestCase):
    def test_labelled_unlabelled_and_per_gold_value(self):
        items = [{"gold": "a"}, {"gold": "b"}, {"gold": "a"}, {"gold": None}]
        self.assertEqual(
            data_counts.item_counts(items),
            {
                "n_items": 4,
                "n_labelled": 3,
                "n_unlabelled": 1,
                "gold_counts": {"a": 2, "b": 1},
            },
        )

    def test_a_measured_quantity_is_not_counted_per_value(self):
        items = [{"gold": float(i)} for i in range(data_counts.CLASS_LIMIT + 1)]
        self.assertIsNone(data_counts.item_counts(items)["gold_counts"])

    def test_an_item_without_the_gold_field_raises(self):
        with self.assertRaises(KeyError):
            data_counts.item_counts([{"id": 1}])

    def test_the_counts_replace_their_own_part_and_keep_the_words(self):
        counts = f"counts (prepare run {RUN}): 3 items prepared"
        self.assertEqual(
            data_counts.with_counts("<source, N, producer script>", counts), counts
        )
        self.assertEqual(
            data_counts.with_counts("data/raw/x.csv by 00_prepare.py.", counts),
            f"data/raw/x.csv by 00_prepare.py · {counts}",
        )
        old = f"data/raw/x.csv · counts (prepare run {RUN}): 2 items prepared"
        self.assertEqual(
            data_counts.with_counts(old, counts), f"data/raw/x.csv · {counts}"
        )


class HeldToTheRun(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name) / "experiments" / "01-x"
        (Path(tmp.name) / ".git").mkdir()
        run = self.area / "runs" / RUN
        run.mkdir(parents=True)
        record = run_record(
            run_kind="preparation",
            data={"source": {"path": "data/raw/x.csv", "sha256": "ab", "rows": 5}},
        )
        (run / "config.json").write_text(json.dumps(record), encoding="utf-8")
        (run / "metrics.json").write_text(
            json.dumps(
                {
                    "n_items": 4,
                    "n_labelled": 3,
                    "n_unlabelled": 1,
                    "gold_counts": {"a": 2, "b": 1},
                }
            ),
            encoding="utf-8",
        )
        (run / "completion.json").write_text(
            json.dumps({"finished": "x"}), encoding="utf-8"
        )
        self.run_dir = run

    def test_the_rendering_names_the_files_and_the_items(self):
        self.assertEqual(
            data_counts.counts_text(self.run_dir),
            f"counts (prepare run {RUN}): read x.csv 5 lines; 4 items prepared — "
            f"3 labelled (a 2, b 1), 1 unlabelled",
        )

    def test_written_counts_hold_and_typed_ones_do_not(self):
        written = "data/raw/x.csv · " + data_counts.counts_text(self.run_dir)
        self.assertIsNone(data_counts.counts_gap(self.area, written))
        self.assertIsNone(data_counts.counts_gap(self.area, "data/raw/x.csv, 4 items"))
        typed = written.replace("3 labelled", "4 labelled")
        gap = data_counts.counts_gap(self.area, typed)
        assert gap is not None
        self.assertIn("the counts differ", gap[0])
        self.assertEqual(gap[1], RUN)
        gone = written.replace(RUN, "2026-01-01T00-00-00_0009")
        gap = data_counts.counts_gap(self.area, gone)
        assert gap is not None
        self.assertIn("which the area does not have", gap[0])


if __name__ == "__main__":
    unittest.main()
