"""calltree: the tree of one run, cut to the target's package, counted per path."""

import io
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from labkit import calltree

ENTRY = """
import sys
from . import helper


def cli():
    print("args", sys.argv[1:])
    helper.twice()
    sorted([3, 1, 2], key=helper.key)
    if "--fail" in sys.argv:
        raise ValueError("boom")
    sys.exit(3 if "--three" in sys.argv else 0)
"""

HELPER = """
import json


def leaf():
    return json.dumps({})


def twice():
    leaf()
    leaf()


def key(x):
    return x
"""


class Calltree(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        # a fresh package name per test: the import cache must not hand back an earlier one
        self.pkg = f"ctpkg_{self._testMethodName}"
        pkg = self.dir / self.pkg
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "entry.py").write_text(textwrap.dedent(ENTRY))
        (pkg / "helper.py").write_text(textwrap.dedent(HELPER))
        sys.path.insert(0, str(self.dir))
        self.addCleanup(sys.path.remove, str(self.dir))

    def run_main(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = calltree.main([f"{self.pkg}.entry:cli", *extra])
        return code, out.getvalue(), err.getvalue()

    def tree_lines(self, err):
        return [ln for ln in err.splitlines() if not ln.startswith("---")]

    def test_tree_holds_only_package_functions_with_counts(self):
        code, out, err = self.run_main("--", "a")
        self.assertEqual(code, 0)
        self.assertIn("args ['a']", out)
        labels = [ln.strip().split("  ")[0] for ln in self.tree_lines(err)]
        e, h = f"{self.pkg}.entry", f"{self.pkg}.helper"
        self.assertEqual(labels, [f"{e}.cli", f"{h}.twice", f"{h}.leaf", f"{h}.key"])
        lines = self.tree_lines(err)
        self.assertTrue(lines[2].endswith("×2"), lines[2])  # leaf, twice on one path
        self.assertTrue(lines[3].endswith("×3"), lines[3])  # key, via sorted()
        # depth: helper.leaf hangs under twice, key under cli across the stdlib's sorted
        self.assertEqual([len(ln) - len(ln.lstrip()) for ln in lines], [0, 2, 4, 2])

    def test_location_is_path_line_of_the_definition(self):
        _, _, err = self.run_main()
        twice = next(ln for ln in self.tree_lines(err) if ".twice" in ln)
        path, line = twice.strip().split("  ")[1].rsplit(":", 1)
        self.assertTrue(path.endswith(f"{self.pkg}/helper.py"), path)
        self.assertEqual(int(line), 9)

    def test_exit_code_is_the_commands_own(self):
        code, _, _ = self.run_main("--three")
        self.assertEqual(code, 3)

    def test_an_exception_propagates_after_the_tree(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            with self.assertRaisesRegex(ValueError, "boom"):
                calltree.main([f"{self.pkg}.entry:cli", "--fail"])
        self.assertIn(f"{self.pkg}.entry.cli", err.getvalue())

    def test_depth_cuts_the_tree(self):
        _, _, err = self.run_main()
        full = self.tree_lines(err)
        err_cut = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err_cut):
            calltree.main(["--depth", "1", f"{self.pkg}.entry:cli"])
        self.assertEqual(len(full), 4)
        self.assertEqual(len(self.tree_lines(err_cut.getvalue())), 1)

    def test_argv_is_restored(self):
        before = list(sys.argv)
        self.run_main("x")
        self.assertEqual(sys.argv, before)


class Targets(unittest.TestCase):
    def test_console_script_resolves_to_its_function(self):
        self.assertEqual(
            calltree.resolve_target("labkit-params"), ("labkit.params", "cli")
        )

    def test_module_function_form(self):
        self.assertEqual(calltree.resolve_target("a.b:c"), ("a.b", "c"))

    def test_unknown_script_fails_loud(self):
        with self.assertRaisesRegex(calltree.CalltreeError, "no console script"):
            calltree.resolve_target("no-such-script-xyz")

    def test_bad_depth_fails_loud(self):
        with self.assertRaisesRegex(calltree.CalltreeError, "positive integer"):
            calltree.parse_args(["--depth", "0", "x:y"])


if __name__ == "__main__":
    unittest.main()
