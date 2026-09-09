"""Tests for protocol-fill — fill a stamped placeholder by label.

Why this is tested: filling protocol fields by quoting the placeholder text
back failed in 3-round loops twice in one day (2026-09-09, PROTOCOL-67).
The label match must hit single- and multi-line placeholders, refuse
ambiguity and silent overwrites, and leave every other byte alone.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test

from labkit import protocol_fill  # noqa: E402

SAMPLE = """# Experiment protocol: x

## Summary † (write last)

- **Question †:** <the same sentence as in the Intent>
- **Result †:** <number(s) + run_id>

## Intent

- **Question / hypothesis:** does Y move X?
- **Meaning of the gold label †:** <what does the positive class REALLY
  mean, in the annotator's words>
- **Model / tool:** haiku via models.toml
"""


class TestFill(unittest.TestCase):

    def test_single_line_placeholder_is_replaced_by_label(self):
        out = protocol_fill.fill(SAMPLE, "Result", "K2 PASS, run 2026-x")
        self.assertIn("- **Result †:** K2 PASS, run 2026-x", out)
        self.assertNotIn("<number(s)", out)
        self.assertIn("does Y move X?", out)          # untouched neighbours

    def test_multi_line_placeholder_collapses_to_the_filled_line(self):
        out = protocol_fill.fill(SAMPLE, "Meaning of the gold label",
                                 "positive = the judge prefers world A")
        self.assertIn("- **Meaning of the gold label †:** positive = the "
                      "judge prefers world A", out)
        self.assertNotIn("annotator's words", out)

    def test_label_match_ignores_dagger_and_case(self):
        out = protocol_fill.fill(SAMPLE, "result †", "filled")
        self.assertIn("- **Result †:** filled", out)

    def test_filled_field_is_refused_without_force(self):
        with self.assertRaises(ValueError) as ctx:
            protocol_fill.fill(SAMPLE, "Model / tool", "gpt-oss")
        self.assertIn("already filled", str(ctx.exception))
        out = protocol_fill.fill(SAMPLE, "Model / tool", "gpt-oss",
                                 force=True)
        self.assertIn("- **Model / tool:** gpt-oss", out)

    def test_unknown_label_lists_the_open_fields(self):
        with self.assertRaises(ValueError) as ctx:
            protocol_fill.fill(SAMPLE, "No such field", "x")
        msg = str(ctx.exception)
        self.assertIn("Question", msg)
        self.assertIn("Meaning of the gold label", msg)

    def test_ambiguous_label_requires_line(self):
        two = SAMPLE + "\n- **Result †:** <second stamp>\n"
        with self.assertRaises(ValueError) as ctx:
            protocol_fill.fill(two, "Result", "x")
        self.assertIn("--line", str(ctx.exception))
        out = protocol_fill.fill(two, "Result", "x", line_no=6)
        self.assertIn("- **Result †:** x", out)
        self.assertIn("<second stamp>", out)

    def test_open_fields_lists_placeholders_only(self):
        labels = [lbl for _, lbl in protocol_fill.open_fields(SAMPLE)]
        self.assertIn("Question †", labels)
        self.assertIn("Meaning of the gold label †", labels)
        self.assertNotIn("Model / tool", labels)


if __name__ == "__main__":
    unittest.main()
