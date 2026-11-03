"""The sha256 manifest format (`data_manifest`): what `shasum -a 256`
writes reads, in text and binary mode; anything else is refused with the
line it stands on."""

from __future__ import annotations

import unittest

from labkit.formats.data_manifest import ManifestError, parse_manifest

A, B = "a" * 64, "b" * 64


class Parse(unittest.TestCase):
    def test_shasum_lines_read_in_text_and_binary_mode(self) -> None:
        text = f"{A}  data/x.json\n\n{B} *data/dir with space/y.zip\n"
        self.assertEqual(
            parse_manifest(text, "M"),
            {"data/x.json": A, "data/dir with space/y.zip": B},
        )

    def test_a_line_that_is_no_entry_is_refused_with_its_number(self) -> None:
        for bad in (f"{A[:-1]}  x", f"{A.upper()}  x", f"{A}\tx", "# comment"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ManifestError, r"^M:2: "):
                    parse_manifest(f"{A}  ok\n{bad}\n", "M")

    def test_a_path_listed_twice_reads_only_with_one_digest(self) -> None:
        self.assertEqual(parse_manifest(f"{A}  x\n{A}  x\n", "M"), {"x": A})
        with self.assertRaisesRegex(ManifestError, "M:2: x is listed twice"):
            parse_manifest(f"{A}  x\n{B}  x\n", "M")


if __name__ == "__main__":
    unittest.main()
