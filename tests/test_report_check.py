"""report-check: the last gate at every repeat cost — frozen (high repeat cost
only), finalize clean and named, the answering run a full run, an analysis
audit of code, promises and that run as they are now, `02_analyze.py
--check` passing.

The cloud judge probe (2026-10-14, draw 3) skipped the analysis audit, the
check and the note, and finalize was green; finalize cannot ask for what
follows the analysis audit, so the end has its own gate. Until 0.99.0 the
gate exited 0 at `repeat_cost = "low"`, so a probe's number passed there as a
reported one (TODO 1, 2026-10-19). Each station is tested where it lives
(findings.audit_coverage, recheck.holds, finalize); here: what is owed when,
that every station blocks on its own, and `--if-reported` — the gate the
stop hook and the pre-commit run — holds exactly the protocols whose answer
cites a run.
"""

from __future__ import annotations

from labkit.formats.runs import RunKind
from labkit.tools import protocol_fill

import contextlib
import dataclasses
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from protocol_fixture import (
    registration_of,
    C1_BLOCK,
    C1_PROSE,
    completed_run,
    head,
    scope_file,
    started_at,
    shown_sha,
)

from labkit.formats import findings, handovers, promises, scope_sha, standard_contract
from labkit.gates import report_check


class ReportCheck(unittest.TestCase):
    def _area(self, repeat_cost: str = "high", frozen: bool = True) -> Path:
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        (area / "scripts" / "02_analyze.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        scope_file(area)
        (area / "PROTOCOL-x.md").write_text(
            head(
                repeat_cost=repeat_cost,
                frozen=frozen,
                preflight_audit="n/a — test",
                promises=C1_BLOCK,
            )
            + C1_PROSE,
            encoding="utf-8",
        )
        return area

    def _answered(self, area: Path, name: str = "2026-01-01T00-00-00_0001") -> Path:
        """The completed run bound to the fixture's protocol that answers it."""
        return completed_run(area, name, metrics={"criterion_1_pass": True})

    def _audited(self, area: Path, run: Path | None = None) -> None:
        """A decided analysis record of the area's code, promises and RUN
        (the answering run when none is named)."""
        run = run or self._answered(area)
        sha = scope_sha.area_stamp(area)[0]
        block = promises.block_stamp(
            (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        )
        findings.write(
            area,
            "analysis",
            "opus",
            sha,
            block,
            (0, 0, 0),
            [],
            run_id=run.name,
            shown_sha=shown_sha(area, run),
            registration=registration_of(area),
        )

    def _run(
        self,
        area: Path,
        finalize: int = 0,
        check: str | None = None,
        fields: bool = False,
    ) -> tuple[int, str]:
        """FINALIZE and CHECK stand in for their stations; the fixture's
        protocol is a bare head, so its field gaps count only with FIELDS."""
        out = io.StringIO()
        no_gaps = SimpleNamespace(missing_must=[], must_holes=[])

        def fake_finalize(area_: Path, protocol: Path | None, collected) -> int:
            if finalize:  # finalize keeps every reason it has as a blocker
                collected.block(
                    f"stub blocker (finalize exit {finalize})", fix="stub way out"
                )
            return finalize

        with (
            contextlib.nullcontext()
            if fields
            else mock.patch.object(report_check, "check_fields", return_value=no_gaps),
            mock.patch.object(report_check, "finalize_area", fake_finalize),
            mock.patch.object(
                report_check, "check_analysis_script", return_value=check
            ),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.report_check(area)
        return code, out.getvalue()

    def test_the_twin_every_station_holds_is_clean(self):
        area = self._area()
        self._audited(area)
        code, out = self._run(area)
        self.assertEqual(code, 0, out)
        self.assertIn("all clear", out)

    def _asked(self, area: Path, question: str) -> Path:
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        proto.write_text(
            text + f"- **Question / hypothesis:** {question}\n", encoding="utf-8"
        )
        return proto

    def test_a_question_rewritten_after_the_audit_is_refused(self):
        """The analysis audit judged one question; the protocol now asks
        another, and report-check passed it with the old audit (review
        2026-10-23, finding 1). The refusal names the field."""
        area = self._area()
        proto = self._asked(area, "what is the mean line count per case?")
        self._audited(area)
        self.assertEqual(self._run(area)[0], 0)
        proto.write_text(
            proto.read_text(encoding="utf-8").replace(
                "the mean line count", "the mean number of causal claims"
            ),
            encoding="utf-8",
        )
        code, out = self._run(area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "the registration changed after the audit (Question / hypothesis)", out
        )

    def test_report_fields_written_after_the_audit_leave_it_standing(self):
        """The twin: the conclusion, the limits and a reflowed question are
        no new registration — writing the report owes no new audit."""
        area = self._area()
        proto = self._asked(area, "what is the mean line count per case?")
        self._audited(area)
        proto.write_text(
            proto.read_text(encoding="utf-8").replace(
                "mean line count per", "mean line count\n  per"
            )
            + "- **Conclusion:** the cases hold eleven lines on average.\n"
            + "- **Limitations:** one corpus only.\n",
            encoding="utf-8",
        )
        code, out = self._run(area)
        self.assertEqual(code, 0, out)

    def test_the_context_is_built_once_and_names_what_it_holds(self):
        """One text, one head, one answering run, one named file state for
        every station (`checked`): the declaration is read from the text
        the caller hands over, the run is chosen once through
        `audit_binding.audited_run`, and the output says which state was held."""
        area = self._area(repeat_cost="low", frozen=False)
        run = self._answered(area)
        proto = area / "PROTOCOL-x.md"
        ctx = report_check.checked(area, proto)
        self.assertEqual(
            (ctx.state, ctx.declared, ctx.run), (report_check.TREE, None, run)
        )
        self.assertEqual(ctx.text, proto.read_text(encoding="utf-8"))
        # the index's text, not the tree's: the declaration comes from there
        staged = protocol_fill.fill_result_run(ctx.text, run.name)
        ctx = report_check.checked(area, proto, state=report_check.INDEX, text=staged)
        self.assertEqual((ctx.state, ctx.declared), (report_check.INDEX, run.name))
        self.assertEqual(ctx.head.repeat_cost, "low")
        self._audited(area, run)
        code, out = self._run(area)
        self.assertEqual(code, 0, out)
        self.assertIn(
            f"read from the working tree; the head has adopted no run; the answering "
            f"run is {run.name}",
            out,
        )

    def test_without_an_answering_run_the_context_says_why(self):
        area = self._area()
        ctx = report_check.checked(area, area / "PROTOCOL-x.md")
        self.assertIsNone(ctx.run)
        self.assertIn("no completed run bound to", ctx.why)
        code, out = self._run(area)
        self.assertEqual(code, 1)
        self.assertIn(f"the answering run is none — {ctx.why}", out)

    def test_a_freeze_with_a_must_gap_blocks(self):
        """Frozen with the stamp's `<…>` promise sentences: the flag is set,
        the freeze registers nothing (cloud judge probe, draw 4)."""
        area = self._area()
        self._audited(area)
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        start = text.index('sentence = "') + len('sentence = "')
        end = text.index('"', start)
        proto.write_text(
            text[:start] + "<the criterion in one sentence>" + text[end:],
            encoding="utf-8",
        )
        code, out = self._run(area, fields=True)
        self.assertEqual(code, 1, out)
        self.assertIn("still carries the stamp's", out)

    def test_a_must_field_still_a_placeholder_blocks(self):
        """Station 1 read `missing_must` only: a must field holding its
        stamped `<…>` passed the last gate while protocol-check and preflight
        refused it (audit 2026-10-15)."""
        area = self._area()
        self._audited(area)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            "- **Unit:** <the counted unit>\n\n" + proto.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        code, out = self._run(area, fields=True)
        self.assertEqual(code, 1, out)
        self.assertIn("Unit still a placeholder", out)

    def test_low_owes_no_freeze_and_everything_after_it(self):
        """The twin at low repeat cost: unfrozen, no preflight audit, and clean — a
        full run, the analysis record of it, the check."""
        area = self._area(repeat_cost="low", frozen=False)
        self._audited(area)
        code, out = self._run(area)
        self.assertEqual(code, 0, out)
        self.assertIn("no freeze and no preflight audit owed", out)
        self.assertIn("finalized, audited, checked", out)
        self.assertNotIn("frozen,", out)

    def test_at_low_a_probes_number_is_refused(self):
        """Third haiku round: t3 and t5 reported a probe's number; at low repeat cost
        the gate said "nothing owed here"."""
        area = self._area(repeat_cost="low", frozen=False)
        run = self._answered(area)
        completed_run(
            area, run.name, metrics={"criterion_1_pass": True}, run_kind="probe"
        )
        self._audited(area, run)
        code, out = self._run(area)
        self.assertEqual(code, 1, out)
        self.assertIn("a probe (run_kind='probe'), not a measurement", out)
        self.assertIn("owes a full run (run_kind='measurement')", out)
        self.assertNotIn("on a frozen protocol", out)  # none is owed at low repeat cost

    def test_at_low_an_acknowledged_run_is_refused(self):
        area = self._area(repeat_cost="low", frozen=False)
        run = self._answered(area)
        completed_run(
            area, run.name, metrics={"criterion_1_pass": True}, unfrozen_ack=True
        )
        self._audited(area, run)
        code, out = self._run(area)
        self.assertEqual(code, 1, out)
        self.assertIn("acknowledged over an unfrozen protocol", out)

    def test_at_low_the_analysis_audit_and_finalize_are_owed(self):
        area = self._area(repeat_cost="low", frozen=False)
        self._answered(area)
        code, out = self._run(area, finalize=1)
        self.assertEqual(code, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)
        self.assertIn("finalize", out)
        # the lane's one audit, at the promotion: its rule, not the long lane's
        self.assertIn("(LAB-017 The number of audits follows the cost tier)", out)
        self.assertNotIn("LAB-050", out)

    def test_finalize_blockers_are_named_not_pointed_at(self):
        """Inside the stop hook "run it to see them" was a round trip the
        agent did not take: finalize's blockers stand in report-check's list."""
        area = self._area(repeat_cost="low", frozen=False)  # no run at all
        out = io.StringIO()
        with (
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.report_check(area)
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn("BLOCKER: finalize: no completed run bound to", out.getvalue())
        self.assertNotIn("run it to see", out.getvalue())

    def test_finalize_exiting_without_a_blocker_is_a_bug_not_a_hint(self):
        """Until the 2026-10-23 audit a non-zero finalize without a blocker
        became "run it to see why" — the round trip again. finalize keeps
        every reason as a blocker now; a bare exit is a bug and says so."""
        area = self._area(repeat_cost="low", frozen=False)
        with (
            mock.patch.object(report_check, "finalize_area", return_value=2),
            self.assertRaises(RuntimeError) as caught,
        ):
            report_check.finalize_gaps(area, area / "PROTOCOL-x.md")
        self.assertIn("kept no blocker", str(caught.exception))

    def test_finalize_findings_arrive_as_data_not_through_stdout(self):
        """finalize runs on a silent collector: its blockers reach this gate
        as findings, its headers and notes reach nothing, and stdout is never
        redirected for it (until 0.100.0 it was, and the blockers were read
        back from the collector while the output was thrown away)."""
        area = self._area(repeat_cost="low", frozen=False)
        out = io.StringIO()
        seen: dict[str, object] = {}

        def fake_finalize(area_: Path, protocol: Path | None, collected) -> int:
            seen["stdout_untouched"] = sys.stdout is out  # this test's, no other
            seen["silent"] = collected._tell is None
            collected.note("── completion ──")
            collected.block("no completed run bound to p-x", fix="measure: `x`")
            return collected.report("finalize", "reporting")

        with (
            mock.patch.object(report_check, "finalize_area", fake_finalize),
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.report_check(area)
        self.assertEqual(code, 1, out.getvalue())
        self.assertEqual(seen, {"stdout_untouched": True, "silent": True})
        # the nested gate's way out reaches the line (TODO 3.2: nested gates)
        self.assertIn(
            "BLOCKER: finalize: no completed run bound to p-x — way out: measure: `x`",
            out.getvalue(),
        )
        self.assertNotIn("── completion ──", out.getvalue())
        self.assertNotIn("finalize: 1 blocker", out.getvalue())

    def test_each_station_blocks_on_its_own(self):
        area = self._area(frozen=False)
        code, out = self._run(area, finalize=1, check="02_analyze.py --check exits 1")
        self.assertEqual(code, 1)
        for needle in (
            "not `frozen = true`",
            "finalize",
            "analysis audit: no answering run to hold it to",
            "--check exits 1",
        ):
            self.assertIn(needle, out)
        self.assertIn("4 blocker(s)", out)

    def test_no_analysis_record_of_the_answering_run_blocks(self):
        area = self._area()
        self._answered(area)
        code, out = self._run(area)
        self.assertEqual(code, 1)
        self.assertIn("no analysis audit saw the area as it is now", out)
        self.assertIn("(LAB-050 Analysis audit before reporting)", out)

    def test_an_analysis_audit_of_an_earlier_run_or_other_promises_blocks(self):
        """Same code, a later answering run: until 0.97.1 the old record
        held, since it named the code only (review 2026-10-18). The twin:
        a record of the newest run is clean. Then a promise sentence edited
        after the audit."""
        area = self._area()
        self._audited(area)  # of the first run
        later = self._answered(area, "2026-01-02T00-00-00_0002")
        code, out = self._run(area)
        self.assertEqual(code, 1, out)
        self.assertIn(f"run {later.name}, shown ", out)
        self._audited(area, later)
        code, out = self._run(area)
        self.assertEqual(code, 0, out)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            proto.read_text(encoding="utf-8").replace(
                "the criterion holds", "the criterion holds twice"
            ),
            encoding="utf-8",
        )
        code, out = self._run(area)
        self.assertEqual(code, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)

    def test_the_same_run_with_other_metrics_or_rows_than_audited_blocks(self):
        """The record named the run id only, so a metrics.json or output rows
        changed after the audit still read as audited (review 2026-10-20).
        The twin: the audited run as it was is clean."""
        area = self._area()
        run = self._answered(area)
        self._audited(area, run)
        code, out = self._run(area)
        self.assertEqual(code, 0, out)
        metrics = run / "metrics.json"
        metrics.write_text(metrics.read_text(encoding="utf-8").replace("true", "false"))
        code, out = self._run(area)
        self.assertEqual(code, 1, out)
        self.assertIn(f"run {run.name}, shown ", out)
        self.assertIn("no analysis audit saw the area as it is now", out)

    def test_an_analysis_audit_of_older_code_blocks(self):
        area = self._area()
        self._audited(area)
        (area / "scripts" / "02_analyze.py").write_text(
            "print('changed')\n", encoding="utf-8"
        )
        code, out = self._run(area)
        self.assertEqual(code, 1)
        self.assertIn("a change after the audit owes a new one", out)

    def test_the_check_runs_the_areas_script(self):
        area = self._area()
        repo = area.parent.parent
        self.assertIsNone(report_check.check_analysis_script(area, repo))
        (area / "scripts" / "02_analyze.py").write_text(
            "import sys\nprint('recheck: numbers not in PROTOCOL')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        failed = report_check.check_analysis_script(area, repo) or ""
        self.assertIn("exits 1", failed)
        self.assertIn("numbers not in PROTOCOL", failed)

    def test_the_check_is_one_command_at_every_tier(self):
        """The counting skeleton carried its check inside `01_measure.py` and
        stamped no analysis script; station 4 asked for `02_analyze.py` and
        refused every correct count (audit 2026-10-19). Now every skeleton
        stamps `02_analyze.py` (`standard_contract.CHECK_SCRIPT`), and the
        station names the one it is missing — at low repeat cost as at high."""
        for cost in ("low", "high"):
            with self.subTest(cost):
                area = self._area(repeat_cost=cost, frozen=cost != "low")
                repo = area.parent.parent
                self.assertIsNone(report_check.check_analysis_script(area, repo))
                (area / "scripts" / "02_analyze.py").unlink()
                (area / "scripts" / "01_measure.py").write_text(
                    "print('ok')\n", encoding="utf-8"
                )
                failed = report_check.check_analysis_script(area, repo) or ""
                self.assertIn("no scripts/02_analyze.py —", failed)
                self.assertIn("analyze-quick-script.py.template", failed)

    def test_the_gate_reads_the_lanes_audit_and_freeze_obligations(self):
        """Analysis is owed where the lane's `audits` name the analysis
        audit — every lane of the standard does; a lane without it (built
        here, not in the contract) owes no record, and reportability names the
        freeze only where the lane owes it (review 2026-10-19: the release
        read only `freeze` off the contract)."""
        area = self._area(repeat_cost="low", frozen=False)
        run = self._answered(area)
        completed_run(
            area, run.name, metrics={"criterion_1_pass": True}, run_kind="probe"
        )
        low = standard_contract.lane("low")
        with mock.patch.object(report_check, "lane", return_value=low):
            code, out = self._run(area)
            self.assertEqual(code, 1, out)
            self.assertIn("analysis audit:", out)
            self.assertNotIn("on a frozen protocol", out)
            without = dataclasses.replace(low, audits=(), freeze=True)
        with (
            mock.patch.object(report_check, "lane", return_value=without),
            mock.patch.object(report_check, "review_findings") as decisions,
        ):
            code, out = self._run(area)
            self.assertEqual(code, 1, out)
            self.assertNotIn("analysis audit:", out)
            self.assertIn("on a frozen protocol", out)
            decisions.assert_not_called()

    def test_a_check_printing_bytes_no_codec_reads_is_a_named_gap(self):
        """`protocol-fill --from-run` ran this inside `adopt`; a
        UnicodeDecodeError left the unchecked answer in the protocol
        (audit 2026-10-19)."""
        area = self._area()
        (area / "scripts" / "02_analyze.py").write_text(
            "import sys\nsys.stderr.buffer.write(b'bad \\xff byte\\n')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        failed = report_check.check_analysis_script(area, area.parent.parent)
        self.assertIn("exits 1: bad \ufffd byte", failed or "")


class IfReported(unittest.TestCase):
    """`report-check --if-reported`: the gate at the stop and the commit (it
    was `finalize --if-reported` until 0.99.0). A number written back into
    "Recorded results" is held to the whole chain; a protocol whose
    answer is still open owes nothing — an exploration ends with no reported
    result, probes in `runs/` or not (TODO 2, 2026-10-19)."""

    RUN = "2026-10-07T10-00-00_ab12"

    def _area(
        self,
        answer: str,
        *,
        declared: str | None = None,
        run_kind: RunKind = "measurement",
        audited: bool = True,
        git: bool = False,
        report: str | None = None,
    ) -> Path:
        """A low-lane area (no freeze owed, so the bare fixture head passes
        station 1) whose protocol says ANSWER and declares DECLARED as its
        result (the head's `[result] run`; None: an exploration); its one
        run a full run unless LONG says a probe; an analysis record of it
        when AUDITED. GIT: the
        root is a repository (before the record: the stamp's paths are
        repo-relative) and everything is committed at the end. REPORT: the
        head's registered report file (`report = "…"`)."""
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        if git:
            self._git(area.parent.parent, "init", "-q", ".")
            self._git(area.parent.parent, "config", "user.email", "t@t")
            self._git(area.parent.parent, "config", "user.name", "t")
        (area / "scripts" / "02_analyze.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        scope_file(area)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            head(repeat_cost="low", result=declared, promises=C1_BLOCK, report=report)
            + "- **Question / hypothesis:** does it hold?\n"
            + C1_PROSE
            + f"- **Recorded results:** {answer}\n",
            encoding="utf-8",
        )
        if git:
            # the registration committed before the run, as the lane owes it
            self._git(area.parent.parent, "add", "-A")
            self._git(area.parent.parent, "commit", "-qm", "registration")
        run = completed_run(
            area, self.RUN, metrics={"criterion_1_pass": True}, run_kind=run_kind
        )
        if git:
            started_at(run, area.parent.parent)
        # at low repeat cost finalize holds the provenance: the source frozen in the run
        src = area / "data.jsonl"
        src.write_text('{"id": 1}\n', encoding="utf-8")
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["data"] = {"cases": {"path": str(src), "sha": "x", "rows": 1}}
        cfg.write_text(json.dumps(data), encoding="utf-8")
        if audited:
            findings.write(
                area,
                "analysis",
                "opus",
                scope_sha.area_stamp(area)[0],
                promises.block_stamp(proto.read_text(encoding="utf-8")),
                (0, 0, 0),
                [],
                run_id=run.name,
                shown_sha=shown_sha(area, run),
                registration=registration_of(area),
            )
        if git:
            self._git(area.parent.parent, "add", "-A")
            self._git(area.parent.parent, "commit", "-qm", "init")
        return area

    @staticmethod
    def _git(cwd: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)

    def _staged_gate(self, root: Path, *paths: Path) -> tuple[int, str]:
        """The pre-commit's form of the gate over PATHS in the repo ROOT."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = report_check.if_reported(list(paths), root, staged=True)
        return code, buf.getvalue()

    def test_staged_reads_the_answer_as_the_index_holds_it(self):
        """The pre-commit's form: a reported answer in the index, the tree's
        reopened — the hook read the tree and passed the commit (audit
        2026-10-19)."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=self.RUN, git=True
        )
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        code, out = self._staged_gate(root, proto)
        self.assertEqual(code, 0, out)  # the twin: tree is index, all holds
        self.assertIn("finalized, audited, checked", out)
        reported = proto.read_text(encoding="utf-8")
        proto.write_text(
            reported.replace(f'\n[result]\nrun = "{self.RUN}"\n', ""),
            encoding="utf-8",
        )  # reopened: the declaration gone, the tree differs from the index
        code, out = self._staged_gate(root, proto)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "the working tree differs from the index (experiments/01-x/PROTOCOL-x.md)",
            out,
        )
        # the twin's twin: the index open, the answer only in the tree —
        # the commit declares nothing, the gate is silent
        self._git(root, "add", "-A")
        proto.write_text(reported, encoding="utf-8")
        code, out = self._staged_gate(root, proto)
        self.assertEqual((code, out), (0, ""))

    def test_staged_names_the_index_as_the_state_held(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=self.RUN, git=True
        )
        code, out = self._staged_gate(area.parent.parent, area / "PROTOCOL-x.md")
        self.assertEqual(code, 0, out)
        self.assertIn("read from the index; the head has adopted " + self.RUN, out)

    def test_staged_refuses_an_area_whose_tree_is_not_the_index(self):
        """A script modified and one untracked under a reported number: the
        stations would judge a state the commit does not hold."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=self.RUN, git=True
        )
        root = area.parent.parent
        (area / "scripts" / "02_analyze.py").write_text(
            "print('changed')\n", encoding="utf-8"
        )
        (area / "scripts" / "new.py").write_text("x = 1\n", encoding="utf-8")
        code, out = self._staged_gate(root, area / "PROTOCOL-x.md")
        self.assertEqual(code, 1, out)
        self.assertIn(
            "(experiments/01-x/scripts/02_analyze.py, experiments/01-x/scripts/new.py)",
            out,
        )
        self.assertNotIn("analysis audit", out)  # no station ran

    def test_staged_finds_a_protocol_deleted_only_in_the_tree(self):
        """The script staged, the reported protocol deleted in the tree and
        not in the index: the commit keeps the protocol, so the gate holds
        it — the search for protocols read the tree and found none."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=self.RUN, git=True
        )
        root = area.parent.parent
        script = area / "scripts" / "02_analyze.py"
        script.write_text("print('changed')\n", encoding="utf-8")
        self._git(root, "add", "-A")
        (area / "PROTOCOL-x.md").unlink()
        code, out = self._staged_gate(root, script)
        self.assertEqual(code, 1, out)
        self.assertIn("report-check", out)
        self.assertIn("the working tree differs from the index", out)

    def test_an_adoption_written_but_not_staged_is_named_as_such(self):
        """Task 34 of the pressure pilot (2026-10-29): `--from-run` wrote the
        declaration into the tree, the commit staged the report and not the
        protocol, and the hook said "declares no result"; the agent took it
        for a rejected review's effect and withdrew. The hold now names the
        unstaged protocol and `git add`; staged, that line is gone (the twin).
        """
        area = self._area("criterion-1 met", git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        prose = text[text.index("- **Question") :]
        proto.write_text(
            head(repeat_cost="low", result=self.RUN, promises=C1_BLOCK) + prose,
            encoding="utf-8",
        )
        report = root / "REPORT.md"
        report.write_text(f"# Report\n\nRun ID: {self.RUN}\n", encoding="utf-8")
        self._git(root, "add", "REPORT.md")
        code, out = self._staged_gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("adopts it in the working tree but not in the index", out)
        self.assertIn("`git add experiments/01-x/PROTOCOL-x.md`", out)
        self.assertNotIn("which has adopted no result", out)
        self._git(root, "add", "experiments/01-x/PROTOCOL-x.md")
        code, out = self._staged_gate(root, report)
        self.assertNotIn("not in the index", out)
        self.assertNotIn("which has adopted no result", out)

    def test_a_shared_helper_reopens_the_areas_that_import_it(self):
        """lib/scoring.py lies in no area; an area whose script imports it is
        touched by its change, and one that does not is not."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})",
            declared=self.RUN,
            git=False,
        )
        root = area.parent.parent
        (root / "lib").mkdir()
        helper = root / "lib" / "scoring.py"
        helper.write_text("T = 1\n", encoding="utf-8")
        (area / "scripts" / "01_measure.py").write_text(
            "from lib import scoring\n", encoding="utf-8"
        )
        other = root / "experiments" / "02-y"
        (other / "scripts").mkdir(parents=True)
        (other / "PROTOCOL-y.md").write_text(head(), encoding="utf-8")
        (other / "scripts" / "01_measure.py").write_text("x = 1\n")
        self.assertEqual(
            report_check.affected_protocols([helper], root),
            [area.resolve() / "PROTOCOL-x.md"],
        )
        helper.unlink()  # a deleted helper is still one the area rests on
        self.assertEqual(
            report_check.affected_protocols([helper], root),
            [area.resolve() / "PROTOCOL-x.md"],
        )

    def test_the_cli_takes_staged(self):
        with mock.patch.object(report_check, "if_reported", return_value=0) as gate:
            report_check.main(["--if-reported", "--staged", "a/PROTOCOL-x.md"])
        gate.assert_called_once_with([Path("a/PROTOCOL-x.md")], mock.ANY, staged=True)
        with mock.patch.object(report_check, "if_reported", return_value=0) as gate:
            report_check.main(["--if-reported", "a/PROTOCOL-x.md"])
        gate.assert_called_once_with([Path("a/PROTOCOL-x.md")], mock.ANY, staged=False)

    def _gate(self, area: Path, *paths: Path) -> tuple[int, str]:
        """The gate over PATHS — the protocol itself when none are named."""
        buf = io.StringIO()
        paths = paths or (area / "PROTOCOL-x.md",)
        with contextlib.redirect_stdout(buf):
            code = report_check.main(["--if-reported", *map(str, paths)])
        return code, buf.getvalue()

    def test_a_changed_script_reopens_the_areas_reported_number(self):
        """The protocol untouched, a script under it edited: the analysis
        audit saw other code, and both hooks passed it (audit 2026-10-19)."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=self.RUN
        )
        script = area / "scripts" / "02_analyze.py"
        code, out = self._gate(area, script)
        self.assertEqual(code, 0, out)  # the twin: unchanged, the gate holds
        script.write_text("print('changed')\n", encoding="utf-8")
        code, out = self._gate(area, script)
        self.assertEqual(code, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)
        # a path under no area, and a path in another area, owe nothing here
        code, out = self._gate(area, area.parent.parent / "README.md")
        self.assertEqual((code, out), (0, ""))

    def test_an_open_answer_owes_nothing_even_over_a_probe(self):
        """The exploration: a probe in runs/, the answer still the stamp's."""
        code, out = self._gate(
            self._area("<number + run_id>", run_kind="probe", audited=False)
        )
        self.assertEqual((code, out), (0, ""))

    def test_an_answer_without_a_declaration_is_not_one(self):
        """Neither reported nor open: protocol-check warns, this gate is silent."""
        code, out = self._gate(self._area("AUC 0.91", audited=False))
        self.assertEqual((code, out), (0, ""))

    def test_a_declaration_that_does_not_read_is_held_and_blocks(self):
        """A typed `…_final` in [result]: no exploration to skip, a blocker
        naming the table — the commit must not carry it."""
        area = self._area("AUC 0.91")
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            proto.read_text(encoding="utf-8").replace(
                'preflight_audit = ""\n',
                'preflight_audit = ""\n\n[result]\nrun = "2026-10-01T09-00-00_final"\n',
            ),
            encoding="utf-8",
        )
        code, out = self._gate(area)
        self.assertEqual(code, 1, out)
        self.assertIn("a result that does not read", out)
        self.assertIn("no run id runlog writes", out)

    def test_a_reported_full_run_passes(self):
        code, out = self._gate(
            self._area(
                f"criterion-1 met · recorded: (run {self.RUN})", declared=self.RUN
            )
        )
        self.assertEqual(code, 0, out)
        self.assertIn(f"its head has adopted {self.RUN}", out)
        self.assertIn("finalized, audited, checked", out)

    def test_a_reported_probe_is_refused(self):
        """Third haiku round, t3 and t5: the probe's number, written back."""
        code, out = self._gate(
            self._area(
                f"criterion-1 met · recorded: (run {self.RUN})",
                declared=self.RUN,
                run_kind="probe",
            )
        )
        self.assertEqual(code, 1, out)
        self.assertIn("a probe (run_kind='probe'), not a measurement", out)

    def test_citing_another_run_than_the_one_that_answers_blocks(self):
        other = "2026-10-01T09-00-00_ffff"
        code, out = self._gate(
            self._area(f"criterion_1_pass = True (run {other})", declared=other)
        )
        self.assertEqual(code, 1, out)
        self.assertIn("finalize: ", out)
        self.assertIn("but the run that answers is", out)

    def test_a_reported_run_without_its_analysis_audit_blocks(self):
        code, out = self._gate(
            self._area(
                f"criterion-1 met · recorded: (run {self.RUN})",
                declared=self.RUN,
                audited=False,
            )
        )
        self.assertEqual(code, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)


if __name__ == "__main__":
    unittest.main()


class RegisteredReport(unittest.TestCase):
    """The registered report owes its result (Max, 2026-10-29): a protocol
    whose head says `report = "REPORT.md"` holds that file, once it is
    delivered, to the result block of the declared run or the protocol's
    handover block — at the stop, the commit and the plain call. In the
    pressure pilot of that day three of six agents deleted the run id
    from REPORT.md after the hook refused the citation, and the commit
    passed: a number without a run id was outside the gate."""

    RUN = IfReported.RUN
    _git = staticmethod(IfReported._git)
    _fixture = IfReported._area  # the low-lane area, as ReportFiles reuses it
    P = "experiments/01-x/PROTOCOL-x.md"

    def _area(
        self,
        declared: str | None = None,
        *,
        report: str | None = "REPORT.md",
        git: bool = False,
    ) -> Path:
        return self._fixture(
            f"criterion-1 met · recorded: (run {self.RUN})",
            declared=declared,
            git=git,
            report=report,
        )

    def _gate(self, root: Path, *paths: Path, staged: bool = False) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = report_check.if_reported(list(paths), root, staged=staged)
        return code, buf.getvalue()

    OWED = "carries neither"
    WAYS = ("--into", "--discuss", "--handover")

    def test_a_registered_report_without_its_block_is_held_with_the_three_ways_out(
        self,
    ):
        """The delivered state of tasks 34, 15 and 60: a number, no run id.
        Held when the report is among the paths (it lies in no area) and
        when the protocol is; the plain call's station holds it too."""
        area = self._area(git=True)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text("# Report\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        for path in (report, area / "PROTOCOL-x.md"):
            with self.subTest(path=path.name):
                code, out = self._gate(root, path)
                self.assertEqual(code, 1, out)
                self.assertIn(
                    "/REPORT.md carries "
                    "neither a result block (the head has adopted no result) nor "
                    "the protocol's handover block — a registered report owes "
                    "the result or an explicit end without one; a number with "
                    "its run id removed, or a run id typed in, releases nothing",
                    out,
                )
                self.assertIn("PROTOCOL-x.md registers ", out)
                self.assertIn(
                    f"--from-run {self.RUN}` adopts the run (the newest kept one), then `",
                    out,
                )
                self.assertIn(f"--discuss {self.RUN} --why", out)
                self.assertIn(
                    "releases nothing — the report then still owes the result or the handover",
                    out,
                )
                self.assertIn("--handover --why", out)
                self.assertIn("ends the protocol without a result", out)
                self.assertIn(
                    "its head has adopted no result; its registered report is delivered",
                    out,
                )
        ctx = report_check.checked(area, area / "PROTOCOL-x.md")
        (gap,) = report_check.report_findings(ctx)
        self.assertEqual(gap.grade, "BLOCKER")
        self.assertIn(self.OWED, gap.text)

    def test_the_adoption_is_not_held_against_itself(self):
        """Route probe, 2026-10-29: with the registered REPORT.md already in
        the tree (no block yet), `--from-run` ran this check on the proposed
        protocol and was refused for the block only `--into` can write after
        it; `--into` was refused for the missing declaration; the hook for
        both. The adoption's own check (PROPOSED) does not hold the report;
        the tree and the index do (the twin)."""
        area = self._area(git=True)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text("# Report\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        declared = (
            head(repeat_cost="low", result=self.RUN, promises=C1_BLOCK)
            + text[text.index("- **Question") :]
        )
        ctx = report_check.checked(
            area, proto, state=report_check.PROPOSED, text=declared
        )
        self.assertEqual(report_check.report_findings(ctx), [])
        ctx = report_check.checked(area, proto)
        (gap,) = report_check.report_findings(ctx)
        self.assertIn(self.OWED, gap.text)

    def test_the_twin_the_result_block_of_the_declared_run_passes(self):
        area = self._area(declared=self.RUN, git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        report = root / "REPORT.md"
        new, _ = protocol_fill.into_report(
            proto.read_text(encoding="utf-8"), area, "# Report\n\n", self.P
        )
        report.write_text(new, encoding="utf-8")
        for path in (report, proto):
            with self.subTest(path=path.name):
                code, out = self._gate(root, path)
                self.assertEqual(code, 0, out)
                self.assertNotIn(self.OWED, out)
        self.assertEqual(
            report_check.report_findings(report_check.checked(area, proto)), []
        )
        # a block showing another run than the head declares is no release;
        # with a result declared the way out is `--into` alone
        report.write_text(
            new.replace(self.RUN, "2026-10-07T11-00-00_cd34"), encoding="utf-8"
        )
        code, out = self._gate(root, proto)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"neither the result block of run {self.RUN}, its adopted result", out
        )
        line = next(ln for ln in out.splitlines() if "registers " in ln)
        self.assertIn("way out: `protocol-fill ", line)
        self.assertIn("--into ", line)
        self.assertNotIn("--from-run", line.split("--discuss")[0])

    def test_the_twin_the_handover_block_passes_and_a_typed_one_does_not(self):
        area = self._area(git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        report = root / "REPORT.md"
        report.write_text("# Report\n\nno result\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = protocol_fill.main(
                [
                    str(proto),
                    "--handover",
                    "--why",
                    "the audit found what the data cannot answer",
                    "--tried",
                    "two runs",
                    "--into",
                    str(report),
                ]
            )
        self.assertEqual(rc, 0, buf.getvalue())
        for path in (report, proto):
            with self.subTest(path=path.name):
                code, out = self._gate(root, path)
                self.assertEqual(code, 0, out)
                self.assertNotIn(self.OWED, out)
        self._git(root, "add", "-A")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        # a block typed by hand names no record that reads: held, saying so
        typed = "\n".join(
            [
                "# Report",
                "",
                handovers.OPEN,
                f'protocol = "{self.P}"',
                'record = "experiments/01-x/audits/handovers/handover-00.json"',
                "-->",
                "Unresolved: handed over.",
                handovers.CLOSE,
                "",
            ]
        )
        report.write_text(typed, encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(self.OWED, out)
        self.assertIn("its handover block at line 3 names no record that reads", out)

    def test_a_discussion_block_alone_is_held(self):
        area = self._area()
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        report = root / "REPORT.md"
        report.write_text(
            protocol_fill.discuss_into(
                proto.read_text(encoding="utf-8"),
                area,
                "# Report\n\n",
                self.P,
                self.RUN,
                "looked at, not adopted",
            ),
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(self.OWED, out)

    def test_a_typed_run_id_without_the_block_is_held(self):
        area = self._area()
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            f"# Report\n\nmean = 0.69 (run {self.RUN})\n", encoding="utf-8"
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(self.OWED, out)
        self.assertIn("a run id typed in, releases nothing", out)

    def test_a_protocol_without_report_and_a_second_file_hold_nothing(self):
        """The obligation is the registered file's alone: a protocol that
        registers none holds REPORT.md to nothing new, and a note beside a
        registered report owes nothing; a registered report not yet
        written owes nothing either — the obligation is on what is
        delivered."""
        area = self._area(report=None)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text("# Report\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        code, out = self._gate(root, report, area / "PROTOCOL-x.md")
        self.assertEqual(code, 0, out)
        self.assertNotIn("registers", out)
        area = self._area()
        root = area.parent.parent
        code, out = self._gate(root, area / "PROTOCOL-x.md")
        self.assertEqual(code, 0, out)  # REPORT.md not written yet
        note = root / "notes" / "x.md"
        note.parent.mkdir()
        note.write_text("# Notes\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        code, out = self._gate(root, note)
        self.assertEqual(code, 0, out)
        self.assertNotIn("registers", out)

    def test_staged_reads_the_report_as_the_index_holds_it(self):
        """The commit holds the index: a REPORT.md only in the tree is not
        delivered by the commit; staged without its block it is held."""
        area = self._area(git=True)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text("# Report\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn(self.OWED, out)


if __name__ == "__main__":
    unittest.main()
