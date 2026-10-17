"""A gate's subprocess has a time limit: a hanging area test or `--check`
hung preflight, finalize and report-check until the hook's own timeout
killed them, wordless (audit 2026-10-15). Over the limit is a failing
test, a failing check — said in the finding.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit import finalize, preflight


class Timeouts(unittest.TestCase):
    def test_a_hanging_area_test_is_a_failed_test(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "tests").mkdir()
            (repo / "tests" / "test_01_x.py").write_text(
                "import time\n\ndef test_x():\n    time.sleep(30)\n", encoding="utf-8"
            )
            area = repo / "experiments" / "01-x"
            area.mkdir(parents=True)
            with mock.patch.object(preflight, "AREA_TEST_TIMEOUT_S", 1.0):
                result = preflight.area_tests(area, repo)
            self.assertEqual(result.state, "failed")
            self.assertIn("timed out after 1 s", result.tail[0])

    def test_a_hanging_check_is_a_failed_check(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            area = repo / "experiments" / "01-x"
            (area / "scripts").mkdir(parents=True)
            (area / "scripts" / "02_analyze.py").write_text(
                "import time\ntime.sleep(30)\n", encoding="utf-8"
            )
            with mock.patch.object(finalize, "CHECK_TIMEOUT_S", 1.0):
                gap = finalize.check_analysis_script(area, repo)
            self.assertIsNotNone(gap)
            self.assertIn("did not finish in 1 s", gap or "")


if __name__ == "__main__":
    unittest.main()
