"""FIELDS is the checker's contract, the template the author's: they must name
the same fields, or the checker holds a protocol to a label it never saw."""

import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from labkit import protocol_check
from protocol_fixture import head

TEMPLATE = (
    Path(protocol_check.__file__)
    .with_name("experiment-protocol.md.template")
    .read_text(encoding="utf-8")
)


def template_fields() -> dict[str, tuple[str, str]]:
    """field name -> (seconds marker, kinds marker) as the template
    stamps them: "s" / "" and "m" / "me" / ""; a wrapped label carries its
    markers on its last line."""
    out = {}
    lines = TEMPLATE.splitlines()
    for f in protocol_check.fields(TEMPLATE):
        span = "\n".join(lines[f.line - 1 : max(f.line, f.last)])
        tags = set(re.findall(r"<!--\s*(s|a|af)\s*-->", span))
        seconds = "s" if "s" in tags else ""
        kinds = "af" if "af" in tags else ("a" if "a" in tags else "")
        out.setdefault(f.name, (seconds, kinds))
    return out


class Contract(unittest.TestCase):
    def test_every_checked_label_is_a_template_field(self):
        stamped = template_fields()
        for f in protocol_check.FIELDS:
            self.assertIn(f.label.casefold(), stamped, f.label)

    def test_the_cuts_are_the_template_markers(self):
        """Both axes: the seconds cut and the kinds that owe a field."""
        stamped = template_fields()
        for f in protocol_check.FIELDS:
            self.assertEqual((f.seconds, f.kinds), stamped[f.label.casefold()], f.label)

    def test_the_template_head_is_well_formed(self):
        stamped = TEMPLATE.replace("<protocol-id>", "p-0123456789abcdef")
        report = protocol_check.check_fields(stamped)
        self.assertIsNone(report.head_error)
        assert report.head is not None
        self.assertEqual(report.head.placeholders, ["type", "cost", "kind"])


class FieldGuide(unittest.TestCase):
    """The guide's kind bullet lists the fields a count and an
    estimator do not owe — the catalogue's two lists, never retyped by
    hand (standard 0.20)."""

    GUIDE = (
        Path(protocol_check.__file__)
        .with_name("protocol-field-guide.md")
        .read_text(encoding="utf-8")
    )

    def listed(self, lead: str) -> list[str]:
        m = re.search(re.escape(lead) + r"\s*(.*?)(?: \(nor|;|\.)", self.GUIDE, re.S)
        assert m is not None, lead
        return " ".join(m.group(1).split()).split(", ")

    def test_the_guide_lists_the_catalogue_cut_by_kind(self):
        self.assertEqual(
            self.listed("A count owes none of:"),
            [f.label for f in protocol_check.FIELDS if f.kinds],
        )
        self.assertEqual(
            self.listed("fit owes none of:"),
            [f.label for f in protocol_check.FIELDS if f.kinds == "a"],
        )


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
            self.one("- **Admissibility condition:** <10% unparsed [A1]\n").placeholder
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
            head() + "We will write a prompt later.\n- **Question / hypothesis:** q\n"
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
        """Twin of the seconds gate: written below the label passes, a
        multi-line placeholder stays a placeholder (review 2026-10-07)."""
        written = (
            head(cost="seconds") + "- **Question / hypothesis:**\n  Does X beat Y?\n"
            "- **Success / failure criterion:** [C1] x\n- **Admissibility condition:** [A1] y\n"
        )
        self.assertEqual(protocol_check.seconds_registration_missing(written), [])
        unwritten = written.replace(
            "  Does X beat Y?", "  <the one question —\n  what do we expect?>"
        )
        self.assertEqual(
            protocol_check.seconds_registration_missing(unwritten),
            ["Question / hypothesis"],
        )

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
        report = protocol_check.check_fields(
            head(cost="seconds", kind="count", frozen=True)
        )
        self.assertIn("Unit", report.missing_must)
        self.assertNotIn("Model I/O", report.missing_must)
        self.assertNotIn("Prompt", report.missing_must)
        self.assertEqual(report.missing_should, [])
        with_model = head(cost="seconds", kind="apply")
        self.assertIn("Prompt", protocol_check.check_fields(with_model).missing_must)

    def test_report_fields_fall_due_with_a_documented_run_once_frozen(self):
        run = "\n## Runs\n\n- 2026-10-07T10-00-00_ab12 — the full run\n"
        frozen = head(frozen=True, preflight_audit="x")
        self.assertNotIn(
            "Analysis audit", protocol_check.check_fields(frozen).missing_must
        )
        self.assertIn(
            "Analysis audit", protocol_check.check_fields(frozen + run).missing_must
        )
        self.assertNotIn(
            "Analysis audit", protocol_check.check_fields(head() + run).missing_must
        )  # pilot
        self.assertNotIn(
            "Analysis audit",
            protocol_check.check_fields(head(cost="seconds") + run).missing_must,
        )

    def test_the_head_decides_the_kind_not_the_prose(self):
        """Until 0.20 a "Model / tool" line naming a model made the prompt
        owed; the head's `kind` is the one reading now."""
        count = head(cost="seconds", kind="count") + "- **Model / tool:** haiku\n"
        self.assertNotIn("Prompt", protocol_check.check_fields(count).missing_must)
        model = head(cost="seconds", kind="apply") + "- **Model / tool:** none\n"
        self.assertIn("Prompt", protocol_check.check_fields(model).missing_must)

    def test_a_head_placeholder_is_a_must_gap(self):
        report = protocol_check.check_fields(head(cost="<seconds | minutes | hours>"))
        self.assertIn("[protocol] cost", report.missing_must)

    def test_a_malformed_head_is_one_finding(self):
        report = protocol_check.check_fields("- **Cost:** seconds\n")
        self.assertIsNone(report.head)
        self.assertIn("no [protocol] table", report.head_error or "")


class OpenHolesFollowTheCut(unittest.TestCase):
    """At seconds a placeholder outside the cut is not owed, so it is not
    listed; inside the cut it is (usability probe 2026-10-07)."""

    BODY = "- **Unit:** <one file>\n- **Free knobs:** <which>\n"

    def labels(self, cost: str) -> list[str]:
        text = head(cost=cost) + self.BODY
        block = protocol_check.protocol_block.head(text)
        return [lbl for _, lbl in protocol_check.open_holes(text, block)]

    def test_seconds_lists_only_the_cut(self):
        self.assertEqual(self.labels("seconds"), ["Unit"])

    def test_fields_written_after_the_run_wait_for_a_run(self):
        text = (
            head(cost="seconds") + "- **Answer to the question:** <number + run_id>\n"
        )
        block = protocol_check.protocol_block.head(text)
        self.assertEqual(protocol_check.open_holes(text, block), [])

    def test_once_a_run_is_documented_they_are_owed(self):
        text = (
            head(cost="seconds")
            + "- **Answer to the question:** <number + run_id>\n"
            + "- Runs: 2026-10-07T16-50-37_a9db measure\n"
        )
        block = protocol_check.protocol_block.head(text)
        labels = [lbl for _, lbl in protocol_check.open_holes(text, block)]
        self.assertEqual(labels, ["Answer to the question"])

    def test_the_full_form_lists_every_placeholder(self):
        self.assertEqual(self.labels("minutes"), ["Unit", "Free knobs"])

    def test_the_last_line_names_the_must_finding(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "PROTOCOL-x.md"
            f.write_text(head(cost="seconds") + self.BODY)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(f)])
        self.assertEqual(rc, 1)
        self.assertIn("Unit (line", buf.getvalue().rstrip().splitlines()[-1])

    def test_protocol_check_stays_quiet_about_fields_not_owed(self):
        report = protocol_check.check_fields(head(cost="seconds") + self.BODY)
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
            f.write_text(head(cost="minutes", frozen=frozen) + body)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                protocol_check.main([str(f)])
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
            f.write_text(head(cost="minutes") + f"- **Free knobs †:** {value}\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                protocol_check.main([str(f)])
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
