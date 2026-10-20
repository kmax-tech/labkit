"""gate.Findings: one spelling of the grade, one summary, one exit contract
for every gate that blocks (audit 2026-10-15: five shapes, three
spellings, and preflight counted code-check's lines a second time)."""

from __future__ import annotations

import contextlib
import io
import unittest

from labkit.formats import gate


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
        f = gate.Findings(tell=None)
        f.warn("w")
        self.assertEqual(run(lambda: f.report("t", "x"))[0], 0)
        code, out = run(lambda: gate.Findings().report("t", "x"))
        self.assertEqual((code, out.strip()), (0, "t: all clear."))

    def test_a_graded_line_counts_by_its_own_word(self):
        f = gate.Findings()
        with contextlib.redirect_stdout(io.StringIO()):
            f.add("BLOCKER · a.py:1 · x")
            f.add("WARNING · a.py:2 · y")
            f.add("WARNING · PROTOCOL-BLOCKER.md:3 · z")
            f.add("something ungraded")  # nobody graded it: a blocker
        self.assertEqual((len(f.blocked), f.warnings), (2, 2))
        self.assertEqual(gate.grade_of("fine"), "BLOCKER")

    def test_only_the_first_word_grades_a_line(self):
        """A path or quoted text further on must not grade it: a doubled id
        in PROTOCOL-WARNING.md passed as a warning (review 2026-10-20)."""
        self.assertEqual(gate.grade_of("PROTOCOL-WARNING.md: DUPLICATE id"), "BLOCKER")
        self.assertEqual(gate.grade_of("  WARNING · x"), "WARNING")


class Silent(unittest.TestCase):
    """The findings are data; the console is one channel for them, and a
    gate inside a gate wants the data alone (report-check's finalize
    station — until 0.100.0 it redirected stdout to silence finalize)."""

    def test_a_silent_collector_keeps_the_findings_and_prints_nothing(self):
        f = gate.Findings(tell=None)
        code, out = run(
            lambda: (
                f.note("── station ──"),
                f.block("x failed"),
                f.warn("y"),
                f.add("WARNING · a.py:2 · z"),
                f.report("t", "freezing"),
            )[-1]
        )
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(f.blocked, ["x failed"])
        self.assertEqual(f.warned, ["y", "WARNING · a.py:2 · z"])
        self.assertEqual([x.grade for x in f.found], ["BLOCKER", "WARNING", "WARNING"])
        self.assertEqual(f.exit_code, 1)

    def test_the_summary_is_the_same_data_the_console_shows(self):
        told = gate.Findings()
        quiet = gate.Findings(tell=None)
        for f in (told, quiet):
            f.block("x failed")
            f.warn("y")
        _, out = run(lambda: told.report("t", "freezing"))
        self.assertEqual(out.strip().splitlines()[-3:], quiet.summary("t", "freezing"))
        self.assertEqual(gate.GateFinding("BLOCKER", "x").line, "BLOCKER: x")
        self.assertEqual(
            gate.GateFinding("WARNING", "WARNING · a · b", graded_by_text=True).line,
            "WARNING · a · b",
        )

    def test_a_channel_of_ones_own_receives_every_line(self):
        lines: list[str] = []
        f = gate.Findings(tell=lines.append)
        f.note("── x ──")
        f.block("b")
        f.report("t", "x")
        self.assertEqual(lines[:2], ["── x ──", "  BLOCKER: b"])
        self.assertIn(
            "t: 1 blocker(s), 0 warning(s) — fix the blockers before x:", lines
        )


if __name__ == "__main__":
    unittest.main()
