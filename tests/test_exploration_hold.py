"""finalize's station 2 splits by the workflow the first measurement
registered (`registration_station`): a confirmatory protocol keeps the
first-measurement lock; an exploratory one binds each run to its own text
and the step it made (`exploration_hold`), and a type changed after the
first measurement is held either way (`registration_hold.type_hold`).

Real commands on a stamped count lab (`test_end_to_end.stamp_count`): the
measuring script, `protocol-fill` and its `--builds-on`, git commits and
finalize. Acceptance cases 2, 4, 6, 12 and 18 of the plan
(docs/notes/2026-11-14-exploratory-workflow-plan.md), each with its twin;
the old hold is shown on the confirmatory twin.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

import test_end_to_end as e2e
from protocol_fixture import PID, completed_run, head, scope_file

from labkit.gates import registration_station, report_context

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

FIRST_LOCK = "what the number is about changed after the first measurement"
FILTER = "Exclusions / filters=hidden entries, nested directories and empty documents"
UNIT = "Unit=one visible document of data/raw/docs"
EXPLORING = "exploratory: each step the answering run builds on declares its changes"


class _Exploration(e2e.CountCommands):
    """A count lab of the given type with run A measured and finalize
    clean. A base without tests of its own."""

    def setUp(self) -> None:
        super().setUp()
        self.run_a = self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)

    def step_on(self, basis: str, step: str = "filter") -> None:
        """`protocol-fill --builds-on BASIS`: the step with its changes computed."""
        self.lab.fill(
            self.protocol,
            "--builds-on",
            basis,
            "--step-id",
            step,
            "--occasion",
            "observation",
            "--why",
            "A counted empty documents as zero-line rows",
        )

    def set_type(self, protocol_type: str) -> None:
        """The head's type rewritten in the TOML head, as an author edits it
        (protocol-fill sets only the stamp's placeholder)."""
        text = self.protocol.read_text(encoding="utf-8")
        was = next(ln for ln in text.splitlines() if ln.strip().startswith("type = "))
        self.protocol.write_text(
            text.replace(was, f'type = "{protocol_type}"', 1), encoding="utf-8"
        )

    def holds(self) -> tuple[int, str, list[str]]:
        """(exit, output, BLOCKER lines) of finalize on the area."""
        rc, out = self.lab.finalize(self.area)
        return rc, out, [ln for ln in out.splitlines() if "BLOCKER" in ln]


class AStepDeclared(_Exploration):
    """B measured after a step on A that declares the changed filter."""

    def test_the_declared_change_passes_in_exploration(self):
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)
        self.lab.commit("B filters empty documents, declared as a step on A")
        self.measure()
        rc, out, blockers = self.holds()
        self.assertEqual(blockers, [], out)
        self.assertNotIn(FIRST_LOCK, out)
        self.assertIn(EXPLORING, out)
        self.assertEqual(rc, 0, out)

    def test_an_undeclared_change_beside_the_step_is_held_by_its_entry(self):
        """Case 4: the Unit changed too, after the step was written."""
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)
        self.lab.fill(self.protocol, "--force", UNIT)
        self.lab.commit("B: the step, and a Unit the step does not name")
        b = self.measure()
        rc, out, blockers = self.holds()
        (line,) = [ln for ln in blockers if 'made the step "filter"' in ln]
        self.assertIn(f"run {b} made the step", line)
        self.assertIn('not declared: Unit "one document of data/raw/docs"', line)
        self.assertNotIn("Exclusions / filters", line.split("not declared:")[1])
        self.assertIn("--builds-on", line)
        self.assertIn(f"{b} keeps the text it ran under", line)
        self.assertEqual(rc, 1, out)


class NoStepDeclared(_Exploration):
    """Case 6 and case 18: changes without a step."""

    def test_a_run_without_a_step_under_the_same_text_passes(self):
        self.measure()
        rc, out, blockers = self.holds()
        self.assertEqual((rc, blockers), (0, []), out)

    def test_a_prepared_step_leaves_the_older_run_checkable(self):
        """Step B written on A, not yet measured: A is not adopted, so
        finalize reads it under its own text and does not hold it."""
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)
        self.lab.commit("step B prepared on A, not measured")
        rc, out, blockers = self.holds()
        self.assertEqual((rc, blockers), (0, []), out)
        self.assertIn("once it adopts that run as its result", out)

    def test_adopting_a_run_under_a_text_changed_since_is_held(self):
        """Case 18: the result would be read under a text no run measured —
        held at the adoption, which checks its proposal through
        report-check, and not written."""
        self.lab.fill(self.protocol, "--force", FILTER)
        self.lab.commit("the filter changed, not measured")
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        (line,) = [
            ln
            for ln in out.splitlines()
            if "BLOCKER" in ln and "after the answering run" in ln
        ]
        self.assertIn(f"changed after the answering run {self.run_a}", line)
        self.assertIn("Exclusions / filters", line)
        self.assertIn(f"measure the change as a step on {self.run_a}", line)
        self.assertIn("--builds-on", line)
        self.assertNotIn(FIRST_LOCK, out)
        self.assertNotEqual(rc, 0, out)
        self.assertIsNone(self.declared())

    def test_the_twin_adopting_under_the_unchanged_text_is_not_held_so(self):
        _, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertNotIn("after the answering run", out)

    def test_a_run_measured_under_a_change_without_a_step_is_held(self):
        """Case 6, changed: declare its step."""
        self.lab.fill(self.protocol, "--force", FILTER)
        self.lab.commit("the filter changed, no step")
        b = self.measure()
        rc, out, blockers = self.holds()
        (line,) = [ln for ln in blockers if "without a step" in ln]
        self.assertIn(f"run {b} was measured without a step", line)
        self.assertIn(f"first measurement {self.run_a}'s", line)
        self.assertIn("Exclusions / filters", line)
        self.assertIn("declare the step", line)
        self.assertEqual(rc, 1, out)


class Confirmation(_Exploration):
    """Case 2: the same declared step in a confirmatory protocol is held by
    the first-measurement lock as before."""

    PROTOCOL_TYPE = "confirmatory"

    def test_a_declared_step_does_not_lift_the_confirmatory_lock(self):
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)
        self.lab.commit("B filters empty documents, declared as a step on A")
        self.measure()
        rc, out, blockers = self.holds()
        self.assertTrue(any(FIRST_LOCK in ln for ln in blockers), out)
        self.assertNotIn(EXPLORING, out)
        self.assertEqual(rc, 1, out)

    def test_the_twin_unchanged_passes(self):
        self.measure()
        rc, out, blockers = self.holds()
        self.assertEqual((rc, blockers), (0, []), out)


class TypeChanged(_Exploration):
    """Case 12: the type changed after the first measurement, in either
    direction, is held; the way out a new protocol, or the type back."""

    def test_exploration_turned_confirmatory_is_held(self):
        self.set_type("confirmatory")
        self.lab.commit("relabelled after A")
        rc, out, blockers = self.holds()
        (line,) = [ln for ln in blockers if "the type changed" in ln]
        self.assertIn(
            f"the type changed after the first measurement {self.run_a}: "
            f'"exploratory" → "confirmatory" (as the protocol stands now)',
            line,
        )
        self.assertIn("turns no exploration into a confirmation", line)
        self.assertIn('put `type = "exploratory"` back', line)
        self.assertIn("register anew", line)
        self.assertEqual(rc, 1, out)

    def test_the_twin_the_type_back_passes(self):
        self.set_type("confirmatory")
        self.set_type("exploratory")
        self.lab.commit("relabelled and back")
        rc, out, blockers = self.holds()
        self.assertEqual((rc, blockers), (0, []), out)


class ConfirmationTurnedExploratory(_Exploration):
    PROTOCOL_TYPE = "confirmatory"

    def test_confirmation_turned_exploratory_keeps_its_lock_and_is_held(self):
        """The workflow stays the first measurement's: the declared step is
        held by the confirmatory lock, and the relabelling by its own hold."""
        self.set_type("exploratory")
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)
        self.lab.commit("relabelled exploratory, then a step")
        b = self.measure()
        rc, out, blockers = self.holds()
        typed = [ln for ln in blockers if "the type changed" in ln]
        self.assertEqual(len(typed), 2, out)  # B's own text and the protocol now
        self.assertIn(f"as the answering run {b} saw the protocol", typed[0])
        self.assertTrue(any(FIRST_LOCK in ln for ln in blockers), out)
        self.assertEqual(rc, 1, out)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class UndecidedAtTheFirstMeasurement(unittest.TestCase):
    """A first measurement whose type was the stamp's placeholder (a run an
    earlier labkit let start): no workflow can be read from it, so the
    confirmatory lock applies, never the exploratory one, and naming the
    type exploratory afterwards is a type change. From records written as
    runlog writes them (`protocol_fixture.completed_run`)."""

    FIRST = "2026-10-07T09-25-31_98dd"
    LATER = "2026-10-07T10-00-00_ab12"

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        _git(self.root, "init", "-q")
        self.area = self.root / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)
        self.protocol = self.area / "PROTOCOL-x.md"

    def commit(self, protocol_type: str, question: str) -> str:
        self.protocol.write_text(
            head(repeat_cost="low", type=protocol_type)
            + f"- **Question / hypothesis:** {question}\n",
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        return _git(self.root, "rev-parse", "HEAD")

    def run_at(self, commit: str, name: str) -> Path:
        run = completed_run(self.area, name, metrics={"criterion_1_pass": True})
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["git"], data["git_full"] = commit[:7], commit
        cfg.write_text(json.dumps(data), encoding="utf-8")
        return run

    def test_an_undecided_first_type_holds_the_confirmatory_way(self):
        self.run_at(
            self.commit("<exploratory | confirmatory>", "does it hold?"), self.FIRST
        )
        later = self.run_at(
            self.commit("exploratory", "does it hold here?"), self.LATER
        )
        ctx = report_context.checked(self.area, self.protocol)
        self.assertEqual(ctx.run, later)
        exploring, holds = registration_station.station_changes(
            ctx.area, ctx.protocol, PID, ctx.run, ctx.area_state, ctx.evidence
        )
        self.assertFalse(exploring)
        lines = [h.line for h in holds]
        self.assertTrue(any('"undecided" → "exploratory"' in ln for ln in lines), lines)
        self.assertTrue(any(FIRST_LOCK in ln for ln in lines), lines)
