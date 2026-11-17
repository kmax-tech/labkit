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
import re
import time
import unittest
from collections.abc import Mapping
from pathlib import Path

import pytest

from labkit.formats import runs
from labkit.formats.runs import RUN_ID_TIME
from labkit.checks import recheck
from labkit.checks.audit_binding import (
    NOT_RECONSTRUCTED,
    SOURCE_PROTOCOL_LABEL,
    run_rows,
)
from labkit.gates import report_check
from labkit.gates.finalize import finalize_area
from labkit.formats import standard_contract as sc
from labkit.formats import protocol_block
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
        self.assertNotIn(a1, prompt_c)
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


if __name__ == "__main__":
    unittest.main()
