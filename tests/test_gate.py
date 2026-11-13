"""gate.Findings: one spelling of the grade, one summary, one exit contract
for every gate that blocks."""

from __future__ import annotations

import contextlib
import io
import unittest
from dataclasses import replace
from typing import cast

from labkit.formats import commands
from labkit.formats import gate

from gate_fixture import BREACH, EVERY_RULE


def run(fn) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn()
    return code, buf.getvalue()


class HelpStatesTheExitContract(unittest.TestCase):
    """Every gate's --help ends with the exit contract — one line, one home
    (`gate.EXIT_CONTRACT`; labkit-audit its own, `audit.AUDIT_EXIT_CONTRACT`)
    — and report-check's names the hooks' form, which is parsed before
    argparse."""

    def _help(self, main) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
            main(["--help"])
        return out.getvalue()

    def test_every_mechanical_gate(self):
        from labkit.checks import code_check, intent_check, notes_check
        from labkit.checks import protocol_report
        from labkit.gates import finalize, preflight
        from labkit.tools import report_command

        for mod in (
            code_check,
            intent_check,
            notes_check,
            protocol_report,
            finalize,
            preflight,
            report_command,
        ):
            with self.subTest(gate=mod.__name__):
                text = self._help(mod.main)
                self.assertIn("exit codes: 0 clean", text)
                self.assertIn("1 at least one blocker", text)

    def test_report_check_names_the_hooks_form(self):
        from labkit.tools import report_command

        self.assertIn("--if-reported [--staged] PATH", self._help(report_command.main))

    def test_labkit_audit_states_its_own(self):
        from labkit.gates import audit

        text = self._help(audit.main)  # argparse re-wraps the epilog's lines
        self.assertIn("exit codes: 0 no blocker and no warning", text)
        self.assertIn("2 no audit", text)


class RuleCitation(unittest.TestCase):
    """The rule a finding records is cited in its line from the datum
    (`gate.with_rule`), in every form and in the summary: a site types no
    citation, so the line cannot name another rule than the one counted."""

    LAB_010 = gate.cited_rule("LAB-010 Commit before the run")

    def test_a_known_rule_is_cited_after_the_text_before_the_way_out(self):
        f = gate.blocker("the run recorded no commit", fix="commit", rule=self.LAB_010)
        self.assertEqual(
            f.line,
            "BLOCKER: the run recorded no commit (LAB-010 Commit before the run). "
            "Next: commit",
        )
        self.assertEqual(
            f.message,
            "the run recorded no commit (LAB-010 Commit before the run). Next: commit",
        )

    def test_the_line_as_written_and_the_dotted_line_cite_it_too(self):
        written = gate.GateFinding(
            "WARNING",
            "a.md: WARNING: x",
            gate.AS_WRITTEN,
            evidence_kind=gate.GUARANTEED,
            rule=self.LAB_010,
        )
        self.assertEqual(
            written.line, "a.md: WARNING: x (LAB-010 Commit before the run)"
        )
        dotted = gate.coded(
            "WARNING", "a.py:1", "x", evidence_kind=gate.GUARANTEED, rule=self.LAB_010
        )
        self.assertEqual(
            dotted.line, "WARNING · a.py:1 · x · LAB-010 Commit before the run"
        )

    def test_the_summary_repeats_the_blocker_with_its_rule(self):
        f = gate.Findings(tell=None)
        f.block("x", fix="y", rule=self.LAB_010)
        self.assertEqual(
            f.summary("t", "the run")[1],
            "  - x (LAB-010 Commit before the run). Next: y",
        )

    def test_the_texts_own_full_stop_goes_before_the_citation(self):
        self.assertEqual(
            gate.with_rule("One sentence. A second.", self.LAB_010),
            "One sentence. A second (LAB-010 Commit before the run)",
        )

    def test_the_twin_an_assignment_without_a_rule_adds_nothing(self):
        """A technical contract and an open assignment are data for the
        inventory: the text stands as written, its full stop too."""
        for rule in (gate.TECHNICAL_RULE, gate.OPEN_RULE):
            with self.subTest(rule=rule.kind):
                self.assertEqual(gate.with_rule("x.", rule), "x.")
        self.assertEqual(
            gate.blocker("x", fix="y", rule=gate.TECHNICAL_RULE).line,
            "BLOCKER: x. Next: y",
        )

    def test_a_new_class_is_named_as_the_dotted_line_names_it(self):
        self.assertEqual(gate.with_rule("x", gate.NEW_CLASS_RULE), "x (new class)")

    def test_another_rule_changes_the_line_and_nothing_else(self):
        """The citation follows the datum: the same sentence under another
        rule cites that rule."""
        f = gate.blocker("x", fix="y", rule=self.LAB_010)
        other = replace(f, rule=gate.cited_rule("LAB-043 Runs go through `runlog`"))
        self.assertEqual(other.text, f.text)
        self.assertEqual(
            other.line, "BLOCKER: x (LAB-043 Runs go through `runlog`). Next: y"
        )


class EvidenceKind(unittest.TestCase):
    """`evidence_kind` says what carries a finding's sentence, given at every
    site: static evidence warns and never blocks, every form names it,
    the summary counts it."""

    def test_static_evidence_never_blocks(self):
        for rule in EVERY_RULE:
            with self.subTest(rule=rule.kind):
                with self.assertRaises(ValueError) as caught:
                    gate.GateFinding(
                        "BLOCKER",
                        "x",
                        fix="y",
                        evidence_kind=gate.STATIC_EVIDENCE,
                        rule=rule,
                    )
                self.assertIn("never blocks", str(caught.exception))
                # the twin: the same sentence as a warning stands
                f = gate.GateFinding(
                    "WARNING", "x", evidence_kind=gate.STATIC_EVIDENCE, rule=rule
                )
                self.assertEqual(f.evidence_kind, gate.STATIC_EVIDENCE)

    def test_the_kind_is_given_never_defaulted_and_one_of_two(self):
        for rule in EVERY_RULE:
            with self.subTest(rule=rule.kind):
                with self.assertRaisesRegex(TypeError, "evidence_kind"):
                    gate.GateFinding("WARNING", "x", rule=rule)  # type: ignore[call-arg]
                with self.assertRaises(ValueError):
                    gate.GateFinding(
                        "WARNING", "x", evidence_kind="agent audit", rule=rule
                    )
                f = gate.Findings(tell=None)
                with self.assertRaisesRegex(TypeError, "evidence_kind"):
                    f.warn("y", rule=rule)  # type: ignore[call-arg]
                f.block("z", fix="do w", rule=rule)  # a blocker is always guaranteed
                self.assertEqual(f.found[0].evidence_kind, gate.GUARANTEED)

    def test_the_rule_is_given_never_defaulted(self):
        """An assignment left out is no open assignment: every constructor
        refuses the call, and None where the value belongs is refused
        too. The twin: OPEN_RULE, said by the site, stands."""
        f = gate.Findings(tell=None)
        for build in (
            lambda: gate.GateFinding("WARNING", "x", evidence_kind=gate.GUARANTEED),  # type: ignore[call-arg]
            lambda: gate.blocker("x", fix="y"),  # type: ignore[call-arg]
            lambda: gate.coded("WARNING", None, "x", evidence_kind=gate.GUARANTEED),  # type: ignore[call-arg]
            lambda: f.block("x", fix="y"),  # type: ignore[call-arg]
            lambda: f.warn("x", evidence_kind=gate.GUARANTEED),  # type: ignore[call-arg]
        ):
            with self.assertRaisesRegex(TypeError, "rule"):
                build()
        with self.assertRaisesRegex(ValueError, "rule is a RuleAssignment"):
            gate.blocker("x", fix="y", rule=cast(gate.RuleAssignment, None))
        self.assertEqual(f.found, [])
        self.assertEqual(
            gate.blocker("x", fix="y", rule=gate.OPEN_RULE).outcome, gate.DEVIATION
        )

    def test_a_blocker_blocks_whatever_its_rule(self):
        for rule in EVERY_RULE:
            with self.subTest(rule=rule.kind):
                f = gate.Findings(tell=None)
                f.block("x", fix="y", rule=rule)
                self.assertEqual(run(lambda: f.report("t", "x"))[0], 1)

    def test_every_form_names_static_evidence_as_a_suspicion(self):
        for rule in EVERY_RULE:
            with self.subTest(rule=rule.kind):
                self.assertEqual(
                    gate.coded(
                        "WARNING",
                        "a.py:1",
                        "z",
                        evidence_kind=gate.STATIC_EVIDENCE,
                        rule=rule,
                    ).line,
                    " · ".join(
                        p
                        for p in (
                            "WARNING · suspected, static evidence · a.py:1 · z",
                            rule.line_part,
                        )
                        if p
                    ),
                )
                self.assertEqual(
                    gate.GateFinding(
                        "WARNING", "z", evidence_kind=gate.STATIC_EVIDENCE, rule=rule
                    ).line,
                    f"WARNING (suspected, static evidence): {gate.with_rule('z', rule)}",
                )
        # the twin: an exact check on a decided basis names neither
        self.assertEqual(
            gate.coded(
                "WARNING",
                "a.py:1",
                "z",
                evidence_kind=gate.GUARANTEED,
                rule=gate.TECHNICAL_RULE,
            ).line,
            "WARNING · a.py:1 · z",
        )

    def test_the_summary_counts_static_evidence_among_the_warnings(self):
        for rule in EVERY_RULE:  # the count reads the kind, never the rule
            with self.subTest(rule=rule.kind):
                f = gate.Findings(tell=None)
                f.warn("a", evidence_kind=gate.STATIC_EVIDENCE, rule=rule)
                f.warn("b", evidence_kind=gate.GUARANTEED, rule=rule)
                self.assertEqual((f.warnings, f.static_evidence), (2, 1))
                self.assertIn(
                    "2 warning(s) (1 static evidence)", f.summary("t", "x")[0]
                )
                f.block("c", fix="d", rule=rule)
                self.assertIn(
                    "1 blocker(s), 2 warning(s) (1 static evidence)",
                    f.summary("t", "x")[0],
                )
        g = gate.Findings(tell=None)
        g.warn("a", evidence_kind=gate.GUARANTEED, rule=BREACH)
        self.assertNotIn("static evidence", g.summary("t", "x")[0])


class Findings(unittest.TestCase):
    def test_the_area_slot_is_filled_where_the_area_is_known(self):
        """A check that does not know the working directory names
        `labkit-audit <area> …`; the gate that does fills it, in the line
        and in the summary. Without an area the slot stays."""
        step = f"`labkit-audit {gate.AREA_SLOT} --mode analysis` follows it up"
        f = gate.Findings(tell=None, area="experiments/01-x")
        f.block(f"{gate.AREA_SLOT}: x", fix=step, rule=BREACH)
        f.take(
            gate.coded(
                gate.WARNING,
                "a.py:1",
                "x",
                evidence_kind=gate.GUARANTEED,
                fix=step,
                rule=BREACH,
            )
        )
        self.assertEqual(
            f.blocked,
            [
                "experiments/01-x: x. Next: `labkit-audit experiments/01-x "
                "--mode analysis` follows it up"
            ],
        )
        self.assertIn("labkit-audit experiments/01-x --mode", f.warned[0])
        bare = gate.Findings(tell=None)
        bare.block("x", fix=step, rule=BREACH)
        self.assertEqual(bare.blocked, [f"x{gate.WAY_OUT}{step}"])

    def test_a_blocker_is_exit_1_and_named_again(self):
        f = gate.Findings()
        code, out = run(
            lambda: (
                f.block("x failed", fix="mend x", rule=BREACH),
                f.warn("y", evidence_kind=gate.GUARANTEED, rule=BREACH),
                f.report("t", "freezing"),
            )[-1]
        )
        self.assertEqual(code, 1)
        self.assertIn("  BLOCKER: x failed. Next: mend x", out)
        self.assertIn("  WARNING: y", out)
        self.assertIn(
            "t: 1 blocker(s), 1 warning(s) — fix the blockers before freezing:", out
        )
        self.assertIn("  - x failed. Next: mend x", out)

    def test_warnings_alone_are_exit_0_and_clear_is_said(self):
        for rule in EVERY_RULE:
            with self.subTest(rule=rule.kind):
                f = gate.Findings(tell=None)
                f.warn("w", evidence_kind=gate.GUARANTEED, rule=rule)
                self.assertEqual(run(lambda: f.report("t", "x"))[0], 0)
        code, out = run(lambda: gate.Findings().report("t", "x"))
        self.assertEqual((code, out.strip()), (0, "t: all clear."))

    def test_the_grade_is_data_never_a_word_of_the_line(self):
        """A path or quoted text must not grade a finding: a doubled id in
        PROTOCOL-WARNING.md is a blocker. The field counts; the words are
        only told."""
        f = gate.Findings()
        with contextlib.redirect_stdout(io.StringIO()):
            entries = (
                gate.coded(
                    "BLOCKER",
                    "a.py:1",
                    "x",
                    evidence_kind=gate.GUARANTEED,
                    fix="y",
                    rule=BREACH,
                ),
                gate.coded(
                    "WARNING",
                    "PROTOCOL-BLOCKER.md:3",
                    "z",
                    evidence_kind=gate.GUARANTEED,
                    rule=BREACH,
                ),
                gate.GateFinding(
                    "BLOCKER",
                    "PROTOCOL-WARNING.md: DUPLICATE id",
                    gate.AS_WRITTEN,
                    fix="re-stamp the copy",
                    evidence_kind=gate.GUARANTEED,
                    # as the site records it (`protocol_history.check_protocol_id`)
                    rule=BREACH,
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
            rule=gate.cited_rule("LAB-004 Identifiers make the intent addressable"),
            fix="do this",
            evidence_kind=gate.GUARANTEED,
        )
        self.assertEqual(
            full.line,
            "WARNING · a.py:2 · y · why · LAB-004 Identifiers make the intent addressable · Next: do this",
        )
        self.assertEqual(
            gate.coded(
                "BLOCKER",
                None,
                "x",
                evidence_kind=gate.GUARANTEED,
                fix="y",
                rule=BREACH,
            ).line,
            "BLOCKER · x · Next: y",
        )
        self.assertEqual(
            (full.where, full.rule, full.fix),
            (
                "a.py:2",
                gate.RuleAssignment(
                    gate.KNOWN_RULE,
                    "LAB-004",
                    "Identifiers make the intent addressable",
                ),
                "do this",
            ),
        )

    def test_an_ungraded_finding_is_refused(self):
        for rule in EVERY_RULE:
            with self.subTest(rule=rule.kind):
                with self.assertRaisesRegex(ValueError, "grade"):
                    gate.GateFinding(
                        "NOTE", "x", evidence_kind=gate.GUARANTEED, rule=rule
                    )
                with self.assertRaisesRegex(ValueError, "form"):
                    gate.GateFinding(
                        "BLOCKER",
                        "x",
                        "shouted",
                        fix="y",
                        evidence_kind=gate.GUARANTEED,
                        rule=rule,
                    )


class Silent(unittest.TestCase):
    """The findings are data; the console is one channel for them, and a
    gate inside a gate wants the data alone (report-check's finalize
    station)."""

    def test_a_silent_collector_keeps_the_findings_and_prints_nothing(self):
        f = gate.Findings(tell=None)
        code, out = run(
            lambda: (
                f.note("── station ──"),
                f.block("x failed", fix="mend x", rule=BREACH),
                f.warn("y", evidence_kind=gate.GUARANTEED, rule=BREACH),
                f.take_all(
                    [
                        gate.coded(
                            "WARNING",
                            "a.py:2",
                            "z",
                            evidence_kind=gate.GUARANTEED,
                            rule=BREACH,
                        )
                    ]
                ),
                f.report("t", "freezing"),
            )[-1]
        )
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(f.blocked, ["x failed. Next: mend x"])
        self.assertEqual(f.warned, ["y", "WARNING · a.py:2 · z"])
        self.assertEqual([x.grade for x in f.found], ["BLOCKER", "WARNING", "WARNING"])
        self.assertEqual(f.exit_code, 1)

    def test_the_summary_is_the_same_data_the_console_shows(self):
        told = gate.Findings()
        quiet = gate.Findings(tell=None)
        for f in (told, quiet):
            f.block("x failed", fix="mend x", rule=BREACH)
            f.warn("y", evidence_kind=gate.GUARANTEED, rule=BREACH)
        _, out = run(lambda: told.report("t", "freezing"))
        self.assertEqual(out.strip().splitlines()[-3:], quiet.summary("t", "freezing"))
        self.assertEqual(
            gate.GateFinding(
                "BLOCKER",
                "x",
                fix="y",
                evidence_kind=gate.GUARANTEED,
                rule=BREACH,
            ).line,
            "BLOCKER: x. Next: y",
        )
        self.assertEqual(
            gate.GateFinding(
                "WARNING",
                "WARNING · a · b",
                gate.AS_WRITTEN,
                evidence_kind=gate.GUARANTEED,
                rule=BREACH,
            ).line,
            "WARNING · a · b",
        )

    def test_a_channel_of_ones_own_receives_every_line(self):
        lines: list[str] = []
        f = gate.Findings(tell=lines.append)
        f.note("── x ──")
        f.block("b", fix="c", rule=BREACH)
        f.report("t", "x")
        self.assertEqual(lines[:2], ["── x ──", "  BLOCKER: b. Next: c"])
        self.assertIn(
            "t: 1 blocker(s), 0 warning(s) — fix the blockers before x:", lines
        )


class AreaSlot(unittest.TestCase):
    """A step a check names with `<area>` runs as printed: an audit command
    takes the gate's audit head (`--protocol` where the area holds several),
    any other the area quoted."""

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
                rule=BREACH,
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
                rule=BREACH,
            )
        )
        self.assertIn("`labkit-audit experiments/01-x --mode analysis`", f.blocked[0])


class TheWayAsData(unittest.TestCase):
    """A finding carries the command its way out names as data
    (`GateFinding.step`, a `commands.Command`) and the withdrawal a hold
    names first as data (`withdraw_first`); the data changes nothing that is
    told — the twin of every site that passes a step."""

    def test_a_step_changes_no_line(self):

        step = commands.Command(commands.ADOPT, "labkit-adopt experiments/01-x R1")
        for rule in EVERY_RULE:
            with self.subTest(rule=rule.kind):
                plain = gate.blocker("x", fix=f"`{step}` adopts it", rule=rule)
                with_step = gate.blocker(
                    "x", fix=f"`{step}` adopts it", step=step, rule=rule
                )
                self.assertEqual(with_step.line, plain.line)
                self.assertEqual(with_step.message, plain.message)
        self.assertEqual(str(step), step.line)
        self.assertEqual(step.kind, commands.MECHANICAL)
        with self.assertRaisesRegex(ValueError, "a command's name"):
            commands.Command("dance", "x")

    def test_withdraw_first_is_told_before_the_way_and_only_on_a_blocker(self):

        withdrawal = commands.Command(
            commands.WITHDRAW, 'protocol-fill P --withdraw --why "<why>"'
        )
        held = gate.blocker("the code changed", fix="measure anew", rule=BREACH)
        warned = gate.GateFinding(
            gate.WARNING,
            "a note",
            fix="read it",
            evidence_kind=gate.GUARANTEED,
            rule=BREACH,
        )
        first, same = gate.withdrawn_first([held, warned], withdrawal)
        self.assertEqual(
            first.line,
            "BLOCKER: the code changed. Next: withdraw the adoption first "
            '(`protocol-fill P --withdraw --why "<why>"`), then measure anew',
        )
        self.assertEqual(first.fix, "measure anew")  # the datum, not the words
        self.assertIs(same, warned)
        self.assertEqual(gate.withdrawn_first([held], None), [held])


class ARuleAssignmentIsData(unittest.TestCase):
    """`gate.RuleAssignment`: one validated value per kind, each refusal
    beside the valid twin it differs from."""

    RULE = "LAB-043 Runs go through `runlog`"

    def test_a_cited_rule_carries_its_id_and_name(self):
        r = gate.cited_rule(self.RULE)
        self.assertEqual(
            (r.kind, r.rule_id, r.name),
            (gate.KNOWN_RULE, "LAB-043", "Runs go through `runlog`"),
        )
        self.assertEqual(r.line_part, self.RULE)

    def test_a_rule_of_the_code_standard_is_cited_the_same_way(self):
        r = gate.cited_rule("CODE-003 Test the functions that produce numbers")
        self.assertEqual(
            (r.kind, r.rule_id, r.name),
            (gate.KNOWN_RULE, "CODE-003", "Test the functions that produce numbers"),
        )

    def test_a_cited_rule_without_its_name_or_of_another_shape_is_refused(self):
        for bad in (
            "LAB-043",
            "LAB-43 Runs go",
            "lab-043 Runs go",
            "§2.D4 Runs go",
            "CODE-003",
            "LOCAL-081 Bindungstest",
        ):
            with self.subTest(bad), self.assertRaises(ValueError):
                gate.cited_rule(bad)

    def test_the_kinds_without_a_rule_name_none_and_tell_nothing_but_new_class(self):
        self.assertEqual(
            [
                r.line_part
                for r in (gate.OPEN_RULE, gate.TECHNICAL_RULE, gate.NEW_CLASS_RULE)
            ],
            [None, None, gate.NEW_CLASS],
        )

    def test_contradictory_combinations_are_refused(self):
        with self.assertRaises(ValueError):
            gate.RuleAssignment(
                gate.OPEN_ASSIGNMENT, "LAB-043", "Runs go through `runlog`"
            )
        with self.assertRaises(ValueError):
            gate.RuleAssignment(gate.TECHNICAL_CONTRACT, "LAB-043")
        with self.assertRaises(ValueError):
            gate.RuleAssignment(gate.KNOWN_RULE)
        with self.assertRaises(ValueError):
            gate.RuleAssignment(gate.KNOWN_RULE, "LAB-043", " ")
        with self.assertRaises(ValueError):
            gate.RuleAssignment("proposed")
        # the twins
        gate.RuleAssignment(gate.OPEN_ASSIGNMENT)
        gate.RuleAssignment(gate.KNOWN_RULE, "LAB-043", "Runs go through `runlog`")

    def test_a_finding_refuses_a_plain_string_and_keeps_the_value_when_forwarded(self):
        with self.assertRaises(ValueError):
            gate.GateFinding(
                "WARNING",
                "x",
                # a plain string where the value belongs: the refusal under test
                rule=cast(gate.RuleAssignment, self.RULE),
                evidence_kind=gate.GUARANTEED,
            )
        f = gate.blocker("x", fix="y", rule=gate.cited_rule(self.RULE))
        forwarded = replace(f, text="finalize: x")
        self.assertEqual(forwarded.rule, gate.cited_rule(self.RULE))
        held = gate.Findings(tell=None)
        held.block("z", fix="y", rule=gate.OPEN_RULE)
        held.warn("w", evidence_kind=gate.GUARANTEED, rule=gate.TECHNICAL_RULE)
        self.assertEqual(
            [g.rule for g in held.found], [gate.OPEN_RULE, gate.TECHNICAL_RULE]
        )


if __name__ == "__main__":
    unittest.main()
