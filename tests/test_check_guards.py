"""The guards of the rule layer (`tests/check_guards.py`) and the state
builder (`tests/state_fixture.py`), each with a forbidden example it rejects
and an allowed one it passes (docs/notes/2026-11-10-test-model.md,
"Architecture guards").
"""

from __future__ import annotations

import ast
import subprocess
import unittest
from pathlib import Path

import pytest

from check_guards import ForbiddenAccess, no_process_or_command, pure_call
from labkit.formats.area_state import Measured
from labkit.formats.repo import shown
from labkit.gates import finalize
from protocol_fixture import PID
from state_fixture import AREA, area_state, run_dir

TESTS = Path(__file__).resolve().parent
#: the file name every rule test carries, so its mark is held below
RULE_TESTS = "test_rules_*.py"


class APureCallReadsNoFile(unittest.TestCase):
    def test_reading_listing_or_statting_a_file_is_refused(self):
        here = Path(__file__)
        with self.assertRaises(ForbiddenAccess):
            pure_call(here.read_text)
        with self.assertRaises(ForbiddenAccess):
            pure_call(here.is_file)
        with self.assertRaises(ForbiddenAccess):
            pure_call(here.exists)
        with self.assertRaises(ForbiddenAccess):
            pure_call(lambda: list(TESTS.iterdir()))

    def test_starting_a_process_is_refused(self):
        with self.assertRaises(ForbiddenAccess):
            pure_call(subprocess.run, ["true"], check=True)

    def test_a_computation_and_a_path_resolved_for_display_pass(self):
        self.assertEqual(pure_call(sorted, [2, 1]), [1, 2])
        self.assertEqual(pure_call(shown, AREA / "x.md", Path.cwd()), "area/x.md")

    def test_the_file_calls_come_back_after_the_call(self):
        with self.assertRaises(ForbiddenAccess):
            pure_call(Path(__file__).read_text)
        self.assertTrue(Path(__file__).is_file())


class ARuleTestStartsNoProcessAndEntersNoCommand(unittest.TestCase):
    def test_a_process_and_a_command_are_refused(self):
        with no_process_or_command():
            with self.assertRaises(ForbiddenAccess):
                subprocess.run(["git", "init", "-q"], check=True)
            with self.assertRaises(ForbiddenAccess):
                finalize.main(["area"])

    def test_typed_data_in_memory_passes(self):
        with no_process_or_command():
            self.assertEqual(area_state().runs, ())

    def test_every_rule_test_file_carries_the_mark(self):
        files = sorted(TESTS.glob(RULE_TESTS))
        self.assertTrue(files, f"no {RULE_TESTS} — the check would pass on nothing")
        for path in files:
            with self.subTest(path.name):
                self.assertTrue(_marks_rule(path.read_text(encoding="utf-8")))

    def test_the_mark_check_tells_a_marked_file_from_an_unmarked_one(self):
        self.assertTrue(_marks_rule("pytestmark = pytest.mark.rule\n"))
        self.assertFalse(_marks_rule("pytestmark = pytest.mark.slow\n"))


@pytest.mark.rule
class TheMarkSwitchesTheGuardOn(unittest.TestCase):
    def test_a_marked_test_cannot_start_a_process(self):
        with self.assertRaises(ForbiddenAccess):
            subprocess.run(["true"], check=True)


def _marks_rule(source: str) -> bool:
    """Does SOURCE, a test module, assign `pytestmark = pytest.mark.rule`?"""
    return any(
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets)
        and ast.unparse(node.value) == "pytest.mark.rule"
        for node in ast.parse(source).body
    )


class TheStateBuilderKeepsWhatItIsGiven(unittest.TestCase):
    """`state_fixture.area_state` derives and repairs nothing."""

    def test_an_inconsistent_state_stays_as_written(self):
        # a run present and the same run deleted, a protocol whose text is
        # missing, and nothing measured beside a run: `assemble` would derive
        # `measured`; the builder keeps every field as given
        state = area_state(
            protocols=[AREA / "PROTOCOL-x.md"],
            runs=[run_dir("r1")],
            deleted=[run_dir("r1", from_commit="c" * 40)],
        )
        self.assertEqual([rd.dir.name for rd in state.runs], ["r1"])
        self.assertEqual([rd.dir.name for rd in state.deleted], ["r1"])
        self.assertEqual(state.protocol_texts, {})
        self.assertEqual(state.measured, {})
        self.assertEqual(state.run_facts, ())

    def test_a_given_derived_field_is_kept_too(self):
        measured = Measured(AREA, PID, (), (), (), ())
        state = area_state(measured={PID: measured})
        self.assertIs(state.measured[PID], measured)


if __name__ == "__main__":
    unittest.main()
