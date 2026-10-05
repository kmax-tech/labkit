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


class TestDocumentedRunsNotCountedAsProse(unittest.TestCase):
    """The documented runs are mandatory content, not prose (2026-09-06): 93 of
    a protocol's 409 lines were its run list — the length budget must not teach
    people to stop documenting runs."""

    def test_a_huge_run_list_does_not_flag_the_protocol(self):
        import tempfile
        run_list = "## Runs (Ledger)\n" + "- 2026-09-06T10-00-00_aa11 — x\n" * 400
        text = TestSeriesDetector.BASE + run_list
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "PROTOCOL-x.md"
            f.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                protocol_check.main([str(f)])
        self.assertNotIn("prose lines (tables/code excluded)", buf.getvalue())


class TestAuditGates(unittest.TestCase):
    """The two audit fields are due only once the template stamps them (2026-09-08).

    Occasion: ten small errors in four weeks — a sign flip between BT score
    and log-odds, r2 fitted and scored on the same anchors, a gate without a
    positive control, a probe writing into the run's output file. Every one
    was caught by a human objection, a crash or a test written afterwards;
    none by the chain itself. Hence two audits (Arbeitsstandard §2.A12 code
    vs. intent before freezing, §2.D11 evaluation vs. frozen criterion before
    reporting) and their enforcement HERE: through the placeholder mechanism,
    so that a protocol written before the gates existed keeps its verdict.
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

    # Everything a frozen protocol needs, so only the audit field decides.
    FROZEN = ("# x\nBegriffe, Hypothese, Erfolg, Abbruch, konfirmatorisch, Anker, "
              "Prompt, Roh-Output, Instrumentenprobe, Einordnung, Rivalen, "
              "Fehlerrichtung, Skopus, freie Knoepfe, Prognose, gold, Ausbeute, "
              "Ergebnis.\n- **Frozen before run:** ja\n\n```\nAnswer: Yes\n```\n")

    PREFLIGHT_PLACEHOLDER = ("- **Preflight audit:** <date · scope sha · N findings "
                             "(blockers fixed / accepted with reason)>\n")
    ANALYSIS_PLACEHOLDER = ("- **Analysis audit †:** <date · scope sha · N findings "
                            "— the audit of the EVALUATION>\n")

    def test_stamped_preflight_placeholder_fails_once_frozen(self):
        rc, out = self._run(self.FROZEN + self.PREFLIGHT_PLACEHOLDER)
        self.assertEqual(rc, 1, out)
        self.assertIn("Preflight audit", out)

    def test_filled_preflight_passes(self):
        rc, out = self._run(self.FROZEN + "- **Preflight audit:** 2026-09-08 · "
                            "scope sha 3f9a1c2b7e04 · 4 Befunde (2 Blocker behoben)\n")
        self.assertEqual(rc, 0, out)

    def test_stamped_analysis_placeholder_fails_once_frozen(self):
        rc, out = self._run(self.FROZEN + self.ANALYSIS_PLACEHOLDER)
        self.assertEqual(rc, 1, out)
        self.assertIn("Analysis audit", out)

    def test_filled_analysis_passes(self):
        rc, out = self._run(self.FROZEN + "- **Analysis audit †:** 2026-09-09 · "
                            "scope sha 8b1e6d0a4c31 · 2 Befunde (1 Blocker behoben)\n")
        self.assertEqual(rc, 0, out)

    def test_justified_na_counts(self):
        rc, out = self._run(self.FROZEN + "- **Preflight audit:** n/a — Wegwerf-Test "
                            "ohne berichtete Zahl\n")
        self.assertEqual(rc, 0, out)

    def test_legacy_protocol_without_the_fields_keeps_its_verdict(self):
        """The whole point of SHOULD_IF_PRESENT: no retrofitting of closed runs."""
        rc, out = self._run(self.FROZEN)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Preflight audit", out)
        self.assertNotIn("Analysis audit", out)

    def test_severity_of_ranks_both_audit_labels_as_should(self):
        self.assertEqual(protocol_check.severity_of("Preflight audit"), "should")
        self.assertEqual(protocol_check.severity_of("Analysis audit †"), "should")

    def test_template_stamps_both_fields(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Preflight audit", text)
        self.assertIn("Analysis audit", text)


class TestResolutionCheckGate(unittest.TestCase):
    """The resolution check field (§2.A13, 2026-09-09) rides the placeholder
    mechanism exactly like the audit fields: stamped-but-unfilled fails at
    frozen:yes, absent stays silent (no retrofitting), and the pattern must
    NOT catch the template's own "Answer form + resolution †" field."""

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    FROZEN = TestAuditGates.FROZEN

    def test_stamped_placeholder_fails_once_frozen(self):
        rc, out = self._run(self.FROZEN + "- **Resolution check (ZERO calls):** "
                            "<perfect effect fires? null stays silent?>\n")
        self.assertEqual(rc, 1, out)
        self.assertIn("Resolution check", out)

    def test_filled_passes(self):
        rc, out = self._run(self.FROZEN + "- **Resolution check:** perfect "
                            "effect p = 0.0002 (fires), null p = 0.4791 "
                            "(silent), 8 draws as in the run\n")
        self.assertEqual(rc, 0, out)

    def test_german_label_counts(self):
        rc, out = self._run(self.FROZEN + "- **Auflösungsprobe:** perfekter "
                            "Effekt feuert (p = 0,0002), Null schweigt\n")
        self.assertEqual(rc, 0, out)

    def test_absent_field_stays_silent(self):
        rc, out = self._run(self.FROZEN)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Resolution check", out)

    def test_severity_of_resolution_check_is_should(self):
        self.assertEqual(protocol_check.severity_of("Resolution check (ZERO "
                                                    "calls)"), "should")

    def test_answer_form_resolution_is_not_caught(self):
        """Guard against the near-collision that would have retrofitted a MUST
        onto every frozen protocol carrying the stamped 'Answer form +
        resolution †' placeholder."""
        self.assertEqual(protocol_check.severity_of("Answer form + resolution †"),
                         "other")

    def test_template_stamps_the_field(self):
        self.assertIn("Resolution check", TEMPLATE.read_text(encoding="utf-8"))


class TestProseBudgetEscalation(unittest.TestCase):
    """Frozen protocols escalate prose budgets from warning to must (2026-09-13).

    Escalation is gated by the freeze date: only protocols frozen on or after
    BUDGET_MUST_SINCE (2026-09-14) get the MUST. Older freezes (or freezes
    without a date) stay as warnings — zero edits to existing protocols.
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

    FROZEN_NEW = ("# x\n- **Standard:** 0.15\n"
                  "Begriffe, Hypothese, Erfolg, Abbruch, konfirmatorisch, Anker, "
                  "Prompt, Roh-Output, Instrumentenprobe, Einordnung, Rivalen, "
                  "Fehlerrichtung, Skopus, freie Knoepfe, Prognose, gold, Ausbeute, "
                  "Ergebnis, Exclusions.\n- **Frozen before run:** ja\n"
                  "\n```\nAnswer: Yes\n```\n")

    FROZEN_OLD = ("# x\n- **Standard:** 0.13\n"
                  "Begriffe, Hypothese, Erfolg, Abbruch, konfirmatorisch, Anker, "
                  "Prompt, Roh-Output, Instrumentenprobe, Einordnung, Rivalen, "
                  "Fehlerrichtung, Skopus, freie Knoepfe, Prognose, gold, Ausbeute, "
                  "Ergebnis.\n- **Frozen before run:** ja\n"
                  "\n```\nAnswer: Yes\n```\n")

    def test_new_freeze_oversized_section_exits_one(self):
        intent = "## Intent\n" + "Eine Zeile Prose.\n" * 40
        rc, out = self._run(self.FROZEN_NEW + intent)
        self.assertEqual(rc, 1, out)
        self.assertIn("OVERSIZED (must)", out)
        self.assertIn("Intent", out)

    def test_new_freeze_global_over_350_exits_one(self):
        filler = "Eine Zeile Prose.\n" * 360
        rc, out = self._run(self.FROZEN_NEW + filler)
        self.assertEqual(rc, 1, out)
        self.assertIn("OVERSIZED (must)", out)

    def test_old_freeze_oversized_warns_but_exits_zero(self):
        intent = "## Intent\n" + "Eine Zeile Prose.\n" * 40
        rc, out = self._run(self.FROZEN_OLD + intent)
        self.assertEqual(rc, 0, out)
        self.assertIn("oversized", out.lower())
        self.assertNotIn("OVERSIZED (must)", out)

    def test_no_date_frozen_oversized_warns_but_exits_zero(self):
        frozen_no_date = TestAuditGates.FROZEN
        intent = "## Intent\n" + "Eine Zeile Prose.\n" * 40
        rc, out = self._run(frozen_no_date + intent)
        self.assertEqual(rc, 0, out)
        self.assertIn("oversized", out.lower())
        self.assertNotIn("OVERSIZED (must)", out)

    def test_unfrozen_oversized_section_warns_but_exits_zero(self):
        base = ("# x\nBegriffe, Frage, Erfolg, Abbruch, explorativ, Anker, "
                "Prompt:\n\n```\nx\n```\nRoh-Output: n/a — kein Modell.\n")
        intent = "## Intent\n" + "Eine Zeile Prose.\n" * 40
        rc, out = self._run(base + intent)
        self.assertEqual(rc, 0, out)
        self.assertIn("oversized", out.lower())


class TestMeasurementType(unittest.TestCase):
    """Measurement protocols have 7 fields, no freeze, no SHOULD (2026-09-13)."""

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    FULL = ("# Measurement: test\n"
            "- **Standard:** 0.15\n"
            "- **Type:** measurement\n"
            "- **Question:** How many pairs?\n"
            "- **Data / scope:** corpus, N=100, scripts/00_prepare.py\n"
            "- **Prior computation:** none\n"
            "- **Method:** scripts/count_pairs.py\n"
            "- **Exclusions / filters:** none\n"
            "- **Result:** 42 (run_id 2026-09-13T10-00-00_ab12)\n"
            "- **Terms:** pair = two adjacent sentences\n")

    def test_full_measurement_passes(self):
        rc, out = self._run(self.FULL)
        self.assertEqual(rc, 0, out)
        self.assertIn("measurement, all fields filled", out)

    def test_missing_question_exits_one(self):
        text = self.FULL.replace("- **Question:** How many pairs?\n", "")
        rc, out = self._run(text)
        self.assertEqual(rc, 1, out)
        self.assertIn("MISSING (must): Question", out)

    def test_missing_exclusions_exits_one(self):
        text = self.FULL.replace("- **Exclusions / filters:** none\n", "")
        rc, out = self._run(text)
        self.assertEqual(rc, 1, out)
        self.assertIn("MISSING (must): Exclusions", out)

    def test_experiment_should_fields_not_checked(self):
        rc, out = self._run(self.FULL)
        self.assertEqual(rc, 0)
        self.assertNotIn("should", out.lower())
        self.assertNotIn("Frozen", out)

    def test_frozen_yes_not_escalated(self):
        text = self.FULL + "- **Frozen before run:** ja\n"
        rc, out = self._run(text)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("must once frozen", out)

    def test_misdeclared_with_prompt_block_exits_one(self):
        text = self.FULL + "\nPrompt:\n\n```\nIs this fallacious?\n```\n"
        rc, out = self._run(text)
        self.assertEqual(rc, 1, out)
        self.assertIn("MISDECLARED", out)

    def test_german_type_messung_recognised(self):
        text = self.FULL.replace("**Type:** measurement", "**Typ:** Messung")
        rc, out = self._run(text)
        self.assertEqual(rc, 0, out)
        self.assertIn("measurement", out)

    def test_placeholder_in_measurement_field_exits_one(self):
        text = self.FULL.replace("42 (run_id 2026-09-13T10-00-00_ab12)",
                                 "<number + run_id, or \"pending\">")
        rc, out = self._run(text)
        self.assertEqual(rc, 1, out)
        self.assertIn("PLACEHOLDER ONLY (must)", out)


class TestExperimentNewFields(unittest.TestCase):
    """Exclusions is MUST from Standard >= 0.15; Gate/Randomness are SHOULD_IF_PRESENT."""

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    BASE_V015 = ("# x\n- **Standard:** 0.15\n"
                 "Begriffe, Hypothese, Erfolg, Abbruch, konfirmatorisch, Anker, "
                 "Prompt, Roh-Output, Instrumentenprobe, Einordnung, Rivalen, "
                 "Fehlerrichtung, Skopus, freie Knoepfe, Prognose, gold, Ausbeute, "
                 "Ergebnis.\n- **Frozen before run:** nein\n"
                 "\n```\nAnswer: Yes\n```\n")

    def test_v015_without_exclusions_exits_one(self):
        rc, out = self._run(self.BASE_V015)
        self.assertEqual(rc, 1, out)
        self.assertIn("Exclusions", out)

    def test_v015_with_exclusions_passes(self):
        text = self.BASE_V015 + "Exclusions: none.\n"
        rc, out = self._run(text)
        self.assertEqual(rc, 0, out)

    def test_legacy_without_exclusions_passes(self):
        legacy = self.BASE_V015.replace("- **Standard:** 0.15\n", "")
        rc, out = self._run(legacy)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Exclusions", out)

    def test_v013_explicit_without_exclusions_passes(self):
        legacy = self.BASE_V015.replace("0.15", "0.13")
        rc, out = self._run(legacy)
        self.assertEqual(rc, 0, out)

    def test_template_stamps_exclusions(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Exclusions / filters", text)

    def test_template_stamps_gate_labels(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Gate labels (expected)", text)

    def test_template_stamps_randomness(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Randomness controls", text)

    def test_template_stamps_standard(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Standard:", text)


class TestStandardVersion(unittest.TestCase):
    """Standard-Version field replaces per-feature cutoff dates (2026-09-13)."""

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    BASE = ("# x\nBegriffe, Hypothese, Erfolg, Abbruch, konfirmatorisch, Anker, "
            "Prompt, Roh-Output, Instrumentenprobe, Einordnung, Rivalen, "
            "Fehlerrichtung, Skopus, freie Knoepfe, Prognose, gold, Ausbeute, "
            "Ergebnis, Exclusions.\n")

    def test_v014_frozen_oversized_exits_one(self):
        text = (self.BASE + "- **Standard:** 0.14\n"
                "- **Frozen before run:** ja\n\n```\nAnswer: Yes\n```\n"
                + "## Intent\n" + "Prose line.\n" * 40)
        rc, out = self._run(text)
        self.assertEqual(rc, 1, out)
        self.assertIn("OVERSIZED (must)", out)

    def test_v013_frozen_oversized_exits_zero(self):
        text = (self.BASE + "- **Standard:** 0.13\n"
                "- **Frozen before run:** ja\n\n```\nAnswer: Yes\n```\n"
                + "## Intent\n" + "Prose line.\n" * 40)
        rc, out = self._run(text)
        self.assertEqual(rc, 0, out)
        self.assertIn("oversized", out.lower())
        self.assertNotIn("OVERSIZED (must)", out)

    def test_no_standard_field_defaults_to_v013(self):
        text = (self.BASE
                + "- **Frozen before run:** ja\n\n```\nAnswer: Yes\n```\n"
                + "## Intent\n" + "Prose line.\n" * 40)
        rc, out = self._run(text)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("OVERSIZED (must)", out)

    def test_standard_version_regex_reads_field(self):
        m = protocol_check.STANDARD_VERSION.search("- **Standard:** 0.15\n")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "0.15")

    def test_version_comparison_is_numeric_not_lexicographic(self):
        """String comparison puts "0.9" above "0.15" and "0.100" below it —
        both would misapply every versioned gate."""
        self.assertLess(protocol_check._std("0.9"), (0, 15))
        self.assertGreater(protocol_check._std("0.100"), (0, 15))
        self.assertGreaterEqual(protocol_check._std("0.15"), (0, 15))

    def test_v09_standard_gets_no_v015_musts(self):
        """A pre-0.15 protocol must not be held to the 0.15 field set
        (lexicographically "0.9" >= "0.15" was True)."""
        must, _ = protocol_check.check_text(
            self.BASE.lower().replace("exclusions.", ""), standard="0.9")
        self.assertFalse([m for m in must if "Exclusions" in m], must)


class TestCheckerTooOld(unittest.TestCase):
    """A protocol declaring a NEWER standard than the checker implements gets
    one hard failure and zero other findings — an old gate judging a new
    template produces false positives, not fewer findings (2026-09-14: a
    pre-0.15 checker flagged the 0.15 template's stamped preamble as
    "verbatim template text" for a whole session)."""

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    def test_newer_standard_fails_hard(self):
        rc, out = self._run("# x\n- **Standard:** 0.99\n")
        self.assertEqual(rc, 1, out)
        self.assertIn("CHECKER TOO OLD", out)

    def test_newer_standard_produces_no_other_findings(self):
        # An empty protocol would normally rain MISSING findings; behind the
        # guard, none of them may appear — they would be noise.
        rc, out = self._run("# x\n- **Standard:** 0.99\n")
        self.assertNotIn("MISSING", out)
        self.assertNotIn("template text", out)

    def test_supported_standard_passes_the_guard(self):
        rc, out = self._run(
            "# x\nBegriffe, Hypothese, Erfolg, Abbruch, konfirmatorisch, "
            "Anker, Prompt, Roh-Output, Instrumentenprobe, Einordnung, "
            "Rivalen, Fehlerrichtung, Skopus, freie Knoepfe, Prognose, gold, "
            "Ausbeute, Ergebnis, Exclusions.\n- **Standard:** 0.15\n"
            "\n```\nAnswer: Yes\n```\n")
        self.assertNotIn("CHECKER TOO OLD", out)

    def test_supported_constant_is_a_valid_version(self):
        self.assertIsInstance(protocol_check._std(
            protocol_check.SUPPORTED_STANDARD), tuple)


class TestIntentBudgetCalibration(unittest.TestCase):
    """Intent budget 35 (calibration 2026-09-15, n=94): the [K/S/W/N]
    registrations moved mandatory content into Intent — the disciplined
    confirmatory cluster tops out at 35 prose lines and must pass."""

    def test_intent_35_lines_is_within_budget(self):
        text = "## Intent\n" + "Prose line.\n" * 35
        self.assertEqual(protocol_check.oversized_sections(text), [])

    def test_intent_36_lines_is_over_budget(self):
        text = "## Intent\n" + "Prose line.\n" * 36
        self.assertEqual(protocol_check.oversized_sections(text),
                         [("Intent", 36, 35)])


class TestStampedLegendIsNotTemplateText(unittest.TestCase):
    """The template's preamble (before the first `## `) is a stamped legend
    that survives filling — the verbatim-template check must not flag it
    (2026-09-14/15: every freshly stamped protocol was flagged forever)."""

    def test_preamble_lines_are_excluded(self):
        lines = protocol_check.template_lines(
            protocol_check.find_template(None))
        self.assertTrue(lines, "template not found")
        self.assertFalse([s for s in lines if "A checklist, not a copy-form" in s])
        self.assertFalse([s for s in lines if "intent ids" in s])

    def test_body_instruction_lines_still_count(self):
        lines = protocol_check.template_lines(
            protocol_check.find_template(None))
        # An instruction line from inside a section stays in the set.
        self.assertTrue([s for s in lines if "Plain language" in s], lines)


class TestCostTier(unittest.TestCase):
    """`Cost:` (2026-10-05) is due once stamped, and its value is readable."""

    def test_template_stamps_cost(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("- **Cost:**", text)

    def test_the_tier_is_read_from_the_field(self):
        self.assertEqual(protocol_check.cost_tier_of("- **Cost:** seconds\n"), "seconds")
        self.assertEqual(protocol_check.cost_tier_of("- **Cost:** Hours — x\n"), "hours")

    def test_a_placeholder_or_absent_field_has_no_tier(self):
        self.assertIsNone(protocol_check.cost_tier_of("- **Cost:** <seconds | hours>\n"))
        self.assertIsNone(protocol_check.cost_tier_of("- **Timebox:** 2h\n"))

    def test_a_stamped_placeholder_is_a_should_gap(self):
        self.assertEqual(protocol_check.severity_of("Cost"), "should")

