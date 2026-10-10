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
        msg = repo.no_such_area(Path("/nope"))
        self.assertTrue(msg.startswith("no such area: /nope — "), msg)
        self.assertNotIn("relative to", msg)

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


class BareName(unittest.TestCase):
    """`01-<name>` and `<name>`, as `labkit-init exp` prints them, find the area
    (2026-10-07: two agents were refused for `01-docs-per-case`)."""

    def resolve(self, arg: str) -> Path:
        old = Path.cwd()
        try:
            os.chdir(self.root)
            return repo.area_path(arg)
        finally:
            os.chdir(old)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / "experiments" / "01-docs-per-case").mkdir(parents=True)

    def test_the_numbered_name_finds_the_area(self):
        self.assertEqual(
            self.resolve("01-docs-per-case"),
            self.root / "experiments" / "01-docs-per-case",
        )

    def test_the_slug_alone_finds_it(self):
        self.assertEqual(
            self.resolve("docs-per-case"),
            self.root / "experiments" / "01-docs-per-case",
        )

    def test_an_unknown_name_stays_as_given(self):
        self.assertEqual(self.resolve("nope"), Path("nope"))


if __name__ == "__main__":
    unittest.main()
