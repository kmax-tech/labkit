"""Tests for batch.Store(mode="produce") — a producer replaces its file.

Why this is tested: 2026-09-09, area 71 — a second producer run APPENDED its
plan to the first one (625+528 = 1153 rows) because Store is append-only by
design; only the producer's --verify caught the hybrid file. Produce mode
must make re-running the producer idempotent (one run's file, atomically),
and a crash must leave the previous file untouched.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test

from labkit.run import batch  # noqa: E402


def _rows(path: Path) -> list[dict]:
    return [
        json.loads(x)
        for x in path.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]


class TestProduce(unittest.TestCase):
    def test_second_producer_run_replaces_instead_of_appending(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.jsonl"
            for _ in range(2):
                with batch.Store(out, mode="produce") as store:
                    for i in range(3):
                        store.append({"id": i})
            self.assertEqual(
                len(_rows(out)), 3, "produce mode must replace, never concatenate"
            )

    def test_crash_leaves_the_previous_file_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.jsonl"
            with batch.Store(out, mode="produce") as store:
                store.append({"id": "good"})
            with self.assertRaises(RuntimeError):
                with batch.Store(out, mode="produce") as store:
                    store.append({"id": "partial"})
                    raise RuntimeError("boom mid-produce")
            self.assertEqual(
                [r["id"] for r in _rows(out)],
                ["good"],
                "a crashed produce must not touch the target",
            )
            self.assertTrue(
                out.with_suffix(".jsonl.tmp").exists(),
                "the partial output must stay visible",
            )

    def test_produce_pending_sees_all_records_as_open(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.jsonl"
            with batch.Store(out, mode="produce") as store:
                store.append({"id": 1})
            recs = [{"id": 1}, {"id": 2}]
            with batch.Store(out, mode="produce") as store:
                open_ids = [r["id"] for r in store.pending(recs)]
            self.assertEqual(
                open_ids, [1, 2], "a producer re-run regenerates everything"
            )

    def test_resume_mode_is_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "scores.jsonl"
            with batch.Store(out) as store:
                store.append({"id": 1})
            with batch.Store(out) as store:
                open_ids = [r["id"] for r in store.pending([{"id": 1}, {"id": 2}])]
                for i in open_ids:
                    store.append({"id": i})
            self.assertEqual([r["id"] for r in _rows(out)], [1, 2])

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            batch.Store("x.jsonl", mode="append")


if __name__ == "__main__":
    unittest.main()
