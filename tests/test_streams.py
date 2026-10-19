"""Findings go to stdout, a refusal to run goes to stderr (`console.refuse`).

Audit 2026-10-15: 44 refusals went to stdout and 25 to stderr, so a caller
reading stdout for a gate's findings read "no such area" as one.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from labkit.checks import code_check
from labkit.gates import finalize, preflight
from labkit import params, protocol_fill
from labkit.run import runlog
from labkit.formats import scope_sha


def run(fn, argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(argv)
    return code, out.getvalue(), err.getvalue()


class Refusals(unittest.TestCase):
    def test_no_such_area_is_on_stderr_alone(self):
        missing = str(Path(tempfile.mkdtemp()) / "nope")
        mains = (
            code_check.main,
            finalize.main,
            params.main,
            preflight.main,
            runlog.main,
        )
        for main, argv in [(m, [missing]) for m in mains] + [
            (scope_sha.main, ["--area", missing])
        ]:
            with self.subTest(main=main.__module__):
                code, out, err = run(main, argv)
                self.assertEqual(code, 2)
                self.assertIn("no such area", err)
                self.assertEqual(out, "")

    def test_several_protocols_and_a_missing_file_refuse_on_stderr(self):
        area = Path(tempfile.mkdtemp())
        for name in ("PROTOCOL-a.md", "PROTOCOL-b.md"):
            (area / name).write_text("", encoding="utf-8")
        for main in (code_check.main, finalize.main, preflight.main):
            with self.subTest(main=main.__module__):
                code, out, err = run(main, [str(area)])
                self.assertEqual(code, 2)
                self.assertIn("--protocol", err)
                self.assertEqual(out, "")
        code, out, err = run(protocol_fill.main, [str(area / "nope.md"), "--list"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("no such file", err)


if __name__ == "__main__":
    unittest.main()
