"""protocol_reading measures how a protocol reads: form facts and a cold
reader's answer held to the run's number (2026-10-07)."""

import json
import tempfile
import unittest
from pathlib import Path

from labkit.probes import protocol_reading as pr
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
        "first_lines": "a count",
        "question": "q",
        "result": "r",
        "number": "0,8333",
        "criterion_held": True,
        "admissible": True,
        "holds": "h",
        "next": None,
        "unclear": ["LLM-Arm"],
        "effort": 3,
    }
    TRUTH = pr.Truth(number=0.8333333, criterion_held=True, admissible=True)

    def test_every_checkable_answer_is_held_to_the_run(self):
        s = pr.score_reader_answer(json.dumps(self.ANSWER), self.TRUTH)
        self.assertEqual((s.correct, s.checkable), (3, 3))
        self.assertEqual((s.unclear, s.effort), (["LLM-Arm"], 3))

    def test_a_wrong_verdict_counts_against(self):
        s = pr.score_reader_answer(
            json.dumps({**self.ANSWER, "criterion_held": False}), self.TRUTH
        )
        self.assertIs(s.criterion_ok, False)
        self.assertEqual((s.correct, s.checkable), (2, 3))

    def test_what_the_run_does_not_say_is_not_scored(self):
        truth = pr.Truth(number=3.5, criterion_held=None, admissible=None)
        s = pr.score_reader_answer(json.dumps({**self.ANSWER, "number": "3.5"}), truth)
        self.assertEqual((s.correct, s.checkable), (1, 1))

    def test_the_whole_criterion_wins_over_its_conjuncts(self):
        t = pr.truth_from_metrics(
            {
                "c1_pass": True,
                "c2_pass": False,
                "criterion_pass": False,
                "a1_pass": True,
            },
            None,
        )
        self.assertEqual((t.criterion_held, t.admissible), (False, True))
        t = pr.truth_from_metrics(
            {"c1_pass": True, "a1_pass": True, "a2_pass": False}, None
        )
        self.assertEqual((t.criterion_held, t.admissible), (True, False))

    def test_an_answer_without_the_keys_is_refused(self):
        with self.assertRaises(ValueError):
            pr.score_reader_answer('{"question": "q"}', self.TRUTH)

    def test_the_prompt_carries_the_protocol_and_every_question(self):
        prompt = pr.reader_prompt(CLEAR, "/tmp/a.json")
        self.assertIn("missed the criterion", prompt)
        self.assertIn("new student", prompt)
        for key, _ in pr.READER_QUESTIONS:
            self.assertIn(f'"{key}"', prompt)


SUMMARY_FIRST = """# Experiment protocol: x

## Summary (after the run, for a person)

- **Result:** The model judged 11 of 12 sentences right, clearly above a placebo question.
- **Limits:** Twelve sentences, one run.
- **Next step:** none

## Intent (before the run)

- **Question / hypothesis:** Can the model tell a causal claim?
- **Terms of this protocol:** lane — one prompt variant run over every item;
  item ids c01–c12 = the sentences; see [glossary](glossary.md).
"""

HEAD_FIRST = """# Experiment protocol: x

```toml
[protocol]
standard = "0.19"
id = "p-0000000000000000"
type = "exploratory"
cost = "seconds"
frozen = false
preflight_audit = ""
```

## Summary (after the run, for a person)

- **Result:** The model judged 11 of 12 sentences right.
- **Limits:** One run.
- **Next step:** none
"""


class Glance(unittest.TestCase):
    def test_a_summary_on_top_is_inside_the_first_lines(self):
        g = pr.glance(SUMMARY_FIRST)
        self.assertEqual(g.summary_fields, ("result", "limits", "next step"))
        self.assertEqual(g.lines, 10)
        self.assertEqual(g.chars, len(g.excerpt))

    def test_a_head_on_top_pushes_the_summary_out(self):
        self.assertEqual(pr.glance(HEAD_FIRST).summary_fields, ())

    def test_the_prompt_carries_only_the_excerpt(self):
        g = pr.glance(SUMMARY_FIRST, lines=6)
        prompt = pr.glance_prompt(g.excerpt, "/tmp/g.json")
        self.assertIn("11 of 12", prompt)
        self.assertNotIn("Can the model tell", prompt)
        for key, _ in pr.GLANCE_QUESTIONS:
            self.assertIn(f'"{key}"', prompt)

    def test_a_null_where_the_run_has_a_value_is_not_taken_away(self):
        truth = pr.Truth(number=0.9167, criterion_held=True, admissible=True)
        answer = {
            "question": "q",
            "result": None,
            "number": None,
            "criterion_held": None,
            "how_sure": "h",
            "what_follows": None,
            "unclear": [],
        }
        s = pr.score_glance_answer(json.dumps(answer), truth)
        self.assertEqual((s.number_ok, s.criterion_ok), (False, False))
        self.assertEqual(s.answered, ("question", "how_sure"))

    def test_a_right_glance_passes(self):
        truth = pr.Truth(number=0.9167, criterion_held=True, admissible=None)
        answer = {
            "question": "q",
            "result": "r",
            "number": "0.9167",
            "criterion_held": True,
            "how_sure": "h",
            "what_follows": "w",
            "unclear": ["lane"],
        }
        s = pr.score_glance_answer(json.dumps(answer), truth)
        self.assertEqual((s.number_ok, s.criterion_ok), (True, True))
        self.assertEqual(len(s.answered), 4)


class Terms(unittest.TestCase):
    def test_the_defining_entry_wins_over_a_mention(self):
        glossary = (
            "Grundbegriffe (Fall, Anker …): [Begriffe](b.md). *Anker* — der Arm,\n"
            "der immer gleich entscheidet. *Ziehung* — ein Lauf mit Zufall.\n"
            "- **Anker** — der deterministische Arm im selben Lauf: er muss\n"
            "  jedes Mal gleich entscheiden.\n"
        )
        self.assertEqual(
            pr.entry_for("Anker (anchor)", glossary),
            "*Anker* — der Arm,",
        )
        self.assertEqual(
            pr.entry_for("Ziehung", glossary), "*Ziehung* — ein Lauf mit Zufall."
        )

    def test_a_bullet_keeps_its_continuation_lines(self):
        glossary = "- **Profil** — eine Datei in `register/profiles/`, die\n  festlegt, was geprüft wird.\n"
        self.assertEqual(
            pr.entry_for("Profil", glossary),
            "- **Profil** — eine Datei in `register/profiles/`, die festlegt, was geprüft wird.",
        )

    def test_ids_match_as_patterns(self):
        self.assertEqual(
            pr.normalize_term("`beschaffungsantrag-09`"), "beschaffungsantrag-nn"
        )

    def test_a_term_in_terms_is_found_and_a_missing_one_is_not(self):
        hits = pr.terms_coverage(
            SUMMARY_FIRST, ["lane / registered lane", "c08", "MARGIN"]
        )
        self.assertEqual(
            [(h.in_summary, h.in_terms) for h in hits],
            [(False, True), (False, True), (False, False)],
        )

    def test_a_summary_term_is_marked_as_such(self):
        hits = pr.terms_coverage(SUMMARY_FIRST, ["placebo question"])
        self.assertTrue(hits[0].in_summary)

    def test_a_linked_glossary_counts_and_a_missing_one_raises(self):
        with tempfile.TemporaryDirectory() as d:
            proto = Path(d) / "PROTOCOL-x.md"
            proto.write_text(SUMMARY_FIRST)
            (Path(d) / "glossary.md").write_text(
                "- **Profil:** eine Datei mit Regeln.\n"
            )
            hits = pr.terms_coverage(SUMMARY_FIRST, ["Profil"], str(proto))
            self.assertTrue(hits[0].in_terms)
            self.assertEqual(
                pr.entry_for("Profil", pr.glossary_text(SUMMARY_FIRST, str(proto))),
                "- **Profil:** eine Datei mit Regeln.",
            )
            (Path(d) / "glossary.md").unlink()
            with self.assertRaises(FileNotFoundError):
                pr.glossary_text(SUMMARY_FIRST, str(proto))


class EntryLabels(unittest.TestCase):
    def test_a_shorter_label_inside_the_term_does_not_win(self):
        glossary = (
            "- **Position** — eine Zeile einer Bestellung.\n"
            "- **Fall** — ein Vorgang.\n"
            "- **Positions-Zuordner** — das Modell ordnet Positionen zu.\n"
        )
        self.assertEqual(
            pr.entry_for("Positions-Zuordner", glossary),
            "- **Positions-Zuordner** — das Modell ordnet Positionen zu.",
        )
        self.assertIsNone(pr.entry_for("unstable/fallback", glossary))


class AuditFixes(unittest.TestCase):
    """Findings of the 2026-10-07 code audit, each pinned."""

    TEXT = (
        "## Summary\n\n- **Result:** The CI was wide, as the paragraph says.\n\n"
        "## Context\n\n- **Terms of this protocol:** *CI* — confidence interval;"
        " *N* = sample size; see [g](g.md#calibration).\n"
    )

    def test_short_abbreviations_count(self):
        hits = pr.terms_coverage(self.TEXT, ["CI", "N"])
        self.assertEqual(
            [(h.in_summary, h.in_terms) for h in hits], [(True, True), (False, True)]
        )

    def test_part_of_a_word_is_no_occurrence(self):
        self.assertEqual(pr.terms_coverage(self.TEXT, ["RAG"])[0].in_summary, False)

    def test_a_link_with_an_anchor_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            proto = Path(d) / "PROTOCOL-x.md"
            proto.write_text(self.TEXT)
            (Path(d) / "g.md").write_text(
                "- **Calibration** — how far scores match rates.\n"
            )
            self.assertTrue(
                pr.terms_coverage(self.TEXT, ["calibration"], str(proto))[0].in_terms
            )

    def test_a_verdict_as_a_string_is_refused(self):
        answer = {**Reader.ANSWER, "criterion_held": "true"}
        with self.assertRaises(ValueError):
            pr.score_reader_answer(json.dumps(answer), Reader.TRUTH)

    def test_a_pass_flag_that_is_not_a_bool_is_refused(self):
        with self.assertRaises(ValueError):
            pr.truth_from_metrics({"c1_pass": True, "c2_pass": None}, None)

    def test_a_named_number_that_is_missing_is_refused(self):
        with self.assertRaises(ValueError):
            pr.truth_from_metrics({"c1_pass": True}, "accuracy")
        self.assertEqual(pr.truth_from_metrics({"acc": 0.5}, "acc").number, 0.5)


if __name__ == "__main__":
    unittest.main()
