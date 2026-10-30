"""An accepted finding's effect on the verdicts, as the record holds it.

`stands` keeps the verdicts, read within the limit; `criterion-1 not assessable`
says the run does not judge criterion-1. An accepted BLOCKER owes one (`--decide`
refuses it without), an accepted WARNING may name one — severity and
what the result still allows are two questions — and nothing else
carries one (review 2026-10-21).
"""

import tempfile
import unittest
from pathlib import Path

from labkit.formats import findings
from protocol_fixture import registration_of  # noqa: E402


def record(area: Path) -> Path:
    return findings.write(
        area,
        "analysis",
        "test",
        "aaaaaaaaaaaa",
        "bbbbbbbbbbbb",
        (1, 1, 0),
        [("BLOCKER", "BLOCKER · x.py:1 · a"), ("WARNING", "WARNING · x.py:2 · b")],
        run_id="2026-10-21T10-00-00_aa11",
        shown_sha="cccccccccccc",
        registration=registration_of(area),
    )


class EffectGrammar(unittest.TestCase):
    def test_stands_and_not_assessable(self):
        self.assertEqual(findings.effect_ids("stands"), ())
        self.assertEqual(
            findings.effect_ids("criterion-1 not assessable"), ("criterion-1",)
        )
        self.assertEqual(
            findings.effect_ids("criterion-1, quality-check-2 not assessable"),
            ("criterion-1", "quality-check-2"),
        )

    def test_anything_else_is_refused(self):
        for bad in (
            "",
            "criterion-1",
            "c1 not assessable",
            "criterion-1 not met",
            "holds",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                findings.effect_ids(bad)


class Decide(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = record(Path(self.tmp.name))

    def test_an_accepted_blocker_owes_its_effect(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(findings.FindingsError, "owes its effect"):
            findings.write_decision(self.path, 1, "accepted", "kept")
        self.assertEqual(self.path.read_bytes(), before)

    def test_a_refusal_of_the_effects_form_is_told_apart(self):
        """`--decide` completes these for a protocol without promises, whose
        form example (`criterion-1`) cannot hold there; another refusal is not one."""
        for effect in ("", "4 not assessable"):
            with (
                self.subTest(effect=effect),
                self.assertRaises(findings.EffectFormError),
            ):
                findings.write_decision(self.path, 1, "accepted", "kept", effect)
        with self.assertRaises(findings.FindingsError) as caught:
            findings.write_decision(self.path, 1, "dismissed", "no", "stands")
        self.assertNotIsInstance(caught.exception, findings.EffectFormError)

    def test_the_effect_is_stored_and_read_back(self):
        rec = findings.write_decision(
            self.path, 1, "accepted", "kept", "criterion-1 not assessable"
        )
        self.assertEqual(rec.findings[0].effect, "criterion-1 not assessable")
        self.assertEqual(rec.limits(), [(1, rec.findings[0])])
        again = findings.write_decision(self.path, 1, "accepted", "kept", "stands")
        self.assertEqual(again.findings[0].effect, "stands")
        self.assertEqual(self.path.read_text(encoding="utf-8").count("effect ="), 1)

    def test_an_accepted_warning_may_name_an_effect_and_is_then_a_limit(self):
        rec = findings.write_decision(self.path, 2, "accepted", "a cue", "stands")
        self.assertEqual(rec.findings[1].effect, "stands")
        self.assertEqual([n for n, _ in rec.limits()], [2])  # the BLOCKER is still open

    def test_an_accepted_warning_without_an_effect_is_no_limit(self):
        rec = findings.write_decision(self.path, 2, "accepted", "noted")
        self.assertEqual(rec.findings[1].effect, "")
        self.assertEqual(rec.limits(), [])  # the BLOCKER is still open

    def test_no_effect_on_anything_but_an_accepted_blocker_or_warning(self):
        with self.assertRaisesRegex(
            findings.FindingsError, "accepted BLOCKER or WARNING"
        ):
            findings.write_decision(self.path, 1, "dismissed", "no", "stands")
        with self.assertRaisesRegex(
            findings.FindingsError, "accepted BLOCKER or WARNING"
        ):
            findings.write_decision(self.path, 2, "deferred", "later", "stands")

    def test_the_answer_note_counts_the_limits(self):
        """One note however many limits; three "read within" tails grew the
        Answer (sandbox, 2026-10-21). Which promise a limit leaves unjudged
        stands in the line's verdicts (`result_render.verdicts`)."""
        a, b = "Limit (audit x #1)", "Limit (audit x #2)"
        self.assertEqual(findings.answer_note([]), "")
        self.assertEqual(
            findings.answer_note([(a, "stands")]),
            "; subject to 1 recorded limitation (the Limit lines below)",
        )
        self.assertEqual(
            findings.answer_note(
                [(a, "stands"), (b, "criterion-1, quality-check-2 not assessable")]
            ),
            "; subject to 2 recorded limitations (the Limit lines below)",
        )

    def test_a_hand_written_effect_is_held_on_reading(self):
        text = self.path.read_text(encoding="utf-8").replace(
            'status = "open"\nreason = ""', 'status = "accepted"\nreason = "k"\neffect = "criterion-1 not met"', 1
        )  # fmt: skip
        self.path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(findings.FindingsError, "finding 1: effect"):
            findings.read(self.path)

    def test_an_accepted_blocker_decided_by_hand_without_effect_reads(self):
        """report-check asks for the effect; the record itself stays readable."""
        text = self.path.read_text(encoding="utf-8").replace(
            'status = "open"\nreason = ""', 'status = "accepted"\nreason = "k"', 1
        )
        self.path.write_text(text, encoding="utf-8")
        self.assertEqual(findings.read(self.path).findings[0].effect, "")


if __name__ == "__main__":
    unittest.main()


class LimitLinesInRecordOrder(unittest.TestCase):
    """Each limit was inserted right below Recorded results, so three of them read
    #3, #2, #1 — all three final audits named it (2026-10-21)."""

    def test_the_limit_lines_follow_the_record_order(self):
        from labkit.tools import protocol_fill

        text = (
            "## Result\n\n- **Recorded results:** a = 1 (run x)\n- **Raw output:** r\n"
        )
        limits = tuple((f"Limit (audit r #{n})", f"v{n}") for n in (1, 2, 3))
        out, written = protocol_fill.limit_lines(text, limits)
        self.assertEqual(written, [label for label, _ in limits])
        rows = [ln for ln in out.splitlines() if ln.startswith("- **")]
        self.assertEqual(
            rows,
            [
                "- **Recorded results:** a = 1 (run x)",
                "- **Limit (audit r #1):** v1",
                "- **Limit (audit r #2):** v2",
                "- **Limit (audit r #3):** v3",
                "- **Raw output:** r",
            ],
        )
