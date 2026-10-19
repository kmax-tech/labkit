"""finalize looks for the area's tests where preflight does.

Audit 2026-10-15: preflight asked `layout_root(area)`, finalize
`git_root(area) or area` — in a stamped tree before `git init` preflight
ran the failing `tests/test_01_x.py` and finalize reported "none".
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from labkit.gates import finalize, preflight
from labkit.formats.repo import layout_root


class SameRoot(unittest.TestCase):
    def test_a_stamped_tree_before_git_init(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            (root / "CLAUDE.md").write_text("x", encoding="utf-8")
            area = root / "experiments" / "01-x"
            area.mkdir(parents=True)
            (root / "tests" / "test_01_x.py").write_text(
                "def test_x():\n    assert False\n", encoding="utf-8"
            )
            self.assertEqual(
                preflight.area_tests(area, layout_root(area)).state, "failed"
            )
            findings = finalize.Findings()
            with contextlib.redirect_stdout(io.StringIO()):
                finalize.check_area_tests(findings, area)
            self.assertEqual(len(findings.blocked), 1)


if __name__ == "__main__":
    unittest.main()
