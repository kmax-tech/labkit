"""labkit.run.profile: the data profile per gold class, before any model call.

Three judge probes left the stamped `audit()` TODO alone, and their audits
found a cue only one class carried — six connectives, every causal item
holds one, no other item does (sandbox, 2026-10-21). The profile counts
what the area names; an open decision prints as open, never as an empty
table, and "checked, no hit" reads apart from "none counted". The counts
are static evidence for the judgement and the audit, never proof.
"""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from labkit.run import profile
from labkit.tools import scaffold

ITEMS = [
    {"id": "c1", "text": "Because the road was icy, the bus was late.", "gold": "causal", "overlap": 0.5},
    {"id": "c2", "text": "The price cut drove sales up.", "gold": "causal", "overlap": 0.25},
    {"id": "n1", "text": "The road was icy and the bus was late.", "gold": "not_causal", "overlap": 0.5},
    {"id": "n2", "text": "Sales rose; the price fell.", "gold": "not_causal", "overlap": 0.0},
]  # fmt: skip


class Counts(unittest.TestCase):
    def test_items_and_mean_words_per_class(self):
        p = profile.profile(ITEMS, markers=None, confounds=None)
        self.assertEqual(
            [(c.gold, c.n) for c in p.classes], [("causal", 2), ("not_causal", 2)]
        )
        self.assertEqual(p.classes[0].mean_words, (9 + 6) / 2)
        self.assertEqual(p.classes[1].mean_words, (9 + 5) / 2)

    def test_markers_are_counted_per_class_as_whole_words_case_ignored(self):
        p = profile.profile(
            ITEMS, markers=("because", "drove", "the", "becaus"), confounds=()
        )
        assert p.markers is not None
        got = {m.marker: m.per_class for m in p.markers}
        self.assertEqual(got["because"], {"causal": 1, "not_causal": 0})
        self.assertEqual(got["the"], {"causal": 2, "not_causal": 2})
        self.assertEqual(
            got["becaus"], {"causal": 0, "not_causal": 0}
        )  # no part of a word
        self.assertEqual(p.markers[0].only_in, "causal")
        self.assertIsNone(p.markers[2].only_in)
        self.assertEqual(p.any_marker, {"causal": 2, "not_causal": 2})

    def test_a_marker_padded_with_spaces_is_refused(self):
        """Two cold agents wrote " so " to keep it out of longer words; the
        whole-word match then needed a word character on neither side of the
        spaces, and `…cut, so the…` went uncounted — 5/6 instead of 6/6
        (sandbox, 2026-10-21). Markers match as whole words already."""
        for padded in (" so ", "so ", " so"):
            with (
                self.subTest(padded=padded),
                self.assertRaisesRegex(ValueError, "whole words"),
            ):
                profile.profile(ITEMS, markers=(padded,), confounds=())

    def test_a_marker_after_a_comma_is_counted(self):
        rows = [
            {
                "id": "c3",
                "text": "Sales rose after the cut, so the cut drove demand.",
                "gold": "causal",
            }
        ]
        p = profile.profile(rows, markers=("so",), confounds=())
        assert p.markers is not None
        self.assertEqual(p.markers[0].per_class, {"causal": 1})

    def test_the_markers_together_can_separate_the_classes(self):
        p = profile.profile(ITEMS, markers=("because", "drove"), confounds=())
        self.assertEqual(p.any_marker, {"causal": 2, "not_causal": 0})
        self.assertIn(
            "  any of them      causal 2/2 · not_causal 0/2", profile.lines(p)
        )

    def test_confounds_are_averaged_per_class(self):
        p = profile.profile(ITEMS, markers=(), confounds=("overlap",))
        self.assertEqual([c.confounds["overlap"] for c in p.classes], [0.375, 0.25])

    def test_a_confound_that_is_no_number_is_refused(self):
        rows = [dict(ITEMS[0], overlap="high")]
        with self.assertRaisesRegex(ValueError, "c1.*overlap.*not a number"):
            profile.profile(rows, markers=(), confounds=("overlap",))

    def test_an_item_without_its_gold_is_refused(self):
        with self.assertRaisesRegex(ValueError, "x.*'gold'"):
            profile.profile([{"id": "x", "text": "t"}], markers=(), confounds=())


class OpenReadsApartFromNoHit(unittest.TestCase):
    def test_the_profile_says_it_is_static_evidence(self):
        out = "\n".join(
            profile.lines(profile.profile(ITEMS, markers=("because",), confounds=()))
        )
        self.assertIn("static evidence", out)
        self.assertIn("no test of the task", out)

    def test_not_decided_none_applies_and_no_hit_are_three_lines(self):
        undecided = "\n".join(
            profile.lines(profile.profile(ITEMS, markers=None, confounds=None))
        )
        self.assertIn("none counted — MARKERS is None", undecided)
        self.assertIn("none counted — CONFOUNDS is None", undecided)
        none = "\n".join(
            profile.lines(profile.profile(ITEMS, markers=(), confounds=()))
        )
        self.assertIn("decided: none applies (MARKERS = ())", none)
        self.assertIn("decided: none beyond the word count (CONFOUNDS = ())", none)
        self.assertNotIn("none counted", none)
        checked = "\n".join(
            profile.lines(profile.profile(ITEMS, markers=("whereas",), confounds=()))
        )
        self.assertIn("checked: in no item", checked)
        shortcut = "\n".join(
            profile.lines(profile.profile(ITEMS, markers=("because",), confounds=()))
        )
        self.assertIn("only in causal — a shortcut candidate", shortcut)


class TheStampedPrepare(unittest.TestCase):
    def test_audit_prints_the_profile_and_says_what_is_open(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lab"
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(scaffold.main(["lab", str(root)]), 0)
                argv = [
                    "exp",
                    "judge",
                    "--repo",
                    str(root),
                    "--cost",
                    "seconds",
                    "--model",
                    "haiku",
                ]
                self.assertEqual(scaffold.main(argv), 0)
            raw = root / "data" / "raw" / "claims.jsonl"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text(
                "".join(
                    json.dumps({k: r[k] for k in ("id", "text", "gold")}) + "\n"
                    for r in ITEMS
                ),
                encoding="utf-8",
            )
            script = root / "experiments" / "01-judge" / "scripts" / "00_prepare.py"
            text = script.read_text(encoding="utf-8").replace(
                'REPO / "data" / "TODO"', 'REPO / "data" / "raw" / "claims.jsonl"'
            )
            script.write_text(text, encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(script), "--audit"],
                capture_output=True,
                text=True,
                cwd=root,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("causal              2  7.5", r.stdout)
            self.assertIn("none counted — MARKERS is None", r.stdout)
            script.write_text(
                text.replace(
                    "MARKERS: tuple[str, ...] | None = None",
                    'MARKERS: tuple[str, ...] | None = ("because", "drove")',
                ),
                encoding="utf-8",
            )
            r = subprocess.run(
                [sys.executable, str(script), "--audit"],
                capture_output=True,
                text=True,
                cwd=root,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("causal 2/2 · not_causal 0/2", r.stdout)  # fmt: skip


if __name__ == "__main__":
    unittest.main()
