"""The local apply skeleton predicts with fixed instruments; only fit trains."""

from __future__ import annotations

import contextlib
from dataclasses import asdict, replace
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
        self.assertEqual(instrument.fit.call_count, 2 * measure.CONFIG.n_folds + 1)


if __name__ == "__main__":
    unittest.main()
