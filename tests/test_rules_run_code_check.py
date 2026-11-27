"""Rule tests of `run_code_check`'s pure checks: each condition from typed
data in memory, its violation and its valid twin (docs/architecture.md,
"Checks and their tests"). The gate that composes them is finalize
(`tests/test_finalize_steps.py` for its stations); the comparison of the code
reads run folders and git and is tested in `tests/test_run_code.py`.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest

from check_guards import pure_call
from labkit.checks.run_code_check import answer_reading_gaps
from labkit.formats.gate import BLOCKER, LAB_041, LAB_067
from labkit.formats.runs import OutputEntry

pytestmark = pytest.mark.rule


class ADeclaredAnswerReadingHoldsPromptsAndAnswers(unittest.TestCase):
    """A derived run that declares its answer reading re-reads its parent's
    answers under the same prompts: the prompts field exact, the shared
    answer file with the parent's sha256, at least one shared file."""

    TEXT = "Count  the lines."
    OUT = Path("output/answers.jsonl")
    ANEW = "measure anew (`python scripts/01_measure.py`) and audit that run"

    def gaps(self, prompts: tuple, parent: str, child: str) -> list:
        outputs = (
            [OutputEntry(path=self.OUT, sha256=parent, lines=3)],
            [OutputEntry(path=self.OUT, sha256=child, lines=3)],
        )
        return pure_call(answer_reading_gaps, "A", "D", prompts, outputs, self.ANEW)

    def test_the_same_prompts_and_answers_pass(self) -> None:
        self.assertEqual(self.gaps((self.TEXT, self.TEXT), "abc", "abc"), [])

    def test_a_changed_prompt_holds_even_in_whitespace(self) -> None:
        for now in (self.TEXT.replace("  ", " "), None):
            with self.subTest(now=now):
                (found,) = self.gaps((self.TEXT, now), "abc", "abc")
                self.assertEqual(found.grade, BLOCKER)
                self.assertEqual(found.rule, LAB_067)
                self.assertIn("differs from the text A was measured under", found.text)
                self.assertIn(self.ANEW, found.line)

    def test_answers_registered_with_other_bytes_hold(self) -> None:
        (found,) = self.gaps((self.TEXT, self.TEXT), "abc", "abd")
        self.assertEqual(found.rule, LAB_041)
        self.assertIn("the answers changed after A ran", found.text)

    def test_no_shared_answer_file_holds(self) -> None:
        outputs = ([OutputEntry(path=self.OUT, sha256="abc", lines=3)], [])
        (found,) = pure_call(
            answer_reading_gaps, "A", "D", (self.TEXT, self.TEXT), outputs, self.ANEW
        )
        self.assertIn("registered none of the files A registered", found.text)
