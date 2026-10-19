"""code-check stations 1b and 1c (2026-10-05): every parse_* has a test,
the protocol's prompt block is the PROMPT constant and not a transcript."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks import code_check  # noqa: E402

SCRIPT = """
PROMPT = ("Judge the claim: {claim}\\n\\n"
          "Answer with a single word, Yes or No.\\n\\n"
          "Answer:")


def parse_answer(text: str) -> str:
    return text.strip()


def parse_score(text: str) -> float:
    return float(text)
"""
PROTOCOL = """# Experiment protocol: x
- **Protocol id:** p-0123456789abcdef
- **Prompt (verbatim, per variant):**

  ```text
  Judge the claim: The sky is green.

  Answer with a single word, Yes or No.

  Answer:
  ```
"""


class Gates(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / ".git").mkdir()
        self.area = self.repo / "experiments" / "01-x"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "scripts" / "01_measure.py").write_text(SCRIPT, encoding="utf-8")
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(PROTOCOL, encoding="utf-8")
        (self.repo / "tests").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_parser_without_test_is_a_blocker(self):
        (self.repo / "tests" / "test_01_x.py").write_text(
            "from x import parse_answer\n", encoding="utf-8"
        )
        f = code_check.check_parser_fixtures(self.area, self.repo)
        self.assertEqual(len(f), 1)
        self.assertIn("parse_score()", f[0])
        self.assertTrue(f[0].startswith("BLOCKER"))

    def test_all_parsers_tested_is_silent(self):
        (self.repo / "tests" / "test_01_x.py").write_text(
            "measure.parse_answer('x'); measure.parse_score('1')\n", encoding="utf-8"
        )
        self.assertEqual(code_check.check_parser_fixtures(self.area, self.repo), [])

    def test_rendered_block_matches_the_constant(self):
        self.assertEqual(code_check.check_prompt_drift(self.area, self.protocol), [])

    def test_drifted_block_is_a_blocker(self):
        self.protocol.write_text(
            PROTOCOL.replace(
                "Answer with a single word, Yes or No.", "Answer Yes or No."
            ),
            encoding="utf-8",
        )
        f = code_check.check_prompt_drift(self.area, self.protocol)
        self.assertEqual(len(f), 1)
        self.assertIn("drifted from PROMPT", f[0])

    def test_placeholder_block_is_not_judged(self):
        self.protocol.write_text(
            PROTOCOL.replace(
                "Judge the claim: The sky is green.\n\n  Answer with a single word, Yes or No.\n\n  Answer:",
                "<the real prompt — it belongs here>",
            ),
            encoding="utf-8",
        )
        self.assertEqual(code_check.check_prompt_drift(self.area, self.protocol), [])

    def test_no_prompt_constant_means_nothing_to_hold(self):
        (self.area / "scripts" / "01_measure.py").write_text(
            "x = 1\n", encoding="utf-8"
        )
        self.assertEqual(code_check.check_prompt_drift(self.area, self.protocol), [])


if __name__ == "__main__":
    unittest.main()
