"""labkit-audit (2026-10-06): the experiment-preflight audit as a command,
through labkit.llm instead of a Claude subagent.

The model call is faked; what is tested is what the auditor gets to read,
what refuses, and the exit-code contract — 1 for a blocker OR a warning,
because the benchmark's hardest fault came only as a WARNING."""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import audit  # noqa: E402

PROTOCOL = "- **Protocol id:** p-0123456789abcdef\nCriterion [C1].\n"
SCRIPT = "import scoring\nfrom labkit import runlog\nprint(scoring.X)\n"


def repo_with(standard: bool = True, protocols: int = 1) -> Path:
    repo = Path(tempfile.mkdtemp())
    (repo / ".git").mkdir()
    area = repo / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "scripts" / "01_measure.py").write_text(SCRIPT, encoding="utf-8")
    for i in range(protocols):
        (area / f"PROTOCOL-x{i}.md").write_text(PROTOCOL, encoding="utf-8")
    (repo / "lib").mkdir()
    (repo / "lib" / "scoring.py").write_text("X = 0.7\n", encoding="utf-8")
    if standard:
        (repo / "docs").mkdir()
        (repo / "docs" / "arbeitsstandard.md").write_text(
            "§2.A12 scar table\n", encoding="utf-8"
        )
    return area


def run(area: Path, answer: str, *extra: str) -> tuple[int, str, str, list[str]]:
    sent: list[str] = []

    def fake(alias, prompt, **kw):
        sent.append(prompt)
        return answer

    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch.object(audit.llm, "complete", fake),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        rc = audit.main([str(area), "--mode", "preflight", *extra])
    return rc, out.getvalue(), err.getvalue(), sent


CLEAN = "verdict: 0 blockers, 0 warnings, 2 notes\nscope:\nscripts/01_measure.py"
WARN = "WARNING · a.py:1 · x · y · §2.A12 · z\nverdict: 0 blockers, 1 warnings, 0 notes"
BLOCK = (
    "BLOCKER · a.py:1 · x · y · §2.A12 · z\nverdict: 1 blockers, 0 warnings, 0 notes"
)


class Audit(unittest.TestCase):
    def test_the_auditor_reads_protocol_code_lib_and_standard(self):
        rc, _, _, sent = run(repo_with(), CLEAN)
        self.assertEqual(rc, 0)
        prompt = sent[0]
        self.assertIn("MODE: preflight · AREA: experiments/01-x", prompt)
        for path in (
            "experiments/01-x/PROTOCOL-x0.md",
            "experiments/01-x/scripts/01_measure.py",
            "lib/scoring.py",
            "docs/arbeitsstandard.md",
        ):
            self.assertIn(f"===== FILE: {path} =====", prompt)
        self.assertIn("Experiment preflight audit", prompt)  # the shipped instructions

    def test_a_warning_is_a_finding_to_decide(self):
        self.assertEqual(run(repo_with(), WARN)[0], 1)
        self.assertEqual(run(repo_with(), BLOCK)[0], 1)

    def test_the_last_verdict_line_counts(self):
        corrected = (
            BLOCK
            + "\nCorrection: no finding.\nverdict: 0 blockers, 0 warnings, 0 notes"
        )
        self.assertEqual(run(repo_with(), corrected)[0], 0)

    def test_an_unreadable_report_is_no_audit(self):
        rc, _, err, _ = run(repo_with(), "Looks fine to me.")
        self.assertEqual(rc, 2)
        self.assertIn("verdict", err)

    def test_missing_standard_and_ambiguous_protocol_refuse(self):
        rc, _, err, sent = run(repo_with(standard=False), CLEAN)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("arbeitsstandard.md is missing", err)
        rc, _, err, sent = run(repo_with(protocols=2), CLEAN)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("--protocol", err)

    def test_the_stamp_facts_are_printed(self):
        _, _, err, _ = run(repo_with(), WARN)
        self.assertRegex(
            err, r"stamp: \d{4}-\d\d-\d\d · scope sha [0-9a-f]{12} · 1 findings"
        )


if __name__ == "__main__":
    unittest.main()
