"""What a step before the first measurement adds for what only the task can
say (`standard_contract.first_measurement_hint`): a report to register, and for a
computation a stated value to register as `[reference]` and the
hand-checked case to fill by hand. In usage round 24 no task-34 agent
registered the stated values before the first measurement (0 of 6), every
one filled the hand-checked case from its own run, and two reports were
never registered (docs/notes/2026-11-15-agent-guidance-replays.md). Read
from the head in memory; `labkit-next` and runlog print the same sentences
(their tests: `test_next_step.TheChain`,
`test_adoption_order.FirstStepBeforeARun`), in the same cases
(`BothCommandsInTheSameCases`).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from labkit.formats import protocol_block, runs
from labkit.formats.area_state import TREE, AreaState, assemble
from labkit.formats.standard_contract import first_measurement_hint
from labkit.gates import next_step
from labkit.run import start_check
from protocol_fixture import PID, head, run_record  # noqa: E402

PROTOCOL = Path("experiments/02-hrv/PROTOCOL-hrv.md")
WITHIN = 'value = 760\ntolerance = 7.6\nrelation = "within"\n'


class ForAComputation(unittest.TestCase):
    def test_a_bare_head_names_report_reference_and_hand_checked_case(self):
        hint = first_measurement_hint(PROTOCOL, head(repeat_cost="low", kind="compute"))
        self.assertIn('"report=REPORT.md"', hint)
        self.assertIn("`[reference]`", hint)
        self.assertIn("`tests/test_02_hrv.py`", hint)
        self.assertIn("copied from a run's output", hint)

    def test_a_registered_reference_is_not_asked_for_again(self):
        hint = first_measurement_hint(
            PROTOCOL, head(repeat_cost="low", kind="compute", reference=WITHIN)
        )
        self.assertNotIn("`[reference]`", hint)
        self.assertIn("hand-checked case", hint)

    def test_a_registered_report_is_not_asked_for_again(self):
        hint = first_measurement_hint(
            PROTOCOL, head(repeat_cost="low", kind="compute", report="REPORT.md")
        )
        self.assertNotIn("report=REPORT.md", hint)
        self.assertIn("`[reference]`", hint)


class ForAKindWithABar(unittest.TestCase):
    """A fit or an apply compares in its criterion and carries no
    hand-checked case in its stamped test: only the report is named."""

    def test_only_the_report(self):
        for kind in ("fit", "apply"):
            with self.subTest(kind=kind):
                hint = first_measurement_hint(
                    PROTOCOL, head(repeat_cost="low", kind=kind)
                )
                self.assertIn('"report=REPORT.md"', hint)
                self.assertNotIn("[reference]", hint)
                self.assertNotIn("hand-checked", hint)


class TheColdReader(unittest.TestCase):
    """LAB-102 Cold reader before freezing: preflight names the reader where
    the freeze is owed; at low nothing freezes and preflight never runs, so
    the step before the first measurement names it (argmining27, 2026-11-17:
    an unclear `evaluate_rows` surfaced only to another session after the
    run)."""

    def test_named_at_low_for_every_kind(self):
        for kind in ("compute", "fit", "apply"):
            with self.subTest(kind=kind):
                hint = first_measurement_hint(
                    PROTOCOL, head(repeat_cost="low", kind=kind)
                )
                self.assertIn("`labkit-audit experiments/02-hrv --mode clarity`", hint)
                self.assertIn("blocks nothing", hint)

    def test_not_at_high_where_preflight_names_it(self):
        hint = first_measurement_hint(PROTOCOL, head(repeat_cost="high", kind="apply"))
        self.assertNotIn("--mode clarity", hint)


class WithoutAnId(unittest.TestCase):
    def test_nothing(self):
        self.assertEqual(
            first_measurement_hint(
                PROTOCOL, head(id="<p-id>", repeat_cost="low", kind="compute")
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()


def _record(name: str, run_kind: runs.RunKind = "measurement") -> runs.RunDir:
    cfg = runs.parse_run_config(
        run_record(protocol={"id": PID, "path": "PROTOCOL-x.md"}, run_kind=run_kind)
    )
    return runs.RunDir(Path("runs") / name, cfg, None)


class BothCommandsInTheSameCases(unittest.TestCase):
    """runlog's first step and `labkit-next` add the hint while the area has
    not measured the protocol (`area_state.Measured.has_measured`), and
    neither adds it after: a lost run and a run whose record does not read
    count, as either may have been the first measurement."""

    TEXT = head(repeat_cost="low", kind="compute")

    def hints(self, state: AreaState) -> tuple[bool, bool]:
        """(runlog's first step carries the hint, labkit-next's does)."""
        bound = start_check._Bound(  # noqa: SLF001
            {"id": PID, "path": "PROTOCOL-x.md"},
            self.TEXT,
            protocol_block.head(self.TEXT),
        )
        runlog = start_check._first_step(Path("area"), bound, state)  # noqa: SLF001
        after = next_step._before_first_hint(  # noqa: SLF001
            Path("area") / "PROTOCOL-x.md", self.TEXT, state.measured_of(PID)
        )
        return "register it now" in runlog, "register it now" in after

    def state(
        self, present: list[runs.RunDir], lost: dict[str, str] | None = None
    ) -> AreaState:
        return assemble(Path("area"), None, TREE, present, [], lost or {})

    def test_before_a_measurement_both_add_it(self):
        probe = _record("2026-10-07T09-00-00_0000", run_kind="probe")
        for name, state in (
            ("no run", self.state([])),
            ("a probe only", self.state([probe])),
        ):
            with self.subTest(name):
                self.assertEqual(self.hints(state), (True, True))

    def test_after_a_measurement_neither_adds_it(self):
        dead = runs.RunDir(
            Path("runs") / "2026-10-06T10-00-00_dead", None, "unreadable"
        )
        for name, state in (
            (
                "a measurement that reads",
                self.state([_record("2026-10-07T10-00-00_ab12")]),
            ),
            ("a lost run", self.state([], {"2026-10-05T10-00-00_lost": PID})),
            ("a record that does not read", self.state([dead])),
        ):
            with self.subTest(name):
                self.assertEqual(self.hints(state), (False, False))


class AnEarlierMeasurementWithoutItsRecord(unittest.TestCase):
    """runlog's start names an earlier measurement that left no record that
    reads (`start_check.earlier_measurement_note`): the run is not the
    first, HEAD does not stand in for what was registered then, and finalize
    will hold the number — a warning, the run starts."""

    TEXT = BothCommandsInTheSameCases.TEXT

    def state(
        self, present: list[runs.RunDir], lost: dict[str, str] | None = None
    ) -> AreaState:
        return assemble(Path("area"), None, TREE, present, [], lost or {})

    def note(self, state: AreaState) -> str | None:
        bound = start_check._Bound(  # noqa: SLF001
            {"id": PID, "path": "PROTOCOL-x.md"},
            self.TEXT,
            protocol_block.head(self.TEXT),
        )
        return start_check.earlier_measurement_note(bound, state)

    def test_a_lost_run_and_an_unreadable_record_are_named(self):
        dead = runs.RunDir(
            Path("runs") / "2026-10-06T10-00-00_dead", None, "unreadable"
        )
        for name, state, run in (
            (
                "a lost run",
                self.state([], {"2026-10-05T10-00-00_lost": PID}),
                "run 2026-10-05T10-00-00_lost is gone",
            ),
            (
                "a record that does not read",
                self.state([dead]),
                "the record of run 2026-10-06T10-00-00_dead does not read",
            ),
        ):
            with self.subTest(name):
                note = self.note(state)
                assert note is not None
                self.assertIn(run, note)
                self.assertIn("PROTOCOL-x.md: not its first measurement", note)
                self.assertIn("does not stand in for it", note)
                self.assertIn("The run starts", note)

    def test_the_twins_no_measurement_and_one_that_reads_say_nothing(self):
        for name, state in (
            ("no run", self.state([])),
            (
                "a measurement that reads",
                self.state([_record("2026-10-07T10-00-00_ab12")]),
            ),
            (
                "a run lost to another protocol",
                self.state([], {"2026-10-05T10-00-00_lost": "p-0000000000000000"}),
            ),
        ):
            with self.subTest(name):
                self.assertIsNone(self.note(state))
