"""code_navigation: truth resolved from the source, answers held to it."""

import json
import tempfile
import unittest
from pathlib import Path

from labkit.probes import code_navigation as cn

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
        got = cn.score_nav_answer(
            json.dumps({"majority": "pkg/mod.py:7", "check": "`./pkg/mod.py:12`"}),
            self.questions,
            self.repo,
        )
        self.assertEqual(
            [(f.file_right, f.found) for f in got], [(True, True), (True, True)]
        )

    def test_the_right_file_at_the_wrong_line_is_not_found(self):
        got = cn.score_nav_answer(
            json.dumps({"majority": "pkg/mod.py:12", "check": None}),
            self.questions,
            self.repo,
        )
        self.assertEqual(
            [(f.file_right, f.found) for f in got], [(True, False), (False, False)]
        )

    def test_an_answer_without_every_key_is_refused(self):
        with self.assertRaises(ValueError):
            cn.score_nav_answer(
                '{"majority": "pkg/mod.py:7"}', self.questions, self.repo
            )

    def test_the_prompt_names_every_question_and_no_truth(self):
        p = cn.nav_prompt(self.repo, self.questions, "/tmp/a.json")
        self.assertIn('"majority"', p)
        self.assertNotIn("Checker.check", p)


class Flows(unittest.TestCase):
    FLOW = cn.Flow(
        "steps",
        "List the checks in order.",
        (("completion", "complet"), ("intent", "intent"), ("tests", "test")),
    )

    def test_steps_named_in_order_count(self):
        answer = ["is the run completed?", "intent ids reported", "area tests pass"]
        self.assertEqual(cn.flow_in_order(answer, self.FLOW), 3)

    def test_a_step_out_of_order_does_not_count(self):
        answer = ["area tests pass", "is the run completed?", "intent ids"]
        self.assertEqual(cn.flow_in_order(answer, self.FLOW), 2)

    def test_a_line_range_is_a_truth(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.py").write_text("x = 1\n" * 30)
            self.assertEqual(cn.symbol_span(Path(d), "m.py:L10-L20"), ("m.py", 10, 20))


class Tails(unittest.TestCase):
    def test_a_unique_tail_names_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pkg").mkdir()
            (repo / "pkg/mod.py").write_text(SOURCE)
            qs = [cn.Question("m", "q", ("pkg/mod.py:majority",))]
            got = cn.score_nav_answer('{"m": "mod.py:7"}', qs, repo)
            self.assertTrue(got[0].found)

    def test_an_ambiguous_tail_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            for sub in ("pkg", "other"):
                (repo / sub).mkdir()
                (repo / sub / "mod.py").write_text(SOURCE)
            qs = [cn.Question("m", "q", ("pkg/mod.py:majority",))]
            got = cn.score_nav_answer('{"m": "mod.py:7"}', qs, repo)
            self.assertFalse(got[0].file_right)


class NavAuditFixes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg/mod.py").write_text(SOURCE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_an_absolute_path_inside_the_repo_counts(self):
        qs = [cn.Question("m", "q", ("pkg/mod.py:majority",))]
        got = cn.score_nav_answer(
            json.dumps({"m": f"{self.repo}/pkg/mod.py:7"}), qs, self.repo
        )
        self.assertTrue(got[0].found)

    def test_a_range_outside_the_file_refuses(self):
        with self.assertRaises(cn.NavigationError):
            cn.symbol_span(self.repo, "pkg/mod.py:L20-L5")
        with self.assertRaises(cn.NavigationError):
            cn.symbol_span(self.repo, "pkg/mod.py:L1-L9999")

    def test_a_flow_answer_that_is_not_a_list_is_refused(self):
        flow = cn.Flow("s", "q", (("a", "alpha"),))
        with self.assertRaises(ValueError):
            cn.score_flows('{"s": "alpha beta"}', [flow])
        with self.assertRaises(ValueError):
            cn.score_flows("{}", [flow])

    def test_two_steps_in_one_item_both_count(self):
        flow = cn.Flow("s", "q", (("a", "alpha"), ("b", "beta"), ("c", "gamma")))
        self.assertEqual(cn.flow_in_order(["alpha and beta", "gamma"], flow), 3)

    def test_a_bad_step_pattern_refuses_at_load(self):
        (self.repo / "q.toml").write_text(
            '[[flow]]\nid = "s"\nquestion = "q"\nsteps = [["a", "("]]\n'
        )
        with self.assertRaises(cn.NavigationError):
            cn.load_flows(self.repo / "q.toml")

    def test_effort_counts_calls_files_and_seconds(self):
        t = self.repo / "t.jsonl"
        rows = [
            {
                "timestamp": "2026-10-07T10:00:00Z",
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "1",
                            "name": "Read",
                            "input": {"file_path": f"{self.repo}/pkg/mod.py"},
                        }
                    ]
                },
            },
            {
                "timestamp": "2026-10-07T10:00:05Z",
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "tool_use_id": "1", "content": "x"}
                    ]
                },
            },
            {
                "timestamp": "2026-10-07T10:00:09Z",
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "2",
                            "name": "Bash",
                            "input": {"command": f"grep -n def {self.repo}/pkg/mod.py"},
                        }
                    ]
                },
            },
        ]
        t.write_text("\n".join(json.dumps(r) for r in rows))
        e = cn.effort(t, self.repo)
        self.assertEqual(
            (e.seconds, e.calls, e.by_tool), (9, 2, {"Read": 1, "Bash": 1})
        )
        self.assertEqual(e.files_opened, ["pkg/mod.py"])


class Choices(unittest.TestCase):
    TOML = (
        '[[choice]]\nid = "c1"\nquestion = "Can warnings alone exit 1?"\n'
        'choices = ["yes", "no"]\ntruth = ["no"]\n'
        '[[choice]]\nid = "c2"\nquestion = "Which stations need a run?"\n'
        'choices = ["a", "b", "c"]\ntruth = ["a", "c"]\n'
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "q.toml"
        self.path.write_text(self.TOML)
        self.choices = cn.load_choices(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_exactly_the_right_set_is_right(self):
        got = cn.score_choices('{"c1": ["no"], "c2": ["c", "a"]}', self.choices)
        self.assertEqual({k: v.right for k, v in got.items()}, {"c1": True, "c2": True})

    def test_a_subset_or_superset_is_wrong(self):
        got = cn.score_choices('{"c1": ["yes"], "c2": ["a", "b"]}', self.choices)
        self.assertEqual(
            {k: v.right for k, v in got.items()}, {"c1": False, "c2": False}
        )
        self.assertEqual((got["c2"].missed, got["c2"].invented), (("c",), ("b",)))
        self.assertEqual((got["c1"].missed, got["c1"].invented), (("no",), ("yes",)))

    def test_an_answer_outside_the_choices_is_refused(self):
        with self.assertRaises(ValueError):
            cn.score_choices('{"c1": ["maybe"], "c2": []}', self.choices)
        with self.assertRaises(ValueError):
            cn.score_choices('{"c1": "no", "c2": []}', self.choices)

    def test_a_truth_outside_the_choices_refuses_at_load(self):
        self.path.write_text(
            '[[choice]]\nid = "c"\nquestion = "q"\nchoices = ["yes", "no"]\ntruth = ["perhaps"]\n'
        )
        with self.assertRaises(cn.NavigationError):
            cn.load_choices(self.path)

    def test_the_prompt_lists_the_choices(self):
        p = cn.nav_prompt(Path("/r"), [], "/tmp/a.json", (), tuple(self.choices))
        self.assertIn("'yes', 'no'", p)
        self.assertNotIn("truth", p)


class Human(unittest.TestCase):
    C = cn.Choice("c", "Which stations?", ("a", "b", "c"), frozenset({"a", "c"}))

    def test_numbers_become_choices(self):
        self.assertEqual(cn.parse_picks("1, 3", self.C), ("a", "c"))
        with self.assertRaises(ValueError):
            cn.parse_picks("4", self.C)

    def test_a_session_times_each_answer_and_asks_again_on_a_typo(self):
        typed = iter(["7", "", "1,3", "2"])
        ticks = iter([0.0, 12.5])
        got = cn.human_session(
            [self.C], lambda _: next(typed), lambda: next(ticks), True
        )
        self.assertEqual(got, [cn.HumanAnswer("c", ("a", "c"), 12.5, 2)])


if __name__ == "__main__":
    unittest.main()
