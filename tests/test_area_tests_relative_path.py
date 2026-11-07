"""`area_tests` on a relative area path: `preflight .` and `finalize .`
pass Path(".") whose .name is "", and the pattern is read from the resolved
area — never `tests/test_.py`, which would count the area's own test absent.

    .venv/bin/python -m pytest tests/test_area_tests_relative_path.py
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from labkit.gates.preflight import area_tests


class RelativeAreaPath(unittest.TestCase):
    def test_dot_names_the_areas_test(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d).resolve()
            area = repo / "experiments" / "07-span-detection"
            area.mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "tests" / "test_07_span_detection.py").write_text(
                "def test_x():\n    assert True\n", encoding="utf-8"
            )
            cwd = os.getcwd()
            os.chdir(area)
            try:
                t = area_tests(Path("."), repo)
            finally:
                os.chdir(cwd)
            self.assertEqual(t.pattern, "tests/test_07_span_detection.py")
            self.assertEqual([f.name for f in t.files], ["test_07_span_detection.py"])
            self.assertNotEqual(t.state, "none")


if __name__ == "__main__":
    unittest.main()
