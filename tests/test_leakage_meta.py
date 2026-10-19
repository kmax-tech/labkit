"""Integration: write_dataset → _ids → describe_data must not be fooled by _meta.

write_dataset() puts a _meta header as the first line of every dataset. Before
the fix, _ids() bailed out on the missing "id" key in that header and returned
None, causing the leakage check to be silently skipped for exactly the
standard-generated files it is meant to protect. describe_data()'s row count also
included the _meta line.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from labkit.run.batch import write_dataset
from labkit.run.provenance import _data_rows, describe_data, _ids, _is_meta


class TestIsMetaRecognition(unittest.TestCase):
    def test_meta_dict(self):
        self.assertTrue(_is_meta({"_meta": {"about": "x"}}))

    def test_data_row(self):
        self.assertFalse(_is_meta({"id": "a", "text": "hello"}))

    def test_non_dict(self):
        self.assertFalse(_is_meta([1, 2, 3]))


class TestIdsSkipsMeta(unittest.TestCase):
    """_ids must skip the _meta header and return the data ids."""

    def setUp(self):
        self._dir = TemporaryDirectory()
        self.dir = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def test_standard_dataset_returns_ids(self):
        path = self.dir / "train.jsonl"
        write_dataset(
            path,
            [{"id": "a", "x": 1}, {"id": "b", "x": 2}],
            about="test",
            fields={"id": "id", "x": "feature"},
            producer="test",
        )
        ids = _ids(path)
        self.assertIsNotNone(ids, "_ids should not bail on _meta header")
        self.assertEqual(ids, {"a", "b"})

    def test_data_rows_excludes_meta(self):
        path = self.dir / "train.jsonl"
        write_dataset(
            path,
            [{"id": "a", "x": 1}, {"id": "b", "x": 2}],
            about="test",
            fields={"id": "id", "x": "feature"},
            producer="test",
        )
        self.assertEqual(_data_rows(path), 2)


class TestLeakageWithMeta(unittest.TestCase):
    """End-to-end: two datasets with overlapping ids must be caught."""

    def setUp(self):
        self._dir = TemporaryDirectory()
        self.dir = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def test_leakage_detected_across_meta_datasets(self):
        fields = {"id": "id", "text": "text"}
        train = self.dir / "train.jsonl"
        test = self.dir / "test.jsonl"
        write_dataset(
            train,
            [{"id": "shared", "text": "a"}, {"id": "only-train", "text": "b"}],
            about="train",
            fields=fields,
            producer="test",
        )
        write_dataset(
            test,
            [{"id": "shared", "text": "c"}, {"id": "only-test", "text": "d"}],
            about="test",
            fields=fields,
            producer="test",
        )
        with self.assertRaises(RuntimeError, msg="leakage must be caught"):
            describe_data({"train": str(train), "test": str(test)}, self.dir)

    def test_no_leakage_passes(self):
        fields = {"id": "id", "text": "text"}
        train = self.dir / "train.jsonl"
        dev = self.dir / "dev.jsonl"
        write_dataset(
            train,
            [{"id": "a", "text": "x"}],
            about="train",
            fields=fields,
            producer="test",
        )
        write_dataset(
            dev, [{"id": "b", "text": "y"}], about="dev", fields=fields, producer="test"
        )
        result = describe_data({"train": str(train), "dev": str(dev)}, self.dir)
        self.assertIn("leakage_check", result)
        self.assertIn("ok", result["leakage_check"])
        self.assertEqual(result["train"]["rows"], 1)
        self.assertEqual(result["dev"]["rows"], 1)


if __name__ == "__main__":
    unittest.main()


class TestDamagedLineIsNamed(unittest.TestCase):
    """A line that is not JSON names file and line (audit 2026-10-15: a
    bare JSONDecodeError named neither); a row that is no object is not
    checkable, like a row without an id."""

    def test_file_and_line_are_named(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "train.jsonl"
            path.write_text('{"id": 1}\n{not json\n', encoding="utf-8")
            with self.assertRaises(ValueError) as cm:
                _ids(path)
            self.assertIn("train.jsonl:2", str(cm.exception))
            self.assertIn("not JSON", str(cm.exception))

    def test_a_row_that_is_no_object_is_not_checkable(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "train.jsonl"
            path.write_text("[1, 2]\n", encoding="utf-8")
            self.assertIsNone(_ids(path))
