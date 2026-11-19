"""An area's check holds one protocol at a time, with the script its run ran.

`recheck.protocol_named` is the choice of the protocol (the named one, or
the area's only one — never the first of several), `recheck.script_module`
the choice of the evaluation: the script the held run recorded, so a second
protocol of the area with a script of its own is recomputed by that script.
From files in a temporary area; the commands that pass both on:
tests/test_adopt_per_protocol.py, tests/test_origin_scenario.py.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from labkit.checks import recheck
from labkit.formats import runs
from protocol_fixture import head, run_record


class TheProtocolTheCheckHolds(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.area = Path(self._tmp.name).resolve() / "01-x"
        self.area.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _protocol(self, name: str) -> Path:
        path = self.area / name
        path.write_text(head(repeat_cost="low"), encoding="utf-8")
        return path

    def test_the_only_protocol_needs_no_name(self):
        only = self._protocol("PROTOCOL-a.md")
        self.assertEqual(recheck.protocol_named(self.area, None), only)

    def test_of_several_the_named_one_is_held(self):
        self._protocol("PROTOCOL-a.md")
        second = self._protocol("PROTOCOL-b.md")
        self.assertEqual(recheck.protocol_named(self.area, "PROTOCOL-b.md"), second)

    def test_of_several_none_named_is_refused_never_the_first(self):
        self._protocol("PROTOCOL-a.md")
        self._protocol("PROTOCOL-b.md")
        with self.assertRaises(SystemExit) as cm:
            recheck.protocol_named(self.area, None)
        said = str(cm.exception)
        self.assertTrue(said.startswith("recheck: 2 protocols in"), said)
        self.assertIn("name one with --protocol FILE", said)
        self.assertIn("PROTOCOL-a.md", said)
        self.assertIn("PROTOCOL-b.md", said)

    def test_a_name_the_area_does_not_hold_is_refused(self):
        self._protocol("PROTOCOL-a.md")
        with self.assertRaises(SystemExit) as cm:
            recheck.protocol_named(self.area, "PROTOCOL-gone.md")
        self.assertTrue(str(cm.exception).startswith("recheck: "), cm.exception)


class TheScriptTheRunRan(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.area = Path(self._tmp.name).resolve() / "01-x"
        (self.area / "scripts").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _script(self, name: str, formula: str) -> None:
        (self.area / "scripts" / name).write_text(
            f"FORMULA = {formula!r}\n", encoding="utf-8"
        )

    def _run(self, run_id: str, script: str | None) -> Path:
        """A run directory whose record names SCRIPT; no record for None."""
        run = runs.run_path(self.area, run_id)
        run.mkdir(parents=True)
        if script is not None:
            record = run_record(script=script, command=[f"scripts/{script}"])
            (run / "config.json").write_text(json.dumps(record), encoding="utf-8")
        return run

    def test_each_run_is_evaluated_by_the_script_it_ran(self):
        """Two scripts in one area: the module is the one of the run's own
        record, not the area's measuring script for both."""
        self._script("01_measure.py", "the count")
        self._script("03_compare.py", "the comparison")
        measured = self._run("r1", "01_measure.py")
        compared = self._run("r2", "03_compare.py")
        self.assertEqual(
            recheck.script_module(self.area, measured).FORMULA, "the count"
        )
        self.assertEqual(
            recheck.script_module(self.area, compared).FORMULA, "the comparison"
        )

    def test_a_script_that_is_gone_is_not_verifiable(self):
        """No other script is taken in its place; the sentence carries the
        clause report-check reads as a check that could not be made."""
        self._script("01_measure.py", "the count")
        run = self._run("r1", "03_compare.py")
        with self.assertRaises(recheck.NotVerifiable) as cm:
            recheck.script_module(self.area, run)
        said = str(cm.exception)
        self.assertIn(f"run r1 {recheck.NOT_VERIFIABLE}", said)
        self.assertIn("its script scripts/03_compare.py is gone", said)

    def test_a_run_without_a_record_is_not_verifiable(self):
        self._script("01_measure.py", "the count")
        run = self._run("r1", None)
        with self.assertRaises(recheck.NotVerifiable) as cm:
            recheck.script_module(self.area, run)
        self.assertIn("it has no record of the script it ran", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
