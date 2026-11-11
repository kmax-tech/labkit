"""Rule tests of `audit_binding`'s pure checks: each condition from typed
data in memory, its violation and its valid twin (docs/architecture.md,
"Checks and their tests"). The gate that composes them is `finalize`'s station 9
(`tests/test_finalize_open_findings.py`).
"""

from __future__ import annotations

import unittest

import pytest

from check_guards import pure_call
from labkit.checks.audit_binding import (
    UNDECIDED,
    check_audit_findings_decided,
    check_audit_records_read,
    check_audited_runs_kept,
)
from labkit.formats import findings
from labkit.formats.commands import HANDOVER, handover_command
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    KNOWN_RULE,
    NOTE,
    OPEN_RULE,
    VIOLATED,
    WARNING,
    GateFinding,
    RuleAssignment,
)
from labkit.formats.standard_contract import ANALYSIS_AUDIT, PREFLIGHT_AUDIT
from state_fixture import AREA, area_evidence, area_state, audit_record, run_dir

pytestmark = pytest.mark.rule

PROTOCOL = AREA / "PROTOCOL-x.md"
RECORD = "2026-11-10T10-00-analysis.toml"


class AnAuditedRunIsKept(unittest.TestCase):
    """LAB-043 Runs go through `runlog`: the run an analysis audit read
    stays in the area (`check_audited_runs_kept`)."""

    def test_a_record_of_a_run_the_area_no_longer_holds_blocks(self):
        state = area_state(protocols=[PROTOCOL], runs=[run_dir("r1")])
        evidence = area_evidence(
            records=[audit_record(RECORD, mode=ANALYSIS_AUDIT, run_id="r0")]
        )
        found = pure_call(check_audited_runs_kept, state, evidence=evidence)
        self.assertEqual(len(found), 1)
        (f,) = found
        self.assertEqual(
            (f.grade, f.evidence_kind, f.check_outcome), (BLOCKER, GUARANTEED, VIOLATED)
        )
        self.assertEqual(
            f.rule, RuleAssignment(KNOWN_RULE, "LAB-043", "Runs go through `runlog`")
        )
        self.assertEqual(
            f.text,
            f"{RECORD}: names r0 as the run it read, and there is no runs/r0/ in "
            f"this area — a run an audit read is a kept run (LAB-043 Runs go "
            f"through `runlog`)",
        )
        # no commit holds r0: the way out hands over or registers anew; a new
        # measurement leaves the record standing and is never offered
        assert f.fix is not None
        self.assertIn("no commit holds it", f.fix)
        self.assertIn("register anew", f.fix)
        self.assertNotIn("measure anew", f.fix)
        self.assertEqual(f.step, handover_command(PROTOCOL))
        assert f.step is not None
        self.assertEqual(f.step.name, HANDOVER)

    def test_a_gone_run_a_commit_holds_is_put_back_from_that_commit(self):
        held = "c" * 40
        state = area_state(
            protocols=[PROTOCOL], deleted=[run_dir("r0", from_commit=held)]
        )
        evidence = area_evidence(
            records=[audit_record(RECORD, mode=ANALYSIS_AUDIT, run_id="r0")]
        )
        (f,) = pure_call(check_audited_runs_kept, state, evidence=evidence)
        assert f.fix is not None
        self.assertIn(f"git checkout {held} -- runs/r0", f.fix)
        self.assertNotIn("no commit holds it", f.fix)

    def test_the_twin_a_kept_run_no_run_and_a_preflight_record_pass(self):
        state = area_state(protocols=[PROTOCOL], runs=[run_dir("r1")])
        evidence = area_evidence(
            records=[
                audit_record("a.toml", mode=ANALYSIS_AUDIT, run_id="r1"),
                audit_record("b.toml", mode=ANALYSIS_AUDIT, run_id=findings.NO_RUN),
                audit_record("c.toml", mode=PREFLIGHT_AUDIT, run_id=None),
            ]
        )
        self.assertEqual(
            pure_call(check_audited_runs_kept, state, evidence=evidence), []
        )


def _finding(grade: str, status: str = "open") -> findings.Finding:
    """An audit finding of GRADE as the auditor writes its line, STATUS as
    decided ("open": nobody decided it)."""
    return findings.Finding(
        grade,
        f"{grade} · scripts/01_measure.py:3 · statement · LAB-015 Preflight audit "
        f"before freezing · the target leaks",
        status,
        "" if status == "open" else "the leak is no leak: the column is a constant",
    )


class AnAuditRecordReads(unittest.TestCase):
    """A record nobody can read is not "no findings"
    (`check_audit_records_read`)."""

    def test_an_unreadable_record_blocks_with_its_sentence(self):
        evidence = area_evidence(unreadable=["audits/x.toml: not TOML (line 1)"])
        (f,) = pure_call(check_audit_records_read, area_state(), evidence=evidence)
        self.assertEqual(
            (f.grade, f.text), (BLOCKER, "audits/x.toml: not TOML (line 1)")
        )
        self.assertEqual(f.rule, OPEN_RULE)
        assert f.fix is not None
        self.assertIn("restore the record as labkit-audit wrote it", f.fix)

    def test_the_twin_every_record_reads(self):
        evidence = area_evidence(
            records=[audit_record("a.toml", mode=PREFLIGHT_AUDIT, run_id=None)]
        )
        self.assertEqual(
            pure_call(check_audit_records_read, area_state(), evidence=evidence), []
        )


class AnAuditFindingIsDecided(unittest.TestCase):
    """LAB-015 Preflight audit before freezing: finalize holds every finding
    nobody decided at its record's grade (`check_audit_findings_decided`)."""

    LAB_015 = RuleAssignment(KNOWN_RULE, "LAB-015", "Preflight audit before freezing")

    def _found(self, *found: findings.Finding) -> list[GateFinding]:
        evidence = area_evidence(
            records=[
                audit_record(RECORD, mode=PREFLIGHT_AUDIT, run_id=None, found=found)
            ]
        )
        return pure_call(check_audit_findings_decided, area_state(), evidence=evidence)

    def test_an_open_blocker_blocks_with_its_decision_command(self):
        (f,) = self._found(_finding(BLOCKER))
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (BLOCKER, GUARANTEED, self.LAB_015)
        )
        self.assertTrue(
            f.text.startswith(f"{RECORD}: BLOCKER · scripts/01_measure.py:3")
        )
        self.assertTrue(f.text.endswith(f" — {UNDECIDED}"))
        assert f.fix is not None
        self.assertIn("--decide", f.fix)
        self.assertIn("--findings", f.fix)

    def test_an_open_warning_warns_and_an_open_note_is_no_gate_finding(self):
        (f,) = self._found(_finding(WARNING), _finding(NOTE))
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (WARNING, GUARANTEED, self.LAB_015)
        )

    def test_the_twin_a_decided_finding_passes(self):
        self.assertEqual(self._found(_finding(BLOCKER, status="false-positive")), [])


if __name__ == "__main__":
    unittest.main()
