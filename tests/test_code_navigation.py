"""code_navigation: truth resolved from the source, answers held to it."""

import json
import tempfile
import unittest
from pathlib import Path

from labkit import code_navigation as cn

SOURCE = '''"""A small module."""

LIMIT = 3


def majority(votes):
    """The strict majority, else 'unstable'."""
    return "unstable"


class Checker:
    def check(self, case):
        return case
'''

QUESTIONS = """
[[question]]
id = "majority"
question = "Where is the majority decided?"
truth = ["pkg/mod.py:majority"]

[[question]]
id = "check"
question = "Where is a case checked?"
truth = ["pkg/mod.py:Checker.check", "pkg/mod.py:LIMIT"]
"""


class Navigation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg/mod.py").write_text(SOURCE)
        (self.repo / "q.toml").write_text(QUESTIONS)
        self.questions = cn.load_questions(self.repo / "q.toml")

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_symbol_resolves_to_its_lines(self):
        self.assertEqual(
            cn.symbol_span(self.repo, "pkg/mod.py:majority"), ("pkg/mod.py", 6, 8)
        )
        self.assertEqual(
            cn.symbol_span(self.repo, "pkg/mod.py:Checker.check"),
            ("pkg/mod.py", 12, 13),
        )
        self.assertEqual(
            cn.symbol_span(self.repo, "pkg/mod.py:LIMIT"), ("pkg/mod.py", 3, 3)
        )

    def test_a_truth_that_is_gone_refuses(self):
        with self.assertRaises(cn.NavigationError):
            cn.symbol_span(self.repo, "pkg/mod.py:minority")
        with self.assertRaises(cn.NavigationError):
            cn.symbol_span(self.repo, "pkg/other.py:majority")

    def test_a_right_answer_is_found(self):
        got = cn.score(
            json.dumps({"majority": "pkg/mod.py:7", "check": "`./pkg/mod.py:12`"}),
            self.questions,
            self.repo,
        )
        self.assertEqual(
            [(f.file_right, f.found) for f in got], [(True, True), (True, True)]
        )

    def test_the_right_file_at_the_wrong_line_is_not_found(self):
        got = cn.score(
            json.dumps({"majority": "pkg/mod.py:12", "check": None}),
            self.questions,
            self.repo,
        )
        self.assertEqual(
            [(f.file_right, f.found) for f in got], [(True, False), (False, False)]
        )

    def test_an_answer_without_every_key_is_refused(self):
        with self.assertRaises(ValueError):
            cn.score('{"majority": "pkg/mod.py:7"}', self.questions, self.repo)

    def test_the_prompt_names_every_question_and_no_truth(self):
        p = cn.prompt(self.repo, self.questions, "/tmp/a.json")
        self.assertIn('"majority"', p)
        self.assertNotIn("Checker.check", p)


if __name__ == "__main__":
    unittest.main()
