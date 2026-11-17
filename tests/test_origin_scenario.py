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
import unittest
from pathlib import Path

import pytest

from labkit.formats import runs
from labkit.gates import report_check
from labkit.formats import standard_contract as sc
from test_end_to_end import Lab, stamp_count

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow


def _point_script_at(measure: Path, source_run_out: Path) -> None:
    """The measure script reads SOURCE_RUN_OUT as its frozen input and
    writes its own rows beside it under another name, so the source's file
    stays as its run registered it."""
    text = measure.read_text(encoding="utf-8")
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
    measure.write_text(text, encoding="utf-8")


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
        source = lab.run_id_of(lab.script(self.area, "01_measure.py"))
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


if __name__ == "__main__":
    unittest.main()
