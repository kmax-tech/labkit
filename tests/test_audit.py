"""labkit-audit (2026-10-06): the experiment-preflight audit as a command,
through labkit.run.llm instead of a Claude subagent.

The model call is faked; what is tested is what the auditor gets to read,
what refuses, and the exit-code contract — 1 for a blocker OR a warning,
because the benchmark's hardest fault came only as a WARNING."""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import protocol_fixture as fixture  # noqa: E402
from protocol_fixture import registration_of, run_record  # noqa: E402
from labkit.gates import audit  # noqa: E402
from labkit.checks import audit_binding  # noqa: E402
from labkit.formats import attempts, findings, promises, scope_sha  # noqa: E402

PROTOCOL = "- **Protocol id:** p-0123456789abcdef\nCriterion [C1].\n"
SCRIPT = "import scoring\nfrom labkit.run import runlog\nprint(scoring.X)\n"


def completed_run(area: Path, pid: str, output: str) -> Path:
    """A completed run bound to PID that registered OUTPUT (a repo-relative
    path) and reports c1_pass — the run MODE analysis reads."""
    d = area / "runs" / "2026-01-01T00-00-00_0001"
    d.mkdir(parents=True)
    cfg = {
        "schema_version": 4,
        "run_kind": "measurement",
        "script": "01_measure.py",
        "pid": 1,
        "protocol": {"id": pid, "path": "PROTOCOL-x0.md"},
        "derived_from": None,
        "models_resolved": {},
        "config": {},
    }
    (d / "config.json").write_text(json.dumps(run_record(cfg)), encoding="utf-8")
    (d / "metrics.json").write_text(json.dumps({"c1_pass": True}), encoding="utf-8")
    (d / "outputs.json").write_text(
        json.dumps([{"path": output, "sha256": None, "lines": None}]), encoding="utf-8"
    )
    (d / "completion.json").write_text(
        json.dumps(
            {
                "schema_version": 4,
                "run_kind": "measurement",
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
        mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
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
        # the record names the run whose rows the auditor read (review 2026-10-18)
        record = next((area / "audits").glob("*-analysis.toml")).read_text()
        self.assertIn('run_id = "2026-01-01T00-00-00_0001"', record)
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
        # what the prompt showed is one snapshot: every shown piece stands in
        # the prompt, and the record's shown_sha is its digest, the one
        # report-check recomputes for the answering run
        shown = audit_binding.run_shown(
            area, area / "runs" / "2026-01-01T00-00-00_0001", ""
        )
        for label, text in shown.pieces:
            self.assertIn(f"===== {label} =====\n{text}\n", prompt)
        self.assertIn(f'shown_sha = "{shown.sha}"', record)

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
            fixture.head(id="p-0123456789abcdef", repeat_cost="low") + PROTOCOL,
            encoding="utf-8",
        )
        rc, _, err, _ = run(area, CLEAN)
        self.assertEqual(rc, 0, err)
        self.assertIn("LAB-017 The number of audits follows the cost tier", err)
        self.assertIn('repeat_cost = "low" and no completed run', err)
        # the twins: a completed run, or a dearer tier, and the line is gone
        completed_run(area, "p-0123456789abcdef", "data/out.jsonl")
        _, _, err, _ = run(area, CLEAN)
        self.assertNotIn("LAB-017", err)
        area2 = repo_with()
        (area2 / "PROTOCOL-x0.md").write_text(
            fixture.head(id="p-0123456789abcdef", repeat_cost="high") + PROTOCOL,
            encoding="utf-8",
        )
        _, _, err, _ = run(area2, CLEAN)
        self.assertNotIn("LAB-017", err)

    def test_the_findings_are_written_as_data_into_the_area(self):
        area = repo_with()
        rc, out, err, _ = run(area, WARN)
        self.assertEqual(rc, 1)
        files = sorted((area / "audits").glob("*-preflight.toml"))
        self.assertEqual(len(files), 1, err)
        # the record as the working directory reaches it (`repo.shown`:
        # resolved), on stdout after the report — what the person acts on
        self.assertIn(f"findings: {files[0].resolve()}", out)
        self.assertIn("  1 · WARNING · ", out)
        text = files[0].read_text(encoding="utf-8")
        self.assertIn('grade = "WARNING"', text)
        self.assertIn('status = "open"', text)
        self.assertIn("LAB-015 Preflight audit before freezing", text)
        self.assertIn("warnings = 1", text)

    def test_a_backend_that_does_not_answer_leaves_the_failed_attempt(self):
        """0.99.0: the evidence an acknowledged full run's LABKIT_UNFROZEN=1 rests on —
        written by labkit-audit with the backend's words, the code, the
        promises and the time the call had; a usage error writes none."""
        area = repo_with()

        def dead(alias, prompt, **kw):
            raise audit.llm_backends.BackendError("claude-cli exit 1: quota")

        err = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", dead),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(err),
        ):
            rc = audit.main([str(area), "--mode", "preflight", "--timeout", "1200"])
        self.assertEqual(rc, 2)
        files = list((area / "audits").glob(f"*{findings.FAILED_SUFFIX}"))
        self.assertEqual(len(files), 1, err.getvalue())
        self.assertIn(f"recorded as {files[0]}", err.getvalue())
        self.assertIn("LABKIT_UNFROZEN=1", err.getvalue())
        tried = findings.read_failed(files[0])
        self.assertEqual(tried.error, "claude-cli exit 1: quota")
        self.assertEqual(tried.timeout_s, 1200)
        self.assertEqual(tried.scope_sha, scope_sha.area_stamp(area)[0])
        self.assertIn("--mode preflight --timeout 1200", tried.command)
        self.assertEqual(findings.area_records(area), [])  # no findings were made
        (attempt,) = attempts.read_journal(area)
        self.assertEqual((attempt.outcome, attempt.file), ("failed", files[0].name))
        # eighth haiku round (t18): `rm audits/*.toml` before a new attempt —
        # the next audit names the attempt whose evidence is gone and
        # refuses before any call
        files[0].unlink()
        err = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", dead),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(err),
        ):
            rc = audit.main([str(area), "--mode", "preflight", "--timeout", "1200"])
        self.assertEqual(rc, 2)
        self.assertIn(
            f"attempt {attempt.id} (preflight, opus) ended as failed", err.getvalue()
        )
        self.assertIn("the file is gone", err.getvalue())
        self.assertEqual(len(attempts.read_journal(area)), 1)  # no new attempt

    def test_an_unproven_answer_ends_the_auditing_of_this_state_with_that_model(self):
        """The fit probes: a safety classifier stopped the auditor on every
        try, and each try cost minutes and a dollar. The first unproven
        answer is recorded with cause `unproven`; the next try with the
        same model on the same state is refused before any call; another
        model, or a backend that merely did not answer, may try again."""
        area = repo_with()
        calls: list[str] = []

        def stopped(alias, prompt, **kw):
            calls.append(alias)
            raise audit.llm_backends.UnprovenAnswer(
                "claude-cli: requested claude-opus-5-5, the reply was written by "
                "claude-opus-4-8, claude-opus-5-5"
            )

        def audit_once(*extra: str) -> tuple[int, str]:
            err = io.StringIO()
            with (
                mock.patch.object(audit.llm, "complete", stopped),
                mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(err),
            ):
                rc = audit.main([str(area), "--mode", "preflight", *extra])
            return rc, err.getvalue()

        rc, err = audit_once()
        self.assertEqual(rc, 2)
        self.assertIn("Do not run it again on this state", err)
        (tried,) = findings.failed_attempts(area)
        self.assertEqual(tried.cause, "unproven")
        self.assertEqual(calls, ["opus"])

        rc, err = audit_once()
        self.assertEqual(rc, 2)
        self.assertIn("no further try on the same code, promises and model", err)
        self.assertEqual(calls, ["opus"])  # refused before any call
        self.assertEqual(len(findings.failed_attempts(area)), 1)

        rc, _ = audit_once("--model", "haiku")
        self.assertEqual(calls, ["opus", "haiku"])  # another model may try

    def test_an_unavailable_backend_does_not_stop_the_next_try(self):
        area = repo_with()
        calls: list[str] = []

        def dead(alias, prompt, **kw):
            calls.append(alias)
            raise audit.llm_backends.BackendError("claude-cli exit 1: quota")

        for _ in range(2):
            with (
                mock.patch.object(audit.llm, "complete", dead),
                mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                audit.main([str(area), "--mode", "preflight"])
        self.assertEqual(calls, ["opus", "opus"])
        self.assertEqual(
            [f.cause for f in findings.failed_attempts(area)],
            ["unavailable", "unavailable"],
        )

    def test_an_unknown_alias_is_a_usage_error_and_leaves_no_attempt(self):
        area = repo_with()

        def unknown(alias, *a, **kw):
            raise KeyError("no such alias")

        # the alias is looked up before the call, where models.toml says
        # whether the backend takes a cap
        with (
            mock.patch.object(audit.llm, "complete", unknown),
            mock.patch.object(audit.llm, "takes_max_tokens", unknown),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            rc = audit.main([str(area), "--mode", "preflight", "--model", "nope"])
        self.assertEqual(rc, 2)
        self.assertFalse(
            list((area / "audits").glob("*")) if (area / "audits").is_dir() else []
        )

    def test_a_warning_is_a_finding_to_decide(self):
        self.assertEqual(run(repo_with(), WARN)[0], 1)
        self.assertEqual(run(repo_with(), BLOCK)[0], 1)

    def test_the_last_verdict_line_counts_and_must_match_the_lines(self):
        """A second verdict line below the first is read, and held to the
        finding lines like any: a withdrawn BLOCKER is no audit (exit 2)."""
        corrected = (
            BLOCK
            + "\nCorrection: no finding.\nverdict: 0 blockers, 0 warnings, 0 notes"
        )
        self.assertEqual(run(repo_with(), corrected)[0], 2)
        recounted = (
            "verdict: 2 blockers, 0 warnings, 0 notes\n"
            "verdict: 0 blockers, 0 warnings, 0 notes\nscope:\nscripts/01_measure.py"
        )
        self.assertEqual(run(repo_with(), recounted)[0], 0)

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

    def test_the_stamp_is_taken_before_the_call(self):
        """A lib module edited while the model answers: the record names the
        code the auditor read, not the code afterwards (audit 2026-10-15),
        and the change is said."""
        area = repo_with()
        before = scope_sha.area_stamp(area)[0]
        lib = area.parent.parent / "lib" / "scoring.py"

        def fake(alias, prompt, **kw):
            lib.write_text("X = 0.9\n", encoding="utf-8")  # during the call
            return WARN

        err = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", fake),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(err),
        ):
            rc = audit.main([str(area), "--mode", "preflight"])
        self.assertEqual(rc, 1)
        after = scope_sha.area_stamp(area)[0]
        self.assertNotEqual(before, after)
        record = next((area / "audits").glob("*-preflight.toml")).read_text()
        self.assertIn(f'scope_sha = "{before}"', record)
        self.assertIn("stamp: ", err.getvalue())
        self.assertIn(f"scope sha {before}", err.getvalue())
        self.assertIn("stamp NOTE: the code changed", err.getvalue())
        block = promises.NO_BLOCK  # the fixture's protocol declares no tables
        self.assertIn(f'block_sha = "{block}"', record)
        self.assertNotIn("run_id", record)  # a preflight audit reads no run
        self.assertIn(
            "still `open`",
            findings.audit_coverage(
                area, before, "preflight", block, registration=registration_of(area)
            )
            or "",
        )
        self.assertIn(
            "no preflight audit saw",
            findings.audit_coverage(
                area, after, "preflight", block, registration=registration_of(area)
            )
            or "",
        )

    def test_a_finding_written_with_a_dash_or_colon_is_read(self):
        """`BLOCKER — …` and `BLOCKER: …` parsed as no finding while the
        verdict counted two; the record then read as covered (audit
        2026-10-15)."""
        report = (
            "BLOCKER — a.py:1 — wrong denominator\n**BLOCKER:** b.py:2 · x\n"
            "verdict: 2 blockers, 0 warnings"
        )
        self.assertEqual(len(audit.parse(report)["findings"]), 2)
        area = repo_with()
        rc, _, err, _ = run(area, report)
        self.assertEqual(rc, 1)
        record = next((area / "audits").glob("*-preflight.toml")).read_text()
        self.assertEqual(record.count("[[finding]]"), 2)

    def test_a_verdict_without_readable_findings_records_nothing(self):
        area = repo_with()
        rc, _, err, _ = run(area, "BLOCKER a.py:1 x\nverdict: 1 blockers, 0 warnings")
        self.assertEqual(rc, 2)
        self.assertIn("counts 1 blocker(s)", err)
        self.assertEqual(list(area.glob("audits/*.toml")), [])
        # the attempt is in the journal, ended without a record and why
        (attempt,) = attempts.read_journal(area)
        self.assertEqual(attempt.outcome, "none")
        self.assertIn("counts 1 blocker(s)", attempt.error)

    def test_the_stamp_facts_are_printed(self):
        _, _, err, _ = run(repo_with(), WARN)
        self.assertRegex(
            err, r"stamp: \d{4}-\d\d-\d\d · scope sha [0-9a-f]{12} · 1 findings"
        )


class OneSnapshot(unittest.TestCase):
    """Acceptance of the audit snapshot (2026-10-20): a file changed between
    reading and the model call cannot give a record whose digest describes
    other contents than the prompt. Inside the reading — listing, snapshot,
    rendering — a change refuses the audit; during the model call the
    record keeps the bytes the prompt showed."""

    def area(self) -> Path:
        area = repo_with()
        (area / "PROTOCOL-x0.md").write_text(
            fixture.head(id="p-0123456789abcdef") + PROTOCOL, encoding="utf-8"
        )
        rows = area / "output" / "x.jsonl"
        rows.parent.mkdir()
        rows.write_text('{"i": 1}\n', encoding="utf-8")
        completed_run(area, "p-0123456789abcdef", "experiments/01-x/output/x.jsonl")
        return area

    def audit(self, area: Path, answer=None, **hooks) -> tuple[int, str, list[str]]:
        """labkit-audit in mode analysis; HOOKS wrap a function of the
        reading (`audited_run`, `area_snapshot`) to edit the area first;
        ANSWER fakes the model (it may edit the area too)."""
        patches = []
        for name, edit in hooks.items():
            real = getattr(audit, name)

            def edited_then(*args, _real=real, _edit=edit, **kw):
                _edit()
                return _real(*args, **kw)

            patches.append(mock.patch.object(audit, name, edited_then))
        sent: list[str] = []

        def fake(alias, prompt, **kw):
            sent.append(prompt)
            if answer is not None:
                answer()
            return CLEAN

        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            stack.enter_context(mock.patch.object(audit.llm, "complete", fake))
            stack.enter_context(
                mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True)
            )
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            rc = audit.main([str(area), "--mode", "analysis"])
        return rc, err.getvalue(), sent

    @staticmethod
    def stamped(area: Path) -> list[str]:
        root = area.parents[1].resolve()
        return sorted(
            f.resolve().relative_to(root).as_posix()
            for f in scope_sha.area_stamp(area)[1]
        )

    @staticmethod
    def digest_of_the_prompt(prompt: str, stamped: list[str]) -> str:
        """The stamp recomputed from the bytes the prompt shows for each
        stamped file — what the record must name."""
        parts = re.split(r"^===== (.+?) =====\n", prompt, flags=re.M)
        shown = {
            label.removeprefix("FILE: "): body[:-1]  # the join's newline
            for label, body in zip(parts[1::2], parts[2::2], strict=True)
        }
        return scope_sha.tree_digest(
            sorted((key, shown[key].encode("utf-8")) for key in stamped)
        )

    def test_an_edit_inside_the_reading_refuses_the_audit(self):
        area = self.area()
        lib = area.parents[1] / "lib" / "scoring.py"
        proto = area / "PROTOCOL-x0.md"
        for name, edit in (
            ("audited_run", lambda: lib.write_text("X = 999\n", encoding="utf-8")),
            ("audited_run", lambda: proto.write_text("# edited\n", encoding="utf-8")),
        ):
            with self.subTest(name=name):
                rc, err, sent = self.audit(area, **{name: edit})
                self.assertEqual((rc, sent), (2, []), err)
                self.assertIn("changed while it was read", err)
                self.assertEqual(findings.area_records(area), [])

    def test_a_script_added_between_listing_and_snapshot_refuses(self):
        """Review 2026-10-20: the snapshot came after gather(), the prompt
        used gather's list — a script added in between stood in the stamp
        and not in the prompt."""
        area = self.area()
        new = area / "scripts" / "02_new.py"
        rc, err, sent = self.audit(
            area, area_snapshot=lambda: new.write_text("Y = 1\n", encoding="utf-8")
        )
        self.assertEqual((rc, sent), (2, []), err)
        self.assertIn("changed while it was read", err)

    def test_an_edit_during_the_call_leaves_the_record_on_the_prompts_bytes(self):
        area = self.area()
        lib = area.parents[1] / "lib" / "scoring.py"
        stamped, before = self.stamped(area), scope_sha.area_stamp(area)[0]
        rc, err, sent = self.audit(
            area, answer=lambda: lib.write_text("X = 999\n", encoding="utf-8")
        )
        self.assertEqual(rc, 0, err)
        (record,) = findings.area_records(area)
        self.assertIn("X = 0.7", sent[0])
        self.assertEqual(record.scope_sha, before)
        self.assertEqual(record.scope_sha, self.digest_of_the_prompt(sent[0], stamped))
        self.assertIn("the code changed while the auditor read it", err)

    def test_without_an_edit_the_record_covers_the_code_now(self):
        """The twin: nothing changes, the record names the stamp as it is."""
        area = self.area()
        stamped = self.stamped(area)
        rc, err, sent = self.audit(area)
        self.assertEqual(rc, 0, err)
        (record,) = findings.area_records(area)
        self.assertEqual(record.scope_sha, scope_sha.area_stamp(area)[0])
        self.assertEqual(record.scope_sha, self.digest_of_the_prompt(sent[0], stamped))

    def test_every_stamped_file_stands_in_the_prompt(self):
        """A file the stamp covers and the reading does not take in full —
        here one another protocol declares — is indexed, never left out."""
        area = self.area()
        other = area.parents[1] / "lib" / "other.py"
        other.write_text("def helper():\n    return 1\n", encoding="utf-8")
        block = (
            '[[promise]]\nid = "C1"\nkey = "c1_pass"\nsentence = "s"\n'
            'scope = ["../../lib/other.py"]\n'
        )
        (area / "PROTOCOL-x1.md").write_text(
            fixture.head(id="p-1123456789abcdef", promises=block), encoding="utf-8"
        )
        sent: list[str] = []

        def fake(alias, prompt, **kw):
            sent.append(prompt)
            return CLEAN

        with (
            mock.patch.object(audit.llm, "complete", fake),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            rc = audit.main(
                [
                    str(area),
                    "--mode",
                    "preflight",
                    "--protocol",
                    str(area / "PROTOCOL-x0.md"),
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("lib/other.py (2 lines)", sent[0])
        for key in self.stamped(area):
            self.assertIn(key, sent[0])


class DecisionListReachesThePerson(unittest.TestCase):
    """The numbered list is what the person acts on. Printed on stderr while
    the report went to buffered stdout, it came out before the report in a
    pipe, and `2>&1 | tail -30` cut it off; one agent paid for a second
    audit only to see it (sandbox judge probes, 2026-10-21)."""

    def test_in_one_pipe_the_list_comes_after_the_report(self):
        import subprocess

        area = repo_with()
        child = (
            "import sys; sys.path.insert(0, sys.argv[1])\n"
            "from unittest import mock\n"
            "from labkit.gates import audit\n"
            "import test_audit as t\n"
            "with mock.patch.object(audit.llm, 'complete', lambda a, p, **kw: t.WARN), "
            "mock.patch.object(audit.llm, 'takes_max_tokens', lambda a: True):\n"
            "    sys.exit(audit.main([sys.argv[2], '--mode', 'preflight']))\n"
        )
        p = subprocess.run(
            [
                sys.executable,
                "-c",
                child,
                str(Path(__file__).resolve().parent),
                str(area),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=120,
        )
        self.assertEqual(p.returncode, 1, p.stdout)
        out = p.stdout
        self.assertLess(out.index("verdict:"), out.index("  1 · WARNING · "), out)
        tail = "\n".join(out.splitlines()[-6:])
        self.assertIn("--decide 1", tail, out)

    def test_findings_shows_the_newest_record_without_a_call(self):
        area = repo_with()
        run(area, WARN)

        def no_call(alias, prompt, **kw):
            raise AssertionError("--findings called the model")

        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", no_call),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            rc = audit.main([str(area), "--findings"])
        self.assertEqual(rc, 0, err.getvalue())
        self.assertIn("1 to decide", out.getvalue())
        self.assertIn("  1 · WARNING · a.py:1", out.getvalue())
        self.assertIn("--decide 1 STATUS", out.getvalue())
        self.assertEqual(
            len(list((area / "audits").glob("*.toml"))), 1
        )  # no new record

    def test_findings_without_a_record_and_with_mode_are_refused(self):
        area = repo_with()
        for argv in (
            [str(area), "--findings"],
            [str(area), "--findings", "--mode", "analysis"],
        ):
            with self.subTest(argv=argv[1:]):
                err = io.StringIO()
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(err),
                ):
                    try:
                        rc = audit.main(argv)
                    except SystemExit as exc:
                        rc = exc.code
                self.assertEqual(rc, 2, err.getvalue())


if __name__ == "__main__":
    unittest.main()


class FixVerdicts(unittest.TestCase):
    """The analysis audit judges every earlier `fixed` BLOCKER (eighth haiku
    round, t3: a leak `fixed` by dropping one of two leaking features, the
    check the finding asked for never run). One verdict per shown finding,
    bound to the decision shown; what does not read refuses the record,
    what is left out stays unchecked — never resolved."""

    LEAK = "BLOCKER · scripts/01_measure.py:9 · G_VRH and poisson_ratio give K · c1 · new class · drop both"

    def area(self, line: str | None = None) -> tuple[Path, Path]:
        """An area with an answering run and an earlier analysis record
        whose BLOCKER #1 (LINE, LEAK by default) is decided `fixed`."""
        area = OneSnapshot.area(OneSnapshot())
        earlier = findings.write(
            area,
            "analysis",
            "opus",
            "0" * 12,
            "1" * 12,
            (1, 0, 0),
            [("BLOCKER", line or self.LEAK)],
            registration={"kind": "compute"},
            run_id="2026-01-01T00-00-00_0001",
            shown_sha="2" * 12,
            now=0,
        )
        findings.write_decision(earlier, 1, "fixed", "dropped poisson_ratio")
        return area, earlier

    def audit(
        self, area: Path, answer: str, during=None
    ) -> tuple[int, str, str, list[str]]:
        sent: list[str] = []

        def fake(alias, prompt, **kw):
            sent.append(prompt)
            if during is not None:
                during()
            return answer

        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", fake),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            rc = audit.main([str(area), "--mode", "analysis"])
        return rc, out.getvalue(), err.getvalue(), sent

    def new_records(self, area: Path, earlier: Path) -> list[findings.Record]:
        return [r for r in findings.area_records(area) if r.path != earlier]

    def test_the_prompt_shows_each_fixed_blocker_and_the_verdict_is_bound(self):
        area, earlier = self.area()
        ref = f"{earlier.name}#1"
        answer = f"FIX · {ref} · unresolved · scripts/01_measure.py:9 still reads G_VRH\n{CLEAN}"
        rc, out, err, sent = self.audit(area, answer)
        self.assertEqual(rc, 0, err)
        self.assertIn(
            f"===== EARLIER FIXED BLOCKERS =====\n{ref}\n  finding: {self.LEAK}\n"
            f"  closed as fixed: dropped poisson_ratio\n",
            sent[0],
        )
        (record,) = self.new_records(area, earlier)
        (v,) = record.fix_verdicts
        decided = findings.read(earlier).findings[0]
        self.assertEqual(
            (v.record, v.n, v.verdict, v.decision_sha),
            (earlier.name, 1, "unresolved", findings.decision_digest(decided)),
        )
        self.assertIn(f"fix {ref}: unresolved — scripts/01_measure.py:9", out)

    def test_a_diagnostic_changed_after_the_audit_stales_the_verdict(self):
        """The verdict rests on what the prompt showed of the run: a
        metrics.json diagnostic changed afterwards leaves the record (and its
        verdict) no longer covering the area (`shown_sha`); the twin, the
        run untouched, still covers."""
        area, earlier = self.area()
        run = area / "runs" / "2026-01-01T00-00-00_0001"
        (run / "metrics.json").write_text(
            json.dumps({"c1_pass": True, "identity_r2_kept": 0.31}), encoding="utf-8"
        )
        answer = f"FIX · {earlier.name}#1 · resolved · metrics.json identity_r2_kept 0.31\n{CLEAN}"
        rc, _, err, sent = self.audit(area, answer)
        self.assertEqual(rc, 0, err)
        self.assertIn('"identity_r2_kept": 0.31', sent[0])
        (record,) = self.new_records(area, earlier)
        self.assertEqual(record.fix_verdicts[0].verdict, "resolved")
        text = (area / "PROTOCOL-x0.md").read_text(encoding="utf-8")

        def covering() -> list[Path]:
            return [r.path for r in audit_binding.covering_analysis(area, text, run)]

        self.assertIn(record.path, covering())
        (run / "metrics.json").write_text(
            json.dumps({"c1_pass": True, "identity_r2_kept": 0.99}), encoding="utf-8"
        )
        self.assertNotIn(record.path, covering())

    def test_a_shown_finding_without_a_line_stays_unchecked(self):
        area, earlier = self.area()
        rc, out, err, _ = self.audit(area, CLEAN)
        self.assertEqual(rc, 0, err)
        (record,) = self.new_records(area, earlier)
        self.assertEqual(record.fix_verdicts, ())
        self.assertIn(
            f"fix {earlier.name}#1: no verdict — its repair stays unchecked", out
        )

    #: the FIX entry of pilot draw B-2 (2026-10-26) as the auditor wrote it,
    #: its record name replaced by the fixture's
    B2 = (
        "FIX · {ref} · unresolved · The leaked feature is still produced:\n"
        "- 00_prepare.py:66 and :83 still append `float(row['poisson_ratio'])` to train and test features.\n"
        "- 00_prepare.py:118 refuses to overwrite compounds_v1.jsonl.\n"
        "- The new run's `c1_score` 0.9792 equals the 0.979 of the flagged run.\n"
        "- The closed-form probe R² the finding assigned is in no shown file.\n"
        "\n"
        "READ · PROTOCOL-bulk-modulus.md:16 · Recorded results still holds the stamp · fill it\n"
    )

    def test_a_why_over_several_lines_is_kept_whole(self):
        """Pilot B-2: the evidence below the FIX line is the verdict's ground;
        the record held only the first line. The blank line ends the entry,
        the READ line after it is not part of the why."""
        area, earlier = self.area()
        rc, _, err, _ = self.audit(
            area, self.B2.format(ref=f"{earlier.name}#1") + CLEAN
        )
        self.assertEqual(rc, 0, err)
        (record,) = self.new_records(area, earlier)
        why = record.fix_verdicts[0].why.splitlines()
        self.assertEqual(len(why), 5, why)
        self.assertEqual(why[0], "The leaked feature is still produced:")
        self.assertIn("no shown file", why[-1])
        self.assertNotIn("READ", record.fix_verdicts[0].why)

    def test_a_one_line_why_stays_one_line(self):
        """The twin: a FIX line followed by a blank line and a finding."""
        area, earlier = self.area()
        answer = (
            f"FIX · {earlier.name}#1 · unresolved · scripts/01_measure.py:9 still reads G_VRH\n"
            f"\n{WARN}\n"
        )
        rc, _, err, _ = self.audit(area, answer)
        self.assertEqual(rc, 1, err)
        (record,) = self.new_records(area, earlier)
        self.assertEqual(
            record.fix_verdicts[0].why, "scripts/01_measure.py:9 still reads G_VRH"
        )

    def test_an_entry_ends_at_the_next_entry_without_a_blank_line(self):
        area, earlier = self.area()
        answer = (
            f"FIX · {earlier.name}#1 · resolved · gone:\n"
            f"- 00_prepare.py:44 reads no elastic column\n{WARN}\n"
        )
        rc, _, err, _ = self.audit(area, answer)
        self.assertEqual(rc, 1, err)
        (record,) = self.new_records(area, earlier)
        self.assertEqual(
            record.fix_verdicts[0].why,
            "gone:\n- 00_prepare.py:44 reads no elastic column",
        )

    def test_an_entry_that_names_another_shown_finding_is_refused(self):
        """Two fixed BLOCKERs shown; a continuation line naming the second
        leaves open which finding the verdict judges: no record."""
        area = OneSnapshot.area(OneSnapshot())
        two = findings.write(
            area,
            "analysis",
            "opus",
            "0" * 12,
            "1" * 12,
            (2, 0, 0),
            [("BLOCKER", self.LEAK), ("BLOCKER", self.LEAK + " (test split)")],
            registration={"kind": "compute"},
            run_id="2026-01-01T00-00-00_0001",
            shown_sha="2" * 12,
            now=0,
        )
        for n in (1, 2):
            findings.write_decision(two, n, "fixed", "dropped poisson_ratio")
        answer = (
            f"FIX · {two.name}#1 · resolved · gone\n"
            f"- and {two.name}#2 is gone too\n\n{CLEAN}"
        )
        rc, _, err, _ = self.audit(area, answer)
        self.assertEqual(rc, 2)
        self.assertIn(f"also names {two.name}#2", err)
        self.assertEqual(self.new_records(area, two), [])

    def test_what_does_not_read_records_nothing(self):
        """A twin each for the parser: an unknown finding, a second verdict,
        a word outside the three, a FIX line in another form — no record."""
        cases = {
            "unknown": "FIX · 1970-01-01T01-00-analysis.toml#2 · resolved · gone\n",
            "second": "FIX · {ref} · resolved · gone\nFIX · {ref} · unresolved · not gone\n",
            "word": "FIX · {ref} · fixed · gone\n",
            "form": "FIX · {ref} resolved\n",
        }
        for name, lines in cases.items():
            with self.subTest(name):
                area, earlier = self.area()
                answer = lines.format(ref=f"{earlier.name}#1") + CLEAN
                rc, _, err, sent = self.audit(area, answer)
                self.assertEqual((rc, len(sent)), (2, 1), err)
                self.assertEqual(self.new_records(area, earlier), [])

    def test_a_decision_changed_while_the_auditor_read_refuses_the_record(self):
        area, earlier = self.area()
        answer = f"FIX · {earlier.name}#1 · resolved · gone\n{CLEAN}"

        def redecide():
            findings.write_decision(earlier, 1, "fixed", "dropped both features")

        rc, _, err, _ = self.audit(area, answer, during=redecide)
        self.assertEqual(rc, 2)
        self.assertIn("changed while the auditor read it", err)
        self.assertEqual(self.new_records(area, earlier), [])

    def test_only_blockers_decided_fixed_are_shown(self):
        area, earlier = self.area()
        findings.write_decision(earlier, 1, "accepted", "kept", "stands")
        _, _, _, sent = self.audit(area, CLEAN)
        self.assertIn("===== EARLIER FIXED BLOCKERS =====\nnone:", sent[0])

    def test_the_record_holds_its_fix_verdicts_to_their_form(self):
        area, _ = self.area()
        v = findings.FixVerdict("a.toml", 1, "3" * 12, "resolved", "gone")

        def write(mode: str, verdicts: list[findings.FixVerdict]) -> Path:
            analysis = mode == "analysis"
            return findings.write(
                area,
                mode,
                "opus",
                "0" * 12,
                "1" * 12,
                (0, 0, 0),
                [],
                registration={"kind": "compute"},
                run_id="r" if analysis else None,
                shown_sha="s" * 12 if analysis else None,
                fix_verdicts=verdicts,
            )

        with self.assertRaisesRegex(ValueError, "only an analysis audit"):
            write("preflight", [v])
        with self.assertRaisesRegex(ValueError, "second verdict"):
            write("analysis", [v, v])
        path = write("analysis", [v])
        self.assertEqual(findings.read(path).fix_verdicts, (v,))
        text = path.read_text(encoding="utf-8")
        for edit, problem in (
            ('verdict = "resolved"', 'verdict = "fixed"'),
            ('why = "gone"', 'why = "gone"\nextra = 1'),
            ("n = 1", 'n = "1"'),
        ):
            with self.subTest(problem):
                path.write_text(text.replace(edit, problem), encoding="utf-8")
                with self.assertRaises(findings.FindingsError):
                    findings.read(path)


class RequiredCheck(unittest.TestCase):
    """A finding may require the diagnostic its repair must show: the
    auditor's closing `· check: <metrics key>`, fixed when the finding is
    written and bound in its decision digest. The follow-up audit is shown
    that key's whole value from the metrics.json the prompt renders, and
    each verdict records whether the key stood there — computed by labkit,
    never by the model. No check required and a required key missing are
    two states."""

    CHECKED = FixVerdicts.LEAK + " · check: feature_sources"

    def setUp(self) -> None:
        self.fv = FixVerdicts()

    def with_metrics(self, area: Path, metrics: dict) -> None:
        run = area / "runs" / "2026-01-01T00-00-00_0001"
        (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

    def verdict(self, area: Path, earlier: Path, word: str = "resolved"):
        answer = f"FIX · {earlier.name}#1 · {word} · 00_prepare.py:44\n\n{CLEAN}"
        rc, out, err, sent = self.fv.audit(area, answer)
        self.assertEqual(rc, 0, err)
        (record,) = self.fv.new_records(area, earlier)
        return record.fix_verdicts[0], sent[0], out

    def test_the_check_is_written_from_the_finding_line_and_kept_by_decisions(self):
        area, earlier = self.fv.area(self.CHECKED)
        self.assertIn('check = "feature_sources"', earlier.read_text(encoding="utf-8"))
        (f,) = findings.read(earlier).findings
        self.assertEqual((f.status, f.check), ("fixed", "feature_sources"))

    def test_the_value_shown_is_the_snapshots_and_the_key_is_recorded_present(self):
        area, earlier = self.fv.area(self.CHECKED)
        sources = {"space_group": "column space_group", "n_sites": "structure text"}
        self.with_metrics(area, {"c1_pass": True, "feature_sources": sources})
        v, prompt, _ = self.verdict(area, earlier)
        self.assertIn(
            f"  required check `feature_sources` = {json.dumps(sources)}", prompt
        )
        self.assertEqual((v.check, v.check_present), ("feature_sources", True))

    def test_a_missing_key_is_shown_missing_and_a_resolved_is_kept_as_written(self):
        area, earlier = self.fv.area(self.CHECKED)
        v, prompt, _ = self.verdict(area, earlier)
        self.assertIn(
            "required check `feature_sources`: missing in the answering run's metrics.json",
            prompt,
        )
        self.assertEqual(
            (v.verdict, v.check, v.check_present),
            ("resolved", "feature_sources", False),
        )

    def test_no_check_required_is_not_a_missing_check(self):
        area, earlier = self.fv.area()
        v, prompt, _ = self.verdict(area, earlier)
        piece = prompt.split("===== EARLIER FIXED BLOCKERS =====\n")[1].split("=====")[
            0
        ]
        self.assertNotIn("required check", piece)
        self.assertEqual((v.check, v.check_present), ("", None))
        (record,) = self.fv.new_records(area, earlier)
        self.assertNotIn("check_present", record.path.read_text(encoding="utf-8"))

    def test_the_check_is_part_of_the_decision_digest(self):
        """A changed or removed check is another decision; a finding without
        one keeps the digest it had before checks existed."""
        base = findings.Finding("BLOCKER", "x", "fixed", "r")
        legacy = scope_sha.digest(
            findings.as_stored(["BLOCKER", "x", "fixed", "r", ""]).encode("utf-8")
        )
        self.assertEqual(findings.decision_digest(base), legacy)
        with_check = findings.Finding("BLOCKER", "x", "fixed", "r", "", "a_key")
        other = findings.Finding("BLOCKER", "x", "fixed", "r", "", "b_key")
        digests = {findings.decision_digest(f) for f in (base, with_check, other)}
        self.assertEqual(len(digests), 3)

    def test_a_check_changed_or_removed_later_stales_the_verdict(self):
        """The verdict binds the decision as shown, check included: the same
        record with the check removed or renamed no longer has the verdict's
        digest; untouched, it still has it."""
        area, earlier = self.fv.area(self.CHECKED)
        v, _, _ = self.verdict(area, earlier)
        text = earlier.read_text(encoding="utf-8")

        def digest_now() -> str:
            return findings.decision_digest(findings.read(earlier).findings[0])

        self.assertEqual(digest_now(), v.decision_sha)
        for edited in (
            text.replace('check = "feature_sources"\n', ""),
            text.replace('check = "feature_sources"', 'check = "identity_r2"'),
        ):
            earlier.write_text(edited, encoding="utf-8")
            self.assertNotEqual(digest_now(), v.decision_sha)
        earlier.write_text(text, encoding="utf-8")
        self.assertEqual(digest_now(), v.decision_sha)

    def test_a_check_edited_while_the_auditor_read_refuses_the_record(self):
        area, earlier = self.fv.area(self.CHECKED)
        answer = f"FIX · {earlier.name}#1 · resolved · gone\n\n{CLEAN}"
        text = earlier.read_text(encoding="utf-8")

        def drop_check():
            earlier.write_text(
                text.replace('check = "feature_sources"\n', ""), encoding="utf-8"
            )

        rc, _, err, _ = self.fv.audit(area, answer, during=drop_check)
        self.assertEqual(rc, 2)
        self.assertIn("changed while the auditor read it", err)

    def test_a_check_field_that_does_not_read_records_nothing(self):
        area = OneSnapshot.area(OneSnapshot())
        answer = f"{FixVerdicts.LEAK} · check: Feature Sources\nverdict: 1 blockers, 0 warnings, 0 notes"
        rc, _, err, _ = self.fv.audit(area, answer)
        self.assertEqual(rc, 2, err)
        self.assertIn("check field that does not read", err)
        self.assertEqual(list((area / "audits").glob("*-analysis.toml")), [])

    def test_the_record_holds_check_and_presence_together(self):
        area, earlier = self.fv.area(self.CHECKED)
        v, _, _ = self.verdict(area, earlier)
        (record,) = self.fv.new_records(area, earlier)
        text = record.path.read_text(encoding="utf-8")
        self.assertIn('check = "feature_sources"\ncheck_present = false', text)
        record.path.write_text(
            text.replace("check_present = false\n", ""), encoding="utf-8"
        )
        with self.assertRaises(findings.FindingsError):
            findings.read(record.path)
