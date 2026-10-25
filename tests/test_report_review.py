"""report_review: the cold reader on a report that marks a run as not
reported — what its prompt carries, how its reply is read, what it prints.
The model is faked; whether it catches t18 is measured, not tested
(docs/usability/2026-10-25-report-review-pilot.md)."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.checks.audit_binding import AuditError  # noqa: E402
from labkit.formats import findings  # noqa: E402
from labkit.gates import audit, report_review  # noqa: E402

RUN = "2026-10-25T20-57-42_9ae7"
PROTOCOL = "# Protocol\n\n**Question:** does C1 hold?\n"
MARKED = (
    "# Report\n\n"
    f"run {RUN} (not reported: analysis audit failed)\n\n"
    "C1 PASS, AUROC 0.7795\n"
)
HONEST = (
    "# Report\n\n"
    f"run {RUN} (not reported: analysis audit failed — no audit saw its numbers)\n\n"
    "No result is reported.\n"
)


class Area:
    """A temporary area: a protocol, one run with metrics, one analysis
    record whose BLOCKER is accepted with C1 not assessable, one failed
    attempt."""

    def __init__(self, d: str) -> None:
        self.area = Path(d) / "experiments" / "01-x"
        (self.area / "runs" / RUN).mkdir(parents=True)
        (self.area / "PROTOCOL-x.md").write_text(PROTOCOL, encoding="utf-8")
        (self.area / "runs" / RUN / "metrics.json").write_text(
            json.dumps({"c1_score": 0.7795, "c1_pass": True}), encoding="utf-8"
        )
        rec = findings.write(
            self.area,
            "analysis",
            "opus",
            "0123456789ab",
            "fedcba987654",
            (1, 0, 0),
            [
                (
                    "BLOCKER",
                    "scripts/m.py:3 · test rows in the fit · C1 · LAB-050 · split",
                )
            ],
            registration={"question": "does C1 hold?"},
            run_id=RUN,
            shown_sha="0" * 12,
        )
        findings.write_decision(
            rec, 1, "accepted", "the leak stays", "C1 not assessable"
        )
        findings.write_failed(
            self.area,
            "analysis",
            "opus",
            "0123456789ab",
            "fedcba987654",
            900,
            "claude-cli: 2 turns where one answer takes one",
            "labkit-audit experiments/01-x --mode analysis",
            cause="unproven",
        )

    def report(self, text: str) -> Path:
        p = self.area.parent.parent / "REPORT.md"
        p.write_text(text, encoding="utf-8")
        return p


class Gather(unittest.TestCase):
    def test_the_prompt_carries_report_metrics_decisions_and_failed_attempts(self):
        with tempfile.TemporaryDirectory() as d:
            a = Area(d)
            prompt, marked = report_review.gather_report(
                a.area, a.report(MARKED), a.area / "PROTOCOL-x.md"
            )
        self.assertEqual([m.run_id for m in marked], [RUN])
        self.assertIn("5: C1 PASS, AUROC 0.7795", prompt)  # numbered lines
        self.assertIn('"c1_pass": true', prompt)
        self.assertIn("effect: C1 not assessable", prompt)
        self.assertIn("reason: the leak stays", prompt)
        self.assertIn("FAILED (unproven) · opus", prompt)
        self.assertIn("LAB-011", prompt)  # the cited rules are inlined

    def test_a_report_marking_no_run_is_not_reviewed(self):
        with tempfile.TemporaryDirectory() as d:
            a = Area(d)
            with self.assertRaisesRegex(AuditError, "nothing to review"):
                report_review.gather_report(
                    a.area, a.report(f"cites run {RUN}\n"), a.area / "PROTOCOL-x.md"
                )

    def test_a_marked_run_the_area_lacks_is_refused(self):
        other = "2026-10-25T20-00-00_abcd"
        with tempfile.TemporaryDirectory() as d:
            a = Area(d)
            text = f"run {other} (not reported: looked at)\n"
            with self.assertRaisesRegex(AuditError, f"no runs/{other}/"):
                report_review.gather_report(
                    a.area, a.report(text), a.area / "PROTOCOL-x.md"
                )


class Hint(unittest.TestCase):
    def test_a_marked_run_names_its_area_and_the_report(self):
        with tempfile.TemporaryDirectory() as d:
            a = Area(d)
            repo = a.area.parent.parent
            hint = report_review.review_hint(MARKED, a.report(MARKED), repo)
        self.assertIsNotNone(hint)
        self.assertIn(
            "`labkit-audit experiments/01-x --report-review REPORT.md`", hint or ""
        )

    def test_no_mark_names_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            a = Area(d)
            text = f"cites run {RUN}\n"
            repo = a.area.parent.parent
            self.assertIsNone(report_review.review_hint(text, a.report(text), repo))

    def test_a_marked_run_no_area_holds_names_nothing(self):
        text = "run 2026-10-25T20-00-00_abcd (not reported: looked at)\n"
        with tempfile.TemporaryDirectory() as d:
            a = Area(d)
            repo = a.area.parent.parent
            self.assertIsNone(report_review.review_hint(text, a.report(text), repo))


class Parse(unittest.TestCase):
    def test_no_claim(self):
        self.assertEqual(report_review.parse_claims("verdict: 0 claim(s)", 5), [])

    def test_claims_in_order(self):
        reply = (
            "CLAIM #1 · line 5 · contradiction · C1 PASS against C1 not assessable\n"
            "CLAIM #2 · line 5 · result · AUROC of the marked run\n"
            "verdict: 2 claim(s)\n"
        )
        claims = report_review.parse_claims(reply, 5)
        self.assertEqual(
            [(c.line, c.kind) for c in claims], [(5, "contradiction"), (5, "result")]
        )

    def test_a_count_that_disagrees_names_nothing(self):
        reply = "CLAIM #1 · line 5 · result · x\nverdict: 2 claim(s)\n"
        with self.assertRaisesRegex(AuditError, "counts 2"):
            report_review.parse_claims(reply, 5)

    def test_a_line_outside_the_report_names_nothing(self):
        reply = "CLAIM #1 · line 9 · result · x\nverdict: 1 claim(s)\n"
        with self.assertRaisesRegex(AuditError, r"line\(s\) \[9\]"):
            report_review.parse_claims(reply, 5)

    def test_misnumbered_claims_name_nothing(self):
        reply = "CLAIM #2 · line 5 · result · x\nverdict: 1 claim(s)\n"
        with self.assertRaisesRegex(AuditError, "numbered"):
            report_review.parse_claims(reply, 5)

    def test_no_closing_line_is_no_review(self):
        with self.assertRaisesRegex(AuditError, "verdict"):
            report_review.parse_claims("CLAIM #1 · line 5 · result · x", 5)


class Command(unittest.TestCase):
    def run_with(self, text: str, reply: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as d:
            a = Area(d)
            report = a.report(text)
            out = io.StringIO()
            with (
                mock.patch.object(report_review.llm, "complete", lambda *a, **k: reply),
                mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                rc = report_review.review_report(a.area, report, None, "m", 60, None)
        return rc, out.getvalue()

    def test_a_claim_is_a_warning_with_the_report_line(self):
        rc, out = self.run_with(
            MARKED,
            "CLAIM #1 · line 5 · contradiction · C1 PASS against C1 not assessable\n"
            "verdict: 1 claim(s)\n",
        )
        self.assertEqual(rc, 1)
        self.assertIn("WARNING: ", out)
        self.assertIn("REPORT.md:5: contradiction", out)
        self.assertIn("blocks nothing", out)

    def test_an_honest_report_without_claims_exits_0(self):
        rc, out = self.run_with(HONEST, "verdict: 0 claim(s)\n")
        self.assertEqual(rc, 0)
        self.assertNotIn("WARNING", out)

    def test_an_unreadable_reply_is_no_review(self):
        rc, _ = self.run_with(MARKED, "looks fine to me")
        self.assertEqual(rc, 2)


class Cli(unittest.TestCase):
    def test_report_review_goes_alone(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            audit.main(["x", "--report-review", "REPORT.md", "--review"])

    def test_the_instructions_ship(self):
        self.assertIn("Report review", audit.instructions("report"))
        self.assertEqual(audit.cited_rules("report"), ["LAB-011", "LAB-050"])


if __name__ == "__main__":
    unittest.main()
