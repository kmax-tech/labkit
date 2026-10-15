"""gate.Findings: one spelling of the grade, one summary, one exit contract
for every gate that blocks (audit 2026-10-15: five shapes, three
spellings, and preflight counted code-check's lines a second time)."""

from __future__ import annotations

import contextlib
import io
import unittest

from labkit import gate


def run(fn) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn()
    return code, buf.getvalue()


class Findings(unittest.TestCase):
    def test_a_blocker_is_exit_1_and_named_again(self):
        f = gate.Findings()
        code, out = run(
            lambda: (f.block("x failed"), f.warn("y"), f.report("t", "freezing"))[-1]
        )
        self.assertEqual(code, 1)
        self.assertIn("  BLOCKER: x failed", out)
        self.assertIn("  WARNING: y", out)
        self.assertIn(
            "t: 1 blocker(s), 1 warning(s) — fix the blockers before freezing:", out
        )
        self.assertIn("  - x failed", out)

    def test_warnings_alone_are_exit_0_and_clear_is_said(self):
        f = gate.Findings()
        f.warned.append("w")
        self.assertEqual(run(lambda: f.report("t", "x"))[0], 0)
        code, out = run(lambda: gate.Findings().report("t", "x"))
        self.assertEqual((code, out.strip()), (0, "t: all clear."))

    def test_a_graded_line_counts_by_its_own_word(self):
        f = gate.Findings()
        with contextlib.redirect_stdout(io.StringIO()):
            f.add("BLOCKER · a.py:1 · x")
            f.add("WARNING · a.py:2 · y")
            f.add("PROTOCOL-x.md: WARNING: protocol id changed against HEAD")
            f.add("something ungraded")  # nobody graded it: a blocker
        self.assertEqual((len(f.blocked), f.warnings), (2, 2))
        self.assertEqual(gate.grade_of("fine"), "BLOCKER")


if __name__ == "__main__":
    unittest.main()
