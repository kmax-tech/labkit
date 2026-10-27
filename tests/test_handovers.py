"""Terminal recovery with lost evidence: no model, approval or global bypass.

Simulated answers use the same parser as the existing whole-chain counter
cases. These tests establish mechanics, not an auditor's judgement.
"""

from __future__ import annotations

import contextlib
import io
import json
import unittest

import test_counter_cases as cases
import test_end_to_end as e2e
from labkit.formats import attempts, findings, handovers, protocol_block
from labkit.gates import audit, claude_hooks
from labkit.tools import protocol_fill


class HandoverRecovery(cases._Chain):
    """Each test gets a fresh, registered judge; every model is simulated."""

    @classmethod
    def setUpClass(cls) -> None:
        pass

    @classmethod
    def tearDownClass(cls) -> None:
        pass

    def setUp(self) -> None:
        self.lab = e2e.Lab()
        self.area, self.protocol = e2e.judge_area(self.lab, "judge")
        self.lab.commit("registered judge")
        self.run_id = self.run_measure(e2e.Judge._model)
        self.report = self.lab.root / "REPORT.md"

    def tearDown(self) -> None:
        self.lab.close()

    def handover(self, *extra: str) -> tuple[int, str]:
        """Run the actual handover CLI on this protocol, capturing its output."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = protocol_fill.main(
                [
                    str(self.protocol),
                    "--handover",
                    "--why",
                    "audit evidence is incomplete",
                    "--tried",
                    "checked the retained files and committed history",
                    "--into",
                    str(self.report),
                    *extra,
                ]
            )
        return rc, out.getvalue()

    def staged_release(self) -> None:
        """Both pre-commit checks, including undecided evidence, must pass."""
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(self.report, self.protocol)
        self.assertEqual(rc, 0, out)
        self.assertEqual(
            claude_hooks.undecided_blockers(
                self.lab.root,
                [self.protocol],
                staged=True,
            ),
            [],
        )

    def test_lost_record_can_be_handed_over_but_not_audited_or_adopted(self):
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        original = record.path.read_bytes()
        record.path.unlink()
        self.assertTrue(attempts.area_gaps(self.area).blockers)
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        self.assertTrue(handovers.valid(self.area))
        self.assertEqual(self.lab.stop_hook()[0], 0)
        self.staged_release()
        self.lab.commit("unresolved handover with explicit evidence loss")
        # Loss does not vanish when the handover commit becomes HEAD.
        self.assertTrue(attempts.area_gaps(self.area).blockers)
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 2, out)
        rc, out = self.lab.adopt(self.protocol, self.run_id)
        self.assertNotEqual(rc, 0, out)
        self.assertIsNone(protocol_block.declared_run(self.protocol.read_text()))
        # A new or unstaged evidence change cannot borrow that acknowledgement.
        (self.area / "audits" / "new-evidence.txt").write_text("new evidence")
        self.assertFalse(handovers.valid(self.area))
        self.assertEqual(self.lab.stop_hook()[0], 2)
        self.lab.git("add", "-A")
        self.assertTrue(
            claude_hooks.undecided_blockers(self.lab.root, [self.protocol], staged=True)
        )
        # Restoration is distinct from acknowledgement and actually repairs loss.
        record.path.write_bytes(original)
        self.lab.commit("restore the original evidence")
        self.assertEqual(attempts.area_gaps(self.area).blockers, [])

    def test_broken_journal_does_not_hide_an_older_open_blocker(self):
        rc, out = self.audit(
            cases.SIMULATED
            + "BLOCKER · scripts/01_measure.py:82 · unresolved source · cannot judge C1 · "
            "LAB-038 What the prompt demands · inspect source\n"
            "verdict: 1 blockers, 0 warnings, 0 notes\nscope:\nscripts/01_measure.py"
        )
        self.assertEqual(rc, 1, out)
        (record,) = findings.area_records(self.area)
        self.lab.record(self.area, self.protocol, "analysis", self.run_id)
        attempts.journal_path(self.area).write_text("not JSON\n")
        rc, out = self.handover()
        self.assertEqual(rc, 2, out)
        self.assertIn("open BLOCKERs", out)
        self.assertEqual(handovers.record_paths(self.area), [])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = audit.main([str(self.area), "--findings"])
        self.assertEqual(rc, 2)
        self.assertIn("audit evidence incomplete", buf.getvalue())
        self.assertIn(record.path.name, buf.getvalue())
        self.assertIn("deferred", buf.getvalue())
        self.assertIn("--handover", buf.getvalue())
        self.decide(record.path, "deferred", "unresolved; handed over without a result")
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.lab.stop_hook()[0], 0)
        self.staged_release()
        # The report is part of the exact acknowledgement, including at the index.
        self.report.write_text(self.report.read_text() + "changed\n")
        self.assertFalse(handovers.valid(self.area))
        self.assertTrue(handovers.valid(self.area, staged=True))
        self.lab.git("add", "-A")
        self.assertFalse(handovers.valid(self.area, staged=True))
        self.assertTrue(
            claude_hooks.undecided_blockers(self.lab.root, [self.protocol], staged=True)
        )

    def test_binary_journal_is_preserved_and_only_terminal_handover_passes(self):
        attempts.journal_path(self.area).parent.mkdir(exist_ok=True)
        broken = b"\xff\xfe\n"
        attempts.journal_path(self.area).write_bytes(broken)
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        self.assertEqual(attempts.journal_path(self.area).read_bytes(), broken)
        self.assertEqual(self.lab.stop_hook()[0], 0)
        self.staged_release()
        with self.assertRaises(attempts.AttemptError):
            attempts.area_gaps(self.area)
        # A later readable open finding is never waived by a handover.
        self.lab.record(self.area, self.protocol, "analysis", self.run_id)
        self.assertFalse(handovers.valid(self.area))
        self.assertEqual(self.lab.stop_hook()[0], 2)

    def test_existing_report_requires_explicit_force_and_result_is_withdrawn(self):
        text = self.protocol.read_text()
        text = protocol_fill.fill_result_run(text, self.run_id, force=True)
        self.protocol.write_text(text)
        self.report.write_text("# Earlier report\n")
        rc, out = self.handover()
        self.assertEqual(rc, 2, out)
        self.assertIn("--force", out)
        self.assertEqual(self.report.read_text(), "# Earlier report\n")
        self.assertEqual(self.protocol.read_text(), text)
        rc, out = self.handover("--force")
        self.assertEqual(rc, 0, out)
        self.assertIsNone(protocol_block.declared_run(self.protocol.read_text()))
        self.assertNotIn(self.run_id, self.report.read_text())
        self.assertTrue(handovers.valid(self.area))

    def test_malformed_record_never_grants_permission(self):
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        (path,) = handovers.record_paths(self.area)
        data = json.loads(path.read_text())
        data["schema"] = True
        path.write_text(json.dumps(data))
        self.assertFalse(handovers.valid(self.area))
        with self.assertRaises(handovers.HandoverError):
            handovers.read_handover(path)

    def test_handover_cannot_overwrite_evidence_or_another_protocol(self):
        answer = self.area / "audits" / "answers" / "retained.md"
        answer.parent.mkdir(parents=True)
        answer.write_text("retained answer")
        _, other = e2e.judge_area(self.lab, "other-question")
        for target in (answer, other):
            with self.subTest(target=target):
                original = target.read_bytes()
                previous = self.report
                self.report = target
                rc, out = self.handover("--force")
                self.report = previous
                self.assertEqual(rc, 2, out)
                self.assertIn("must not replace", out)
                self.assertEqual(target.read_bytes(), original)
        self.assertEqual(handovers.record_paths(self.area), [])

    def test_a_bad_record_name_does_not_hide_its_readable_blocker(self):
        rc, out = self.audit(
            cases.SIMULATED
            + "BLOCKER · scripts/01_measure.py:82 · unresolved source · cannot judge C1 · "
            "LAB-038 What the prompt demands · inspect source\n"
            "verdict: 1 blockers, 0 warnings, 0 notes\nscope:\nscripts/01_measure.py"
        )
        self.assertEqual(rc, 1, out)
        (record,) = findings.area_records(self.area)
        renamed = record.path.with_name("renamed-analysis.toml")
        record.path.rename(renamed)
        status = findings.record_status(self.area)
        self.assertTrue(status.errors)
        self.assertEqual(len(findings.open_findings(status.records)), 1)
        rc, out = self.handover()
        self.assertEqual(rc, 2, out)
        self.assertIn("open BLOCKERs", out)
        self.assertEqual(handovers.record_paths(self.area), [])

    def test_a_staged_handover_cannot_leave_new_audit_evidence_unstaged(self):
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        record.path.unlink()
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        self.staged_release()
        self.lab.record(self.area, self.protocol, "analysis", self.run_id)
        self.assertTrue(findings.record_status(self.area, staged=True).errors)
        self.assertFalse(handovers.valid(self.area, staged=True))
        self.assertTrue(
            claude_hooks.undecided_blockers(
                self.lab.root,
                [self.protocol],
                staged=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
