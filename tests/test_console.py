"""console: a reader that closes the pipe is exit 0 and no traceback; a\nrefusal is exit 2 on stderr, in every module."""

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClosedPipe(unittest.TestCase):
    def test_a_reader_closing_the_pipe_is_not_a_crash(self):
        # 400 kB past the pipe buffer, the reader takes one byte and leaves
        prog = (
            "from labkit.formats import console\n"
            "console.exit_with(lambda argv: (print('x' * 400_000), 0)[1])\n"
        )
        writer = subprocess.Popen(
            [sys.executable, "-c", prog],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert writer.stdout is not None
        writer.stdout.read(1)
        writer.stdout.close()
        _, err = writer.communicate(timeout=30)
        self.assertEqual(writer.returncode, 0, err.decode())
        self.assertNotIn(b"Traceback", err)
        self.assertNotIn(b"BrokenPipe", err)

    def test_the_exit_code_is_main_s(self):
        prog = "from labkit.formats import console\nconsole.exit_with(lambda argv: 3)\n"
        self.assertEqual(
            subprocess.run([sys.executable, "-c", prog], cwd=ROOT).returncode, 3
        )


class CommandNames(unittest.TestCase):
    def test_the_installed_commands_are_the_declared_scripts(self):
        """A stale editable install lacks a command added since: reinstall."""
        import tomllib

        from labkit.formats import console

        declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(console.command_names(), set(declared["project"]["scripts"]))


class Refusal(unittest.TestCase):
    def test_a_refused_main_says_why_on_stderr_and_exits_2(self):
        prog = (
            "from labkit.formats import console\n"
            "def main(argv):\n"
            "    raise console.Refused('some-tool', 'no such area: x')\n"
            "console.exit_with(main)\n"
        )
        r = subprocess.run(
            [sys.executable, "-c", prog], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(
            (r.returncode, r.stdout, r.stderr), (2, "", "some-tool: no such area: x\n")
        )


class RefusalsOnStderr(unittest.TestCase):
    """A refusal goes through console.refuse to stderr; stdout carries only
    what a check found (CHANGELOG 0.96.1). The shape that broke it, a print
    to stdout right before `return 2`, is held here for every module."""

    @staticmethod
    def refusals_on_stdout(source: str) -> list[int]:
        """Lines of a `print(...)` without `file=` followed directly by `return 2`."""
        hits = []
        for node in ast.walk(ast.parse(source)):
            for field in ("body", "orelse", "finalbody"):
                body = getattr(node, field, None)
                if not isinstance(body, list):
                    continue
                for a, b in zip(body, body[1:]):
                    if (
                        isinstance(a, ast.Expr)
                        and isinstance(a.value, ast.Call)
                        and getattr(a.value.func, "id", "") == "print"
                        and not any(k.arg == "file" for k in a.value.keywords)
                        and isinstance(b, ast.Return)
                        and isinstance(b.value, ast.Constant)
                        and b.value.value == 2
                    ):
                        hits.append(a.lineno)
        return hits

    def test_the_scan_finds_the_shape(self):
        bad = "def main(argv):\n    if not argv:\n        print('tool: no area')\n        return 2\n"
        good = "def main(argv):\n    print('found: x')\n    return 1\n"
        self.assertEqual(self.refusals_on_stdout(bad), [3])
        self.assertEqual(self.refusals_on_stdout(good), [])

    def test_usage_asked_is_stdout_usage_missing_is_a_refusal(self):
        import contextlib
        import io

        from labkit.formats import console

        for asked, want in (
            (True, (0, "usage: t X\n", "")),
            (False, (2, "", "t: no arguments\nusage: t X\n")),
        ):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = console.usage("t", "usage: t X", asked=asked)
            self.assertEqual((code, out.getvalue(), err.getvalue()), want)

    def test_no_command_prints_its_usage_on_stdout_and_exits_2(self):
        """`return 0 if argv else 2` after the usage on stdout: eight commands
        called without arguments refused on stdout (2026-10-20)."""
        found = [
            f"{p.relative_to(ROOT)}"
            for p in sorted((ROOT / "labkit").rglob("*.py"))
            if "0 if argv else 2" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            found, [], "return console.usage(tool, text, asked=bool(argv))"
        )

    def test_no_module_refuses_on_stdout(self):
        found = [
            f"{p.relative_to(ROOT)}:{line}"
            for p in sorted((ROOT / "labkit").rglob("*.py"))
            for line in self.refusals_on_stdout(p.read_text(encoding="utf-8"))
        ]
        self.assertEqual(found, [], "refuse through console.refuse")


class SplitCommand(unittest.TestCase):
    """The one cut of a command line that runs another command: at the
    first `--`, the rest untouched (`runlog start`, `usability log`)."""

    def test_the_cut_is_at_the_first_separator(self):
        from labkit.formats import console

        self.assertEqual(
            console.split_command(["run", "x", "--log", "f", "--", "c", "--log", "--"]),
            (["run", "x", "--log", "f"], ["c", "--log", "--"]),
        )

    def test_no_separator_is_no_command_and_an_empty_one_is_empty(self):
        from labkit.formats import console

        self.assertEqual(console.split_command(["a", "b"]), (["a", "b"], None))
        self.assertEqual(console.split_command(["a", "--"]), (["a"], []))


if __name__ == "__main__":
    unittest.main()
