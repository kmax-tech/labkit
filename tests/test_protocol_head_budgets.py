"""The budgets the template's HEAD comment names are the checker's
(2026-10-05): two homes for one number must agree, or the comment lies."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import protocol_check  # noqa: E402

TEMPLATE = (
    Path(__file__).resolve().parents[1] / "labkit" / "experiment-protocol.md.template"
)


class HeadBudgets(unittest.TestCase):
    def test_comment_matches_section_budget(self):
        head = TEMPLATE.read_text(encoding="utf-8").split("-->", 1)[0]
        head = head.split("<!-- HEAD", 1)[1]
        named = dict(re.findall(r"(Summary|Context|Intent|Setup) (\d+)", head))
        coded = {label: str(limit) for label, _, limit in protocol_check.SECTION_BUDGET}
        self.assertEqual(named, coded)


if __name__ == "__main__":
    unittest.main()
