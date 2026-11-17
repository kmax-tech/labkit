"""`[builds_on]`, the step the next runs make: the table read from the
protocol head (`protocol_block.builds_on`), and the start refused while its
basis cannot be built on (`start_check.require_step_basis`) — a basis that
is no completed run of the area, a repeat, or a run of another protocol."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import DEFAULT_BLOCK, PID, head, scope_file

from labkit.formats import protocol_block
from labkit.formats.protocol_block import BlockError, StepChange
from labkit.run import runlog

BASIS = "2026-11-17T10-00-00_aaaa"
OTHER_PID = "p-fedcba9876543210"


def step_toml(
    run: str = BASIS,
    *,
    step_id: str = "filter",
    occasion: str = "observation",
    why: str = "A's errors cluster in short documents",
    changes: str = "",
) -> str:
    """A `[builds_on]` table as TOML, CHANGES appended verbatim."""
    return (
        f'\n[builds_on]\nid = "{step_id}"\nrun = "{run}"\n'
        f'occasion = "{occasion}"\nwhy = "{why}"\n{changes}'
    )


def protocol(step: str = "", *, pid: str = PID) -> str:
    """A protocol whose head carries the default block and STEP."""
    return head(id=pid, promises=DEFAULT_BLOCK + step) + (
        "\n- **Question / hypothesis:** q\n"
    )


class Parse(unittest.TestCase):
    """The table from data in memory: each field and its refusal."""

    def test_a_step_reads_with_its_changes(self) -> None:
        changes = (
            '[[builds_on.change]]\nwhat = "Exclusions / filters"\n'
            'from = "(none)"\nto = "documents under 3 lines"\n'
            '[[builds_on.change]]\nwhat = "Unit"\nfrom = "a"\nto = "b"\n'
            'why = "the unit follows the filter"\n'
        )
        step = protocol_block.builds_on(protocol(step_toml(changes=changes)))
        assert step is not None
        self.assertEqual(
            (step.id, step.run, step.occasion), ("filter", BASIS, "observation")
        )
        self.assertEqual(
            step.changes,
            (
                StepChange(
                    "Exclusions / filters", "(none)", "documents under 3 lines", None
                ),
                StepChange("Unit", "a", "b", "the unit follows the filter"),
            ),
        )

    def test_the_twin_no_table_is_no_step(self) -> None:
        self.assertIsNone(protocol_block.builds_on(protocol()))

    def test_each_malformed_field_is_named(self) -> None:
        cases = {
            "[builds_on] id": step_toml(step_id="Filter One"),
            "[builds_on] run": step_toml(run="runs/2026-11-17"),
            "[builds_on] occasion": step_toml(occasion="hunch"),
            "[builds_on] why": step_toml(why=" "),
            "#1: to missing": step_toml(
                changes='[[builds_on.change]]\nwhat = "Unit"\nfrom = "a"\n'
            ),
            "unknown field": step_toml(changes='basis = "A"\n'),
        }
        for named, step in cases.items():
            with self.subTest(named), self.assertRaises(BlockError) as cm:
                protocol_block.builds_on(protocol(step))
            self.assertIn(named, str(cm.exception))


class StartRefusal(unittest.TestCase):
    """A start under a step whose basis cannot be built on is refused before
    its run directory exists; a valid basis starts."""

    def setUp(self) -> None:
        os.environ.pop("CLAUDECODE", None)
        self.area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(protocol(), encoding="utf-8")
        self.basis = self.measure()

    def measure(
        self, *, repeat_of: str | None = None, protocol: Path | None = None
    ) -> str:
        """A completed run of the area; its id."""
        r = runlog.run(
            "m",
            config={},
            base_dir=self.area,
            data=runlog.NO_INPUTS,
            repeat_of=repeat_of,
            protocol=protocol,
        )
        with contextlib.redirect_stdout(io.StringIO()), r as run:
            run.metrics(criterion_1_pass=True)
        return run.run_id

    def started_on(self, basis: str) -> str:
        """The refusal of a start under a step on BASIS, "" when it starts."""
        self.protocol.write_text(protocol(step_toml(basis)), encoding="utf-8")
        held = set((self.area / "runs").iterdir())
        try:
            self.measure(protocol=self.protocol)
        except SystemExit as exc:
            self.assertEqual(set((self.area / "runs").iterdir()), held)
            return str(exc.code)
        return ""

    def test_the_twin_a_completed_run_of_this_protocol_is_built_on(self) -> None:
        self.assertEqual(self.started_on(self.basis), "")

    def test_a_basis_that_is_no_run_of_the_area_is_refused(self) -> None:
        told = self.started_on(BASIS)
        self.assertIn(f"[builds_on] run={BASIS!r} names no completed run", told)

    def test_a_repeat_is_never_a_basis(self) -> None:
        again = self.measure(repeat_of=self.basis)
        told = self.started_on(again)
        self.assertIn(f"is a repeat of {self.basis}", told)
        self.assertIn(f"build on {self.basis}", told)

    def test_a_run_of_another_protocol_is_never_a_basis(self) -> None:
        other = self.area / "PROTOCOL-y.md"
        other.write_text(protocol(pid=OTHER_PID), encoding="utf-8")
        theirs = self.measure(protocol=other)
        told = self.started_on(theirs)
        self.assertIn(f"is bound to {OTHER_PID}, not to this protocol ({PID})", told)

    def test_a_table_that_does_not_read_is_refused(self) -> None:
        self.protocol.write_text(
            protocol(step_toml(self.basis, occasion="hunch")), encoding="utf-8"
        )
        with self.assertRaises(SystemExit) as cm:
            self.measure()
        self.assertIn("[builds_on] occasion = 'hunch'", str(cm.exception.code))


if __name__ == "__main__":
    unittest.main()
