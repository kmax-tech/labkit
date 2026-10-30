"""FIELDS is the checker's contract, the template the author's: they must name
the same fields, or the checker holds a protocol to a label it never saw."""

import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import protocol_check
from labkit.checks import protocol_report
from protocol_fixture import head

TEMPLATE = (PACKAGE_DIR / "templates" / "experiment-protocol.md.template").read_text(
    encoding="utf-8"
)


def template_fields() -> dict[str, str]:
    """field name -> cut marker ("s", "lb", "lm" or "") as the template stamps them."""
    out = {}
    for f in protocol_check.fields(TEMPLATE):
        line = TEMPLATE.splitlines()[f.line - 1]
        m = re.search(r"<!--\s*(l[bm]?)\s*-->", line)
        out.setdefault(f.name, m.group(1) if m else "")
    return out


class Contract(unittest.TestCase):
    def test_every_checked_label_is_a_template_field(self):
        stamped = template_fields()
        for f in protocol_check.FIELDS:
            self.assertIn(f.label.casefold(), stamped, f.label)

    def test_low_cut_is_the_template_markers(self):
        stamped = template_fields()
        for f in protocol_check.FIELDS:
            self.assertEqual(f.low_cut, stamped[f.label.casefold()], f.label)

    def test_the_template_head_is_well_formed(self):
        stamped = TEMPLATE.replace("<protocol-id>", "p-0123456789abcdef")
        report = protocol_check.check_fields(stamped)
        self.assertIsNone(report.head_error)
        assert report.head is not None
        self.assertEqual(report.head.placeholders, ["type", "repeat_cost", "kind"])


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
        self.assertFalse(
            self.one(
                "- **Quality check:** <10% unparsed [quality-check-1]\n"
            ).placeholder
        )

    def test_unfilled_forms_are_placeholders(self):
        for line in (
            "- **Unit:** <what one counted thing is>\n",
            "- **Unit:** TODO\n",
            "- **Unit:** n/a — <why>\n",
            "- **Unit:**\n",
        ):
            self.assertTrue(self.one(line).placeholder, line)

    def test_indented_content_below_a_bare_label_is_its_value(self):
        """Twin pair (found migrating the thesis example, 2026-10-07):
        sub-bullets or an indented paragraph below count as the value; the
        next field at the same depth does not."""
        sub = protocol_check.fields(
            "- **Model I/O:**\n  - *In:* topic + text\n- **Unit:** u\n"
        )
        self.assertFalse(sub[0].placeholder)
        para = protocol_check.fields("- **Prompt:**\n\n  `prompts/v1.txt` — minimal\n")
        self.assertFalse(para[0].placeholder)
        bare = protocol_check.fields("- **Model I/O:**\n- **Unit:** u\n")
        self.assertTrue(bare[0].placeholder)

    def test_a_label_with_a_code_block_below_is_filled(self):
        f = self.one("- **Prompt (verbatim):**\n\n  ```text\n  Is it?\n  ```\n")
        self.assertFalse(f.placeholder)


class Fields(unittest.TestCase):
    def test_a_word_elsewhere_does_not_fill_a_field(self):
        # the keyword check let "prompt" in any sentence cover Model I/O
        text = (
            head(model="haiku")
            + "We will write a prompt later.\n- **Question / hypothesis:** q\n"
        )
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
        """Twin of the registration gate: written below the label passes, a
        multi-line placeholder stays a placeholder (review 2026-10-07)."""
        written = (
            head(repeat_cost="low") + "- **Question / hypothesis:**\n  Does X beat Y?\n"
            "- **Inference criterion:** [criterion-1] x\n- **Quality check:** [quality-check-1] y\n"
        )
        self.assertEqual(protocol_check.low_registration_missing(written), [])
        unwritten = written.replace(
            "  Does X beat Y?", "  <the one question —\n  what do we expect?>"
        )
        self.assertEqual(
            protocol_check.low_registration_missing(unwritten),
            ["Question / hypothesis"],
        )

    def test_fields_inside_code_blocks_are_not_fields(self):
        text = "```text\n- **Question / hypothesis:** inside a prompt\n```\n"
        self.assertEqual(protocol_check.fields(text), [])

    def test_after_run_fields_are_not_owed_before_the_run(self):
        text = head() + "- **Recorded results:** <number + run_id>\n"
        report = protocol_check.check_fields(text)
        self.assertNotIn("Recorded results", report.missing_must)
        self.assertEqual(report.must_holes, [])

    def test_frozen_graduates_should_to_must(self):
        pilot = protocol_check.check_fields(head())
        frozen = protocol_check.check_fields(head(frozen=True))
        self.assertIn("Free knobs", pilot.missing_should)
        self.assertIn("Free knobs", frozen.missing_must)
        self.assertEqual(frozen.missing_should, [])

    def test_low_owes_its_cut_and_nothing_graduates(self):
        report = protocol_check.check_fields(head(repeat_cost="low", frozen=True))
        self.assertIn("Unit", report.missing_must)
        self.assertNotIn("Model I/O", report.missing_must)
        self.assertNotIn("Prompt", report.missing_must)
        self.assertEqual(report.missing_should, [])
        with_model = (
            head(repeat_cost="low", model="haiku") + "- **Model / tool:** haiku\n"
        )
        self.assertIn("Prompt", protocol_check.check_fields(with_model).missing_must)

    def test_report_fields_fall_due_with_a_declared_result_once_frozen(self):
        run = "2026-10-07T10-00-00_ab12"
        listed = f"\n## Runs\n\n- {run} — the full run\n"
        frozen = head(frozen=True, preflight_audit="x")
        self.assertNotIn(
            "Analysis audit", protocol_check.check_fields(frozen).missing_must
        )
        self.assertNotIn(  # a run in the list declares nothing (phase 5)
            "Analysis audit", protocol_check.check_fields(frozen + listed).missing_must
        )
        declared = head(frozen=True, preflight_audit="x", result=run)
        self.assertIn(
            "Analysis audit", protocol_check.check_fields(declared).missing_must
        )
        self.assertNotIn(
            "Analysis audit", protocol_check.check_fields(head(result=run)).missing_must
        )  # pilot
        self.assertNotIn(
            "Analysis audit",
            protocol_check.check_fields(
                head(repeat_cost="low", result=run)
            ).missing_must,
        )

    def test_none_names_no_model(self):
        text = (
            head(repeat_cost="low")
            + "- **Model / tool:** none — a deterministic count\n"
        )
        self.assertNotIn("Prompt", protocol_check.check_fields(text).missing_must)

    def test_a_head_placeholder_is_a_must_gap(self):
        report = protocol_check.check_fields(head(repeat_cost="<low | high>"))
        self.assertIn("[protocol] repeat_cost", report.missing_must)

    def test_a_malformed_head_is_one_finding(self):
        report = protocol_check.check_fields("- **Cost:** seconds\n")
        self.assertIsNone(report.head)
        self.assertIn("no [protocol] table", report.head_error or "")


class OpenHolesFollowTheCut(unittest.TestCase):
    """At low repeat cost a placeholder outside the cut is not owed, so it is not
    listed; inside the cut it is (usability probe 2026-10-07)."""

    BODY = "- **Unit:** <one file>\n- **Free knobs:** <which>\n"

    def labels(self, cost: str) -> list[str]:
        text = head(repeat_cost=cost) + self.BODY
        block = protocol_check.protocol_block.head(text)
        return [lbl for _, lbl in protocol_check.open_holes(text, block)]

    def test_low_lists_only_the_cut(self):
        self.assertEqual(self.labels("low"), ["Unit"])

    def test_fields_written_after_the_run_wait_for_a_run(self):
        text = head(repeat_cost="low") + "- **Recorded results:** <number + run_id>\n"
        block = protocol_check.protocol_block.head(text)
        self.assertEqual(protocol_check.open_holes(text, block), [])

    def test_once_a_result_is_declared_they_are_owed(self):
        text = (
            head(repeat_cost="low", result="2026-10-07T16-50-37_a9db")
            + "- **Recorded results:** <number + run_id>\n"
            + "- Runs: 2026-10-07T16-50-37_a9db measure\n"
        )
        block = protocol_check.protocol_block.head(text)
        labels = [lbl for _, lbl in protocol_check.open_holes(text, block)]
        self.assertEqual(labels, ["Recorded results"])

    def test_the_full_form_lists_every_placeholder(self):
        self.assertEqual(self.labels("high"), ["Unit", "Free knobs"])

    def test_the_last_line_names_the_must_finding(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "PROTOCOL-x.md"
            f.write_text(head(repeat_cost="low") + self.BODY)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_report.main([str(f)])
        self.assertEqual(rc, 1)
        self.assertIn("Unit (line", buf.getvalue().rstrip().splitlines()[-1])

    def test_protocol_check_stays_quiet_about_fields_not_owed(self):
        report = protocol_check.check_fields(head(repeat_cost="low") + self.BODY)
        self.assertEqual([lbl for _, lbl in report.must_holes], ["Unit"])
        self.assertEqual(report.soft_holes, [])


class StampedLeftovers(unittest.TestCase):
    """A frozen, reported protocol kept `- <run_id> — <…>` under Runs and
    `- <…>` under Notes, and protocol-check said nothing (uniagent area 08,
    2026-10-07): the template line carries a cut marker, the written one
    does not, and `- <…>` has no label for a field check to see."""

    def leftovers(self, body: str, frozen: bool = False) -> str:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "PROTOCOL-x.md"
            f.write_text(head(repeat_cost="high", frozen=frozen) + body)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                protocol_report.main([str(f)])
        return buf.getvalue()

    def test_the_stamped_runs_line_and_a_bare_item_are_named_when_frozen(self):
        out = self.leftovers(
            "## Runs\n\n- <run_id> — <one sentence: what this run was>\n\n"
            "## Notes\n\n- <…>\n",
            frozen=True,
        )
        self.assertIn("- <run_id> — <one sentence: what this run was>", out)
        self.assertIn("- <…>", out)

    def test_before_the_run_the_stamped_runs_line_names_from_run_not_a_leftover(self):
        """Two cold agents stopped at 'still verbatim template text' for the
        line only --from-run can write (Haiku H6, H7, 2026-10-13)."""
        out = self.leftovers(
            "## Runs\n\n- <run_id> — <one sentence: what this run was>\n\n"
            "## Notes\n\n- <…>\n"
        )
        self.assertIn("--from-run", out)
        self.assertNotIn("- <run_id> — <one sentence: what this run was>", out)
        self.assertIn("- <…>", out)  # a bare item is still a leftover

    def test_a_written_runs_line_is_silent(self):
        out = self.leftovers(
            "## Runs\n\n- 2026-10-07T14-11-17_5b06 — the decisive run\n"
        )
        self.assertNotIn("verbatim template text", out)


class BareReferences(unittest.TestCase):
    """A field that only names another area warns; with a link it is silent."""

    def out(self, value: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "PROTOCOL-x.md"
            f.write_text(head(repeat_cost="high") + f"- **Free knobs †:** {value}\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                protocol_report.main([str(f)])
        return buf.getvalue()

    def test_a_bare_reference_warns(self):
        self.assertIn(
            "reference without a link: Free knobs", self.out("wie Bereich 07.")
        )

    def test_a_linked_reference_is_silent(self):
        out = self.out(
            "[Bereich 07](../07-x/PROTOCOL-x.md#setup): threshold 0.6, window 5"
        )
        self.assertNotIn("reference without a link", out)


if __name__ == "__main__":
    unittest.main()
