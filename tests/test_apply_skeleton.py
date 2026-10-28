"""The local apply skeleton predicts with fixed instruments; only fit trains."""

from __future__ import annotations

import contextlib
from dataclasses import replace
import math
from dataclasses import asdict
import importlib.util
import io
import pickle
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
        # CONFIG hashed PREDICTOR_FILES at import, so the area's test, which
        # imports the script, read the model files (workflow review
        # 2026-10-27, TODO 8 (4)); main() binds them
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
        metrics = measure.evaluate_rows(rows)
        self.assertEqual(
            (metrics["c1_score"], metrics["a2_score"], metrics["n_test"]), (1.0, 0.5, 1)
        )
        self.assertTrue(metrics["c1_pass"])
        self.assertTrue(all(r["fold"] is None for r in rows))

    def test_apply_null_scores_the_same_predictions_against_permuted_labels(self):
        # decided 2026-10-27: no second instrument by default — the primary's
        # predictions against the gold permuted with the seed, as fit's lane
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
        self.assertEqual(metrics["c1_score"], 1.0)
        self.assertLess(metrics["a2_score"], 1.0)

    def test_calibrate_null_measures_the_permutation_spread_before_registration(self):
        # the stamped null_band 0.1 was kept although the skeleton asked to
        # derive it, and --probe had no way at low (SAB-like draw 3,
        # 2026-10-28): the band comes from permutations of the gold with the
        # predictions fixed, by a rule fixed before calibration
        area, measure = self.measure_module("apply")
        primary = mock.Mock()
        primary.predict.side_effect = lambda xs: [x[0] for x in xs]
        with mock.patch.object(measure, "make_estimator", return_value=primary):
            cal = measure.calibrate_null(measure.CONFIG, self.items())
            again = measure.calibrate_null(measure.CONFIG, self.items())
        primary.fit.assert_not_called()
        self.assertEqual(primary.predict.call_count, 2)  # once per calibration
        # the stamp registers the rule beside the band: 0.99 over 200
        self.assertEqual(len(cal["null_scores"]), 200)
        self.assertEqual(cal, again)  # seeded: the same band each time
        # the band is the spread around the exact permutation expectation
        off = sorted(abs(s - cal["target"]) for s in cal["null_scores"])
        self.assertEqual(
            cal["band"], off[197]
        )  # the 0.99 quantile of 200, its exact rank
        self.assertEqual(cal["registered"], math.ceil(cal["band"] * 100) / 100)
        self.assertLess(cal["band"], 1 - cal["target"])  # no permutation is the truth

    # -- [A2]'s band and its registered rule
    def primary(self):
        primary = mock.Mock()
        primary.predict.side_effect = lambda xs: [x[0] for x in xs]
        return primary

    def test_another_count_than_the_registered_rule_is_refused(self):
        """The fifth SAB-like draw calibrated over 50 permutations while the
        rule said 200: with the rule registered, 50 answers another rule. The
        twin: without a registered rule the count is free."""
        _, measure = self.measure_module("apply")
        with mock.patch.object(measure, "make_estimator", return_value=self.primary()):
            with self.assertRaisesRegex(ValueError, "null_permutations = 200"):
                measure.calibrate_null(measure.CONFIG, self.items(), 50)
            free = replace(
                measure.CONFIG, null_band_quantile=None, null_permutations=None
            )
            self.assertEqual(
                len(measure.calibrate_null(free, self.items(), 50)["null_scores"]), 50
            )

    def test_the_first_measurement_refuses_a_band_its_rule_does_not_give(self):
        """The fifth draw registered 0.05 while the rule gave 0.13; the check
        runs before the run opens (a started measurement binds the
        registration) and never changes the band. The twin: the band the
        rule gives passes, and its predictions are reused."""
        _, measure = self.measure_module("apply")
        primary = self.primary()
        with (
            mock.patch.object(measure, "make_estimator", return_value=primary),
            mock.patch.object(measure, "first_measurements", return_value=[]),
        ):
            rule = measure.band_rule(measure.CONFIG)
            assert rule is not None
            golds = [it["gold"] for it in measure.labelled(self.items())]
            preds = [it["features"][0] for it in measure.labelled(self.items())]
            right = measure.band_by_rule(measure.CONFIG, preds, golds, *rule)[
                "registered"
            ]
            wrong = replace(measure.CONFIG, null_band=right + 0.05)
            with self.assertRaises(SystemExit) as cm:
                measure.band_check(wrong, self.items())
            self.assertIn(f"its registered rule gives {right}", str(cm.exception))
            self.assertIn("--calibrate-null --write", str(cm.exception))
            held = replace(measure.CONFIG, null_band=right)
            self.assertEqual(measure.band_check(held, self.items()), preds)

    def test_the_measurement_reuses_the_checks_predictions(self):
        area, measure = self.measure_module("apply")
        primary = self.primary()
        preds = [it["features"][0] for it in measure.labelled(self.items())]
        with (
            mock.patch.object(measure, "make_estimator", return_value=primary),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            measure.measure(
                measure.CONFIG,
                self.items(),
                area / "output" / "kept.jsonl",
                registered=preds,
            )
        # one call: the unlabelled item's test lane; the labelled ones came reused
        self.assertEqual(primary.predict.call_count, 1)

    def test_after_the_first_measurement_the_band_is_not_held_to_the_rule(self):
        """A repair changes the predictions and so the rule's band, while the
        registered band stands: no check after the first measurement."""
        _, measure = self.measure_module("apply")
        with (
            mock.patch.object(measure, "make_estimator", return_value=self.primary()),
            mock.patch.object(measure, "first_measurements", return_value=["a run"]),
        ):
            self.assertIsNone(measure.band_check(measure.CONFIG, self.items()))

    def test_no_rule_no_check_and_fit_no_check(self):
        _, measure = self.measure_module("apply")
        free = replace(measure.CONFIG, null_band_quantile=None, null_permutations=None)
        self.assertIsNone(measure.band_check(free, self.items()))
        _, fit = self.measure_module("fit")
        self.assertIsNone(fit.band_check(fit.CONFIG, self.items()))

    def test_write_registers_the_band_before_the_first_measurement_only(self):
        area, measure = self.measure_module("apply")
        protocol = measure.PROTOCOL
        argv = ["01_measure.py", "--calibrate-null", "--write"]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(measure, "read_jsonl", return_value=self.items()),
            mock.patch.object(measure, "make_estimator", return_value=self.primary()),
            mock.patch.object(measure, "first_measurements", return_value=[]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            measure.main()
        from labkit.formats import promises

        written = promises.all_constants(promises.load(protocol))["null_band"]
        cal = measure.band_by_rule(
            measure.CONFIG,
            [it["features"][0] for it in measure.labelled(self.items())],
            [it["gold"] for it in measure.labelled(self.items())],
            0.99,
            200,
        )
        self.assertEqual(written, cal["registered"])
        before = protocol.read_text(encoding="utf-8")
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(measure, "read_jsonl", return_value=self.items()),
            mock.patch.object(measure, "make_estimator", return_value=self.primary()),
            mock.patch.object(measure, "first_measurements", return_value=["a run"]),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            measure.main()
        self.assertEqual(protocol.read_text(encoding="utf-8"), before)
        with (
            mock.patch.object(sys, "argv", ["01_measure.py", "--write"]),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            measure.main()

    def test_main_refuses_before_the_run_opens(self):
        _, measure = self.measure_module("apply")
        with (
            mock.patch.object(sys, "argv", ["01_measure.py"]),
            mock.patch.object(measure, "read_jsonl", return_value=self.items()),
            mock.patch.object(measure, "make_estimator", return_value=self.primary()),
            mock.patch.object(measure, "first_measurements", return_value=[]),
            mock.patch.object(measure.runlog, "run") as start,
            self.assertRaises(SystemExit),
        ):
            measure.main()
        start.assert_not_called()

    def test_the_permutation_expectation_is_exact(self):
        """The bar at apply: the mean score over EVERY permutation of the gold,
        computed in closed form — checked against all 720 orderings of six
        items, for accuracy (with a missing prediction), auc and r2."""
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
        }
        for score, (preds, golds) in cases.items():
            with self.subTest(score=score):
                draws = [
                    measure.SCORES[score](list(zip(preds, perm)))
                    for perm in itertools.permutations(golds)
                ]
                exact = measure.permutation_expectation(score, list(zip(preds, golds)))
                if score == "r2":
                    self.assertAlmostEqual(exact, sum(draws) / len(draws), places=12)
                else:
                    self.assertEqual(exact, sum(draws, Fraction(0)) / len(draws))

    def test_apply_holds_the_bar_and_the_null_to_the_expectation(self):
        """A permuted null's draw is the anchor, not the bar: the same
        registered lane passes or fails by the expectation alone, whatever
        the draw — one draw put the bar anywhere between 0.54 and 0.78
        (null-lane decision, 2026-10-28). The twin: a fitted null (no
        donors) keeps its score as the bar and chance as [A2]'s target."""
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
            self.assertEqual(m["a2_target"], 0.5)  # q = p = 1/2: 1/4 + 1/4
            self.assertEqual(
                m["c1_threshold"], 0.5 + cfg.margin
            )  # the draw moves nothing
        fitted = measure.evaluate_rows(reg + null(7, False), cfg)
        self.assertEqual(fitted["c1_threshold"], 7 / 12 + cfg.margin)

    def test_the_scored_lanes_are_the_ones_finalize_reads(self):
        # the skeleton's lane names and finalize's null-lane station must
        # agree, or the station holds nothing (audit 2026-10-28, H7)
        from labkit.checks import run_record_check

        _, measure = self.measure_module("apply")
        self.assertEqual(measure.SCORED_LANES, run_record_check.NULL_LANES)

    def test_each_skeleton_keeps_c1_under_its_contract_key(self):
        # the probes named the key by hand (audit 2026-10-28, H6)
        from labkit.formats import standard_contract
        from labkit.tools.scaffold import template

        for sk in (standard_contract.ESTIMATOR, standard_contract.MODEL):
            with self.subTest(sk=sk.instrument):
                measure = next(t for t, dest in sk.scripts if dest == "01_measure.py")
                key = standard_contract.criterion_key(sk)
                self.assertIn(f'C1_VALUE_KEY = "{key}"', template(measure))
        with self.assertRaises(ValueError):
            standard_contract.criterion_key(standard_contract.COMPUTE)

    def test_calibrate_null_has_no_free_path_at_fit_or_for_a_fixed_null(self):
        _, fit = self.measure_module("fit")
        with self.assertRaisesRegex(ValueError, "apply only"):
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
        """The row identity carries the measuring code: a repair measured
        again kept the faulty rows while it held only the estimator line
        (repair case, 2026-10-28). The twin: the same code resumes."""
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
            mock.patch.object(measure, "band_check", return_value=None),
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
        """One permuted-label refit decided a fit's verdict (fourth SAB-like
        draw: c1_score = c1_threshold). The bar and [A2] read the mean of
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
        self.assertEqual(m["a2_draw_scores"], [c / 12 for c in (4, 5, 6, 7, 8)])
        self.assertEqual(m["a2_score"], 0.5)  # the mean of 4..8 of 12
        self.assertEqual(m["c1_threshold"], 0.5 + measure.CONFIG.margin)
        single = [
            measure.lane_row("null", {"id": str(i)}, g if i < 7 else flip[g], g)
            for i, g in enumerate(golds)
        ]
        one = measure.evaluate_rows(reg + single)
        self.assertNotIn("a2_draw_scores", one)
        self.assertEqual(one["c1_threshold"], 7 / 12 + measure.CONFIG.margin)

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


if __name__ == "__main__":
    unittest.main()
