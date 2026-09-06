"""Tests for protocol-check.py against real protocol material.

The checker turns freely written protocols into a pass/fail decision, so it
gets the parser treatment (Arbeitsstandard §2): tested with real raw text.
The frozen excerpt below is verbatim from experiments/_archiv/17-bruchstufe-nli/PROTOCOL-bruchstufe-nli.md
(2026-08-11), one of the five freely written protocols that omitted exactly
"Typ" and "Modell-I/O" — the two fields whose omission caused bad runs on
2026-08-13. It names no term either, which is why it also fails the Begriffe
field added on 2026-08-19. The excerpt is frozen here so the test keeps working
after the live protocol gets fixed.
"""

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "labkit" / "protocol_check.py"
TEMPLATE = REPO / "labkit" / "experiment-protocol.md.template"

spec = importlib.util.spec_from_file_location("protocol_check", CHECKER)
assert spec is not None and spec.loader is not None
protocol_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol_check)

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


class TestCheckText(unittest.TestCase):
    def test_template_passes_all_fields(self):
        missing_must, missing_should = protocol_check.check_text(
            TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(missing_must, [])
        self.assertEqual(missing_should, [])

    def test_real_freeform_protocol_misses_terms_type_and_model_io(self):
        missing_must, _ = protocol_check.check_text(REAL_FREEFORM_PROTOCOL)
        self.assertEqual(missing_must, [
            "Terms (every label with a half-sentence gloss)",
            "Type (exploratory / confirmatory)",
            "Model I/O / prompt (verbatim)",
            "Raw output (one real example + model output)",
        ])

    def test_explicit_na_counts_as_present(self):
        text = (REAL_FREEFORM_PROTOCOL
                + "\nBegriffe: Bruchstufe = wie stark der Seed die Praemisse bricht."
                + "\nTyp: explorativ."
                + "\nModell-I/O: n/a — kein LLM in diesem Lauf."
                + "\nRoh-Output: n/a — kein LLM in diesem Lauf.\n")
        missing_must, _ = protocol_check.check_text(text)
        self.assertEqual(missing_must, [])

    def test_empty_text_misses_everything(self):
        missing_must, missing_should = protocol_check.check_text("")
        self.assertEqual(len(missing_must), len(protocol_check.MUST))
        self.assertEqual(len(missing_should), len(protocol_check.SHOULD))


class TestMain(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = protocol_check.main(argv)
        return code, out.getvalue()

    def test_template_names_every_field(self):
        """The template mentions every must and should field."""
        missing_must, missing_should = protocol_check.check_text(
            TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(missing_must, [])
        self.assertEqual(missing_should, [])

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
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-frozen-real.md"
            p.write_text(REAL_FREEFORM_PROTOCOL, encoding="utf-8")
            code, out = self._run([d])
            self.assertEqual(code, 1)
            self.assertIn("MISSING (must): Type", out)
            self.assertIn("MISSING (must): Model I/O", out)

    def test_no_args_exits_two(self):
        code, _ = self._run([])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()


# --- Placeholder detection (2026-08-17) --------------------------------------
#
# The occasion: across 28 protocols NOT ONE contained a real model
# input/output example while the checker reported them clean — the word
# "Prompt" in the template placeholder satisfied it. The lines below are
# verbatim from experiments/13-akzeptanzregel/PROTOCOL-akzeptanzregel.md
# (2026-08-17, before the repair). German on purpose: grown protocols are
# German-filled and the checker's contract is bilingual.

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
        filled = ("- **Modell / Tool:** Alias `qwen` (qwen2.5:7b, ollama)\n"
                  "- **Prompt (wörtlich):** siehe Codeblock unten\n")
        self.assertEqual(protocol_check.placeholder_fields(filled), [])

    def test_justified_na_is_no_placeholder(self):
        # The rule allows "n/a — <why>"; the reason must be there.
        na = "- **Modell-I/O:** n/a — dieser Lauf ruft kein Modell auf.\n"
        self.assertEqual(protocol_check.placeholder_fields(na), [])

    def test_placeholder_in_a_must_field_weighs_more(self):
        self.assertEqual(protocol_check.severity_of("Prompt (wörtlich)"), "must")
        self.assertEqual(protocol_check.severity_of("Modell-I/O"), "must")
        self.assertEqual(protocol_check.severity_of("Ausbeute je Stufe"), "should")
        self.assertEqual(protocol_check.severity_of("Nächster Schritt"), "other")

    def test_pipeline_exits_one_on_must_placeholder(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text("# x\nHypothese, Erfolg, Abbruch, explorativ, Anker.\n"
                         + REAL_PLACEHOLDER_BLOCK, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            self.assertEqual(rc, 1)
            self.assertIn("PLACEHOLDER ONLY (must)", buf.getvalue())


class TestTemplateLines(unittest.TestCase):

    def test_verbatim_template_line_is_recognised(self):
        if not TEMPLATE.exists():
            self.skipTest("template absent")
        lines = protocol_check.template_lines(TEMPLATE)
        self.assertTrue(lines, "template yields no comparison lines")
        # Any long template line must be recognised again.
        sample = next(iter(lines))
        self.assertIn(sample.strip(), lines)


class TestFrozenWithoutExample(unittest.TestCase):
    """"Frozen before run: yes" without a rendered example (2026-08-18).

    Occasion (MH): the flow had to change — register first, then run the
    pipeline ONCE over a handful of real items, put the result into the
    protocol as the example, and only then freeze. Freezing on an unchecked
    instrument freezes the error in.
    """

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    BASE = ("# x\nBegriffe, Hypothese, Erfolg, Abbruch, explorativ, Anker, Prompt, "
            "Roh-Output, Instrumentenprobe, Einordnung, Rivalen, Fehlerrichtung, "
            "Skopus, freie Knoepfe, Prognose, gold, Ausbeute, Ergebnis.\n")

    def test_frozen_yes_without_code_block_fails(self):
        rc, out = self._run(self.BASE + "- **Frozen before run:** ja\n")
        self.assertEqual(rc, 1)
        self.assertIn("not a single", out)

    def test_frozen_yes_with_code_block_passes(self):
        rc, out = self._run(self.BASE + "- **Frozen before run:** ja\n\n```\nAnswer: Yes\n```\n")
        self.assertEqual(rc, 0)

    def test_frozen_no_without_code_block_is_no_must_failure(self):
        # A pre-registered protocol may exist without an example — it
        # precisely does NOT claim to be frozen.
        rc, out = self._run(self.BASE + "- **Frozen before run:** nein, noch nicht\n")
        self.assertNotIn("not a single", out)


class TestGraduationGate(unittest.TestCase):
    """Frozen: yes escalates should to must (2026-08-18) — pilot light, report heavy."""

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    # Pilot minimum present, should fields absent entirely (German content
    # on purpose — the contract is bilingual):
    PILOT = ("# x\nBegriffe, Frage, Hypothese, Erfolg, Abbruch/Kill, explorativ, Anker,\n"
             "Prompt und Modell-I/O:\n\n```\nAnswer: Yes\n```\n"
             "Roh-Output: siehe output/beispiele.md.\n"
             "Instrumentenprobe: gelaufen.\n")

    def test_pilot_without_frozen_only_warns(self):
        rc, out = self._run(self.PILOT)
        self.assertEqual(rc, 0, out)           # should missing -> warning, no failure

    def test_frozen_yes_makes_should_a_must(self):
        rc, out = self._run(self.PILOT + "\n- **Frozen before run:** ja\n")
        self.assertEqual(rc, 1)
        self.assertIn("must once frozen: yes", out)


class TestPromptAndExample(unittest.TestCase):
    """Verbatim prompt + one real example with output are musts (2026-08-20).

    That is the core of the protocol: seeing later what really went in and
    came out. Two tightenings: a mentioned prompt without a code block is a
    must failure (paraphrased instead of recorded), and the raw-output must
    field demands an example + model output — embedded, linked, or as a
    justified n/a.
    """

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    BASE = ("# x\nBegriffe, Frage, Erfolg, Kill, explorativ, Anker, "
            "Frozen before run: nein.\n")

    def test_prompt_without_code_block_is_a_must_failure(self):
        rc, out = self._run(self.BASE + "Prompt: fragt sinngemaess nach Fallacy.\n"
                            + "Roh-Output: siehe output/beispiele.md.\n")
        self.assertEqual(rc, 1)
        self.assertIn("no code block", out)

    def test_missing_raw_output_is_a_must_failure(self):
        rc, out = self._run(self.BASE + "Prompt:\n\n```\nIs this fallacious?\n```\n")
        self.assertEqual(rc, 1)
        self.assertIn("MISSING (must): Raw output", out)

    def test_both_present_passes(self):
        rc, out = self._run(self.BASE + "Prompt:\n\n```\nIs this fallacious?\n```\n"
                            + "Roh-Output: siehe output/beispiele.md.\n")
        self.assertEqual(rc, 0, out)


class TestPilotStampNotFrozen(unittest.TestCase):
    """The template head MENTIONS the frozen rule — that must not trip the
    FROZEN_YES detector (2026-08-20: '`Frozen before run: yes` makes them
    musts' in the head text made every fresh pilot stamp look frozen; all
    should-gaps were wrongly escalated to musts). The head therefore avoids
    the field pattern."""

    def test_pilot_part_is_not_frozen(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        pilot = text.split("<!-- report:start")[0]
        self.assertIsNone(protocol_check.FROZEN_YES.search(pilot))
        self.assertIsNotNone(protocol_check.FROZEN_NO.search(pilot))


class TestTerms(unittest.TestCase):
    """Terms are a must (2026-08-19).

    The template asks for them twice — in the context block and after the
    dry run — and the checker looked at neither. 20 of 31 protocols in the
    repo named not a single term while five definition notes sat next door.
    German fixture labels on purpose: grown protocols carry them.
    """

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    def test_without_terms_the_must_field_is_missing(self):
        missing_must, _ = protocol_check.check_text("# x\nHypothese: A schlaegt B.\n")
        self.assertIn("Terms (every label with a half-sentence gloss)", missing_must)

    def test_stop_rule_vocabulary_satisfies_the_field(self):
        """The field label moved from "Kill criterion" to "Stop rule"; old
        protocols keep passing via kill/Abbruch, new ones via stop rule."""
        base = ("# x\nTerms: n/a. Question: A>B. Success: AUC. Type: exploratory. "
                "Anchor: swap. Prompt + raw output: n/a — no model.\n")
        for wording in ("Stop rule: LR stays at 1.", "Kill: LR stays at 1.",
                        "Abbruchkriterium: LR bleibt bei 1."):
            missing_must, _ = protocol_check.check_text(base + wording)
            self.assertNotIn("Stop rule", "".join(missing_must), wording)

    def test_a_half_sentence_suffices(self):
        text = "# x\nBegriffe: Sog = Tendenz des Bildes, Ko-Praesenz zu zeigen.\n"
        missing_must, _ = protocol_check.check_text(text)
        self.assertNotIn("Terms (every label with a half-sentence gloss)", missing_must)

    def test_glossary_and_terminology_count_too(self):
        for wort in ("Glossar: siehe notes/messung/pipeline-glossar.md",
                     "Terminologie folgt dem Standard."):
            missing_must, _ = protocol_check.check_text("# x\n" + wort + "\n")
            self.assertNotIn("Terms (every label with a half-sentence gloss)",
                             missing_must, f"'{wort}' should satisfy the field")

    def test_placeholder_does_not_count_as_filled(self):
        # The keyword is there, the field is not filled — exactly the gap
        # closed for the prompt field on 2026-08-17.
        rc, out = self._run("# x\n- **Begriffe dieses Protokolls:** <jedes Etikett>\n")
        self.assertEqual(rc, 1)
        self.assertIn("PLACEHOLDER ONLY (must): Begriffe", out)

    def test_severity_of_maps_both_template_labels_to_must(self):
        for label in ("Begriffe dieses Protokolls", "Geklaerte Begriffe"):
            self.assertEqual(protocol_check.severity_of(label), "must", label)


class TestHelpFlag(unittest.TestCase):
    def test_help_prints_usage_and_exits_zero(self):
        """`protocol-check --help` used to read the flag as a filename and
        answer "nicht lesbar" — whoever looks for the flags must find usage."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = protocol_check.main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage: protocol-check", buf.getvalue())


class TestSeriesDetector(unittest.TestCase):
    """A follow-up registration appended to the same protocol is a series
    (2026-09-06): one file had grown to 649 lines out of three experiments,
    each under a "... (deklariert vor dem Lauf)" heading. One question per
    protocol — the follow-up gets its own PROTOCOL-s<N> file."""

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "PROTOCOL-x.md"
            f.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(f)])
            return rc, buf.getvalue()

    BASE = ("# x\nBegriffe, Frage, Erfolg, Abbruch, explorativ, Anker, "
            "Prompt:\n\n```\nx\n```\nRoh-Output: n/a — kein Modell.\n")

    def test_declared_follow_up_heading_warns(self):
        rc, out = self._run(self.BASE +
                            "## Lauf B — Richterwechsel (deklariert vor dem Lauf)\n")
        self.assertIn("PROTOCOL-s<N>", out)
        self.assertEqual(rc, 0, "warning, not a failure")

    def test_plain_sections_do_not_trigger(self):
        rc, out = self._run(self.BASE + "## Setup\n## Result\n")
        self.assertNotIn("PROTOCOL-s<N>", out)


class TestLedgerNotCountedAsProse(unittest.TestCase):
    """The runs ledger is mandatory content, not prose (2026-09-06): 93 of a
    protocol's 409 lines were its ledger — the length budget must not teach
    people to stop documenting runs."""

    def test_a_huge_ledger_does_not_flag_the_protocol(self):
        import tempfile
        ledger = "## Runs (Ledger)\n" + "- 2026-09-06T10-00-00_aa11 — x\n" * 400
        text = TestSeriesDetector.BASE + ledger
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "PROTOCOL-x.md"
            f.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                protocol_check.main([str(f)])
        self.assertNotIn("prose lines (tables/code excluded)", buf.getvalue())
