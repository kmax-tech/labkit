"""Terminal recovery with lost evidence: no model, approval or global bypass.

Simulated answers use the same parser as the existing whole-chain counter
cases. These tests establish mechanics, not an auditor's judgement.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest

import test_counter_cases as cases
import test_end_to_end as e2e
from labkit.formats import attempts, findings, handovers, protocol_block
from labkit.checks import report_blocks
from labkit.gates import audit, claude_hooks, report_check
from labkit.tools import protocol_fill

#: a simulated analysis answer holding one BLOCKER
BLOCKED = (
    cases.SIMULATED
    + "BLOCKER · scripts/01_measure.py:82 · unresolved source · cannot judge C1 · "
    "LAB-038 What the prompt demands · inspect source\n"
    "verdict: 1 blockers, 0 warnings, 0 notes\nscope:\nscripts/01_measure.py"
)


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

    def findings_listing(self) -> tuple[int, str]:
        """`labkit-audit AREA --findings`, its output captured."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = audit.main([str(self.area), "--findings"])
        return rc, out.getvalue()

    def report_check(self) -> tuple[int, str]:
        """`report-check AREA`, its output captured."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = report_check.main([str(self.area)])
        return rc, out.getvalue()

    @staticmethod
    def analysis_blocker(out: str) -> str:
        """report-check's one analysis-audit BLOCKER line in OUT."""
        (line,) = [
            ln for ln in out.splitlines() if ln.startswith("  BLOCKER: analysis audit:")
        ]
        return line

    def test_report_check_names_a_lost_record_and_the_restore_that_works(self):
        """report-check said "none has run yet" and named `--mode analysis`
        after an audit's record was deleted, though the journal holds the
        attempt and labkit-audit refuses every audit until the record is
        back (pilot of labkit-paper area 15, t60). The twin: an area never
        audited is told so."""
        rc, out = self.report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("none has run yet", self.analysis_blocker(out))
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        written = record.path.read_bytes()
        record.path.unlink()
        rc, out = self.report_check()
        self.assertEqual(rc, 1, out)
        line = self.analysis_blocker(out)
        self.assertNotIn("none has run yet", line)
        self.assertIn(f"ended as record in audits/{record.path.name}", line)
        self.assertIn(
            "starts no audit or review while the area's audit evidence is gone", line
        )
        self.assertIn("--findings", line)
        self.assertIn("hand over", line)
        self.assertEqual(self.audit(cases.CLEAN)[0], 2)  # refused, as it says
        # the restore it names (`attempts.restore_way`, from the evidence
        # copy: the record was never committed) brings the record back
        restore = line.split("restore it as the audit wrote it (`")[1].split("`")[0]
        subprocess.run(restore, shell=True, cwd=self.area, check=True)
        self.assertEqual(record.path.read_bytes(), written)
        rc, out = self.report_check()
        self.assertNotIn("BLOCKER: analysis audit", out)

    def test_a_covering_record_with_an_open_finding_is_decided_despite_a_loss(self):
        """The twin: deciding needs no attempt, so a loss elsewhere in the
        area does not replace the open finding's way out."""
        rc, out = self.audit(BLOCKED)
        self.assertEqual(rc, 1, out)
        (answer,) = (self.area / "audits" / "answers").iterdir()
        answer.unlink()
        self.assertTrue(attempts.evidence_gaps(self.area))
        rc, out = self.report_check()
        line = self.analysis_blocker(out)
        self.assertIn("still `open` — decide each", line)
        self.assertNotIn("audit evidence is gone", line)

    def test_after_a_lost_record_a_discussion_names_the_way_that_leads_out(self):
        """Pilot of labkit-paper area 15, t60: under a handover for a lost
        record, protocol-fill and AGENTS.md prescribed `--discuss`, which
        owes a report review; the review was refused (no attempt starts
        while evidence is gone) and the commit demanded it — no exit. Now
        every text names the route that works: restore, or the report cites
        no run of the area. The twin: with the evidence intact the
        discussion still owes its review."""
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = protocol_fill.main(
                [str(self.protocol), "--discuss", self.run_id, "--why",
                 "the adoption was refused", "--into", str(self.report)]
            )  # fmt: skip
        self.assertEqual(rc, 0, out.getvalue())
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(self.report, self.protocol)
        self.assertEqual(rc, 1, out)
        self.assertIn("--report-review", out)  # the twin: the review is owed
        # the record is lost: deleted, its evidence copy too
        record.path.unlink()
        attempts.kept_files(self.area)[record.path.name].unlink()
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(self.report, self.protocol)
        self.assertEqual(rc, 1, out)
        (line,) = [ln for ln in out.splitlines() if ln.startswith("  BLOCKER: ")]
        self.assertIn("none can run: labkit-audit starts no audit or review", line)
        self.assertIn("remove the run ids and the discussion block", line)
        self.assertIn("keep its handover block", line)
        self.assertNotIn("--report-review", line)
        review = io.StringIO()
        with contextlib.redirect_stdout(review), contextlib.redirect_stderr(review):
            rc = audit.main([str(self.area), "--report-review", str(self.report)])
        self.assertEqual(rc, 2, review.getvalue())
        self.assertIn("remove the run ids and the discussion block", review.getvalue())
        rc, out = self.lab.adopt(self.protocol, self.run_id)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("a report cannot discuss this run now", out)
        self.assertNotIn("--discuss", out.split("protocol-fill: not adopted")[1])
        # the route named leads out: the discussion block removed, the
        # handover's block stands alone and the commit passes
        text = self.report.read_text(encoding="utf-8")
        start = text.index("<!-- labkit discussed")
        end = text.index("<!-- /labkit discussed -->") + len(
            "<!-- /labkit discussed -->\n"
        )
        self.report.write_text(text[:start] + text[end:], encoding="utf-8")
        self.staged_release()

    def test_after_a_lost_record_a_citation_names_the_way_that_leads_out(self):
        """The same for the answering run cited undiscussed: its ways out,
        adoption and discussion, both owe an attempt (t60's first refusal)."""
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        self.report.write_text(f"We looked at {self.run_id}.\n", encoding="utf-8")
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(self.report, self.protocol)
        self.assertIn("--discuss", out)  # the twin: evidence intact
        record.path.unlink()
        attempts.kept_files(self.area)[record.path.name].unlink()
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(self.report, self.protocol)
        self.assertEqual(rc, 1, out)
        (line,) = [
            ln
            for ln in out.splitlines()
            if ln.startswith("  BLOCKER: ") and f"cites {self.run_id}" in ln
        ]
        self.assertIn("neither its adoption nor a discussion can pass", line)
        self.assertIn("remove the run ids", line)
        self.assertNotIn("--discuss", line)

    def test_a_loss_a_handover_recorded_names_the_restore_that_works(self):
        """It said "restore it" whether or not anything could (pilot of
        labkit-paper area 15, t60, where nothing kept the record)."""
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        self.lab.commit("the audit")
        record.path.unlink()
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        name = f"audits/{record.path.name}: lost, as a handover recorded — "
        (line,) = [g for g in attempts.evidence_gaps(self.area) if name in g]
        self.assertIn(
            f"restore it (`git checkout HEAD -- audits/{record.path.name}`)", line
        )
        # the twin: nothing keeps it — said so, no restore offered
        self.lab.commit("the handover")  # HEAD no longer holds the record
        attempts.kept_files(self.area)[record.path.name].unlink()
        (line,) = [g for g in attempts.evidence_gaps(self.area) if name in g]
        self.assertIn(f"{attempts.NOTHING_KEEPS}, and audits and adoption stay", line)
        self.assertNotIn("restore it", line)
        self.assertNotIn("until it is back", line)

    def test_findings_offer_the_handover_only_where_something_stands(self):
        # It printed the handover command in a clean area and, before its
        # own refusal, in an area never audited (audit 2026-10-27, H1).
        rc, out = self.findings_listing()
        self.assertEqual(rc, 2, out)
        self.assertIn("no audit record yet", out)
        self.assertNotIn("--handover", out)
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        rc, out = self.findings_listing()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("--handover", out)
        rc, out = self.audit(BLOCKED)
        self.assertEqual(rc, 1, out)
        rc, out = self.findings_listing()
        self.assertEqual(rc, 0, out)
        self.assertIn("1. decide it:", out)
        self.assertIn("<why it stays unresolved>", out)
        self.assertIn("2. hand over: protocol-fill", out)
        self.assertIn("1 earlier record(s) without an open finding not shown", out)

    def test_a_stop_the_handover_lets_pass_names_the_loss(self):
        # it passed in silence: "nothing wrong" instead of "loss acknowledged"
        # (audit 2026-10-27, third, K9)
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        record.path.unlink()
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.stop_hook()
        self.assertEqual(rc, 0, out)
        self.assertIn("a handover acknowledges this loss", out)
        self.assertIn(record.path.name, out)
        state = claude_hooks.undecided_state(self.lab.root, [self.protocol])
        self.assertEqual(state.blockers, [])
        self.assertEqual(len(state.acknowledged), 1)

    def test_a_handover_that_no_longer_matches_says_why(self):
        # The stop held with the original loss and named no handover, so the
        # agent wrote another (audit 2026-10-27, H2).
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        record.path.unlink()
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        (path,) = handovers.record_paths(self.area)
        rc, out = self.lab.stop_hook()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("no longer acknowledges", out)
        self.report.write_text(
            self.report.read_text().replace("- Why: ", "- Why: plainly ")
        )
        rc, out = self.lab.stop_hook()
        self.assertEqual(rc, 2, out)
        self.assertIn(f"the handover {path.name} no longer acknowledges this", out)
        self.assertIn("differs from the record", out)
        self.assertIn("--handover", out)

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
        rc, out = self.audit(BLOCKED)
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
        # Its block is part of the exact acknowledgement, including at the
        # index; prose beside the block is free.
        self.report.write_text(self.report.read_text() + "\nA sentence by hand.\n")
        self.assertTrue(handovers.valid(self.area))
        self.report.write_text(
            self.report.read_text().replace("Tried: ", "Tried: also ")
        )
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

    def test_an_existing_report_keeps_its_text_and_the_result_is_withdrawn(self):
        text = self.protocol.read_text()
        text = protocol_fill.fill_result_run(text, self.run_id)
        self.protocol.write_text(text)
        self.report.write_text("# Earlier report\n\nWhat we looked at.\n")
        with self.assertRaises(SystemExit):  # the block is written in place
            self.handover("--force")
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        self.assertTrue(
            self.report.read_text().startswith(
                "# Earlier report\n\nWhat we looked at.\n"
            )
        )
        self.assertIsNone(protocol_block.declared_run(self.protocol.read_text()))
        self.assertNotIn(self.run_id, self.report.read_text())
        self.assertTrue(handovers.valid(self.area))
        # A second handover of the same protocol replaces its block in place.
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(handovers.handover_blocks(self.report.read_text())), 1)
        self.assertTrue(handovers.valid(self.area))

    def test_a_handover_withdraws_the_earlier_report_result_block(self):
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, self.run_id)
        self.assertEqual(rc, 0, out)
        prefix = "# Earlier report\n\nAn explanation we keep.\n"
        self.report.write_text(prefix)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = protocol_fill.main([str(self.protocol), "--into", str(self.report)])
        self.assertEqual(rc, 0)
        self.assertEqual(len(report_blocks.blocks(self.report.read_text())), 1)
        self.report.write_text(self.report.read_text() + "\nA closing observation.\n")
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        text = self.report.read_text()
        self.assertEqual(report_blocks.blocks(text), [])
        self.assertTrue(text.startswith(prefix), text)
        self.assertIn("A closing observation.", text)
        self.assertNotIn(self.run_id, text)
        self.assertTrue(handovers.valid(self.area))
        self.staged_release()

    def test_other_reports_still_hold_a_withdrawn_result(self):
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, self.run_id)
        self.assertEqual(rc, 0, out)
        other_report = self.lab.root / "OTHER.md"
        for report in (self.report, other_report):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = protocol_fill.main([str(self.protocol), "--into", str(report)])
            self.assertEqual(rc, 0)
        before = other_report.read_bytes()
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        # each report still citing the withdrawn run is named with the
        # command that discusses it (workflow review 2026-10-27, TODO 8 (2))
        self.assertIn("1 report(s) still cite the withdrawn run", out)
        self.assertIn("OTHER.md: protocol-fill", out)
        self.assertIn(f"--discuss {self.run_id}", out)
        self.assertEqual(other_report.read_bytes(), before)
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(self.report, self.protocol, other_report)
        self.assertEqual(rc, 1, out)
        self.assertIn("OTHER.md", out)
        self.assertIn("it declares no result", out)

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
                rc, out = self.handover()
                self.report = previous
                self.assertEqual(rc, 2, out)
                self.assertIn("must not replace", out)
                self.assertEqual(target.read_bytes(), original)
        self.assertEqual(handovers.record_paths(self.area), [])

    def test_a_bad_record_name_does_not_hide_its_readable_blocker(self):
        rc, out = self.audit(BLOCKED)
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

    def test_an_undecodable_handover_record_is_a_sentence_in_tree_and_index(self):
        # The pre-commit raised UnicodeDecodeError on it (audit 2026-10-27, H4).
        broken = self.area / "audits" / "handovers" / "handover-broken.json"
        broken.parent.mkdir(parents=True)
        broken.write_bytes(b"\xff\xfe not json")
        self.lab.git("add", "-A")
        for staged in (False, True):
            with self.subTest(staged=staged):
                lines = claude_hooks.undecided_blockers(
                    self.lab.root, [self.protocol], staged=staged
                )
                self.assertTrue(any(broken.name in line for line in lines), lines)

    def test_an_unreadable_handover_record_hides_no_other_gap(self):
        # its HandoverError replaced every gap already found (audit
        # 2026-10-27, third, K1)
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        self.lab.commit("audited")
        record.path.unlink()
        broken = self.area / "audits" / "handovers" / "handover-broken.json"
        broken.parent.mkdir(parents=True)
        broken.write_text("{}", encoding="utf-8")
        problems = attempts.area_integrity(self.area).problems
        self.assertTrue(any(record.path.name in p for p in problems), problems)
        self.assertTrue(any(broken.name in p for p in problems), problems)

    def test_a_link_staged_in_audits_is_a_sentence_at_the_commit(self):
        # git listed it as no regular file and the pre-commit ended in a
        # traceback (audit 2026-10-27, third, K3)
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        link = self.area / "audits" / "handovers" / "handover-link.json"
        link.parent.mkdir(parents=True)
        link.symlink_to(self.protocol)
        self.lab.git("add", "-A")
        lines = claude_hooks.undecided_blockers(
            self.lab.root, [self.protocol], staged=True
        )
        self.assertTrue(any("regular, merged index file" in ln for ln in lines), lines)

    def test_a_handover_that_fails_at_the_report_names_what_it_wrote(self):
        # record and protocol were written, the report not, and the refusal
        # said nothing of them (audit 2026-10-27, third, K8)
        self.report.mkdir()  # a directory where the report goes: the write fails
        rc, out = self.handover()
        self.assertEqual(rc, 2, out)
        (path,) = handovers.record_paths(self.area)
        self.assertIn("written before it", out)
        self.assertIn(path.name, out)
        self.assertFalse(handovers.valid(self.area))

    def test_the_handover_writes_only_where_report_check_looks(self):
        # it took REPORT.MD, a file report-check never holds (audit
        # 2026-10-27, third, S3)
        root = self.lab.root.resolve()  # as git_root gives it
        with self.assertRaises(handovers.HandoverError):
            handovers.report_destination(root, root / "REPORT.MD")
        self.assertEqual(
            handovers.report_destination(root, self.report), self.report.resolve()
        )

    def test_a_staged_record_that_is_not_utf8_names_its_file(self):
        rc, out = self.audit(cases.CLEAN)
        self.assertEqual(rc, 0, out)
        (record,) = findings.area_records(self.area)
        record.path.write_bytes(b"\xff\xfe")
        self.lab.git("add", "-A")
        (error,) = findings.record_status(self.area, staged=True).errors
        self.assertIn(record.path.name, error)

    def test_two_areas_and_a_discussion_share_one_report(self):
        # Every handover went into one whole-file REPORT.md, so the second
        # area's voided the first's (audit 2026-10-27, H3).
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        other_area, other = e2e.judge_area(self.lab, "other-question")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = protocol_fill.main(
                [
                    str(other),
                    "--handover",
                    "--why",
                    "no data yet",
                    "--tried",
                    "asked for the corpus",
                    "--into",
                    str(self.report),
                ]
            )
            self.assertEqual(rc, 0, out.getvalue())
            rc = protocol_fill.main(
                [
                    str(self.protocol),
                    "--discuss",
                    self.run_id,
                    "--why",
                    "measured before the evidence was lost",
                    "--into",
                    str(self.report),
                ]
            )
        self.assertEqual(rc, 0, out.getvalue())
        self.assertEqual(len(handovers.handover_blocks(self.report.read_text())), 2)
        self.assertTrue(handovers.valid(self.area))
        self.assertTrue(handovers.valid(other_area))

    def test_the_block_names_each_unsettled_finding_by_record_and_number(self):
        rc, out = self.audit(BLOCKED)
        self.assertEqual(rc, 1, out)
        (record,) = findings.area_records(self.area)
        self.decide(record.path, "deferred", "the source cannot be read here")
        rc, out = self.handover()
        self.assertEqual(rc, 0, out)
        named = f"{record.path.name} #1 (BLOCKER, deferred)"
        self.assertIn(named, self.report.read_text())
        (path,) = handovers.record_paths(self.area)
        self.assertEqual(handovers.read_handover(path).remaining, [named])


if __name__ == "__main__":
    unittest.main()
