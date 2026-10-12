"""labkit-audit (2026-10-06): the experiment-preflight audit as a command,
through labkit.llm instead of a Claude subagent.

The model call is faked; what is tested is what the auditor gets to read,
what refuses, and the exit-code contract — 1 for a blocker OR a warning,
because the benchmark's hardest fault came only as a WARNING."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import protocol_fixture as fixture  # noqa: E402
from labkit import audit  # noqa: E402

PROTOCOL = "- **Protocol id:** p-0123456789abcdef\nCriterion [C1].\n"
SCRIPT = "import scoring\nfrom labkit import runlog\nprint(scoring.X)\n"


def completed_run(area: Path, pid: str, output: str) -> Path:
    """A completed run bound to PID that registered OUTPUT (a repo-relative
    path) and reports c1_pass — the run MODE analysis reads."""
    d = area / "runs" / "2026-01-01T00-00-00_0001"
    d.mkdir(parents=True)
    cfg = {
        "schema_version": 2,
        "script": "01_measure.py",
        "pid": 1,
        "protocol": {"id": pid, "path": "PROTOCOL-x0.md"},
        "derived_from": None,
        "models_resolved": {},
        "config": {},
    }
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    (d / "metrics.json").write_text(json.dumps({"c1_pass": True}), encoding="utf-8")
    (d / "outputs.json").write_text(
        json.dumps([{"path": output, "sha256": None, "lines": None}]), encoding="utf-8"
    )
    (d / "completion.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "finished": "x",
                "git": "g",
                "git_full": "g",
                "note": "",
            }
        ),
        encoding="utf-8",
    )
    return d


def repo_with(protocols: int = 1) -> Path:
    repo = Path(tempfile.mkdtemp())
    (repo / ".git").mkdir()
    area = repo / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "scripts" / "01_measure.py").write_text(SCRIPT, encoding="utf-8")
    for i in range(protocols):
        (area / f"PROTOCOL-x{i}.md").write_text(PROTOCOL, encoding="utf-8")
    (repo / "lib").mkdir()
    (repo / "lib" / "scoring.py").write_text("X = 0.7\n", encoding="utf-8")
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
WARN = "WARNING · a.py:1 · x · y · LAB-015 Preflight audit before freezing · z\nverdict: 0 blockers, 1 warnings, 0 notes"
BLOCK = "BLOCKER · a.py:1 · x · y · LAB-015 Preflight audit before freezing · z\nverdict: 1 blockers, 0 warnings, 0 notes"


class Audit(unittest.TestCase):
    def test_the_auditor_reads_protocol_code_lib_and_the_cited_rules(self):
        rc, _, err, sent = run(repo_with(), CLEAN)
        self.assertEqual(rc, 0)
        self.assertIn("labkit-audit: tokens · prompt ", err)  # what the call cost
        prompt = sent[0]
        self.assertIn("MODE: preflight · AREA: experiments/01-x", prompt)
        for path in (
            "experiments/01-x/PROTOCOL-x0.md",
            "experiments/01-x/scripts/01_measure.py",
            "lib/scoring.py",
        ):
            self.assertIn(f"===== FILE: {path} =====", prompt)
        self.assertIn("Experiment preflight audit", prompt)  # the shipped instructions
        # the standard: the cited rules' text, not the whole document
        self.assertIn(
            "===== FILE: labkit/docs/standard.md (LAB-103, LAB-015, LAB-017, LAB-004, LAB-050 — "
            "the rules this audit cites) =====",
            prompt,
        )
        for head in (
            "LAB-015 · Preflight audit before freezing",
            "LAB-050 · Analysis audit before reporting",
        ):
            self.assertIn(head, prompt)
        self.assertIn(
            "| Criterion ≠ code", prompt
        )  # the scar table came with LAB-015 Preflight audit before freezing
        self.assertNotIn("### 2B · The Data Path", prompt)  # a chapter nobody cited
        self.assertNotIn("## 1. Evidence", prompt)
        self.assertEqual(
            audit.cited_rules("preflight"),
            ["LAB-103", "LAB-015", "LAB-017", "LAB-004", "LAB-050"],
        )

    def test_declared_scope_and_direct_imports_in_full_deeper_modules_as_index(self):
        # LAB-103 The audit reads by declared scope, not by import graph: scripts/01_measure imports lib/scoring (direct → full);
        # lib/scoring imports lib/deep (deeper → index); the promise block
        # declares scripts/helpers.py, which nothing imports (declared → full)
        area = repo_with()
        repo = area.parents[1]
        (repo / "lib" / "scoring.py").write_text(
            "import deep\nX = deep.anchor()\n", encoding="utf-8"
        )
        (repo / "lib" / "deep.py").write_text(
            '"""The anchor module.\n\nMore."""\n\n'
            "def anchor(k: int = 3) -> float:\n"
            '    """The anchor value, by k."""\n    return 0.7 * k\n\n'
            "class Table:\n    pass\n",
            encoding="utf-8",
        )
        (area / "scripts" / "helpers.py").write_text("def foo():\n    return 1\n")
        block = (
            '[[promise]]\nid = "C1"\nkey = "c1_pass"\nsentence = "holds"\n'
            'scope = ["scripts/helpers.py:foo"]\n'
        )
        (area / "PROTOCOL-x0.md").write_text(
            fixture.head(id="p-0123456789abcdef", promises=block) + PROTOCOL,
            encoding="utf-8",
        )
        rc, _, err, sent = run(area, CLEAN)
        self.assertEqual(rc, 0)
        prompt = sent[0]
        for path in (
            "experiments/01-x/scripts/01_measure.py",
            "experiments/01-x/scripts/helpers.py",
            "lib/scoring.py",
        ):
            self.assertIn(f"===== FILE: {path} =====", prompt)
        self.assertNotIn("===== FILE: lib/deep.py =====", prompt)
        self.assertNotIn("return 0.7 * k", prompt)  # not read, only indexed
        self.assertIn("===== INDEX: repo-local modules further down", prompt)
        self.assertIn(
            "lib/deep.py (10 lines)\n  def anchor(k: int=3)  — The anchor value, by k.\n  class Table",
            prompt,
        )
        self.assertIn("3 code file(s) in full, 1 indexed", err)
        # the indexed module is the caller's to add: no scope WARNING for it
        self.assertNotIn("scope WARNING: the stamp covers lib/deep.py", err)

    def test_a_declared_scope_file_that_is_missing_refuses(self):
        area = repo_with()
        block = (
            '[[promise]]\nid = "C1"\nkey = "c1_pass"\nsentence = "holds"\n'
            'scope = ["scripts/gone.py"]\n'
        )
        (area / "PROTOCOL-x0.md").write_text(
            fixture.head(id="p-0123456789abcdef", promises=block) + PROTOCOL,
            encoding="utf-8",
        )
        rc, _, err, sent = run(area, CLEAN)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("declares scope `scripts/gone.py`", err)

    def test_mode_analysis_inlines_the_answering_runs_rows_and_metrics(self):
        area = repo_with()
        (area / "PROTOCOL-x0.md").write_text(
            fixture.head(id="p-0123456789abcdef") + PROTOCOL, encoding="utf-8"
        )
        rows = area / "output" / "x.jsonl"
        rows.parent.mkdir()
        rows.write_text(
            "\n".join(
                f'{{"i": {i}, "label": "{"Yes" if i % 7 else "yes"}"}}'
                for i in range(1, 81)
            )
            + "\n"
            + '{"i": 81, "long": "'
            + "x" * 3000
            + '"}\n',
            encoding="utf-8",
        )
        completed_run(area, "p-0123456789abcdef", "experiments/01-x/output/x.jsonl")
        rc, _, _, sent = run(area, CLEAN, "--mode", "analysis")
        self.assertEqual(rc, 0)
        prompt = sent[0]
        self.assertIn("MODE: analysis", prompt)
        self.assertIn(
            "===== ROWS experiments/01-x/output/x.jsonl (81 line(s); "
            "the first 50 and last 20 are shown) =====",
            prompt,
        )
        self.assertIn('\n1: {"i": 1,', prompt)
        self.assertIn('\n50: {"i": 50,', prompt)
        self.assertIn("\n… 11 line(s) not shown …\n62: ", prompt)
        self.assertRegex(
            prompt, r"\n81: .{2000} … \[\d+ more chars\]"
        )  # cut, not dropped
        self.assertNotIn('\n51: {"i": 51,', prompt)
        self.assertIn("runs/2026-01-01T00-00-00_0001/metrics.json =====", prompt)
        self.assertIn('"c1_pass": true', prompt)

    def test_mode_analysis_without_a_run_says_so(self):
        area = repo_with()
        (area / "PROTOCOL-x0.md").write_text(
            fixture.head(id="p-0123456789abcdef") + PROTOCOL, encoding="utf-8"
        )
        rc, _, _, sent = run(area, CLEAN, "--mode", "analysis")
        self.assertEqual(rc, 0)
        self.assertIn("===== ROWS =====\nno rows: ", sent[0])
        # a prose head cannot name the run: refused as no audit, not a traceback
        rc, _, err, sent = run(repo_with(), CLEAN, "--mode", "analysis")
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("head unreadable", err)

    def test_a_preflight_audit_at_cost_seconds_without_a_run_says_it_is_early(self):
        area = repo_with()
        (area / "PROTOCOL-x0.md").write_text(
            fixture.head(id="p-0123456789abcdef", cost="seconds") + PROTOCOL,
            encoding="utf-8",
        )
        rc, _, err, _ = run(area, CLEAN)
        self.assertEqual(rc, 0, err)
        self.assertIn("LAB-017 The number of audits follows the cost tier", err)
        self.assertIn('cost = "seconds" and no completed run', err)
        # the twins: a completed run, or a dearer tier, and the line is gone
        completed_run(area, "p-0123456789abcdef", "data/out.jsonl")
        _, _, err, _ = run(area, CLEAN)
        self.assertNotIn("LAB-017", err)
        area2 = repo_with()
        (area2 / "PROTOCOL-x0.md").write_text(
            fixture.head(id="p-0123456789abcdef", cost="minutes") + PROTOCOL,
            encoding="utf-8",
        )
        _, _, err, _ = run(area2, CLEAN)
        self.assertNotIn("LAB-017", err)

    def test_the_findings_are_written_as_data_into_the_area(self):
        area = repo_with()
        rc, _, err, _ = run(area, WARN)
        self.assertEqual(rc, 1)
        files = sorted((area / "audits").glob("*-preflight.toml"))
        self.assertEqual(len(files), 1, err)
        self.assertIn(f"findings: {files[0]}", err)
        text = files[0].read_text(encoding="utf-8")
        self.assertIn('grade = "WARNING"', text)
        self.assertIn('status = "open"', text)
        self.assertIn("LAB-015 Preflight audit before freezing", text)
        self.assertIn("warnings = 1", text)

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
        with mock.patch.object(
            audit.rules, "STANDARD", Path("/nonexistent/standard.md")
        ):
            rc, _, err, sent = run(repo_with(), CLEAN)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("installed without its standard", err)
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
