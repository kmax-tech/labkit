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

    def test_the_name_is_read_by_the_area_name_grammar_not_a_glob(self):
        """`[0-9]*-<name>` matched `02-count-docs` for `docs` too — a false
        "matches 2 areas" — and `*` matched every numbered area (audit
        2026-10-27, step 1.4). A bare name names the area called so or
        `NN-<name>` (`repo.AREA_NAME`), nothing else."""
        exp = self.root / "experiments"
        (exp / "02-count-docs").mkdir()
        (exp / "03-docs-per-case-v2").mkdir()
        (exp / "4x-docs").mkdir()  # no area name: the number is not digits
        self.assertEqual(self.resolve("docs-per-case"), exp / "01-docs-per-case")
        self.assertEqual(self.resolve("count-docs"), exp / "02-count-docs")
        self.assertEqual(self.resolve("docs"), Path("docs"))
        self.assertEqual(self.resolve("*"), Path("*"))
        self.assertEqual(
            repo.areas_named(exp, "docs-per-case"), [exp / "01-docs-per-case"]
        )
        self.assertEqual(repo.areas_named(exp, "4x-docs"), [exp / "4x-docs"])
        self.assertEqual(repo.areas_named(self.root / "none", "docs"), [])

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


class AmbiguousName(unittest.TestCase):
    """A name two areas carry (`01-x`, `02-x`, called with `x`) was refused
    as "no such area … give its name" — the name it was given (review,
    2026-10-20). It names the candidates and asks for one path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        for name in ("01-x", "02-x", "03-y"):
            (self.root / "experiments" / name).mkdir(parents=True)

    def in_root(self, call):
        old = Path.cwd()
        os.chdir(self.root)
        try:
            return call()
        finally:
            os.chdir(old)

    def test_the_ambiguous_name_names_every_candidate(self):
        with self.assertRaises(repo.AmbiguousArea) as cm:
            self.in_root(lambda: repo.area_path("x"))
        said = str(cm.exception)
        self.assertIn("experiments/01-x", said)
        self.assertIn("experiments/02-x", said)
        self.assertNotIn("no such area", said)

    def test_a_unique_and_a_missing_name_are_unchanged(self):
        self.assertEqual(
            self.in_root(lambda: repo.area_path("y")),
            self.root / "experiments" / "03-y",
        )
        self.assertEqual(
            self.in_root(lambda: repo.area_path("01-x")),
            self.root / "experiments" / "01-x",
        )
        self.assertEqual(self.in_root(lambda: repo.area_path("z")), Path("z"))

    def test_every_command_refuses_with_the_candidates(self):
        from labkit.gates import audit, finalize, preflight, report_check
        from labkit.run import runlog_command
        from labkit.tools import params

        commands = {
            "code-check": lambda: code_check.main(["x"]),
            "finalize": lambda: finalize.main(["x"]),
            "preflight": lambda: preflight.main(["x"]),
            "params": lambda: params.main(["x"]),
            "runlog": lambda: runlog_command.main(["x"]),
            "labkit-audit": lambda: audit.main(["x", "--mode", "analysis"]),
            "report-check": lambda: report_check.main(["x"]),
        }
        for name, call in commands.items():
            with self.subTest(command=name):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    try:
                        rc = self.in_root(call)
                    except SystemExit as exc:
                        rc = exc.code
                self.assertEqual(rc, 2, out.getvalue() + err.getvalue())
                self.assertIn("experiments/02-x", err.getvalue())
                self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
