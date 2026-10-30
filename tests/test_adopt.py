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
