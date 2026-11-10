"""report-check: the last gate at every repeat cost — frozen (high repeat cost
only), finalize clean and named, the answering run a full run, an analysis
audit of code, promises and that run as they are now, `02_analyze.py
--check` passing.

finalize runs before the analysis audit and cannot ask for it or for what
follows — the check and the note — so the end has its own gate, at every
repeat cost: a probe's number never passes as a reported one. Each station
is tested where it lives (audit_gaps.audit_coverage, recheck.holds,
finalize); here: what is owed when,
that every station blocks on its own, and `--if-reported` — the gate the
stop hook and the pre-commit run — holds exactly the protocols whose answer
cites a run.
"""

from __future__ import annotations

import pytest

from labkit.formats.evidence import read_evidence
from labkit.formats import run_index
from labkit.formats.area_state import state_of
from labkit.formats import area_state
from labkit.gates import registered_report
from labkit.tools import report_command
from labkit.formats.runs import RunKind
from labkit.tools import protocol_fill
from labkit.tools import protocol_result

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
    source_entry,
    protocol_id_of,
    registration_of,
    C1_BLOCK,
    C1_PROSE,
    completed_run,
    head,
    scope_file,
    started_at,
    shown_sha,
)

from labkit.formats import (
    findings,
    handovers,
    promises,
    protocol_block,
    scope_sha,
    standard_contract,
)
from labkit.gates import report_check, report_hold
from labkit.gates import report_context

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow


def _measured(protocol: Path) -> area_state.Measured:
    """What PROTOCOL's area measured of it, as the tree holds it."""
    text = protocol.read_text(encoding="utf-8")
    return area_state.state_of(protocol.parent).measured_of(
        protocol_block.head(text).id
    )


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
        no_gaps = SimpleNamespace(missing_must=[], must_holes=[], repeated=[])

        def fake_finalize(
            area_: Path, protocol: Path | None, collected, *, state=None, held=None
        ) -> int:
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
            collected.block("no completed run bound to p-x", fix="measure: `x`")
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
            collected.warn("one draw only", evidence_kind="guaranteed")
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


class IfReported(unittest.TestCase):
    """`report-check --if-reported`: the gate at the stop and the commit.
    A number written back into
    "Recorded results" is held to the whole chain; a protocol whose
    answer is still open owes nothing — an exploration ends with no reported
    result, probes in `runs/` or not."""

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
        must_fields: bool = False,
    ) -> Path:
        """A low-lane area (no freeze owed, so the bare fixture head passes
        station 1) whose protocol says ANSWER and declares DECLARED as its
        result (the head's `[result] run`; None: an exploration); its one
        run a full run unless LONG says a probe; an analysis record of it
        when AUDITED. GIT: the
        root is a repository (before the record: the stamp's paths are
        repo-relative) and everything is committed at the end. REPORT: the
        head's registered report file (`report = "…"`). MUST_FIELDS: the four
        MUST fields the fixture's prose lacks are registered too, so the
        hook's protocol-check passes."""
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
            + f"- **Recorded results:** {answer}\n"
            # a declared result owes its answer, which its block shows
            + "- **Conclusion:** criterion-1 holds on the one case.\n"
            + "".join(
                f"- **{label}:** n/a — test\n"
                for label in (
                    "Terms of this protocol",
                    "Data / scope",
                    "Exclusions / filters",
                    "Unit",
                )
                if must_fields
            ),
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
        data["data"] = {"cases": source_entry(src)}
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
                protocol_id=protocol_id_of(area),
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
            code = report_check.hold_reported(list(paths), root, staged=True).exit
        return code, buf.getvalue()

    def test_staged_reads_the_answer_as_the_index_holds_it(self):
        """The pre-commit's form: a reported answer in the index, the tree's
        reopened — the hook reads the index, the state the commit holds."""
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
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
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
        )
        code, out = self._staged_gate(area.parent.parent, area / "PROTOCOL-x.md")
        self.assertEqual(code, 0, out)
        self.assertIn("read from the index; the head has adopted " + self.RUN, out)

    def test_staged_refuses_an_area_whose_tree_is_not_the_index(self):
        """A script modified and one untracked under a reported number: the
        stations would judge a state the commit does not hold."""
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
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

    def test_the_commits_tree_vs_index_hold_is_nexts_step(self):
        """One mouth (docs/notes/2026-11-04-one-explainer-plan.md): an
        adoption committed with the run untracked is held as "the working
        tree differs from the index", and the hold is a finding `next`
        carries — the gate prints the one finding
        (`report_hold.staged_area_gap`) and `next --staged` names its step,
        the whole area staged; in the tree `next` says nothing of it, and
        once staged neither does."""
        from labkit.gates import next_step

        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
        )
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        # the fixture's prose lacks four MUST fields, which `next` names
        # first, as the hook's protocol-check would: fill and commit them
        with proto.open("a", encoding="utf-8") as f:
            for label in (
                "Terms of this protocol",
                "Data / scope",
                "Exclusions / filters",
                "Unit",
            ):
                f.write(f"- **{label}:** n/a — test\n")
        self._git(root, "commit", "-qam", "fields")
        (area / "scripts" / "new.py").write_text("x = 1\n", encoding="utf-8")
        with contextlib.chdir(root):
            staged = next_step.next_step(area, proto, file_state=area_state.INDEX)
            tree = next_step.next_step(area, proto, file_state=area_state.TREE)
            code, out = self._staged_gate(root, proto)
        self.assertEqual(code, 1, out)
        self.assertEqual(
            staged.next.split(" stages")[0], "`git add -- experiments/01-x`"
        )
        self.assertIn(staged.where, out)  # the gate's hold is next's finding
        self.assertIn(staged.next, out)
        self.assertNotIn("git add", tree.next)  # the tree is not the commit
        self._git(root, "add", "-A")
        with contextlib.chdir(root):
            after = next_step.next_step(area, proto, file_state=area_state.INDEX)
        self.assertNotIn("git add", after.next)

    def test_a_commit_without_the_adopted_runs_record_is_held(self):
        """The record is the run's integrity evidence, so the commit that
        first cites an adopted run must carry `runs/<id>/` (pin route, "Check
        before building", docs/notes/2026-11-06-pin-route.md): left out of
        the index, the commit gate names its files; kept out by an ignore
        rule, it names the rule's way out. The twin, the record staged,
        passes. A fresh clone of a commit made past the hook fails loudly
        elsewhere (`report_blocks`: "cites run … no runs/<id>/ in the
        repo")."""
        from labkit.gates import claude_hooks

        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
            must_fields=True,
        )
        root = area.parent.parent
        # the run, its audit and the adoption staged, not yet committed: the
        # registration alone is in HEAD
        self._git(root, "reset", "-q", "--soft", "HEAD~1")
        run = f"experiments/01-x/runs/{self.RUN}"
        self._git(root, "rm", "-r", "-q", "--cached", run)

        def commit_gate() -> tuple[int, str]:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.chdir(root):
                rc = claude_hooks.main(["pre-commit"])
            return rc, out.getvalue()

        rc, out = commit_gate()
        self.assertEqual(rc, 1, out)
        self.assertIn("the working tree differs from the index", out)
        self.assertIn(f"{run}/config.json", out)
        (root / ".gitignore").write_text("runs/\n", encoding="utf-8")
        self._git(root, "add", ".gitignore")
        rc, out = commit_gate()
        self.assertEqual(rc, 1, out)
        self.assertIn(
            f"runs/{self.RUN}/config.json: git ignores it — evidence labkit wrote",
            out,
        )
        self._git(root, "rm", "-q", "--cached", ".gitignore")
        (root / ".gitignore").unlink()
        self._git(root, "add", run)
        rc, out = commit_gate()
        self.assertEqual(rc, 0, out)
        self.assertIn("finalized, audited, checked", out)

    def test_staged_finds_a_protocol_deleted_only_in_the_tree(self):
        """The script staged, the reported protocol deleted in the tree and
        not in the index: the commit keeps the protocol, so the gate holds
        it — the search for protocols reads the index, not the tree."""
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
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
        """`--from-run` wrote the declaration into the tree, and the commit
        stages the report, not the protocol: the hold names the unstaged
        protocol and `git add`, never a bare "declares no result" an agent
        could read as a rejected review; staged, that line is gone (the twin).
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
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
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
        clean = report_check.HoldVerdict(0, {})
        with mock.patch.object(
            report_check, "hold_reported", return_value=clean
        ) as gate:
            report_command.main(["--if-reported", "--staged", "a/PROTOCOL-x.md"])
        gate.assert_called_once_with([Path("a/PROTOCOL-x.md")], mock.ANY, staged=True)
        with mock.patch.object(
            report_check, "hold_reported", return_value=clean
        ) as gate:
            report_command.main(["--if-reported", "a/PROTOCOL-x.md"])
        gate.assert_called_once_with([Path("a/PROTOCOL-x.md")], mock.ANY, staged=False)

    def _gate(self, area: Path, *paths: Path) -> tuple[int, str]:
        """The gate over PATHS — the protocol itself when none are named."""
        buf = io.StringIO()
        paths = paths or (area / "PROTOCOL-x.md",)
        with contextlib.redirect_stdout(buf):
            code = report_command.main(["--if-reported", *map(str, paths)])
        return code, buf.getvalue()

    def test_a_changed_script_reopens_the_areas_reported_number(self):
        """The protocol untouched, a script under it edited: the analysis
        audit saw other code, and both hooks hold the reported number."""
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
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
                f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
                declared=self.RUN,
            )
        )
        self.assertEqual(code, 0, out)
        self.assertIn(f"its head has adopted {self.RUN}", out)
        self.assertIn("finalized, audited, checked", out)

    def test_a_reported_probe_is_refused(self):
        """The probe's number, written back."""
        code, out = self._gate(
            self._area(
                f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
                declared=self.RUN,
                run_kind="probe",
            )
        )
        self.assertEqual(code, 1, out)
        self.assertIn("a probe (run_kind='probe'), not a measurement", out)

    def test_citing_a_run_that_does_not_exist_blocks(self):
        other = "2026-10-01T09-00-00_ffff"
        code, out = self._gate(
            self._area(f"criterion_1_pass = True (run {other})", declared=other)
        )
        self.assertEqual(code, 1, out)
        self.assertIn("finalize: ", out)
        self.assertIn("which cannot answer for", out)

    def test_a_reported_run_without_its_analysis_audit_blocks(self):
        code, out = self._gate(
            self._area(
                f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
                declared=self.RUN,
                audited=False,
            )
        )
        self.assertEqual(code, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)


if __name__ == "__main__":
    unittest.main()


class RegisteredReport(unittest.TestCase):
    """The registered report owes its result: a protocol
    whose head says `report = "REPORT.md"` holds that file, once it is
    delivered, to the result block of the declared run or the protocol's
    handover block — at the stop, the commit and the plain call. A number
    without a run id is inside the gate too, so deleting the run id after a
    refused citation passes nothing."""

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
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=declared,
            git=git,
            report=report,
        )

    def _gate(self, root: Path, *paths: Path, staged: bool = False) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = report_check.hold_reported(list(paths), root, staged=staged).exit
        return code, buf.getvalue()

    OWED = "carries neither"
    WAYS = ("--into", "--discuss", "--handover")
    UNREVIEWED = "PROTOCOL-x.md registers and has no clean report review"

    def _reviewed(self, area: Path, report: Path, claims: tuple = ()) -> None:
        """A report review of REPORT under the area's protocol in its state
        now, naming CLAIMS — what `--report-review` writes."""
        from labkit.formats import report_reviews
        from labkit.gates import report_review

        proto = area / "PROTOCOL-x.md"
        text = report.read_text(encoding="utf-8")
        pieces = report_review.review_pieces(
            area,
            report,
            text,
            proto,
            proto.read_text(encoding="utf-8"),
            report_review.discussed_under(report, text, proto),
            state_of(area),
            read_evidence(area, staged=False),
        )
        whole, parts = report_hold.review_fingerprint(pieces)
        rkey, pkey = report_review.review_keys(area, report, proto)
        report_reviews.write_report_review(
            area,
            model="m",
            report=rkey,
            protocol=pkey,
            whole=whole,
            parts=parts,
            claims=list(claims),
            again=False,
        )

    def test_a_registered_report_without_its_block_is_held_with_the_three_ways_out(
        self,
    ):
        """A delivered report with a number and no run id.
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
                    f" {self.RUN}` adopts the run (the newest kept one) and writes "
                    "its result block",
                    out,
                )
                self.assertIn(f"--discuss {self.RUN} --why", out)
                self.assertIn(
                    "writes the progress account of the run the gates hold it to — "
                    "the commit takes it, it releases nothing and the result or the "
                    "handover stays owed",
                    out,
                )
                self.assertIn("--handover --why", out)
                self.assertIn("ends the protocol without a result", out)
                self.assertIn(
                    "its head has adopted no result; its registered report is delivered",
                    out,
                )
        ctx = report_context.checked(area, area / "PROTOCOL-x.md")
        (gap,) = report_check.report_findings(ctx)
        self.assertEqual(gap.grade, "BLOCKER")
        self.assertIn(self.OWED, gap.text)

    def test_the_adoption_is_not_held_against_itself(self):
        """With the registered REPORT.md already in the tree (no block yet),
        the adoption's own check (PROPOSED) does not hold the report for the
        block only `--into` can write after it — else `--from-run` and
        `--into` would each refuse the other's step; the tree and the index
        hold it (the twin)."""
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
        ctx = report_context.checked(
            area, proto, file_state=area_state.PROPOSED, text=declared
        )
        self.assertEqual(report_check.report_findings(ctx), [])
        ctx = report_context.checked(area, proto)
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
        # the block releases the result; the report's text still owes its
        # review — the prose may present another run
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertNotIn(self.OWED, out)
        self.assertIn(self.UNREVIEWED, out)
        self.assertIn("--report-review", out)
        self._reviewed(area, report)
        for path in (report, proto):
            with self.subTest(path=path.name):
                code, out = self._gate(root, path)
                self.assertEqual(code, 0, out)
                self.assertNotIn(self.OWED, out)
        self.assertEqual(
            report_check.report_findings(report_context.checked(area, proto)), []
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
        self.assertIn("Next: `protocol-fill ", line)
        self.assertIn("--into ", line)
        self.assertNotIn("--from-run", line.split("--discuss")[0])

    def test_the_registered_report_is_held_by_a_claim_and_reviewed_again_after_a_change(
        self,
    ):
        """A REPORT.md may call an older run's criterion "PASS", with or
        without a discussion block: the registered report owes a review of its
        final state; a claim holds it; a clean review releases that state only
        — a later edit owes another."""
        from labkit.formats.report_reviews import ReportClaim

        area = self._area(declared=self.RUN, git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        report = root / "REPORT.md"
        new, _ = protocol_fill.into_report(
            proto.read_text(encoding="utf-8"), area, "# Report\n\n", self.P
        )
        report.write_text(
            new + "\nAn older run passed criterion-1.\n", encoding="utf-8"
        )
        claim = ReportClaim(
            line=len(new.split("\n")) + 1, kind="result", why="an older run's verdict"
        )
        self._reviewed(area, report, (claim,))
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("the report review holds this state (is the report", out)
        # the twin: the claim answered by the text, a clean review of that state
        report.write_text(new, encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertIn(self.UNREVIEWED, out)
        self._reviewed(area, report)
        self.assertEqual(self._gate(root, report)[0], 0)
        report.write_text(new + "\nAdded later.\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(self.UNREVIEWED, out)
        self.assertIn("changed since", out)

    def test_a_registered_report_never_written_is_an_incomplete_delivery(self):
        """The registered report owes its review, written or not: once the
        area measured, the stop holds a protocol whose registered report is
        missing — deleting the run does not lift it;
        the twins: before a measurement, and with the report written,
        nothing."""
        import shutil

        from labkit.gates import agent_hooks

        area = self._area(git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        # the bare fixture lacks MUST fields; filled, so that the step the
        # stop prints is the report's, not the registration's
        proto.write_text(
            proto.read_text(encoding="utf-8")
            + "- **Terms of this protocol:** none\n- **Data / scope:** all\n"
            "- **Exclusions / filters:** none\n- **Unit:** 1\n",
            encoding="utf-8",
        )
        text = proto.read_text(encoding="utf-8")
        gap = registered_report.missing_report(
            proto, text, root, measured=_measured(proto)
        )
        assert gap is not None
        self.assertIn("REPORT.md as its report, which is not written", gap.text)
        self.assertIn("labkit-adopt", gap.fix or "")
        self.assertIn("--handover", gap.fix or "")
        # the stop holds on that finding and prints `labkit-next`'s step for
        # the state: the progress account into the registered report
        from labkit.gates import next_step

        with contextlib.chdir(root):
            (line,) = agent_hooks.missing_reports(root, [proto]).steps.values()
            step = next_step.next_step(area, proto)
        self.assertEqual(line, step.render("experiments/01-x"))
        self.assertIn("REPORT.md carries no account of it yet", line)
        # the twin: the report written, nothing missing
        (root / "REPORT.md").write_text("# Report\n", encoding="utf-8")
        self.assertIsNone(
            registered_report.missing_report(
                proto, text, root, measured=_measured(proto)
            )
        )
        (root / "REPORT.md").unlink()
        # deleting the measured run does not lift it: the commit holds it,
        # and so does runs.tsv (`area_state.Measured`)
        from labkit.run import runlog

        runlog.reindex(area)
        shutil.rmtree(area / "runs")
        self.assertIsNotNone(
            registered_report.missing_report(
                proto, text, root, measured=_measured(proto)
            )
        )
        (area / run_index.RUN_INDEX).unlink()
        self.assertIsNotNone(
            registered_report.missing_report(
                proto, text, root, measured=_measured(proto)
            )
        )
        # the twin: a run never committed, deleted with its index — no
        # measurement anywhere, nothing owed yet
        area = self._area(git=False)
        proto = area / "PROTOCOL-x.md"
        shutil.rmtree(area / "runs")
        self.assertIsNone(
            registered_report.missing_report(
                proto,
                proto.read_text(encoding="utf-8"),
                area.parent.parent,
                measured=_measured(proto),
            )
        )

    def test_the_twin_a_note_citing_a_run_owes_no_review(self):
        """A research note may describe an unreviewed run: only the report
        the head registers owes a review, not every file citing a run."""
        area = self._area(declared=self.RUN, git=True)
        root = area.parent.parent
        older = "2026-10-06T10-00-00_aa11"
        completed_run(area, older, metrics={"criterion_1_pass": True})
        note = root / "notes" / "pilot.md"
        note.parent.mkdir()
        note.write_text(
            f"The first run, {older}, gave 0.89 and was dropped.\n",
            encoding="utf-8",
        )
        code, out = self._gate(root, note)
        self.assertNotIn("report review", out)
        self.assertEqual(code, 0, out)

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
        code, out = self._gate(root, report)
        self.assertIn(self.UNREVIEWED, out)  # a handover owes its review too
        self._reviewed(area, report)
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

    def _discussed(self, area: Path, run_id: str) -> Path:
        """REPORT.md at the root with the progress account of RUN_ID."""
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            protocol_fill.discuss_into(
                (area / "PROTOCOL-x.md").read_text(encoding="utf-8"),
                area,
                "# Report\n\nmeasured; the audit is still open\n",
                self.P,
                run_id,
                "measured, the analysis audit still open",
            ),
            encoding="utf-8",
        )
        return report

    def test_the_progress_account_passes_the_commit_and_the_stop(
        self,
    ):
        """While nothing is adopted, a discussion of the answering run is the
        progress account, an honest interim state: the commit and the stop
        take it without a model call. It releases nothing: nothing is
        adopted, and report-check of the protocol still owes the analysis
        audit."""
        area = self._fixture(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            git=True,
            report="REPORT.md",
            audited=False,
        )
        root = area.parent.parent
        report = self._discussed(area, self.RUN)
        self._git(root, "add", "-A")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        self.assertNotIn("report review", out.lower().replace("report-check", ""))
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertNotIn("carries the progress account of run", out)
        proto = area / "PROTOCOL-x.md"
        self.assertIsNone(protocol_block.declared_run(proto.read_text("utf-8")))
        ctx = report_context.checked(area, proto)
        gaps = report_check.chain_gaps(ctx, undeclared=True).found
        self.assertTrue(any("analysis" in g.text for g in gaps), gaps)

    def test_the_twin_a_discussion_of_another_run_is_no_progress_account(self):
        area = self._area(git=True)
        root = area.parent.parent
        other = completed_run(area, "2026-10-01T00-00-00_0000", metrics={"n": 1})
        started_at(other, root)
        report = self._discussed(area, other.name)
        self._git(root, "add", "-A")
        code, out = self._gate(root, report, staged=True)
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
