"""Ids in the letters labkit 0.47 read are refused, never read (review 2026-10-07:
a protocol with [K1] passed intent-check with "no intent ids registered" and
exit 0 — every promise unchecked, and the house CLAUDE template still asked
for those letters)."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from labkit.checks import intent_check
from labkit.formats import promises, protocol_check
from protocol_fixture import head

TEXT = head() + "- **Inference criterion:** [K1] accuracy >= 0.8; [S1] stop on errors\n"


class EarlierIds(unittest.TestCase):
    def test_found_as_written(self):
        self.assertEqual(promises.earlier_ids(TEXT), ["K1", "S1"])
        self.assertEqual(
            promises.earlier_ids(head() + "[criterion-1] and [quality-check-2]"), []
        )

    def test_protocol_check_makes_them_a_must_finding(self):
        missing = protocol_check.check_fields(TEXT).missing_must
        self.assertTrue(any("K1, S1" in m and "0.47" in m for m in missing), missing)

    def test_intent_check_refuses_instead_of_passing(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(TEXT, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                rc = intent_check.main([str(p)])
        self.assertEqual(rc, 2, buf.getvalue())
        self.assertIn("K1, S1", buf.getvalue())

    def test_current_and_previous_letters_are_refused_in_both_cases(self):
        for pid in ("C1", "c1", "A2", "a2", "B1", "b1", "k1"):
            with self.subTest(pid=pid), tempfile.TemporaryDirectory() as d:
                text = (
                    head(kind="compute", repeat_cost="low", promises=None)
                    + f"Criterion [{pid}] accuracy >= 0.8\n"
                )
                self.assertEqual(promises.earlier_ids(text), [pid])
                self.assertTrue(promises.registers_ids(text))
                missing = protocol_check.check_fields(text).missing_must
                self.assertTrue(any("intent ids" in m for m in missing), missing)
                self.assertTrue(
                    any("no [[promise]] table" in m for m in missing), missing
                )
                path = Path(d) / "PROTOCOL-x.md"
                path.write_text(text, encoding="utf-8")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    rc = intent_check.main([str(path)])
                self.assertEqual(rc, 2, buf.getvalue())
                self.assertIn(pid, buf.getvalue())

    def test_new_letters_are_untouched(self):
        text = head() + "- **Inference criterion:** [criterion-1] accuracy >= 0.8\n"
        missing = protocol_check.check_fields(text).missing_must
        self.assertFalse(any("intent ids" in m for m in missing), missing)


if __name__ == "__main__":
    unittest.main()


class EarlierIdsInRecords(unittest.TestCase):
    def test_an_effect_in_the_old_letters_names_the_version_that_reads_it(self):
        """An audit record of 0.103.0 leaves `C1 not assessable`: refused with
        the version that reads it; the twin, today's id, reads."""
        from labkit.formats import findings

        with self.assertRaisesRegex(ValueError, "labkit 0.103.0"):
            findings.effect_ids("C1 not assessable")
        self.assertEqual(
            findings.effect_ids("criterion-1 not assessable"), ("criterion-1",)
        )
