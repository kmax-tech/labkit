"""`repo.area_parser` and `repo.GivenOnce`: the one reading of an area
command's line — a flag without its value and a single-value flag given
twice are named; a flag may stand before the area."""

import argparse
import contextlib
import io
import unittest
from pathlib import Path

from labkit.formats import repo


def parser():
    """`area_parser("t", …)` with `--run` added, as a command adds a flag."""
    ap = repo.area_parser("t", "test")
    ap.add_argument("--run", action=repo.GivenOnce)
    return ap


def parse(argv: list[str]) -> argparse.Namespace:
    """ARGV read by `parser()`; the test fails if it refuses."""
    return parser().parse_args(argv)


def refusal(argv: list[str]) -> str:
    """What `parser()` prints refusing ARGV; asserts exit 2."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            parser().parse_args(argv)
        except SystemExit as exc:
            assert exc.code == 2, exc.code
            return err.getvalue()
    raise AssertionError(f"{argv} was not refused")


class AreaParser(unittest.TestCase):
    def test_area_and_options_in_either_order(self):
        for argv in (
            ["a", "--protocol", "P.md", "--run", "r1"],
            ["--protocol", "P.md", "a", "--run", "r1"],
            ["--run", "r1", "--protocol", "P.md", "a"],
        ):
            with self.subTest(argv=argv):
                args = parse(argv)
                self.assertEqual(
                    (args.area, args.protocol, args.run), ("a", Path("P.md"), "r1")
                )

    def test_options_once_or_not_at_all(self):
        args = parse(["a"])
        self.assertEqual((args.area, args.protocol, args.run), ("a", None, None))

    def test_a_flag_without_its_value_is_named(self):
        err = refusal(["a", "--protocol"])
        self.assertIn("t: error: argument --protocol: expected one argument", err)

    def test_a_single_value_flag_given_twice_is_refused(self):
        for flag in ("--protocol", "--run"):
            with self.subTest(flag=flag):
                err = refusal(["a", flag, "x", flag, "y"])
                self.assertIn(f"t: error: {flag} given twice — give it once", err)

    def test_an_unknown_word_is_named(self):
        err = refusal(["a", "extra"])
        self.assertIn("unrecognized arguments: extra", err)

    def test_no_protocol_when_the_command_reads_none(self):
        ap = repo.area_parser("t", "test", protocol=False)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ap.parse_args(["a", "--protocol", "P.md"])

    def test_given_once_needs_a_none_default(self):
        ap = repo.area_parser("t", "test")
        with self.assertRaises(ValueError):
            ap.add_argument("--max", action=repo.GivenOnce, default=3)


class EveryCommandRefusesARepeatedProtocol(unittest.TestCase):
    """Each command that reads `--protocol` refuses it given twice, before
    it looks at the area (which does not exist here)."""

    def test_each_command(self):
        from labkit.checks import code_check
        from labkit.gates import audit, finalize, preflight
        from labkit.tools import adopt, next_command, params, report_command

        mains = {
            "preflight": preflight.main,
            "finalize": finalize.main,
            "labkit-params": params.main,
            "code-check": code_check.main,
            "labkit-audit": audit.main,
            "labkit-next": next_command.main,
            "labkit-adopt": adopt.main,
            "report-check": report_command.main,
        }
        argv = ["nope", "--protocol", "A.md", "--protocol", "B.md"]
        for tool, main in mains.items():
            with self.subTest(command=tool):
                err = io.StringIO()
                with (
                    contextlib.redirect_stderr(err),
                    self.assertRaises(SystemExit) as cm,
                ):
                    main(argv)
                self.assertEqual(cm.exception.code, 2)
                self.assertIn(f"{tool}: error: --protocol given twice", err.getvalue())


if __name__ == "__main__":
    unittest.main()
