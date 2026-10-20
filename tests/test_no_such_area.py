"""A missing area names the directory a relative path resolved against
(2026-10-07: an agent ran code-check from inside the area with the
repo-relative path and tried four spellings)."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from labkit.checks import code_check
from labkit.formats import repo


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
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    rc = code_check.main(["experiments/01-x"])
            finally:
                os.chdir(old)
        self.assertNotEqual(rc, 0)
        self.assertIn("relative to", err.getvalue())  # a usage error: stderr
        self.assertEqual(out.getvalue(), "")


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

    def test_audit_and_report_check_take_the_name(self):
        """Both took the argument as a plain path: `labkit-audit 01-<name>`
        was refused in four of seven cold probes (2026-10-20) while
        code-check and finalize took it. The area here is empty, so each
        refuses — for the empty area, not for a missing one."""
        from labkit.gates import audit, report_check

        commands = {
            "labkit-audit": lambda: audit.main(
                ["01-docs-per-case", "--mode", "analysis"]
            ),
            "report-check": lambda: report_check.main(["01-docs-per-case"]),
        }
        for name, call in commands.items():
            with self.subTest(command=name):
                old = Path.cwd()
                out, err = io.StringIO(), io.StringIO()
                os.chdir(self.root)
                try:
                    with (
                        contextlib.redirect_stdout(out),
                        contextlib.redirect_stderr(err),
                    ):
                        try:
                            rc = call()
                        except SystemExit as exc:
                            rc = exc.code
                finally:
                    os.chdir(old)
                said = out.getvalue() + err.getvalue()
                self.assertNotEqual(rc, 0, said)
                self.assertNotIn("no such area", said)


if __name__ == "__main__":
    unittest.main()
