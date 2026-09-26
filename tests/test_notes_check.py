"""Tests for notes_check.py against real messung-note heads.

The checker turns the note-kind convention (Arbeitsstandard §4, 2026-09-10)
into a pass/fail decision, so it gets the parser treatment: tested with real
raw text. The heads below are verbatim from the 2026-09-10 inventory of the
two lab repos (counterfactual-worlds, fallacy-datasets), frozen here so the
tests keep working after the live notes evolve. They cover the wild variants
that shaped the contract: multi-line meta paragraphs, an inline status word,
a limitation blockquote BEFORE the meta line, and a kindless head.
"""

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "labkit" / "notes_check.py"

spec = importlib.util.spec_from_file_location("notes_check", CHECKER)
assert spec is not None and spec.loader is not None
notes_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes_check)


# Verbatim head of counterstory-messprotokoll.md (counterfactual-worlds),
# retro-stamped: date leading, kind after the date, wrapped meta paragraph.
STAMPED_IMPLEMENTED = """\
# Messprotokoll: Counter-Story-Distanz mit Validator-Batterie

*2026-07-17 · Instrument — implementiert · operationalisiert die
Revisions-Distanz aus [[distanz-definition-kalibrierung]] ·
Implementierung: `experiment_counterstory_validators.py`*

## Wozu
"""

# Verbatim head of skepsis-als-rater-strenge.md (fallacy-datasets): status
# word inline, no date in the original — stamped variant keeps the prose.
STAMPED_DRAFT = """\
# Skepsis als Rater-Strenge

*2026-09-01 · Instrument — Entwurf · Status: **sketch** — das Modell steht,
gemessen ist nichts davon. Anlass: Diskussion zum v3-Gitter am 2026-09-01.*

## Modell
"""

# The pre-stamp normal case (counterstory head as it was): meta line present,
# date present, but no kind — the one MUST the retro-stamp exists to fix.
UNSTAMPED = """\
# Messprotokoll: Counter-Story-Distanz mit Validator-Batterie

*2026-07-17 · operationalisiert die Revisions-Distanz aus
[[distanz-definition-kalibrierung]] · Fehlermodi-Taxonomie: Dokument MH*

## Wozu
"""

# A limitation blockquote before the meta line is the documented convention
# (the Befundregister reads exactly that) — it must not hide the meta line.
BLOCKQUOTE_FIRST = """\
# Verdikt vs. Delta-Weg

> **Einschränkung (2026-08-24):** gilt nur für Paar-Antwortform, s.
> [[ratio-paar-messung]].

*2026-08-20 · Instrument — implementiert · Bereich
`experiments/32-welt-paarvergleich` · Skript `s2_measure.py`*

## Kern
"""

# Declared implemented but names no script, function, or area path — the
# inconsistency the checker exists to catch (kind is declared, not derived).
IMPLEMENTED_NO_CODE = """\
# Phantom-Instrument

*2026-09-10 · Instrument — implementiert · misst angeblich etwas.*

## Text ohne jeden Code-Verweis
"""

RELATED_NO_KEY = """\
# Eichel & Schulte im Walde (2023): Plausibilität ist Welt-Häufigkeit

*2026-08-14 · Related-Lesart · erklärt den Nullbefund aus
[[world-bending-pilot]].*
"""


class TestMetaParagraph(unittest.TestCase):
    def test_finds_wrapped_meta(self):
        n, para = notes_check.meta_paragraph(STAMPED_IMPLEMENTED)
        self.assertEqual(n, 3)
        self.assertIn("Instrument — implementiert", para)
        self.assertIn("distanz-definition-kalibrierung", para)

    def test_blockquote_before_meta_is_skipped(self):
        n, para = notes_check.meta_paragraph(BLOCKQUOTE_FIRST)
        self.assertEqual(n, 6)
        self.assertIn("Instrument — implementiert", para)

    def test_no_meta_line(self):
        self.assertIsNone(
            notes_check.meta_paragraph("# Titel\n\nNur Fließtext.\n"))


class TestKindContract(unittest.TestCase):
    def test_dash_variants_all_match(self):
        for dash in ("—", "–", "-"):
            for variant in (f"Instrument {dash} Entwurf",
                            f"Instrument{dash}Entwurf"):
                self.assertTrue(notes_check.KIND.search(variant), variant)

    def test_all_kinds_match(self):
        for kind in ("Instrument — implementiert", "Related-Lesart (gordon07)",
                     "Referenzkarte", "Audit"):
            self.assertTrue(notes_check.KIND.search(kind), kind)

    def test_related_key_accepts_a_comma_list(self):
        # a Werkfamilie note reads several papers at once
        m = notes_check.RELATED_WITH_KEY.search(
            "Related-Lesart (hahn07, hahn16, hahn20)")
        self.assertIsNotNone(m)

    def test_bare_instrument_without_status_does_not_count(self):
        self.assertFalse(notes_check.KIND.search(
            "*2026-09-10 · Instrument für X · Zweck*"))


class TestCheckFile(unittest.TestCase):
    def check(self, name: str, text: str):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / name
            f.write_text(text, encoding="utf-8")
            return notes_check.check_file(f)

    def test_stamped_notes_pass(self):
        for text in (STAMPED_IMPLEMENTED, STAMPED_DRAFT, BLOCKQUOTE_FIRST):
            must, warn = self.check("note.md", text)
            self.assertEqual(must, [], text[:40])
            self.assertEqual(warn, [], text[:40])

    def test_unstamped_note_fails_kind(self):
        must, _ = self.check("note.md", UNSTAMPED)
        self.assertEqual(len(must), 1)
        self.assertIn("no kind", must[0])

    def test_implemented_with_protocol_reference_passes(self):
        # a synthesis note over documented runs names the protocol, not a script
        text = ("# Instrument × Modellstärke\n\n"
                "*2026-08-24 · Instrument — implementiert · legt zwei Läufe "
                "übereinander (PROTOCOL-graded-route, Läufe `…54cf`).*\n")
        must, warn = self.check("note.md", text)
        self.assertEqual(must, [])
        self.assertEqual(warn, [])

    def test_implemented_without_code_fails(self):
        must, _ = self.check("note.md", IMPLEMENTED_NO_CODE)
        self.assertEqual(len(must), 1)
        self.assertIn("names no script", must[0])

    def test_related_without_citekey_warns(self):
        must, warn = self.check("related-eichel23-plausibilitaet.md",
                                RELATED_NO_KEY)
        self.assertEqual(must, [])
        self.assertEqual(len(warn), 1)
        self.assertIn("citekey", warn[0])

    def test_related_kind_mismatch_warns(self):
        must, warn = self.check("related-foo.md", STAMPED_DRAFT)
        self.assertEqual(must, [])
        self.assertTrue(any("filename says related-*" in w for w in warn))


class TestMain(unittest.TestCase):
    def test_exit_1_on_must_failure(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "notes" / "messung"
            base.mkdir(parents=True)
            (base / "a.md").write_text(UNSTAMPED, encoding="utf-8")
            (base / "b.md").write_text(STAMPED_DRAFT, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = notes_check.main([d])
            self.assertEqual(rc, 1)
            out = buf.getvalue()
            self.assertIn("no kind", out)
            self.assertIn("b.md: OK", out)

    def test_exit_0_when_clean(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "notes" / "messung"
            base.mkdir(parents=True)
            (base / "b.md").write_text(STAMPED_IMPLEMENTED, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = notes_check.main([d])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
