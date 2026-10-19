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

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from protocol_fixture import completed_run, head, scope_file

from labkit import findings, promises, report_check, scope_sha


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
            area, "analysis", "opus", sha, block, (0, 0, 0), [], run_id=run.name
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
        completed_run(area, run.name, metrics={"c1_pass": True}, long=False)
        self._audited(area, run)
        code, out = self._run(area)
        self.assertEqual(code, 1, out)
        self.assertIn("a probe (long=False), not a full run", out)
        self.assertIn("owes a full run (long=True)", out)
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
        self.assertIn(f"run {later.name}; audited: ", out)
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
        self.assertIsNone(report_check.check_analysis_script(area, repo, False))
        (area / "scripts" / "02_analyze.py").write_text(
            "import sys\nprint('recheck: numbers not in PROTOCOL')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        failed = report_check.check_analysis_script(area, repo, False) or ""
        self.assertIn("exits 1", failed)
        self.assertIn("numbers not in PROTOCOL", failed)

    def test_at_seconds_the_counting_skeletons_check_is_the_check(self):
        """The counting skeleton (`labkit-init exp --cost seconds`, no model)
        stamps `01_measure.py` with the `--check` inside and no analysis
        script; station 4 demanded `02_analyze.py` there and refused every
        correct count (audit 2026-10-19)."""
        area = self._area(cost="seconds", frozen=False)
        repo = area.parent.parent
        (area / "scripts" / "02_analyze.py").unlink()
        (area / "scripts" / "01_measure.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        self.assertEqual(
            report_check.check_script(area, True), Path("scripts/01_measure.py")
        )
        self.assertIsNone(report_check.check_analysis_script(area, repo, True))
        self._audited(area)
        code, out = self._run(area, check=None)
        self.assertEqual(code, 0, out)
        # the twin: at minutes the analysis script stays owed
        failed = report_check.check_analysis_script(area, repo, False) or ""
        self.assertIn("no scripts/02_analyze.py —", failed)
        # neither script: both named
        (area / "scripts" / "01_measure.py").unlink()
        failed = report_check.check_analysis_script(area, repo, True) or ""
        self.assertIn("no scripts/02_analyze.py and no scripts/01_measure.py", failed)

    def test_a_check_printing_bytes_no_codec_reads_is_a_named_gap(self):
        """`protocol-fill --from-run` ran this inside `adopt`; a
        UnicodeDecodeError left the unchecked answer in the protocol
        (audit 2026-10-19)."""
        area = self._area()
        (area / "scripts" / "02_analyze.py").write_text(
            "import sys\nsys.stderr.buffer.write(b'bad \\xff byte\\n')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        failed = report_check.check_analysis_script(area, area.parent.parent, False)
        self.assertIn("exits 1: bad \ufffd byte", failed or "")


class IfReported(unittest.TestCase):
    """`report-check --if-reported`: the gate at the stop and the commit (it
    was `finalize --if-reported` until 0.99.0). A number written back into
    "Answer to the question" is held to the whole chain; a protocol whose
    answer is still open owes nothing — an exploration ends with no reported
    result, probes in `runs/` or not (TODO 2, 2026-10-19)."""

    RUN = "2026-10-07T10-00-00_ab12"

    def _area(self, answer: str, *, long: bool = True, audited: bool = True) -> Path:
        """A seconds area (no freeze owed, so the bare fixture head passes
        station 1) whose protocol says ANSWER; its one run a full run unless
        LONG says a probe; an analysis record of it when AUDITED."""
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        (area / "scripts" / "02_analyze.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        scope_file(area)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            head(cost="seconds") + f"- **Answer to the question:** {answer}\n",
            encoding="utf-8",
        )
        run = completed_run(area, self.RUN, metrics={"c1_pass": True}, long=long)
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
            )
        return area

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
        area = self._area(f"AUC 0.91 ({self.RUN})")
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
            self._area("<number + run_id>", long=False, audited=False)
        )
        self.assertEqual((code, out), (0, ""))

    def test_an_answer_without_a_run_id_is_not_a_declaration(self):
        """Neither reported nor open: protocol-check warns, this gate is silent."""
        code, out = self._gate(self._area("AUC 0.91", audited=False))
        self.assertEqual((code, out), (0, ""))

    def test_a_reported_full_run_passes(self):
        code, out = self._gate(self._area(f"AUC 0.91 ({self.RUN})"))
        self.assertEqual(code, 0, out)
        self.assertIn(f"its answer cites {self.RUN}", out)
        self.assertIn("finalized, audited, checked", out)

    def test_a_reported_probe_is_refused(self):
        """Third haiku round, t3 and t5: the probe's number, written back."""
        code, out = self._gate(self._area(f"AUC 0.91 ({self.RUN})", long=False))
        self.assertEqual(code, 1, out)
        self.assertIn("a probe (long=False), not a full run", out)

    def test_citing_another_run_than_the_one_that_answers_blocks(self):
        code, out = self._gate(self._area("AUC 0.91 (2026-10-01T09-00-00_ffff)"))
        self.assertEqual(code, 1, out)
        self.assertIn("finalize: ", out)
        self.assertIn("but the run that answers is", out)

    def test_a_reported_run_without_its_analysis_audit_blocks(self):
        code, out = self._gate(self._area(f"AUC 0.91 ({self.RUN})", audited=False))
        self.assertEqual(code, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)


if __name__ == "__main__":
    unittest.main()
