"""Tests for notes_check.py against real messung-note heads.

The checker turns the note-kind convention (LAB-082 In `notes/messung/` trägt jede Note ihre Sorte)
into a pass/fail decision, so it gets the parser treatment: tested with real
raw text. The heads below are verbatim from the
two lab repos (counterfactual-worlds, fallacy-datasets), frozen here so the
tests keep working after the live notes evolve. They cover the wild variants
the contract handles: multi-line meta paragraphs, an inline status word,
a limitation blockquote BEFORE the meta line, and a kindless head.
"""

import contextlib
import io
import unittest
from pathlib import Path

from labkit.checks import notes_check
from labkit.formats.gate import OPEN_RULE
from repo_fixture import git as _git


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
        found = notes_check.meta_paragraph(STAMPED_IMPLEMENTED)
        assert found is not None
        n, para = found
        self.assertEqual(n, 3)
        self.assertIn("Instrument — implementiert", para)
        self.assertIn("distanz-definition-kalibrierung", para)

    def test_blockquote_before_meta_is_skipped(self):
        found = notes_check.meta_paragraph(BLOCKQUOTE_FIRST)
        assert found is not None
        n, para = found
        self.assertEqual(n, 6)
        self.assertIn("Instrument — implementiert", para)

    def test_no_meta_line(self):
        self.assertIsNone(notes_check.meta_paragraph("# Titel\n\nNur Fließtext.\n"))


class TestKindContract(unittest.TestCase):
    def test_dash_variants_all_match(self):
        for dash in ("—", "–", "-"):
            for variant in (f"Instrument {dash} Entwurf", f"Instrument{dash}Entwurf"):
                self.assertTrue(notes_check.KIND.search(variant), variant)

    def test_all_kinds_match(self):
        for kind in (
            "Instrument — implementiert",
            "Related-Lesart (gordon07)",
            "Referenzkarte",
            "Audit",
        ):
            self.assertTrue(notes_check.KIND.search(kind), kind)

    def test_related_key_accepts_a_comma_list(self):
        # a Werkfamilie note reads several papers at once
        m = notes_check.RELATED_WITH_KEY.search(
            "Related-Lesart (hahn07, hahn16, hahn20)"
        )
        self.assertIsNotNone(m)

    def test_bare_instrument_without_status_does_not_count(self):
        self.assertFalse(
            notes_check.KIND.search("*2026-09-10 · Instrument für X · Zweck*")
        )


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
        self.assertIn("no kind", must[0].text)
        self.assertIn("Instrument — Entwurf|implementiert", must[0].fix or "")

    def test_implemented_with_protocol_reference_passes(self):
        # a synthesis note over runs listed in a protocol names that protocol
        text = (
            "# Instrument × Modellstärke\n\n"
            "*2026-08-24 · Instrument — implementiert · legt zwei Läufe "
            "übereinander (PROTOCOL-graded-route, Läufe `…54cf`).*\n"
        )
        must, warn = self.check("note.md", text)
        self.assertEqual(must, [])
        self.assertEqual(warn, [])

    def test_implemented_without_code_fails(self):
        must, _ = self.check("note.md", IMPLEMENTED_NO_CODE)
        self.assertEqual(len(must), 1)
        self.assertIn("names no script", must[0].text)

    def test_related_without_citekey_warns(self):
        must, warn = self.check("related-eichel23-plausibilitaet.md", RELATED_NO_KEY)
        self.assertEqual(must, [])
        self.assertEqual(len(warn), 1)
        self.assertIn("citekey", warn[0].text)
        self.assertEqual(warn[0].rule, notes_check.LAB_082)

    def test_a_meta_line_without_a_date_warns(self):
        text = "# Entwurf ohne Datum\n\n*Instrument — Entwurf · noch ohne Lauf.*\n"
        must, warn = self.check("note.md", text)
        self.assertEqual(must, [])
        (no_date,) = warn
        self.assertIn("note.md:3: warning: no date in the meta line", no_date.text)
        self.assertEqual(no_date.rule, OPEN_RULE)
        # the twin: the same line with its date is quiet
        dated = text.replace("*Instrument", "*2026-09-01 · Instrument")
        self.assertEqual(self.check("note.md", dated), ([], []))

    def test_named_scripts_none_of_which_is_in_the_repo_warn(self):
        import tempfile

        text = (
            "# Instrument mit verschwundenem Skript\n\n"
            "*2026-09-01 · Instrument — implementiert · Skript `s9_gone.py`.*\n"
        )
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            _git(root, "init", "-q")
            note = root / "note.md"
            note.write_text(text, encoding="utf-8")
            must, warn = notes_check.check_file(note)
            self.assertEqual(must, [])
            (rotten,) = warn
            self.assertIn(
                "none of the named scripts resolve in the repo (s9_gone.py)",
                rotten.text,
            )
            self.assertEqual(rotten.rule, OPEN_RULE)
            # the twin: the script anywhere in the repository, and it is quiet
            (root / "scripts").mkdir()
            (root / "scripts" / "s9_gone.py").write_text("", encoding="utf-8")
            self.assertEqual(notes_check.check_file(note), ([], []))

    def test_related_kind_mismatch_warns(self):
        must, warn = self.check("related-foo.md", STAMPED_DRAFT)
        self.assertEqual(must, [])
        rules = {w.rule for w in warn if "filename says related-*" in w.text}
        self.assertEqual(rules, {OPEN_RULE})


class TestMain(unittest.TestCase):
    def test_a_convention_gap_warns_and_exits_0(self):
        """A note convention no number depends on warns; it stops nothing."""
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "notes" / "messung"
            base.mkdir(parents=True)
            (base / "a.md").write_text(UNSTAMPED, encoding="utf-8")
            (base / "b.md").write_text(STAMPED_DRAFT, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = notes_check.main([d])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("WARNING:", out)
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


class WhichFileIsANote(unittest.TestCase):
    """`notes-check <dir>` and the post-change hook take the same files as
    measurement notes (`notes_check.is_measurement_note`): a note directly
    in `notes/messung/`, not one nested below it, not one in a `messung/`
    directory outside `notes/`."""

    def test_the_checker_and_the_hook_agree(self):
        import tempfile

        from labkit.gates import hook_post_change

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            note = root / "notes" / "messung" / "a.md"
            nested = root / "notes" / "messung" / "sub" / "x.md"
            outside = root / "other" / "messung" / "y.md"
            index = root / "notes" / "messung" / "00-index.md"
            for f in (note, nested, outside, index):
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(STAMPED_DRAFT, encoding="utf-8")
            collected = set(
                notes_check.collect_notes([d, str(root / "notes" / "messung")])
                + notes_check.collect_notes([str(outside.parent)])
            )
            for f, is_note in (
                (note, True),
                (nested, False),
                (outside, False),
                (index, False),
            ):
                with self.subTest(f.relative_to(root).as_posix()):
                    self.assertEqual(f in collected, is_note)
                    self.assertEqual(hook_post_change.wants_check(f) == "note", is_note)


if __name__ == "__main__":
    unittest.main()
