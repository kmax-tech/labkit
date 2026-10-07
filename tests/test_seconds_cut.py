"""The seconds cut (2026-10-05): one template, tagged `<!-- s -->`; the
checker's FIELDS name exactly the tagged fields as the cut; the registration
gate asks for question, criterion, admissibility condition and cost."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import protocol_check  # noqa: E402
from protocol_fixture import head  # noqa: E402

TEMPLATE = (
    Path(__file__).resolve().parents[1] / "labkit" / "experiment-protocol.md.template"
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
        with_model = text + "- **Model / tool:** haiku\n"
        missing = protocol_check.check_fields(with_model).missing_must
        self.assertEqual(missing, ["Prompt", "Null condition / anchors"])

    def test_seconds_protocol_is_checked_against_the_cut_only(self):
        text = (
            "# Experiment protocol: x\n"
            + head(type="confirmatory", cost="seconds")
            + """
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [C1] accuracy > 0.5
- **Admissibility condition:** [A1] at most two empty answers
- **Terms of this protocol:** n/a — standard vocabulary
- **Data / scope:** data/raw/claims.jsonl, 12 rows
- **Unit:** one sentence, judged once
- **Model / tool:** haiku
- **Prompt (verbatim, per variant):** see block
- **Null condition / anchors (in the same run):** [A2] two anchors
- **Exclusions / filters:** none
- **Answer to the question:** pending
- **Raw output:** pending
"""
        )
        report = protocol_check.check_fields(text)
        self.assertEqual(report.missing_must, [])
        self.assertEqual(report.missing_should, [])
        gap = text.replace("- **Unit:** one sentence, judged once\n", "")
        self.assertEqual(protocol_check.check_fields(gap).missing_must, ["Unit"])

    def test_frozen_at_seconds_is_refused_not_graduated(self):
        """Nothing freezes at seconds (§2.A14): `frozen = true` there owes no
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
    QUESTION = "- **Question / hypothesis:** q\n- **Success / failure criterion:** c\n"

    def test_all_four_written(self):
        text = (
            head(cost="seconds") + self.QUESTION + "- **Admissibility condition:** a\n"
        )
        self.assertEqual(protocol_check.intent_missing(text), [])

    def test_placeholder_counts_as_missing(self):
        text = (
            head(cost="seconds")
            + self.QUESTION
            + "- **Admissibility condition:** <what must hold…>\n"
        )
        self.assertEqual(
            protocol_check.intent_missing(text), ["Admissibility condition"]
        )

    def test_the_old_stop_rule_label_does_not_register(self):
        text = head(cost="seconds") + self.QUESTION + "- **Stop rule:** s\n"
        self.assertEqual(
            protocol_check.intent_missing(text), ["Admissibility condition"]
        )

    def test_cost_is_read_from_the_head(self):
        text = (
            head(cost="<seconds | minutes | hours>")
            + self.QUESTION
            + "- **Admissibility condition:** a\n- **Cost:** seconds\n"
        )
        self.assertEqual(protocol_check.intent_missing(text), ["[protocol] cost"])


if __name__ == "__main__":
    unittest.main()
