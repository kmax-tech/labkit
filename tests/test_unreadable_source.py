"""A scope file that is not Python is one blocker, not a traceback.

Audit 2026-10-15: with a `lib/` in the repo the import walk
(`scope_sha._lib_names`) raised ValueError from inside preflight station 3
and code-check — a traceback, exit 1, and so NOT blocking in the pre-run
hook: a stale `analysis/old.py` with a syntax error let a frozen area's
run command through. The twin: the same area with the file fixed is clean.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import DEFAULT_BLOCK, head, scope_file

from labkit import code_check, preflight, scope_sha


class UnreadableSource(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        (self.repo / "lib").mkdir()
        (self.repo / "CLAUDE.md").write_text("", encoding="utf-8")
        self.area = self.repo / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(
            head(promises=DEFAULT_BLOCK) + "\n- **Question / hypothesis:** [C1] q\n",
            encoding="utf-8",
        )
        (self.area / "analysis").mkdir()
        self.stale = self.area / "analysis" / "old.py"
        self.stale.write_text("def broken(:\n", encoding="utf-8")

    def test_code_check_reports_one_blocker(self):
        for findings in (
            code_check.check_intent_ids(self.area, self.protocol),
            code_check.stamp_coverage_findings(self.area, self.repo),
        ):
            with self.subTest(findings=findings):
                self.assertEqual(len(findings), 1)
                self.assertTrue(findings[0].startswith("BLOCKER"))
                self.assertIn("old.py", findings[0])
                self.assertIn("cannot be read", findings[0])

    def test_preflight_blocks_instead_of_a_traceback(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = preflight.preflight_area(self.area, self.protocol)
        self.assertEqual(code, 1)
        self.assertIn("old.py", out.getvalue())
        self.assertIn("BLOCKER", out.getvalue())

    def test_twin_a_readable_scope_is_clean_here(self):
        self.stale.write_text("def fine():\n    return 1\n", encoding="utf-8")
        for findings in (
            code_check.check_intent_ids(self.area, self.protocol),
            code_check.stamp_coverage_findings(self.area, self.repo),
        ):
            # the fixture's warnings (static evidence) stay; no blocker, no traceback
            self.assertEqual([f for f in findings if f.startswith("BLOCKER")], [])

    def test_the_error_names_the_file(self):
        with self.assertRaises(scope_sha.SourceError) as cm:
            scope_sha.imported_repo_helpers(self.area, self.repo)
        self.assertIn("old.py", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
