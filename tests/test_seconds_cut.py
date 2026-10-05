"""The seconds cut (2026-10-05): one template, tagged `<!-- s -->`; the
checker's MUST_SECONDS names exactly the tagged fields; the registration
gate asks for question, criterion, stop rule and cost."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import protocol_check  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "labkit" / "experiment-protocol.md.template"


class Cut(unittest.TestCase):
    def test_every_must_seconds_label_is_tagged_in_the_template(self):
        lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
        tagged = [ln.lower() for ln in lines if "<!-- s -->" in ln and ln.startswith("- **")]
        tagged_model = [ln.lower() for ln in lines if "<!-- sm -->" in ln and ln.startswith("- **")]
        for label, pat in protocol_check.MUST_SECONDS:
            self.assertTrue([ln for ln in tagged if re.search(pat, ln)],
                            f"{label!r} ({pat}) matches no `s` field line")
        for label, pat in protocol_check.MUST_SECONDS_MODEL:
            self.assertTrue([ln for ln in tagged_model if re.search(pat, ln)],
                            f"{label!r} ({pat}) matches no `sm` field line")

    def test_count_without_model_owes_no_prompt(self):
        text = """- **Standard:** 0.17
- **Protocol id:** p-0123456789abcdef
- **Question / hypothesis:** how many?
- **Success / failure criterion:** the mean is reported
- **Stop rule:** n/a — deterministic
- **Type:** measurement
- **Cost:** seconds
- **Terms of this protocol:** n/a
- **Data / scope:** data/raw/cases.jsonl
- **Unit:** one file
- **Exclusions / filters:** hidden files
"""
        self.assertEqual(protocol_check.check_text(text, standard="0.17")[0], [])
        with_model = text + "- **Model / tool:** haiku\n"
        missing, _ = protocol_check.check_text(with_model, standard="0.17")
        self.assertEqual(len(missing), 2)

    def test_seconds_protocol_is_checked_against_the_cut_only(self):
        text = """# Experiment protocol: x
- **Standard:** 0.17
- **Protocol id:** p-0123456789abcdef
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [K1] accuracy > 0.5
- **Stop rule:** [S1] more than two empty answers
- **Type:** confirmatory
- **Cost:** seconds — 14 calls
- **Terms of this protocol:** n/a — standard vocabulary
- **Data / scope:** data/raw/claims.jsonl, 12 rows
- **Unit:** one sentence, judged once
- **Model / tool:** haiku
- **Prompt (verbatim, per variant):** see block
- **Null condition / anchors (in the same run):** [N1] two anchors
- **Exclusions / filters:** none
- **Answer to the question:** pending
- **Raw output:** pending
"""
        missing_must, missing_should = protocol_check.check_text(text, standard="0.17")
        self.assertEqual(missing_must, [])
        self.assertEqual(missing_should, [])
        gap = text.replace("- **Unit:** one sentence, judged once\n", "")
        missing_must, _ = protocol_check.check_text(gap, standard="0.17")
        self.assertEqual(len(missing_must), 1)
        self.assertIn("Unit", missing_must[0])


class Registration(unittest.TestCase):
    def test_all_four_written(self):
        text = ("- **Question / hypothesis:** q\n- **Success / failure criterion:** c\n"
                "- **Stop rule:** s\n- **Cost:** seconds\n")
        self.assertEqual(protocol_check.intent_missing(text), [])

    def test_placeholder_counts_as_missing(self):
        text = ("- **Question / hypothesis:** q\n- **Success / failure criterion:** c\n"
                "- **Stop rule:** <at what point…>\n- **Cost:** seconds\n")
        self.assertEqual(protocol_check.intent_missing(text), ["stop rule"])


if __name__ == "__main__":
    unittest.main()
