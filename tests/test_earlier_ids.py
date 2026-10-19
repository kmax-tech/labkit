"""Ids in the letters labkit 0.47 read are refused, never read (review 2026-10-07:
a protocol with [K1] passed intent-check with "no intent ids registered" and
exit 0 — every promise unchecked, and the house CLAUDE template still asked
for those letters)."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from labkit import intent_check
from labkit.formats import promises, protocol_check
from protocol_fixture import head

TEXT = (
    head()
    + "- **Success / failure criterion:** [K1] accuracy >= 0.8; [S1] stop on errors\n"
)


class EarlierIds(unittest.TestCase):
    def test_found_as_written(self):
        self.assertEqual(promises.earlier_ids(TEXT), ["K1", "S1"])
        self.assertEqual(promises.earlier_ids(head() + "[C1] and [A2]"), [])

    def test_protocol_check_makes_them_a_must_finding(self):
        missing = protocol_check.check_fields(TEXT).missing_must
        self.assertTrue(
            any("K1, S1" in m and "labkit 0.47" in m for m in missing), missing
        )

    def test_intent_check_refuses_instead_of_passing(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(TEXT, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = intent_check.main([str(p)])
        self.assertEqual(rc, 2, buf.getvalue())
        self.assertIn("K1, S1", buf.getvalue())

    def test_new_letters_are_untouched(self):
        text = head() + "- **Success / failure criterion:** [C1] accuracy >= 0.8\n"
        missing = protocol_check.check_fields(text).missing_must
        self.assertFalse(any("intent ids" in m for m in missing), missing)


if __name__ == "__main__":
    unittest.main()
