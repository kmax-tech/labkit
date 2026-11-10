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
        self.assertEqual(finding.check_outcome, gate.NOT_EXECUTABLE)
        self.assertIn("BLOCKER · check not executable · ", finding.line)

    def test_a_file_that_is_not_python_is_a_violated_condition(self) -> None:
        self.src.write_text("def (:\n", encoding="utf-8")
        with self.assertRaises(scope_sha.SourceError) as cm:
            scope_sha.parse_text(scope_sha.read_source(self.src), self.src)
        finding = unreadable_source(cm.exception)
        self.assertEqual(finding.check_outcome, gate.VIOLATED)
        self.assertNotIn("not executable", finding.line)


class Outcome(unittest.TestCase):
    def test_a_finding_is_a_violation_unless_said_otherwise(self) -> None:
        f = gate.blocker("x", fix="y")
        self.assertEqual(f.check_outcome, gate.VIOLATED)
        self.assertEqual(f.line, "BLOCKER: x. Next: y")

    def test_a_check_not_executed_says_so_in_every_form(self) -> None:
        f = gate.blocker("x", fix="y", check_outcome=gate.NOT_EXECUTABLE)
        self.assertEqual(f.line, "BLOCKER (check not executable): x. Next: y")
        written = gate.GateFinding(
            gate.WARNING,
            "x",
            gate.AS_WRITTEN,
            evidence_kind=gate.GUARANTEED,
            check_outcome=gate.NOT_EXECUTABLE,
        )
        self.assertEqual(written.line, "x (check not executable)")

    def test_an_unknown_outcome_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "outcome"):
            gate.blocker("x", fix="y", check_outcome="skipped")

    def test_only_access_leaves_a_check_not_executed(self) -> None:
        self.assertEqual(
            gate.outcome_of_failed_read(PermissionError("x")), gate.NOT_EXECUTABLE
        )
        for exc in (FileNotFoundError("x"), ValueError("x")):
            with self.subTest(exc=type(exc).__name__):
                self.assertEqual(gate.outcome_of_failed_read(exc), gate.VIOLATED)


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
        self.assertEqual(f.check_outcome, gate.VIOLATED)
        self.assertIn("measure anew", f.fix or "")

    @unittest.skipIf(AS_ROOT, "root reads every file")
    def test_a_file_that_cannot_be_opened_is_made_readable(self) -> None:
        self.outputs.write_text("[]", encoding="utf-8")
        unreadable(self.outputs)
        self.addCleanup(self.outputs.chmod, 0o644)
        (f,) = self.found()
        self.assertEqual(f.check_outcome, gate.NOT_EXECUTABLE)
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
        preflight.tell_test_run(findings, tests, "the resolution check")
        (f,) = findings.found
        return f

    def test_a_failed_run_is_violated(self) -> None:
        f = self.told("failed")
        self.assertEqual((f.grade, f.check_outcome), (gate.BLOCKER, gate.VIOLATED))
        self.assertIn("failed", f.text)

    def test_a_run_that_did_not_test_the_code_is_not_executed(self) -> None:
        f = self.told("not run")
        self.assertEqual(
            (f.grade, f.check_outcome), (gate.BLOCKER, gate.NOT_EXECUTABLE)
        )
        self.assertIn("did not run", f.text)


class EvidenceComparison(unittest.TestCase):
    def test_a_comparison_git_could_not_run_is_not_executed(self) -> None:
        unread, changed = evidence.change_blockers(
            [
                ("git could not compare", evidence.UNREAD_WAY),
                ("a record changed", "restore it"),
            ]
        )
        self.assertEqual(unread.check_outcome, gate.NOT_EXECUTABLE)
        self.assertEqual(changed.check_outcome, gate.VIOLATED)


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
