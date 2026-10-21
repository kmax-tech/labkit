"""report-check: the last gate at every cost tier — frozen (minutes/hours
only), finalize clean and named, the answering run a full run, an analysis
audit of code, promises and that run as they are now, `02_analyze.py
--check` passing.

The cloud judge probe (2026-10-14, draw 3) skipped the analysis audit, the
check and the note, and finalize was green; finalize cannot ask for what
follows the analysis audit, so the end has its own gate. Until 0.99.0 the
gate exited 0 at `cost = "seconds"`, so a probe's number passed there as a
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

from protocol_fixture import completed_run, head, scope_file

from labkit.formats import findings, promises, scope_sha, standard_contract
from labkit.gates import report_check
from labkit.checks import audit_binding  # noqa: E402


class ReportCheck(unittest.TestCase):
    def _area(self, cost: str = "minutes", frozen: bool = True) -> Path:
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        (area / "scripts" / "02_analyze.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        scope_file(area)
        (area / "PROTOCOL-x.md").write_text(
            head(cost=cost, frozen=frozen, preflight_audit="n/a — test"),
            encoding="utf-8",
        )
        return area

    def _answered(self, area: Path, name: str = "2026-01-01T00-00-00_0001") -> Path:
        """The completed run bound to the fixture's protocol that answers it."""
        return completed_run(area, name, metrics={"c1_pass": True})

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
            shown_sha=audit_binding.run_shown(area, run, "").sha,
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
        with (
            contextlib.nullcontext()
            if fields
            else mock.patch.object(report_check, "check_fields", return_value=no_gaps),
            mock.patch.object(report_check, "finalize_area", return_value=finalize),
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

    def test_the_context_is_built_once_and_names_what_it_holds(self):
        """One text, one head, one answering run, one named file state for
        every station (`checked`): the declaration is read from the text
        the caller hands over, the run is chosen once through
        `audit_binding.audited_run`, and the output says which state was held."""
        area = self._area(cost="seconds", frozen=False)
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
        self.assertEqual(ctx.head.cost, "seconds")
        self._audited(area, run)
        code, out = self._run(area)
        self.assertEqual(code, 0, out)
        self.assertIn(
            f"read from the working tree; the head declares no run; the answering "
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

    def test_seconds_owes_no_freeze_and_everything_after_it(self):
        """The twin at seconds: unfrozen, no preflight audit, and clean — a
        full run, the analysis record of it, the check."""
        area = self._area(cost="seconds", frozen=False)
        self._audited(area)
        code, out = self._run(area)
        self.assertEqual(code, 0, out)
        self.assertIn("no freeze and no preflight audit owed", out)
        self.assertIn("finalized, audited, checked", out)
        self.assertNotIn("frozen,", out)

    def test_at_seconds_a_probes_number_is_refused(self):
        """Third haiku round: t3 and t5 reported a probe's number; at seconds
        the gate said "nothing owed here"."""
        area = self._area(cost="seconds", frozen=False)
        run = self._answered(area)
        completed_run(area, run.name, metrics={"c1_pass": True}, run_kind="probe")
        self._audited(area, run)
        code, out = self._run(area)
        self.assertEqual(code, 1, out)
        self.assertIn("a probe (run_kind='probe'), not a measurement", out)
        self.assertIn("owes a full run (run_kind='measurement')", out)
        self.assertNotIn("on a frozen protocol", out)  # none is owed at seconds

    def test_at_seconds_an_acknowledged_run_is_refused(self):
        area = self._area(cost="seconds", frozen=False)
        run = self._answered(area)
        completed_run(area, run.name, metrics={"c1_pass": True}, unfrozen_ack=True)
        self._audited(area, run)
        code, out = self._run(area)
        self.assertEqual(code, 1, out)
        self.assertIn("acknowledged over an unfrozen protocol", out)

    def test_at_seconds_the_analysis_audit_and_finalize_are_owed(self):
        area = self._area(cost="seconds", frozen=False)
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
        area = self._area(cost="seconds", frozen=False)  # no run at all
        out = io.StringIO()
        with (
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.report_check(area)
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn("BLOCKER: finalize: no completed run bound to", out.getvalue())
        self.assertNotIn("run it to see", out.getvalue())

    def test_finalize_findings_arrive_as_data_not_through_stdout(self):
        """finalize runs on a silent collector: its blockers reach this gate
        as findings, its headers and notes reach nothing, and stdout is never
        redirected for it (until 0.100.0 it was, and the blockers were read
        back from the collector while the output was thrown away)."""
        area = self._area(cost="seconds", frozen=False)
        out = io.StringIO()
        seen: dict[str, object] = {}

        def fake_finalize(area_: Path, protocol: Path | None, collected) -> int:
            seen["stdout_untouched"] = sys.stdout is out  # this test's, no other
            seen["silent"] = collected._tell is None
            collected.note("── completion ──")
            collected.block("no completed run bound to p-x")
            return collected.report("finalize", "reporting")

        with (
            mock.patch.object(report_check, "finalize_area", fake_finalize),
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.report_check(area)
        self.assertEqual(code, 1, out.getvalue())
        self.assertEqual(seen, {"stdout_untouched": True, "silent": True})
        self.assertIn(
            "BLOCKER: finalize: no completed run bound to p-x", out.getvalue()
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
        station names the one it is missing — at seconds as at minutes."""
        for cost in ("seconds", "minutes"):
            with self.subTest(cost):
                area = self._area(cost=cost, frozen=cost != "seconds")
                repo = area.parent.parent
                self.assertIsNone(report_check.check_analysis_script(area, repo))
                (area / "scripts" / "02_analyze.py").unlink()
                (area / "scripts" / "01_measure.py").write_text(
                    "print('ok')\n", encoding="utf-8"
                )
                failed = report_check.check_analysis_script(area, repo) or ""
                self.assertIn("no scripts/02_analyze.py —", failed)
                self.assertIn("analyze-quick-script.py.template", failed)

    def test_the_later_stations_read_the_lane(self):
        """Station 3 is owed where the lane's `audits` name the analysis
        audit — every lane of the standard does; a lane without it (built
        here, not in the contract) owes no record, and station 2 names the
        freeze only where the lane owes it (review 2026-10-19: the release
        read only `freeze` off the contract)."""
        area = self._area(cost="seconds", frozen=False)
        run = self._answered(area)
        completed_run(area, run.name, metrics={"c1_pass": True}, run_kind="probe")
        ctx = report_check.checked(area, area / "PROTOCOL-x.md")
        seconds = standard_contract.lane("seconds")
        with (
            mock.patch.object(report_check, "finalize_area", return_value=0),
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
        ):
            gaps = report_check.later_gaps(ctx, seconds)
            self.assertTrue(any("analysis audit:" in g for g in gaps), gaps)
            self.assertFalse(any("on a frozen protocol" in g for g in gaps), gaps)
            without = dataclasses.replace(seconds, audits=(), freeze=True)
            gaps = report_check.later_gaps(ctx, without)
            self.assertFalse(any("analysis audit:" in g for g in gaps), gaps)
            self.assertTrue(any("on a frozen protocol" in g for g in gaps), gaps)

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
    "Answer to the question" is held to the whole chain; a protocol whose
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
    ) -> Path:
        """A seconds area (no freeze owed, so the bare fixture head passes
        station 1) whose protocol says ANSWER and declares DECLARED as its
        result (the head's `[result] run`; None: an exploration); its one
        run a full run unless LONG says a probe; an analysis record of it
        when AUDITED. GIT: the
        root is a repository (before the record: the stamp's paths are
        repo-relative) and everything is committed at the end."""
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
            head(cost="seconds", result=declared)
            + f"- **Answer to the question:** {answer}\n",
            encoding="utf-8",
        )
        run = completed_run(
            area, self.RUN, metrics={"c1_pass": True}, run_kind=run_kind
        )
        # at seconds finalize holds the provenance: the source frozen in the run
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
                shown_sha=audit_binding.run_shown(area, run, "").sha,
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
        area = self._area(f"AUC 0.91 ({self.RUN})", declared=self.RUN, git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        code, out = self._staged_gate(root, proto)
        self.assertEqual(code, 0, out)  # the twin: tree is index, all holds
        self.assertIn("finalized, audited, checked", out)
        reported = proto.read_text(encoding="utf-8")
        proto.write_text(
            reported.replace(f'\n[result]\nrun = "{self.RUN}"\n', ""),
            encoding="utf-8",
        )
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
        area = self._area(f"1 (run {self.RUN})", declared=self.RUN, git=True)
        code, out = self._staged_gate(area.parent.parent, area / "PROTOCOL-x.md")
        self.assertEqual(code, 0, out)
        self.assertIn("read from the index; the head declares " + self.RUN, out)

    def test_staged_refuses_an_area_whose_tree_is_not_the_index(self):
        """A script modified and one untracked under a reported number: the
        stations would judge a state the commit does not hold."""
        area = self._area(f"AUC 0.91 ({self.RUN})", declared=self.RUN, git=True)
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
        area = self._area(f"AUC 0.91 ({self.RUN})", declared=self.RUN, git=True)
        root = area.parent.parent
        script = area / "scripts" / "02_analyze.py"
        script.write_text("print('changed')\n", encoding="utf-8")
        self._git(root, "add", "-A")
        (area / "PROTOCOL-x.md").unlink()
        code, out = self._staged_gate(root, script)
        self.assertEqual(code, 1, out)
        self.assertIn("report-check", out)
        self.assertIn("the working tree differs from the index", out)

    def test_a_shared_helper_reopens_the_areas_that_import_it(self):
        """lib/scoring.py lies in no area; an area whose script imports it is
        touched by its change, and one that does not is not."""
        area = self._area(f"AUC 0.91 ({self.RUN})", declared=self.RUN, git=False)
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
            report_check.reported_protocols([helper], root),
            [area.resolve() / "PROTOCOL-x.md"],
        )
        helper.unlink()  # a deleted helper is still one the area rests on
        self.assertEqual(
            report_check.reported_protocols([helper], root),
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
        area = self._area(f"AUC 0.91 ({self.RUN})", declared=self.RUN)
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
        code, out = self._gate(self._area(f"AUC 0.91 ({self.RUN})", declared=self.RUN))
        self.assertEqual(code, 0, out)
        self.assertIn(f"its head declares {self.RUN}", out)
        self.assertIn("finalized, audited, checked", out)

    def test_a_reported_probe_is_refused(self):
        """Third haiku round, t3 and t5: the probe's number, written back."""
        code, out = self._gate(
            self._area(f"AUC 0.91 ({self.RUN})", declared=self.RUN, run_kind="probe")
        )
        self.assertEqual(code, 1, out)
        self.assertIn("a probe (run_kind='probe'), not a measurement", out)

    def test_citing_another_run_than_the_one_that_answers_blocks(self):
        other = "2026-10-01T09-00-00_ffff"
        code, out = self._gate(self._area(f"AUC 0.91 ({other})", declared=other))
        self.assertEqual(code, 1, out)
        self.assertIn("finalize: ", out)
        self.assertIn("but the run that answers is", out)

    def test_a_reported_run_without_its_analysis_audit_blocks(self):
        code, out = self._gate(
            self._area(f"AUC 0.91 ({self.RUN})", declared=self.RUN, audited=False)
        )
        self.assertEqual(code, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)


if __name__ == "__main__":
    unittest.main()
