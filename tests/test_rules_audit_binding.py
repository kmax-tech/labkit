"""Rule tests of `audit_binding`'s pure checks: each condition from typed
data in memory, its violation and its valid twin (docs/notes/2026-11-10-test-model.md,
"The model"). The gate that composes them is `finalize`'s station 9
(`tests/test_finalize_open_findings.py`).
"""

from __future__ import annotations

import unittest

import pytest

from check_guards import pure_call
from labkit.checks.audit_binding import check_audited_runs_kept
from labkit.formats import findings
from labkit.formats.commands import HANDOVER, handover_command
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    KNOWN_RULE,
    VIOLATED,
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


if __name__ == "__main__":
    unittest.main()
