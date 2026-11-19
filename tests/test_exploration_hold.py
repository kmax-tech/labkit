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

import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

import test_end_to_end as e2e

from labkit.formats import run_starts
from labkit.formats import standard_contract as sc

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

FIRST_LOCK = "what the number is about changed after the first measurement"
FILTER = "Exclusions / filters=hidden entries, nested directories and empty documents"
UNIT = "Unit=one visible document of data/raw/docs"
UNIT_BEFORE = "Unit=one document of data/raw/docs"
EXPLORING = "exploratory: each step the answering run builds on declares its changes"
SPLIT = "the first measurements saw different texts"


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


class GoingOnAfterAnAdoption(_Exploration):
    """A audited, adopted and committed; the exploration goes on with step
    B. The adoption keeps A the answering run, so B prepared is held at
    the stop and the commit until the adoption is withdrawn
    (`protocol-fill --withdraw`), which keeps A, its number and the reason
    in the protocol."""

    WHY = "exploration goes on: step B filters empty documents"

    def setUp(self) -> None:
        super().setUp()
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 0, out)
        self.lab.commit(f"adopt {self.run_a}")
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)

    def held_line(self, out: str) -> str:
        (line,) = [
            ln
            for ln in out.splitlines()
            if "BLOCKER" in ln and "after the answering run" in ln
        ]
        return line

    def test_a_step_prepared_after_the_adoption_names_the_withdrawal_first(self):
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(self.protocol)
        line = self.held_line(out)
        self.assertEqual(rc, 1, out)
        way = line.split("Next:")[1]
        self.assertLess(way.index("--withdraw"), way.index("as a step on"), line)
        self.assertIn(f"{self.run_a}, its number and the withdrawal's reason stay", way)

    def test_b_measured_beside_the_standing_adoption_releases_nothing(self):
        self.lab.commit("step B prepared on the adopted A")
        self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertIn(f"after the answering run {self.run_a}", self.held_line(out))
        self.assertEqual(rc, 1, out)

    def test_withdrawn_a_stays_and_b_is_measured_audited_and_adopted(self):
        rc, out = self.withdraw(self.WHY)
        self.assertEqual(rc, 0, out)
        self.assertIsNone(self.declared())
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(self.protocol)
        self.assertEqual(rc, 0, out)
        self.lab.commit("withdraw A, step B prepared")
        b = self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        rc, out, prompt = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, b)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared(), b)
        # A is kept: its run, its number, and the reason it was withdrawn,
        # which B's auditor is shown
        self.assertTrue((self.area / "runs" / self.run_a / "metrics.json").is_file())
        text = self.protocol.read_text(encoding="utf-8")
        self.assertRegex(text, rf"- {self.run_a} — .* · withdrawn [-\d]+: {self.WHY}")
        self.assertIn(self.WHY, prompt)


class CorrectionInExploration(e2e.CorrectionCommands):
    """The correction commands' lab (Data / scope registered with 4
    documents, run A read 3), exploratory: the twins of
    `test_end_to_end.CorrectedDescription` and `CorrectionThenNewRun`,
    which run confirmatory. Adopting A under the corrected text takes the
    correction route; a later run takes the step."""

    PROTOCOL_TYPE = "exploratory"

    def repair_step(self) -> None:
        self.lab.fill(
            self.protocol,
            "--builds-on",
            self.run_a,
            "--step-id",
            "recount",
            "--occasion",
            "repair",
            "--why",
            "Data / scope named 4 documents; 3 are there",
        )

    def test_adopting_a_under_its_corrected_description_takes_the_correction_route(
        self,
    ):
        blocking = self.audited("BLOCKER", "Data / scope")
        self.describe(self.RIGHT)
        self.decide(blocking, 1, "fixed", "Data / scope now says 3 documents")
        rc, out = self.lab.finalize(self.area)  # not adopted: A under its own text
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"changed after the answering run {self.run_a}", out)
        rc, out, _ = self.follow_up(blocking, "resolved", "3 documents, as A read")
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared(), self.run_a)

    def test_the_correction_declared_as_a_repair_step_is_measured_and_adopted(self):
        self.describe(self.RIGHT)
        self.repair_step()
        run_b = self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 0, out)

    def test_a_first_measurement_changed_in_the_tree_stands_by_its_own_text(self):
        """The correction left in the tree, B measured at A's commit
        without a step: A and B are two first measurements with different
        texts, and in exploration that alone holds nothing — B stands by
        its own text and is audited and adopted. C, a repair step on A at
        the same commit, is measured and finalized too."""
        self.describe(self.RIGHT)
        run_b = self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertNotIn(SPLIT, out)
        self.assertEqual(rc, 0, out)
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared(), run_b)

    def test_a_repair_step_on_a_at_the_same_commit_goes_on(self):
        self.describe(self.RIGHT)
        self.measure()
        self.repair_step()
        self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertNotIn(SPLIT, out)
        self.assertEqual(rc, 0, out)

    def test_a_correction_after_a_step_is_shown_against_the_audited_runs_text(self):
        """A step on A changes Data / scope to 2 documents, C is measured
        under it, and C's audit has the field corrected in place to 3. The
        hold releases against C's own text, so the follow-up shows C's value
        as the one corrected — not the first measurement A's — and its
        `resolved` lets C be adopted."""
        two = "data/raw/docs, 2 documents, read directly"
        self.describe(two)
        self.lab.fill(
            self.protocol,
            "--builds-on",
            self.run_a,
            "--step-id",
            "two",
            "--occasion",
            "planned",
            "--why",
            "two documents only",
        )
        self.lab.commit("step two on A")
        run_c = self.measure()
        blocking = self.audited("BLOCKER", "Data / scope")
        self.describe(self.RIGHT)
        self.decide(blocking, 1, "fixed", "Data / scope now says 3 documents")
        rc, out, prompt = self.follow_up(blocking, "resolved", "3 documents, as C read")
        self.assertEqual(rc, 0, out)
        self.assertIn(f"Data / scope registered (as the run audited {run_c}", prompt)
        self.assertIn(f"): {two}", prompt)
        self.assertNotIn(f"): {self.WRONG}", prompt)
        rc, out = self.lab.adopt(self.protocol, run_c)
        self.assertEqual(rc, 0, out)

    def test_the_correction_measured_without_a_step_is_held_naming_the_step(self):
        self.describe(self.RIGHT)
        self.lab.commit("Data / scope corrected, no step")
        run_b = self.measure()
        rc, out = self.lab.finalize(self.area)
        (line,) = [
            ln for ln in out.splitlines() if "BLOCKER" in ln and "without a step" in ln
        ]
        self.assertIn(f"run {run_b} was measured without a step", line)
        self.assertIn("Data / scope", line)
        self.assertIn("declare the step", line)
        self.assertEqual(rc, 1, out)


class TwoPatchesAtOneCommit(e2e.CountCommands):
    """Two first measurements at one commit, each with its own
    uncommitted.patch, both read back in full: in exploration neither is
    held for the other, each stands by its own text. The confirmatory twin
    keeps the split hold."""

    def setUp(self) -> None:
        super().setUp()
        self.lab.fill(self.protocol, "--force", FILTER)
        self.run_a = self.measure()
        self.lab.fill(self.protocol, "--force", UNIT)
        self.run_b = self.measure()
        for run in (self.run_a, self.run_b):
            patch = self.area / "runs" / run / "uncommitted.patch"
            self.assertTrue(patch.is_file(), run)

    def test_the_newer_stands_by_its_own_text_and_is_adopted(self):
        rc, out = self.lab.finalize(self.area)
        self.assertNotIn(SPLIT, out)
        self.assertEqual(rc, 0, out)
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, self.run_b)
        self.assertEqual(rc, 0, out)

    def test_the_older_is_held_only_by_the_text_changed_since(self):
        """A's adoption is held because the protocol now reads B's text —
        the hold of the protocol as it stands, not a split."""
        _, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertNotIn(SPLIT, out)
        self.assertIn(f"changed after the answering run {self.run_a}", out)

    def test_a_later_run_without_a_step_may_repeat_either_first_text(self):
        """Committed after both, D repeats A's text (the Unit undone): it
        reads as one of the first texts and passes."""
        self.lab.fill(self.protocol, "--force", UNIT_BEFORE)
        self.lab.commit("back to A's text")
        self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertNotIn("without a step", out)
        self.assertEqual(rc, 0, out)

    def test_a_later_run_without_a_step_may_not_bring_a_new_text(self):
        """Committed after both, D brings a text neither first measurement
        saw: an undeclared change, held — the commit does not make it
        allowed."""
        self.lab.commit("B's text committed")
        self.lab.fill(self.protocol, "--force", "Unit=one line of data/raw/docs")
        self.lab.commit("a new Unit, no step")
        run_d = self.measure()
        rc, out = self.lab.finalize(self.area)
        (line,) = [
            ln for ln in out.splitlines() if "BLOCKER" in ln and "without a step" in ln
        ]
        self.assertIn(f"run {run_d} was measured without a step", line)
        self.assertEqual(rc, 1, out)

    def test_a_step_on_either_goes_on_at_the_same_commit(self):
        self.lab.fill(
            self.protocol,
            "--builds-on",
            self.run_a,
            "--step-id",
            "unit",
            "--occasion",
            "observation",
            "--why",
            "visible documents only",
        )
        self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)


class TwoPatchesAtOneCommitConfirmatory(e2e.CountCommands):
    """The confirmatory twin: the first-measurement lock holds the split."""

    PROTOCOL_TYPE = "confirmatory"

    def test_the_split_holds(self):
        self.lab.fill(self.protocol, "--force", FILTER)
        self.measure()
        self.lab.fill(self.protocol, "--force", UNIT)
        self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertIn(SPLIT, out)
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


class ARunLost(_Exploration):
    """A run deleted before a commit held it, in exploration: what the
    answering run does not build on holds nothing where the start files put
    it after a measurement that reads; what it builds on holds. The
    confirmatory scenarios are `test_end_to_end.FirstMeasurementLost`."""

    def lose(self, run: str) -> None:
        """RUN's directory moved out of the lab, no commit holding it."""
        kept = Path(tempfile.mkdtemp()) / run
        shutil.move(str(self.area / "runs" / run), str(kept))

    def test_a_lost_side_run_does_not_hold_a_declared_step(self):
        """A reads and was first; a second run is lost; B builds on A by a
        declared step. The lost run is named and holds nothing."""
        side = self.measure()
        self.lose(side)
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)
        self.lab.commit("B filters empty documents, declared as a step on A")
        self.measure()
        rc, out, blockers = self.holds()
        self.assertEqual(blockers, [], out)
        self.assertIn(f"WARNING: run {side} is gone", out)
        self.assertIn(EXPLORING, out)
        self.assertEqual(rc, 0, out)

    def test_a_lost_run_of_the_basis_chain_holds(self):
        """The twin: C builds on B builds on A, and B is the run lost."""
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)
        self.lab.commit("B: a step on A")
        b = self.measure()
        self.lab.fill(self.protocol, "--force", UNIT)
        self.step_on(b, "unit")
        self.lab.commit("C: a step on B")
        c = self.measure()
        self.lose(b)
        rc, out, blockers = self.holds()
        line, *_ = [ln for ln in blockers if "cannot be told" in ln]
        self.assertIn(f"run {b} does not read", line)
        self.assertIn(f"reached from the answering run {c} through its steps", line)
        self.assertEqual(rc, 1, out)

    def test_a_basis_without_its_start_file_holds(self):
        """The twin: B builds on A, and A's start file is deleted before a
        commit held it."""
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)
        self.measure()
        run_starts.start_path(self.area, self.run_a).unlink()
        rc, out, blockers = self.holds()
        line, *_ = [ln for ln in blockers if "check not executable" in ln]
        self.assertIn(f"a start file was written for run {self.run_a}", line)
        self.assertEqual(rc, 1, out)


class OrderUnknown(_Exploration):
    """Runs that read and whose order no start file tells (runs from before
    start files: neither mark nor file): the order alone holds nothing in
    exploration. With a record lost as well it holds —
    `test_rules_registration_hold`, the unordered run."""

    def unmark(self, run: str) -> None:
        (self.area / "runs" / run / run_starts.START_MARK).unlink()
        run_starts.start_path(self.area, run).unlink()

    def test_a_side_run_of_unknown_order_holds_no_declared_step(self):
        side = self.measure()
        for run in (self.run_a, side):
            self.unmark(run)
        self.lab.fill(self.protocol, "--force", FILTER)
        self.step_on(self.run_a)
        self.unmark(self.measure())
        rc, out, blockers = self.holds()
        self.assertEqual(blockers, [], out)
        self.assertIn(EXPLORING, out)
        self.assertEqual(rc, 0, out)


class AStepAtHighRepeatCost(unittest.TestCase):
    """An exploratory fit at high repeat cost, preflight-audited and
    frozen, run A measured: the costly run of a step starts only while the
    preflight audit covers what the step changed. A repeat and a step that
    changes nothing the audit read start under the audit that stands; a
    step that rewrites a field the audit read owes a new one."""

    # set by the estimator scenario's setup, which this class borrows
    lab: e2e.Lab
    area: Path
    protocol: Path

    @classmethod
    def setUpClass(cls) -> None:
        e2e.Estimator.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def frozen(self) -> None:
        """The probe, the preflight audit decided, the † fields, the freeze."""
        lab = self.lab
        lab.script(self.area, "01_measure.py", "--probe", "8")
        lab.commit("the estimator, filled")
        lab.record(self.area, self.protocol, sc.PREFLIGHT_AUDIT)
        lab.exp("threshold", repeat_cost="high", report=True)
        lab.fill_open(self.protocol)
        lab.fill(self.protocol, "--freeze")
        lab.commit("frozen")

    def step_on(self, basis: str, step: str) -> None:
        self.lab.fill(
            self.protocol,
            "--builds-on",
            basis,
            "--step-id",
            step,
            "--occasion",
            "planned",
            "--why",
            "another draw of the split",
        )

    def test_the_audit_covers_a_repeat_and_an_unchanged_step_not_a_rewritten_field(
        self,
    ):
        lab = self.lab
        self.frozen()
        run_a = lab.run_id_of(lab.script(self.area, "01_measure.py"))
        # a repeat is a new run id under the same audit
        out = lab.script(self.area, "01_measure.py", "--repeat-of", run_a)
        self.assertIn(f"draw 2 of {run_a}", out)
        # a step that changes nothing the audit read
        self.step_on(run_a, "again")
        lab.commit("B: a step on A that rewrites no field")
        run_b = lab.run_id_of(lab.script(self.area, "01_measure.py"))
        # a step that rewrites what the number is about
        lab.fill(
            self.protocol, "--force", "Exclusions / filters=points with an empty text"
        )
        self.step_on(run_b, "filter")
        lab.commit("C: a step on B that rewrites the exclusions")
        with self.assertRaises(AssertionError) as cm:
            lab.script(self.area, "01_measure.py")
        refusal = str(cm.exception)
        self.assertIn("no longer covers the protocol", refusal)
        self.assertIn(
            "the registration changed after the audit (Exclusions / filters)", refusal
        )
        self.assertIn("--mode preflight", refusal)
