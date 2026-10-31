"""`labkit-audit --review`: a second auditor on the `stands` decisions of one
analysis record (`gates/decision_review`), the review file it writes
(`formats/reviews`), and report-check's blocker or warning for a `stands`
no review upholds, according to the finding's grade. The model call is
faked; the tests cover what the reviewer gets to read, what is recorded
from its answer, and what releases.

History: docs/notes/2026-10-23-decision-review-history.md.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from protocol_fixture import registration_of, completed_run, head, scope_file, shown_sha

from labkit.formats import attempts, findings, promises, reviews, scope_sha
from labkit.gates import audit, decision_review, report_check
from labkit.run import llm_backends
from labkit.tools import protocol_result

RUN = "2026-10-07T10-00-00_ab12"
BLOCKER = (
    "BLOCKER",
    "BLOCKER · experiments/01-x/scripts/01_measure.py:1 · the threshold is fit "
    "in-sample · criterion_1_pass reads True for any rows · LAB-050 Analysis audit before "
    "reporting · fit it out of sample",
)
WARNING = (
    "WARNING",
    "WARNING · experiments/01-x/scripts/01_measure.py:1 · one seed · the spread is "
    "unknown · LAB-015 Preflight audit before freezing · report the spread",
)
UPHELD = "DECISION #1 · upheld · the Conclusion claims an in-sample fit and no more\nverdict: 1 upheld, 0 rejected, 0 insufficient\n"
REJECTED = (
    "DECISION #1 · rejected · the reason restates the finding; criterion_1_pass as reported "
    "rests on the in-sample fit\nverdict: 0 upheld, 1 rejected, 0 insufficient\n"
)
INSUFFICIENT = (
    "DECISION #1 · insufficient · the reason names no diff and no sha; whether "
    "the rows are stale is not on the page\nverdict: 0 upheld, 0 rejected, "
    "1 insufficient\n"
)


def area_with(
    rows: list[tuple[str, str]],
    decide: dict[int, tuple[str, str, str]],
    *,
    promise_block: str | None = "",
) -> tuple[Path, Path]:
    """(area, record) — a low-lane area whose one run is audited with ROWS,
    each finding N decided as DECIDE[N] = (status, reason, effect); its
    protocol's [[promise]] tables PROMISE_BLOCK (`head`'s `promises`: the
    default tables, None for none — a computation's)."""
    root = Path(tempfile.mkdtemp())
    (root / ".git").mkdir()  # the layout root, so paths show repo-relative
    area = root / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "scripts" / "02_analyze.py").write_text("print('ok')\n", encoding="utf-8")
    scope_file(area)
    proto = area / "PROTOCOL-x.md"
    proto.write_text(
        head(repeat_cost="low", result=RUN, promises=promise_block)
        + "- **Question / hypothesis:** does it hold?\n"
        + "- **Conclusion:** the fit is in-sample; nothing more is claimed.\n"
        + f"- **Recorded results:** criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: (run {RUN})\n",
        encoding="utf-8",
    )
    run = completed_run(
        area,
        RUN,
        metrics={
            "criterion_1_pass": True,
            "quality_check_1_pass": True,
            "quality_check_2_pass": True,
        },
    )
    src = area / "data.jsonl"
    src.write_text('{"id": 1}\n', encoding="utf-8")
    cfg = run / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["data"] = {"cases": {"path": str(src), "sha": "x", "rows": 1}}
    cfg.write_text(json.dumps(data), encoding="utf-8")
    record = findings.write(
        area,
        "analysis",
        "opus",
        scope_sha.area_stamp(area)[0],
        promises.block_stamp(proto.read_text(encoding="utf-8")),
        (
            sum(g == "BLOCKER" for g, _ in rows),
            sum(g == "WARNING" for g, _ in rows),
            0,
        ),
        rows,
        run_id=RUN,
        shown_sha=shown_sha(area, run),
        registration=registration_of(area),
    )
    for n, (status, reason, effect) in decide.items():
        findings.write_decision(record, n, status, reason, effect)
    # the result section as --from-run writes it: Recorded results with its
    # note, one Limitation line per decided limitation
    rendered, _ = protocol_result.render_result(proto.read_text(encoding="utf-8"), area)
    proto.write_text(rendered, encoding="utf-8")
    return area, record


def decide(record: Path, n: int, status: str, reason: str, effect: str = "") -> None:
    """Decide finding N and write the result section again, as the person
    does after `--decide` (`protocol-fill --render`): a Limitation line of a
    closed finding would otherwise stand stale."""
    findings.write_decision(record, n, status, reason, effect)
    area = record.parent.parent
    proto = area / "PROTOCOL-x.md"
    rendered, _ = protocol_result.render_result(proto.read_text(encoding="utf-8"), area)
    proto.write_text(rendered, encoding="utf-8")


def run_review(area: Path, answer: str, *extra: str) -> tuple[int, str, str, list[str]]:
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
        rc = audit.main([str(area), "--review", *extra])
    return rc, out.getvalue(), err.getvalue(), sent


def gate(area: Path) -> tuple[int, str]:
    """report-check with finalize and recomputation stood in."""
    buf = io.StringIO()
    no_gaps = SimpleNamespace(missing_must=[], must_holes=[])
    with (
        mock.patch.object(report_check, "check_fields", return_value=no_gaps),
        mock.patch.object(report_check, "finalize_area", return_value=0),
        mock.patch.object(report_check, "check_analysis_script", return_value=None),
        mock.patch.object(report_check, "registration_gaps", return_value=[]),
        contextlib.redirect_stdout(buf),
    ):
        code = report_check.report_check(area)
    return code, buf.getvalue()


class Reviewable(unittest.TestCase):
    def test_only_stands_limits_are_reviewed(self):
        _, record = area_with(
            [BLOCKER, BLOCKER, WARNING, WARNING],
            {
                1: ("limitation", "an in-sample fit, said so", "stands"),
                2: (
                    "limitation",
                    "the run cannot judge it",
                    "criterion-1 not assessable",
                ),
                3: ("limitation", "one seed", "stands"),
                4: ("limitation", "noted", ""),
            },
        )
        rec = findings.read(record)
        self.assertEqual([n for n, _ in decision_review.reviewable(rec, [])], [1, 3])

    def test_named_files_resolve_against_the_repo_then_the_area(self):
        area, record = area_with([BLOCKER], {1: ("limitation", "r", "stands")})
        rec = findings.read(record)
        files = decision_review.named_files(
            decision_review.reviewable(rec, []), area.parent.parent, area
        )
        self.assertEqual(files, [(area / "scripts" / "01_measure.py").resolve()])


class TheCall(unittest.TestCase):
    def test_the_reviewer_reads_decisions_protocol_named_files_rows_and_rules(self):
        area, record = area_with(
            [BLOCKER],
            {
                1: (
                    "limitation",
                    "the fit is in-sample, the Conclusion says so",
                    "stands",
                )
            },
        )
        rc, out, err, sent = run_review(area, UPHELD)
        self.assertEqual(rc, 0, out + err)
        prompt = sent[0]
        self.assertIn("Decision review — does the reported claim stand", prompt)
        self.assertIn(
            f"MODE: review · AREA: experiments/01-x · RECORD: {record.name}", prompt
        )
        self.assertIn(f"===== {decision_review.DECISIONS_LABEL} =====", prompt)
        self.assertIn(
            "#1 · BLOCKER · BLOCKER · experiments/01-x/scripts/01_measure.py:1", prompt
        )
        self.assertIn("reason: the fit is in-sample, the Conclusion says so", prompt)
        self.assertIn("effect: stands", prompt)
        self.assertIn("===== FILE: experiments/01-x/PROTOCOL-x.md =====", prompt)
        self.assertIn(
            "===== FILE: experiments/01-x/scripts/01_measure.py =====", prompt
        )
        self.assertIn("def evaluate_rows", prompt)
        self.assertIn(
            f"===== FILE: experiments/01-x/runs/{RUN}/metrics.json =====", prompt
        )
        self.assertIn("LAB-015, LAB-050 — the rules this audit cites", prompt)
        self.assertIn("LAB-015 · Preflight audit before freezing", prompt)
        self.assertNotIn("Experiment preflight audit", prompt)  # not the auditor's text
        self.assertIn("labkit-audit: review · ", err)
        self.assertIn("1 upheld, 0 rejected, 0 insufficient", out)

    def test_an_upheld_review_releases_the_stands_and_the_gate_is_silent(self):
        area, record = area_with(
            [BLOCKER], {1: ("limitation", "in-sample, said so", "stands")}
        )
        code, out = gate(area)
        self.assertEqual(code, 1, out)  # a BLOCKER's stands blocks until upheld
        self.assertIn("BLOCKER: Limitation (audit", out)
        self.assertIn(
            "`stands` on a BLOCKER decided limitation not reviewed — no decision review upholds",
            out,
        )
        self.assertIn(f"--review --record {record.name}", out)
        self.assertNotIn("<area>", out)  # the whole command, ready to run
        self.assertNotIn("write the Conclusion", out)  # it is written
        rc, _, _, _ = run_review(area, UPHELD)
        self.assertEqual(rc, 0)
        (review,) = reviews.area_reviews(area)
        rec = findings.read(record)
        self.assertEqual(review.record, record.name)
        self.assertEqual(
            (review.scope_sha, review.shown_sha), (rec.scope_sha, rec.shown_sha)
        )
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        self.assertEqual(review.claim_sha, reviews.claim_digest(text))
        self.assertTrue(reviews.upholding(rec, 1, [review], text))
        code, out = gate(area)
        self.assertEqual(code, 0, out)
        self.assertNotIn("decision review", out)
        # the review file is no findings record
        self.assertEqual(len(findings.area_records(area)), 1)

    def test_a_rejected_review_does_not_release_and_the_gate_says_why(self):
        area, _ = area_with([BLOCKER], {1: ("limitation", "Finding noted", "stands")})
        rc, out, _, _ = run_review(area, REJECTED)
        self.assertEqual(rc, 1, out)
        self.assertIn("rejected: decide the finding again first", out)
        self.assertIn("auditing again does not settle a rejection", out)
        code, out = gate(area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "`stands` on a BLOCKER decided limitation rejected: the reason restates",
            out,
        )

    def test_after_a_rejection_not_assessable_is_offered_only_with_a_promise(self):
        """A computation registers no promise and `--decide` refuses every id
        an effect names; the review offered `--effect "<ID> not assessable"`
        there all the same (pilot t34, t21, 2026-10-28). Its routes name
        what works instead; the twin keeps the route."""
        for block, offered in ((None, False), ("", True)):
            with self.subTest(promises="none" if block is None else "default"):
                area, _ = area_with(
                    [BLOCKER],
                    {1: ("limitation", "Finding noted", "stands")},
                    promise_block=block,
                )
                rc, out, _, _ = run_review(area, REJECTED)
                self.assertEqual(rc, 1, out)
                (line,) = [ln for ln in out.splitlines() if "  rejected: " in ln]
                self.assertEqual("--not-assessable <ID>" in line, offered, line)
                self.assertEqual("hand the protocol over" in line, not offered)
                rc, _, err, sent = run_review(area, UPHELD)  # contested: refused
                self.assertEqual((rc, sent), (2, []))
                self.assertEqual("effect `not assessable`" in err, offered, err)
                self.assertEqual("hand the protocol over" in err, not offered)

    def test_report_check_asks_a_limit_without_its_effect_to_decide_again(self):
        """A BLOCKER decided limitation without its effect (a record changed by
        hand: `--decide … limit` writes it): report-check names the decision
        to make again, with or without promises registered."""
        for block, offered in ((None, False), ("", True)):
            with self.subTest(promises="none" if block is None else "default"):
                area, record = area_with([BLOCKER], {}, promise_block=block)
                text = record.read_text(encoding="utf-8")
                record.write_text(
                    text.replace(
                        'status = "open"\nreason = ""',
                        'status = "limitation"\nreason = "kept"',
                        1,
                    )
                )
                _, out = gate(area)
                (line,) = [
                    ln
                    for ln in out.splitlines()
                    if "BLOCKER:" in ln and "owes its effect" in ln
                ]
                self.assertIn("decide it again", line)
                self.assertIn("--decide 1 limitation --why", line)

    def test_the_twin_a_warnings_stands_without_a_review_only_warns(self):
        """The scope, narrow at first: the release does not hang on every
        lesser limit — an accepted WARNING's `stands` no review upholds is a
        warning, a BLOCKER's a blocker."""
        area, _ = area_with(
            [WARNING], {1: ("limitation", "one seed, said so", "stands")}
        )
        code, out = gate(area)
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING: Limitation (audit", out)
        self.assertIn("`stands` on a WARNING decided limitation not reviewed", out)
        self.assertNotIn("BLOCKER:", out)

    def test_the_reviewer_sees_the_result_as_it_renders(self):
        area, record = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        _, _, _, sent = run_review(area, UPHELD)
        self.assertIn(f"===== {decision_review.RESULT_LABEL} =====", sent[0])
        self.assertIn(
            f"- **Limitation (audit {record.stem} #1):** the verdicts stand", sent[0]
        )
        self.assertIn(
            f"- **Recorded results:** criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: (run {RUN})",
            sent[0],
        )

    def test_a_changed_decision_makes_the_review_stale(self):
        area, record = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        run_review(area, UPHELD)
        findings.write_decision(
            record, 1, "limitation", "in-sample, and more", "stands"
        )
        rec = findings.read(record)
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        self.assertFalse(reviews.upholding(rec, 1, reviews.area_reviews(area), text))
        self.assertEqual(
            reviews.state(rec, 1, reviews.area_reviews(area), text),
            reviews.NOT_REVIEWED,
        )

    def test_a_rewritten_claim_makes_the_review_stale(self):
        """The wording of the claim separates upheld from rejected (replay
        2026-10-22): a Conclusion strengthened after the review is another
        claim, and the gate asks again."""
        area, record = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        run_review(area, UPHELD)
        code, out = gate(area)
        self.assertNotIn("decision review", out)
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        proto.write_text(
            text.replace(
                "the fit is in-sample; nothing more is claimed.",
                "the classifier generalises to unseen compounds.",
            ),
            encoding="utf-8",
        )
        rec = findings.read(record)
        self.assertFalse(
            reviews.upholding(
                rec, 1, reviews.area_reviews(area), proto.read_text(encoding="utf-8")
            )
        )
        code, out = gate(area)
        self.assertEqual(code, 1, out)
        self.assertIn("`stands` on a BLOCKER decided limitation not reviewed", out)
        # the claim's digest reads the Conclusion and nothing generated: the
        # lines --from-run writes after the decision must not stale a review
        self.assertEqual([k for k, _ in reviews.reported_claim(text)], ["Conclusion"])
        self.assertEqual(
            reviews.claim_digest(text),
            reviews.claim_digest(text.replace("criterion-1 met", "criterion-1 missed")),
        )

    def test_a_rejection_before_a_claim_edit_stays_in_the_sentence(self):
        """Eighth haiku round (t5, decision 08-48 #2): the review rejected a
        decision, the agent edited the Conclusion, and report-check named
        the decision only "not reviewed" — the rejection was out of sight.
        Now the state says not reviewed as claimed now and what the earlier
        review said; the grade is unchanged (a WARNING stays a warning)."""
        for grade, code_now in ((WARNING, 0), (BLOCKER, 1)):
            area, record = area_with([grade], {1: ("limitation", "noted", "stands")})
            run_review(area, REJECTED)
            proto = area / "PROTOCOL-x.md"
            text = proto.read_text(encoding="utf-8").replace(
                "the fit is in-sample; nothing more is claimed.",
                "the fit is in-sample; criterion-1 is not assessable with this run.",
            )
            proto.write_text(text, encoding="utf-8")
            state = reviews.state(
                findings.read(record), 1, reviews.area_reviews(area), text
            )
            self.assertTrue(
                state.startswith(
                    "not reviewed as decided and claimed now; earlier rejected: "
                ),
                state,
            )
            code, out = gate(area)
            self.assertEqual(code, code_now, out)
            self.assertIn("earlier rejected: the reason restates", out)

    def test_a_review_nobody_can_read_is_named_by_the_gate(self):
        area, _ = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        run_review(area, UPHELD)
        (review,) = (area / "audits").glob("*-review.toml")
        review.write_text(
            review.read_text(encoding="utf-8").replace("claim_sha", "claim_sh"),
            encoding="utf-8",
        )
        code, out = gate(area)
        self.assertEqual(code, 1, out)  # the BLOCKER's stands stays unupheld
        self.assertIn("a review nobody can read", out)
        self.assertIn("review again", out)

    def test_an_again_draw_alone_releases_nothing(self):
        """`--again` on a decision never reviewed skipped the contested check
        and its `upheld` released the decision, though the rule decided for
        both reviews is that an `--again` draw releases nothing (2026-10-27).
        The record says it was one, its verdicts count, and the exit says
        the state. The twin: a review without `--again` on the same state
        releases it."""
        area, record = area_with(
            [BLOCKER], {1: ("limitation", "Finding noted", "stands")}
        )
        rc, out, _, sent = run_review(area, UPHELD, "--again")
        self.assertEqual((rc, len(sent)), (1, 1))
        self.assertIn("(--again, it releases nothing)", out)
        rec = findings.read(record)
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        found = reviews.area_reviews(area)
        self.assertTrue(found[0].again)
        self.assertFalse(reviews.upholding(rec, 1, found, text))
        self.assertIn(
            "only `--again` draws said upheld", reviews.state(rec, 1, found, text)
        )
        rc, out, _, _ = run_review(area, UPHELD)
        self.assertEqual(rc, 0, out)
        self.assertIn("review state: every decision reviewed is released", out)
        self.assertTrue(reviews.upholding(rec, 1, reviews.area_reviews(area), text))

    def test_a_rejected_decision_is_not_released_by_a_later_draw(self):
        """Review 2026-10-22: the newest matching review won, so an unchanged
        rejected could be re-reviewed until an upheld came. Now every draw
        on one state counts, the command refuses another draw, and deciding
        again is the way out."""
        area, record = area_with(
            [BLOCKER], {1: ("limitation", "Finding noted", "stands")}
        )
        rc, _, _, _ = run_review(area, REJECTED)
        self.assertEqual(rc, 1)
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("another draw settles nothing", err)
        self.assertIn("decide again", err)
        rc, out, _, sent = run_review(area, UPHELD, "--again")
        # the draw itself says upheld, the exit the state: held
        self.assertEqual((rc, len(sent)), (1, 1))
        self.assertIn("review state: held — finding(s) 1 not released", out)
        rec = findings.read(record)
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        found = reviews.area_reviews(area)
        self.assertEqual(len(found), 2)
        self.assertFalse(
            reviews.upholding(rec, 1, found, text)
        )  # …and releases nothing
        self.assertIn(
            "contested over 2 draws (1 upheld, 1 rejected",
            reviews.state(rec, 1, found, text),
        )
        code, out = gate(area)
        self.assertIn("contested over 2 draws", out)
        # deciding again is a new state: one upheld review on it releases
        findings.write_decision(
            record,
            1,
            "limitation",
            "the Conclusion claims the in-sample fit only",
            "stands",
        )
        rc, _, _, sent = run_review(area, UPHELD)
        self.assertEqual((rc, len(sent)), (0, 1))
        rec = findings.read(record)
        self.assertTrue(reviews.upholding(rec, 1, reviews.area_reviews(area), text))

    def test_dismissed_after_insufficient_owes_a_review_of_its_own(self):
        """Sixth haiku round (2026-10-23, t5, steps 104–105): the reviewer
        found the evidence for a `stands` insufficient; the agent dismissed
        the finding with "insufficient evidence withdrawn" and the state
        was released — a dismissal needed no review. Now a finding a review
        did not uphold is held under `false-positive` or `fixed`
        until a review upholds the new decision; a filled-in reason alone
        releases nothing."""
        area, record = area_with(
            [BLOCKER], {1: ("limitation", "rows are stale, see the diff", "stands")}
        )
        rc, _, _, _ = run_review(area, INSUFFICIENT)
        self.assertEqual(rc, 1)
        for status in ("fixed", "false-positive"):
            with self.subTest(status=status):
                decide(record, 1, status, "insufficient evidence withdrawn")
                code, out = gate(area)
                self.assertEqual(code, 1, out)
                self.assertIn(
                    f"`{status}` on a BLOCKER a review said insufficient on", out
                )
                self.assertIn("closing a finding a reviewer did not uphold", out)
                self.assertIn(f"--review --record {record.name}", out)
                self.assertNotIn("Limitation (audit", out)  # no limit: closed
        # the reviewer is asked about the new decision, and sees what it answers to
        rc, _, _, sent = run_review(area, UPHELD)
        self.assertEqual((rc, len(sent)), (0, 1))
        self.assertIn("   status: false-positive", sent[0])
        self.assertIn("   reason: insufficient evidence withdrawn", sent[0])
        self.assertIn(
            "   decided again after a review said insufficient: the reason names "
            "no diff",
            sent[0],
        )
        self.assertNotIn("   effect:", sent[0])
        # the twin: the upholding review of the new decision releases
        code, out = gate(area)
        self.assertEqual(code, 0, out)
        self.assertNotIn("decision review", out)

    def test_a_first_dismissal_of_a_blocker_owes_a_review(self):
        """A BLOCKER dismissed without any review on it: the deciding
        agent's own decision does not release it (decided 2026-10-28); a
        review that upholds the dismissal does."""
        area, record = area_with(
            [BLOCKER],
            {1: ("false-positive", "the threshold is read from the config", "")},
        )
        code, out = gate(area)
        self.assertEqual(code, 1, out)
        self.assertIn("`false-positive` on a BLOCKER not reviewed", out)
        rec = findings.read(record)
        self.assertEqual([n for n, _ in decision_review.reviewable(rec, [])], [1])
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual(rc, 0, err)
        code, out = gate(area)
        self.assertEqual(code, 0, out)

    def test_the_twin_a_dismissed_warning_nobody_contested_owes_no_review(self):
        """A WARNING dismissed without any review on it was never contested:
        it is decided, not under review, and the gate is silent."""
        area, record = area_with(
            [WARNING],
            {1: ("false-positive", "the threshold is read from the config", "")},
        )
        code, out = gate(area)
        self.assertEqual(code, 0, out)
        self.assertNotIn("decision review", out)
        rec = findings.read(record)
        self.assertEqual(decision_review.reviewable(rec, []), [])
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("nothing to review", err)

    def test_a_closed_warning_after_a_rejection_only_warns(self):
        """The grade rule holds for a closed contested finding as for a
        `stands`: a WARNING's is a warning, a BLOCKER's a blocker."""
        area, record = area_with(
            [WARNING], {1: ("limitation", "Finding noted", "stands")}
        )
        run_review(area, REJECTED)
        decide(record, 1, "false-positive", "one seed is enough here")
        code, out = gate(area)
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING: audit", out)
        self.assertIn("`false-positive` on a WARNING a review said rejected on", out)

    def test_a_report_that_disagrees_with_itself_records_nothing(self):
        area, _ = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        for bad in (
            "DECISION #1 · upheld · x\nverdict: 0 upheld, 1 rejected, 0 insufficient\n",
            "DECISION #2 · upheld · x\nverdict: 1 upheld, 0 rejected, 0 insufficient\n",
            "no verdict here\n",
        ):
            rc, _, err, _ = run_review(area, bad)
            self.assertEqual(rc, 2, err)
        self.assertEqual(reviews.area_reviews(area), [])
        self.assertIn(
            "the record asked about [1]", err
        ) if "DECISION #2" in bad else None

    def test_code_changed_after_the_record_is_refused(self):
        area, _ = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        (area / "scripts" / "01_measure.py").write_text("x = 1\n", encoding="utf-8")
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual(rc, 2)
        self.assertEqual(sent, [])  # no call on a state the auditor did not read
        self.assertIn("the record's auditor read", err)

    def test_the_gate_names_the_conclusion_before_the_review(self):
        """The refusal names what `--review` needs first: with the
        Conclusion a placeholder, the step is to write it, then the review
        (ninth haiku round, t3, never ran the review the gate named)."""
        area, record = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            proto.read_text(encoding="utf-8").replace(
                "- **Conclusion:** the fit is in-sample; nothing more is claimed.",
                "- **Conclusion:** <the answer to the question above, in at most two plain sentences…>",
            ),
            encoding="utf-8",
        )
        code, out = gate(area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "write the Conclusion in PROTOCOL-x.md first (the review judges that claim",
            out,
        )
        self.assertIn("then `labkit-audit ", out)
        self.assertIn(f"--review --record {record.name}`", out)

    def test_record_by_bare_name_and_a_conclusion_still_owed(self):
        """Round on 86e38bc (judge-2): `--record 2026-…-analysis.toml` as the
        gate names it was refused with "No such file"; and a review made
        while the Conclusion was a placeholder went stale when it was
        written — a second opus call. The name resolves under audits/,
        and the review asks for the Conclusion first."""
        area, record = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        rc, _, _, sent = run_review(area, UPHELD, "--record", record.name)
        self.assertEqual((rc, len(sent)), (0, 1))
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        proto.write_text(
            text.replace(
                "- **Conclusion:** the fit is in-sample; nothing more is claimed.",
                "- **Conclusion:** <the answer to the question above, in at most two plain sentences…>",
            ),
            encoding="utf-8",
        )
        rc, _, err, sent = run_review(area, UPHELD, "--record", record.name)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("the Conclusion is not written yet", err)
        # --decide takes the bare name too
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = audit.main(
                [
                    str(area),
                    "--decide",
                    "1",
                    "limitation",
                    "--why",
                    "in-sample, said so",
                    "--record",
                    record.name,
                ]
            )
        self.assertEqual(rc, 0, out.getvalue())

    def test_nothing_to_review_is_a_refusal(self):
        area, _ = area_with([BLOCKER], {1: ("fixed", "fixed it", "")})
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("no finding decided `limitation` with effect `stands`", err)


class TheFile(unittest.TestCase):
    def test_counts_and_verdicts_are_held_on_read(self):
        area = Path(tempfile.mkdtemp())
        d = reviews.Decision(1, "a" * 12, "upheld", "fine")
        path = reviews.write_review(
            area, "opus", "r.toml", "s" * 12, "h" * 12, "c" * 12, [d], again=False
        )
        self.assertEqual(reviews.read_review(path).counts, (1, 0, 0))
        text = path.read_text(encoding="utf-8")
        # a review written before `again` was recorded is not read: whether
        # it was an `--again` draw cannot be told
        path.write_text(text.replace("again = false\n", ""), encoding="utf-8")
        with self.assertRaisesRegex(reviews.ReviewError, "again is missing"):
            reviews.read_review(path)
        path.write_text(text, encoding="utf-8")
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("upheld = 1", "upheld = 2"), encoding="utf-8")
        with self.assertRaisesRegex(reviews.ReviewError, "counts"):
            reviews.read_review(path)
        path.write_text(
            text.replace('verdict = "upheld"', 'verdict = "ok"'), encoding="utf-8"
        )
        with self.assertRaisesRegex(reviews.ReviewError, "verdict 'ok'"):
            reviews.read_review(path)
        with self.assertRaisesRegex(ValueError, "reviewed twice"):
            reviews.write_review(
                area, "opus", "r.toml", "s", "h", "c", [d, d], again=False
            )
        self.assertEqual(
            findings.written_order(path),
            ("".join(path.name.split("-review")[:1]), 1, path.name),
        )
        # a second review of the minute: numbered before the suffix, read as
        # a review and never as a findings record
        path.write_text(text, encoding="utf-8")
        second = reviews.write_review(
            area, "opus", "r.toml", "s", "h", "c", [d], again=False
        )
        self.assertTrue(second.name.endswith("-review-2.toml"), second.name)
        self.assertEqual([r.path for r in reviews.area_reviews(area)], [path, second])
        self.assertEqual(findings.area_records(area), [])


class Journal(unittest.TestCase):
    """A review is an attempt in the area's journal, as an audit is: the
    start before the call, the answer kept before it is read, the end with
    the record or why there is none. A review deleted before the commit is
    named by the attempt that wrote it (ninth haiku round, t5 deleted a
    report review that named two claims)."""

    def test_a_review_is_journaled_with_its_answer_and_its_record(self):
        area, _ = area_with(
            [BLOCKER], {1: ("limitation", "in-sample, said so", "stands")}
        )
        rc, _, _, _ = run_review(area, UPHELD)
        self.assertEqual(rc, 0)
        (a,) = attempts.read_journal(area)
        (review,) = reviews.area_reviews(area)
        self.assertEqual(
            (a.mode, a.outcome, a.file), ("review", "record", review.path.name)
        )
        self.assertEqual(
            (area / "audits" / a.answer).read_text(encoding="utf-8"), UPHELD
        )
        self.assertEqual(attempts.area_gaps(area).blockers, [])

    def test_a_deleted_review_is_named_and_refuses_the_next_call(self):
        area, _ = area_with([BLOCKER], {1: ("limitation", "Finding noted", "stands")})
        run_review(area, REJECTED)
        (review,) = reviews.area_reviews(area)
        review.path.unlink()
        (gap,) = attempts.area_gaps(area).blockers
        self.assertIn(f"audits/{review.path.name}", gap)
        # no repository git runs in (an empty .git), so no commit and no copy:
        # the loss is said, not a restore that cannot work
        self.assertIn("no commit and no copy keeps it: it is lost", gap)
        # with the rejection gone nothing else holds the draw; the journal does
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn(review.path.name, err)

    def test_a_backend_that_does_not_answer_ends_the_attempt_with_its_cause(self):
        area, _ = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})

        def down(alias, prompt, **kw):
            raise llm_backends.BackendError("claude-cli: exit 1, empty stderr")

        with (
            mock.patch.object(audit.llm, "complete", down),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            rc = audit.main([str(area), "--review"])
        self.assertEqual(rc, 2)
        (a,) = attempts.read_journal(area)
        self.assertEqual((a.outcome, a.file, a.answer), ("none", "", ""))
        self.assertIn("exit 1, empty stderr", a.error)
        self.assertEqual(reviews.area_reviews(area), [])

    def test_an_answer_that_does_not_read_is_kept_and_named(self):
        area, _ = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        rc, _, _, _ = run_review(area, "looks fine to me")
        self.assertEqual(rc, 2)
        (a,) = attempts.read_journal(area)
        self.assertEqual(a.outcome, "none")
        self.assertTrue(a.error)
        self.assertEqual(
            (area / "audits" / a.answer).read_text(encoding="utf-8"),
            "looks fine to me",
        )
        self.assertEqual(reviews.area_reviews(area), [])

    def test_the_twin_a_review_older_than_the_journal_is_not_held(self):
        """No entry is written afterwards for a review made before the
        journal: one that no attempt names stands as it is."""
        area, record = area_with([BLOCKER], {1: ("limitation", "in-sample", "stands")})
        d = reviews.Decision(1, "a" * 12, "upheld", "fine")
        reviews.write_review(area, "opus", record.name, "s", "h", "c", [d], again=False)
        self.assertEqual(attempts.read_journal(area), [])
        self.assertEqual(attempts.area_gaps(area).blockers, [])


if __name__ == "__main__":
    unittest.main()
