"""The compute skeleton reads its inputs from the frozen INPUTS.

The usability fixture gives every case its own `inputs` path; the skeleton
froze only the constant INPUTS, so every cold agent read the record's path
and the number followed a value the run did not freeze — the analysis
audit warned in each of three sandbox probes (2026-10-21). INPUTS decides
what is read; a record that names another path is refused.
"""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

from labkit.formats import protocol_block
from labkit.tools import scaffold
from labkit.tools.protocol_edit import fill_many


def stamp_compute_area(case: unittest.TestCase) -> tuple[Path, ModuleType]:
    """A fresh lab with the compute area `01-docs` at low repeat cost:
    (lab root, its `01_measure.py` imported). Cleans up with CASE."""
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    root = Path(tmp.name) / "lab"
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        scaffold.stamp_lab(root, root.name)
        case.assertEqual(
            scaffold.main(
                [
                    "exp",
                    "docs",
                    "--repo",
                    str(root),
                    "--repeat-cost",
                    "low",
                    "--kind",
                    "compute",
                ]
            ),
            0,
        )
    path = root / "experiments" / "01-docs" / "scripts" / "01_measure.py"
    spec = importlib.util.spec_from_file_location("stamped_count_measure", path)
    assert spec is not None and spec.loader is not None
    measure = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = measure
    case.addCleanup(sys.modules.pop, spec.name, None)
    spec.loader.exec_module(measure)
    return root, measure


class InputDir(unittest.TestCase):
    def setUp(self) -> None:
        _, self.measure = stamp_compute_area(self)
        setattr(self.measure, "INPUTS", self.measure.REPO / "data" / "raw" / "inputs")

    def test_a_record_naming_the_frozen_inputs_is_read_there(self):
        m = self.measure
        self.assertEqual(
            m.input_dir({"inputs": "data/raw/inputs"}, "c1"), m.INPUTS / "c1"
        )

    def test_a_record_without_a_path_reads_under_inputs(self):
        m = self.measure
        self.assertEqual(m.input_dir({"case_id": "c1"}, "c1"), m.INPUTS / "c1")

    def test_a_record_naming_another_path_is_refused(self):
        with self.assertRaisesRegex(ValueError, "c1.*data/elsewhere.*data/raw/inputs"):
            self.measure.input_dir({"inputs": "data/elsewhere"}, "c1")

    def test_without_inputs_set_the_reader_refuses(self):
        setattr(self.measure, "INPUTS", None)
        with self.assertRaisesRegex(ValueError, "INPUTS"):
            self.measure.input_dir({"inputs": "data/raw/inputs"}, "c1")


class FillList(unittest.TestCase):
    """The skeleton's docstring names every blank it stamps: it said "the
    three TODOs" while INPUTS was a fourth place to fill, and an agent left
    its TODO behind (sandbox probe, 2026-10-21)."""

    def test_every_constant_and_function_with_a_todo_is_named(self):
        import re

        text = (
            Path(scaffold.__file__).resolve().parent.parent
            / "templates"
            / "measure-quick-script.py.template"
        ).read_text(encoding="utf-8")
        doc = text.split('"""', 2)[1]
        blanks = re.findall(r"^([A-Z_]+) = .*TODO", text, re.M)
        blanks += re.findall(r'^def (\w+)\(.*\n    """TODO', text, re.M)
        self.assertEqual(
            sorted(blanks),
            [
                "INPUTS",
                "SOURCE",
                "deliverable_rows",
                "evaluate_rows",
                "expected_ids",
                "rows",
            ],
        )
        for name in blanks:
            self.assertIn(name, doc, name)
        self.assertNotRegex(doc, r"\b(three|four|five) TODOs\b")
        # the kept number's key is the head's, never a constant to fill here
        self.assertNotIn("METRIC_KEY", text)
        self.assertIn("`[kept]`", doc)


class KeptNumber(unittest.TestCase):
    """The kept number is the one the head's `[kept] key` names, and a
    number. Reference pilot trial 2, task 34 (2026-11-01): the script's
    METRIC_KEY named a flag, `hrv_computed = True` became the adopted result
    while the protocol's Unit named HRV_MeanNN. The skeleton reads the key
    from the head (`metric_key`); the run and `--check` (`metrics_of`) and
    the area's test refuse a bool, a text or a missing key, naming the key;
    the twin, a numeric kept number, passes all three."""

    ROWS = [{"id": "s1", "mean_nn": 812.5, "computed": True}]

    def setUp(self) -> None:
        self.root, self.measure = stamp_compute_area(self)
        self.protocol = self.root / "experiments" / "01-docs" / "PROTOCOL-docs.md"
        self.stamped = self.protocol.read_text(encoding="utf-8")

    def keep(self, key: str) -> None:
        """The head's `[kept]` names KEY, unit ms — as `protocol-fill
        PROTOCOL kept.key=KEY kept.unit=ms` writes it."""
        self.protocol.write_text(
            fill_many(self.stamped, [("kept.key", key), ("kept.unit", "ms")]),
            encoding="utf-8",
        )

    def evaluating(self, key: str) -> None:
        def evaluate_rows(items: list[dict], ids: list[str]) -> dict:
            return {
                "hrv_mean_nn": items[0]["mean_nn"],
                "hrv_computed": items[0]["computed"],
                "unit": "ms",
            }

        self.keep(key)
        setattr(self.measure, "evaluate_rows", evaluate_rows)

    def test_the_key_is_read_from_the_head(self) -> None:
        self.keep("hrv_mean_nn")
        self.assertEqual(self.measure.metric_key(), "hrv_mean_nn")

    def test_a_placeholder_or_a_missing_table_is_refused_naming_kept(self) -> None:
        self.assertEqual(
            protocol_block.kept(self.stamped), protocol_block.Kept(None, None)
        )
        with self.assertRaisesRegex(
            ValueError, r"\[kept\] key is still the placeholder"
        ):
            self.measure.metric_key()
        start = self.stamped.index("[kept]")
        end = self.stamped.index('unit = "<unit>"\n') + len('unit = "<unit>"\n')
        self.protocol.write_text(
            self.stamped[:start] + self.stamped[end:], encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, r"no \[kept\] table"):
            self.measure.metric_key()

    def test_a_flag_text_or_missing_key_is_refused_naming_the_key(self) -> None:
        for key, says in (
            ("hrv_computed", "'hrv_computed' holds True, which is no number"),
            ("unit", "'unit' holds 'ms', which is no number"),
            ("hrv_rmssd", "'hrv_rmssd': evaluate_rows\\(\\) returns no such key"),
        ):
            with self.subTest(key=key):
                self.evaluating(key)
                with self.assertRaisesRegex(ValueError, says):
                    self.measure.metrics_of(self.ROWS, ["s1"])

    def test_a_numeric_kept_number_passes(self) -> None:
        self.evaluating("hrv_mean_nn")
        metrics = self.measure.metrics_of(self.ROWS, ["s1"])
        self.assertEqual(metrics["hrv_mean_nn"], 812.5)
        self.assertEqual(self.measure.kept_number({"hrv_mean_nn": 812}), 812)

    def test_the_area_test_refuses_a_flag_and_passes_a_number(self) -> None:
        script = self.root / "experiments" / "01-docs" / "scripts" / "01_measure.py"
        test = self.root / "tests" / "test_01_docs.py"
        stamped_script = script.read_text(encoding="utf-8")
        stamped_test = test.read_text(encoding="utf-8")
        evaluate = '    raise NotImplementedError("evaluate_rows(): compute the number(s) from items")\n'
        self.assertEqual(stamped_script.count(evaluate), 1)
        self.assertNotIn("METRIC_KEY", stamped_script)
        filled = stamped_script.replace(
            evaluate,
            '    return {"hrv_mean_nn": items[0]["mean_nn"], "hrv_computed": True}\n',
        )
        blanks = (
            "KNOWN_IDS: list[str] = []\n"
            "KNOWN_ROWS: list[dict] = []\n"
            "KNOWN_METRICS: dict = {}\n"
        )
        self.assertEqual(stamped_test.count(blanks), 1)
        for key, known, code in (
            ("hrv_computed", "{'hrv_computed': True}", 1),
            ("hrv_mean_nn", "{'hrv_mean_nn': 812.5}", 0),
        ):
            with self.subTest(key=key):
                script.write_text(filled, encoding="utf-8")
                self.keep(key)
                test.write_text(
                    stamped_test.replace(
                        blanks,
                        'KNOWN_IDS: list[str] = ["s1"]\n'
                        f"KNOWN_ROWS: list[dict] = {self.ROWS!r}\n"
                        f"KNOWN_METRICS: dict = {known}\n",
                    ),
                    encoding="utf-8",
                )
                r = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        "-p",
                        "no:cacheprovider",
                        "-k",
                        "known_rows",
                        str(test),
                    ],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    # both rewrites of the test file have the same size within
                    # the same second: a cached .pyc of the first was run for
                    # the second (the merged suite, 2026-11-01)
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                self.assertEqual(r.returncode, code, r.stdout + r.stderr)
                if code:
                    self.assertIn("'hrv_computed' holds True", r.stdout)


if __name__ == "__main__":
    unittest.main()
