"""A missing area names the directory a relative path resolved against
(2026-10-07: an agent ran code-check from inside the area with the
repo-relative path and tried four spellings)."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from labkit import code_check, repo


class NoSuchArea(unittest.TestCase):
    def test_a_relative_path_names_the_working_directory(self):
        msg = repo.no_such_area(Path("experiments/01-x"))
        self.assertIn(f"relative to {Path.cwd()}", msg)

    def test_an_absolute_path_needs_no_anchor(self):
        self.assertEqual(repo.no_such_area(Path("/nope")), "no such area: /nope")

    def test_code_check_says_it(self):
        old = Path.cwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = code_check.main(["experiments/01-x"])
            finally:
                os.chdir(old)
        self.assertNotEqual(rc, 0)
        self.assertIn("relative to", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
