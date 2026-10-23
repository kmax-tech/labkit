"""Tests for jsonl.record_lines — the one line reader of JSON Lines files.

`json.dumps(..., ensure_ascii=False)` leaves U+2028, U+2029 and U+0085 raw;
`str.splitlines()` breaks at them, so a record holding one read as two torn
lines and the file was called damaged (2026-10-23).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test
from labkit.checks import recheck  # noqa: E402
from labkit.formats import jsonl  # noqa: E402
from labkit.run import batch  # noqa: E402

#: the line separators json.dumps leaves raw and str.splitlines breaks at
SEPARATORS = (" ", " ", "\x85")


class TestLines(unittest.TestCase):
    def test_splits_at_newline_only(self):
        for sep in SEPARATORS:
            with self.subTest(sep=repr(sep)):
                text = json.dumps({"t": f"a{sep}b"}, ensure_ascii=False) + "\n"
                # the case is real: the old reader saw two lines here
                self.assertEqual(len(text.splitlines()), 2)
                self.assertEqual(len(jsonl.record_lines(text)), 1)

    def test_a_final_newline_adds_no_empty_line(self):
        self.assertEqual(
            jsonl.record_lines('{"a": 1}\n{"a": 2}\n'), ['{"a": 1}', '{"a": 2}']
        )
        self.assertEqual(jsonl.record_lines('{"a": 1}'), ['{"a": 1}'])
        self.assertEqual(jsonl.record_lines(""), [])

    def test_crlf_and_blank_lines_read_as_splitlines_did(self):
        self.assertEqual(
            jsonl.record_lines('{"a": 1}\r\n\r\n{"a": 2}\r\n'),
            ['{"a": 1}', "", '{"a": 2}'],
        )


class TestRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "out.jsonl"

    def test_store_reads_back_what_it_wrote(self):
        for sep in SEPARATORS:
            with self.subTest(sep=repr(sep)):
                self.out.unlink(missing_ok=True)
                rows = [{"id": "a", "text": f"x{sep}y"}, {"id": "b", "text": "z"}]
                with batch.Store(self.out) as s:
                    for r in rows:
                        s.append(r)
                with batch.Store(self.out) as s:
                    self.assertEqual(
                        [(r["id"], r["text"]) for r in s.records()],
                        [(r["id"], r["text"]) for r in rows],
                    )
                    self.assertEqual(s.done_ids(), ["a", "b"])

    def test_write_dataset_reads_back_through_the_store_and_recheck(self):
        for sep in SEPARATORS:
            with self.subTest(sep=repr(sep)):
                rows = [{"id": "a", "text": f"x{sep}y"}, {"id": "b", "text": "z"}]
                batch.write_dataset(
                    self.out,
                    rows,
                    about="one item per row",
                    fields={"id": "unique per row", "text": "the item"},
                    producer="t",
                )
                self.assertEqual(batch.Store(self.out).records(), rows)
                self.assertEqual(recheck.rows_of(self.out), rows)

    def test_a_torn_last_line_is_cut_and_the_rows_before_it_stay_whole(self):
        for sep in SEPARATORS:
            with self.subTest(sep=repr(sep)):
                whole = {"id": "a", "text": f"x{sep}y"}
                self.out.write_text(
                    json.dumps(whole, ensure_ascii=False) + '\n{"id": "b", "te',
                    encoding="utf-8",
                )
                with batch.Store(self.out) as s:
                    self.assertEqual(s.records(), [whole])
                self.assertEqual(
                    self.out.read_text(encoding="utf-8"),
                    json.dumps(whole, ensure_ascii=False) + "\n",
                )

    def test_a_broken_line_mid_file_is_still_refused(self):
        self.out.write_text(
            '{"id": "a"}\n{"id": "b"\n'
            + json.dumps({"id": "c", "t": "x y"}, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            ValueError, r"out\.jsonl:2: unparseable line before the end"
        ):
            batch.Store(self.out).records()


if __name__ == "__main__":
    unittest.main()
