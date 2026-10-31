"""labkit-adopt — the adoption, the report's result block and the check in
one command, stopping at the first step that does not pass.

The plan (docs/notes/2026-10-30-agent-surface.md, step 4): in round 1 four
agents ran and never adopted; the adoption took three commands in order.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.gates import report_context  # noqa: E402
from labkit.formats import protocol_block  # noqa: E402
from labkit.formats import standard_contract as sc  # noqa: E402
from labkit.tools import adopt  # noqa: E402
from test_end_to_end import Lab, stamp_count  # noqa: E402


class Adopt(unittest.TestCase):
    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)

    def labkit_adopt(self, area: Path, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        old = Path.cwd()
        os.chdir(self.lab.root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                rc = adopt.main([str(area), *args])
        finally:
            os.chdir(old)
        return rc, out.getvalue()

    def measured(self, report_file: str | None) -> tuple[Path, Path, str]:
        area, protocol = stamp_count(self.lab, report_file=report_file)
        run_id = self.lab.run_id_of(self.lab.script(area, "01_measure.py"))
        return area, protocol, run_id

    def test_an_audited_run_is_adopted_written_into_the_report_and_checked(self):
        area, protocol, run_id = self.measured("REPORT.md")
        self.lab.record(area, protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out = self.labkit_adopt(area, run_id)
        self.assertEqual(rc, 0, out)
        text = protocol.read_text(encoding="utf-8")
        self.assertEqual(protocol_block.declared_run(text), run_id)
        report = (self.lab.root / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn(run_id, report)
        self.assertIn("labkit-adopt: 3. check", out)
        self.assertIn("finalized, audited, checked", out)
        # again: the adoption is skipped, the block stands, the check passes
        rc, out = self.labkit_adopt(area, run_id)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"has adopted {run_id} already", out)

    def test_an_unaudited_run_is_refused_and_nothing_is_written(self):
        """The twin: the same run before its analysis audit stops at step 1,
        the protocol as it was and no report written."""
        area, protocol, run_id = self.measured("REPORT.md")
        before = protocol.read_text(encoding="utf-8")
        rc, out = self.labkit_adopt(area, run_id)
        self.assertEqual(rc, 1, out)
        self.assertEqual(protocol.read_text(encoding="utf-8"), before)
        self.assertFalse((self.lab.root / "REPORT.md").exists())
        self.assertNotIn("2. report", out)

    def test_a_refused_report_step_keeps_the_adoption_and_a_call_resumes(self):
        """Step 2 refuses a report whose block does not read; the adoption
        of step 1 stands and the refusal names the line to run again. Once
        the report is repaired, the same call without a run id resumes at
        step 2 (the twin: it passes)."""
        area, protocol, run_id = self.measured("REPORT.md")
        self.lab.record(area, protocol, sc.ANALYSIS_AUDIT, run_id)
        report = self.lab.root / "REPORT.md"
        report.write_text(
            "# Report\n\n<!-- labkit result: x run y (z) -->\nunclosed\n",
            encoding="utf-8",
        )
        rc, out = self.labkit_adopt(area, run_id)
        self.assertNotEqual(rc, 0, out)
        self.assertEqual(
            protocol_block.declared_run(protocol.read_text(encoding="utf-8")), run_id
        )
        self.assertIn(f"step 2 refused; {run_id} stays adopted", out)
        self.assertIn(f"`labkit-adopt experiments/01-lines {run_id}` resumes", out)
        report.write_text("# Report\n", encoding="utf-8")
        rc, out = self.labkit_adopt(area)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"has adopted {run_id} already", out)
        self.assertIn(run_id, report.read_text(encoding="utf-8"))

    def test_a_refused_check_step_keeps_the_written_report_and_a_call_resumes(self):
        """Step 3 refuses after step 2 wrote the report's block — another
        state than a refused step 2: the adoption and the block stand, the
        refusal says so; the next call skips the adoption, finds the block
        unchanged and checks again (the twin: it passes)."""
        from unittest import mock

        from labkit.gates import report_check

        area, protocol, run_id = self.measured("REPORT.md")
        self.lab.record(area, protocol, sc.ANALYSIS_AUDIT, run_id)
        report = self.lab.root / "REPORT.md"
        real = report_check.report_check
        calls: list[str] = []

        def refusing_on_the_tree(*args, **kw):
            if kw.get("state", report_context.TREE) == report_context.TREE:
                calls.append("tree")
                return 1
            return real(*args, **kw)

        with mock.patch.object(report_check, "report_check", refusing_on_the_tree):
            rc, out = self.labkit_adopt(area, run_id)
        self.assertEqual((rc, calls), (1, ["tree"]), out)
        self.assertIn(f"step 3 refused; {run_id} stays adopted", out)
        written = report.read_text(encoding="utf-8")
        self.assertIn(run_id, written)
        rc, out = self.labkit_adopt(area)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"has adopted {run_id} already", out)
        self.assertIn("unchanged", out)
        self.assertEqual(report.read_text(encoding="utf-8"), written)

    def test_no_registered_report_skips_the_report_step(self):
        area, protocol, run_id = self.measured(None)
        self.lab.record(area, protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out = self.labkit_adopt(area)
        self.assertEqual(rc, 0, out)
        self.assertIn("none registered", out)
        text = protocol.read_text(encoding="utf-8")
        self.assertEqual(protocol_block.declared_run(text), run_id)


if __name__ == "__main__":
    unittest.main()
