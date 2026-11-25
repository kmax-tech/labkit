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
    what a check found. The shape that would break it, a print to stdout
    right before `return 2`, is held here for every module."""

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
        """`return 0 if argv else 2` after the usage on stdout would refuse
        a command called without arguments on stdout; no module holds it."""
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


class OncePerCommand(unittest.TestCase):
    """`once_per_command`: inside one command a question is asked once;
    with no command running, after an exception, and for an answer the
    caller's KEEP refuses, it is asked every time."""

    def setUp(self) -> None:
        self.asked: list[str] = []

    def ask(self, answer: str = "answer") -> str:
        from labkit.formats import console

        def asking() -> str:
            self.asked.append(answer)
            return answer

        return console.once_per_command("the question", asking)

    def test_inside_a_command_the_question_is_asked_once(self):
        from labkit.formats import console

        with console.one_command():
            self.assertEqual([self.ask(), self.ask()], ["answer", "answer"])
            self.assertEqual(self.asked, ["answer"])
            # the key is the question: another key is asked for itself
            self.assertEqual(console.once_per_command("another", lambda: 7), 7)

    def test_with_no_command_running_it_is_asked_every_time(self):
        self.assertEqual([self.ask("a"), self.ask("b")], ["a", "b"])

    def test_a_command_starts_with_no_answer_and_leaves_none(self):
        from labkit.formats import console

        with console.one_command():
            self.ask("first command")
        self.assertEqual(self.ask("between"), "between")
        with console.one_command():
            self.assertEqual(self.ask("second command"), "second command")
        with self.assertRaises(KeyError), console.one_command():
            self.ask("ended by an error")
            raise KeyError("the command failed")
        self.assertEqual(self.ask("after the error"), "after the error")

    def test_a_command_inside_a_command_is_refused(self):
        """The inner span's end would drop the outer one's answers; the
        outer command goes on keeping."""
        from labkit.formats import console

        with console.one_command():
            self.ask()
            with self.assertRaises(RuntimeError), console.one_command():
                self.fail("the inner span opened")
            self.ask()
        self.assertEqual(self.asked, ["answer"])

    def test_an_exception_keeps_nothing(self):
        from labkit.formats import console

        def failing() -> str:
            raise OSError("could not read")

        with console.one_command():
            with self.assertRaises(OSError):
                console.once_per_command("the question", failing)
            self.assertEqual(self.ask(), "answer")

    def test_an_answer_keep_refuses_is_asked_again(self):
        from labkit.formats import console

        answers = iter([None, "arrived", "never asked"])
        with console.one_command():
            got = [
                console.once_per_command(
                    "the question", lambda: next(answers), keep=lambda a: a is not None
                )
                for _ in range(3)
            ]
        self.assertEqual(got, [None, "arrived", "arrived"])

    def test_exit_with_runs_main_as_one_command(self):
        from unittest import mock

        from labkit.formats import console

        def main(argv: list[str]) -> int:
            self.ask()
            self.ask()
            return 0

        for _ in range(2):
            with mock.patch.object(sys, "argv", ["tool"]):
                with self.assertRaises(SystemExit) as exit_:
                    console.exit_with(main)
            self.assertEqual(exit_.exception.code, 0)
        # once per command, and the second command did not get the first's
        self.assertEqual(self.asked, ["answer", "answer"])
        self.ask("after the commands")
        self.ask("after the commands")
        self.assertEqual(self.asked[2:], ["after the commands"] * 2)


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


class AsksHelp(unittest.TestCase):
    def test_help_counts_anywhere_on_the_line(self):
        from labkit.formats import console

        for argv in (["--help"], ["-h"], ["install", "--help"], ["a", "b", "-h"]):
            self.assertTrue(console.asks_help(argv), argv)
        for argv in ([], ["install"], ["--helpful"], ["a", "--h"]):
            self.assertFalse(console.asks_help(argv), argv)


if __name__ == "__main__":
    unittest.main()
