"""Gate tests of finalize's station 2 (`registration_station`): which
workflow it reads from the first measurements' own type
(`registration_hold.workflow`) and which holds follow, and that the
follow-up audit's prompt compares a corrected field with the text the hold
compares (`registration_hold.run_compared_with`, read by
`registration_station.check_registration` and `audit_prompt._field_change`)
— and that an untold first measurement, which leaves the station with its
one hold, does not exchange the text of the run audited in that prompt.

The fixture is a repository with a protocol committed twice and one run
recorded at each commit, written as runlog writes them
(`protocol_fixture.completed_run`); no command runs. The decision itself,
from types in memory: tests/test_rules_registration_hold.py,
`WorkflowRegistered`. The route through the commands:
tests/test_exploration_hold.py.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import PID, completed_run, head, scope_file
from repo_fixture import git as _git
from state_fixture import audit_record

from labkit.formats import findings, followup
from labkit.formats.area_state import Measured
from labkit.formats.gate import BLOCKER
from labkit.formats.protocol_history import Workflow
from labkit.gates import (
    audit_prompt,
    registration_hold,
    registration_station,
    report_context,
)
from labkit.run import runlog

FIRST_LOCK = "what the number is about changed after the first measurement"
LIVE_HOLD = "what the number is about changed after the answering run"
FIRST = "2026-10-07T09-25-31_98dd"
LATER = "2026-10-07T10-00-00_ab12"
#: a run id before FIRST's, for a measurement that is lost
LOST = "2026-10-06T08-00-00_0c0c"
UNDECIDED_TYPE = "<exploratory | confirmatory>"
#: the Data / scope values of the prompt tests
FOUR, THREE, TWO = "4 documents", "3 documents", "2 documents"


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
            self.area, self.protocol, PID, self.root, measured, history_unread=""
        )

    def test_a_contradicted_binding_leaves_the_workflow_undecided(self):
        read = self.read(
            Measured(self.area, PID, (), (), (), (), conflict_clauses=(self.CONFLICT,))
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
        self.run_under(protocol_type, FOUR, FIRST)
        later = self.run_under(protocol_type, TWO, LATER)
        self.write(protocol_type, THREE, result=LATER)
        return later

    def shown(self, run: Path | None) -> audit_prompt.FieldChange:
        """The change of Data / scope the follow-up shows, RUN audited."""
        text = self.protocol.read_text(encoding="utf-8")
        return audit_prompt._field_change(self.protocol, text, self.CORRECTION, run)

    def printed(self, change: audit_prompt.FieldChange) -> list[str]:
        """The lines the follow-up prints for CHANGE, as the piece holds
        them under the correction's entry."""
        record = audit_record(
            "r.toml", mode="analysis", run_id=LATER, found=[self.CORRECTION]
        )
        member = followup.Member(record, 1, self.CORRECTION)
        shown = audit_prompt.Followup([member], None, {}, {member.ref: change})
        ((_, text),) = audit_prompt.earlier_piece(shown)
        lines = text.split("\n")
        start = next(i for i, ln in enumerate(lines) if ln.startswith("  decided:"))
        return [ln.removeprefix("  ") for ln in lines[start + 1 :]]

    def test_in_exploration_both_compare_with_the_answering_runs_own_text(self):
        """The twin of the confirmatory case: the change is taken against
        the own text of the run audited, as the hold compares; the first
        registration is printed under its own name, as context."""
        later = self.measured_twice("exploratory")
        flow, lines, ctx = self.station()
        self.assertEqual(ctx.run, later)
        self.assertIs(flow, Workflow.EXPLORATORY)
        held = [ln for ln in lines if LIVE_HOLD in ln]
        self.assertEqual(len(held), 1, lines)
        self.assertIn('Data / scope "2 documents" → "3 documents"', held[0])
        change = self.shown(later)
        assert change.run_audited is not None and change.first_measured is not None
        self.assertEqual((change.run_audited.value, change.now), (TWO, THREE))
        self.assertIn(f"the run audited {LATER}", change.run_audited.where)
        self.assertEqual(change.first_measured.value, FOUR)
        self.assertTrue(change.compared_with_run_audited)
        first, own, now, judged = self.printed(change)
        self.assertTrue(
            first.startswith(
                f"Data / scope as first registered (as its first measurement {FIRST} "
            ),
            first,
        )
        self.assertTrue(first.endswith(f"): {FOUR}"), first)
        self.assertTrue(own.endswith(f"): {TWO}"), own)
        self.assertEqual(now, f"Data / scope now: {THREE}")
        self.assertTrue(
            judged.startswith(
                "change to judge: from the value in the audited run's own text "
                "to the value now"
            ),
            judged,
        )

    def test_in_confirmation_both_compare_with_the_first_measurement(self):
        """Confirmatory, first measurement told, a run audited: the first
        registration is the benchmark, and the audited run's own text
        stands beside it under its own name."""
        later = self.measured_twice("confirmatory")
        flow, lines, _ = self.station()
        self.assertIs(flow, Workflow.CONFIRMATORY)
        held = [ln for ln in lines if FIRST_LOCK in ln]
        self.assertTrue(held, lines)
        self.assertTrue(all('Data / scope "4 documents"' in ln for ln in held), held)
        change = self.shown(later)
        assert change.run_audited is not None and change.first_measured is not None
        self.assertEqual(change.first_measured.value, FOUR)
        self.assertIn(f"first measurement {FIRST}", change.first_measured.where)
        self.assertEqual(change.run_audited.value, TWO)
        self.assertIn(f"the run audited {LATER}", change.run_audited.where)
        self.assertEqual(change.first_untold, "")
        self.assertFalse(change.compared_with_run_audited)
        first, own, now, judged = self.printed(change)
        self.assertTrue(
            first.startswith(
                f"Data / scope as first registered (as its first measurement {FIRST} "
            ),
            first,
        )
        self.assertTrue(first.endswith(f"): {FOUR}"), first)
        self.assertTrue(
            own.startswith(
                f"Data / scope in the audited run's own text (as the run audited "
                f"{LATER} "
            ),
            own,
        )
        self.assertTrue(own.endswith(f"): {TWO}"), own)
        self.assertEqual(now, f"Data / scope now: {THREE}")
        self.assertTrue(
            judged.startswith(
                "change to judge: from the value as first registered to the value now"
            ),
            judged,
        )

    def test_a_change_after_the_first_registration_shows_though_the_run_saw_it(
        self,
    ):
        """The case the benchmark protects: the field was changed after
        the first registration and the run audited already saw the new
        value. Against that run's own text nothing changed; against the
        first registration the change is there, and that is the one to
        judge. Both lines are printed though two of the values are equal."""
        self.run_under("confirmatory", FOUR, FIRST)
        later = self.run_under("confirmatory", THREE, LATER)
        self.write("confirmatory", THREE, result=LATER)
        change = self.shown(later)
        assert change.run_audited is not None and change.first_measured is not None
        self.assertEqual(
            (change.first_measured.value, change.run_audited.value, change.now),
            (FOUR, THREE, THREE),
        )
        self.assertFalse(change.compared_with_run_audited)
        first, own, now, judged = self.printed(change)
        self.assertTrue(first.endswith(f"): {FOUR}"), first)
        self.assertIn("as first registered", first)
        self.assertTrue(own.endswith(f"): {THREE}"), own)
        self.assertIn("in the audited run's own text", own)
        self.assertEqual(now, f"Data / scope now: {THREE}")
        self.assertIn("from the value as first registered", judged)

    def test_an_audited_run_whose_text_cannot_be_read_back_says_so(self):
        """The run audited recorded another promise block than its commit
        gives: its line says that its text cannot be read back, with the
        reason, and no other text stands in; the first registration is
        shown as before."""
        later = self.measured_twice("confirmatory")
        cfg = later / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["promises"]["block_sha"] = "0" * 12
        cfg.write_text(json.dumps(data), encoding="utf-8")
        change = self.shown(later)
        assert change.run_audited is not None and change.first_measured is not None
        self.assertIsNone(change.run_audited.value)
        self.assertEqual(change.first_measured.value, FOUR)
        first, own, now, _ = self.printed(change)
        self.assertTrue(first.endswith(f"): {FOUR}"), first)
        self.assertTrue(
            own.startswith(
                f"Data / scope in the audited run's own text: cannot be read back — "
                f"the run audited {LATER} "
            ),
            own,
        )
        self.assertIn("recorded block 000000000000", own)
        self.assertNotIn(FOUR, own)
        self.assertEqual(now, f"Data / scope now: {THREE}")

    def test_an_undecided_first_type_is_shown_against_the_first_measurement(self):
        """The prompt reads the station's decision, not the head as it
        stands: named exploratory after an undecided first measurement,
        the change is still taken against the first measurement's text."""
        self.run_under(UNDECIDED_TYPE, FOUR, FIRST)
        later = self.run_under("exploratory", TWO, LATER)
        self.write("exploratory", THREE, result=LATER)
        flow, _, _ = self.station()
        self.assertIs(flow, Workflow.UNDECIDED)
        change = self.shown(later)
        assert change.first_measured is not None
        self.assertEqual(change.first_measured.value, FOUR)
        self.assertFalse(change.compared_with_run_audited)

    def lose_a_possible_first(self) -> None:
        """A measurement only the run index lists: measured, indexed and
        deleted before any commit held it, with no start file to tell its
        order — it may have been the first, so the first measurement is
        untold (`registration_hold.lost_record_hold`)."""
        lost = completed_run(self.area, LOST, metrics={"criterion_1_pass": True})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runlog.reindex(self.area), 0)
        shutil.rmtree(lost)

    def assert_first_only_as_evidence(self, lines: list[str]) -> None:
        """LINES say that the first registration is undetermined, and show
        FIRST's value only under the evidence name, FIRST named as a run."""
        self.assertTrue(
            lines[0].startswith("first registration: undetermined — "), lines[0]
        )
        self.assertIn("may have been the first measurement", lines[0])
        self.assertIn(
            "Which workflow binds this protocol's runs is undetermined", lines[0]
        )
        # no verdict is prescribed, and none stands in for the evidence
        self.assertTrue(
            lines[0].endswith(audit_prompt.NOT_ASSESSABLE_WITHOUT_FIRST), lines[0]
        )
        self.assertIn("cannot be assessed from this evidence", lines[0])
        self.assertIn("does not lift the hold on the release", lines[0])
        self.assertTrue(
            lines[1].startswith(
                f"Data / scope in the first measurement whose text can be read back "
                f"— evidence, not "
                f"established as the first registration (as run {FIRST} saw it ("
            ),
            lines[1],
        )
        self.assertTrue(lines[1].endswith(f"): {FOUR}"), lines[1])
        text = "\n".join(lines)
        self.assertNotIn("as first registered", text)
        self.assertNotIn(f"first measurement {FIRST}", text)
        self.assertEqual(text.count(FOUR), 1, text)

    def test_an_untold_first_keeps_the_audited_runs_own_text(self):
        """An exploration whose first measurement is untold: the station
        returns the one hold and no workflow — and the follow-up still
        takes the change against the own text of the run audited, says
        what is missing, and shows the first measurement that reads only
        as evidence."""
        later = self.measured_twice("exploratory")
        self.lose_a_possible_first()
        flow, lines, ctx = self.station()
        self.assertEqual(ctx.run, later)
        self.assertIs(flow, Workflow.UNDECIDED)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn(f"{LOST}", lines[0])
        self.assertIn("may have been the first measurement", lines[0])
        change = self.shown(later)
        assert change.run_audited is not None
        self.assertEqual((change.run_audited.value, change.now), (TWO, THREE))
        self.assertIn(f"the run audited {LATER}", change.run_audited.where)
        self.assertIn("may have been the first measurement", change.first_untold)
        self.assertIn(LOST, change.first_untold)
        self.assertTrue(change.compared_with_run_audited)
        printed = self.printed(change)
        self.assert_first_only_as_evidence(printed)
        _, _, own, now, judged = printed
        self.assertTrue(
            own.startswith(
                f"Data / scope in the audited run's own text (as the run audited "
                f"{LATER} saw"
            ),
            own,
        )
        self.assertTrue(own.endswith(f"): {TWO}"), own)
        self.assertEqual(now, f"Data / scope now: {THREE}")
        self.assertIn("from the value in the audited run's own text", judged)

    def test_the_twin_an_untold_first_in_confirmation_shows_evidence_only(self):
        """The twin: the same loss in a confirmatory protocol. The change
        is taken against the first registration, which is undetermined;
        the first measurement that reads appears as evidence, never as
        the registration, and the audited run keeps its own line."""
        later = self.measured_twice("confirmatory")
        self.lose_a_possible_first()
        flow, lines, _ = self.station()
        self.assertIs(flow, Workflow.UNDECIDED)
        self.assertEqual(len(lines), 1, lines)
        change = self.shown(later)
        assert change.run_audited is not None and change.first_measured is not None
        self.assertEqual(change.first_measured.value, FOUR)
        self.assertEqual(change.run_audited.value, TWO)
        self.assertIn("may have been the first measurement", change.first_untold)
        self.assertFalse(change.compared_with_run_audited)
        printed = self.printed(change)
        self.assert_first_only_as_evidence(printed)
        _, _, own, now, judged = printed
        self.assertTrue(own.endswith(f"): {TWO}"), own)
        self.assertEqual(now, f"Data / scope now: {THREE}")
        self.assertTrue(
            judged.startswith(
                "change to judge: from the first registration to the value now — "
                "and the first registration is undetermined"
            ),
            judged,
        )

    def test_without_a_run_an_untold_first_is_undetermined_too(self):
        """No run audited and the first measurement untold: the same
        labelling — undetermined, the text that reads as evidence — and
        no line of a run audited."""
        self.measured_twice("confirmatory")
        self.lose_a_possible_first()
        change = self.shown(None)
        self.assertIsNone(change.run_audited)
        self.assertIn(LOST, change.first_untold)
        printed = self.printed(change)
        self.assert_first_only_as_evidence(printed)
        self.assertEqual(len(printed), 4, printed)
        self.assertNotIn("audited run's own text", "\n".join(printed))

    def test_a_told_first_names_nothing_missing(self):
        later = self.measured_twice("exploratory")
        change = self.shown(later)
        self.assertEqual(change.first_untold, "")
        text = "\n".join(self.printed(change))
        self.assertNotIn("undetermined", text)
        self.assertNotIn(audit_prompt.NOT_ASSESSABLE_WITHOUT_FIRST, text)

    def test_without_a_run_only_the_prompt_compares_and_names_the_first(self):
        """The one case where the two part: with no run audited an
        exploration has no run's own text, so the follow-up takes the
        change against the first measurement's — and no hold compares
        anything, since station 2 runs only with an answering run
        (`registration_hold.run_compared_with`)."""
        self.measured_twice("exploratory")
        change = self.shown(None)
        assert change.first_measured is not None
        self.assertEqual(change.first_measured.value, FOUR)
        self.assertIn(f"first measurement {FIRST}", change.first_measured.where)
        self.assertIsNone(change.run_audited)
        self.assertFalse(change.compared_with_run_audited)
        first, now, judged = self.printed(change)
        self.assertIn("as first registered", first)
        self.assertEqual(
            judged,
            "change to judge: from the value as first registered to the value now",
        )
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


class TheLinesOfAFieldChange(unittest.TestCase):
    """`audit_prompt.field_change_lines` from a change in memory: what no
    repository state above reaches."""

    def test_no_measurement_listed_and_the_first_untold_shows_no_first_text(self):
        """A contradicted binding with no measurement listed: nothing is
        printed in the place of the first registration but that it is
        undetermined."""
        change = audit_prompt.FieldChange(
            "Unit", None, None, "ms", "run r1: its record names p-1", False
        )
        self.assertEqual(
            audit_prompt.field_change_lines(change),
            [
                "first registration: undetermined — run r1: its record names p-1. "
                "Which workflow binds this protocol's runs is undetermined too. "
                "No value below is established as the first registration. "
                "Whether the first registration was kept cannot be assessed from "
                "this evidence. A verdict does not replace the missing evidence "
                "and does not lift the hold on the release. Judge what the "
                "evidence shown does support",
                "Unit now: ms",
                "change to judge: from the first registration to the value now — "
                "and the first registration is undetermined: no value shown here "
                "is that benchmark, and a value marked as evidence does not stand "
                "in for it",
            ],
        )

    def test_a_first_registration_that_cannot_be_read_back_says_so(self):
        change = audit_prompt.FieldChange(
            "Unit",
            audit_prompt.ValueThen(None, "its first measurement r1 recorded no commit"),
            None,
            "ms",
            "",
            False,
        )
        self.assertEqual(
            audit_prompt.field_change_lines(change)[0],
            "Unit as first registered: cannot be read back — its first "
            "measurement r1 recorded no commit",
        )
