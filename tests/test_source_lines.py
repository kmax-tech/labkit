"""C's sources in its result and in a report, on real commands: run A0 of
measurement protocol M writes rows, run C of computation protocol P reads
them. Adopted, P's Recorded results line carries A0's values under M's
text as A0 started under it (`result_render.source_phrases`), never M's
text of today; the report block of P carries the same line, and A0 cited
there as C's source owes no block of M and is no promotion
(`report_hold.drawn_citations`) — cited in prose, it still is.
"""

from __future__ import annotations

import contextlib
import io
import os
import unittest

import pytest

import test_end_to_end as e2e
from test_origin_scenario import _pointed

from labkit.formats import protocol_block, runs
from labkit.formats.protocol_check import recorded_results_field
from labkit.tools import protocol_fill, report_command

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

UNIT_THEN = 'unit = "lines"'
UNIT_NOW = 'unit = "text lines"'


class SourceLines(e2e.CountCommands):
    """M (the stamped count) measured as A0 and adopted; P a computation
    protocol in the same area whose script `03_compare.py` reads A0's
    rows; M's kept unit renamed after A0. C measured, audited and
    adopted. A0 being M's result is the stricter case for the report: a
    citation of it would owe M's block."""

    def run_script(self, script: str) -> str:
        return self.lab.measure(self.area, script)

    def setUp(self) -> None:
        super().setUp()
        text = self.protocol.read_text(encoding="utf-8")
        self.mid = protocol_block.head(text).id
        assert self.mid is not None and UNIT_THEN in text
        self.computed = self.area / "PROTOCOL-compared.md"
        self.computed.write_text(
            text.replace(self.mid, "p-0123456789abcdef"), encoding="utf-8"
        )
        self.a0 = self.run_script("01_measure.py")
        (written,) = runs.read_outputs(self.area / "runs" / self.a0) or []
        measure = self.area / "scripts" / "01_measure.py"
        script = measure.read_text(encoding="utf-8")
        bound = f'"{self.protocol.name}"'
        (self.area / "scripts" / "03_compare.py").write_text(
            _pointed(script.replace(bound, f'"{self.computed.name}"'), written.path),
            encoding="utf-8",
        )
        self.lab.commit("the computation beside the measurement")
        rel = self.area.relative_to(self.lab.root).as_posix()
        clean = f"{self.clean}\n{rel}/scripts/03_compare.py"
        # A0 adopted by M: the area's stamped check holds M's answer too
        rc, out, _ = self.analysis(clean, self.protocol)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, self.a0)
        self.assertEqual(rc, 0, out)
        # M today names its unit otherwise; A0 was measured under "lines"
        text = self.protocol.read_text(encoding="utf-8")
        self.protocol.write_text(text.replace(UNIT_THEN, UNIT_NOW), encoding="utf-8")
        self.lab.commit("A0 adopted; the measurement's unit renamed")
        self.c = self.run_script("03_compare.py")
        rc, out, _ = self.analysis(clean, self.computed)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.computed, self.c)
        self.assertEqual(rc, 0, out)
        self.lab.commit("C adopted")

    def report(self, prose: str = "") -> str:
        """REPORT.md with P's block written by `--into`, PROSE below it:
        what `report-check --if-reported` tells of the report itself — M's
        own section holds M for its unit renamed after its adoption, which
        is not the report's question."""
        report = self.lab.root / "REPORT.md"
        report.write_text("# Report\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = protocol_fill.main([str(self.computed), "--into", str(report)])
        self.assertEqual(rc, 0)
        if prose:
            with report.open("a", encoding="utf-8") as f:
                f.write(f"\n{prose}\n")
        out = io.StringIO()
        here = os.getcwd()
        os.chdir(self.lab.root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                report_command.main(["--if-reported", "REPORT.md"])
        finally:
            os.chdir(here)
        told = out.getvalue()
        section = told[told.index("═══ report-check REPORT.md") :]
        return section.split("\n═══ ", 1)[0]

    def test_the_result_names_a0_under_its_own_text(self):
        line = recorded_results_field(self.computed.read_text(encoding="utf-8"))
        assert line is not None
        self.assertIn(f"(run {self.c})", line)
        sources = line.split(" · sources: ", 1)[1]
        self.assertTrue(sources.startswith(f"{self.mid} as run {self.a0} saw it: "))
        self.assertIn("lines_mean = ", sources)
        self.assertIn(" lines", sources)
        self.assertNotIn("text lines", sources)  # M's unit of today
        self.assertTrue(sources.endswith(f"(run {self.a0})"), sources)

    def test_a0_in_c_s_block_owes_nothing_and_in_prose_it_does(self):
        told = self.report()
        report = (self.lab.root / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn(f"{self.mid} as run {self.a0} saw it", report)
        self.assertIn("report-check: all clear.", told)
        told = self.report(f"The counts come from run {self.a0}.")
        owed = [ln for ln in told.splitlines() if "BLOCKER" in ln and self.a0 in ln]
        self.assertNotEqual(owed, [], told)
        self.assertIn("without its generated block", owed[0])


if __name__ == "__main__":
    unittest.main()
