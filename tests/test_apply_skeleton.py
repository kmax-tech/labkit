"""The local apply skeleton predicts with fixed instruments; only fit trains."""

from __future__ import annotations

import contextlib
import math
from dataclasses import asdict, replace
import importlib.util
import io
import pickle
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.tools import scaffold
from labkit.run import batch, provenance
from labkit.formats import answering_run
from protocol_fixture import run_record
from labkit.formats import runs


class ApplySkeleton(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        scaffold.stamp_lab(self.root, "local-predictor")

    def measure_module(self, kind):
        with contextlib.redirect_stdout(io.StringIO()):
            area, _ = scaffold.stamp_area(self.root, kind, repeat_cost="low", kind=kind)
        name = f"fixed_predictor_{kind}_{id(self)}"
        spec = importlib.util.spec_from_file_location(
            name, area / "scripts" / "01_measure.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)
        return area, module

    def test_importing_the_script_reads_no_predictor_file(self):
        # the area's test imports the script, so CONFIG must not hash
        # PREDICTOR_FILES at import; main() binds them
        with contextlib.redirect_stdout(io.StringIO()):
            area, _ = scaffold.stamp_area(
                self.root, "late", repeat_cost="low", kind="apply"
            )
        script = area / "scripts" / "01_measure.py"
        text = script.read_text(encoding="utf-8")
        script.write_text(
            text.replace(
                "PREDICTOR_FILES: dict[str, Path] = {}",
                'PREDICTOR_FILES: dict[str, Path] = {"primary": AREA / "absent.model"}',
            ),
            encoding="utf-8",
        )
        name = f"late_{id(self)}"
        spec = importlib.util.spec_from_file_location(name, script)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)  # no FileNotFoundError at import
        self.assertEqual(module.CONFIG.predictor_sha, {})
        with self.assertRaises(FileNotFoundError):
            module.predictor_digests()

    @staticmethod
    def items():
        return [
            {"id": str(i), "features": [i % 2], "gold": i % 2} for i in range(12)
        ] + [{"id": "unlabelled", "features": [1], "gold": None}]

    def test_apply_with_a_registered_fixed_null_trains_neither(self):
        area, measure = self.measure_module("apply")
        primary, null = mock.Mock(), mock.Mock()
        primary.predict.side_effect = lambda xs: [x[0] for x in xs]
        null.predict.side_effect = lambda xs: [0 for _ in xs]
        with (
            mock.patch.object(measure, "make_estimator", return_value=primary),
            mock.patch.object(measure, "make_null_predictor", return_value=null),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            rows = measure.measure(
                measure.CONFIG, self.items(), area / "output" / "kept.jsonl"
            )
        primary.fit.assert_not_called()
        null.fit.assert_not_called()
        self.assertEqual(
            [r["pred"] for r in rows if r["lane"] == "registered"],
            [i % 2 for i in range(12)],
        )
        self.assertEqual([r["pred"] for r in rows if r["lane"] == "null"], [0] * 12)
        metrics = measure.evaluate_rows(rows, self.reasoned(measure))
        self.assertEqual(
            (
                metrics["criterion_1_score"],
                metrics["quality_check_2_score"],
                metrics["n_test"],
            ),
            (1.0, 0.5, 1),
        )
        self.assertTrue(metrics["criterion_1_pass"])
        self.assertTrue(all(r["fold"] is None for r in rows))

    def test_apply_null_scores_the_same_predictions_against_permuted_labels(self):
        # no second instrument by default — the primary's predictions
        # against the gold permuted with the seed, as fit's lane
        area, measure = self.measure_module("apply")
        primary = mock.Mock()
        primary.predict.side_effect = lambda xs: [x[0] for x in xs]
        with (
            mock.patch.object(measure, "make_estimator", return_value=primary),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            rows = measure.measure(
                measure.CONFIG, self.items(), area / "output" / "kept.jsonl"
            )
            again = measure.apply_rows(measure.CONFIG, self.items(), False)
        primary.fit.assert_not_called()
        self.assertEqual(primary.predict.call_count, 4)  # labelled + test, twice
        reg = [r for r in rows if r["lane"] == "registered"]
        null = [r for r in rows if r["lane"] == "null"]
        self.assertEqual([r["pred"] for r in null], [r["pred"] for r in reg])
        self.assertEqual(
            sorted(r["gold"] for r in null), sorted(r["gold"] for r in reg)
        )
        by_id = {it["id"]: it["gold"] for it in self.items()}
        self.assertTrue(all(r["gold"] == by_id[r["gold_of"]] for r in null))
        self.assertNotEqual([r["gold_of"] for r in null], [r["item"] for r in null])
        self.assertEqual(
            [r["gold_of"] for r in null],
            [r["gold_of"] for r in again if r["lane"] == "null"],
        )
        metrics = measure.evaluate_rows(rows)
        self.assertEqual(metrics["criterion_1_score"], 1.0)
        self.assertLess(metrics["quality_check_2_score"], 1.0)

    def test_calibrate_null_previews_what_each_run_computes(self):
        """The preview puts the predictions on the labelled items through the
        registered rule, as each evaluation does on the kept rows: 200
        permutations, the 0.99 quantile by its exact rank, rounded up, the
        same each time. It never trains and registers nothing."""
        area, measure = self.measure_module("apply")
        primary = self.primary()
        with mock.patch.object(measure, "make_estimator", return_value=primary):
            cal = measure.calibrate_null(measure.CONFIG, self.items())
            again = measure.calibrate_null(measure.CONFIG, self.items())
            rows = measure.apply_rows(measure.CONFIG, self.items(), False)
        primary.fit.assert_not_called()
        self.assertEqual(len(cal["null_scores"]), 200)
        self.assertEqual(cal, again)
        off = sorted(abs(s - cal["target"]) for s in cal["null_scores"])
        self.assertEqual(cal["deviation"], off[197])
        self.assertEqual(cal["rounded"], math.ceil(cal["deviation"] * 100) / 100)
        # no permutation is the truth
        self.assertLess(cal["deviation"], 1 - cal["target"])
        m = measure.evaluate_rows(rows)
        self.assertEqual(m["quality_check_2_null_band"], cal["rounded"])

    # -- [quality-check-2]'s permitted deviation, computed per run by the registered rule
    def primary(self):
        primary = mock.Mock()
        primary.predict.side_effect = lambda xs: [x[0] for x in xs]
        return primary

    def test_the_untouched_stamp_copies_no_constant(self):
        """The calibration rule's None defaults are no copies of the registered
        rule: an untouched apply or fit stamp reports none."""
        from labkit.checks import code_check
        from labkit.formats import promises

        for kind in ("apply", "fit"):
            area, measure = self.measure_module(kind)
            block = promises.load(measure.PROTOCOL)
            for p in block.promises:
                with self.subTest(kind=kind, promise=p.id):
                    self.assertEqual(
                        code_check.constant_copies(area, measure.PROTOCOL, p), []
                    )

    def test_the_permitted_deviation_is_the_runs_own_and_repeatable(self):
        """Each run computes [quality-check-2]'s permitted deviation from its
        own registered predictions: the same inputs give the same value in
        any row order and under any run seed (the calibration seed is its
        own), and repaired predictions get their own value — the second run
        after a repair is no longer held to the first run's (replay
        2026-11-14, docs/notes/2026-11-14-apply-chance-comparison.md)."""
        _, measure = self.measure_module("apply")
        with mock.patch.object(measure, "make_estimator", return_value=self.primary()):
            rows = measure.apply_rows(measure.CONFIG, self.items(), False)
            other_seed = measure.apply_rows(
                replace(measure.CONFIG, seed=7), self.items(), False
            )
        m = measure.evaluate_rows(rows)
        rule = measure.deviation_rule(measure.CONFIG)
        assert rule is not None
        reg = [
            (r["item"], r["pred"], r["gold"]) for r in rows if r["lane"] == "registered"
        ]
        self.assertEqual(
            m["quality_check_2_null_band"],
            measure.deviation_by_rule(measure.CONFIG, reg, rule)["rounded"],
        )
        self.assertEqual(
            measure.evaluate_rows(list(reversed(rows)))["quality_check_2_null_band"],
            m["quality_check_2_null_band"],
        )
        self.assertNotEqual(
            [r["gold_of"] for r in other_seed if r["lane"] == "null"],
            [r["gold_of"] for r in rows if r["lane"] == "null"],
        )  # the run seed moves the null draw ...
        self.assertEqual(
            measure.evaluate_rows(other_seed, replace(measure.CONFIG, seed=7))[
                "quality_check_2_null_band"
            ],
            m["quality_check_2_null_band"],
        )  # ... and not the permitted deviation
        repaired = mock.Mock()
        repaired.predict.side_effect = lambda xs: [
            1 if i == 0 else 0 for i, _ in enumerate(xs)
        ]
        with mock.patch.object(measure, "make_estimator", return_value=repaired):
            after = measure.apply_rows(measure.CONFIG, self.items(), False)
        self.assertNotEqual(
            measure.evaluate_rows(after)["quality_check_2_null_band"],
            m["quality_check_2_null_band"],
        )

    @staticmethod
    def rich_rows(measure) -> list[dict]:
        """Forty items with continuous gold and noisy predictions (spearman),
        and the seeded null lane: fine enough that the rows' order, the
        seed and the quantile's rank each move the permitted deviation."""
        import random as _random

        rng = _random.Random(3)
        golds = [rng.uniform(0, 5) for _ in range(40)]
        preds = [g + rng.gauss(0, 2) for g in golds]
        donors = list(range(40))
        rng.shuffle(donors)
        reg = [
            measure.lane_row("registered", {"id": f"i{i}"}, p, g)
            for i, (p, g) in enumerate(zip(preds, golds))
        ]
        null = [
            measure.lane_row("null", {"id": f"i{i}"}, p, golds[d], gold_of=f"i{d}")
            for i, (p, d) in enumerate(zip(preds, donors))
        ]
        return reg + null

    def test_the_permitted_deviation_holds_on_fine_grained_data(self):
        """On forty continuous items, the exact quantile: the rows' order and
        the run's seed leave it as it is, the calibration seed moves it, and
        it is the rule's exact rank (the 198th of 200 deviations), where the
        neighbouring ranks differ, so an off-by-one shows. The kept value is
        it rounded up to two places."""
        _, measure = self.measure_module("apply")
        cfg = replace(measure.CONFIG, score="spearman")
        rows = self.rich_rows(measure)
        reg = [
            (r["item"], r["pred"], r["gold"]) for r in rows if r["lane"] == "registered"
        ]
        rule = (0.99, 200, cfg.null_band_seed)
        held = measure.deviation_by_rule(cfg, reg, rule)
        self.assertEqual(
            measure.deviation_by_rule(cfg, list(reversed(reg)), rule)["deviation"],
            held["deviation"],
        )
        self.assertEqual(
            measure.deviation_by_rule(replace(cfg, seed=7), reg, rule)["deviation"],
            held["deviation"],
        )
        self.assertNotEqual(
            measure.deviation_by_rule(cfg, reg, (0.99, 200, 2))["deviation"],
            held["deviation"],
        )
        off = sorted(abs(s - held["target"]) for s in held["null_scores"])
        self.assertEqual(held["deviation"], off[197])
        self.assertNotEqual(off[196], off[197])
        self.assertNotEqual(off[198], off[197])
        value = measure.evaluate_rows(list(reversed(rows)), replace(cfg, seed=7))[
            "quality_check_2_null_band"
        ]
        self.assertEqual(value, math.ceil(off[197] * 100) / 100)

    def test_the_null_check_interval_is_inclusive(self):
        """The null draw exactly at the permitted deviation from its target
        passes; a hair inside the draw's distance fails."""
        _, measure = self.measure_module("apply")
        rows = self.chance_rows(
            measure, wrong=2, null_correct=10
        )  # null 10/16, target 1/2
        for deviation, passed in ((0.125, True), (0.12, False)):
            with mock.patch.object(measure, "run_null_band", return_value=deviation):
                self.assertIs(
                    measure.evaluate_rows(rows)["quality_check_2_pass"], passed
                )

    def test_the_evaluation_refuses_a_rule_without_a_permutation_spread(self):
        """Null rows without donors (fit, a fixed null predictor) under a
        registered calibration rule: refused in the evaluation too, not only
        before the run. And a fit or fixed null without null_band is refused
        before the run opens, not after its fits."""
        _, measure = self.measure_module("apply")
        rows = self.chance_rows(measure, wrong=2, null_correct=8)
        fitted = [{k: v for k, v in r.items() if k != "gold_of"} for r in rows]
        with self.assertRaisesRegex(ValueError, "registers a calibration rule"):
            measure.evaluate_rows(fitted)
        _, fit = self.measure_module("fit")
        with self.assertRaisesRegex(SystemExit, "registers no null_band"):
            fit.null_check(replace(fit.CONFIG, null_band=None))

    def test_the_rule_is_registered_whole_and_null_band_is_not_registered_beside_it(
        self,
    ):
        """At apply with the seeded permuted null the protocol registers the
        rule — quantile, permutations, calibration seed — together, and no
        null_band: a registered value beside the computed one would be a
        second truth. Both refusals come before the run opens. The twin: the
        stamped registration passes."""
        _, measure = self.measure_module("apply")
        with self.assertRaisesRegex(ValueError, "registered together"):
            replace(measure.CONFIG, null_band_seed=None)
        measure.null_check(measure.CONFIG)
        both = replace(measure.CONFIG, null_band=0.1)
        with self.assertRaisesRegex(SystemExit, "drop null_band"):
            measure.null_check(both)
        with mock.patch.object(measure, "make_estimator", return_value=self.primary()):
            rows = measure.apply_rows(measure.CONFIG, self.items(), False)
        with self.assertRaisesRegex(ValueError, "registers null_band"):
            measure.evaluate_rows(rows, both)
        none = replace(
            measure.CONFIG,
            null_band_quantile=None,
            null_permutations=None,
            null_band_seed=None,
        )
        with self.assertRaisesRegex(SystemExit, "registers no calibration rule"):
            measure.null_check(none)

    def test_a_reasoned_null_band_where_there_is_no_permutation_spread(self):
        """At fit and with a fixed null predictor the permitted deviation is a
        registered, reasoned null_band, and a calibration rule there is
        refused: it would calibrate nothing. The twin: the fit stamp
        passes."""
        _, fit = self.measure_module("fit")
        fit.null_check(fit.CONFIG)
        _, measure = self.measure_module("apply")
        with (
            mock.patch.object(measure, "make_null_predictor", return_value=mock.Mock()),
            self.assertRaisesRegex(SystemExit, "fixed null predictor"),
        ):
            measure.null_check(measure.CONFIG)
        with mock.patch.object(
            measure, "make_null_predictor", return_value=mock.Mock()
        ):
            measure.null_check(self.reasoned(measure))

    @staticmethod
    def reasoned(measure, band: float | None = 0.1):
        """The apply CONFIG as a protocol with a fixed null or a null order
        registers it: a reasoned null_band (or none), no calibration rule."""
        return replace(
            measure.CONFIG,
            null_band=band,
            null_band_quantile=None,
            null_permutations=None,
            null_band_seed=None,
        )

    @staticmethod
    def permuted_rows(measure, preds: list, golds: list) -> list[dict]:
        """The registered lane of PREDS against GOLDS and the seeded null
        lane: the same predictions against the gold of a shuffled donor."""
        import random as _random

        donors = list(range(len(golds)))
        _random.Random(5).shuffle(donors)
        reg = [
            measure.lane_row("registered", {"id": f"i{i}"}, p, g)
            for i, (p, g) in enumerate(zip(preds, golds))
        ]
        null = [
            measure.lane_row("null", {"id": f"i{i}"}, p, golds[d], gold_of=f"i{d}")
            for i, (p, d) in enumerate(zip(preds, donors))
        ]
        return reg + null

    def test_constant_predictions_give_the_deviation_zero(self):
        """Predictions with one answer for every item score alike under
        every permutation: the permitted deviation is 0, the null check
        exact and passed, criterion-1 and the offered criterion-2 judged
        (the score is the expectation, so criterion-2 is not reached), the
        yield check reported — in the preview and in the evaluation. For
        accuracy, auc and r2; r2 exactly, where floats scored the
        permutations apart by rounding and the rounded-up deviation was
        0.01. The twin: predictions that vary give a deviation above 0."""
        area, _ = self.measure_module("apply")
        self.activate(area, table=True, code=True)
        measure = self.reloaded(area)
        one_class = mock.Mock()
        one_class.predict.side_effect = lambda xs: [0 for _ in xs]
        with mock.patch.object(measure, "make_estimator", return_value=one_class):
            cal = measure.calibrate_null(measure.CONFIG, self.items())
            rows = measure.apply_rows(measure.CONFIG, self.items(), False)
        self.assertEqual((cal["deviation"], cal["rounded"]), (0, 0))
        m = measure.evaluate_rows(rows)
        self.assertEqual(m["quality_check_2_null_band"], 0)
        self.assertIs(m["quality_check_2_pass"], True)
        self.assertIs(m["quality_check_1_pass"], True)
        self.assertIsNotNone(m["criterion_1_pass"])
        self.assertEqual(m["criterion_2_threshold"], m["criterion_1_score"])
        self.assertIs(m["criterion_2_pass"], False)
        import random as _random

        rng = _random.Random(2)
        floats = [rng.uniform(0, 5) for _ in range(30)]
        for score, preds, golds in (
            ("auc", [0.7] * 12, [i % 2 for i in range(12)]),
            ("r2", [2.3] * 30, floats),
        ):
            with self.subTest(score=score):
                cfg = replace(measure.CONFIG, score=score)
                m = measure.evaluate_rows(
                    self.permuted_rows(measure, preds, golds), cfg
                )
                self.assertEqual(m["quality_check_2_null_band"], 0)
                self.assertIs(m["quality_check_2_pass"], True)
        with mock.patch.object(measure, "make_estimator", return_value=self.primary()):
            cal = measure.calibrate_null(measure.CONFIG, self.items())
        self.assertGreater(cal["deviation"], 0)

    def test_no_prediction_or_an_undefined_score_gives_no_deviation(self):
        """Three ways the null does not move that are no deviation 0, each
        loud after the run: no item has a prediction; at accuracy no
        prediction is a gold value (labels from another vocabulary, varied
        or constant — apply-screen, 2026-10-29); spearman on constant
        predictions, where rank correlation is undefined. The twin:
        predictions in the gold's labels with one missing give a
        deviation."""
        _, measure = self.measure_module("apply")
        golds = [i % 2 for i in range(12)]
        with self.assertRaisesRegex(ValueError, "has a prediction"):
            measure.evaluate_rows(self.permuted_rows(measure, [None] * 12, golds))
        for preds in (["neg", "pos"] * 6, ["x"] * 12):
            with (
                self.subTest(preds=preds[:2]),
                self.assertRaisesRegex(ValueError, "no prediction is a gold value"),
            ):
                measure.evaluate_rows(self.permuted_rows(measure, preds, golds))
        with self.assertRaisesRegex(ValueError, "constant"):
            measure.evaluate_rows(
                self.permuted_rows(measure, [1.0] * 12, [float(i) for i in range(12)]),
                replace(measure.CONFIG, score="spearman"),
            )
        m = measure.evaluate_rows(
            self.permuted_rows(measure, [None, *golds[1:]], golds),
            replace(measure.CONFIG, max_empty=1),
        )
        self.assertGreater(m["quality_check_2_null_band"], 0)

    def test_main_refuses_before_the_run_opens(self):
        _, measure = self.measure_module("apply")
        with (
            mock.patch.object(sys, "argv", ["01_measure.py"]),
            mock.patch.object(
                measure, "CONFIG", replace(measure.CONFIG, null_band=0.1)
            ),
            mock.patch.object(measure, "read_jsonl", return_value=self.items()),
            mock.patch.object(measure, "make_estimator", return_value=self.primary()),
            mock.patch.object(measure.runlog, "run") as start,
            self.assertRaises(SystemExit),
        ):
            measure.main()
        start.assert_not_called()

    def test_the_permutation_expectation_is_exact(self):
        """The bar at apply: the mean score over EVERY permutation of the gold,
        computed in closed form — checked against all 720 orderings of six
        items, for accuracy (with a missing prediction), auc, r2 and
        spearman (tied gold, so the draws are floats)."""
        import itertools
        from fractions import Fraction

        _, measure = self.measure_module("apply")
        cases = {
            "accuracy": (
                ["a", "a", "b", None, "b", "a"],
                ["a", "b", "b", "a", "a", "b"],
            ),
            "auc": ([0.9, 0.2, 0.7, 0.4, None, 0.1], [1, 0, 1, 0, 1, 0]),
            "r2": ([1.0, 2.5, 0.5, None, 3.0, 2.0], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
            "spearman": (
                [1.0, 2.5, 0.5, None, 3.0, 2.0],
                [1.0, 2.0, 2.0, 4.0, 5.0, 6.0],
            ),
        }
        for score, (preds, golds) in cases.items():
            with self.subTest(score=score):
                draws = [
                    measure.SCORES[score](list(zip(preds, perm)))
                    for perm in itertools.permutations(golds)
                ]
                exact = measure.permutation_expectation(score, list(zip(preds, golds)))
                if score == "spearman":
                    self.assertAlmostEqual(exact, sum(draws) / len(draws), places=12)
                else:
                    self.assertEqual(exact, sum(draws, Fraction(0)) / len(draws))

    def test_spearman_is_the_pearson_correlation_of_mean_ranks(self):
        """The skeleton offers Spearman beside accuracy, r2 and auc.
        Checked by hand:
        x = 1, 2, 2, 3 ranks 1, 2.5, 2.5, 4; y = 0.5, 0.1, 0.9, 0.7 ranks
        2, 1, 4, 3; the centred products sum to 1.5, the squares to 4.5 and
        5, so rho = 1.5 / sqrt(22.5). Without ties rho is exact: 1 and -1
        for a monotone pair; a missing prediction ranks below every real
        one. A constant vector has no rank correlation and is refused,
        never 0; chance and the permutation expectation are 0."""
        from fractions import Fraction

        _, measure = self.measure_module("apply")
        rho = measure.SCORES["spearman"]
        tied = rho(list(zip([1, 2, 2, 3], [0.5, 0.1, 0.9, 0.7])))
        self.assertAlmostEqual(tied, 1.5 / math.sqrt(22.5), places=15)
        self.assertEqual(rho([(1, 10.0), (2, 20.0), (3, 30.0)]), Fraction(1))
        self.assertEqual(rho([(1, 30.0), (2, 20.0), (3, 10.0)]), Fraction(-1))
        self.assertIsInstance(rho([(1, 30.0), (2, 20.0), (3, 10.0)]), Fraction)
        self.assertEqual(rho([(None, 0.0), (2, 20.0), (3, 30.0)]), Fraction(1))
        with self.assertRaisesRegex(ValueError, "predictions are constant"):
            rho([(1.0, 1.0), (1.0, 2.0), (1.0, 3.0)])
        with self.assertRaisesRegex(ValueError, "gold values are constant"):
            rho([(1.0, 5.0), (2.0, 5.0), (3.0, 5.0)])
        self.assertEqual(measure.chance_of("spearman", [1.0, 2.0]), 0)
        self.assertEqual(
            measure.permutation_expectation("spearman", [(1, 2.0), (2, 1.0)]), 0
        )

    def test_a_registered_null_order_is_the_control_and_its_score_the_bar(self):
        """A registered null order is a staged permutation, read, never
        regenerated. With NULL_ORDER the null lane follows the file, its
        score plus margin is the bar, and no band is forced where none is
        registered. The twins: no band and no order is refused; an order that
        is no permutation of the items is refused."""
        import json as _json

        area, measure = self.measure_module("apply")
        order = [11, 0, 5, 3, 7, 1, 9, 2, 10, 4, 8, 6]
        (area / "null_order.json").write_text(_json.dumps(order), encoding="utf-8")
        primary = mock.Mock()
        primary.predict.side_effect = lambda xs: [x[0] for x in xs]
        cfg = self.reasoned(measure, None)
        with (
            mock.patch.object(measure, "NULL_ORDER", area / "null_order.json"),
            mock.patch.object(measure, "make_estimator", return_value=primary),
        ):
            rows = measure.apply_rows(cfg, self.items(), False)
            null = [r for r in rows if r["lane"] == "null"]
            self.assertEqual([r["gold_of"] for r in null], [str(j) for j in order])
            m = measure.evaluate_rows(rows, cfg)
            self.assertAlmostEqual(
                m["criterion_1_threshold"],
                m["quality_check_2_score"] + cfg.margin,
                places=12,
            )
            self.assertTrue(m["quality_check_2_pass"])
            self.assertIn("null_order", measure.data_files())
            (area / "null_order.json").write_text(
                _json.dumps(order[:-1]), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "not a permutation"):
                measure.apply_rows(cfg, self.items(), False)
        with mock.patch.object(measure, "make_estimator", return_value=primary):
            rows = measure.apply_rows(cfg, self.items(), False)
        with self.assertRaisesRegex(ValueError, "computed per run"):
            measure.evaluate_rows(rows, cfg)  # seeded rows: the rule is owed

    def test_apply_holds_the_bar_and_the_null_to_the_expectation(self):
        """A permuted null's draw is the anchor, not the bar: the same
        registered lane passes or fails by the expectation alone, whatever
        the draw, which alone can put the bar anywhere in a wide range. The
        twin: a fitted null (no
        donors) keeps its score as the bar and chance as [quality-check-2]'s target."""
        _, measure = self.measure_module("apply")
        golds = ["pos"] * 6 + ["neg"] * 6
        reg = [
            measure.lane_row("registered", {"id": str(i)}, g, g)
            for i, g in enumerate(golds)
        ]

        def null(correct: int, permuted: bool) -> list[dict]:
            rows = []
            for i, g in enumerate(golds):
                pred = g if i < correct else ("neg" if g == "pos" else "pos")
                more = {"gold_of": str(i)} if permuted else {}
                rows.append(measure.lane_row("null", {"id": str(i)}, pred, g, **more))
            return rows

        cfg = measure.CONFIG
        for drawn in (5, 6, 7):
            m = measure.evaluate_rows(reg + null(drawn, True), cfg)
            self.assertEqual(m["quality_check_2_target"], 0.5)  # q = p = 1/2: 1/4 + 1/4
            self.assertEqual(
                m["criterion_1_threshold"], 0.5 + cfg.margin
            )  # the draw moves nothing
        fitted = measure.evaluate_rows(reg + null(7, False), self.reasoned(measure))
        self.assertEqual(fitted["criterion_1_threshold"], 7 / 12 + cfg.margin)

    def chance_rows(self, measure, *, wrong: int, null_correct: int) -> list[dict]:
        """Sixteen balanced items: the registered lane with WRONG errors per
        class (the predictions stay balanced, so the expectation is 1/2), the
        permuted null lane with NULL_CORRECT of 16 right."""
        golds = ["pos"] * 8 + ["neg"] * 8
        flip = {"pos": "neg", "neg": "pos"}
        rows = []
        for i, g in enumerate(golds):
            pred = flip[g] if i % 8 < wrong else g
            rows.append(measure.lane_row("registered", {"id": str(i)}, pred, g))
            null_pred = g if i < null_correct else flip[g]
            rows.append(
                measure.lane_row("null", {"id": str(i)}, null_pred, g, gold_of=str(i))
            )
        return rows

    def activate(self, area: Path, *, table: bool, code: bool) -> None:
        """The two documented steps that turn the offered criterion-2 on:
        TABLE uncomments its table in the protocol and names the id in the
        Inference criterion field; CODE uncomments the block between the
        criterion-2 markers in scripts/01_measure.py."""
        if table:
            protocol = next(area.glob("PROTOCOL-*.md"))
            offered = (
                "# [[promise]]",
                "# id =",
                "# key =",
                "# sentence =",
                "# scope =",
            )
            text = "\n".join(
                line[2:] if line.startswith(offered) else line
                for line in protocol.read_text(encoding="utf-8").split("\n")
            )
            named = text.replace(
                "- **Inference criterion:** [criterion-1] ",
                "- **Inference criterion:** [criterion-1] [criterion-2] <above the band> · ",
                1,
            )
            self.assertNotEqual(named, text)
            protocol.write_text(named, encoding="utf-8")
        if code:
            script = area / "scripts" / "01_measure.py"
            out, inside = [], False
            for line in script.read_text(encoding="utf-8").split("\n"):
                if line.strip() in ("# --- criterion-2 begin", "# --- criterion-2 end"):
                    inside = line.strip().endswith("begin")
                elif inside:
                    line = line.replace("# ", "", 1)
                out.append(line)
            script.write_text("\n".join(out), encoding="utf-8")

    def reloaded(self, area: Path):
        """The area's measure script imported afresh, under a unique name."""
        name = f"chance_{id(self)}_{len(sys.modules)}"
        spec = importlib.util.spec_from_file_location(
            name, area / "scripts" / "01_measure.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)
        return module

    def test_criterion_2_holds_the_score_strictly_above_expectation_plus_band(self):
        """The offered comparison with chance, both steps taken: the
        comparison threshold is the permutation expectation plus the run's
        own permitted deviation. Strictness, with the deviation held at a
        known value: 12 of 16 right is 0.75, the expectation 1/2; at 0.25 the
        score sits on the threshold and fails, at 0.24 it passes. A failed
        quality check gives no verdict. The twin: the stamp as it is reports
        no criterion-2 key at all."""
        area, plain = self.measure_module("apply")
        rows = self.chance_rows(plain, wrong=2, null_correct=8)
        self.assertFalse(
            [k for k in plain.evaluate_rows(rows) if k.startswith("criterion_2")]
        )
        self.activate(area, table=True, code=True)
        measure = self.reloaded(area)
        self.assertTrue(measure.CONFIG.chance_criterion)
        m = measure.evaluate_rows(rows)
        self.assertEqual(
            m["criterion_2_threshold"], 0.5 + m["quality_check_2_null_band"]
        )
        for deviation, passed in ((0.25, False), (0.24, True)):
            with mock.patch.object(measure, "run_null_band", return_value=deviation):
                m = measure.evaluate_rows(rows)
            self.assertEqual(m["criterion_2_threshold"], 0.5 + deviation)
            self.assertIs(m["criterion_2_pass"], passed)
        far = self.chance_rows(measure, wrong=2, null_correct=16)  # null at 1.0
        m = measure.evaluate_rows(far)
        self.assertIs(m["quality_check_2_pass"], False)
        self.assertIsNone(m["criterion_2_pass"])
        m = measure.evaluate_rows(
            rows, replace(measure.CONFIG, max_empty=-1)
        )  # yield fails
        self.assertIs(m["quality_check_1_pass"], False)
        self.assertIsNone(m["criterion_2_pass"])

    def test_criterion_2_is_refused_where_the_band_is_no_permutation_quantile(self):
        """At fit, with a registered null order and with a fixed null
        predictor the permitted deviation is no permutation quantile of
        these predictions, so the comparison would state a threshold it
        does not have: refused in the evaluation and before the run opens."""
        _, measure = self.measure_module("apply")
        on = replace(self.reasoned(measure), chance_criterion=True)
        rows = self.chance_rows(measure, wrong=2, null_correct=8)
        with (
            mock.patch.object(measure, "NULL_ORDER", Path("null_order.json")),
            self.assertRaisesRegex(ValueError, "permutation quantile"),
        ):
            measure.evaluate_rows(rows, on)
        fitted = [{k: v for k, v in r.items() if k != "gold_of"} for r in rows]
        with self.assertRaisesRegex(ValueError, "permutation quantile"):
            measure.evaluate_rows(fitted, on)
        measure.null_check(replace(measure.CONFIG, chance_criterion=True))
        for patch, where in (
            (
                mock.patch.object(
                    measure, "make_null_predictor", return_value=mock.Mock()
                ),
                "a fixed null predictor",
            ),
            (
                mock.patch.object(measure, "NULL_ORDER", Path("null_order.json")),
                "a registered NULL_ORDER",
            ),
            (mock.patch.object(measure, "KIND", "fit"), "kind fit"),
        ):
            with (
                patch,
                self.assertRaisesRegex(SystemExit, rf"\[criterion-2\].*{where}"),
            ):
                measure.null_check(on)

    def area_tests(self) -> subprocess.CompletedProcess:
        """The stamped area's own tests, run as finalize runs them."""
        (test,) = self.root.glob("tests/test_01_*.py")
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test)],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

    def chance_findings(self, area: Path) -> list[tuple[str, str]]:
        """code-check's (grade, text) findings that name criterion-2."""
        from labkit.checks import code_check

        protocol = next(area.glob("PROTOCOL-*.md"))
        text = protocol.read_text(encoding="utf-8")
        found = code_check.code_findings(
            area, protocol, text, self.root, block_told=False
        )
        return [
            (f.grade, f.text)
            for f in found
            if "criterion-2" in f.text or "criterion_2" in f.text
        ]

    def test_a_fit_area_gets_no_criterion_2_finding(self):
        # the offered block is commented out in the skeleton both kinds share
        area, _ = self.measure_module("fit")
        self.assertEqual(self.chance_findings(area), [])

    def test_the_apply_stamp_offers_criterion_2_in_two_steps(self):
        """The stamp registers no criterion-2 and writes no key for it (no
        duty, no standing warning). Each step alone is held by code-check —
        the table without the code a BLOCKER, the code without the table a
        WARNING —; both together are clean, and the area's own tests stay
        green before and after."""
        from labkit.formats import promises
        from labkit.formats.gate import BLOCKER, WARNING

        area, measure = self.measure_module("apply")
        protocol = next(area.glob("PROTOCOL-*.md"))
        text = protocol.read_text(encoding="utf-8")
        self.assertIn('# id = "criterion-2"', text)
        self.assertNotIn("criterion-2", promises.load(protocol).by_id())
        self.assertNotIn("criterion-2", promises.ids_in_prose(text))
        self.assertFalse(measure.CONFIG.chance_criterion)
        self.assertEqual(self.chance_findings(area), [])
        plain = self.area_tests()
        self.assertEqual(plain.returncode, 0, plain.stdout)
        script = area / "scripts" / "01_measure.py"
        stamped_script = script.read_text(encoding="utf-8")

        self.activate(area, table=False, code=True)
        self.assertEqual({g for g, _ in self.chance_findings(area)}, {WARNING})
        script.write_text(stamped_script, encoding="utf-8")

        self.activate(area, table=True, code=False)
        self.assertEqual(
            promises.load(protocol).by_id()["criterion-2"].key, "criterion_2_pass"
        )
        self.assertIn(BLOCKER, {g for g, _ in self.chance_findings(area)})

        self.activate(area, table=False, code=True)
        self.assertEqual(self.chance_findings(area), [])
        self.assertTrue(self.reloaded(area).CONFIG.chance_criterion)
        registered = self.area_tests()
        self.assertEqual(registered.returncode, 0, registered.stdout)

    def test_the_scored_lanes_are_the_ones_finalize_reads(self):
        # the skeleton's lane names and finalize's null-lane station must
        # agree, or the station holds nothing
        from labkit.checks import run_record_check

        _, measure = self.measure_module("apply")
        self.assertEqual(measure.SCORED_LANES, run_record_check.NULL_LANES)

    def test_each_skeleton_keeps_c1_under_its_contract_key(self):
        # the key comes from the contract, not typed by hand
        from labkit.formats import standard_contract
        from labkit.tools.scaffold import template

        for sk in (standard_contract.ESTIMATOR, standard_contract.MODEL):
            with self.subTest(sk=sk.instrument):
                measure = next(t for t, dest in sk.scripts if dest == "01_measure.py")
                key = standard_contract.criterion_key(sk)
                self.assertIn(f'CRITERION_VALUE_KEY = "{key}"', template(measure))
        with self.assertRaises(ValueError):
            standard_contract.criterion_key(standard_contract.COMPUTE)

    def test_calibrate_null_has_no_free_path_at_fit_or_for_a_fixed_null(self):
        _, fit = self.measure_module("fit")
        with self.assertRaisesRegex(ValueError, "computed per run only at kind apply"):
            fit.calibrate_null(fit.CONFIG, self.items())
        _, measure = self.measure_module("apply")
        with (
            mock.patch.object(measure, "make_null_predictor", return_value=mock.Mock()),
            self.assertRaisesRegex(ValueError, "fixed null predictor"),
        ):
            measure.calibrate_null(measure.CONFIG, self.items())

    def test_apply_refuses_a_missing_prediction_instead_of_dropping_an_item(self):
        area, measure = self.measure_module("apply")
        primary = mock.Mock()
        primary.predict.return_value = [0]
        with (
            mock.patch.object(measure, "make_estimator", return_value=primary),
            mock.patch.object(measure, "make_null_predictor", return_value=mock.Mock()),
            self.assertRaises(ValueError),
        ):
            measure.measure(
                measure.CONFIG, self.items(), area / "output" / "kept.jsonl"
            )

    def test_apply_protocols_name_the_permuted_label_null(self):
        for cost in ("low", "high"):
            for report in (False, True):
                with self.subTest(cost=cost, report=report):
                    text = scaffold.protocol_stamp(
                        self.root, "fixed", cost, "apply", False, report
                    )
                    self.assertIn("permuted-label lane", text)
                    self.assertNotIn("out-of-fold prediction", text)
                    if not report:  # the pilot stamp answers the null field
                        self.assertIn("gold labels permuted with the seed", text)

    def test_declared_primary_and_null_files_bind_rows_config_and_run_inputs(self):
        area, measure = self.measure_module("apply")
        primary = area / "primary.model"
        null = area / "null.model"
        primary.write_bytes(pickle.dumps({"weight": 1.0}))
        null.write_bytes(pickle.dumps({"weight": 0.0}))
        measure.PREDICTOR_FILES.update(primary=primary, null=null)
        before = replace(measure.CONFIG, predictor_sha=measure.predictor_digests())
        self.assertEqual(
            measure.data_files(),
            {
                "prepared": measure.ITEMS,
                "predictor_primary": provenance.BinaryInput(primary),
                "predictor_null": provenance.BinaryInput(null),
            },
        )
        predictor = mock.Mock()
        predictor.predict.side_effect = lambda xs: [0 for _ in xs]
        for artifact in (primary, null):
            with self.subTest(artifact=artifact.name):
                output = area / "output" / f"{artifact.name}.jsonl"
                current = replace(
                    measure.CONFIG, predictor_sha=measure.predictor_digests()
                )
                first_instrument = measure.instrument(current, self.items())
                with (
                    mock.patch.object(
                        measure, "make_estimator", return_value=predictor
                    ),
                    mock.patch.object(
                        measure, "make_null_predictor", return_value=predictor
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    measure.measure(current, self.items(), output)
                artifact.write_bytes(artifact.read_bytes() + b"\xff changed")
                self.assertNotEqual(
                    first_instrument, measure.instrument(current, self.items())
                )
                after = replace(
                    measure.CONFIG, predictor_sha=measure.predictor_digests()
                )
                with (
                    mock.patch.object(
                        measure, "make_estimator", return_value=predictor
                    ),
                    mock.patch.object(
                        measure, "make_null_predictor", return_value=predictor
                    ),
                    self.assertRaises(batch.InstrumentError),
                ):
                    measure.measure(after, self.items(), output)
        parent = runs.parse_run_config(run_record({"config": asdict(before)}))
        problem = answering_run.repeat_mismatch(parent, {"config": asdict(after)})
        self.assertIsNotNone(problem)
        self.assertIn("predictor_sha", str(problem))

    def test_a_code_change_refuses_to_resume_the_rows_of_the_old_code(self):
        """The row identity carries the measuring code, not only the
        estimator line: a repair measured again does not keep the faulty
        rows. The twin: the same code resumes."""
        area, measure = self.measure_module("apply")
        predictor = mock.Mock()
        predictor.predict.side_effect = lambda xs: [0 for _ in xs]
        output = area / "output" / "kept.jsonl"
        script = area / "scripts" / "01_measure.py"
        with (
            mock.patch.object(measure, "make_estimator", return_value=predictor),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            measure.measure(measure.CONFIG, self.items(), output)
            # the same code and items resume: nothing is pending, nothing refused
            measure.measure(measure.CONFIG, self.items(), output)
            script.write_text(script.read_text(encoding="utf-8") + "# repaired\n")
            with self.assertRaises(batch.InstrumentError) as cm:
                measure.measure(measure.CONFIG, self.items(), output)
        said = str(cm.exception)
        self.assertIn("code_sha", said)
        self.assertIn("`kept_v2.jsonl`", said)

    def test_a_helper_change_refuses_to_resume_the_rows_of_the_old_code(self):
        """The row identity covers a local module the script imports: with
        the script unchanged, a repaired helper under `lib/` refuses the
        resume. The twin: the same helper resumes."""
        with contextlib.redirect_stdout(io.StringIO()):
            area, _ = scaffold.stamp_area(
                self.root, "helper", repeat_cost="low", kind="apply"
            )
        helper = self.root / "lib" / "skeleton_resume_helper.py"
        helper.parent.mkdir(exist_ok=True)
        helper.write_text("OFFSET = 0\n", encoding="utf-8")
        script = area / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text(encoding="utf-8") + "import skeleton_resume_helper\n",
            encoding="utf-8",
        )
        name = f"helper_resume_{id(self)}"
        spec = importlib.util.spec_from_file_location(name, script)
        assert spec is not None and spec.loader is not None
        measure = importlib.util.module_from_spec(spec)
        sys.modules[name] = measure
        self.addCleanup(sys.modules.pop, name, None)
        self.addCleanup(sys.modules.pop, "skeleton_resume_helper", None)
        spec.loader.exec_module(measure)
        predictor = mock.Mock()
        predictor.predict.side_effect = lambda xs: [0 for _ in xs]
        output = area / "output" / "kept.jsonl"
        as_run = script.read_bytes()
        with (
            mock.patch.object(measure, "make_estimator", return_value=predictor),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            measure.measure(measure.CONFIG, self.items(), output)
            measure.measure(measure.CONFIG, self.items(), output)  # resumes
            helper.write_text("OFFSET = 1  # repaired\n", encoding="utf-8")
            with self.assertRaises(batch.InstrumentError) as cm:
                measure.measure(measure.CONFIG, self.items(), output)
        self.assertIn("code_sha", str(cm.exception))
        self.assertEqual(script.read_bytes(), as_run)  # the helper alone changed

    def test_changed_artifact_after_config_snapshot_refuses_before_predictions(self):
        area, measure = self.measure_module("apply")
        model = area / "primary.model"
        model.write_bytes(b"old")
        measure.PREDICTOR_FILES["primary"] = model
        cfg = replace(measure.CONFIG, predictor_sha=measure.predictor_digests())
        model.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "predictor.*changed"):
            measure.measure(cfg, self.items(), area / "output" / "kept.jsonl")

    def test_main_records_loaded_primary_and_null_dependencies(self):
        area, measure = self.measure_module("apply")
        primary, null = area / "primary.model", area / "null.model"
        primary.write_bytes(b"primary model")
        null.write_bytes(b"null model")
        measure.PREDICTOR_FILES.update(primary=primary, null=null)
        with (
            mock.patch.object(sys, "argv", ["01_measure.py"]),
            mock.patch.object(measure, "read_jsonl", return_value=self.items()),
            mock.patch.object(
                measure.runlog, "run", side_effect=RuntimeError("captured")
            ) as start,
            self.assertRaisesRegex(RuntimeError, "captured"),
        ):
            measure.main()
        self.assertEqual(start.call_args.kwargs["data"], measure.data_files())
        self.assertEqual(
            start.call_args.kwargs["config"]["predictor_sha"],
            measure.predictor_digests(),
        )

    def test_a_declared_dependency_cannot_be_missing(self):
        area, measure = self.measure_module("apply")
        measure.PREDICTOR_FILES["primary"] = area / "missing.model"
        with self.assertRaisesRegex(FileNotFoundError, "missing.model"):
            measure.predictor_digests()

    def test_fit_holds_the_bar_to_the_mean_of_its_refits(self):
        """One permuted-label refit does not decide a fit's verdict. The bar
        and [quality-check-2] read the mean of
        NULL_REFITS refits, each draw kept and named; the twin: a null of one
        unnumbered draw keeps its score as the bar."""
        _, measure = self.measure_module("fit")
        golds = ["pos"] * 6 + ["neg"] * 6
        flip = {"pos": "neg", "neg": "pos"}
        reg = [
            measure.lane_row("registered", {"id": str(i)}, g, g)
            for i, g in enumerate(golds)
        ]

        def draw(d, correct: int) -> list[dict]:
            return [
                measure.lane_row(
                    "null", {"id": str(i)}, g if i < correct else flip[g], g, draw=d
                )
                for i, g in enumerate(golds)
            ]

        nulls = [draw(d, c) for d, c in enumerate((4, 5, 6, 7, 8))]
        m = measure.evaluate_rows(reg + [r for rows in nulls for r in rows])
        self.assertEqual(
            m["quality_check_2_draw_scores"], [c / 12 for c in (4, 5, 6, 7, 8)]
        )
        self.assertEqual(m["quality_check_2_score"], 0.5)  # the mean of 4..8 of 12
        self.assertEqual(m["criterion_1_threshold"], 0.5 + measure.CONFIG.margin)
        single = [
            measure.lane_row("null", {"id": str(i)}, g if i < 7 else flip[g], g)
            for i, g in enumerate(golds)
        ]
        one = measure.evaluate_rows(reg + single)
        self.assertNotIn("quality_check_2_draw_scores", one)
        self.assertEqual(one["criterion_1_threshold"], 7 / 12 + measure.CONFIG.margin)

    def test_the_fit_refits_draw_different_permutations(self):
        _, measure = self.measure_module("fit")
        seen: list[list] = []
        instrument = mock.Mock()
        instrument.fit.side_effect = lambda xs, ys: seen.append(list(ys))
        instrument.predict.side_effect = lambda xs: [x[0] for x in xs]
        with mock.patch.object(measure, "make_estimator", return_value=instrument):
            rows = measure.fit_rows(measure.CONFIG, self.items(), probe=False)
        per_fold = 1 + measure.NULL_REFITS
        first_fold = seen[:per_fold]
        permuted = first_fold[1:]
        self.assertEqual(len({tuple(ys) for ys in permuted}), measure.NULL_REFITS)
        nulls = [r for r in rows if r["lane"] == "null"]
        self.assertEqual({r["draw"] for r in nulls}, set(range(measure.NULL_REFITS)))
        self.assertEqual(len({r["id"] for r in rows}), len(rows))  # ids stay unique

    def test_fit_still_trains_registered_and_permuted_label_lanes(self):
        area, measure = self.measure_module("fit")
        instrument = mock.Mock()
        instrument.predict.side_effect = lambda xs: [x[0] for x in xs]
        with (
            mock.patch.object(measure, "make_estimator", return_value=instrument),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            measure.measure(
                measure.CONFIG, self.items(), area / "output" / "kept.jsonl"
            )
        # per fold the registered fit and NULL_REFITS permuted-label refits,
        # then one fit on every labelled item for the test lane
        self.assertEqual(
            instrument.fit.call_count,
            (1 + measure.NULL_REFITS) * measure.CONFIG.n_folds + 1,
        )

    # the fit plan follows the protocol's repeat cost and the Timebox is a
    # budget the run holds (docs/notes/2026-10-31-fit-budget.md)

    def test_the_plan_at_low_is_three_folds_and_two_refits_recorded_in_the_config(self):
        _, measure = self.measure_module("fit")
        self.assertEqual(measure.FIT_PLAN["low"], (3, 2))
        self.assertEqual(measure.FIT_PLAN["high"], (5, 5))
        self.assertEqual((measure.CONFIG.n_folds, measure.CONFIG.null_refits), (3, 2))
        self.assertIn("null_refits", asdict(measure.CONFIG))
        instrument = mock.Mock()
        instrument.predict.side_effect = lambda xs: [x[0] for x in xs]
        with mock.patch.object(measure, "make_estimator", return_value=instrument):
            measure.fit_rows(measure.CONFIG, self.items(), probe=False)
        self.assertEqual(
            instrument.fit.call_count, 3 * (1 + 2) + 1
        )  # nine fits and the test fit

    def test_fewer_than_two_refits_are_refused(self):
        _, measure = self.measure_module("fit")
        with self.assertRaises(ValueError) as cm:
            measure.fit_rows(
                replace(measure.CONFIG, null_refits=1), self.items(), probe=False
            )
        self.assertIn("null_refits = 1", str(cm.exception))

    def _timed_fit(self, measure, seconds_per_fold: float, budget_s: int | None):
        instrument = mock.Mock()
        instrument.predict.side_effect = lambda xs: [x[0] for x in xs]
        ticks = iter([0.0] + [seconds_per_fold * k for k in range(1, 10)])
        with mock.patch.object(measure, "make_estimator", return_value=instrument):
            return measure.fit_rows(
                measure.CONFIG,
                self.items(),
                probe=False,
                budget_s=budget_s,
                clock=lambda: next(ticks),
            )

    def test_a_first_fold_that_projects_over_the_timebox_stops_the_measurement_with_the_numbers(
        self,
    ):
        _, measure = self.measure_module("fit")
        # 3 folds of 240 s and a test fit project to 800 s against 600 s
        with self.assertRaises(SystemExit) as cm:
            self._timed_fit(measure, 240.0, budget_s=600)
        msg = str(cm.exception)
        self.assertIn("240 s", msg)
        self.assertIn("13.3 min", msg)
        self.assertIn("10.0 min", msg)
        self.assertIn("Next:", msg)

    def test_a_projection_within_the_timebox_and_no_timebox_both_run_through(self):
        _, measure = self.measure_module("fit")
        rows = self._timed_fit(measure, 100.0, budget_s=600)  # 333 s projected
        self.assertEqual(len([r for r in rows if r["lane"] == "test"]), 1)
        rows = self._timed_fit(
            measure, 240.0, budget_s=None
        )  # no budget, no projection
        self.assertEqual(len({r["id"] for r in rows}), len(rows))


if __name__ == "__main__":
    unittest.main()
