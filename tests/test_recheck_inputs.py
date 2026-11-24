"""recheck over a run's recorded inputs (`recheck.holds_from_inputs`): run
C computes from run W's rows and a plain input. Two steps kept apart —
the inputs are the bytes C read (an input with an origin still W's
registered output), and C's evaluation over them gives the numbers C's
metrics.json holds. A failed input leaves the evaluation uncalled; intact
inputs with a number that does not follow from them fail at the
recomputation. W is never run again."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

from labkit.checks import recheck
from labkit.run import runlog
from protocol_fixture import recheck_without_git


def evaluate(inputs: Mapping[str, Path]) -> dict:
    """C's evaluation: the mean `n` of the source's rows, scaled by the
    plain input's factor, and the verdict on it."""
    rows = [json.loads(line) for line in inputs["rows"].read_text().splitlines()]
    factor = float(inputs["factor"].read_text())
    mean = factor * sum(r["n"] for r in rows) / len(rows)
    return {"criterion_1_mean": mean, "criterion_1_pass": mean > 3}


class FromInputs(unittest.TestCase):
    def setUp(self) -> None:
        self.require_run_code = recheck.require_run_code
        recheck_without_git(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name) / "area"
        self.area.mkdir()
        self.aside = Path(tmp.name) / "aside"
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))
        self.rows = self.area / "rows.jsonl"
        with runlog.run("w", {}, self.area, data=runlog.NO_INPUTS) as w:
            w.output(self.rows)
            self.rows.write_text('{"n": 4}\n{"n": 3}\n', encoding="utf-8")
            w.metrics(n=2)
        self.writer = w.dir
        self.factor = self.area / "factor.txt"
        self.factor.write_text("2\n", encoding="utf-8")
        inputs = {"rows": self.rows, "factor": self.factor}
        # C records no script whatever started the tests: sys.argv[0] is a file
        # under `python -m pytest` and none under xdist's workers
        with mock.patch.object(sys, "argv", [""]):
            with runlog.run("c", {}, self.area, data=inputs) as c:
                c.metrics(**evaluate(inputs))
        self.c = c.dir
        self.calls = 0

    def counted(self, inputs: Mapping[str, Path]) -> dict:
        """`evaluate`, counting its calls."""
        self.calls += 1
        return evaluate(inputs)

    def verified(self) -> dict:
        return recheck.verified_from_inputs(self.c, self.area, self.counted)[0]

    def test_the_twin_intact_inputs_give_the_recorded_numbers(self) -> None:
        runs_before = sorted(p.name for p in (self.area / "runs").iterdir())
        metrics = self.verified()
        self.assertEqual(metrics["criterion_1_mean"], 7.0)
        self.assertEqual(self.calls, 1)
        # the source run is read, never run again
        self.assertEqual(
            sorted(p.name for p in (self.area / "runs").iterdir()), runs_before
        )

    def test_inputs_are_pinned_by_key_with_the_origin_held(self) -> None:
        pinned = recheck.inputs_pinned(self.c, self.area)
        self.assertEqual(set(pinned), {"rows", "factor"})
        self.assertEqual(pinned["rows"].resolve(), self.rows.resolve())

    def test_a_gone_origin_refuses_before_any_recomputation(self) -> None:
        shutil.move(self.writer, self.aside)
        with self.assertRaises(SystemExit) as cm:
            self.verified()
        self.assertIn(
            f"its origin run {self.writer.name} is gone", str(cm.exception.code)
        )
        self.assertIn("not recomputed", str(cm.exception.code))
        self.assertEqual(self.calls, 0)

    def test_a_changed_source_file_refuses_before_any_recomputation(self) -> None:
        self.rows.write_text('{"n": 40}\n{"n": 3}\n', encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self.verified()
        self.assertIn("is not the output of its origin run", str(cm.exception.code))
        self.assertEqual(self.calls, 0)

    def test_a_changed_plain_input_refuses_before_any_recomputation(self) -> None:
        self.factor.write_text("3\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self.verified()
        self.assertIn(
            "data['factor'] = factor.txt is not the input it read",
            str(cm.exception.code),
        )
        self.assertEqual(self.calls, 0)

    def test_a_number_that_does_not_follow_from_intact_inputs_fails_the_recomputation(
        self,
    ) -> None:
        metrics_file = self.c / "metrics.json"
        metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
        metrics["criterion_1_mean"] = 7.5
        metrics_file.write_text(json.dumps(metrics), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self.verified()
        self.assertIn("recomputation differs from metrics.json", str(cm.exception.code))
        self.assertEqual(self.calls, 1)  # the inputs held; the evaluation ran

    def test_intact_inputs_with_code_not_recorded_are_not_verifiable(self) -> None:
        """C was written by this process and records no script: its inputs
        hold, and its evaluation is still not called — agreeing with the
        code here would be no recalculation of C."""
        with (
            mock.patch.object(recheck, "require_run_code", self.require_run_code),
            self.assertRaises(recheck.NotVerifiable) as cm,
        ):
            self.verified()
        self.assertIn(f"run {self.c.name} is not verifiable", str(cm.exception.code))
        self.assertEqual(self.calls, 0)

    def test_another_evaluation_over_the_same_inputs_fails(self) -> None:
        def unscaled(inputs: Mapping[str, Path]) -> dict:
            got = evaluate(inputs)
            return {**got, "criterion_1_mean": got["criterion_1_mean"] / 2}

        with self.assertRaises(SystemExit) as cm:
            recheck.verified_from_inputs(self.c, self.area, unscaled)
        self.assertIn("criterion_1_mean", str(cm.exception.code))

    def test_a_run_without_inputs_is_refused_naming_holds(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            recheck.inputs_pinned(self.writer, self.area)
        self.assertIn("recorded no input file", str(cm.exception.code))


if __name__ == "__main__":
    unittest.main()
