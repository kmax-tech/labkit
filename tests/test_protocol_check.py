"""Tests for protocol-check.py against real protocol material.

The checker turns freely written protocols into a pass/fail decision, so it
gets the parser treatment (LAB-023 No silent loss): tested with real raw text.
The frozen excerpt below is verbatim from experiments/_archiv/17-bruchstufe-nli/PROTOCOL-bruchstufe-nli.md
(2026-08-11), one of the five freely written protocols that omitted exactly
"Typ" and "Modell-I/O" — the two fields whose omission caused bad runs on
2026-08-13. It names no term either, which is why it also fails the Begriffe
field added on 2026-08-19. The excerpt is frozen here so the test keeps working
after the live protocol gets fixed.

Since TODO 8 the head is the ```toml block's [protocol] table and the prose
fields are held by their exact template label (`FIELDS`); keyword matching
anywhere in the text is gone on purpose.
"""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "labkit" / "templates" / "experiment-protocol.md.template"

sys.path.insert(0, str(REPO))
from labkit.formats import (  # noqa: E402
    protocol_block,
    protocol_check,
    protocol_history,
    protocol_report,
    scope_sha,
)  # noqa: E402
from protocol_fixture import head, scope_file  # noqa: E402


MUST = [f.label for f in protocol_check.FIELDS if f.level == "must"]
SHOULD = [f.label for f in protocol_check.FIELDS if f.level == "should"]

# Verbatim from experiments/_archiv/17-bruchstufe-nli/PROTOCOL-bruchstufe-nli.md: intro + the real
# section headers. Carries Frage, Hypothese, Anker, Kontrollen, Erfolgs-/
# Abbruchkriterien — but neither "Begriffe", "Typ" nor "Modell-I/O"/"Prompt".
REAL_FREEFORM_PROTOCOL = """\
# PROTOCOL: Fassen NLI-Scores die Bruchstufen des Seeds?

_2026-08-11 · Intent VOR dem Lauf (Arbeitsstandard §2)._

## Frage

Bildet ein Standard-NLI-Modell diese Staffelung ab?

## Hypothese und Erwartung

**H1 (NLI fasst die Staffelung):** Δ(neutral) > Δ(skeptisch) >
Δ(sehr_skeptisch), floor ≈ 0.

## Anker (Instrument-Kontrolle, entscheidet Instrument vs. Hypothese)

**Wenn schon die Anker scheitern (Entailment niedrig / neutral), misst das
Instrument nichts.**

## Kontrollen

1. **Flip-Test:** dieselbe Messung gegen ¬C.

## Erfolgs- / Abbruchkriterien

## Umfang
"""

# Every must field of a pilot, filled — with one rendered example, so the
# verbatim-block check is satisfied.
PILOT_FIELDS = """\
- **Terms of this protocol:** n/a — standard vocabulary
- **Question / hypothesis:** does A beat B?
- **Success / failure criterion:** [C1] AUC > 0.6
- **Admissibility condition:** [A1] yield >= 90%
- **Model I/O:** in: claim · out: yes/no, parsed by parse()
- **Prompt:** see block

  ```text
  Is this fallacious?
  ```

- **Null condition / anchors:** [A2] shuffled labels at chance
- **Exclusions / filters:** none
- **Data / scope:** data/prepared/claims.jsonl, 50 items
- **Data profile:** 6 and 6 items, mean words 9 and 9; no marker only in one class
- **Model / tool:** haiku
- **Unit:** one claim
"""

# Every should field, filled: a frozen protocol owes them as musts.
REPORT_FIELDS = """\
- **Problem in one sentence:** does the judge see fallacies?
- **Meaning of the gold label:** positive = annotated fallacy
- **Yield per stage:** 50 in, 50 parsed
- **Rival explanations:** length bias — checked in evaluate()
- **Out of scope:** other judges
- **Free knobs:** none
- **Prediction for the follow-up run:** AUC 0.65
- **Instrument check:** 10 calls, see block
- **Resolution check:** perfect effect fires, null stays silent
- **Gate labels:** yes, no
- **Randomness controls:** deterministic
- **Why this design:** the judge is the instrument under test
- **Data preparation:** scripts/00_prepare.py writes data/prepared/claims.jsonl
- **Answer form + resolution:** yes/no, two states
- **How measured:** AUC over the judge's yes-probability
- **Validation:** anchors of known label
- **Noise ceiling → threshold:** spread 0.02 over three draws
"""


def pilot(**head_kw) -> str:
    return "# x\n\n" + head(**head_kw) + "\n" + PILOT_FIELDS


AUDIT_LINE = "2026-10-07 · scope sha 3f9a1c2b7e04 · 0 findings"


def frozen(**head_kw) -> str:
    head_kw.setdefault("preflight_audit", AUDIT_LINE)
    return pilot(frozen=True, **head_kw) + REPORT_FIELDS


def run_main(text: str) -> tuple[int, str]:
    """protocol_report.main over `text` written to a PROTOCOL-x.md."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "PROTOCOL-x.md"
        p.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = protocol_report.main([str(p)])
        return rc, buf.getvalue()


class TestFrozenNeedsTheAudit(unittest.TestCase):
    """`frozen = true` means audited first (LAB-015 Preflight audit before freezing): the old checker failed a
    frozen protocol whose audit field was still a placeholder."""

    def test_frozen_without_audit_line_fails(self):
        rc, out = run_main(frozen(preflight_audit=""))
        self.assertEqual(rc, 1)
        self.assertIn("[protocol] preflight_audit", out)

    def test_seconds_needs_no_audit_line(self):
        report = protocol_check.check_fields(head(cost="seconds", frozen=True))
        self.assertFalse(any("preflight_audit" in m for m in report.missing_must))


class TestResultAfterARun(unittest.TestCase):
    """A documented measure run makes the result due — a placeholder counts
    as empty, not only a dash."""

    RUN = "\n## Runs\n\n- 2026-09-06T10-00-00_aa11 — the full run\n"

    def test_placeholder_answer_after_a_run_fails(self):
        text = (
            pilot() + "\n- **Answer to the question:** <number + run_id>\n"
            "- **Raw output:** see output/examples.md\n" + self.RUN
        )
        rc, out = run_main(text)
        self.assertEqual(rc, 1)
        self.assertIn("measure run in the run list", out)


class TestFlagsAnywhere(unittest.TestCase):
    def test_contract_after_the_path_is_the_flag_not_a_file(self):
        for argv in (["--contract", "PROTOCOL-x.md"], ["PROTOCOL-x.md", "--contract"]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(protocol_report.main(argv), 0, argv)
            self.assertNotIn("not readable", out.getvalue())
            self.assertIn("Question / hypothesis", out.getvalue())


class TestFixtures(unittest.TestCase):
    """The shared fixtures are what they claim: a clean pilot, a clean freeze."""

    def test_pilot_passes(self):
        rc, out = run_main(pilot())
        self.assertEqual(rc, 0, out)

    def test_frozen_passes(self):
        """OK only when nothing at all is found: the area's code exists and
        the audit line names the stamp it has now (until 2026-10-20 the OK
        stood beside a preflight_audit warning)."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            scope_file(area)
            sha = scope_sha.area_stamp(area)[0]
            p = area / "PROTOCOL-x.md"
            p.write_text(
                frozen(preflight_audit=f"2026-10-20 · scope sha {sha} · 0 findings"),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_report.main([str(p)])
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("all must and should fields filled", buf.getvalue())


class TestCheckFields(unittest.TestCase):
    def test_template_names_every_field(self):
        names = {
            f.name for f in protocol_check.fields(TEMPLATE.read_text(encoding="utf-8"))
        }
        for f in protocol_check.FIELDS:
            self.assertIn(f.label.casefold(), names, f.label)

    def test_template_owes_only_its_head(self):
        report = protocol_check.check_fields(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(
            report.missing_must, ["[protocol] id", "[protocol] type", "[protocol] cost"]
        )
        self.assertEqual(report.missing_should, [])

    def test_real_freeform_protocol_has_no_head(self):
        report = protocol_check.check_fields(REAL_FREEFORM_PROTOCOL)
        self.assertIsNone(report.head)
        assert report.head_error is not None
        self.assertIn("no [protocol] table", report.head_error)

    def test_real_freeform_protocol_misses_every_must_field(self):
        """With a head, its bold labels (H1, Flip-Test) are no template field:
        it misses all of them, Terms and Model I/O among them."""
        report = protocol_check.check_fields(head() + REAL_FREEFORM_PROTOCOL)
        self.assertEqual(report.missing_must, MUST)
        self.assertIn("Terms of this protocol", report.missing_must)
        self.assertIn("Model I/O", report.missing_must)

    def test_explicit_na_counts_as_present(self):
        text = head() + "".join(
            f"- **{label}:** n/a — no model in this run\n" for label in MUST
        )
        report = protocol_check.check_fields(text)
        self.assertEqual(report.missing_must, [])
        self.assertEqual(report.must_holes, [])

    def test_head_alone_misses_everything(self):
        report = protocol_check.check_fields(head())
        self.assertEqual(report.missing_must, MUST)
        self.assertEqual(report.missing_should, SHOULD)

    def test_empty_text_is_a_head_error(self):
        report = protocol_check.check_fields("")
        self.assertIsNotNone(report.head_error)
        self.assertEqual(report.missing_must, [])

    def test_a_keyword_in_prose_does_not_satisfy_a_field(self):
        """A word anywhere used to satisfy a field (`prompt` in a sentence
        covered Model I/O). Only the label line counts."""
        text = (
            head() + "We ask the model a prompt about terms, model I/O and anchors.\n"
        )
        self.assertEqual(protocol_check.check_fields(text).missing_must, MUST)

    def test_after_fields_are_not_owed_before_the_run(self):
        """Answer, Raw output and Analysis audit cannot exist before the run."""
        report = protocol_check.check_fields(frozen())
        for label in ("Answer to the question", "Raw output", "Analysis audit"):
            self.assertNotIn(label, report.missing_must)
            self.assertNotIn(label, report.missing_should)


class TestCheckFileAsData(unittest.TestCase):
    """`check_protocol` hands every finding back as data; `print_report` only
    renders. A test asserts on fields, not on lines read back from stdout."""

    def _report(self, text: str):
        d = Path(tempfile.mkdtemp())
        path = d / "PROTOCOL-x.md"
        path.write_text(text, encoding="utf-8")
        tmpl = protocol_report.template_lines(TEMPLATE)
        return protocol_report.check_protocol(
            path, text, tmpl, protocol_history.repo_protocol_ids(path)
        )

    def test_a_filled_pilot_is_clean_and_does_not_block(self):
        r = self._report(pilot())
        self.assertIsNone(r.head_error)
        self.assertTrue(r.clean, r)
        self.assertFalse(r.blocks)
        self.assertEqual(r.musts, [])
        self.assertIn("should-field(s) due only at report time", r.pilot_note)

    def test_a_missing_must_field_is_data_and_blocks(self):
        r = self._report(pilot().replace("- **Unit:** one claim\n", ""))
        self.assertIn("Unit", r.missing_must)
        self.assertFalse(r.clean)
        self.assertTrue(r.blocks)
        self.assertEqual(r.musts, ["Unit"])

    def test_an_unreadable_head_is_the_only_finding(self):
        r = self._report("# x\n\nno block here\n")
        self.assertIsNotNone(r.head_error)
        self.assertTrue(r.blocks)
        self.assertEqual(r.missing_must, [])

    def test_the_prose_budget_counts_no_fence_and_no_table(self):
        text = pilot() + "```\n" + "x\n" * 400 + "```\n" + "| a |\n" * 400
        r = self._report(text)
        self.assertFalse(r.too_long, r.n_lines)
        padded = pilot() + "\n## Design\n" + "a line\n" * 400
        r = self._report(padded)
        self.assertTrue(r.too_long, r.n_lines)
        self.assertIn(
            "a shorter protocol (frozen)",
            self._report(frozen() + "\n## Design\n" + "a line\n" * 400).musts,
        )

    def test_print_report_renders_the_data_only(self):
        r = self._report(pilot().replace("- **Unit:** one claim\n", ""))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            protocol_report.print_report(r)
        self.assertIn("MISSING (must): Unit", out.getvalue())
        self.assertIn("must fields missing or empty", out.getvalue().splitlines()[-1])


class TestMain(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = protocol_report.main(argv)
        return code, out.getvalue()

    def test_template_itself_must_fail(self):
        """Expectation INVERTED on 2026-08-17 — and that is the point.

        Until then this test required the template itself to pass. That was
        the assumption covering the actual bug: a protocol indistinguishable
        from the template counted as filled. Exactly thus 28 protocols were
        reported clean while **none** contained a real model input/output
        example. The template consists of placeholders; it MUST fail now.
        """
        code, out = self._run([str(TEMPLATE)])
        self.assertEqual(code, 1)
        self.assertIn("PLACEHOLDER", out)

    def test_missing_must_exits_one(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-frozen-real.md"
            p.write_text(head() + REAL_FREEFORM_PROTOCOL, encoding="utf-8")
            code, out = self._run([d])
            self.assertEqual(code, 1)
            self.assertIn("MISSING (must): Terms of this protocol", out)
            self.assertIn("MISSING (must): Model I/O", out)

    def test_a_protocol_without_head_exits_one(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-frozen-real.md"
            p.write_text(REAL_FREEFORM_PROTOCOL, encoding="utf-8")
            code, out = self._run([d])
            self.assertEqual(code, 1)
            self.assertIn("HEAD (must): no [protocol] table", out)
            self.assertNotIn("MISSING", out)

    def test_no_args_exits_two(self):
        code, _ = self._run([])
        self.assertEqual(code, 2)


# --- Placeholder detection (2026-08-17) --------------------------------------
#
# The occasion: across 28 protocols NOT ONE contained a real model
# input/output example while the checker reported them clean — the word
# "Prompt" in the template placeholder satisfied it. The lines below are
# verbatim from experiments/13-akzeptanzregel/PROTOCOL-akzeptanzregel.md
# (2026-08-17, before the repair). German labels: placeholder detection reads
# any bold label; which ones are owed is the template's (English) list.

REAL_PLACEHOLDER_BLOCK = """\
## Setup

- **Modell / Tool:** <Alias aus `models.toml` (+ Fallback-Alias) — nie
  Endpoint/ID hartkodieren>
- **Prompt (wörtlich):** <der echte Prompt — gehört in die Note, nicht nur ins Skript>
- **Modell-I/O:** <*rein:* welche Felder; *raus instruiert:* verlangtes Format>
- **Bedeutung des Gold-Labels:** <was heisst die positive Klasse WIRKLICH?>
"""


class TestPlaceholders(unittest.TestCase):
    def test_finds_the_four_real_placeholders(self):
        found = protocol_check.placeholder_fields(REAL_PLACEHOLDER_BLOCK)
        labels = [lb for _, lb in found]
        self.assertIn("Prompt (wörtlich)", labels)
        self.assertIn("Modell-I/O", labels)
        self.assertIn("Modell / Tool", labels)
        self.assertIn("Bedeutung des Gold-Labels", labels)

    def test_a_filled_field_is_no_placeholder(self):
        filled = (
            "- **Modell / Tool:** Alias `qwen` (qwen2.5:7b, ollama)\n"
            "- **Prompt (wörtlich):** siehe Codeblock unten\n"
        )
        self.assertEqual(protocol_check.placeholder_fields(filled), [])

    def test_justified_na_is_no_placeholder(self):
        # The rule allows "n/a — <why>"; the reason must be there.
        na = "- **Modell-I/O:** n/a — dieser Lauf ruft kein Modell auf.\n"
        self.assertEqual(protocol_check.placeholder_fields(na), [])

    def test_placeholder_in_a_must_field_weighs_more(self):
        text = (
            head() + "- **Prompt (verbatim, per variant):** <the real prompt>\n"
            "- **Model I/O:** <in · out>\n"
            "- **Yield per stage:** <expected vs. obtained>\n"
            "- **Next step:** <…>\n"
        )
        report = protocol_check.check_fields(text)
        self.assertEqual(
            [lb for _, lb in report.must_holes],
            ["Prompt (verbatim, per variant)", "Model I/O"],
        )
        # Next step is written after the run (Summary): no hole before one.
        self.assertEqual([lb for _, lb in report.soft_holes], ["Yield per stage"])

    def test_pipeline_exits_one_on_must_placeholder(self):
        rc, out = run_main(
            pilot().replace("[C1] AUC > 0.6", "<how do we recognise it?>")
        )
        self.assertEqual(rc, 1)
        self.assertIn("PLACEHOLDER ONLY (must): Success / failure criterion", out)

    def test_a_german_label_is_not_the_field(self):
        """Exact template labels only: `Modell-I/O` filled leaves `Model I/O` missing."""
        text = pilot().replace("- **Model I/O:**", "- **Modell-I/O:**")
        rc, out = run_main(text)
        self.assertEqual(rc, 1)
        self.assertIn("MISSING (must): Model I/O", out)


class TestTemplateLines(unittest.TestCase):
    def test_verbatim_template_line_is_recognised(self):
        if not TEMPLATE.exists():
            self.skipTest("template absent")
        lines = protocol_report.template_lines(TEMPLATE)
        self.assertTrue(lines, "template yields no comparison lines")
        # Any long template line must be recognised again.
        sample = next(iter(lines))
        self.assertIn(sample.strip(), lines)


class TestFrozenWithoutExample(unittest.TestCase):
    """`frozen = true` without a rendered example (2026-08-18).

    Occasion (MH): the flow had to change — register first, then run the
    pipeline ONCE over a handful of real items, put the result into the
    protocol as the example, and only then freeze. Freezing on an unchecked
    instrument freezes the error in.
    """

    NO_EXAMPLE = (
        "- **Prompt:** see block\n\n  ```text\n  Is this fallacious?\n  ```\n",
        "- **Prompt:** n/a — no model\n",
    )

    def test_frozen_without_code_block_fails(self):
        rc, out = run_main(frozen().replace(*self.NO_EXAMPLE))
        self.assertEqual(rc, 1)
        self.assertIn("not a single", out)

    def test_frozen_with_code_block_passes(self):
        rc, out = run_main(frozen())
        self.assertEqual(rc, 0, out)

    def test_the_head_block_is_no_example(self):
        """The ```toml head is a fenced block too; it must not count."""
        self.assertEqual(
            protocol_report.code_blocks(frozen().replace(*self.NO_EXAMPLE)), 0
        )
        self.assertEqual(protocol_report.code_blocks(frozen()), 1)

    def test_unfrozen_without_code_block_is_no_must_failure(self):
        # A pre-registered protocol may exist without an example — it
        # precisely does NOT claim to be frozen.
        _, out = run_main(pilot().replace(*self.NO_EXAMPLE))
        self.assertNotIn("not a single", out)


class TestGraduationGate(unittest.TestCase):
    """`frozen = true` escalates should to must (2026-08-18) — pilot light, report heavy."""

    def test_pilot_without_frozen_only_warns(self):
        rc, out = run_main(pilot())
        self.assertEqual(rc, 0, out)  # should missing -> note, no failure
        self.assertIn(f"{len(SHOULD)} should-field(s) due only at report time", out)

    def test_frozen_makes_should_a_must(self):
        rc, out = run_main(pilot(frozen=True))
        self.assertEqual(rc, 1)
        for label in SHOULD:
            self.assertIn(f"MISSING (must): {label}", out)

    def test_the_graduation_lives_in_owed(self):
        h = protocol_block.head(pilot(frozen=True))
        must, should = protocol_check.owed(pilot(frozen=True), h)
        self.assertEqual([f.label for f in must], MUST + SHOULD)
        self.assertEqual(should, [])


class TestPromptAndExample(unittest.TestCase):
    """Verbatim prompt + one real example are musts (2026-08-20).

    That is the core of the protocol: seeing later what really went in and
    came out. A Prompt field without a code block is a must failure
    (paraphrased instead of recorded). Raw output is written after the run:
    owed once a measure run is documented, never before (TODO 8).
    """

    PARAPHRASE = pilot().replace(
        "- **Prompt:** see block\n\n  ```text\n  Is this fallacious?\n  ```\n",
        "- **Prompt:** asks, in effect, for a fallacy\n",
    )

    def test_prompt_without_code_block_is_a_must_failure(self):
        rc, out = run_main(self.PARAPHRASE)
        self.assertEqual(rc, 1)
        self.assertIn("no code block", out)

    def test_prompt_na_needs_no_code_block(self):
        """`- **Prompt:** n/a — no model` is no prompt to paraphrase; the old
        regex let `\\*{0,2}` backtrack past the n/a and flagged it."""
        rc, out = run_main(
            self.PARAPHRASE.replace("asks, in effect, for a fallacy", "n/a — no model")
        )
        self.assertNotIn("no code block", out)
        self.assertEqual(rc, 0, out)

    def test_raw_output_is_not_owed_before_the_run(self):
        rc, out = run_main(pilot())
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Raw output", out)

    def test_empty_raw_output_after_a_measure_run_is_a_must_failure(self):
        text = (
            pilot() + "\n## Result\n\n- **Raw output:** —\n"
            "\n## Runs\n\n- 2026-09-06T10-00-00_aa11 — the full run\n"
        )
        rc, out = run_main(text)
        self.assertEqual(rc, 1)
        self.assertIn("measure run in the run list", out)

    def test_raw_output_is_not_owed_without_a_model_at_seconds(self):
        """A count has no prompt+answer pair to show: the field is `sm`, owed
        only with a model named (cloud probe 2026-10-12 filled it with n/a)."""
        text = (
            pilot(cost="seconds").replace(
                "- **Model / tool:** haiku", "- **Model / tool:** n/a — deterministic"
            )
            + "\n## Summary\n\n- **Result:** The mean is 3.5 documents per case.\n"
            "- **Limits:** One count over 12 cases.\n- **Next step:** none\n"
            + "\n## Result\n\n- **Answer to the question:** 3.5 (2026-09-06T10-00-00_aa11)\n"
            "\n## Runs\n\n- 2026-09-06T10-00-00_aa11 — the full run\n"
        )
        rc, out = run_main(text)
        self.assertNotIn("Raw output", out)
        self.assertEqual(rc, 0, out)

    def test_a_count_at_seconds_owes_neither_criterion_nor_limits(self):
        """Without a model the seconds cut has no criterion, no admissibility
        condition, and after the run only the Result line of the Summary
        (decisions 2026-10-12, five cloud probes)."""
        base = pilot(cost="seconds").replace(
            "- **Model / tool:** haiku", "- **Model / tool:** n/a — deterministic"
        )
        lines = [
            ln
            for ln in base.splitlines()
            if not ln.startswith(
                ("- **Success / failure criterion:**", "- **Admissibility condition:**")
            )
        ]
        text = (
            "\n".join(lines)
            + "\n## Summary\n\n- **Result:** The mean is 3.5 documents per case.\n"
            + "\n## Result\n\n- **Answer to the question:** 3.5 (2026-09-06T10-00-00_aa11)\n"
            "\n## Runs\n\n- 2026-09-06T10-00-00_aa11 — the full run\n"
        )
        rc, out = run_main(text)
        self.assertEqual(rc, 0, out)
        for label in (
            "Success / failure criterion",
            "Admissibility condition",
            "Limits",
            "Next step",
            "Raw output",
        ):
            self.assertNotIn(label, out)
        # the twin: a model named brings the criterion back
        rc, out = run_main(text.replace("n/a — deterministic", "haiku"))
        self.assertEqual(rc, 1)
        self.assertIn("Success / failure criterion", out)

    def test_a_probe_run_owes_no_result(self):
        text = (
            pilot() + "\n## Result\n\n- **Raw output:** —\n"
            "\n## Runs\n\n- 2026-09-06T10-00-00_aa11 — probe, 10 calls\n"
        )
        rc, out = run_main(text)
        self.assertNotIn("measure run in the run list", out)
        self.assertEqual(rc, 0, out)

    def test_written_raw_output_after_a_measure_run_passes(self):
        text = (
            pilot()
            + "\n## Summary\n\n- **Result:** The classifier separates the two classes"
            " well on the held-out set.\n- **Limits:** One run on one split.\n"
            "- **Next step:** none\n"
            + "\n## Result\n\n- **Answer to the question:** AUC 0.91 "
            "(2026-09-06T10-00-00_aa11)\n- **Raw output:** see output/examples.md\n"
            "\n## Runs\n\n- 2026-09-06T10-00-00_aa11 — the full run\n"
        )
        rc, out = run_main(text)
        self.assertEqual(rc, 0, out)

    def test_a_summary_without_limits_after_a_measure_run_fails(self):
        # The twin above passes; the same protocol without Limits must not.
        text = (
            pilot()
            + "\n## Summary\n\n- **Result:** The classifier separates the two classes"
            " well on the held-out set.\n- **Next step:** none\n"
            + "\n## Result\n\n- **Answer to the question:** AUC 0.91 "
            "(2026-09-06T10-00-00_aa11)\n- **Raw output:** see output/examples.md\n"
            "\n## Runs\n\n- 2026-09-06T10-00-00_aa11 — the full run\n"
        )
        rc, out = run_main(text)
        self.assertEqual(rc, 1, out)
        self.assertIn("Limits", out)


class TestPilotStampNotFrozen(unittest.TestCase):
    """The template's legend MENTIONS the frozen rule — that must not make a
    fresh stamp look frozen (2026-08-20: '`Frozen before run: yes` makes them
    musts' in the head text made every fresh pilot stamp look frozen; all
    should-gaps were wrongly escalated to musts). Frozen is now one typed
    value in the head."""

    def test_template_head_is_not_frozen(self):
        h = protocol_block.head(TEMPLATE.read_text(encoding="utf-8"))
        self.assertIs(h.frozen, False)

    def test_prose_saying_frozen_does_not_freeze(self):
        report = protocol_check.check_fields(pilot() + "- **Frozen before run:** yes\n")
        self.assertFalse(report.frozen)


class TestTerms(unittest.TestCase):
    """Terms are a must (2026-08-19).

    The template asks for them twice — in the context block and after the
    dry run — and the checker looked at neither. 20 of 31 protocols in the
    repo named not a single term while five definition notes sat next door.
    """

    TERMS = "- **Terms of this protocol:** n/a — standard vocabulary\n"

    def test_without_terms_the_must_field_is_missing(self):
        rc, out = run_main(pilot().replace(self.TERMS, ""))
        self.assertEqual(rc, 1)
        self.assertIn("MISSING (must): Terms of this protocol", out)

    def test_only_the_admissibility_label_satisfies_the_field(self):
        """The field is "Admissibility condition" (TODO 7); its earlier labels
        "Stop rule", "Kill", "Abbruch" no longer pass (TODO 8)."""
        adm = "- **Admissibility condition:** [A1] yield >= 90%\n"
        for wording in (
            "- **Stop rule:** LR stays at 1.\n",
            "- **Kill:** LR stays at 1.\n",
            "- **Abbruchkriterium:** LR bleibt bei 1.\n",
            "- **Zulassungsbedingung:** [A1] Ausbeute >= 90 %.\n",
        ):
            with self.subTest(wording):
                report = protocol_check.check_fields(pilot().replace(adm, wording))
                self.assertEqual(report.missing_must, ["Admissibility condition"])

    def test_a_half_sentence_suffices(self):
        text = pilot().replace(
            self.TERMS,
            "- **Terms of this protocol:** Sog = Tendenz "
            "des Bildes, Ko-Praesenz zu zeigen.\n",
        )
        rc, out = run_main(text)
        self.assertEqual(rc, 0, out)

    def test_placeholder_does_not_count_as_filled(self):
        # The label is there, the field is not filled — exactly the gap
        # closed for the prompt field on 2026-08-17.
        rc, out = run_main(
            pilot().replace(self.TERMS, "- **Terms of this protocol:** <every label>\n")
        )
        self.assertEqual(rc, 1)
        self.assertIn("PLACEHOLDER ONLY (must): Terms of this protocol", out)

    def test_clarified_terms_is_not_the_must_field(self):
        """The Checks section's "Clarified terms" is a different field: its
        placeholder is a soft hole, and it does not stand in for the must."""
        text = pilot().replace(
            self.TERMS, "- **Clarified terms:** <what was ambiguous>\n"
        )
        report = protocol_check.check_fields(text)
        self.assertEqual(report.missing_must, ["Terms of this protocol"])
        self.assertEqual([lb for _, lb in report.soft_holes], ["Clarified terms"])


class TestHelpFlag(unittest.TestCase):
    def test_help_prints_usage_and_exits_zero(self):
        """`protocol-check --help` used to read the flag as a filename and
        answer "nicht lesbar" — whoever looks for the flags must find usage."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = protocol_report.main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage: protocol-check", buf.getvalue())


class TestSeriesDetector(unittest.TestCase):
    """A follow-up registration appended to the same protocol is a series
    (2026-09-06): one file had grown to 649 lines out of three experiments,
    each under a "... (deklariert vor dem Lauf)" heading. One question per
    protocol — the follow-up gets its own PROTOCOL-s<N> file."""

    def test_declared_follow_up_heading_warns(self):
        rc, out = run_main(
            pilot() + "## Lauf B — Richterwechsel (deklariert vor dem Lauf)\n"
        )
        self.assertIn("PROTOCOL-s<N>", out)
        self.assertEqual(rc, 0, "warning, not a failure")

    def test_plain_sections_do_not_trigger(self):
        rc, out = run_main(pilot() + "## Setup\n## Result\n")
        self.assertNotIn("PROTOCOL-s<N>", out)


class TestDocumentedRunsNotCountedAsProse(unittest.TestCase):
    """The documented runs are mandatory content, not prose (2026-09-06): 93 of
    a protocol's 409 lines were its run list — the length budget must not teach
    people to stop documenting runs."""

    def test_a_huge_run_list_does_not_flag_the_protocol(self):
        run_list = (
            "## Runs (documented runs)\n" + "- 2026-09-06T10-00-00_aa11 — x\n" * 400
        )
        _, out = run_main(pilot() + run_list)
        self.assertNotIn("prose lines (tables/code excluded)", out)


class TestAuditFields(unittest.TestCase):
    """The two audits (2026-09-08). Occasion: ten small errors in four weeks —
    a sign flip between BT score and log-odds, r2 fitted and scored on the
    same anchors, a gate without a positive control, a probe writing into the
    run's output file; none caught by the chain itself. Hence two audits
    (lab standard LAB-015 Preflight audit before freezing code vs. intent before freezing, LAB-050 Analysis audit before reporting
    evaluation vs. frozen criterion before reporting). The preflight audit is
    now a head value (`preflight_audit`), the analysis audit a field written
    after the run."""

    def test_template_stamps_both(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(protocol_block.head(text).preflight_audit, "")
        self.assertIn(
            "Analysis audit",
            {f.label.split(" †")[0] for f in protocol_check.fields(text)},
        )

    def test_the_preflight_audit_is_read_from_the_head(self):
        line = "2026-09-08 · scope sha 3f9a1c2b7e04 · 4 findings (2 blockers fixed)"
        self.assertEqual(
            protocol_block.head(head(preflight_audit=line)).preflight_audit, line
        )

    def test_an_analysis_placeholder_is_not_owed_before_the_run(self):
        rc, out = run_main(
            frozen() + "- **Analysis audit †:** <date · scope sha · N findings>\n"
        )
        self.assertEqual(rc, 0, out)
        self.assertIn("placeholder only: Analysis audit", out)

    def test_filled_analysis_passes(self):
        rc, out = run_main(
            frozen() + "- **Analysis audit †:** 2026-09-09 · scope sha "
            "8b1e6d0a4c31 · 2 findings (1 blocker fixed)\n"
        )
        self.assertEqual(rc, 0, out)


class TestResolutionCheckGate(unittest.TestCase):
    """The resolution check field (LAB-016 Resolution check before freezing, 2026-09-09) is a should: owed as a
    must once frozen; the template's own "Answer form + resolution †" field
    must NOT stand in for it."""

    RESOLUTION = "- **Resolution check:** perfect effect fires, null stays silent\n"

    def test_stamped_placeholder_fails_once_frozen(self):
        rc, out = run_main(
            frozen().replace(
                self.RESOLUTION,
                "- **Resolution check (ZERO calls):** "
                "<perfect effect fires? null stays silent?>\n",
            )
        )
        self.assertEqual(rc, 1, out)
        self.assertIn("PLACEHOLDER ONLY (must): Resolution check", out)

    def test_filled_passes(self):
        rc, out = run_main(
            frozen().replace(
                self.RESOLUTION,
                "- **Resolution check:** perfect effect p = 0.0002 (fires), "
                "null p = 0.4791 (silent), 8 draws as in the run\n",
            )
        )
        self.assertEqual(rc, 0, out)

    def test_absent_field_is_a_must_gap_once_frozen(self):
        rc, out = run_main(frozen().replace(self.RESOLUTION, ""))
        self.assertEqual(rc, 1, out)
        self.assertIn("MISSING (must): Resolution check", out)

    def test_german_label_does_not_count(self):
        rc, out = run_main(
            frozen().replace(
                self.RESOLUTION, "- **Auflösungsprobe:** perfekter Effekt feuert\n"
            )
        )
        self.assertEqual(rc, 1, out)
        self.assertIn("MISSING (must): Resolution check", out)

    def test_answer_form_resolution_is_not_caught(self):
        """Guard against the near-collision: 'Answer form + resolution †' is
        its own report field, never the resolution check."""
        text = frozen().replace(
            self.RESOLUTION, "- **Answer form + resolution †:** <how many states>\n"
        )
        report = protocol_check.check_fields(text)
        self.assertEqual(report.missing_must, ["Resolution check"])
        self.assertIn("Answer form + resolution †", [lb for _, lb in report.must_holes])

    def test_template_stamps_the_field(self):
        self.assertIn("Resolution check", TEMPLATE.read_text(encoding="utf-8"))


class TestProseBudgetEscalation(unittest.TestCase):
    """A frozen protocol escalates prose budgets from warning to must (2026-09-13)."""

    INTENT = "## Intent\n" + "Eine Zeile Prose.\n" * 40

    def test_frozen_oversized_section_exits_one(self):
        rc, out = run_main(frozen() + self.INTENT)
        self.assertEqual(rc, 1, out)
        self.assertIn("OVERSIZED (must)", out)
        self.assertIn("Intent", out)

    def test_frozen_global_over_350_exits_one(self):
        rc, out = run_main(frozen() + "Eine Zeile Prose.\n" * 360)
        self.assertEqual(rc, 1, out)
        self.assertIn("OVERSIZED (must)", out)

    def test_unfrozen_oversized_section_warns_but_exits_zero(self):
        rc, out = run_main(pilot() + self.INTENT)
        self.assertEqual(rc, 0, out)
        self.assertIn("oversized", out)
        self.assertNotIn("OVERSIZED (must)", out)


class TestHeadValues(unittest.TestCase):
    """The head is typed data; a value outside its choices is one loud MUST
    failure naming the field, never a silent "not found" (TODO 8)."""

    def test_the_measurement_short_form_is_rejected(self):
        rc, out = run_main(pilot(type="measurement"))
        self.assertEqual(rc, 1)
        self.assertIn("HEAD (must): [protocol] type = 'measurement'", out)

    def test_another_standard_is_rejected(self):
        """A newer or older standard gets one hard failure and zero other
        findings — a gate judging another template produces false positives
        (2026-09-14: a pre-0.15 checker flagged the 0.15 template's stamped
        preamble as "verbatim template text" for a whole session)."""
        for std in ("0.99", "0.17", "0.15"):
            with self.subTest(std):
                rc, out = run_main(
                    pilot().replace('standard = "0.19"', f'standard = "{std}"')
                )
                self.assertEqual(rc, 1, out)
                self.assertIn(f"HEAD (must): [protocol] standard = '{std}'", out)
                self.assertNotIn("MISSING", out)
                self.assertNotIn("template text", out)

    def test_template_stamps_the_supported_standard(self):
        h = protocol_block.head(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(h.standard, protocol_block.STANDARD)


class TestExclusions(unittest.TestCase):
    """Exclusions is a must; Gate labels and Randomness controls are stamped
    should fields."""

    EXCL = "- **Exclusions / filters:** none\n"

    def test_without_exclusions_exits_one(self):
        rc, out = run_main(pilot().replace(self.EXCL, ""))
        self.assertEqual(rc, 1, out)
        self.assertIn("MISSING (must): Exclusions / filters", out)

    def test_with_exclusions_passes(self):
        rc, out = run_main(pilot())
        self.assertEqual(rc, 0, out)

    def test_template_stamps_exclusions(self):
        self.assertIn("Exclusions / filters", TEMPLATE.read_text(encoding="utf-8"))

    def test_template_stamps_gate_labels(self):
        self.assertIn("Gate labels (expected)", TEMPLATE.read_text(encoding="utf-8"))

    def test_template_stamps_randomness(self):
        self.assertIn("Randomness controls", TEMPLATE.read_text(encoding="utf-8"))


class TestIntentBudgetCalibration(unittest.TestCase):
    """Intent budget 35 (calibration 2026-09-15, n=94): the intent-id
    registrations moved mandatory content into Intent — the disciplined
    confirmatory cluster tops out at 35 prose lines and must pass."""

    def test_intent_35_lines_is_within_budget(self):
        text = "## Intent\n" + "Prose line.\n" * 35
        self.assertEqual(protocol_report.oversized_sections(text), [])

    def test_intent_36_lines_is_over_budget(self):
        text = "## Intent\n" + "Prose line.\n" * 36
        self.assertEqual(protocol_report.oversized_sections(text), [("Intent", 36, 35)])


class TestProseLinesReadFencesLikeTheParser(unittest.TestCase):
    """Audit 2026-10-18: `prose_lines` toggled on ``` by hand, so a `~~~`
    fence and a ``` nested in a fence counted code as prose; the one fence
    walker (`protocol_block.fence_spans`) reads both right."""

    def test_tilde_fence_is_not_prose(self):
        text = "## Intent\nProse.\n~~~\ncode\ncode\n~~~\nMore prose.\n"
        lines = [s for _, s in protocol_report.prose_lines(text)]
        self.assertEqual(lines, ["## Intent", "Prose.", "More prose."])

    def test_nested_fence_does_not_reopen_prose(self):
        text = (
            "## Intent\n````\nask for ```toml output\n```\nstill code\n````\nProse.\n"
        )
        lines = [s for _, s in protocol_report.prose_lines(text)]
        self.assertEqual(lines, ["## Intent", "Prose."])


class TestStampedLegendIsNotTemplateText(unittest.TestCase):
    """The template's preamble (before the first `## `) is a stamped legend
    that survives filling — the verbatim-template check must not flag it
    (2026-09-14/15: every freshly stamped protocol was flagged forever)."""

    def test_preamble_lines_are_excluded(self):
        lines = protocol_report.template_lines(protocol_report.find_template(None))
        self.assertTrue(lines, "template not found")
        self.assertFalse([s for s in lines if "A checklist, not a copy-form" in s])
        # The Head section (pointer and toml block) stays by design, like the preamble.
        self.assertFalse(
            [s for s in lines if "the cuts by tier and the intent ids" in s]
        )

    def test_body_instruction_lines_still_count(self):
        lines = protocol_report.template_lines(protocol_report.find_template(None))
        # An instruction line from inside a section stays in the set.
        self.assertTrue([s for s in lines if "error direction" in s], lines)


class TestCostTier(unittest.TestCase):
    """The cost tier (2026-10-05) is a head value: `cost` in [protocol]."""

    def test_template_stamps_cost_as_placeholder(self):
        self.assertIsNone(
            protocol_block.head(TEMPLATE.read_text(encoding="utf-8")).cost
        )

    def test_the_tier_is_read_from_the_head(self):
        for tier in protocol_block.COST_TIERS:
            self.assertEqual(protocol_block.head(head(cost=tier)).cost, tier)

    def test_a_typo_is_a_loud_error(self):
        """`Cost: second` used to read as undeclared and so as `hours`."""
        with self.assertRaisesRegex(
            protocol_block.BlockError, r"\[protocol\] cost = 'second'"
        ):
            protocol_block.head(head(cost="second"))

    def test_a_placeholder_is_a_must_gap(self):
        report = protocol_check.check_fields(pilot(cost="<seconds | minutes | hours>"))
        self.assertEqual(report.missing_must, ["[protocol] cost"])

    def test_a_prose_cost_line_is_not_the_tier(self):
        text = pilot(cost="<seconds | minutes | hours>") + "- **Cost:** seconds\n"
        self.assertEqual(
            protocol_check.check_fields(text).missing_must, ["[protocol] cost"]
        )


if __name__ == "__main__":
    unittest.main()
