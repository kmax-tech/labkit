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

from labkit.checks import code_check, import_check
from labkit.gates import preflight
from labkit.formats import scope_sha


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
            head(promises=DEFAULT_BLOCK)
            + "\n- **Question / hypothesis:** [criterion-1] q\n",
            encoding="utf-8",
        )
        (self.area / "analysis").mkdir()
        self.stale = self.area / "analysis" / "old.py"
        self.stale.write_text("def broken(:\n", encoding="utf-8")

    def test_code_check_reports_one_blocker(self):
        for findings in (
            [f.line for f in code_check.check_intent_ids(self.area, self.protocol)],
            [
                f.line
                for f in import_check.stamp_coverage_findings(self.area, self.repo)
            ],
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
            [f.line for f in code_check.check_intent_ids(self.area, self.protocol)],
            [
                f.line
                for f in import_check.stamp_coverage_findings(self.area, self.repo)
            ],
        ):
            # the fixture's warnings (static evidence) stay; no blocker, no traceback
            self.assertEqual([f for f in findings if f.startswith("BLOCKER")], [])

    def test_the_error_names_the_file(self):
        with self.assertRaises(scope_sha.SourceError) as cm:
            scope_sha.imported_repo_helpers(self.area, self.repo)
        self.assertIn("old.py", str(cm.exception))


class UnreadableSourceWithoutLib(unittest.TestCase):
    """Audit 2026-10-18: without a `lib/` the import walk parses nothing, so a
    broken script with a `constants` promise reached a bare `ast.parse` in
    the constant check — the traceback of 0.93.0 again, by another door."""

    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        (self.repo / "CLAUDE.md").write_text("", encoding="utf-8")
        self.area = self.repo / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        self.script = scope_file(self.area)
        self.script.write_text("margin = 0.25\ndef f(:\n    pass\n", encoding="utf-8")
        block = DEFAULT_BLOCK.replace(
            'scope = ["scripts/01_measure.py"]\n\n[[promise]]\nid = "quality-check-1"',
            'scope = ["scripts/01_measure.py"]\nconstants = { margin = 0.25 }\n\n'
            '[[promise]]\nid = "quality-check-1"',
        )
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(
            head(promises=block) + "\n- **Question / hypothesis:** [criterion-1] q\n",
            encoding="utf-8",
        )

    def test_one_blocker_not_a_traceback(self):
        findings = [
            f.line for f in code_check.check_intent_ids(self.area, self.protocol)
        ]
        self.assertEqual(len(findings), 1, findings)
        self.assertTrue(findings[0].startswith("BLOCKER"))
        self.assertIn("01_measure.py", findings[0])

    def test_twin_the_fixed_script_passes(self):
        self.script.write_text(
            'margin = 0.25\ndef evaluate_rows(rows):\n    return {"criterion_1_pass": True, "quality_check_1_pass": True, "quality_check_2_pass": True}\n',
            encoding="utf-8",
        )
        findings = [
            f.line for f in code_check.check_intent_ids(self.area, self.protocol)
        ]
        self.assertEqual([f for f in findings if f.startswith("BLOCKER")], [])


if __name__ == "__main__":
    unittest.main()
