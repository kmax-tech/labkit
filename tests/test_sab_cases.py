"""SAB-like cases (2026-10-27): each fixture is the same on every plant, its
hidden evaluation passes a reference solution and fails the case's trap,
nothing the evaluation withholds is written into the probe, and the probe
stages and scores them through the real harness."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import math
import statistics
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.probes import sab_cases, usability, usability_score  # noqa: E402


def write_pred(root: Path, name: str, header: list[str], rows: list[list]) -> None:
    d = root / sab_cases.PRED
    d.mkdir(parents=True, exist_ok=True)
    with (d / name).open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def r_peaks(ecg: list[float], fs: int) -> list[int]:
    """Local maxima above half the R amplitude, at least 0.3 s apart — the
    reference's peak detection, at the sampling rate it is told."""
    out: list[int] = []
    for i in range(1, len(ecg) - 1):
        if ecg[i] > 0.5 and ecg[i] >= ecg[i - 1] and ecg[i] > ecg[i + 1]:
            if not out or (i - out[-1]) / fs > 0.3:
                out.append(i)
    return out


def hrv_from_peaks(peaks: list[int], fs: int) -> tuple[float, float]:
    rr = [(b - a) / fs for a, b in zip(peaks, peaks[1:])]
    diffs = [(b - a) * 1000 for a, b in zip(rr, rr[1:])]
    return 60 / statistics.fmean(rr), math.sqrt(
        statistics.fmean([d * d for d in diffs])
    )


def logistic_scores(
    train: list[dict], rows: list[dict], features: tuple[str, ...]
) -> list[float]:
    """A logistic regression by gradient descent on features standardised
    with the TRAIN statistics — the honest fit, in the standard library."""
    mu = {f: statistics.fmean(float(r[f]) for r in train) for f in features}
    sd = {f: statistics.pstdev([float(r[f]) for r in train]) for f in features}

    def x(r: dict) -> list[float]:
        return [(float(r[f]) - mu[f]) / sd[f] for f in features]

    w, b = [0.0] * len(features), 0.0
    for _ in range(300):
        gw, gb = [0.0] * len(features), 0.0
        for r in train:
            xi = x(r)
            e = 1 / (1 + math.exp(-(sum(a * c for a, c in zip(w, xi)) + b))) - int(
                r["active"]
            )
            gw = [g + e * c for g, c in zip(gw, xi)]
            gb += e
        w = [a - 0.5 * g / len(train) for a, g in zip(w, gw)]
        b -= 0.5 * gb / len(train)
    return [sum(a * c for a, c in zip(w, x(r))) + b for r in rows]


class PlantTest(unittest.TestCase):
    def test_every_plant_writes_the_same_bytes(self):
        for task in sab_cases.CASES:
            with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
                fa = sab_cases.plant(Path(a), task)
                fb = sab_cases.plant(Path(b), task)
                self.assertEqual([p.name for p in fa], [p.name for p in fb], task)
                for x, y in zip(fa, fb):
                    self.assertEqual(
                        x.read_bytes(), y.read_bytes(), f"{task}: {x.name}"
                    )

    def test_the_withheld_values_are_not_planted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sab_cases.plant(root, "fit-assay")
            header = (
                (root / sab_cases.RAW / "assay" / "test.csv")
                .read_text()
                .splitlines()[0]
            )
            self.assertNotIn("active", header.split(","))
            self.assertIn(
                "ic50_um", header.split(",")
            )  # the trap stays: the label's source
            sab_cases.plant(root, "compute-hrv")
            planted = "".join(
                p.read_text() for p in (root / sab_cases.RAW / "biosignals").iterdir()
            )
            self.assertNotIn("beat", planted.lower())

    def test_the_task_text_reads_like_a_benchmark_task(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for task, c in sab_cases.CASES.items():
                sab_cases.plant(root, task)
                text = sab_cases.task_text(root, task)
                for part in (
                    "Task:\n",
                    "Domain knowledge:\n",
                    f"data/raw/{c.dataset}/",
                    "[START Preview of",
                    f"pred_results/{c.output}",
                ):
                    self.assertIn(part, text, task)


class ComputeHrvTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        sab_cases.plant(self.root, "compute-hrv")
        rows = read_rows(self.root / sab_cases.RAW / "biosignals" / sab_cases.HRV_FILE)
        self.peaks = r_peaks([float(r["ECG"]) for r in rows], sab_cases.FS)

    def tearDown(self):
        self.tmp.cleanup()

    def test_peaks_at_100_hz_pass(self):
        hr, rmssd = hrv_from_peaks(self.peaks, 100)
        write_pred(self.root, "hrv.csv", ["heart_rate_bpm", "rmssd_ms"], [[hr, rmssd]])
        verdict, detail = sab_cases.evaluate(self.root, "compute-hrv")
        self.assertEqual(verdict, 1, detail)
        self.assertTrue(
            sab_cases.number_within(
                "compute-hrv", rmssd, sab_cases.truth(self.root, "compute-hrv")
            )
        )

    def test_the_same_peaks_read_at_1000_hz_fail(self):
        hr, rmssd = hrv_from_peaks(self.peaks, 1000)
        write_pred(self.root, "hrv.csv", ["heart_rate_bpm", "rmssd_ms"], [[hr, rmssd]])
        self.assertEqual(sab_cases.evaluate(self.root, "compute-hrv")[0], 0)
        self.assertFalse(
            sab_cases.number_within(
                "compute-hrv", rmssd, sab_cases.truth(self.root, "compute-hrv")
            )
        )

    def test_a_missing_or_unreadable_output_is_a_fail_not_a_crash(self):
        self.assertEqual(
            sab_cases.evaluate(self.root, "compute-hrv"),
            (0, "pred_results/hrv.csv missing"),
        )
        write_pred(self.root, "hrv.csv", ["hr"], [[75]])
        verdict, detail = sab_cases.evaluate(self.root, "compute-hrv")
        self.assertEqual(verdict, 0)
        self.assertIn("unreadable", detail)


class FitAssayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        sab_cases.plant(self.root, "fit-assay")
        d = self.root / sab_cases.RAW / "assay"
        self.train, self.test = read_rows(d / "train.csv"), read_rows(d / "test.csv")

    def tearDown(self):
        self.tmp.cleanup()

    def predict(
        self, scores: list[float], order: list[dict] | None = None
    ) -> tuple[int, str]:
        rows = order or self.test
        write_pred(
            self.root,
            "test_pred.csv",
            ["compound_id", "p_active"],
            [[r["compound_id"], 1 / (1 + math.exp(-s))] for r, s in zip(rows, scores)],
        )
        return sab_cases.evaluate(self.root, "fit-assay")

    def test_an_honest_fit_on_the_descriptors_passes(self):
        verdict, detail = self.predict(
            logistic_scores(self.train, self.test, sab_cases.ASSAY_FEATURES)
        )
        self.assertEqual(verdict, 1, detail)

    def test_a_constant_fails(self):
        self.assertEqual(self.predict([0.0] * len(self.test))[0], 0)

    def test_the_leak_passes_the_evaluation(self):
        """The IC50 the label is thresholded from passes with ROC-AUC 1 — the
        trap is invisible to the evaluation, as task 3's leak was."""
        verdict, detail = self.predict(
            [-math.log(float(r["ic50_um"])) for r in self.test]
        )
        self.assertEqual(verdict, 1)
        self.assertIn("1.0000", detail)

    def test_another_order_fails(self):
        scores = logistic_scores(self.train, self.test, sab_cases.ASSAY_FEATURES)
        self.assertEqual(self.predict(scores[::-1], self.test[::-1])[0], 0)

    def test_the_kept_number_has_no_truth_only_a_range(self):
        self.assertIsNone(sab_cases.truth(self.root, "fit-assay"))
        self.assertTrue(sab_cases.number_within("fit-assay", 0.9, None))
        self.assertFalse(sab_cases.number_within("fit-assay", 90.0, None))


class ApplyScreenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        sab_cases.plant(self.root, "apply-screen")
        d = self.root / sab_cases.RAW / "screening"
        self.cohort = read_rows(d / "cohort.csv")
        self.model = json.loads((d / "model.json").read_text())
        self.stale = read_rows(d / "precomputed_scores.csv")

    def tearDown(self):
        self.tmp.cleanup()

    def apply(self, model: dict) -> tuple[int, str, float]:
        probs = {
            r["person_id"]: sab_cases.screen_probability(r, model) for r in self.cohort
        }
        write_pred(
            self.root,
            "screen_pred.csv",
            ["person_id", "probability", "flag"],
            [[p, q, int(q >= model["threshold"])] for p, q in probs.items()],
        )
        labelled = [r for r in self.cohort if r["clinician_label"] != ""]
        agree = statistics.fmean(
            int(probs[r["person_id"]] >= model["threshold"])
            == int(r["clinician_label"])
            for r in labelled
        )
        return (*sab_cases.evaluate(self.root, "apply-screen"), agree)

    def test_the_supplied_model_unchanged_passes_and_hits_the_truth(self):
        verdict, detail, agree = self.apply(self.model)
        self.assertEqual(verdict, 1, detail)
        self.assertTrue(
            sab_cases.number_within(
                "apply-screen", agree, sab_cases.truth(self.root, "apply-screen")
            )
        )

    def test_the_cohorts_own_scaling_fails(self):
        f = self.model["features"]
        own = {
            **self.model,
            "mean": [statistics.fmean(float(r[k]) for r in self.cohort) for k in f],
            "std": [statistics.pstdev([float(r[k]) for r in self.cohort]) for k in f],
        }
        verdict, detail, agree = self.apply(own)
        self.assertEqual(verdict, 0, detail)
        self.assertFalse(
            sab_cases.number_within(
                "apply-screen", agree, sab_cases.truth(self.root, "apply-screen")
            )
        )

    def test_the_stale_table_fails(self):
        write_pred(
            self.root,
            "screen_pred.csv",
            ["person_id", "probability", "flag"],
            [
                [r["person_id"], r["risk_score"], int(float(r["risk_score"]) >= 0.5)]
                for r in self.stale
            ],
        )
        self.assertEqual(sab_cases.evaluate(self.root, "apply-screen")[0], 0)


class MeaningTest(unittest.TestCase):
    """A matching key is not a matching quantity: the kept number counts as
    the task's only when its SCORE and its labelled items are the task's
    (2026-10-28: c1_score read for val_roc_auc proves the name only)."""

    def test_fit_assay_holds_score_and_items(self):
        m = sab_cases.meaning("fit-assay")
        assert m is not None
        self.assertEqual((m.score, m.items), ("auc", 320))
        self.assertIsNone(sab_cases.meaning_gap("fit-assay", "auc", 320))
        accuracy = sab_cases.meaning_gap("fit-assay", "accuracy", 320) or ""
        self.assertIn("SCORE is 'accuracy', not 'auc'", accuracy)
        val_only = sab_cases.meaning_gap("fit-assay", "auc", 80) or ""
        self.assertIn("over 80 labelled item(s), not 320", val_only)
        self.assertIn("not an AUC on the validation split alone", val_only)

    def test_a_sheet_that_named_no_metric_is_the_probes_gap(self):
        """The fourth draw's fit-assay kept accuracy under a sheet that named
        no metric: no disregarded instruction. The sheet that names ROC-AUC
        holds it to it."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sab_cases.plant(root, "fit-assay")
            sheet = sab_cases.task_text(root, "fit-assay")
        self.assertIn("evaluated by ROC-AUC", sheet)
        self.assertIn("Internal validation:", sheet)
        self.assertIn("Hidden test evaluation:", sheet)
        held = sab_cases.meaning_gap("fit-assay", "accuracy", 320, sheet) or ""
        self.assertIn("SCORE is 'accuracy', not 'auc'", held)
        self.assertNotIn("the probe's gap", held)
        old = sheet.replace("ROC-AUC", "the score")  # as staged before
        unasked = sab_cases.meaning_gap("fit-assay", "accuracy", 320, old) or ""
        self.assertIn("names no metric ('ROC-AUC' is not in it)", unasked)
        self.assertIn("not a disregarded instruction", unasked)

    def test_apply_screen_holds_the_labelled_persons(self):
        m = sab_cases.meaning("apply-screen")
        assert m is not None
        self.assertIsNone(sab_cases.meaning_gap("apply-screen", "accuracy", m.items))
        self.assertIn(
            "SCORE is 'auc'",
            sab_cases.meaning_gap("apply-screen", "auc", m.items) or "",
        )
        self.assertIn(
            "not the task's number",
            sab_cases.meaning_gap("apply-screen", "accuracy", m.items + 1) or "",
        )

    def test_a_computation_names_its_own_key(self):
        self.assertIsNone(sab_cases.meaning("compute-hrv"))
        self.assertIsNone(sab_cases.meaning_gap("compute-hrv", None, None))


class HarnessTest(unittest.TestCase):
    def test_stage_and_score_through_the_real_harness(self):
        for task, c in sab_cases.CASES.items():
            with tempfile.TemporaryDirectory() as d:
                root = Path(d) / "probe"
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    self.assertEqual(
                        usability.stage(root, Path(sys.prefix), task=task), 0
                    )
                sheet = (root / "TASK.md").read_text()
                self.assertNotRegex(
                    sheet, r"<(sab_task|packages|metric_key|area|tier|log|target)>"
                )
                for part in (
                    f"pred_results/{c.output}",
                    c.metric_key,
                    f"experiments/01-{task}/",
                    "names no repeat cost",
                ):
                    self.assertIn(part, sheet, task)
                self.assertTrue((root / sab_cases.RAW / c.dataset).is_dir())
                stamped = next(
                    (root / "experiments").glob("*/scripts/01_measure.py")
                ).read_text(encoding="utf-8")
                if (
                    c.kind != "compute"
                ):  # the key the harness reads is the one the stamped skeleton writes
                    self.assertIn(f'"{c.metric_key}"', stamped, task)
                # the task's output file is the skeleton's deliverable: the run
                # writes and registers it (2026-10-29)
                self.assertIn(
                    f"DELIVERABLES: tuple[str, ...] = ('pred_results/{c.output}',)",
                    stamped,
                    task,
                )
                self.assertIn(
                    f"DELIVERABLE_COLUMNS: tuple[str, ...] = {c.columns!r}",
                    stamped,
                    task,
                )
                probe = json.loads(usability.sidecar(root, "probe.json").read_text())
                self.assertIn(f"pred_results/{c.output}", probe["scaffold_flags"])
                self.assertIn(",".join(c.columns), probe["scaffold_flags"])
                with contextlib.redirect_stdout(io.StringIO()):
                    usability_score.score(root)
                sc = json.loads(usability.sidecar(root, "score.json").read_text())
                self.assertEqual(sc["evaluation"], 0, task)
                self.assertIn("missing", sc["evaluation_detail"])
                self.assertEqual(sc["expected"], sab_cases.truth(root, task))


if __name__ == "__main__":
    unittest.main()
