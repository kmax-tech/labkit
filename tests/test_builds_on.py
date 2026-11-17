"""`[builds_on]`, the step the next runs make: the table read from the
protocol head (`protocol_block.builds_on`); the start refused while its
basis cannot be built on (`start_check.require_step_basis`) — a basis that
is no completed run of the area, a repeat, or a run of another protocol;
the declared changes held against the differences between the basis's and
the run's own texts (`protocol_history.step_change_gaps`), each run's step
read from its own text (`step_then`); and `protocol-fill --builds-on`,
which computes the changes from the basis's own text."""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import DEFAULT_BLOCK, PID, head, scope_file

from labkit.formats import protocol_block, runs
from labkit.formats.protocol_block import BlockError, BuildsOn, StepChange
from labkit.formats.protocol_history import (
    change_list_gaps,
    step_change_gaps,
    step_then,
)
from labkit.run import runlog
from labkit.tools import protocol_fill

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


def protocol(step: str = "", *, pid: str = PID, exclusions: str = "none") -> str:
    """A protocol whose head carries the default block and STEP, its
    Exclusions / filters EXCLUSIONS."""
    return head(id=pid, promises=DEFAULT_BLOCK + step) + (
        f"\n- **Question / hypothesis:** q\n- **Exclusions / filters:** {exclusions}\n"
    )


def step(run: str, *changes: tuple[str, str, str]) -> BuildsOn:
    """A step on RUN declaring CHANGES."""
    return BuildsOn(
        "filter",
        run,
        "observation",
        "errors cluster",
        tuple(StepChange(w, x, y, None) for w, x, y in changes),
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


FILTER = ("Exclusions / filters", "none", "short documents")


class ChangeList(unittest.TestCase):
    """`change_list_gaps` and `step_change_gaps` from texts in memory."""

    def test_both_directions_are_held_and_the_twin_passes(self) -> None:
        a, b = ("x", "1", "2"), ("y", "3", "4")
        gaps = change_list_gaps([a], [b])
        self.assertEqual((gaps.undeclared, gaps.not_shown), ((a,), (b,)))
        same = change_list_gaps([a], [a])
        self.assertEqual((same.undeclared, same.not_shown), ((), ()))

    def test_a_filter_change_is_declared_or_named(self) -> None:
        basis, run = protocol(), protocol(exclusions="short documents")
        held = step_change_gaps(basis, run, step(BASIS))
        self.assertEqual(held.undeclared, (FILTER,))
        twin = step_change_gaps(basis, run, step(BASIS, FILTER))
        self.assertEqual((twin.undeclared, twin.not_shown), ((), ()))
        shown_none = step_change_gaps(basis, basis, step(BASIS, FILTER))
        self.assertEqual(shown_none.not_shown, (FILTER,))

    def test_branching_each_run_against_its_own_basis(self) -> None:
        # B and D both build on A, E on B: E is compared with B, never with A
        a = protocol()
        b = protocol(exclusions="short documents")
        d = protocol(exclusions="long documents")
        e = protocol(exclusions="short documents")
        to_d = ("Exclusions / filters", "none", "long documents")
        self.assertEqual(step_change_gaps(a, b, step(BASIS, FILTER)).undeclared, ())
        self.assertEqual(step_change_gaps(a, d, step(BASIS, to_d)).undeclared, ())
        on_b = step_change_gaps(b, e, step(BASIS))
        self.assertEqual((on_b.undeclared, on_b.not_shown), ((), ()))
        self.assertEqual(step_change_gaps(a, e, step(BASIS)).undeclared, (FILTER,))

    def test_a_change_in_code_alone_is_no_difference_here(self) -> None:
        # the guaranteed statement covers the protocol parts only
        same = protocol()
        gaps = step_change_gaps(same, same, step(BASIS))
        self.assertEqual((gaps.undeclared, gaps.not_shown), ((), ()))


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


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class InARepository(unittest.TestCase):
    """Each run's step read from its own text, and `protocol-fill
    --builds-on` computing the changes from the basis's own text, in a
    repository with real runs."""

    def setUp(self) -> None:
        os.environ.pop("CLAUDECODE", None)
        self.root = Path(tempfile.mkdtemp())
        _git(self.root, "init", "-q")
        self.area = self.root / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(protocol(), encoding="utf-8")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "stamp")
        self.a = self.measure()
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "A")

    def measure(self) -> str:
        """A completed run of the protocol; its id."""
        r = runlog.run("m", config={}, base_dir=self.area, data=runlog.NO_INPUTS)
        with contextlib.redirect_stdout(io.StringIO()), r as run:
            run.metrics(criterion_1_pass=True)
        return run.run_id

    def fill(self, *argv: str) -> tuple[int, str]:
        """protocol-fill on the protocol: (exit, what it printed)."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = protocol_fill.main([str(self.protocol), *argv])
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, out.getvalue()

    def builds_on(self, basis: str) -> tuple[int, str]:
        return self.fill(
            "--builds-on",
            basis,
            "--step-id",
            "filter",
            "--occasion",
            "observation",
            "--why",
            "A's errors cluster in short documents",
        )

    def test_the_changes_are_computed_from_the_basis_own_text(self) -> None:
        self.protocol.write_text(
            protocol(exclusions="short documents"), encoding="utf-8"
        )
        code, told = self.builds_on(self.a)
        self.assertEqual(code, 0, told)
        written = protocol_block.builds_on(self.protocol.read_text(encoding="utf-8"))
        assert written is not None
        self.assertEqual(written.run, self.a)
        self.assertEqual([(c.what, c.from_, c.to) for c in written.changes], [FILTER])
        # B runs under the step; its own text holds it, and nothing is undeclared
        b = self.measure()
        rd = runs.read_run_dir(self.area / "runs" / b)
        then = step_then(self.protocol, rd, self.root)
        self.assertIsNone(then.unknown, then.where)
        assert then.step is not None and then.text is not None
        self.assertEqual(then.step.run, self.a)
        basis = step_then(
            self.protocol, runs.read_run_dir(self.area / "runs" / self.a), self.root
        )
        assert basis.text is not None
        gaps = step_change_gaps(basis.text, then.text, then.step)
        self.assertEqual((gaps.undeclared, gaps.not_shown), ((), ()))

    def test_a_second_step_replaces_the_first(self) -> None:
        self.assertEqual(self.builds_on(self.a)[0], 0)
        code, told = self.fill(
            "--builds-on",
            self.a,
            "--step-id",
            "seed",
            "--occasion",
            "planned",
            "--why",
            "another seed",
        )
        self.assertEqual(code, 0, told)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertEqual(text.count("[builds_on]"), 1)
        written = protocol_block.builds_on(text)
        assert written is not None
        self.assertEqual((written.id, written.occasion), ("seed", "planned"))

    def test_a_basis_that_cannot_be_built_on_leaves_the_file_untouched(self) -> None:
        before = self.protocol.read_text(encoding="utf-8")
        code, told = self.builds_on(BASIS)
        self.assertEqual(code, 2, told)
        self.assertIn("names no completed run", told)
        self.assertNotIn("runlog:", told)
        self.assertEqual(self.protocol.read_text(encoding="utf-8"), before)

    def test_a_basis_whose_own_text_is_lost_is_refused_not_replaced(self) -> None:
        # A2 starts from a changed tree; its patch lost, its text is unknown
        self.protocol.write_text(protocol(exclusions="tried"), encoding="utf-8")
        a2 = self.measure()
        self.protocol.write_text(protocol(), encoding="utf-8")
        (self.area / "runs" / a2 / "uncommitted.patch").unlink()
        rd = runs.read_run_dir(self.area / "runs" / a2)
        then = step_then(self.protocol, rd, self.root)
        self.assertIsNone(then.text)
        assert then.unknown is not None
        self.assertIn("its uncommitted.patch is gone", then.unknown)
        code, told = self.builds_on(a2)
        self.assertEqual(code, 2, told)
        self.assertIn("cannot be read back", told)
        self.assertIn("never from today's text", told)

    def test_two_runs_at_one_commit_each_read_their_own_step(self) -> None:
        self.assertEqual(self.builds_on(self.a)[0], 0)
        first = self.measure()
        code, _ = self.fill(
            "--builds-on",
            self.a,
            "--step-id",
            "seed",
            "--occasion",
            "planned",
            "--why",
            "another seed",
        )
        self.assertEqual(code, 0)
        second = self.measure()
        steps = [
            step_then(
                self.protocol, runs.read_run_dir(self.area / "runs" / r), self.root
            ).step
            for r in (first, second)
        ]
        self.assertEqual([s.id if s else None for s in steps], ["filter", "seed"])


if __name__ == "__main__":
    unittest.main()
