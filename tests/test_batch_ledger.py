"""Tests for batch.Store.ledger — the balance that decides whether a run
counts as complete. A gate that blocks gets its twin: the whole file passes."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test
from labkit import batch  # noqa: E402

RECORDS = [{"id": f"item-{i}", "text": f"t{i}"} for i in range(4)]
EXPECT = {"prompt_sha": "p1", "input_sha": lambda rec: "sha-" + rec["text"]}


def row(i: int, prompt_sha: str = "p1", **extra: object) -> dict:
    return {
        "id": f"item-{i}",
        "prompt_sha": prompt_sha,
        "input_sha": f"sha-t{i}",
        **extra,
    }


class Ledger(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp()) / "out.jsonl"

    def write(self, rows: list[dict]) -> batch.Store:
        self.out.write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
        )
        return batch.Store(self.out)

    def test_a_whole_file_balances_and_passes(self):
        led = self.write([row(i) for i in range(4)]).ledger(RECORDS, expect=EXPECT)
        self.assertTrue(led.ok)
        led.require_complete()  # no raise: no false blocker
        self.assertEqual(
            led.counts(),
            {
                "n_items": 4,
                "n_rows": 4,
                "n_missing": 0,
                "n_duplicate": 0,
                "n_stray": 0,
                "n_unidentified": 0,
                "n_stale_prompt_sha": 0,
                "n_stale_input_sha": 0,
            },
        )

    def test_a_missing_item_and_a_duplicate_do_not_cancel_out(self):
        led = self.write([row(0), row(0), row(1), row(2)]).ledger(RECORDS)
        self.assertEqual((led.items, led.rows), (4, 4))  # the lengths agree
        self.assertEqual(led.missing, ["item-3"])
        self.assertEqual(led.duplicate, ["item-0"])
        with self.assertRaises(SystemExit) as cm:
            led.require_complete()
        self.assertIn("missing 1", str(cm.exception))
        self.assertIn("duplicate 1", str(cm.exception))
        self.assertIn("NOT complete", str(cm.exception))

    def test_stray_and_unidentified_rows_fail(self):
        rows = [row(i) for i in range(4)] + [{"id": "other"}, {"text": "no id"}]
        led = self.write(rows).ledger(RECORDS)
        self.assertEqual(led.stray, ["other"])
        self.assertEqual(led.unidentified, 1)
        self.assertFalse(led.ok)

    def test_a_row_from_another_prompt_or_item_version_is_stale(self):
        rows = [
            row(0, prompt_sha="p0"),
            row(1),
            row(2),
            {**row(3), "input_sha": "sha-old"},
        ]
        led = self.write(rows).ledger(RECORDS, expect=EXPECT)
        self.assertEqual(led.stale, {"prompt_sha": ["item-0"], "input_sha": ["item-3"]})
        self.assertFalse(led.ok)

    def test_a_row_without_the_expected_field_is_stale_even_if_none_is_expected(self):
        rows = [{"id": f"item-{i}"} for i in range(4)]
        led = self.write(rows).ledger(RECORDS, expect={"problem": None})
        self.assertEqual(len(led.stale["problem"]), 4)

    def test_meta_header_and_torn_tail_are_not_rows(self):
        text = json.dumps({"_meta": {"about": "x"}}) + "\n"
        text += "".join(json.dumps(row(i)) + "\n" for i in range(4)) + '{"id": "item-'
        self.out.write_text(text, encoding="utf-8")
        led = batch.Store(self.out).ledger(RECORDS)
        self.assertEqual(led.rows, 4)
        self.assertTrue(led.ok)

    def test_duplicate_input_ids_are_refused(self):
        with self.assertRaises(ValueError):
            self.write([]).ledger(RECORDS + RECORDS[:1])

    def test_inside_a_run_the_raise_keeps_the_run_from_completing(self):
        from labkit import runlog

        area = self.out.parent
        store = self.write([row(0)])
        with self.assertRaises(SystemExit):
            with runlog.run("ledger-test", {"n": 4}, area) as r:
                led = store.ledger(RECORDS)
                r.metrics(**led.counts())
                led.require_complete()
        run_dirs = [d for d in (area / "runs").iterdir() if d.is_dir()]
        self.assertEqual(len(run_dirs), 1)
        self.assertFalse((run_dirs[0] / "completion.json").exists())
        self.assertFalse((area / "runs.tsv").exists())

    def test_inside_a_run_a_balanced_output_completes(self):
        from labkit import runlog

        area = self.out.parent
        store = self.write([row(i) for i in range(4)])
        with runlog.run("ledger-test", {"n": 4}, area) as r:
            led = store.ledger(RECORDS)
            r.metrics(**led.counts())
            led.require_complete()
        run_dir = next(d for d in (area / "runs").iterdir() if d.is_dir())
        self.assertTrue((run_dir / "completion.json").exists())
        self.assertTrue((area / "runs.tsv").exists())
        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["n_missing"], 0)


if __name__ == "__main__":
    unittest.main()
