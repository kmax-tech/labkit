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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from labkit.formats import protocol_block, runs
from labkit.formats.area_state import TREE, AreaState, assemble
from labkit.formats.run_starts import RunStart
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
    and whose index row names the protocol count, as either may have been
    the first measurement; a record no row names counts for no protocol."""

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

    DEAD = "2026-10-06T10-00-00_dead"

    def state(
        self,
        present: list[runs.RunDir],
        lost: dict[str, str] | None = None,
        index: dict[str, str] | None = None,
    ) -> AreaState:
        return assemble(
            Path("area"), None, TREE, present, [], lost or {}, indexed=index
        )

    def dead(self) -> runs.RunDir:
        return runs.RunDir(Path("runs") / self.DEAD, None, "unreadable")

    def test_before_a_measurement_both_add_it(self):
        probe = _record("2026-10-07T09-00-00_0000", run_kind="probe")
        for name, state in (
            ("no run", self.state([])),
            ("a probe only", self.state([probe])),
            ("a record no index row names", self.state([self.dead()])),
            (
                "a record bound to another protocol",
                self.state([self.dead()], index={self.DEAD: "p-0000000000000000"}),
            ),
        ):
            with self.subTest(name):
                self.assertEqual(self.hints(state), (True, True))

    def test_after_a_measurement_neither_adds_it(self):
        for name, state in (
            (
                "a measurement that reads",
                self.state([_record("2026-10-07T10-00-00_ab12")]),
            ),
            ("a lost run", self.state([], {"2026-10-05T10-00-00_lost": PID})),
            (
                "a record that does not read, bound by its index row",
                self.state([self.dead()], index={self.DEAD: PID}),
            ),
        ):
            with self.subTest(name):
                self.assertEqual(self.hints(state), (False, False))


class AnEarlierRunWithoutItsRecord(unittest.TestCase):
    """runlog's start names the runs without a record
    (`start_check.earlier_measurement_note`), one sentence per case: one
    that may have been the first measurement (HEAD does not stand in for
    what was registered then, finalize will hold the number) — also where
    the start files do not tell its order against a measurement that
    reads —, one the start files put after a measurement that reads
    (nothing held, the assumption behind that stated), one whose binding
    the files contradict, one whose protocol cannot be determined (held
    against none) — a warning each, the run starts."""

    TEXT = BothCommandsInTheSameCases.TEXT
    READS = "2026-10-07T10-00-00_ab12"
    LOST = "2026-10-07T10-00-05_105e"
    DEAD = "2026-10-06T10-00-00_dead"
    NOON = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)

    def note(
        self,
        index: dict[str, str],
        present: list[runs.RunDir],
        lost: dict[str, str] | None = None,
        starts: dict[str, tuple[str, int]] | None = None,
    ) -> str | None:
        """The note over the runs PRESENT, the LOST ones, the run index
        INDEX (run id → protocol id) and the start files STARTS (run id →
        its protocol id and its start, in seconds after NOON)."""
        bound = start_check._Bound(  # noqa: SLF001
            {"id": PID, "path": "PROTOCOL-x.md"},
            self.TEXT,
            protocol_block.head(self.TEXT),
        )
        state = assemble(
            Path("area"),
            None,
            TREE,
            present,
            [],
            lost or {},
            indexed=index,
            starts={
                run: RunStart(
                    run, pid, self.NOON + timedelta(seconds=after), "measurement"
                )
                for run, (pid, after) in (starts or {}).items()
            },
        )
        return start_check.earlier_measurement_note(bound, state)

    def dead(self) -> runs.RunDir:
        return runs.RunDir(Path("runs") / self.DEAD, None, "unreadable")

    def test_a_run_that_may_have_been_the_first_is_named_with_what_holds(self):
        for name, index, present, lost, starts, run in (
            (
                "a lost run",
                {self.LOST: PID},
                [],
                {self.LOST: PID},
                None,
                f"run {self.LOST} is gone",
            ),
            (
                "a record that does not read, bound by its index row",
                {self.DEAD: PID},
                [self.dead()],
                None,
                None,
                f"the record of run {self.DEAD} does not read",
            ),
            (
                "a record that does not read, bound by its start file",
                {},
                [self.dead()],
                None,
                {self.DEAD: (PID, 0)},
                f"the record of run {self.DEAD} does not read",
            ),
        ):
            with self.subTest(name):
                note = self.note(index, present, lost, starts)
                assert note is not None
                self.assertIn(run, note)
                self.assertIn(
                    "PROTOCOL-x.md: this run is not held to HEAD as its first "
                    "measurement",
                    note,
                )
                self.assertIn("may have been the first", note)
                self.assertIn("does not stand in for it", note)
                self.assertIn("The run starts", note)
                self.assertNotIn("is unknown", note)

    def test_an_order_the_start_record_does_not_tell_is_said_and_held_like_the_first(
        self,
    ):
        """No start for the lost run: its id and its row's place in the
        index order nothing."""
        note = self.note(
            {self.READS: PID, self.LOST: PID},
            [_record(self.READS)],
            {self.LOST: PID},
            {self.READS: (PID, 0)},
        )
        assert note is not None
        self.assertIn(f"run {self.LOST} is gone", note)
        self.assertIn("whether it started before the measurements that read", note)
        self.assertIn(f"no start file holds a start for {self.LOST}", note)
        self.assertIn("hold every number of this protocol", note)

    def test_a_lost_run_started_after_a_measurement_that_reads_holds_nothing(self):
        note = self.note(
            {self.READS: PID, self.LOST: PID},
            [_record(self.READS)],
            {self.LOST: PID},
            {self.READS: (PID, 0), self.LOST: (PID, 5)},
        )
        assert note is not None
        self.assertIn(f"run {self.LOST} is gone", note)
        self.assertIn("nothing is held for it", note)
        self.assertIn("which labkit does not check", note)
        self.assertNotIn("not held to HEAD", note)

    def test_a_binding_the_files_contradict_is_named(self):
        other = "p-0000000000000000"
        note = self.note({self.DEAD: other}, [self.dead()], None, {self.DEAD: (PID, 0)})
        assert note is not None
        self.assertIn("which protocol a run belongs to is contradicted", note)
        self.assertIn(f"its start file names {PID}", note)
        self.assertIn(f"the run index names {other}", note)

    def test_a_record_no_file_names_is_held_against_no_protocol(self):
        note = self.note({}, [self.dead()])
        assert note is not None
        self.assertIn(f"the record of run {self.DEAD} does not read", note)
        self.assertIn("which protocol it belongs to cannot be determined", note)
        self.assertIn("nor that none came before", note)
        self.assertIn("restore its config.json", note)
        self.assertNotIn("not held to HEAD", note)

    def test_the_twins_say_nothing(self):
        other = "p-0000000000000000"
        for name, index, present, lost in (
            ("no run", {}, [], None),
            (
                "a measurement that reads",
                {self.READS: PID},
                [_record(self.READS)],
                None,
            ),
            (
                "a run lost to another protocol",
                {self.LOST: other},
                [],
                {self.LOST: other},
            ),
            (
                "a record bound to another protocol",
                {self.DEAD: other},
                [self.dead()],
                None,
            ),
        ):
            with self.subTest(name):
                self.assertIsNone(self.note(index, present, lost))
