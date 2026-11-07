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
import os
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from protocol_fixture import (
    registration_of,
    completed_run,
    head,
    scope_file,
    shown_sha,
    source_entry,
)

from labkit.formats import attempts, findings, promises, reviews, scope_sha
from labkit.gates import audit, decision_review, report_check
from labkit.run import llm_backends
from labkit.tools import protocol_result

RUN = "2026-10-07T10-00-00_ab12"
BLOCKER = (
    "BLOCKER",
    "BLOCKER · experiments/01-x/scripts/01_measure.py:1 · statement · the threshold is fit "
    "in-sample · criterion_1_pass reads True for any rows · LAB-050 Analysis audit before "
    "reporting · fit it out of sample",
)
WARNING = (
    "WARNING",
    "WARNING · experiments/01-x/scripts/01_measure.py:1 · statement · one seed · the spread is "
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
    metrics: dict | None = None,
    before_audit: Callable[[Path], None] | None = None,
) -> tuple[Path, Path]:
    """(area, record) — a low-lane area whose one run is audited with ROWS,
    each finding N decided as DECIDE[N] = (status, reason, effect); its
    protocol's [[promise]] tables PROMISE_BLOCK (`head`'s `promises`: the
    default tables, None for none — a computation's); METRICS more keys of
    the run's metrics.json; BEFORE_AUDIT called with the area between the
    run and the audit that writes the record."""
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
        + f"- **Recorded results:** criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: kept number: n = 1 (run {RUN})\n",
        encoding="utf-8",
    )
    run = completed_run(
        area,
        RUN,
        metrics={
            "criterion_1_pass": True,
            "quality_check_1_pass": True,
            "quality_check_2_pass": True,
            **(metrics or {}),
        },
    )
    src = area / "data.jsonl"
    src.write_text('{"id": 1}\n', encoding="utf-8")
    cfg = run / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["data"] = {"cases": source_entry(src)}
    cfg.write_text(json.dumps(data), encoding="utf-8")
    if before_audit is not None:
        before_audit(area)
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
    no_gaps = SimpleNamespace(missing_must=[], must_holes=[], repeated=[])
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
        an effect names, so its review offers no `--effect "<ID> not
        assessable"`: its routes name what works instead; the twin keeps the
        route."""
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
                self.assertEqual("--not-assessable <ID>" in err, offered, err)
                self.assertEqual("hand the protocol over" in err, not offered)

    def test_rejected_false_positive_routes_follow_each_findings_subject(self):
        """A rejected false-positive offers only decisions the subject allows,
        both after the review and when a repeat review is refused."""
        for subject in findings.SUBJECTS:
            with self.subTest(subject=subject):
                line = BLOCKER[1].replace("· statement ·", f"· {subject} ·")
                if subject == findings.UNDETERMINED:
                    line += (
                        " · check: feature_count — clears if one, confirms otherwise"
                    )
                area, _ = area_with(
                    [("BLOCKER", line)],
                    {1: ("false-positive", "the kept rows show one feature", "")},
                    metrics={"feature_count": 1},
                )
                rc, out, err, _ = run_review(area, REJECTED)
                self.assertEqual(rc, 1, err)
                (route,) = [ln for ln in out.splitlines() if "  rejected: " in ln]
                rc, _, err, sent = run_review(area, UPHELD)
                self.assertEqual((rc, sent), (2, []))
                allowed = subject == findings.STATEMENT
                for hint in (route, err):
                    self.assertEqual("--decide N limitation" in hint, allowed, hint)
                    self.assertEqual("--not-assessable <ID>" in hint, allowed, hint)
                    self.assertEqual("limit the claim" in hint, allowed, hint)
                    if not allowed:
                        self.assertIn("repair or required check", hint)
                        self.assertIn("counter-evidence", hint)
                        self.assertIn("--handover", hint)

    def test_mixed_rejections_keep_their_recovery_routes_separate(self):
        """A statement's limitation route must not become an implementation's
        route when the same review rejects both false-positive decisions."""
        area, _ = area_with(
            [
                BLOCKER,
                ("BLOCKER", BLOCKER[1].replace("· statement ·", "· implementation ·")),
            ],
            {
                1: ("false-positive", "counter-evidence for the statement", ""),
                2: ("false-positive", "counter-evidence for the code", ""),
            },
        )
        answer = (
            "DECISION #1 · rejected · the claim still exceeds the rows\n"
            "DECISION #2 · rejected · the code still departs from registration\n"
            "verdict: 0 upheld, 2 rejected, 0 insufficient\n"
        )
        rc, out, err, _ = run_review(area, answer)
        self.assertEqual(rc, 1, err)
        routes = [ln for ln in out.splitlines() if "  rejected: " in ln]
        self.assertEqual(len(routes), 2, out)
        self.assertIn("--decide N limitation", routes[0])
        self.assertIn("finding #1", routes[0])
        self.assertNotIn("--decide N limitation", routes[1])
        self.assertIn("finding #2", routes[1])
        rc, _, err, sent = run_review(area, answer)
        self.assertEqual((rc, sent), (2, []))
        self.assertEqual(err.count("--decide N limitation"), 1, err)

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
            f"- **Recorded results:** criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: kept number: n = 1 (run {RUN})",
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
        """The wording of the claim separates upheld from rejected: a
        Conclusion strengthened after the review is another claim, and the
        gate asks again."""
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
        """A review rejected a decision, then the Conclusion was edited: the
        state says not reviewed as claimed now and what the earlier review
        said, so the rejection stays in sight; the grade is unchanged (a
        WARNING stays a warning)."""
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
        """An `--again` draw releases nothing, on a decision never reviewed
        too: the record says it was one, its verdicts count, and the exit
        says the state. The twin: a review without `--again` on the same state
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
        """Every draw on one state counts, so an unchanged rejected is not
        re-reviewed until an upheld comes: the command refuses another draw,
        and deciding again is the way out."""
        area, record = area_with(
            [BLOCKER], {1: ("limitation", "Finding noted", "stands")}
        )
        rc, _, _, _ = run_review(area, REJECTED)
        self.assertEqual(rc, 1)
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("another draw settles nothing", err)
        self.assertIn("decide the finding again first", err)
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
        """A finding a review did not uphold is held under `false-positive`
        or `fixed` until a review upholds the new decision: a dismissal with
        a filled-in reason alone releases nothing."""
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
        agent's own decision does not release it; a review that upholds the
        dismissal does."""
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
        Conclusion a placeholder, the step is to write it, then the
        review."""
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
        """`--record 2026-…-analysis.toml` as the gate names it resolves
        under audits/; and the review asks for the Conclusion first, since a
        review made while the Conclusion is a placeholder goes stale when it
        is written."""
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
        # a review that records no `again` is not read: whether it was an
        # `--again` draw cannot be told
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
    named by the attempt that wrote it."""

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


#: a BLOCKER whose closing field requires a check — the key a repair, or a
#: limitation resting on it, shows in the run (`findings.Finding.check`)
CHECKED: tuple[str, str] = (
    "BLOCKER",
    BLOCKER[1] + " · check: feature_count (must be 1)",
)


class RequiredCheckBesideTheDecision(unittest.TestCase):
    """A `stands` resting on what a required check would show meets what the
    run records. The review shows the check's
    value beside the decision, and the decision names a key the run lacks —
    a hint, never a hold."""

    def test_the_review_shows_a_required_check_missing_in_the_run(self):
        area, _ = area_with(
            [CHECKED], {1: ("limitation", "verified: one feature", "stands")}
        )
        rc, out, err, sent = run_review(area, INSUFFICIENT)
        self.assertEqual(rc, 1, out + err)
        decisions = sent[0].split(f"===== {decision_review.DECISIONS_LABEL} =====")[1]
        decisions = decisions.split("=====")[0]
        self.assertIn(
            "   required check `feature_count`: missing in the answering "
            "run's metrics.json",
            decisions,
        )

    def test_the_twin_a_required_check_the_run_carries_shows_its_value(self):
        area, _ = area_with(
            [CHECKED],
            {1: ("limitation", "one feature, counted in the run", "stands")},
            metrics={"feature_count": 1},
        )
        rc, out, err, sent = run_review(area, UPHELD)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("   required check `feature_count` (must be 1) = 1", sent[0])

    def test_the_twin_a_finding_without_a_check_shows_none(self):
        area, _ = area_with(
            [BLOCKER], {1: ("limitation", "in-sample, said so", "stands")}
        )
        rc, out, err, sent = run_review(area, UPHELD)
        self.assertNotIn("required check", sent[0])


def decide_cmd(area: Path, record: Path, *words: str) -> tuple[int, str]:
    """`labkit-audit AREA --decide 1 …` run from the repo root, as an agent runs it."""
    out = io.StringIO()
    old = Path.cwd()
    os.chdir(area.parents[1])
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = audit.main(
                ["experiments/01-x", "--decide", "1", *words, "--record", str(record)]
            )
    finally:
        os.chdir(old)
    return rc, out.getvalue()


class StandsCheckHint(unittest.TestCase):
    """`--decide 1 limitation` on a finding with a required check the run
    does not carry: a hint under the decision — the decision is stored as
    given (exit 0), no hold, no measurement owed otherwise."""

    HINT = "hint: this limitation rests on the finding's required check `feature_count`"

    def test_a_stands_on_a_check_the_run_lacks_is_told_so(self):
        area, record = area_with([CHECKED], {})
        rc, out = decide_cmd(
            area, record, "limitation", "--why", "verified: one feature"
        )
        self.assertEqual(rc, 0, out)
        self.assertIn(self.HINT, out)
        self.assertIn(
            "and run 2026-10-07T10-00-00_ab12's metrics.json does not carry it", out
        )
        self.assertIn("judges a reason the run does not show `insufficient`", out)
        self.assertIn("feature_count", out)
        self.assertEqual(findings.read(record).findings[0].status, "limitation")

    def test_the_twins_a_key_the_run_carries_no_check_or_another_status(self):
        for rows, words, metrics in (
            (
                [CHECKED],
                ("limitation", "--why", "one feature, counted"),
                {"feature_count": 1},
            ),
            ([BLOCKER], ("limitation", "--why", "in-sample, said so"), None),
            ([CHECKED], ("fixed", "--why", "counted now"), None),
            (
                [CHECKED],
                (
                    "limitation",
                    "--why",
                    "the run cannot judge it",
                    "--not-assessable",
                    "criterion-1",
                ),
                None,
            ),
        ):
            with self.subTest(words=words):
                area, record = area_with(list(rows), {}, metrics=metrics)
                rc, out = decide_cmd(area, record, *words)
                self.assertEqual(rc, 0, out)
                self.assertNotIn("hint: this limitation rests", out)


#: a WARNING placed in the protocol, as a unit finding is
IN_PROTOCOL: tuple[str, str] = (
    "WARNING",
    "WARNING · experiments/01-x/PROTOCOL-x.md:Unit · statement · the Unit field calls the "
    "powers ms² · every power is misread · LAB-015 Preflight audit before "
    "freezing · state the unit the run computes",
)
SCRIPT_PIECE = "===== FILE: experiments/01-x/scripts/01_measure.py ====="


class TheMeasuringScriptWithoutANamedFile(unittest.TestCase):
    """A finding placed in the protocol names no code; the review then shows
    the reviewed run's measuring script, the call that computed the
    number."""

    def test_a_finding_in_the_protocol_gets_the_runs_measuring_script(self):
        area, _ = area_with(
            [IN_PROTOCOL], {1: ("limitation", "the library normalizes", "stands")}
        )
        rc, out, err, sent = run_review(area, UPHELD)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(sent[0].count(SCRIPT_PIECE), 1)
        self.assertNotIn(decision_review.SCRIPT_NOT_SHOWN, sent[0])

    def test_the_twin_a_finding_naming_the_script_shows_it_once(self):
        area, _ = area_with(
            [BLOCKER, IN_PROTOCOL],
            {
                1: ("limitation", "in-sample, said so", "stands"),
                2: ("limitation", "noted", "stands"),
            },
        )
        rc, out, err, sent = run_review(
            area,
            "DECISION #1 · upheld · x\nDECISION #2 · upheld · y\n"
            "verdict: 2 upheld, 0 rejected, 0 insufficient\n",
        )
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(sent[0].count(SCRIPT_PIECE), 1)

    def test_a_script_changed_between_the_run_and_the_audit_shows_the_runs_copy(self):
        """The record's stamp holds the changed code, the run recorded the
        old: the review shows the copy the run kept, labelled, never the
        tree's script as the one that ran."""

        def change(area: Path) -> None:
            script = area / "scripts" / "01_measure.py"
            ran = script.read_text(encoding="utf-8")
            (area / "runs" / RUN / "script-source.py").write_text(ran, encoding="utf-8")
            script.write_text(ran + "CHANGED_AFTER_THE_RUN = 1\n", encoding="utf-8")

        area, _ = area_with(
            [IN_PROTOCOL],
            {1: ("limitation", "the library normalizes", "stands")},
            before_audit=change,
        )
        rc, out, err, sent = run_review(area, UPHELD)
        self.assertEqual(rc, 0, out + err)
        self.assertIn(
            f"===== FILE: experiments/01-x/runs/{RUN}/script-source.py (the copy {RUN} "
            f"kept as it ran it — 01_measure.py changed since {RUN} ran it) =====",
            sent[0],
        )
        self.assertNotIn("CHANGED_AFTER_THE_RUN", sent[0])
        self.assertNotIn(SCRIPT_PIECE, sent[0])

    def test_a_changed_script_without_the_runs_copy_is_said_not_shown(self):
        def change(area: Path) -> None:
            script = area / "scripts" / "01_measure.py"
            script.write_text(
                script.read_text(encoding="utf-8") + "CHANGED_AFTER_THE_RUN = 1\n",
                encoding="utf-8",
            )

        area, _ = area_with(
            [IN_PROTOCOL],
            {1: ("limitation", "the library normalizes", "stands")},
            before_audit=change,
        )
        rc, out, err, sent = run_review(area, UPHELD)
        self.assertIn(f"===== {decision_review.SCRIPT_NOT_SHOWN} =====", sent[0])
        self.assertIn(
            f"01_measure.py changed since {RUN} ran it, and {RUN} keeps no copy",
            sent[0],
        )
        self.assertNotIn("CHANGED_AFTER_THE_RUN", sent[0])

    def test_a_script_changed_after_the_audit_refuses_the_review(self):
        """The tree changed after the record: no review rests on it at all."""
        area, _ = area_with(
            [IN_PROTOCOL], {1: ("limitation", "the library normalizes", "stands")}
        )
        script = area / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text(encoding="utf-8") + "LATER = 1\n", encoding="utf-8"
        )
        rc, out, err, sent = run_review(area, UPHELD)
        self.assertNotEqual(rc, 0)
        self.assertEqual(sent, [])
        self.assertIn("the record's auditor read", out + err)

    def test_a_script_that_cannot_be_told_is_said_not_shown(self):
        area, _ = area_with(
            [IN_PROTOCOL], {1: ("limitation", "the library normalizes", "stands")}
        )
        cfg = area / "runs" / RUN / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["command"] = []
        data["script"] = "02_gone.py"
        cfg.write_text(json.dumps(data), encoding="utf-8")
        pieces = decision_review.measuring_script(
            area, area / "runs" / RUN, scope_sha.area_snapshot(area)
        )
        self.assertEqual(len(pieces), 1)
        label, text = pieces[0]
        self.assertEqual(label, decision_review.SCRIPT_NOT_SHOWN)
        self.assertIn("its script 02_gone.py is gone", text)


class FalseAndZeroAreValues(unittest.TestCase):
    """A required check whose value is `false` or `0` stands in the run: it is
    shown as that value, never as missing, and draws no hint."""

    def test_false_and_zero_are_shown_as_values_and_draw_no_hint(self):
        for value, shown_as in ((False, "false"), (0, "0"), (0.0, "0.0")):
            with self.subTest(value=value):
                area, record = area_with(
                    [CHECKED],
                    {1: ("limitation", "the run counts it", "stands")},
                    metrics={"feature_count": value},
                )
                rc, out, err, sent = run_review(area, UPHELD)
                self.assertIn(
                    f"   required check `feature_count` (must be 1) = {shown_as}",
                    sent[0],
                )
                self.assertNotIn("feature_count`: missing", sent[0])
                area, record = area_with(
                    [CHECKED], {}, metrics={"feature_count": value}
                )
                rc, out = decide_cmd(
                    area, record, "limitation", "--why", "the run counts it"
                )
                self.assertEqual(rc, 0, out)
                self.assertNotIn("hint: this limitation rests", out)
