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
import sys
import tempfile
import unittest
from pathlib import Path

from labkit.tools import scaffold


class InputDir(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "lab"
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            scaffold.stamp_lab(root, root.name)
            self.assertEqual(
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
        self.measure = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.measure
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(self.measure)
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


if __name__ == "__main__":
    unittest.main()


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
                "COUNT_FIELD",
                "INPUTS",
                "METRIC_KEY",
                "SOURCE",
                "evaluate_rows",
                "expected_ids",
                "rows",
            ],
        )
        for name in blanks:
            self.assertIn(name, doc, name)
        self.assertNotRegex(doc, r"\b(three|four|five) TODOs\b")
