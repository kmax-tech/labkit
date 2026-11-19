"""Gate tests of finalize's station 2 (`registration_station`): which
workflow it reads from the first measurements' own type
(`registration_hold.workflow`) and which holds follow, and that the
follow-up audit's prompt compares a corrected field with the text the hold
compares (`registration_hold.run_compared_with`, read by
`registration_station.check_registration` and `audit_prompt._field_change`).

The fixture is a repository with a protocol committed twice and one run
recorded at each commit, written as runlog writes them
(`protocol_fixture.completed_run`); no command runs. The decision itself,
from types in memory: tests/test_rules_registration_hold.py,
`WorkflowRegistered`. The route through the commands:
tests/test_exploration_hold.py.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import PID, completed_run, head, scope_file
from repo_fixture import git as _git

from labkit.formats import findings
from labkit.formats.area_state import Measured
from labkit.formats.gate import BLOCKER
from labkit.formats.protocol_history import Workflow
from labkit.gates import (
    audit_prompt,
    registration_hold,
    registration_station,
    report_context,
)

FIRST_LOCK = "what the number is about changed after the first measurement"
LIVE_HOLD = "what the number is about changed after the answering run"
FIRST = "2026-10-07T09-25-31_98dd"
LATER = "2026-10-07T10-00-00_ab12"
UNDECIDED_TYPE = "<exploratory | confirmatory>"


class _TwoRuns(unittest.TestCase):
    """A repository whose protocol is committed once per run: FIRST under
    one text, LATER under another. A base without tests of its own."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        _git(self.root, "init", "-q")
        self.area = self.root / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)
        self.protocol = self.area / "PROTOCOL-x.md"

    def write(
        self, protocol_type: str, scope: str, *, result: str | None = None
    ) -> None:
        """The protocol of PROTOCOL_TYPE whose Data / scope is SCOPE,
        declaring RESULT as its run when given."""
        self.protocol.write_text(
            head(repeat_cost="low", type=protocol_type, result=result)
            + "- **Question / hypothesis:** does it hold?\n"
            + f"- **Data / scope:** {scope}\n",
            encoding="utf-8",
        )

    def run_under(self, protocol_type: str, scope: str, name: str) -> Path:
        """Run NAME, recorded at the commit of the protocol written with
        PROTOCOL_TYPE and SCOPE."""
        self.write(protocol_type, scope)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        commit = _git(self.root, "rev-parse", "HEAD")
        run = completed_run(self.area, name, metrics={"criterion_1_pass": True})
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["git"], data["git_full"] = commit[:7], commit
        cfg.write_text(json.dumps(data), encoding="utf-8")
        return run

    def station(self) -> tuple[Workflow, list[str], report_context.Checked]:
        """(workflow, hold lines, the context) of station 2 on the
        answering run the context chooses."""
        ctx = report_context.checked(self.area, self.protocol)
        assert ctx.run is not None
        flow, holds = registration_station.station_changes(
            ctx.area, ctx.protocol, PID, ctx.run, ctx.area_state, ctx.evidence
        )
        return flow, [h.line for h in holds], ctx


class WorkflowOfTheFirstMeasurement(_TwoRuns):
    """The station returns the workflow by name, one value per case, and
    holds an undecided one the confirmatory way."""

    def test_an_undecided_first_type_holds_the_confirmatory_way(self):
        """A first measurement whose type was the stamp's placeholder (a
        run an earlier labkit let start): no workflow can be read from it,
        so the first-measurement lock applies, and naming the type
        exploratory afterwards is a type change."""
        self.run_under(UNDECIDED_TYPE, "4 documents", FIRST)
        later = self.run_under("exploratory", "2 documents", LATER)
        flow, lines, ctx = self.station()
        self.assertEqual(ctx.run, later)
        self.assertIs(flow, Workflow.UNDECIDED)
        self.assertTrue(any('"undecided" → "exploratory"' in ln for ln in lines), lines)
        self.assertTrue(any(FIRST_LOCK in ln for ln in lines), lines)

    def test_a_confirmatory_first_type_keeps_the_first_measurement_lock(self):
        self.run_under("confirmatory", "4 documents", FIRST)
        self.run_under("confirmatory", "2 documents", LATER)
        flow, lines, _ = self.station()
        self.assertIs(flow, Workflow.CONFIRMATORY)
        self.assertTrue(any(FIRST_LOCK in ln for ln in lines), lines)

    def test_an_exploratory_first_type_holds_each_run_by_its_own_text(self):
        self.run_under("exploratory", "4 documents", FIRST)
        self.run_under("exploratory", "2 documents", LATER)
        flow, lines, _ = self.station()
        self.assertIs(flow, Workflow.EXPLORATORY)
        self.assertFalse(any(FIRST_LOCK in ln for ln in lines), lines)
        self.assertTrue(any("was measured without a step" in ln for ln in lines), lines)

    def test_without_a_stamped_id_no_workflow_is_told_and_nothing_held(self):
        later = self.run_under("exploratory", "4 documents", LATER)
        ctx = report_context.checked(self.area, self.protocol)
        self.assertEqual(
            registration_station.station_changes(
                ctx.area, ctx.protocol, None, later, ctx.area_state, ctx.evidence
            ),
            (Workflow.UNDECIDED, []),
        )


class TheWorkflowReadOfAProtocol(_TwoRuns):
    """`registration_hold.workflow` over what the area measured, given in
    memory: what leaves the first measurement untold decides before any
    text is read."""

    CONFLICT = "run r1: its record names p-1, the run index p-2"

    def read(self, measured: Measured) -> registration_hold.WorkflowRead:
        self.write("exploratory", "4 documents")
        return registration_hold.workflow(
            self.area, self.protocol, PID, self.root, measured
        )

    def test_a_contradicted_binding_leaves_the_workflow_undecided(self):
        read = self.read(
            Measured(self.area, PID, (), (), (), (), conflicts=(self.CONFLICT,))
        )
        self.assertIs(read.workflow, Workflow.UNDECIDED)
        (hold,) = read.untold
        self.assertEqual(hold.grade, BLOCKER)
        self.assertIn(self.CONFLICT, hold.line)
        self.assertEqual(read.seen, [])

    def test_the_twin_nothing_measured_is_undecided_without_a_hold(self):
        read = self.read(Measured(self.area, PID, (), (), (), ()))
        self.assertEqual(
            (read.workflow, read.untold, read.seen), (Workflow.UNDECIDED, [], [])
        )


class PromptAndHoldCompareTheSameText(_TwoRuns):
    """FIRST measured "4 documents", LATER "2 documents", and the protocol
    as it stands says "3 documents" and adopts LATER. The follow-up audit
    is shown the corrected field against the text the hold compares the
    protocol with."""

    #: a correction of Data / scope, as an audit records it
    CORRECTION = findings.Finding(
        "WARNING",
        "WARNING · PROTOCOL-x.md:Data / scope · statement · Data / scope says 2 · "
        "the denominator · LAB-050 Analysis audit before reporting · correct it",
        "fixed",
        "corrected as the audit asked",
    )

    def measured_twice(self, protocol_type: str) -> Path:
        """Both runs under PROTOCOL_TYPE and the corrected text; LATER's path."""
        self.run_under(protocol_type, "4 documents", FIRST)
        later = self.run_under(protocol_type, "2 documents", LATER)
        self.write(protocol_type, "3 documents", result=LATER)
        return later

    def shown(self, run: Path | None) -> audit_prompt.FieldChange:
        """The change of Data / scope the follow-up shows, RUN audited."""
        text = self.protocol.read_text(encoding="utf-8")
        return audit_prompt._field_change(self.protocol, text, self.CORRECTION, run)

    def test_in_exploration_both_compare_with_the_answering_runs_own_text(self):
        later = self.measured_twice("exploratory")
        flow, lines, ctx = self.station()
        self.assertEqual(ctx.run, later)
        self.assertIs(flow, Workflow.EXPLORATORY)
        held = [ln for ln in lines if LIVE_HOLD in ln]
        self.assertEqual(len(held), 1, lines)
        self.assertIn('Data / scope "2 documents" → "3 documents"', held[0])
        change = self.shown(later)
        self.assertEqual(
            (change.registered, change.now), ("2 documents", "3 documents")
        )
        self.assertIn(f"the run audited {LATER}", change.where)

    def test_in_confirmation_both_compare_with_the_first_measurement(self):
        later = self.measured_twice("confirmatory")
        flow, lines, _ = self.station()
        self.assertIs(flow, Workflow.CONFIRMATORY)
        held = [ln for ln in lines if FIRST_LOCK in ln]
        self.assertTrue(held, lines)
        self.assertTrue(all('Data / scope "4 documents"' in ln for ln in held), held)
        change = self.shown(later)
        self.assertEqual(change.registered, "4 documents")
        self.assertIn(f"first measurement {FIRST}", change.where)

    def test_an_undecided_first_type_is_shown_against_the_first_measurement(self):
        """The prompt reads the station's decision, not the head as it
        stands: named exploratory after an undecided first measurement,
        the field is still shown against the first measurement's text."""
        self.run_under(UNDECIDED_TYPE, "4 documents", FIRST)
        later = self.run_under("exploratory", "2 documents", LATER)
        self.write("exploratory", "3 documents", result=LATER)
        flow, _, _ = self.station()
        self.assertIs(flow, Workflow.UNDECIDED)
        self.assertEqual(self.shown(later).registered, "4 documents")

    def test_without_a_run_only_the_prompt_compares_and_names_the_first(self):
        """The one case where the two part, kept as it was: with no run
        audited an exploration has no run's own text, so the follow-up
        shows the field against the first measurement's — and no hold
        compares anything, since station 2 runs only with an answering
        run (`registration_hold.run_compared_with`)."""
        self.measured_twice("exploratory")
        change = self.shown(None)
        self.assertEqual(change.registered, "4 documents")
        self.assertIn(f"first measurement {FIRST}", change.where)
        ctx = report_context.checked(self.area, self.protocol)
        self.assertEqual(
            registration_hold.corrected_in_place(
                ctx.area,
                ctx.protocol,
                PID,
                None,
                ctx.area_state,
                ctx.evidence,
                flow=Workflow.EXPLORATORY,
            ),
            [],
        )
