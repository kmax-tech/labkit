"""Why a read failed travels from the reader to the finding: a file missing,
access refused, or not its writer's format — the check decides what that
means (docs/notes/2026-11-09-check-outcomes.md). Each cause beside a sound
input that passes."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from labkit.checks.code_scan import unreadable_source
from labkit.formats import files, gate, runs, scope_sha
from labkit.gates import finalize, preflight
from labkit.checks import notes_check
from labkit.formats import evidence

#: a permission refused is no refusal for root, so those cases skip there
AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


def unreadable(path: Path) -> Path:
    """PATH made unreadable for this test, its mode restored after it."""
    path.chmod(0)
    return path


class ReadCause(unittest.TestCase):
    def test_each_failure_has_its_cause(self) -> None:
        for exc, cause in (
            (FileNotFoundError("x"), files.MISSING),
            (PermissionError("x"), files.ACCESS),
            (IsADirectoryError("x"), files.ACCESS),
            (json.JSONDecodeError("x", "", 0), files.MALFORMED),
            (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "x"), files.MALFORMED),
            (files.ReadError("x", cause=files.MISSING), files.MISSING),
        ):
            with self.subTest(exc=type(exc).__name__):
                self.assertEqual(files.read_cause(exc), cause)

    def test_an_unknown_cause_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "read cause"):
            files.ReadError("x", cause="gone")


class RunArtefacts(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.metrics = self.dir / "metrics.json"

    def cause(self) -> str:
        with self.assertRaises(runs.MetricsError) as cm:
            runs.read_metrics(self.metrics)
        return cm.exception.cause

    def test_a_sound_metrics_file_reads(self) -> None:
        self.metrics.write_text('{"criterion_1_pass": true}', encoding="utf-8")
        self.assertEqual(runs.read_metrics(self.metrics), {"criterion_1_pass": True})

    def test_missing_malformed_and_wrong_shape(self) -> None:
        self.assertEqual(self.cause(), files.MISSING)
        self.metrics.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.cause(), files.MALFORMED)
        self.metrics.write_text('["criterion_1_pass"]', encoding="utf-8")
        self.assertEqual(self.cause(), files.MALFORMED)

    @unittest.skipIf(AS_ROOT, "root reads every file")
    def test_a_file_that_cannot_be_opened(self) -> None:
        self.metrics.write_text("{}", encoding="utf-8")
        unreadable(self.metrics)
        self.addCleanup(self.metrics.chmod, 0o644)
        self.assertEqual(self.cause(), files.ACCESS)


class SourceFiles(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.src = Path(tmp.name) / "m.py"

    def cause(self) -> str:
        with self.assertRaises(scope_sha.SourceError) as cm:
            scope_sha.parse_text(scope_sha.read_source(self.src), self.src)
        return cm.exception.cause

    def test_sound_python_reads(self) -> None:
        self.src.write_text("x = 1\n", encoding="utf-8")
        tree = scope_sha.parse_text(scope_sha.read_source(self.src), self.src)
        self.assertEqual(len(tree.body), 1)

    def test_missing_not_utf8_and_not_python(self) -> None:
        self.assertEqual(self.cause(), files.MISSING)
        self.src.write_bytes(b"x = '\xff'\n")
        self.assertEqual(self.cause(), files.MALFORMED)
        self.src.write_text("def (:\n", encoding="utf-8")
        self.assertEqual(self.cause(), files.MALFORMED)

    @unittest.skipIf(AS_ROOT, "root reads every file")
    def test_a_source_that_cannot_be_opened_leaves_the_scan_not_executed(
        self,
    ) -> None:
        self.src.write_text("x = 1\n", encoding="utf-8")
        unreadable(self.src)
        self.addCleanup(self.src.chmod, 0o644)
        self.assertEqual(self.cause(), files.ACCESS)
        with self.assertRaises(scope_sha.SourceError) as cm:
            scope_sha.read_source(self.src)
        finding = unreadable_source(cm.exception)
        self.assertEqual(finding.outcome, gate.NOT_EXECUTABLE)
        self.assertIn("BLOCKER · check not executable · ", finding.line)

    def test_a_file_that_is_not_python_is_a_violated_condition(self) -> None:
        self.src.write_text("def (:\n", encoding="utf-8")
        with self.assertRaises(scope_sha.SourceError) as cm:
            scope_sha.parse_text(scope_sha.read_source(self.src), self.src)
        finding = unreadable_source(cm.exception)
        self.assertEqual(finding.outcome, gate.VIOLATED)
        self.assertNotIn("not executable", finding.line)


LAB_003 = gate.cited_rule("LAB-003 No run without an intent paragraph")


class Outcome(unittest.TestCase):
    """`gate.derived_outcome` and `GateFinding.outcome`: what a finding says
    about its check follows from the evidence kind and the rule assignment;
    only a check not executed is said by the site."""

    def warned(self, evidence_kind: str, rule: gate.RuleAssignment | None) -> str:
        return gate.GateFinding(
            gate.WARNING, "x", rule=rule, evidence_kind=evidence_kind
        ).outcome

    def test_an_exact_check_on_a_decided_basis_is_a_violation(self) -> None:
        for rule in (LAB_003, gate.TECHNICAL_RULE):
            with self.subTest(rule=rule.kind):
                f = gate.blocker("x", fix="y", rule=rule)
                self.assertEqual(f.outcome, gate.VIOLATED)
                self.assertEqual(self.warned(gate.GUARANTEED, rule), gate.VIOLATED)
        self.assertEqual(
            gate.blocker("x", fix="y", rule=gate.TECHNICAL_RULE).line,
            "BLOCKER: x. Next: y",
        )

    def test_an_exact_check_on_an_unsettled_basis_is_a_deviation(self) -> None:
        """An open assignment, a new class and a site without an assignment
        name no decided basis: none of them is told as a violation, and the
        line says so. It blocks as before."""
        for rule in (gate.OPEN_RULE, gate.NEW_CLASS_RULE, None):
            with self.subTest(rule=rule):
                f = gate.blocker("x", fix="y", rule=rule)
                self.assertEqual(f.outcome, gate.DEVIATION)
                self.assertEqual(f.grade, gate.BLOCKER)
                self.assertEqual(
                    f.line, "BLOCKER (deviation, basis not settled): x. Next: y"
                )

    def test_every_form_and_the_summary_name_an_outcome_that_is_no_breach(
        self,
    ) -> None:
        """One wording per outcome (`gate.OUTCOME_MARKS`), in the prefixed
        line, the line as written, the dotted line and the summary's
        message."""
        for rule, kind, mark in (
            (gate.OPEN_RULE, gate.GUARANTEED, "deviation, basis not settled"),
            (LAB_003, gate.STATIC_EVIDENCE, "suspected, static evidence"),
        ):
            with self.subTest(mark=mark):
                prefixed = gate.GateFinding(
                    gate.WARNING, "x", rule=rule, fix="y", evidence_kind=kind
                )
                self.assertEqual(prefixed.line, f"WARNING ({mark}): x. Next: y")
                self.assertEqual(prefixed.message, f"({mark}) x. Next: y")
                written = gate.GateFinding(
                    gate.WARNING, "x", gate.AS_WRITTEN, rule=rule, evidence_kind=kind
                )
                self.assertEqual(written.line, f"x ({mark})")
                self.assertEqual(written.message, f"({mark}) x")
                dotted = gate.coded(
                    gate.WARNING, "a.py:1", "x", rule=rule, evidence_kind=kind
                )
                self.assertTrue(
                    dotted.line.startswith(f"WARNING · {mark} · a.py:1 · x"),
                    dotted.line,
                )
                self.assertEqual(dotted.message, dotted.line)

    def test_the_twin_a_breach_is_told_without_a_mark_in_every_form(self) -> None:
        for rule in (LAB_003, gate.TECHNICAL_RULE):
            with self.subTest(rule=rule.kind):
                prefixed = gate.GateFinding(
                    gate.WARNING, "x", rule=rule, evidence_kind=gate.GUARANTEED
                )
                self.assertEqual((prefixed.line, prefixed.message), ("WARNING: x", "x"))
                self.assertIsNone(prefixed.outcome_mark)
                written = gate.GateFinding(
                    gate.WARNING,
                    "x",
                    gate.AS_WRITTEN,
                    rule=rule,
                    evidence_kind=gate.GUARANTEED,
                )
                self.assertEqual((written.line, written.message), ("x", "x"))
                dotted = gate.coded(
                    gate.WARNING,
                    "a.py:1",
                    "x",
                    rule=rule,
                    evidence_kind=gate.GUARANTEED,
                )
                self.assertTrue(dotted.line.startswith("WARNING · a.py:1 · x"))

    def test_a_static_check_not_executed_names_the_kind_beside_the_mark(
        self,
    ) -> None:
        f = gate.coded(
            gate.WARNING,
            "a.py:1",
            "x",
            evidence_kind=gate.STATIC_EVIDENCE,
            stated_outcome=gate.NOT_EXECUTABLE,
        )
        self.assertEqual(
            f.line, "WARNING · static evidence · check not executable · a.py:1 · x"
        )

    def test_static_evidence_is_a_suspicion_whatever_its_basis(self) -> None:
        for rule in (LAB_003, gate.TECHNICAL_RULE, gate.OPEN_RULE, None):
            with self.subTest(rule=rule):
                self.assertEqual(
                    self.warned(gate.STATIC_EVIDENCE, rule), gate.SUSPECTED
                )

    def test_a_check_not_executed_comes_before_every_derived_outcome(self) -> None:
        for kind, rule in (
            (gate.GUARANTEED, LAB_003),
            (gate.GUARANTEED, gate.OPEN_RULE),
            (gate.STATIC_EVIDENCE, LAB_003),
        ):
            with self.subTest(kind=kind, rule=rule.kind):
                f = gate.GateFinding(
                    gate.WARNING,
                    "x",
                    rule=rule,
                    evidence_kind=kind,
                    stated_outcome=gate.NOT_EXECUTABLE,
                )
                self.assertEqual(f.outcome, gate.NOT_EXECUTABLE)

    def test_a_stated_outcome_that_contradicts_the_derived_one_is_refused(
        self,
    ) -> None:
        for kind, rule, stated in (
            (gate.GUARANTEED, gate.OPEN_RULE, gate.VIOLATED),
            (gate.GUARANTEED, None, gate.VIOLATED),
            (gate.GUARANTEED, LAB_003, gate.DEVIATION),
            (gate.STATIC_EVIDENCE, LAB_003, gate.VIOLATED),
            (gate.GUARANTEED, LAB_003, gate.SUSPECTED),
        ):
            with self.subTest(kind=kind, rule=rule, stated=stated):
                with self.assertRaisesRegex(ValueError, "states the outcome"):
                    gate.GateFinding(
                        gate.WARNING,
                        "x",
                        rule=rule,
                        evidence_kind=kind,
                        stated_outcome=stated,
                    )

    def test_the_twin_a_stated_outcome_that_is_the_derived_one_passes(self) -> None:
        for kind, rule, stated in (
            (gate.GUARANTEED, LAB_003, gate.VIOLATED),
            (gate.GUARANTEED, gate.TECHNICAL_RULE, gate.VIOLATED),
            (gate.GUARANTEED, gate.OPEN_RULE, gate.DEVIATION),
            (gate.STATIC_EVIDENCE, gate.OPEN_RULE, gate.SUSPECTED),
        ):
            with self.subTest(kind=kind, rule=rule.kind, stated=stated):
                f = gate.GateFinding(
                    gate.WARNING,
                    "x",
                    rule=rule,
                    evidence_kind=kind,
                    stated_outcome=stated,
                )
                self.assertEqual(f.outcome, stated)

    def test_a_site_that_states_nothing_is_told_from_one_that_states_violated(
        self,
    ) -> None:
        unset = gate.blocker("x", fix="y", rule=LAB_003)
        stated = gate.blocker("x", fix="y", rule=LAB_003, stated_outcome=gate.VIOLATED)
        self.assertEqual(
            (unset.stated_outcome, stated.stated_outcome), (None, gate.VIOLATED)
        )
        self.assertEqual(unset.outcome, stated.outcome)

    def test_a_combination_the_derivation_does_not_name_raises(self) -> None:
        """A new evidence kind or rule kind is decided in `derived_outcome`
        before a finding of it is told as a violation."""
        for kind, basis in (
            ("agent audit", gate.KNOWN_RULE),
            (gate.GUARANTEED, "house rule"),
        ):
            with self.subTest(kind=kind, basis=basis):
                with self.assertRaisesRegex(ValueError, "no check outcome is defined"):
                    gate.derived_outcome(kind, basis)

    def test_every_rule_kind_has_its_outcome(self) -> None:
        for basis in gate.RULE_KINDS:
            with self.subTest(basis=basis):
                self.assertIn(
                    gate.derived_outcome(gate.GUARANTEED, basis), gate.OUTCOMES
                )

    def test_a_check_not_executed_says_so_in_every_form(self) -> None:
        f = gate.blocker("x", fix="y", stated_outcome=gate.NOT_EXECUTABLE)
        self.assertEqual(f.line, "BLOCKER (check not executable): x. Next: y")
        written = gate.GateFinding(
            gate.WARNING,
            "x",
            gate.AS_WRITTEN,
            evidence_kind=gate.GUARANTEED,
            stated_outcome=gate.NOT_EXECUTABLE,
        )
        self.assertEqual(written.line, "x (check not executable)")

    def test_an_unknown_outcome_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "outcome"):
            gate.blocker("x", fix="y", stated_outcome="skipped")

    def test_only_access_leaves_a_check_not_executed(self) -> None:
        self.assertEqual(
            gate.outcome_of_failed_read(PermissionError("x")), gate.NOT_EXECUTABLE
        )
        # a missing or malformed input states nothing: its outcome is derived
        for exc in (FileNotFoundError("x"), ValueError("x")):
            with self.subTest(exc=type(exc).__name__):
                self.assertIsNone(gate.outcome_of_failed_read(exc))


class FinalizeStation(unittest.TestCase):
    """A finalize station over a run's outputs.json: absent, sound,
    malformed, not readable."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_dir = Path(tmp.name) / "01-x" / "runs" / "2026-01-01T00-00-00_0001"
        self.run_dir.mkdir(parents=True)
        self.outputs = self.run_dir / runs.OUTPUTS_FILE

    def found(self) -> list[gate.GateFinding]:
        findings = gate.Findings(None)
        finalize.check_registered_outputs(findings, self.run_dir)
        return findings.found

    def test_no_outputs_file_and_a_sound_one_pass(self) -> None:
        self.assertEqual(self.found(), [])
        self.outputs.write_text("[]", encoding="utf-8")
        self.assertEqual(self.found(), [])

    def test_a_malformed_file_is_a_defect_measured_anew(self) -> None:
        self.outputs.write_text("[not json", encoding="utf-8")
        (f,) = self.found()
        self.assertEqual(f.outcome, gate.VIOLATED)
        self.assertIn("measure anew", f.fix or "")

    @unittest.skipIf(AS_ROOT, "root reads every file")
    def test_a_file_that_cannot_be_opened_is_made_readable(self) -> None:
        self.outputs.write_text("[]", encoding="utf-8")
        unreadable(self.outputs)
        self.addCleanup(self.outputs.chmod, 0o644)
        (f,) = self.found()
        self.assertEqual(f.outcome, gate.NOT_EXECUTABLE)
        self.assertIn("make the run's files readable", f.fix or "")
        self.assertIsNone(f.step)


class TestRunOutcome(unittest.TestCase):
    """The area's tests: a run that failed is a violated condition, a run
    that did not test the code (pytest exit 2-5) a check not executed;
    both block."""

    def told(self, state: str) -> gate.GateFinding:
        tests = preflight.AreaTests(
            "tests/test_01_x.py", [Path("test_01_x.py")], state, ["1 failed"]
        )
        findings = gate.Findings(None)
        preflight.tell_test_run(
            findings, tests, "the resolution check", preflight.LAB_016
        )
        (f,) = findings.found
        return f

    def test_a_failed_run_is_violated(self) -> None:
        f = self.told("failed")
        self.assertEqual((f.grade, f.outcome), (gate.BLOCKER, gate.VIOLATED))
        self.assertIn("failed", f.text)

    def test_a_run_that_did_not_test_the_code_is_not_executed(self) -> None:
        f = self.told("not run")
        self.assertEqual((f.grade, f.outcome), (gate.BLOCKER, gate.NOT_EXECUTABLE))
        self.assertIn("did not run", f.text)


class EvidenceComparison(unittest.TestCase):
    def test_a_comparison_git_could_not_run_is_not_executed(self) -> None:
        unread, changed = evidence.change_blockers(
            [
                ("git could not compare", evidence.UNREAD_WAY),
                ("a record changed", "restore it"),
            ]
        )
        self.assertEqual(unread.outcome, gate.NOT_EXECUTABLE)
        # the changed record's rule is an open assignment: no violation is told
        self.assertEqual(changed.outcome, gate.DEVIATION)
        self.assertEqual(
            (unread.rule, changed.rule), (gate.TECHNICAL_RULE, gate.OPEN_RULE)
        )


class NoteConventions(unittest.TestCase):
    @unittest.skipIf(AS_ROOT, "root reads every file")
    def test_an_unreadable_note_warns_as_a_check_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            note = Path(d) / "a.md"
            note.write_text("# a\n", encoding="utf-8")
            unreadable(note)
            lines: list[str] = []
            try:
                code = notes_check.check_notes([note], tell=lines.append)
            finally:
                note.chmod(0o644)
        self.assertEqual(code, 0)
        self.assertTrue(
            any("WARNING (check not executable)" in ln for ln in lines), lines
        )


if __name__ == "__main__":
    unittest.main()
