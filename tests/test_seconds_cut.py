"""The seconds cut (2026-10-05): one template, tagged `<!-- s -->`; the
checker's FIELDS name exactly the tagged fields as the cut; the registration
gate asks for question, criterion, admissibility condition and cost."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import protocol_check  # noqa: E402
from labkit.tools import scaffold, protocol_cuts  # noqa: E402
from protocol_fixture import head  # noqa: E402

TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "labkit"
    / "templates"
    / "experiment-protocol.md.template"
)


def _tagged(marker: str) -> set[str]:
    """Names of the template fields whose label line carries `marker`."""
    text = TEMPLATE.read_text(encoding="utf-8")
    raw = text.splitlines()
    return {f.name for f in protocol_check.fields(text) if marker in raw[f.line - 1]}


class Cut(unittest.TestCase):
    def test_the_cut_is_exactly_the_tagged_template_fields(self):
        cut = {f.label.casefold() for f in protocol_check.FIELDS if f.seconds == "s"}
        cut_model = {
            f.label.casefold() for f in protocol_check.FIELDS if f.seconds == "sm"
        }
        self.assertEqual(cut, _tagged("<!-- s -->"))
        self.assertEqual(cut_model, _tagged("<!-- sm -->"))

    def test_count_without_model_owes_no_prompt(self):
        text = (
            head(cost="seconds")
            + """
- **Question / hypothesis:** how many?
- **Success / failure criterion:** the mean is reported
- **Admissibility condition:** n/a — deterministic
- **Terms of this protocol:** n/a
- **Data / scope:** data/raw/cases.jsonl
- **Unit:** one file
- **Exclusions / filters:** hidden files
"""
        )
        self.assertEqual(protocol_check.check_fields(text).missing_must, [])
        with_model = (
            head(cost="seconds", model="haiku")
            + text[len(head(cost="seconds")) :]
            + "- **Model / tool:** haiku\n"
        )
        missing = protocol_check.check_fields(with_model).missing_must
        self.assertEqual(
            missing, ["Data profile", "Prompt", "Null condition / anchors"]
        )

    def test_seconds_protocol_is_checked_against_the_cut_only(self):
        text = (
            "# Experiment protocol: x\n"
            + head(type="confirmatory", cost="seconds", model="haiku")
            + """
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [C1] accuracy > 0.5
- **Admissibility condition:** [A1] at most two empty answers
- **Terms of this protocol:** n/a — standard vocabulary
- **Data / scope:** data/raw/claims.jsonl, 12 rows
- **Data profile:** 6 and 6 items, mean words 9 and 9; no marker only in one class
- **Unit:** one sentence, judged once
- **Model / tool:** haiku
- **Prompt (verbatim, per variant):** see block
- **Null condition / anchors (in the same run):** [A2] two anchors
- **Exclusions / filters:** none
- **Recorded results:** pending
- **Raw output:** pending
"""
        )
        report = protocol_check.check_fields(text)
        self.assertEqual(report.missing_must, [])
        self.assertEqual(report.missing_should, [])
        gap = text.replace("- **Unit:** one sentence, judged once\n", "")
        self.assertEqual(protocol_check.check_fields(gap).missing_must, ["Unit"])

    def test_frozen_at_seconds_is_refused_not_graduated(self):
        """Nothing freezes at seconds (LAB-017 The number of audits follows the cost tier): `frozen = true` there owes no
        should field, but claims a freeze no gate held — one must finding
        (review 2026-10-07: it used to pass silently)."""
        text = (
            head(cost="seconds", frozen=True)
            + """
- **Question / hypothesis:** q
- **Success / failure criterion:** c
- **Admissibility condition:** a
- **Terms of this protocol:** n/a
- **Data / scope:** d
- **Data profile:** 6 and 6 items, mean words 9 and 9; no marker only in one class
- **Unit:** u
- **Exclusions / filters:** none
"""
        )
        report = protocol_check.check_fields(text)
        self.assertEqual(len(report.missing_must), 1, report.missing_must)
        self.assertIn('frozen = true at cost = "seconds"', report.missing_must[0])
        self.assertEqual(report.missing_should, [])
        self.assertEqual(report.missing_should, [])


class Registration(unittest.TestCase):
    QUESTION = (
        "- **Model / tool:** haiku\n"  # with a model the gate owes criterion and admissibility
        "- **Question / hypothesis:** q\n- **Success / failure criterion:** c\n"
        "- **Data profile:** 6 and 6 items; 'because' in both classes\n"
    )

    def test_a_count_owes_only_its_question(self):
        """Without a model there is no bar to clear: the gate is the question (0.87.1)."""
        text = head(cost="seconds") + "- **Question / hypothesis:** how many?\n"
        self.assertEqual(protocol_check.seconds_registration_missing(text), [])
        text = head(cost="seconds") + "- **Question / hypothesis:** <the question>\n"
        self.assertEqual(
            protocol_check.seconds_registration_missing(text), ["Question / hypothesis"]
        )

    def test_all_four_written(self):
        text = (
            head(cost="seconds", model="haiku")
            + self.QUESTION
            + "- **Admissibility condition:** a\n"
        )
        self.assertEqual(protocol_check.seconds_registration_missing(text), [])

    def test_placeholder_counts_as_missing(self):
        text = (
            head(cost="seconds", model="haiku")
            + self.QUESTION
            + "- **Admissibility condition:** <what must hold…>\n"
        )
        self.assertEqual(
            protocol_check.seconds_registration_missing(text),
            ["Admissibility condition"],
        )

    def test_with_a_model_the_judged_data_profile_is_owed(self):
        """Review 2026-10-21: printing the profile is not judging it; the run
        waits for the judgement in the protocol."""
        text = (
            head(cost="seconds", model="haiku")
            + self.QUESTION.replace("- **Data profile:** 6 and 6 items; 'because' in both classes\n", "")
            + "- **Admissibility condition:** a\n"
            + "- **Data profile:** <what `00_prepare.py --audit` shows>\n"
        )  # fmt: skip
        self.assertEqual(
            protocol_check.seconds_registration_missing(text), ["Data profile"]
        )

    def test_the_old_stop_rule_label_does_not_register(self):
        text = (
            head(cost="seconds", model="haiku") + self.QUESTION + "- **Stop rule:** s\n"
        )
        self.assertEqual(
            protocol_check.seconds_registration_missing(text),
            ["Admissibility condition"],
        )

    def test_cost_is_read_from_the_head(self):
        text = (
            head(cost="<seconds | minutes | hours>")
            + self.QUESTION
            + "- **Admissibility condition:** a\n- **Cost:** seconds\n"
        )
        self.assertEqual(
            protocol_check.seconds_registration_missing(text), ["[protocol] cost"]
        )


class CountPlaceholders(unittest.TestCase):
    """Without a model the Terms and Question placeholders say what a count
    owes: three cold agents wrote a Terms sentence for a plain count, one read
    'hypothesis' as an expectation to invent (Haiku H5–H7, 2026-10-13)."""

    def test_the_count_cut_says_na_and_no_hypothesis(self):
        cut = protocol_cuts.seconds_cut(
            scaffold.template(scaffold.PROTOCOL_TEMPLATE.name)
        )
        out = protocol_cuts.count_placeholders(cut)
        self.assertIn(
            '**Terms of this protocol:** <one line per coined house word — or "n/a — no coinage">',
            out,
        )
        self.assertIn("a count tests no hypothesis>", out)
        self.assertNotIn("what do we expect?", out)

    def test_a_cut_without_the_field_is_refused(self):
        with self.assertRaises(ValueError):
            protocol_cuts.count_placeholders("- **Unit:** <x>\n")


if __name__ == "__main__":
    unittest.main()
