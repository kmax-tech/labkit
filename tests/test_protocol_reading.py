"""protocol_reading measures how a protocol reads: form facts and a cold
reader's answer held to the run's number (2026-10-07)."""

import json
import unittest

from labkit import protocol_reading as pr
from protocol_fixture import head

DENSE = (
    "# Experiment protocol: x\n\n*legend line one*\n- legend bullet\n\n"
    + head()
    + "\n## Summary\n\n- **Result †:** [C1] met, c1_pass True, run "
    "`2026-10-07T14-11-17_5b06`\n\n## Result\n\n"
    "- **Answer to the question:** c1_pass True · c2_pass False · a1_pass True\n"
)
CLEAR = (
    "# Experiment protocol: x\n\n"
    + head()
    + "\n## Summary\n\n- **Result †:** The model arm missed the criterion on one wrongly "
    "rejected case.\n\n## Result\n\n- **Answer to the question:** no — [C2] missed; run "
    "`2026-10-07T14-11-17_5b06`.\n\n  | arm | right |\n  |---|---|\n  | model | 21 |\n"
)


class Form(unittest.TestCase):
    def test_a_dense_protocol_shows_its_costs(self):
        f = pr.form(DENSE)
        self.assertEqual(f.prose_before_first_field, 2)
        self.assertEqual(f.chains, 1)
        self.assertEqual(f.summary_codes, 3)
        self.assertFalse(f.answer_has_table)

    def test_a_clear_protocol_is_quiet(self):
        f = pr.form(CLEAR)
        self.assertEqual(
            (f.prose_before_first_field, f.chains, f.summary_codes), (0, 0, 0)
        )
        self.assertTrue(f.answer_has_table)


class Reader(unittest.TestCase):
    ANSWER = {
        "question": "q",
        "result": "r",
        "number": "0,8333",
        "holds": "h",
        "next": None,
        "unclear": ["LLM-Arm"],
        "effort": 3,
    }

    def test_the_number_is_held_to_the_run(self):
        s = pr.score_answer(json.dumps(self.ANSWER), 0.8333333)
        self.assertTrue(s.number_ok)
        self.assertEqual((s.unclear, s.effort), (["LLM-Arm"], 3))

    def test_a_wrong_number_is_named(self):
        s = pr.score_answer(json.dumps({**self.ANSWER, "number": "0.75"}), 0.8333)
        self.assertIs(s.number_ok, False)

    def test_an_answer_without_the_keys_is_refused(self):
        with self.assertRaises(ValueError):
            pr.score_answer('{"question": "q"}', 1.0)

    def test_the_prompt_carries_the_protocol_and_every_question(self):
        prompt = pr.reader_prompt(CLEAR, "/tmp/a.json")
        self.assertIn("missed the criterion", prompt)
        for key, _ in pr.READER_QUESTIONS:
            self.assertIn(f'"{key}"', prompt)


if __name__ == "__main__":
    unittest.main()
