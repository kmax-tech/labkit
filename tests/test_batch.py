"""Tests for batch.Store — the resume logic decides WHICH items get scored,
so a silent break here changes a reported number without changing any metric.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test
from labkit.run import batch  # noqa: E402

RECORDS = [{"id": f"item-{i}", "text": f"t{i}"} for i in range(5)]


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "out.jsonl"

    def test_pending_is_everything_when_empty(self):
        with batch.Store(self.out) as s:
            self.assertEqual(
                [r["id"] for r in s.pending(RECORDS)], [r["id"] for r in RECORDS]
            )

    def test_pending_skips_written_ids_and_keeps_input_order(self):
        with batch.Store(self.out) as s:
            s.append({"id": "item-1", "ps": 0.5})
            s.append({"id": "item-3", "ps": 0.1})
        with batch.Store(self.out) as s:
            self.assertEqual(
                [r["id"] for r in s.pending(RECORDS)], ["item-0", "item-2", "item-4"]
            )

    def test_append_flushes_each_record(self):
        with batch.Store(self.out) as s:
            s.append({"id": "item-0"})
            # readable from another handle before the block closes
            self.assertEqual(len(self.out.read_text().splitlines()), 1)

    def test_truncated_last_line_is_skipped_and_redone(self):
        self.out.write_text('{"id": "item-0"}\n{"id": "item-1"\n', encoding="utf-8")
        with batch.Store(self.out) as s:
            self.assertEqual(s.done_ids(), {"item-0"})
            self.assertIn("item-1", [r["id"] for r in s.pending(RECORDS)])

    def test_second_writer_is_refused_while_locked(self):
        with batch.Store(self.out):
            with self.assertRaises(SystemExit):
                batch.Store(self.out).__enter__()

    def test_lock_is_released_after_the_block(self):
        with batch.Store(self.out):
            pass
        with batch.Store(self.out):  # would raise if the lock survived
            pass

    def test_lock_is_released_when_the_block_raises(self):
        with self.assertRaises(ValueError):
            with batch.Store(self.out):
                raise ValueError("boom")
        self.assertFalse(self.out.with_suffix(".jsonl.lock").exists())

    def test_append_outside_the_block_raises(self):
        s = batch.Store(self.out)
        with self.assertRaises(RuntimeError):
            s.append({"id": "item-0"})

    def test_status_counts_done_missing_and_stray(self):
        with batch.Store(self.out) as s:
            s.append({"id": "item-0"})
            s.append({"id": "not-in-input"})
            st = s.status(RECORDS)
        self.assertEqual(st["total"], 5)
        self.assertEqual(st["done"], 2)
        self.assertEqual(st["missing"], 4)
        self.assertEqual(st["stray"], ["not-in-input"])
        self.assertNotIn("duplicate", st)

    def test_status_names_a_duplicate_that_a_missing_item_would_hide(self):
        # 4 rows for 4 ids would look whole; item-3 is missing, item-0 doubled
        with batch.Store(self.out) as s:
            for i in (0, 0, 1, 2):
                s.append({"id": f"item-{i}"})
            st = s.status(RECORDS[:4])
        self.assertEqual(st["missing_ids"], ["item-3"])
        self.assertEqual(st["duplicate"], ["item-0"])

    def test_custom_id_key(self):
        recs = [{"uid": "a"}, {"uid": "b"}]
        with batch.Store(self.out, id_key="uid") as s:
            s.append({"uid": "a"})
            self.assertEqual([r["uid"] for r in s.pending(recs)], ["b"])

    def test_records_roundtrip_keeps_unicode(self):
        with batch.Store(self.out) as s:
            s.append({"id": "item-0", "text": "Prämisse — „obwohl“"})
        self.assertEqual(
            json.loads(self.out.read_text())["text"], "Prämisse — „obwohl“"
        )


if __name__ == "__main__":
    unittest.main()


class TestProvenanceStamp(unittest.TestCase):
    """Per-row provenance (2026-08-20): a copied/filtered output file loses its
    runs.tsv join and goes silent about what produced it — the _prov stamp
    keeps every row self-contained (run pointer, model@digest, endpoint)."""

    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "out.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_static_prov_is_stamped_on_every_row(self):
        with batch.Store(self.out, prov={"run": "r1", "model": "m@abc"}) as s:
            s.append({"id": "a", "p": 1})
        row = json.loads(self.out.read_text().splitlines()[0])
        self.assertEqual(row["_prov"], {"run": "r1", "model": "m@abc"})

    def test_callable_values_are_evaluated_per_append(self):
        state = {"url": "server-A"}
        with batch.Store(self.out, prov={"endpoint": lambda: state["url"]}) as s:
            s.append({"id": "a"})
            state["url"] = "server-B"
            s.append({"id": "b"})
        rows = [json.loads(ln) for ln in self.out.read_text().splitlines()]
        self.assertEqual(rows[0]["_prov"]["endpoint"], "server-A")
        self.assertEqual(rows[1]["_prov"]["endpoint"], "server-B")

    def test_without_prov_nothing_changes(self):
        with batch.Store(self.out) as s:
            s.append({"id": "a"})
        self.assertNotIn("_prov", json.loads(self.out.read_text().splitlines()[0]))

    def test_explicit_prov_in_record_wins(self):
        with batch.Store(self.out, prov={"run": "r1"}) as s:
            s.append({"id": "a", "_prov": {"run": "older"}})
        row = json.loads(self.out.read_text().splitlines()[0])
        self.assertEqual(row["_prov"], {"run": "older"})


class DamagedFile(unittest.TestCase):
    """Only a torn LAST line is an interrupted write (review 2026-10-07: a
    broken line mid-file was skipped and the rows after it kept)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "out.jsonl"

    def test_a_broken_line_mid_file_raises_with_its_line(self):
        self.out.write_text('{"id": "a"}\n{broken}\n{"id": "b"}\n', encoding="utf-8")
        with self.assertRaises(ValueError) as cm:
            batch.Store(self.out).records()
        self.assertIn("out.jsonl:2", str(cm.exception))

    def test_resume_cuts_a_torn_tail_before_appending(self):
        self.out.write_text(
            '{"id": "a"}\n{"id": "b"', encoding="utf-8"
        )  # killed mid-write
        with batch.Store(self.out) as s:
            s.append({"id": "b"})
        self.assertEqual([r["id"] for r in batch.Store(self.out).records()], ["a", "b"])


class StoreInstrument(unittest.TestCase):
    """Resume by id alone let a new prompt keep the old prompt's answers (the
    cloud judge probe's analysis audit, 2026-10-14). With `instrument`, every
    row carries it and a resume refuses rows of another."""

    A = {"prompt_sha": "aaaaaaaaaaaa", "model": "haiku"}

    def _with_rows(self, instrument: dict | None) -> Path:
        out = Path(tempfile.mkdtemp()) / "rows.jsonl"
        with batch.Store(out, instrument=instrument) as store:
            store.append({"id": "x:1", "answer": "Yes"})
        return out

    def test_the_same_instrument_resumes_and_rows_carry_it(self):
        out = self._with_rows(self.A)
        with batch.Store(out, instrument=self.A) as store:
            todo = list(store.pending([{"id": "x:1"}, {"id": "x:2"}]))
        self.assertEqual([r["id"] for r in todo], ["x:2"])
        self.assertEqual(batch.Store(out).records()[0]["_instrument"], self.A)

    def test_another_instrument_or_none_is_refused(self):
        for written in ({**self.A, "prompt_sha": "bbbbbbbbbbbb"}, None):
            with self.subTest(written=written):
                out = self._with_rows(written)
                with batch.Store(out, instrument=self.A) as store:
                    with self.assertRaises(batch.InstrumentError) as cm:
                        list(store.pending([{"id": "x:2"}]))
                self.assertIn("new output file", str(cm.exception))

    def test_without_an_instrument_nothing_changes(self):
        out = self._with_rows(None)
        with batch.Store(out) as store:
            self.assertEqual(len(list(store.pending([{"id": "x:2"}]))), 1)
