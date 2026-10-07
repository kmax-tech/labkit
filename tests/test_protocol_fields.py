"""FIELDS is the checker's contract, the template the author's: they must name
the same fields, or the checker holds a protocol to a label it never saw."""
import re
import unittest
from pathlib import Path

from labkit import protocol_check
from protocol_fixture import head

TEMPLATE = Path(protocol_check.__file__).with_name("experiment-protocol.md.template").read_text(
    encoding="utf-8")


def template_fields() -> dict[str, str]:
    """field name -> cut marker ("s", "sm" or "") as the template stamps them."""
    out = {}
    for f in protocol_check.fields(TEMPLATE):
        line = TEMPLATE.splitlines()[f.line - 1]
        m = re.search(r"<!--\s*(sm?)\s*-->", line)
        out.setdefault(f.name, m.group(1) if m else "")
    return out


class Contract(unittest.TestCase):
    def test_every_checked_label_is_a_template_field(self):
        stamped = template_fields()
        for f in protocol_check.FIELDS:
            self.assertIn(f.label.casefold(), stamped, f.label)

    def test_seconds_cut_is_the_template_markers(self):
        stamped = template_fields()
        for f in protocol_check.FIELDS:
            self.assertEqual(f.seconds, stamped[f.label.casefold()], f.label)

    def test_the_template_head_is_well_formed(self):
        stamped = TEMPLATE.replace("<protocol-id>", "p-0123456789abcdef")
        report = protocol_check.check_fields(stamped)
        self.assertIsNone(report.head_error)
        assert report.head is not None
        self.assertEqual(report.head.placeholders, ["type", "cost"])


class Daggers(unittest.TestCase):
    def test_dagger_marks_exactly_the_report_grade_fields(self):
        """† in the template = should or report in FIELDS, and every report
        field carries †: the legend and the checker say the same thing
        (review 2026-10-07: 14 † fields were never checked)."""
        daggered = {f.name for f in protocol_check.fields(TEMPLATE) if "†" in f.label}
        levels = {f.label.casefold(): f.level for f in protocol_check.FIELDS}
        for name in daggered:
            self.assertIn(levels.get(name), ("should", "report"), name)
        for label, level in levels.items():
            if level == "report":
                self.assertIn(label, daggered, label)


class Placeholders(unittest.TestCase):
    def one(self, line: str):
        (f,) = protocol_check.fields(line)
        return f

    def test_content_starting_with_a_bracket_is_content(self):
        self.assertFalse(self.one("- **Admissibility condition:** <10% unparsed [A1]\n").placeholder)

    def test_unfilled_forms_are_placeholders(self):
        for line in ("- **Unit:** <what one counted thing is>\n",
                     "- **Unit:** TODO\n",
                     "- **Unit:** n/a — <why>\n",
                     "- **Unit:**\n"):
            self.assertTrue(self.one(line).placeholder, line)

    def test_a_label_with_a_code_block_below_is_filled(self):
        f = self.one("- **Prompt (verbatim):**\n\n  ```text\n  Is it?\n  ```\n")
        self.assertFalse(f.placeholder)


class Fields(unittest.TestCase):
    def test_a_word_elsewhere_does_not_fill_a_field(self):
        # the keyword check let "prompt" in any sentence cover Model I/O
        text = head() + "We will write a prompt later.\n- **Question / hypothesis:** q\n"
        missing = protocol_check.check_fields(text).missing_must
        self.assertIn("Model I/O", missing)
        self.assertIn("Prompt", missing)

    def test_label_with_gloss_and_dagger(self):
        text = "- **Rival explanations †:** length\n- **Prompt (verbatim, per variant):**\n"
        names = [f.name for f in protocol_check.fields(text)]
        self.assertEqual(names, ["rival explanations", "prompt"])

    def test_a_wrapped_label_is_read_whole(self):
        text = "- **Resolution check (ZERO calls, real `evaluate()` on synthetic\n  extremes):** <…>\n"
        (f,) = protocol_check.fields(text)
        self.assertEqual(f.name, "resolution check")
        self.assertTrue(f.placeholder)

    def test_a_value_on_the_next_line_is_written(self):
        """Twin of the seconds gate: written below the label passes, a
        multi-line placeholder stays a placeholder (review 2026-10-07)."""
        written = (head(cost="seconds") + "- **Question / hypothesis:**\n  Does X beat Y?\n"
                   "- **Success / failure criterion:** [C1] x\n- **Admissibility condition:** [A1] y\n")
        self.assertEqual(protocol_check.intent_missing(written), [])
        unwritten = written.replace("  Does X beat Y?", "  <the one question —\n  what do we expect?>")
        self.assertEqual(protocol_check.intent_missing(unwritten), ["Question / hypothesis"])

    def test_fields_inside_code_blocks_are_not_fields(self):
        text = "```text\n- **Question / hypothesis:** inside a prompt\n```\n"
        self.assertEqual(protocol_check.fields(text), [])

    def test_after_run_fields_are_not_owed_before_the_run(self):
        text = head() + "- **Answer to the question:** <number + run_id>\n"
        report = protocol_check.check_fields(text)
        self.assertNotIn("Answer to the question", report.missing_must)
        self.assertEqual(report.must_holes, [])

    def test_frozen_graduates_should_to_must(self):
        pilot = protocol_check.check_fields(head())
        frozen = protocol_check.check_fields(head(frozen=True))
        self.assertIn("Free knobs", pilot.missing_should)
        self.assertIn("Free knobs", frozen.missing_must)
        self.assertEqual(frozen.missing_should, [])

    def test_seconds_owes_its_cut_and_nothing_graduates(self):
        report = protocol_check.check_fields(head(cost="seconds", frozen=True))
        self.assertIn("Unit", report.missing_must)
        self.assertNotIn("Model I/O", report.missing_must)
        self.assertNotIn("Prompt", report.missing_must)
        self.assertEqual(report.missing_should, [])
        with_model = head(cost="seconds") + "- **Model / tool:** haiku\n"
        self.assertIn("Prompt", protocol_check.check_fields(with_model).missing_must)

    def test_report_fields_fall_due_with_a_documented_run_once_frozen(self):
        run = "\n## Runs\n\n- 2026-10-07T10-00-00_ab12 — the full run\n"
        frozen = head(frozen=True, preflight_audit="x")
        self.assertNotIn("Analysis audit", protocol_check.check_fields(frozen).missing_must)
        self.assertIn("Analysis audit", protocol_check.check_fields(frozen + run).missing_must)
        self.assertNotIn("Analysis audit",
                         protocol_check.check_fields(head() + run).missing_must)       # pilot
        self.assertNotIn("Analysis audit",
                         protocol_check.check_fields(head(cost="seconds") + run).missing_must)

    def test_none_names_no_model(self):
        text = head(cost="seconds") + "- **Model / tool:** none — a deterministic count\n"
        self.assertNotIn("Prompt", protocol_check.check_fields(text).missing_must)

    def test_a_head_placeholder_is_a_must_gap(self):
        report = protocol_check.check_fields(head(cost="<seconds | minutes | hours>"))
        self.assertIn("[protocol] cost", report.missing_must)

    def test_a_malformed_head_is_one_finding(self):
        report = protocol_check.check_fields("- **Cost:** seconds\n")
        self.assertIsNone(report.head)
        self.assertIn("no [protocol] table", report.head_error or "")


if __name__ == "__main__":
    unittest.main()
