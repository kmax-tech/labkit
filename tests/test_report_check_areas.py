"""report-check on an area without a repository: what is owed when, at
every repeat cost — the freeze, finalize clean and named, the answering run
a full run, an analysis audit of the code, promises and run as they are now,
`02_analyze.py --check` passing — and that every station blocks on its own.
`--if-reported`, the entry the stop and the pre-commit run on a repository's
index and tree: tests/test_report_check.py."""

from __future__ import annotations

from labkit.formats.evidence import read_evidence
from labkit.formats import area_state
from labkit.tools import protocol_result

import contextlib
import dataclasses
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from protocol_fixture import (
    protocol_id_of,
    registration_of,
    C1_BLOCK,
    C1_PROSE,
    completed_run,
    head,
    scope_file,
    shown_sha,
)

from labkit.formats import (
    findings,
    gate,
    promises,
    scope_sha,
    standard_contract,
)
from labkit.gates import report_check
from labkit.gates import report_context


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
            protocol_id=protocol_id_of(area),
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
        no_gaps = SimpleNamespace(must_gaps=[], must_holes=[], repeated=[])

        def fake_finalize(
            area_: Path, protocol: Path | None, collected, *, state=None, held=None
        ) -> int:
            if finalize:  # finalize keeps every reason it has as a blocker
                # a station's blocker counts whatever its rule
                # (test_gate, "a blocker blocks whatever its rule"); the
                # stub is the plainest one, a breach without a rule to cite
                collected.block(
                    f"stub blocker (finalize exit {finalize})",
                    fix="stub way out",
                    rule=gate.TECHNICAL_RULE,
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
            code = report_check.protocol_verdict(area).exit
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
        another, and the old audit does not pass it. The refusal names the
        field."""
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
        ctx = report_context.checked(area, proto)
        self.assertEqual(
            (ctx.file_state, ctx.declared, ctx.run), (area_state.TREE, None, run)
        )
        self.assertEqual(ctx.text, proto.read_text(encoding="utf-8"))
        # the index's text, not the tree's: the declaration comes from there
        # (outside a repository the index has no runs: the tree's state is
        # handed in, as a caller that built one does)
        staged = protocol_result.fill_result_run(ctx.text, run.name)
        ctx = report_context.checked(
            area,
            proto,
            file_state=area_state.INDEX,
            text=staged,
            area_state=ctx.area_state,
            area_evidence=ctx.evidence,
        )
        self.assertEqual((ctx.file_state, ctx.declared), (area_state.INDEX, run.name))
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
        ctx = report_context.checked(area, area / "PROTOCOL-x.md")
        self.assertIsNone(ctx.run)
        self.assertIn("no completed run bound to", ctx.why)
        out = io.StringIO()
        # the real finalize: its first station holds the missing run
        with (
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.protocol_verdict(area).exit
        self.assertEqual(code, 1)
        self.assertIn(f"the answering run is none — {ctx.why}", out.getvalue())

    def test_a_freeze_with_a_must_gap_blocks(self):
        """Frozen with the stamp's `<…>` promise sentences: the flag is set,
        the freeze registers nothing."""
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
        """A must field holding its stamped `<…>` blocks at station 1, as
        protocol-check and preflight refuse it — not only a missing one."""
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

    def test_a_bound_field_written_twice_blocks_with_its_own_way_out(self):
        """Which copy is registered cannot be told: refused as such, not as
        a field to fill (`protocol_check.repeated_fields`)."""
        area = self._area()
        self._audited(area)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            "- **Unit:** one case\n- **Unit (v2):** one document\n\n"
            + proto.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        out = io.StringIO()
        # the real finalize: its open-fields station holds the doubled field,
        # the freeze station does not hold it a second time
        with (
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.protocol_verdict(area).exit
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn(
            "finalize: PROTOCOL-x.md: Unit written 2 times (lines 1 and 2)",
            out.getvalue(),
        )
        self.assertIn("keep one copy and delete the others", out.getvalue())

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
        """A probe's number reported at low repeat cost is refused: the lane
        owes no freeze, but a full run all the same."""
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
        """finalize's blockers stand in report-check's list: inside the stop
        hook, "run it to see them" is a round trip an agent does not take."""
        area = self._area(repeat_cost="low", frozen=False)  # no run at all
        out = io.StringIO()
        with (
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.protocol_verdict(area).exit
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn("BLOCKER: finalize: no completed run bound to", out.getvalue())
        self.assertNotIn("run it to see", out.getvalue())

    def test_finalize_exiting_without_a_blocker_is_a_bug_not_a_hint(self):
        """finalize keeps every reason as a blocker; a non-zero exit without
        one is a bug and says so, never "run it to see why"."""
        area = self._area(repeat_cost="low", frozen=False)
        with (
            mock.patch.object(report_check, "finalize_area", return_value=2),
            self.assertRaises(RuntimeError) as caught,
        ):
            report_check.finalize_findings(
                area,
                area / "PROTOCOL-x.md",
                area_state.state_of(area),
                read_evidence(area, staged=False),
            )
        self.assertIn("kept no blocker", str(caught.exception))

    def test_finalize_findings_arrive_as_data_not_through_stdout(self):
        """finalize runs on a silent collector: its blockers reach this gate
        as findings, its headers and notes reach nothing, and stdout is never
        redirected for it."""
        area = self._area(repeat_cost="low", frozen=False)
        out = io.StringIO()
        seen: dict[str, object] = {}

        def fake_finalize(
            area_: Path, protocol: Path | None, collected, *, state=None, held=None
        ) -> int:
            seen["stdout_untouched"] = sys.stdout is out  # this test's, no other
            seen["silent"] = collected._tell is None
            collected.note("── completion ──")
            # the basis of the finding this stands in for
            # (`answering_run`, a technical contract)
            collected.block(
                "no completed run bound to p-x",
                fix="measure: `x`",
                rule=gate.TECHNICAL_RULE,
            )
            return collected.report("finalize", "reporting")

        with (
            mock.patch.object(report_check, "finalize_area", fake_finalize),
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.protocol_verdict(area).exit
        self.assertEqual(code, 1, out.getvalue())
        self.assertEqual(seen, {"stdout_untouched": True, "silent": True})
        # the nested gate's way out reaches the line
        self.assertIn(
            "BLOCKER: finalize: no completed run bound to p-x. Next: measure: `x`",
            out.getvalue(),
        )
        self.assertNotIn("── completion ──", out.getvalue())
        self.assertNotIn("finalize: 1 blocker", out.getvalue())

    def test_finalize_warnings_reach_report_check(self):
        """A warning of the nested finalize stands in report-check's chain
        and in its output, prefixed — so the stop and the commit show it too."""
        area = self._area(repeat_cost="low", frozen=False)
        self._audited(area)

        def warning_finalize(
            area_: Path, protocol: Path | None, collected, *, state=None, held=None
        ) -> int:
            collected.warn(
                "one draw only", evidence_kind="guaranteed", rule=gate.TECHNICAL_RULE
            )
            return 0

        out = io.StringIO()
        with (
            mock.patch.object(report_check, "finalize_area", warning_finalize),
            mock.patch.object(report_check, "check_analysis_script", return_value=None),
            contextlib.redirect_stdout(out),
        ):
            ctx = report_context.checked(area, area / "PROTOCOL-x.md")
            found = report_check.chain_gaps(ctx).found
            report_check.protocol_verdict(area).exit
        warned = [f.text for f in found if f.grade == "WARNING"]
        self.assertIn("finalize: one draw only", warned)
        self.assertIn("WARNING: finalize: one draw only", out.getvalue())

    def test_no_answering_run_is_one_blocker(self):
        """A missing run is one blocker, finalize's: intent-check's same
        choice and the analysis station do not hold it again."""
        area = self._area(repeat_cost="low", frozen=False)  # no run at all
        with mock.patch.object(
            report_check, "check_analysis_script", return_value=None
        ):
            ctx = report_context.checked(area, area / "PROTOCOL-x.md")
            blockers = [f.text for f in report_check.chain_gaps(ctx).blockers]
        self.assertEqual(
            [b for b in blockers if "no completed run bound" in b],
            [b for b in blockers if "run" in b and "bound" in b],
        )
        self.assertEqual(
            len([b for b in blockers if "no completed run bound" in b]), 1, blockers
        )
        self.assertFalse([b for b in blockers if "intent-check" in b], blockers)
        self.assertFalse([b for b in blockers if "no answering run" in b], blockers)

    def test_an_unreportable_mark_is_one_blocker_not_also_a_warning(self):
        area = self._area(repeat_cost="low", frozen=False)
        run = self._answered(area)
        completed_run(
            area, run.name, metrics={"criterion_1_pass": True}, unfrozen_ack=True
        )
        self._audited(area, run)
        with mock.patch.object(
            report_check, "check_analysis_script", return_value=None
        ):
            ctx = report_context.checked(area, area / "PROTOCOL-x.md")
            found = report_check.chain_gaps(ctx).found
        marked = [
            f for f in found if "acknowledged over an unfrozen protocol" in f.text
        ]
        self.assertEqual(
            [f.grade for f in marked], ["BLOCKER"], [f.text for f in found]
        )

    def test_a_result_table_that_does_not_read_is_one_blocker(self):
        """The declaration station's blocker, with the withdrawal as its
        step — finalize, which read the same text, tells it no second time."""
        area = self._area(repeat_cost="low", frozen=False)
        run = self._answered(area)
        self._audited(area, run)
        protocol = area / "PROTOCOL-x.md"
        text = protocol.read_text(encoding="utf-8")
        typed = text.replace(
            'preflight_audit = "n/a — test"\n',
            'preflight_audit = "n/a — test"\n\n[result]\n'
            'run = "2026-10-07T10-00-00_final"\n',
        )
        self.assertNotEqual(typed, text)
        protocol.write_text(typed, encoding="utf-8")
        with mock.patch.object(
            report_check, "check_analysis_script", return_value=None
        ):
            ctx = report_context.checked(area, protocol)
            found = report_check.chain_gaps(ctx).found
        (told,) = [f for f in found if "no run id runlog writes" in f.text]
        self.assertEqual(told.grade, "BLOCKER")
        self.assertTrue(told.text.startswith("PROTOCOL-x.md: "), told.text)
        self.assertIn("--withdraw", str(told.step))

    def test_a_field_written_twice_is_one_blocker_at_the_freeze(self):
        area = self._area()
        protocol = area / "PROTOCOL-x.md"
        protocol.write_text(
            protocol.read_text(encoding="utf-8") + C1_PROSE, encoding="utf-8"
        )
        with mock.patch.object(
            report_check, "check_analysis_script", return_value=None
        ):
            ctx = report_context.checked(area, protocol)
            blockers = [f.text for f in report_check.chain_gaps(ctx).blockers]
        twice = [b for b in blockers if "written 2 times" in b]
        self.assertEqual(len(twice), 1, blockers)
        # on the adoption's proposal finalize reads the tree, not this text:
        # the freeze station holds it there
        proposed = dataclasses.replace(ctx, file_state=area_state.PROPOSED)
        with mock.patch.object(
            report_check, "check_analysis_script", return_value=None
        ):
            blockers = [f.text for f in report_check.chain_gaps(proposed).blockers]
        self.assertEqual(len([b for b in blockers if "written 2 times" in b]), 2)

    def test_each_station_blocks_on_its_own(self):
        area = self._area(frozen=False)
        self._answered(area)  # the analysis station holds an answering run only
        code, out = self._run(area, finalize=1, check="02_analyze.py --check exits 1")
        self.assertEqual(code, 1)
        for needle in (
            "not `frozen = true`",
            "finalize",
            "analysis audit: no analysis audit saw the area as it is now",
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
        """Same code, a later answering run: a record of the earlier run
        does not hold it, since a record names its run, not the code only. The
        twin: a record of the newest run is clean. Then a promise sentence
        edited after the audit."""
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
        """A metrics.json or output rows changed after the audit do not read
        as audited: the record names the run as it was, not its id only.
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
        """Every skeleton stamps `02_analyze.py` (`standard_contract.CHECK_SCRIPT`),
        never a check inside `01_measure.py`, and station 4 names the one it
        is missing — at low repeat cost as at high."""
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
        freeze only where the lane owes it — the release reads both off the
        contract, not `freeze` alone."""
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
        """`protocol-fill --from-run` runs this inside `adopt`: output no codec
        reads is a named gap, never a UnicodeDecodeError that leaves the
        unchecked answer in the protocol."""
        area = self._area()
        (area / "scripts" / "02_analyze.py").write_text(
            "import sys\nsys.stderr.buffer.write(b'bad \\xff byte\\n')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        failed = report_check.check_analysis_script(area, area.parent.parent)
        self.assertIn("exits 1: bad \ufffd byte", failed or "")
