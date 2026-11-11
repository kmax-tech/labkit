"""code-check stations 1b and 1c: every parse_* has a test,
the protocol's prompt block is the PROMPT constant and not a transcript."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks import prompt_check  # noqa: E402
from labkit.formats import protocol_check  # noqa: E402
from labkit.formats.gate import BLOCKER, cited_rule  # noqa: E402

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

    def test_a_parser_no_test_calls_is_a_static_warning(self):
        """A name match is an indication — a parser tested through its
        caller has no call of its own —, so it warns and never blocks."""
        (self.repo / "tests" / "test_01_x.py").write_text(
            "from x import parse_answer\nparse_answer('Yes')\n", encoding="utf-8"
        )
        found = prompt_check.check_parser_fixtures(self.area, self.repo)
        f = [x.line for x in found]
        self.assertEqual(len(f), 1)
        self.assertIn("parse_score()", f[0])
        # the rule whose text asks every parser for a test with raw answers
        self.assertEqual(
            found[0].rule, cited_rule("LAB-041 Generate numbers, don't retype them")
        )
        self.assertTrue(f[0].startswith("WARNING · static evidence · "), f[0])

    def test_a_name_in_a_comment_string_or_import_is_no_test(self):
        """A mention alone never silences the check."""
        (self.repo / "tests" / "test_01_x.py").write_text(
            "from x import parse_answer  # parse_score: TODO\n"
            '"""parse_score is tested elsewhere"""\n',
            encoding="utf-8",
        )
        f = [x.line for x in prompt_check.check_parser_fixtures(self.area, self.repo)]
        # WARNING · static evidence · <where> · <name>() …
        named = sorted(x.split(" · ")[3].split("()")[0] for x in f)
        self.assertEqual(named, ["parse_answer", "parse_score"])

    def test_an_unparsable_test_file_is_said(self):
        (self.repo / "tests" / "test_01_x.py").write_text("def (:\n", encoding="utf-8")
        f = [x.line for x in prompt_check.check_parser_fixtures(self.area, self.repo)]
        self.assertTrue(any("test_01_x.py · cannot be parsed" in x for x in f), f)
        # it hides only an indication: a warning, the check not executed
        self.assertTrue(
            any(
                x.startswith("WARNING · check not executable · test_01_x.py") for x in f
            ),
            f,
        )

    def test_all_parsers_tested_is_silent(self):
        (self.repo / "tests" / "test_01_x.py").write_text(
            "measure.parse_answer('x'); measure.parse_score('1')\n", encoding="utf-8"
        )
        self.assertEqual(prompt_check.check_parser_fixtures(self.area, self.repo), [])

    def test_rendered_block_matches_the_constant(self):
        self.assertEqual(prompt_check.check_prompt_drift(self.area, self.protocol), [])

    def test_drifted_block_is_a_blocker(self):
        self.protocol.write_text(
            PROTOCOL.replace(
                "Answer with a single word, Yes or No.", "Answer Yes or No."
            ),
            encoding="utf-8",
        )
        f = [x.line for x in prompt_check.check_prompt_drift(self.area, self.protocol)]
        self.assertEqual(len(f), 1)
        self.assertIn("drifted from PROMPT", f[0])

    def with_block(self, body: str) -> None:
        self.protocol.write_text(
            PROTOCOL.replace(
                "Judge the claim: The sky is green.\n\n  Answer with a single word, Yes or No.\n\n  Answer:",
                body,
            ),
            encoding="utf-8",
        )

    def test_placeholder_block_is_not_judged(self):
        (stamped,) = protocol_check.stamp_block_placeholders()
        self.with_block(stamped)
        self.assertEqual(prompt_check.check_prompt_drift(self.area, self.protocol), [])

    def test_a_placeholder_of_ones_own_is_judged(self):
        """Only the stamp's fence is no registration; a `<…>` the author
        writes is held like any prompt, so it blocks, never passes."""
        self.with_block("<the real prompt — it belongs here>")
        (f,) = prompt_check.check_prompt_drift(self.area, self.protocol)
        self.assertEqual(f.grade, BLOCKER)
        # the rule whose text asks for the prompt verbatim in the protocol
        self.assertEqual(
            f.rule, cited_rule("LAB-067 A prompt has one home, which the run freezes")
        )

    def test_no_prompt_constant_means_nothing_to_hold(self):
        (self.area / "scripts" / "01_measure.py").write_text(
            "x = 1\n", encoding="utf-8"
        )
        self.assertEqual(prompt_check.check_prompt_drift(self.area, self.protocol), [])


if __name__ == "__main__":
    unittest.main()
