"""The input-origins station's hold reaches every gate that runs finalize,
on the real chain: run A of the counting skeleton writes its rows, run C
reads them as an input (its record names A as the origin), C is audited,
adopted and committed through the hooks. Then A's run directory is
removed and staged: finalize, report-check, the stop hook and the
pre-commit on the staged protocol all hold C, naming the origin. Restored
from git, every one of them passes again — the way out the blocker names.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import time
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

import pytest

from labkit.formats import gate, runs
from labkit.formats.runs import RUN_ID_TIME
from labkit.checks import recheck
from labkit.checks.audit_binding import (
    NOT_RECONSTRUCTED,
    SOURCE_PROTOCOL_LABEL,
    run_rows,
)
from labkit.gates import audit, report_check
from labkit.gates.finalize import finalize_area
from labkit.formats import standard_contract as sc
from labkit.formats import protocol_block
from labkit.tools import protocol_fill
from test_end_to_end import CountCommands, Lab, stamp_count

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow


def _pointed(text: str, source_run_out: Path) -> str:
    """The measure script TEXT reading SOURCE_RUN_OUT as its frozen input
    and writing its own rows beside it under another name, so the source's
    file stays as its run registered it."""
    text, n_in = re.subn(
        r"^INPUTS = None .*$",
        f'INPUTS = AREA / "output" / "{source_run_out.name}"',
        text,
        flags=re.M,
    )
    text, n_out = re.subn(
        r'^OUT = AREA / "output" / "([^"]+)\.jsonl"',
        r'OUT = AREA / "output" / "\1-compared.jsonl"',
        text,
        flags=re.M,
    )
    assert (n_in, n_out) == (1, 1), (n_in, n_out)
    return text


def _point_script_at(measure: Path, source_run_out: Path) -> None:
    """MEASURE rewritten in place as `_pointed` gives it."""
    text = measure.read_text(encoding="utf-8")
    measure.write_text(_pointed(text, source_run_out), encoding="utf-8")


class OriginHeldThroughTheHooks(unittest.TestCase):
    """C reads A's output; A gone holds C at every gate, restored passes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        cls.area, cls.protocol = stamp_count(cls.lab)
        cls.measure = cls.area / "scripts" / "01_measure.py"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def report_check(self) -> tuple[int, str]:
        """`report-check AREA`, the whole gate."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report_check.protocol_verdict(self.area).exit
        return code, out.getvalue()

    def test_a_gone_origin_holds_every_gate_until_restored(self) -> None:
        lab = self.lab
        # A starts with a line of its protocol not yet committed: what it was
        # measured under is its commit with its uncommitted.patch
        text = self.protocol.read_text(encoding="utf-8")
        assert RUNS_LINE in text
        self.protocol.write_text(
            text.replace(RUNS_LINE, f"{RUNS_LINE}\n{THEN}"), encoding="utf-8"
        )
        source = lab.run_id_of(lab.script(self.area, "01_measure.py"))
        patch = self.area / "runs" / source / "uncommitted.patch"
        (written,) = runs.read_outputs(self.area / "runs" / source) or []
        lab.commit("run A, its rows")
        _point_script_at(self.measure, written.path)
        lab.commit("the script reads A's rows")
        compared = lab.run_id_of(lab.script(self.area, "01_measure.py"))
        entries = runs.read_data(self.area / "runs" / compared) or []
        self.assertEqual(
            {e.key: e.origin_run for e in entries}, {"source": None, "inputs": source}
        )

        # the twin: the origin intact, every gate passes on C
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"the output of {source} (decided by digest)", out)
        lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, compared)
        # A's patch lost: the protocol A was measured under cannot be read
        # back, so finalize holds C and the adoption is refused
        lab.git("rm", "-q", str(patch))
        unread = (
            f"the protocol origin run {source} was measured under cannot be read back"
        )
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn(unread, out)
        self.assertIn("its uncommitted.patch is gone", out)
        rc, out = lab.adopt(self.protocol, compared)
        self.assertNotEqual(rc, 0, out)
        self.assertIn(unread, out)
        # restored from git, the adoption passes
        lab.git("reset", "-q", "HEAD", "--", str(patch))
        lab.git("checkout", "--", str(patch))
        rc, out = lab.adopt(self.protocol, compared)
        self.assertEqual(rc, 0, out)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual(rc, 0, out)
        lab.commit("C adopted")
        self.assertEqual(self.report_check()[0], 0)
        # the area's own check recomputes C from the inputs it recorded, with
        # the code C ran; once that code changed it refuses instead of
        # recomputing with other code, and restored it holds again
        told = lab.script(self.area, "02_analyze.py", "--check")
        self.assertIn("recomputed from its recorded inputs, the same numbers", told)
        as_it_ran = self.measure.read_text(encoding="utf-8")
        self.measure.write_text(as_it_ran + "# changed after C ran\n", encoding="utf-8")
        with self.assertRaises(AssertionError) as cm:
            lab.script(self.area, "02_analyze.py", "--check")
        self.assertIn(f"the code that computed run {compared}", str(cm.exception))
        self.assertIn("no recalculation of that run", str(cm.exception))
        self.measure.write_text(as_it_ran, encoding="utf-8")
        lab.script(self.area, "02_analyze.py", "--check")

        # C's record no longer says which script it ran: nothing shows the
        # code here is C's, so the check ends not verifiable — no number
        # compared — and report-check holds the adopted result as a check
        # not executed; the record restored from git, both pass again
        record = self.area / "runs" / compared / "config.json"
        cfg = json.loads(record.read_text(encoding="utf-8"))
        record.write_text(
            json.dumps({**cfg, "script_sha": "no-script"}), encoding="utf-8"
        )
        with self.assertRaises(AssertionError) as cm:
            lab.script(self.area, "02_analyze.py", "--check")
        self.assertIn(f"run {compared} is not verifiable", str(cm.exception))
        self.assertNotIn("keys identical", str(cm.exception))
        rc, out = self.report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn(
            f"--check --protocol {self.protocol.name} exits 1: recheck: run "
            f"{compared} is not verifiable",
            out,
        )
        self.assertIn(gate.NOT_EXECUTABLE_MARK, out)
        self.assertIn("or measure anew, audit and adopt that run", out)
        lab.git("checkout", "--", str(record))
        lab.script(self.area, "02_analyze.py", "--check")
        self.assertEqual(self.report_check()[0], 0)

        # A's run directory removed and the removal staged
        lab.git("rm", "-r", "-q", str(self.area / "runs" / source))
        gone = f"its origin run {source} is gone"
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn(gone, out)
        self.assertIn("restore the origin run's directory or record from git", out)
        rc, out = self.report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn(gone, out)
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 2, err)
        self.assertIn(gone, err)
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual(rc, 1, out)
        self.assertIn(gone, out)

        # the way out: restored from git, every gate passes again
        lab.git("reset", "-q", "HEAD", "--", str(self.area / "runs" / source))
        lab.git("checkout", "--", str(self.area / "runs" / source))
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.report_check()[0], 0)
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 0, err)
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual(rc, 0, out)


#: the measurement protocol's run list, and a line of it as A0 started
#: under it and as it reads for A1
RUNS_LINE = "- <run_id> — <one sentence: what this run was>"
THEN = "- planned: one count of the lines per document (written for A0)"
NOW = "- planned: count again into a file of its own (written for A1)"


def _recount(inputs: Mapping[str, Path]) -> dict:
    """The computation's evaluation over its recorded inputs: the mean
    line count of the documents under its `source` input."""
    counts = [
        len(f.read_text(encoding="utf-8").splitlines())
        for f in sorted(inputs["source"].iterdir())
        if not f.name.startswith(".")
    ]
    return {"lines_mean": sum(counts) / len(counts)}


class TwoProtocolsOfOneArea(CountCommands):
    """The target layout: the measurement protocol (the count, runs A0 and
    A1 by `01_measure.py`) and a computation protocol C in the same area,
    its own stamped id and script (`03_compare.py`), reading A0's rows.
    The station finds the origin in the other protocol's run, keeps it when
    the measurement is run again (A1), and holds C when that origin is gone; the measurement protocol's own result gets no
    finding from it. The measurement protocol changes between A0 and A1:
    C's auditor is shown it as A0 started under it (commit and patch), and
    told it cannot be read back once A0 is gone. Existing area or repository checks may hold too —
    asserted here is only the input-origins station's part of each gate's
    output."""

    def run_script(self, script: str) -> str:
        """SCRIPT of the area run in a later second than every run it holds
        (`CountCommands.measure`); its run id."""
        held = (self.area / "runs").iterdir() if (self.area / "runs").is_dir() else ()
        newest = max(
            (d.name[: len(time.strftime(RUN_ID_TIME))] for d in held), default=""
        )
        while time.strftime(RUN_ID_TIME) <= newest:
            time.sleep(0.02)
        return self.lab.run_id_of(self.lab.script(self.area, script))

    def station(self, protocol: Path) -> tuple[int, str]:
        """finalize on PROTOCOL: (exit, the input-origins station's lines)."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = finalize_area(self.area, protocol)
        text = out.getvalue()
        start = text.index("── input origins ──")
        return rc, text[start : text.index("── area tests ──", start)]

    def verdict(self, protocol: Path) -> tuple[int, str]:
        """report-check on PROTOCOL: (exit, everything it told)."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report_check.protocol_verdict(self.area, protocol).exit
        return code, out.getvalue()

    def test_c_is_held_by_its_origin_in_the_other_protocol_and_only_c(self):
        lab, measured = self.lab, self.protocol
        text = measured.read_text(encoding="utf-8")
        pid = protocol_block.head(text).id
        assert pid is not None and RUNS_LINE in text
        computed = self.area / "PROTOCOL-compared.md"
        computed.write_text(text.replace(pid, "p-0123456789abcdef"), encoding="utf-8")
        # A0 starts with a line of the measurement protocol not yet committed:
        # its uncommitted.patch holds it
        measured.write_text(text.replace(RUNS_LINE, f"{RUNS_LINE}\n{THEN}"), "utf-8")
        a0 = self.run_script("01_measure.py")
        (written,) = runs.read_outputs(self.area / "runs" / a0) or []
        script = (self.area / "scripts" / "01_measure.py").read_text(encoding="utf-8")
        bound = f'"{measured.name}"'
        assert bound in script
        (self.area / "scripts" / "03_compare.py").write_text(
            _pointed(script.replace(bound, f'"{computed.name}"'), written.path),
            encoding="utf-8",
        )
        lab.commit("the computation protocol beside the measurement")
        c = self.run_script("03_compare.py")
        # A1 writes its rows to a file of its own: a rerun into A0's file
        # would change the bytes C read (its rows carry their run id), which
        # station 6 and this station rightly name
        measure = self.area / "scripts" / "01_measure.py"
        measure.write_text(
            script.replace('"lines.jsonl"', '"lines-again.jsonl"'), encoding="utf-8"
        )
        # the measurement protocol changed for A1; C still reads A0's rows
        measured.write_text(text.replace(RUNS_LINE, f"{RUNS_LINE}\n{NOW}"), "utf-8")
        lab.commit("C, and the measurement writes anew to its own file")
        a1 = self.run_script("01_measure.py")
        lab.commit("A1")
        (origin,) = [
            e.origin_run
            for e in runs.read_data(self.area / "runs" / c) or []
            if e.key == "inputs"
        ]
        self.assertEqual(origin, a0)

        # each protocol answered by its own run; the origin found across protocols
        rc, told = self.station(computed)
        self.assertEqual(rc, 0, told)
        self.assertIn(f"the output of {a0} (decided by digest)", told)
        rc, told = self.station(measured)
        self.assertEqual(rc, 0, told)
        self.assertNotIn(a0, told)  # A1's inputs name no origin
        # the audit of each protocol is shown its own run's origins
        _, _, prompt_c = self.analysis(self.clean, computed)
        _, _, prompt_m = self.analysis(self.clean, measured)
        self.assertIn(f"the output of {a0}", prompt_c)
        self.assertIn("INPUT ORIGINS", prompt_m)
        self.assertNotIn(f"the output of {a0}", prompt_m)
        self.assertNotIn(c, prompt_m)
        # A1 stands among the source protocol's runs (`protocol_runs`), never
        # as an origin or a source text of C
        before_runs = prompt_c.split("===== RUNS OF ", 1)[0]
        self.assertNotIn(a1, before_runs)
        self.assertIn(f"- {a1}: completed, measurement", prompt_c)
        # C's auditor is shown the measurement protocol as A0 started under
        # it — commit and patch —, never as it reads now for A1
        source = prompt_c.split(f"===== SOURCE PROTOCOL {a0} =====", 1)[1]
        source = source.split("\n===== ", 1)[0]
        self.assertIn(f"as origin run {a0} saw it", source)
        self.assertIn("with its uncommitted.patch", source)
        self.assertIn(THEN, source)
        self.assertNotIn(NOW, prompt_c)
        self.assertNotIn(THEN, computed.read_text(encoding="utf-8"))

        # recheck over C's inputs: pinned, then recomputed — A0 is not run again
        note = self.area / "notes-compared.md"
        note.write_text(f"lines_mean 3.0, run {c}\n", encoding="utf-8")
        verdict = recheck.holds_from_inputs(
            self.area, _recount, note, run_id=c, protocol=computed
        )
        # held at all: C's script and modules are shown to be as it ran them
        self.assertEqual((verdict.run_id, verdict.out), (c, None))

        # A0's patch lost: A0's protocol then cannot be read back — C held at
        # finalize and report-check, its auditor told why, the measurement
        # protocol not held by it; restored from git, C passes again
        patch = self.area / "runs" / a0 / "uncommitted.patch"
        lab.git("rm", "-q", str(patch))
        unread = f"the protocol origin run {a0} was measured under cannot be read back"
        rc, told = self.station(computed)
        self.assertEqual(rc, 1, told)
        self.assertIn(unread, told)
        code, out = self.verdict(computed)
        self.assertEqual(code, 1, out)
        self.assertIn(unread, out)
        _, told = self.station(measured)
        self.assertNotIn(unread, told)
        pieces = dict(run_rows(self.area, self.area / "runs" / c, ""))
        told = pieces[f"{SOURCE_PROTOCOL_LABEL}{a0}"]
        self.assertTrue(told.startswith(NOT_RECONSTRUCTED), told)
        self.assertIn("its uncommitted.patch is gone", told)
        self.assertNotIn(NOW, told)
        lab.git("reset", "-q", "HEAD", "--", str(patch))
        lab.git("checkout", "--", str(patch))
        rc, told = self.station(computed)
        self.assertEqual(rc, 0, told)
        self.assertIn(f"its protocol then: as origin run {a0} saw it", told)
        # A0 is held to that text, not to the protocol as it reads for A1
        self.assertIn(f"{a0}, held to that text: no mismatch", told)

        # A0 gone: C held, naming it; the measurement's result untouched by the station
        lab.git("rm", "-r", "-q", str(self.area / "runs" / a0))
        with self.assertRaises(SystemExit) as cm:
            recheck.holds_from_inputs(
                self.area, _recount, note, run_id=c, protocol=computed
            )
        self.assertIn(f"its origin run {a0} is gone", str(cm.exception.code))
        gone = f"its origin run {a0} is gone"
        rc, told = self.station(computed)
        self.assertEqual(rc, 1, told)
        self.assertIn(
            f"BLOCKER: data['inputs'] = {written.path.relative_to(lab.root.resolve()).as_posix()}: {gone}",
            told,
        )
        _, told = self.station(measured)
        self.assertIn("an input without origin", told)  # the station ran on A1
        self.assertNotIn("BLOCKER", told)
        code, out = self.verdict(computed)
        self.assertEqual(code, 1, out)
        self.assertIn(gone, out)
        _, out = self.verdict(measured)
        self.assertNotIn(
            gone, out
        )  # other checks may hold it: the committed run's removal
        # and C's auditor is told the source protocol cannot be read back,
        # with no other text in its place
        pieces = dict(run_rows(self.area, self.area / "runs" / c, ""))
        told = pieces[f"{SOURCE_PROTOCOL_LABEL}{a0}"]
        self.assertTrue(told.startswith(NOT_RECONSTRUCTED), told)
        self.assertNotIn(THEN, told)
        self.assertNotIn(NOW, told)

    def held(self, *paths: Path) -> tuple[int, str]:
        """`report-check --if-reported PATHS`, the stop's hold on the tree."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report_check.hold_reported(
                list(paths), self.lab.root, staged=False
            ).exit
        return code, out.getvalue()

    def report_review(self, report: Path, protocol: Path) -> tuple[int, str]:
        """`labkit-audit AREA --report-review REPORT --protocol PROTOCOL`,
        the reader naming no claim: (exit, what it told)."""
        out = io.StringIO()
        with (
            mock.patch.object(
                audit.llm, "complete", lambda alias, prompt, **kw: "verdict: 0 claim(s)"
            ),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(out),
        ):
            rc = audit.main(
                [
                    str(self.area),
                    "--report-review",
                    str(report),
                    "--protocol",
                    str(protocol),
                ]
            )
        return rc, out.getvalue()

    def test_the_area_passes_with_no_measurement_run_ever_adopted(self):
        """The measurement protocol registered REPORT.md and reports no
        result of its own: its run A0 is an input of C, which the
        computation protocol adopts. No run of the measurement protocol is
        adopted at any point. C is recomputed by the check of its own
        protocol, with the script C ran; the measurement protocol having no
        answer holds nothing of C. Without the reported-through block the
        report hold names it with its command; written by that command, the
        block releases the report, A0's citation in it is no promotion, and
        the report's review stays owed. Reviewed, the whole area passes —
        both protocols and the report. The source stays held without an
        adoption of its own: A0 gone holds C and the report, restored they
        pass. C's adoption withdrawn, the block says something false."""
        lab, measured = self.lab, self.protocol
        text = measured.read_text(encoding="utf-8")
        pid = protocol_block.head(text).id
        assert pid is not None
        computed = self.area / "PROTOCOL-compared.md"
        computed.write_text(text.replace(pid, "p-0123456789abcdef"), encoding="utf-8")
        lab.fill(measured, "report=REPORT.md")
        lab.commit("the measurement registers its report")
        a0 = self.run_script("01_measure.py")
        (written,) = runs.read_outputs(self.area / "runs" / a0) or []
        script = (self.area / "scripts" / "01_measure.py").read_text(encoding="utf-8")
        bound = f'"{measured.name}"'
        (self.area / "scripts" / "03_compare.py").write_text(
            _pointed(script.replace(bound, f'"{computed.name}"'), written.path),
            encoding="utf-8",
        )
        lab.commit("A0, and the computation protocol beside the measurement")
        c = self.run_script("03_compare.py")
        rc, out, _ = self.analysis(self.clean, computed)
        self.assertEqual(rc, 0, out)
        rc, out = lab.adopt(computed, c)
        self.assertEqual(rc, 0, out)
        lab.commit("C adopted, the measurement has adopted no run")
        self.assertIsNone(
            protocol_block.declared_run(measured.read_text(encoding="utf-8"))
        )

        # the area's check, one protocol at a time: C by the script C ran;
        # the measurement's own state is its own, and with two protocols
        # the check takes none unnamed
        told = lab.script(
            self.area, "02_analyze.py", "--check", "--protocol", computed.name
        )
        self.assertIn(f"check: run {c} ", told)
        self.assertIn(f"{computed.name} carries them and the run_id", told)
        self.assertIn("recomputed from its recorded inputs, the same numbers", told)
        with self.assertRaises(AssertionError) as cm:
            lab.script(
                self.area, "02_analyze.py", "--check", "--protocol", measured.name
            )
        self.assertIn(f"recheck: {measured.name} has no answer yet", str(cm.exception))
        with self.assertRaises(AssertionError) as cm:
            lab.script(self.area, "02_analyze.py", "--check")
        self.assertIn("name one with --protocol FILE", str(cm.exception))
        code, out = self.verdict(computed)
        self.assertEqual(code, 0, out)

        report = lab.root / "REPORT.md"
        report.write_text("# Report\n\nThe comparison is below.\n", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = protocol_fill.main([str(computed), "--into", str(report)])
        self.assertEqual(rc, 0, out.getvalue())

        # without the block: the registered report is held, the way named
        code, told = self.held(report, measured)
        self.assertEqual(code, 1, told)
        self.assertIn(
            "nor the block saying its runs are reported through the adopted "
            f"analysis run {c}",
            told,
        )
        self.assertIn(f"--reported-through {c} --into", told)

        # the final form, written by the command the hold named
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = protocol_fill.main(
                [str(measured), "--reported-through", c, "--into", str(report)]
            )
        self.assertEqual(rc, 0, out.getvalue())
        body = report.read_text(encoding="utf-8")
        self.assertIn(
            f"Reported through p-0123456789abcdef, run {c}, adopted there: run "
            f"{a0} of {pid} is an input of that analysis; {pid} reports no result "
            "of its own.",
            body,
        )
        code, told = self.held(report, measured)
        self.assertNotIn("carries neither", told)
        self.assertNotIn("reported-through block", told)
        self.assertNotIn(f"cites {a0}", told)  # stated as an input, not promoted
        # the block replaces no review: the registered report owes its own
        self.assertEqual(code, 1, told)
        self.assertIn(f"{measured.name} registers and has no clean report review", told)

        # reviewed: the whole area passes — the measurement protocol through
        # its final form, C through its own chain, the report through both
        for protocol in (measured, computed):
            rc, out = self.report_review(report, protocol)
            self.assertEqual(rc, 0, out)
        everything = (
            report,
            measured,
            computed,
            self.area / "scripts" / "02_analyze.py",
        )
        code, told = self.held(*everything)
        self.assertEqual(code, 0, told)
        # C's chain ran
        self.assertIn(f"{computed.name} (its head has adopted {c})", told)
        self.assertIsNone(
            protocol_block.declared_run(measured.read_text(encoding="utf-8"))
        )
        lab.commit("the report, reviewed")
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 0, err)

        # the source is held without an adoption of its own: A0 gone holds
        # C; restored from git, the area passes again
        lab.git("rm", "-r", "-q", str(self.area / "runs" / a0))
        code, told = self.held(*everything)
        self.assertEqual(code, 1, told)
        self.assertIn(f"its origin run {a0} is gone", told)
        lab.git("reset", "-q", "HEAD", "--", str(self.area / "runs" / a0))
        lab.git("checkout", "--", str(self.area / "runs" / a0))
        code, told = self.held(*everything)
        self.assertEqual(code, 0, told)

        # C's adoption withdrawn: the block says something false and holds
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = protocol_fill.main(
                [str(computed), "--withdraw", "--why", "x", "--into", str(report)]
            )
        self.assertEqual(rc, 0, out.getvalue())
        code, told = self.held(report, measured)
        self.assertEqual(code, 1, told)
        self.assertIn(f"no protocol of {self.area.name} has adopted run {c}", told)
        self.assertIn("carries neither", told)


if __name__ == "__main__":
    unittest.main()
