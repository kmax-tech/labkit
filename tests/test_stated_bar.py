"""[criterion-1]'s bar in the estimator and the prompt skeleton: `at_least`,
a bar the task states, or `margin`, a lead over the null value — exactly
one, from one home (`labkit.formats.criterion_bar`;
docs/notes/2026-11-02-absolute-task-bar.md). A task's absolute bar written
as a margin passes a value below it; the stated bar holds at its boundary
whatever the null scores."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import random
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from labkit.tools import scaffold


def binary(tp1: int, fn1: int, fp0: int, tn0: int) -> list[tuple]:
    """(pred, gold) pairs by count: (1, 1), (0, 1), (1, 0), (0, 0)."""
    return [(1, 1)] * tp1 + [(0, 1)] * fn1 + [(1, 0)] * fp0 + [(0, 0)] * tn0


def three_classes(wrong: int) -> list[tuple]:
    """100 items of each of three classes, WRONG of each predicted as the
    next class: accuracy (300 − 3 WRONG) / 300, permutation expectation 1/3
    whatever the predictions."""
    return [
        pair
        for c in range(3)
        for pair in [(c, c)] * (100 - wrong) + [((c + 1) % 3, c)] * wrong
    ]


class StatedBar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        scaffold.stamp_lab(self.root, "stated-bar")

    def stamp(self, kind: str, constants: str | None = None, name: str = "bar"):
        """A stamped area NAME of KIND, its [criterion-1] constants replaced by
        CONSTANTS when given, and its measure script loaded as a module."""
        with contextlib.redirect_stdout(io.StringIO()):
            area, _ = scaffold.stamp_area(
                self.root, f"{name}-{kind}", repeat_cost="low", kind=kind
            )
        if constants is not None:
            protocol = next(area.glob("PROTOCOL-*.md"))
            text = protocol.read_text(encoding="utf-8")
            self.assertEqual(text.count("constants = { margin = 0.25 }"), 1)
            protocol.write_text(
                text.replace("constants = { margin = 0.25 }", constants),
                encoding="utf-8",
            )
        module_name = f"stated_bar_{name}_{kind}_{id(self)}"
        spec = importlib.util.spec_from_file_location(
            module_name, area / "scripts" / "01_measure.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        self.addCleanup(sys.modules.pop, module_name, None)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def apply_rows(measure, pairs: list[tuple]) -> list[dict]:
        """The registered lane over PAIRS and the null lane as apply keeps
        it: the same predictions against the gold permuted, each row naming
        its donor (`gold_of`)."""
        donors = list(range(len(pairs)))
        random.Random(0).shuffle(donors)
        reg = [
            measure.lane_row("registered", {"id": str(i)}, p, g)
            for i, (p, g) in enumerate(pairs)
        ]
        null = [
            measure.lane_row("null", {"id": str(i)}, p, pairs[d][1], gold_of=str(d))
            for i, ((p, _), d) in enumerate(zip(pairs, donors))
        ]
        return reg + null

    def verdict(self, measure, cfg, pairs: list[tuple]) -> tuple[float, float, bool]:
        m = measure.evaluate_rows(self.apply_rows(measure, pairs), cfg)
        return m["criterion_1_score"], m["criterion_1_threshold"], m["criterion_1_pass"]

    def test_a_bar_the_task_states_holds_at_its_boundary_whatever_the_expectation(self):
        """Accuracy at least 0.90: 0.89 misses and 0.90 meets it, with the
        permutation expectation at 0.52, 0.518, 0.498 and 1/3 — the bar is
        0.90 in every case. The twin: the same bar written as a margin of
        0.40 over the null passes 0.89 at 1/3."""
        measure = self.stamp("apply", "constants = { at_least = 0.9 }")
        self.assertEqual((measure.CONFIG.at_least, measure.CONFIG.margin), (0.9, None))
        cfg = replace(measure.CONFIG, null_band=1.0)  # the criterion alone
        cases = [
            (binary(55, 5, 5, 35), 0.90, True),  # expectation 0.52
            (binary(54, 6, 5, 35), 0.89, False),  # 0.518
            (binary(49, 11, 0, 40), 0.89, False),  # 0.498
            (three_classes(10), 0.90, True),  # 1/3
            (three_classes(11), 0.89, False),  # 1/3
        ]
        for pairs, score, met in cases:
            with self.subTest(score=score, n=len(pairs)):
                self.assertEqual(self.verdict(measure, cfg, pairs), (score, 0.9, met))
        as_margin = replace(cfg, at_least=None, margin=0.4)
        self.assertEqual(self.verdict(measure, as_margin, three_classes(11))[2], True)

    def test_a_lead_over_the_null_holds_at_its_boundary(self):
        """At least 0.05 over the null: with the permutation expectation at
        0.70 exactly (gold 150/50, predictions 180/20), 0.75 meets the bar
        0.75 and 0.74 misses it — exact, no float short by one ulp."""
        measure = self.stamp("apply", "constants = { margin = 0.05 }")
        cfg = replace(measure.CONFIG, null_band=1.0)
        self.assertEqual(
            self.verdict(measure, cfg, binary(140, 10, 40, 10)), (0.75, 0.75, True)
        )
        self.assertEqual(
            self.verdict(measure, cfg, binary(139, 11, 41, 9)), (0.74, 0.75, False)
        )

    def test_both_bars_or_none_are_refused_before_any_row(self):
        for name, constants, says in (
            (
                "both",
                "constants = { at_least = 0.9, margin = 0.05 }",
                "both `at_least` and `margin`",
            ),
            ("neither", "constants = { }", "neither `at_least` nor `margin`"),
        ):
            with self.subTest(constants=constants):
                with self.assertRaises(ValueError) as cm:
                    self.stamp("apply", constants, name)
                self.assertIn(says, str(cm.exception))
                self.assertIn("for a bar the task states", str(cm.exception))

    def test_a_stated_bar_still_owes_the_null_lane(self):
        """The null lane and [quality-check-2] hold beside a stated bar: a null
        off its band withholds the verdict, and a band is owed."""
        measure = self.stamp("apply", "constants = { at_least = 0.9 }")
        pairs = binary(60, 0, 0, 40)
        reg = self.apply_rows(measure, pairs)[: len(pairs)]
        null_as_registered = [
            measure.lane_row(
                "null", {"id": r["item"]}, r["pred"], r["gold"], gold_of=r["item"]
            )
            for r in reg
        ]
        m = measure.evaluate_rows(
            reg + null_as_registered, replace(measure.CONFIG, null_band=0.1)
        )
        self.assertEqual(
            (m["quality_check_2_pass"], m["criterion_1_pass"]), (False, None)
        )
        with self.assertRaisesRegex(ValueError, "registers no null_band"):
            measure.evaluate_rows(
                self.apply_rows(measure, pairs), replace(measure.CONFIG, null_band=None)
            )

    def test_fit_holds_a_stated_bar_whatever_its_refits(self):
        """At fit the null value is the mean of random refits; a stated bar
        does not move with them."""
        measure = self.stamp("fit", "constants = { at_least = 0.75 }")
        golds = ["pos"] * 6 + ["neg"] * 6
        flip = {"pos": "neg", "neg": "pos"}
        reg = [
            measure.lane_row("registered", {"id": str(i)}, g if i < 9 else flip[g], g)
            for i, g in enumerate(golds)
        ]
        for correct in ((4, 5, 6), (6, 7, 8)):
            nulls = [
                measure.lane_row(
                    "null", {"id": str(i)}, g if i < c else flip[g], g, draw=d
                )
                for d, c in enumerate(correct)
                for i, g in enumerate(golds)
            ]
            m = measure.evaluate_rows(
                reg + nulls, replace(measure.CONFIG, null_band=0.5)
            )
            self.assertEqual(
                (
                    m["criterion_1_score"],
                    m["criterion_1_threshold"],
                    m["criterion_1_pass"],
                ),
                (0.75, 0.75, True),
            )

    def test_a_stated_spearman_bar_is_not_a_margin_over_zero(self):
        """A task's "Spearman at least 0.95" registered as margin 0.05 puts
        the bar at 0.05. As `at_least = 0.95`, ten items with four adjacent
        pairs swapped (rho 0.9515) meet it and five swapped (rho 0.9394) miss
        it."""
        measure = self.stamp("apply", "constants = { at_least = 0.95 }")
        cfg = replace(measure.CONFIG, score="spearman", null_band=1.0)

        def swapped(k: int) -> list[tuple]:
            preds = [float(i) for i in range(10)]
            for j in range(k):
                preds[2 * j], preds[2 * j + 1] = preds[2 * j + 1], preds[2 * j]
            return [(p, float(g)) for g, p in enumerate(preds)]

        score, bar, met = self.verdict(measure, cfg, swapped(4))
        self.assertEqual((round(score, 4), bar, met), (0.9515, 0.95, True))
        score, bar, met = self.verdict(measure, cfg, swapped(5))
        self.assertEqual((round(score, 4), bar, met), (0.9394, 0.95, False))

    def test_the_stamped_sentence_names_both_forms(self):
        for kind in ("apply", "fit"):
            with self.subTest(kind=kind):
                with contextlib.redirect_stdout(io.StringIO()):
                    area, _ = scaffold.stamp_area(
                        self.root, f"sentence-{kind}", repeat_cost="low", kind=kind
                    )
                text = next(area.glob("PROTOCOL-*.md")).read_text(encoding="utf-8")
                self.assertIn(
                    "plus margin — or, for a bar the task states, at least at_least",
                    text,
                )


class PromptSkeleton(unittest.TestCase):
    """The prompt skeleton (apply with a model) reads the same two forms
    through `criterion_bar`; its null value is the null lane's accuracy."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        scaffold.stamp_lab(self.root, "stated-bar-prompt")

    def stamp(self, constants: str, name: str = "judge"):
        """A stamped prompt-skeleton area NAME, [criterion-1]'s constants
        CONSTANTS, its measure script loaded with the answers pos and neg."""
        with contextlib.redirect_stdout(io.StringIO()):
            area, _ = scaffold.stamp_area(
                self.root, name, repeat_cost="low", kind="apply", model="haiku"
            )
        protocol = next(area.glob("PROTOCOL-*.md"))
        text = protocol.read_text(encoding="utf-8")
        self.assertEqual(text.count("constants = { margin = 0.25 }"), 1)
        protocol.write_text(
            text.replace("constants = { margin = 0.25 }", constants), encoding="utf-8"
        )
        module_name = f"stated_bar_prompt_{name}_{id(self)}"
        spec = importlib.util.spec_from_file_location(
            module_name, area / "scripts" / "01_measure.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        self.addCleanup(sys.modules.pop, module_name, None)
        spec.loader.exec_module(module)
        module.ANSWERS.update({"Yes": "pos", "No": "neg"})
        return module

    @staticmethod
    def lane(name: str, correct: int) -> list[dict]:
        """100 items, gold half pos and half neg (chance: 50 right), the first
        CORRECT answered right."""
        rows = []
        for i in range(100):
            gold = "pos" if i % 2 == 0 else "neg"
            right = {"pos": "Yes", "neg": "No"}[gold]
            wrong = {"pos": "No", "neg": "Yes"}[gold]
            rows.append(
                {"lane": name, "gold": gold, "answer": right if i < correct else wrong}
            )
        return rows

    def verdict(
        self, measure, cfg, registered: int, null: int
    ) -> tuple[float, float, bool]:
        m = measure.evaluate_rows(
            self.lane("registered", registered) + self.lane("null", null), cfg
        )
        self.assertTrue(m["quality_check_2_pass"])
        return (
            m["criterion_1_accuracy"],
            m["criterion_1_threshold"],
            m["criterion_1_pass"],
        )

    def test_a_bar_the_task_states_holds_at_its_boundary_whatever_the_null(self):
        """Accuracy at least 0.90: 0.89 misses and 0.90 meets it with the null
        lane at 46 or 54 of 100; the twin, the same bar as a margin of 0.40,
        passes 0.89 over a null of 46 (bar 0.86)."""
        measure = self.stamp("constants = { at_least = 0.9 }")
        cfg = replace(measure.CONFIG, null_band_items=5)
        for null in (46, 54):
            with self.subTest(null=null):
                self.assertEqual(self.verdict(measure, cfg, 90, null), (0.9, 0.9, True))
                self.assertEqual(
                    self.verdict(measure, cfg, 89, null), (0.89, 0.9, False)
                )
        as_margin = replace(cfg, at_least=None, margin=0.4)
        self.assertIs(self.verdict(measure, as_margin, 89, 46)[2], True)

    def test_a_lead_over_the_null_holds_at_its_boundary(self):
        """At least 0.05 over a null lane at 0.50: 0.55 meets the bar, 0.54
        misses it."""
        measure = self.stamp("constants = { margin = 0.05 }")
        cfg = replace(measure.CONFIG, null_band_items=5)
        self.assertEqual(self.verdict(measure, cfg, 55, 50), (0.55, 0.55, True))
        self.assertEqual(self.verdict(measure, cfg, 54, 50), (0.54, 0.55, False))

    def test_both_bars_or_none_are_refused_before_any_row(self):
        for name, constants, says in (
            (
                "both",
                "constants = { at_least = 0.9, margin = 0.05 }",
                "both `at_least` and `margin`",
            ),
            ("neither", "constants = { }", "neither `at_least` nor `margin`"),
        ):
            with self.subTest(constants=constants):
                with self.assertRaises(ValueError) as cm:
                    self.stamp(constants, name)
                self.assertIn(says, str(cm.exception))

    def test_a_stated_bar_does_not_pass_a_failed_quality_check(self):
        """A perfect registered lane over a stated bar still has no verdict
        when [quality-check-2] fails (the null lane 30 items off chance) or
        [quality-check-1] fails (one empty answer past max_empty = 0): no
        threshold, no pass. The twin: the same lanes inside both checks pass."""
        measure = self.stamp("constants = { at_least = 0.9 }")
        cfg = replace(measure.CONFIG, null_band_items=5, max_empty=0)
        off_chance = measure.evaluate_rows(
            self.lane("registered", 100) + self.lane("null", 80), cfg
        )
        self.assertEqual(
            (
                off_chance["quality_check_2_pass"],
                off_chance["criterion_1_threshold"],
                off_chance["criterion_1_pass"],
            ),
            (False, None, None),
        )
        empty = self.lane("registered", 100)
        empty[0]["answer"] = ""
        too_empty = measure.evaluate_rows(empty + self.lane("null", 50), cfg)
        self.assertEqual(
            (
                too_empty["quality_check_1_pass"],
                too_empty["criterion_1_threshold"],
                too_empty["criterion_1_pass"],
            ),
            (False, None, None),
        )
        self.assertEqual(self.verdict(measure, cfg, 100, 50), (1.0, 0.9, True))

    def test_the_stamped_sentence_names_both_forms(self):
        with contextlib.redirect_stdout(io.StringIO()):
            area, _ = scaffold.stamp_area(
                self.root, "sentence", repeat_cost="low", kind="apply", model="haiku"
            )
        text = next(area.glob("PROTOCOL-*.md")).read_text(encoding="utf-8")
        self.assertIn("+ margin — or, for a bar the task states, >= at_least", text)


class CriterionBar(unittest.TestCase):
    """The one home of the two forms (`labkit.formats.criterion_bar`)."""

    def test_the_bar_is_the_registered_value_read_as_written(self):
        from fractions import Fraction

        from labkit.formats import criterion_bar

        self.assertEqual(
            criterion_bar.bar_of(0.9, None, Fraction(1, 3)), Fraction(9, 10)
        )
        self.assertEqual(
            criterion_bar.bar_of(None, 0.25, Fraction(5, 12)), Fraction(2, 3)
        )
        self.assertEqual(
            criterion_bar.bar_of(None, 0.05, Fraction(7, 10)), Fraction(3, 4)
        )
        self.assertEqual(
            criterion_bar.bar_of(None, 0.95, 0.0), 0.95
        )  # a float null stays a float
        self.assertEqual(criterion_bar.bar_of(0.95, None, -0.11), Fraction(19, 20))

    def test_both_or_neither_form_is_refused(self):
        from labkit.formats import criterion_bar

        for at_least, margin, says in (
            (0.9, 0.05, "both `at_least` and `margin`"),
            (None, None, "neither `at_least` nor `margin`"),
        ):
            with self.subTest(at_least=at_least, margin=margin):
                with self.assertRaises(ValueError) as cm:
                    criterion_bar.bar_of(at_least, margin, 0.5)
                self.assertIn(says, str(cm.exception))
        criterion_bar.require_one_form(0.9, None)
        criterion_bar.require_one_form(None, 0.05)


if __name__ == "__main__":
    unittest.main()
