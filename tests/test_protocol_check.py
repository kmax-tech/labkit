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

    def test_real_freeform_protocol_misses_begriffe_typ_and_modell_io(self):
        missing_must, _ = protocol_check.check_text(REAL_FREEFORM_PROTOCOL)
        self.assertEqual(missing_must, [
            "Begriffe (jedes Etikett mit Halbsatz)",
            "Typ (explorativ / konfirmatorisch)",
            "Modell-I/O / Prompt (woertlich)",
            "Roh-Output (ein echtes Beispiel + Modell-Output)",
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

    def test_template_hat_alle_feldnamen(self):
        """Das Template nennt jedes Pflicht- und Soll-Feld."""
        missing_must, missing_should = protocol_check.check_text(
            TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(missing_must, [])
        self.assertEqual(missing_should, [])

    def test_template_faellt_selbst_durch(self):
        """Erwartung UMGEDREHT am 2026-08-17 — und das ist der Punkt.

        Bis dahin verlangte dieser Test, dass das Template selbst durchgeht.
        Das war die Annahme, die den eigentlichen Fehler deckte: Ein Protokoll,
        das ununterscheidbar vom Template ist, galt als ausgefuellt. Genau so
        kam es, dass 28 Protokolle als sauber gemeldet wurden und **keines** ein
        echtes Modell-Ein/Ausgabe-Beispiel enthielt. Das Template besteht aus
        Platzhaltern; es MUSS jetzt durchfallen.
        """
        code, out = self._run([str(TEMPLATE)])
        self.assertEqual(code, 1)
        self.assertIn("PLATZHALTER", out)

    def test_missing_must_exits_one(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-frozen-real.md"
            p.write_text(REAL_FREEFORM_PROTOCOL, encoding="utf-8")
            code, out = self._run([d])
            self.assertEqual(code, 1)
            self.assertIn("FEHLT (Pflicht): Typ", out)
            self.assertIn("FEHLT (Pflicht): Modell-I/O", out)

    def test_no_args_exits_two(self):
        code, _ = self._run([])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()


# --- Platzhalter-Erkennung (2026-08-17) -------------------------------------
#
# Der Anlass: Ueber 28 Protokolle enthielt KEINES ein echtes Modell-Ein/Ausgabe-
# Beispiel, waehrend der Checker sie als sauber meldete — das Wort "Prompt" im
# Template-Platzhalter reichte ihm. Die Zeilen unten sind woertlich aus
# experiments/13-akzeptanzregel/PROTOCOL-akzeptanzregel.md (2026-08-17, vor der Reparatur).

REAL_PLACEHOLDER_BLOCK = """\
## Setup

- **Modell / Tool:** <Alias aus `models.toml` (+ Fallback-Alias) — nie
  Endpoint/ID hartkodieren>
- **Prompt (wörtlich):** <der echte Prompt — gehört in die Note, nicht nur ins Skript>
- **Modell-I/O:** <*rein:* welche Felder; *raus instruiert:* verlangtes Format>
- **Bedeutung des Gold-Labels:** <was heisst die positive Klasse WIRKLICH?>
"""


class TestPlatzhalter(unittest.TestCase):

    def test_findet_die_vier_echten_platzhalter(self):
        found = protocol_check.placeholder_fields(REAL_PLACEHOLDER_BLOCK)
        labels = [lb for _, lb in found]
        self.assertIn("Prompt (wörtlich)", labels)
        self.assertIn("Modell-I/O", labels)
        self.assertIn("Modell / Tool", labels)
        self.assertIn("Bedeutung des Gold-Labels", labels)

    def test_ausgefuelltes_feld_ist_kein_platzhalter(self):
        filled = ("- **Modell / Tool:** Alias `qwen` (qwen2.5:7b, ollama)\n"
                  "- **Prompt (wörtlich):** siehe Codeblock unten\n")
        self.assertEqual(protocol_check.placeholder_fields(filled), [])

    def test_begruendetes_na_ist_kein_platzhalter(self):
        # Die Regel erlaubt "n/a — <warum>"; der Grund muss dastehen.
        na = "- **Modell-I/O:** n/a — dieser Lauf ruft kein Modell auf.\n"
        self.assertEqual(protocol_check.placeholder_fields(na), [])

    def test_platzhalter_in_pflichtfeld_ist_schwerer(self):
        self.assertEqual(protocol_check.severity_of("Prompt (wörtlich)"), "must")
        self.assertEqual(protocol_check.severity_of("Modell-I/O"), "must")
        self.assertEqual(protocol_check.severity_of("Ausbeute je Stufe"), "should")
        self.assertEqual(protocol_check.severity_of("Nächster Schritt"), "other")

    def test_pipeline_meldet_exit_1_bei_pflicht_platzhalter(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text("# x\nHypothese, Erfolg, Abbruch, explorativ, Anker.\n"
                         + REAL_PLACEHOLDER_BLOCK, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            self.assertEqual(rc, 1)
            self.assertIn("NUR PLATZHALTER (Pflicht)", buf.getvalue())


class TestTemplateZeilen(unittest.TestCase):

    def test_woertliche_template_zeile_wird_gemeldet(self):
        if not TEMPLATE.exists():
            self.skipTest("Template nicht vorhanden")
        lines = protocol_check.template_lines(TEMPLATE)
        self.assertTrue(lines, "Template liefert keine Vergleichszeilen")
        # Eine beliebige lange Template-Zeile muss wiedererkannt werden.
        sample = next(iter(lines))
        self.assertIn(sample.strip(), lines)


class TestFrozenOhneBeispiel(unittest.TestCase):
    """„Frozen before run: ja" ohne gerendertes Beispiel (2026-08-18).

    Anlass MH: Der Ablauf gehoert geaendert — erst registrieren, dann die
    Pipeline EINMAL fuer eine Handvoll echter Items laufen lassen, das
    Ergebnis als Beispiel ins Protokoll, und erst dann einfrieren. Wer auf
    einem ungeprueften Instrument einfriert, friert den Fehler mit ein.
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

    def test_frozen_ja_ohne_codeblock_faellt_durch(self):
        rc, out = self._run(self.BASE + "- **Frozen before run:** ja\n")
        self.assertEqual(rc, 1)
        self.assertIn("kein einziges", out)

    def test_frozen_ja_mit_codeblock_geht_durch(self):
        rc, out = self._run(self.BASE + "- **Frozen before run:** ja\n\n```\nAnswer: Yes\n```\n")
        self.assertEqual(rc, 0)

    def test_frozen_nein_ohne_codeblock_ist_kein_pflichtfehler(self):
        # Ein vorgemerktes Protokoll darf ohne Beispiel existieren — es
        # behauptet ja gerade NICHT, eingefroren zu sein.
        rc, out = self._run(self.BASE + "- **Frozen before run:** nein, noch nicht\n")
        self.assertNotIn("kein einziges", out)


class TestGraduierungsTor(unittest.TestCase):
    """Frozen: ja eskaliert Soll zu Pflicht (2026-08-18) — Pilot leicht, Bericht schwer."""

    def _run(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_check.main([str(p)])
            return rc, buf.getvalue()

    # Pilot-Minimum vorhanden, Soll-Felder fehlen komplett:
    PILOT = ("# x\nBegriffe, Frage, Hypothese, Erfolg, Abbruch/Kill, explorativ, Anker,\n"
             "Prompt und Modell-I/O:\n\n```\nAnswer: Yes\n```\n"
             "Roh-Output: siehe output/beispiele.md.\n"
             "Instrumentenprobe: gelaufen.\n")

    def test_pilot_ohne_frozen_warnt_nur(self):
        rc, out = self._run(self.PILOT)
        self.assertEqual(rc, 0, out)           # Soll fehlt -> Warnung, kein Fehler

    def test_frozen_ja_macht_soll_zur_pflicht(self):
        rc, out = self._run(self.PILOT + "\n- **Frozen before run:** ja\n")
        self.assertEqual(rc, 1)
        self.assertIn("Pflicht ab frozen: ja", out)


class TestPromptUndBeispiel(unittest.TestCase):
    """Prompt woertlich + ein echtes Beispiel mit Output sind Pflicht (2026-08-20).

    Das ist der Kern des Protokolls: spaeter sehen, was wirklich reinging und
    rauskam. Zwei Verschaerfungen: ein erwaehnter Prompt ohne Code-Block ist
    ein Pflicht-Fehler (nacherzaehlt statt festgehalten), und das neue
    Pflichtfeld Roh-Output verlangt ein Beispiel + Modell-Output — eingebettet,
    verlinkt oder als begruendetes n/a.
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

    def test_prompt_ohne_codeblock_ist_pflichtfehler(self):
        rc, out = self._run(self.BASE + "Prompt: fragt sinngemaess nach Fallacy.\n"
                            + "Roh-Output: siehe output/beispiele.md.\n")
        self.assertEqual(rc, 1)
        self.assertIn("keinen Code-Block", out)

    def test_fehlender_roh_output_ist_pflichtfehler(self):
        rc, out = self._run(self.BASE + "Prompt:\n\n```\nIs this fallacious?\n```\n")
        self.assertEqual(rc, 1)
        self.assertIn("FEHLT (Pflicht): Roh-Output", out)

    def test_beides_da_geht_durch(self):
        rc, out = self._run(self.BASE + "Prompt:\n\n```\nIs this fallacious?\n```\n"
                            + "Roh-Output: siehe output/beispiele.md.\n")
        self.assertEqual(rc, 0, out)


class TestPilotStampNichtGefroren(unittest.TestCase):
    """Der Template-Kopf ERWAEHNT die Frozen-Regel — das darf den
    FROZEN_YES-Detektor nicht ausloesen (2026-08-20: '`Frozen before run:
    yes` macht sie zur Pflicht' im Kopftext liess jeden frischen
    Pilot-Stempel als eingefroren erscheinen; alle Soll-Luecken wurden
    faelschlich zur Pflicht eskaliert). Der Kopf sagt deshalb '`Frozen:
    yes`', was kein Feld-Pattern ist."""

    def test_pilot_teil_ist_nicht_frozen(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        pilot = text.split("<!-- report:start")[0]
        self.assertIsNone(protocol_check.FROZEN_YES.search(pilot))
        self.assertIsNotNone(protocol_check.FROZEN_NO.search(pilot))


class TestBegriffe(unittest.TestCase):
    """Begriffe sind Pflicht (2026-08-19).

    Das Template fragt sie zweimal ab — `Begriffe dieses Protokolls` im
    Einordnungs-Block, `Geklaerte Begriffe` nach dem Trockenlauf — der Checker
    sah keins von beidem an. 20 der 31 Protokolle im Repo nennen keinen
    einzigen Begriff, waehrend fuenf Definitions-Notes danebenliegen.
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

    def test_ohne_begriff_fehlt_das_pflichtfeld(self):
        missing_must, _ = protocol_check.check_text("# x\nHypothese: A schlaegt B.\n")
        self.assertIn("Begriffe (jedes Etikett mit Halbsatz)", missing_must)

    def test_halbsatz_genuegt(self):
        text = "# x\nBegriffe: Sog = Tendenz des Bildes, Ko-Praesenz zu zeigen.\n"
        missing_must, _ = protocol_check.check_text(text)
        self.assertNotIn("Begriffe (jedes Etikett mit Halbsatz)", missing_must)

    def test_glossar_und_terminologie_zaehlen_auch(self):
        for wort in ("Glossar: siehe notes/messung/pipeline-glossar.md",
                     "Terminologie folgt dem Standard."):
            missing_must, _ = protocol_check.check_text("# x\n" + wort + "\n")
            self.assertNotIn("Begriffe (jedes Etikett mit Halbsatz)", missing_must,
                             f"'{wort}' sollte das Feld erfuellen")

    def test_platzhalter_zaehlt_nicht_als_gefuellt(self):
        # Das Schluesselwort steht da, gefuellt ist es nicht — genau die Luecke,
        # die 2026-08-17 fuer das Prompt-Feld geschlossen wurde.
        rc, out = self._run("# x\n- **Begriffe dieses Protokolls:** <jedes Etikett>\n")
        self.assertEqual(rc, 1)
        self.assertIn("NUR PLATZHALTER (Pflicht): Begriffe", out)

    def test_severity_of_ordnet_beide_template_felder_der_pflicht_zu(self):
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
