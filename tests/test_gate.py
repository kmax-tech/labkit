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


class HelpStatesTheExitContract(unittest.TestCase):
    """Every gate's --help ends with the exit contract — one line, one home
    (`gate.EXIT_CONTRACT`; labkit-audit its own, `audit.AUDIT_EXIT_CONTRACT`)
    — and report-check's names the hooks' form, which is parsed before
    argparse (audit 2026-10-23, C2)."""

    def _help(self, main) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
            main(["--help"])
        return out.getvalue()

    def test_every_mechanical_gate(self):
        from labkit.checks import code_check, intent_check, notes_check
        from labkit.checks import protocol_report
        from labkit.gates import finalize, preflight, report_check

        for mod in (
            code_check,
            intent_check,
            notes_check,
            protocol_report,
            finalize,
            preflight,
            report_check,
        ):
            with self.subTest(gate=mod.__name__):
                text = self._help(mod.main)
                self.assertIn("exit codes: 0 clean", text)
                self.assertIn("1 at least one blocker", text)

    def test_report_check_names_the_hooks_form(self):
        from labkit.gates import report_check

        self.assertIn("--if-reported [--staged] PATH", self._help(report_check.main))

    def test_labkit_audit_states_its_own(self):
        from labkit.gates import audit

        text = self._help(audit.main)  # argparse re-wraps the epilog's lines
        self.assertIn("exit codes: 0 no blocker and no warning", text)
        self.assertIn("2 no audit", text)


class EvidenceKind(unittest.TestCase):
    """`evidence_kind` says what carries a finding's sentence, given at every
    site (audit 2026-10-23, C5): static evidence warns and never blocks, the
    dotted form names it, the summary counts it."""

    def test_static_evidence_never_blocks(self):
        with self.assertRaises(ValueError) as caught:
            gate.GateFinding("BLOCKER", "x", evidence_kind=gate.STATIC_EVIDENCE)
        self.assertIn("never blocks", str(caught.exception))
        # the twin: the same sentence as a warning stands
        f = gate.GateFinding("WARNING", "x", evidence_kind=gate.STATIC_EVIDENCE)
        self.assertEqual(f.evidence_kind, gate.STATIC_EVIDENCE)

    def test_the_kind_is_given_never_defaulted_and_one_of_two(self):
        with self.assertRaises(TypeError):
            gate.GateFinding("WARNING", "x")  # type: ignore[call-arg]
        with self.assertRaises(ValueError):
            gate.GateFinding("WARNING", "x", evidence_kind="agent audit")
        f = gate.Findings(tell=None)
        with self.assertRaises(TypeError):
            f.warn("y")  # type: ignore[call-arg]
        f.block("z", fix="do w")  # a blocker is always guaranteed
        self.assertEqual(f.found[0].evidence_kind, gate.GUARANTEED)

    def test_the_dotted_form_names_static_evidence_only(self):
        self.assertEqual(
            gate.coded(
                "WARNING", "a.py:1", "z", evidence_kind=gate.STATIC_EVIDENCE
            ).line,
            "WARNING · static evidence · a.py:1 · z",
        )
        self.assertEqual(
            gate.coded("WARNING", "a.py:1", "z", evidence_kind=gate.GUARANTEED).line,
            "WARNING · a.py:1 · z",
        )
        self.assertEqual(
            gate.GateFinding("WARNING", "z", evidence_kind=gate.STATIC_EVIDENCE).line,
            "WARNING: z",
        )

    def test_the_summary_counts_static_evidence_among_the_warnings(self):
        f = gate.Findings(tell=None)
        f.warn("a", evidence_kind=gate.STATIC_EVIDENCE)
        f.warn("b", evidence_kind=gate.GUARANTEED)
        self.assertEqual((f.warnings, f.static_evidence), (2, 1))
        self.assertIn("2 warning(s) (1 static evidence)", f.summary("t", "x")[0])
        f.block("c", fix="d")
        self.assertIn(
            "1 blocker(s), 2 warning(s) (1 static evidence)", f.summary("t", "x")[0]
        )
        g = gate.Findings(tell=None)
        g.warn("a", evidence_kind=gate.GUARANTEED)
        self.assertNotIn("static evidence", g.summary("t", "x")[0])


class Findings(unittest.TestCase):
    def test_the_area_slot_is_filled_where_the_area_is_known(self):
        """A check that does not know the working directory names
        `labkit-audit <area> …`; the gate that does fills it, in the line
        and in the summary. Without an area the slot stays."""
        step = f"`labkit-audit {gate.AREA_SLOT} --mode analysis` follows it up"
        f = gate.Findings(tell=None, area="experiments/01-x")
        f.block(f"{gate.AREA_SLOT}: x", fix=step)
        f.take(
            gate.coded(
                gate.WARNING, "a.py:1", "x", evidence_kind=gate.GUARANTEED, fix=step
            )
        )
        self.assertEqual(
            f.blocked,
            [
                "experiments/01-x: x — way out: `labkit-audit experiments/01-x "
                "--mode analysis` follows it up"
            ],
        )
        self.assertIn("labkit-audit experiments/01-x --mode", f.warned[0])
        bare = gate.Findings(tell=None)
        bare.block("x", fix=step)
        self.assertEqual(bare.blocked, [f"x{gate.WAY_OUT}{step}"])

    def test_a_blocker_is_exit_1_and_named_again(self):
        f = gate.Findings()
        code, out = run(
            lambda: (
                f.block("x failed", fix="mend x"),
                f.warn("y", evidence_kind=gate.GUARANTEED),
                f.report("t", "freezing"),
            )[-1]
        )
        self.assertEqual(code, 1)
        self.assertIn("  BLOCKER: x failed — way out: mend x", out)
        self.assertIn("  WARNING: y", out)
        self.assertIn(
            "t: 1 blocker(s), 1 warning(s) — fix the blockers before freezing:", out
        )
        self.assertIn("  - x failed — way out: mend x", out)

    def test_warnings_alone_are_exit_0_and_clear_is_said(self):
        f = gate.Findings(tell=None)
        f.warn("w", evidence_kind=gate.GUARANTEED)
        self.assertEqual(run(lambda: f.report("t", "x"))[0], 0)
        code, out = run(lambda: gate.Findings().report("t", "x"))
        self.assertEqual((code, out.strip()), (0, "t: all clear."))

    def test_the_grade_is_data_never_a_word_of_the_line(self):
        """A path or quoted text must not grade a finding: a doubled id in
        PROTOCOL-WARNING.md passed as a warning (review 2026-10-20). The
        field counts; the words are only told."""
        f = gate.Findings()
        with contextlib.redirect_stdout(io.StringIO()):
            entries = (
                gate.coded(
                    "BLOCKER", "a.py:1", "x", evidence_kind=gate.GUARANTEED, fix="y"
                ),
                gate.coded(
                    "WARNING",
                    "PROTOCOL-BLOCKER.md:3",
                    "z",
                    evidence_kind=gate.GUARANTEED,
                ),
                gate.GateFinding(
                    "BLOCKER",
                    "PROTOCOL-WARNING.md: DUPLICATE id",
                    gate.AS_WRITTEN,
                    fix="re-stamp the copy",
                    evidence_kind=gate.GUARANTEED,
                ),
            )
            f.take_all(iter(entries))
        self.assertEqual((len(f.blocked), f.warnings), (2, 1))
        self.assertEqual(f.found, list(entries))

    def test_a_coded_finding_is_told_with_the_parts_it_has(self):
        full = gate.coded(
            "WARNING",
            "a.py:2",
            "y · why",
            rule="LAB-004 Name",
            fix="do this",
            evidence_kind=gate.GUARANTEED,
        )
        self.assertEqual(
            full.line, "WARNING · a.py:2 · y · why · LAB-004 Name · do this"
        )
        self.assertEqual(
            gate.coded(
                "BLOCKER", None, "x", evidence_kind=gate.GUARANTEED, fix="y"
            ).line,
            "BLOCKER · x · y",
        )
        self.assertEqual(
            (full.where, full.rule, full.fix), ("a.py:2", "LAB-004 Name", "do this")
        )

    def test_an_ungraded_finding_is_refused(self):
        with self.assertRaises(ValueError):
            gate.GateFinding("NOTE", "x", evidence_kind=gate.GUARANTEED)
        with self.assertRaises(ValueError):
            gate.GateFinding(
                "BLOCKER", "x", "shouted", fix="y", evidence_kind=gate.GUARANTEED
            )


class Silent(unittest.TestCase):
    """The findings are data; the console is one channel for them, and a
    gate inside a gate wants the data alone (report-check's finalize
    station — until 0.100.0 it redirected stdout to silence finalize)."""

    def test_a_silent_collector_keeps_the_findings_and_prints_nothing(self):
        f = gate.Findings(tell=None)
        code, out = run(
            lambda: (
                f.note("── station ──"),
                f.block("x failed", fix="mend x"),
                f.warn("y", evidence_kind=gate.GUARANTEED),
                f.take_all(
                    [
                        gate.coded(
                            "WARNING", "a.py:2", "z", evidence_kind=gate.GUARANTEED
                        )
                    ]
                ),
                f.report("t", "freezing"),
            )[-1]
        )
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(f.blocked, ["x failed — way out: mend x"])
        self.assertEqual(f.warned, ["y", "WARNING · a.py:2 · z"])
        self.assertEqual([x.grade for x in f.found], ["BLOCKER", "WARNING", "WARNING"])
        self.assertEqual(f.exit_code, 1)

    def test_the_summary_is_the_same_data_the_console_shows(self):
        told = gate.Findings()
        quiet = gate.Findings(tell=None)
        for f in (told, quiet):
            f.block("x failed", fix="mend x")
            f.warn("y", evidence_kind=gate.GUARANTEED)
        _, out = run(lambda: told.report("t", "freezing"))
        self.assertEqual(out.strip().splitlines()[-3:], quiet.summary("t", "freezing"))
        self.assertEqual(
            gate.GateFinding(
                "BLOCKER", "x", fix="y", evidence_kind=gate.GUARANTEED
            ).line,
            "BLOCKER: x — way out: y",
        )
        self.assertEqual(
            gate.GateFinding(
                "WARNING",
                "WARNING · a · b",
                gate.AS_WRITTEN,
                evidence_kind=gate.GUARANTEED,
            ).line,
            "WARNING · a · b",
        )

    def test_a_channel_of_ones_own_receives_every_line(self):
        lines: list[str] = []
        f = gate.Findings(tell=lines.append)
        f.note("── x ──")
        f.block("b", fix="c")
        f.report("t", "x")
        self.assertEqual(lines[:2], ["── x ──", "  BLOCKER: b — way out: c"])
        self.assertIn(
            "t: 1 blocker(s), 0 warning(s) — fix the blockers before x:", lines
        )


class AreaSlot(unittest.TestCase):
    """A step a check names with `<area>` runs as printed: an audit command
    takes the gate's audit head (`--protocol` where the area holds several),
    any other the area quoted (audit 2026-10-27, D)."""

    def test_the_audit_slot_takes_the_head_and_the_area_is_quoted(self):
        f = gate.Findings(
            tell=None,
            area="my lab/x",
            audit="labkit-audit 'my lab/x' --protocol 'my lab/x/PROTOCOL-b.md'",
        )
        f.take(
            gate.GateFinding(
                "BLOCKER",
                "`labkit-audit <area> --mode analysis` follows it up",
                fix="then `finalize <area>`",
                evidence_kind=gate.GUARANTEED,
            )
        )
        (line,) = f.blocked
        self.assertIn(
            "`labkit-audit 'my lab/x' --protocol 'my lab/x/PROTOCOL-b.md' --mode analysis`",
            line,
        )
        self.assertIn("`finalize 'my lab/x'`", line)

    def test_the_twin_without_an_audit_head_the_area_alone_stands(self):
        f = gate.Findings(tell=None, area="experiments/01-x")
        f.take(
            gate.GateFinding(
                "BLOCKER",
                "x",
                fix="`labkit-audit <area> --mode analysis`",
                evidence_kind=gate.GUARANTEED,
            )
        )
        self.assertIn("`labkit-audit experiments/01-x --mode analysis`", f.blocked[0])


if __name__ == "__main__":
    unittest.main()
