"""report_review: the cold reader on a report that discusses a run as not
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
from labkit.checks.report_blocks import discussion_lines  # noqa: E402
from labkit.formats import attempts, findings, report_reviews  # noqa: E402
from labkit.gates import audit, report_review  # noqa: E402
from labkit.run import llm_backends  # noqa: E402

RUN = "2026-10-25T20-57-42_9ae7"
PROTOCOL = "# Protocol\n\n**Question:** does C1 hold?\n"
P = "experiments/01-x/PROTOCOL-x.md"


def discussed(run: str, why: str) -> str:
    """The discussion block of RUN with WHY, as `--discuss` writes it."""
    return "\n".join(discussion_lines(P, run, why))


MARKED = (
    f"# Report\n\n{discussed(RUN, 'analysis audit failed')}\n\nC1 PASS, AUROC 0.7795\n"
)
HONEST = (
    "# Report\n\n"
    f"{discussed(RUN, 'analysis audit failed — no audit saw its numbers')}\n\n"
    "No result is reported.\n"
)


class Area:
    """A temporary area: a protocol, one run with metrics, one analysis
    record whose BLOCKER is accepted with C1 not assessable, one failed
    attempt."""

    def __init__(self, d: str) -> None:
        self.area = Path(d) / "experiments" / "01-x"
        (self.area / "runs" / RUN).mkdir(parents=True)
        # the repo's root as layout_root finds it before `git init`
        (Path(d) / "CLAUDE.md").write_text("# repo\n", encoding="utf-8")
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
            prompt, marked, _ = report_review.gather_report(
                a.area, a.report(MARKED), a.area / "PROTOCOL-x.md"
            )
        self.assertEqual([m.run_id for m in marked], [RUN])
        self.assertIn("11: C1 PASS, AUROC 0.7795", prompt)  # numbered lines
        self.assertIn(f"line 3: run {RUN} — why: analysis audit failed", prompt)
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
            text = discussed(other, "looked at") + "\n"
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

    def test_in_an_area_of_several_protocols_it_names_the_one_discussed(self):
        with tempfile.TemporaryDirectory() as d:
            a = Area(d)
            (a.area / "PROTOCOL-y.md").write_text(PROTOCOL, encoding="utf-8")
            repo = a.area.parent.parent
            hint = report_review.review_hint(MARKED, a.report(MARKED), repo)
        self.assertIn(
            "`labkit-audit experiments/01-x --report-review REPORT.md "
            "--protocol experiments/01-x/PROTOCOL-x.md`",
            hint or "",
        )

    def test_no_mark_names_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            a = Area(d)
            text = f"cites run {RUN}\n"
            repo = a.area.parent.parent
            self.assertIsNone(report_review.review_hint(text, a.report(text), repo))

    def test_a_marked_run_no_area_holds_names_nothing(self):
        text = discussed("2026-10-25T20-00-00_abcd", "looked at") + "\n"
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
    """The review writes its record; a state it judged is not drawn on
    again; a claim holds until an input changes (eighth haiku round, t18:
    the review as a hint was passed over)."""

    CLAIMED = (
        "CLAIM #1 · line 5 · contradiction · C1 PASS against C1 not assessable\n"
        "verdict: 1 claim(s)\n"
    )
    CLEAN = "verdict: 0 claim(s)\n"

    def setUp(self):
        self.a = Area(tempfile.mkdtemp())

    def review(self, text: str, reply: str, *, again: bool = False):
        """(exit, stdout, stderr, model calls) of one review of TEXT."""
        report = self.a.report(text)
        calls: list[str] = []

        def fake(*args, **kw):
            calls.append(args[1])
            return reply

        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", fake),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            rc = report_review.review_report(
                self.a.area, report, None, "m", 60, None, again=again
            )
        return rc, out.getvalue(), err.getvalue(), len(calls)

    def reviews(self) -> list[report_reviews.ReportReview]:
        return report_reviews.area_report_reviews(self.a.area)

    def test_a_claim_is_recorded_and_holds(self):
        rc, out, _, calls = self.review(MARKED, self.CLAIMED)
        self.assertEqual((rc, calls), (1, 1))
        self.assertIn("CLAIM: ", out)
        self.assertIn("REPORT.md:5: contradiction", out)
        self.assertIn("the commit holds this state: CLAIM in ", out)
        (r,) = self.reviews()
        self.assertEqual((r.report, r.protocol), ("REPORT.md", P))
        self.assertEqual([(c.line, c.kind) for c in r.claims], [(5, "contradiction")])

    def test_a_state_with_a_claim_is_not_drawn_on_again(self):
        self.review(MARKED, self.CLAIMED)
        rc, _, err, calls = self.review(MARKED, self.CLEAN)
        self.assertEqual((rc, calls), (2, 0))
        self.assertIn("another draw settles nothing", err)
        self.assertIn("line 5 (contradiction): C1 PASS against C1 not assessable", err)
        # --again draws and records the draw, releases nothing — and says so,
        # the draw and the state apart: a clean draw on a held state printed
        # "released" while the commit stayed refused (ninth haiku round, t5),
        # then exited 0, which read as done (audit 2026-10-27, C6)
        rc, out, _, calls = self.review(MARKED, self.CLEAN, again=True)
        self.assertEqual((rc, calls), (1, 1))
        self.assertIn("report review: this draw names 0 claim(s), recorded in ", out)
        self.assertIn("an `--again` draw: a claim it names holds the state", out)
        self.assertNotIn("released", out.replace("releases nothing", ""))
        self.assertIn(
            "report review state: the commit holds this state: CLAIM in ", out
        )
        first, second = self.reviews()
        self.assertTrue(second.again)
        self.assertEqual(first.fingerprint, second.fingerprint)
        stands = report_reviews.standing(
            self.reviews(), "REPORT.md", P, second.fingerprint
        )
        self.assertFalse(stands.released)

    def test_a_clean_draw_alone_names_the_review_that_releases(self):
        """A state seen only by an `--again` draw is not released — the exit
        code says so too; the line names the command without `--again` that
        releases it."""
        rc, out, _, calls = self.review(HONEST, self.CLEAN, again=True)
        self.assertEqual((rc, calls), (1, 1))
        self.assertIn("only a review that is no `--again` draw releases it", out)
        self.assertIn("--report-review", out.split("releases it")[-1])
        self.assertNotIn("--again`", out.split("releases it")[-1])

    def test_an_again_draw_on_a_released_state_exits_with_the_state(self):
        """The twin: a clean `--again` draw on a released state leaves it
        released, exit 0; a claim it names holds the state, exit 1 — the
        exit code is the state's either way, never the draw's alone."""
        rc, _, _, _ = self.review(HONEST, self.CLEAN)
        self.assertEqual(rc, 0)
        rc, out, _, calls = self.review(HONEST, self.CLEAN, again=True)
        self.assertEqual((rc, calls), (0, 1))
        self.assertIn("report review state: this state is released", out)
        rc, out, _, calls = self.review(HONEST, self.CLAIMED, again=True)
        self.assertEqual((rc, calls), (1, 1))
        self.assertIn("report review: this draw names 1 claim(s)", out)
        self.assertIn("report review state: the commit holds this state: CLAIM", out)
        stands = report_reviews.standing(
            self.reviews(), "REPORT.md", P, self.reviews()[-1].fingerprint
        )
        self.assertFalse(stands.released)

    def test_a_changed_source_may_be_reviewed_again(self):
        """A corrected source settles a claim without a text change: the
        protocol is an input the reviewer read."""
        self.review(MARKED, self.CLAIMED)
        proto = self.a.area / "PROTOCOL-x.md"
        proto.write_text(PROTOCOL + "\n**Conclusion:** C1 is not assessable.\n")
        rc, _, _, calls = self.review(MARKED, self.CLEAN)
        self.assertEqual((rc, calls), (0, 1))
        stands = report_reviews.standing(
            self.reviews(), "REPORT.md", P, self.reviews()[-1].fingerprint
        )
        self.assertTrue(stands.released)

    def test_the_twin_an_honest_report_is_released_once(self):
        rc, out, _, calls = self.review(HONEST, self.CLEAN)
        self.assertEqual((rc, calls), (0, 1))
        self.assertIn("this state is released", out)
        rc, out, _, calls = self.review(HONEST, self.CLEAN)
        self.assertEqual((rc, calls), (0, 0))  # no second call on a judged state
        self.assertIn("nothing to do", out)

    def test_its_own_record_leaves_the_fingerprint_as_it_was(self):
        report = self.a.report(HONEST)
        proto = self.a.area / "PROTOCOL-x.md"
        _, _, before = report_review.gather_report(self.a.area, report, proto)
        self.review(HONEST, self.CLEAN)
        _, _, after = report_review.gather_report(self.a.area, report, proto)
        self.assertEqual(
            report_reviews.fingerprint(before), report_reviews.fingerprint(after)
        )
        # the folder is no record and no decision review to their readers
        self.assertEqual(len(findings.area_records(self.a.area)), 1)

    def test_an_unreadable_reply_is_no_review(self):
        rc, _, _, _ = self.review(MARKED, "looks fine to me")
        self.assertEqual(rc, 2)
        self.assertEqual(self.reviews(), [])
        # the attempt ends without a record, said why, the answer kept
        (a,) = attempts.read_journal(self.a.area)
        self.assertEqual(a.outcome, "none")
        self.assertTrue(a.error)
        self.assertEqual(
            (self.a.area / "audits" / a.answer).read_text(encoding="utf-8"),
            "looks fine to me",
        )

    def test_a_review_is_journaled_with_its_answer_and_its_record(self):
        self.review(MARKED, self.CLAIMED)
        (a,) = attempts.read_journal(self.a.area)
        (r,) = self.reviews()
        self.assertEqual(
            (a.mode, a.outcome, a.file),
            ("report-review", "record", f"report-reviews/{r.path.name}"),
        )
        self.assertEqual(a.scope_sha, r.fingerprint)  # the inputs it was given
        self.assertEqual(
            (self.a.area / "audits" / a.answer).read_text(encoding="utf-8"),
            self.CLAIMED,
        )
        self.assertEqual(attempts.area_gaps(self.a.area).blockers, [])

    def test_a_deleted_review_with_a_claim_is_named_and_refuses_the_next_call(self):
        """Ninth haiku round, t5: a report review naming two claims was
        deleted; without it nothing held the state, and a clean draw would
        have released it."""
        self.review(MARKED, self.CLAIMED)
        (r,) = self.reviews()
        r.path.unlink()
        (gap,) = attempts.area_gaps(self.a.area).blockers
        self.assertIn(f"audits/report-reviews/{r.path.name}", gap)
        rc, _, err, calls = self.review(MARKED, self.CLEAN)
        self.assertEqual((rc, calls), (2, 0))
        self.assertIn(r.path.name, err)
        self.assertEqual(self.reviews(), [])

    def test_a_backend_that_does_not_answer_ends_the_attempt_with_its_cause(self):
        report = self.a.report(MARKED)

        def down(*args, **kw):
            raise llm_backends.BackendError("claude-cli: exit 1, empty stderr")

        with (
            mock.patch.object(audit.llm, "complete", down),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            rc = report_review.review_report(self.a.area, report, None, "m", 60, None)
        self.assertEqual(rc, 2)
        (a,) = attempts.read_journal(self.a.area)
        self.assertEqual((a.outcome, a.file, a.answer), ("none", "", ""))
        self.assertIn("exit 1, empty stderr", a.error)

    def test_a_plain_value_error_is_refused_not_a_traceback(self):
        # the report review listed no ValueError among its refusals; one
        # list serves the audit and both reviewers now (audit 2026-10-27,
        # third, M7)
        report = self.a.report(MARKED)

        def broken(*args, **kw):
            raise ValueError("a line that does not read")

        with (
            mock.patch.object(audit.llm, "complete", broken),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            rc = report_review.review_report(self.a.area, report, None, "m", 60, None)
        self.assertEqual(rc, 2)
        self.assertIn("a line that does not read", err.getvalue())
        (a,) = attempts.read_journal(self.a.area)
        self.assertEqual(a.outcome, "none")

    def test_no_call_no_attempt(self):
        """A state already judged makes no call, and so no attempt."""
        self.review(HONEST, self.CLEAN)
        self.review(HONEST, self.CLEAN)  # nothing to do
        self.assertEqual(len(attempts.read_journal(self.a.area)), 1)


class Records(unittest.TestCase):
    """`report_reviews`: the record reads loud; the release rule is pure."""

    def _write(self, claims=(), again=False, whole="f1") -> Path:
        area = Path(tempfile.mkdtemp())
        return report_reviews.write_report_review(
            area,
            model="m",
            report="REPORT.md",
            protocol=P,
            whole=whole,
            parts={"REPORT REPORT.md": "d1"},
            claims=list(claims),
            again=again,
        )

    def test_a_written_record_reads_back(self):
        claim = report_reviews.ReportClaim(5, "result", "AUROC of the run")
        r = report_reviews.read_report_review(self._write([claim]))
        self.assertEqual((r.report, r.protocol, r.fingerprint), ("REPORT.md", P, "f1"))
        self.assertEqual(r.claims, (claim,))
        self.assertEqual(r.parts, {"REPORT REPORT.md": "d1"})

    def test_a_record_that_does_not_hold_raises_naming_the_field(self):
        path = self._write([report_reviews.ReportClaim(5, "result", "x")])
        text = path.read_text(encoding="utf-8")
        for bad, said in (
            (text.replace("claims = 1", "claims = 2"), "claims = 2"),
            (text.replace('kind = "result"', 'kind = "maybe"'), "kind 'maybe'"),
            (text.replace("again = false", 'again = "no"'), "again is not true"),
            (text.replace("fingerprint = ", "print = "), "fingerprint is missing"),
        ):
            path.write_text(bad, encoding="utf-8")
            with self.assertRaisesRegex(report_reviews.ReportReviewError, said):
                report_reviews.read_report_review(path)

    def test_standing_releases_only_a_clean_state_no_claim_holds(self):
        def rr(fp, claims=(), again=False):
            return report_reviews.ReportReview(
                Path("x"), "d", "m", "REPORT.md", P, fp, {}, again, tuple(claims)
            )

        claim = report_reviews.ReportClaim(1, "result", "x")
        standing = report_reviews.standing
        self.assertFalse(standing([], "REPORT.md", P, "f").released)
        self.assertTrue(standing([rr("f")], "REPORT.md", P, "f").released)
        self.assertFalse(standing([rr("f", again=True)], "REPORT.md", P, "f").released)
        held = standing([rr("f", [claim]), rr("f")], "REPORT.md", P, "f")
        self.assertFalse(held.released)
        self.assertEqual(len(held.claims), 1)
        other = standing([rr("old")], "REPORT.md", P, "f")
        self.assertFalse(other.released)
        self.assertEqual(other.earlier.fingerprint if other.earlier else "", "old")
        self.assertFalse(standing([rr("f")], "OTHER.md", P, "f").released)


class Cli(unittest.TestCase):
    def test_report_review_goes_alone(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            audit.main(["x", "--report-review", "REPORT.md", "--review"])

    def test_the_instructions_ship(self):
        self.assertIn("Report review", audit.instructions("report"))
        self.assertEqual(audit.cited_rules("report"), ["LAB-011", "LAB-050"])


if __name__ == "__main__":
    unittest.main()
