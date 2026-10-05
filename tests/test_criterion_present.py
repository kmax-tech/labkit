"""criterion_present (2026-10-05): the written success criterion is the
full-run gate at `Cost: seconds` — a placeholder, an empty value or a
missing field is not a criterion."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.protocol_check import criterion_present  # noqa: E402


class CriterionPresent(unittest.TestCase):
    def test_written_field(self):
        self.assertTrue(criterion_present(
            "- **Success / failure criterion:** [K1] accuracy > null\n"))

    def test_german_label(self):
        self.assertTrue(criterion_present("- **Erfolgskriterium:** [K1] r² > 0.5\n"))

    def test_placeholder_is_not_a_criterion(self):
        self.assertFalse(criterion_present(
            "- **Success / failure criterion:** <what counts as success>\n"))

    def test_empty_value_is_not_a_criterion(self):
        self.assertFalse(criterion_present("- **Success / failure criterion:**\n"))

    def test_missing_field(self):
        self.assertFalse(criterion_present("- **Question:** does it hold?\n"))

    def test_prose_mention_does_not_count(self):
        self.assertFalse(criterion_present(
            "The success criterion will be added before the run.\n"))


if __name__ == "__main__":
    unittest.main()
