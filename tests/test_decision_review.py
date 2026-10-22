"""`labkit-audit --review`: a second auditor on the `stands` decisions of one
analysis record (`gates/decision_review`), the review file it writes
(`formats/reviews`), and the warning report-check gives a `stands` no
review upholds. The model call is faked; what is tested is what the
reviewer gets to read, what is recorded from its answer, and what releases.

Why (labkit-paper area 09, fifth haiku round, 2026-10-22): 15 of 28 audit
findings accepted with no action, six of them with the reason "Finding
noted"; nothing asked whether the reported claim stood within the limit.
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

from protocol_fixture import completed_run, head, scope_file

from labkit.checks import audit_binding
from labkit.formats import findings, promises, reviews, scope_sha
from labkit.gates import audit, decision_review, report_check
from labkit.tools import protocol_fill

RUN = "2026-10-07T10-00-00_ab12"
BLOCKER = (
    "BLOCKER",
    "BLOCKER · experiments/01-x/scripts/01_measure.py:1 · the threshold is fit "
    "in-sample · c1_pass reads True for any rows · LAB-050 Analysis audit before "
    "reporting · fit it out of sample",
)
WARNING = (
    "WARNING",
    "WARNING · experiments/01-x/scripts/01_measure.py:1 · one seed · the spread is "
    "unknown · LAB-015 Preflight audit before freezing · report the spread",
)
UPHELD = "DECISION #1 · upheld · the Conclusion claims an in-sample fit and no more\nverdict: 1 upheld, 0 rejected, 0 insufficient\n"
REJECTED = (
    "DECISION #1 · rejected · the reason restates the finding; c1_pass as reported "
    "rests on the in-sample fit\nverdict: 0 upheld, 1 rejected, 0 insufficient\n"
)


def area_with(
    rows: list[tuple[str, str]], decide: dict[int, tuple[str, str, str]]
) -> tuple[Path, Path]:
    """(area, record) — a seconds area whose one run is audited with ROWS,
    each finding N decided as DECIDE[N] = (status, reason, effect)."""
    root = Path(tempfile.mkdtemp())
    (root / ".git").mkdir()  # the layout root, so paths show repo-relative
    area = root / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "scripts" / "02_analyze.py").write_text("print('ok')\n", encoding="utf-8")
    scope_file(area)
    proto = area / "PROTOCOL-x.md"
    proto.write_text(
        head(cost="seconds", result=RUN)
        + "- **Question / hypothesis:** does it hold?\n"
        + "- **Conclusion:** the fit is in-sample; nothing more is claimed.\n"
        + f"- **Recorded results:** c1_pass = True (run {RUN})\n",
        encoding="utf-8",
    )
    run = completed_run(area, RUN, metrics={"c1_pass": True})
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
        shown_sha=audit_binding.run_shown(area, run, "").sha,
    )
    for n, (status, reason, effect) in decide.items():
        findings.write_decision(record, n, status, reason, effect)
    # the result section as --from-run writes it: Recorded results with its
    # note, one Limit line per decided limit
    rendered, _ = protocol_fill.render_result(proto.read_text(encoding="utf-8"), area)
    proto.write_text(rendered, encoding="utf-8")
    return area, record


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
                1: ("accepted", "an in-sample fit, said so", "stands"),
                2: ("accepted", "the run cannot judge it", "C1 not assessable"),
                3: ("accepted", "one seed", "stands"),
                4: ("accepted", "noted", ""),
            },
        )
        rec = findings.read(record)
        self.assertEqual([n for n, _ in decision_review.reviewable(rec)], [1, 3])

    def test_named_files_resolve_against_the_repo_then_the_area(self):
        area, record = area_with([BLOCKER], {1: ("accepted", "r", "stands")})
        rec = findings.read(record)
        files = decision_review.named_files(
            decision_review.reviewable(rec), area.parent.parent, area
        )
        self.assertEqual(files, [(area / "scripts" / "01_measure.py").resolve()])


class TheCall(unittest.TestCase):
    def test_the_reviewer_reads_decisions_protocol_named_files_rows_and_rules(self):
        area, record = area_with(
            [BLOCKER],
            {1: ("accepted", "the fit is in-sample, the Conclusion says so", "stands")},
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
            [BLOCKER], {1: ("accepted", "in-sample, said so", "stands")}
        )
        code, out = gate(area)
        self.assertEqual(code, 1, out)  # a BLOCKER's stands blocks until upheld
        self.assertIn("BLOCKER: Limit (audit", out)
        self.assertIn(
            "`stands` on an accepted BLOCKER not reviewed — no decision review upholds",
            out,
        )
        self.assertIn(f"--review --record {record.name}", out)
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
        area, _ = area_with([BLOCKER], {1: ("accepted", "Finding noted", "stands")})
        rc, out, _, _ = run_review(area, REJECTED)
        self.assertEqual(rc, 1, out)
        self.assertIn("rejected: decide the finding again first", out)
        self.assertIn("auditing again does not settle a rejection", out)
        code, out = gate(area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "`stands` on an accepted BLOCKER rejected: the reason restates", out
        )

    def test_the_twin_a_warnings_stands_without_a_review_only_warns(self):
        """The scope, narrow at first: the release does not hang on every
        lesser limit — an accepted WARNING's `stands` no review upholds is a
        warning, a BLOCKER's a blocker."""
        area, _ = area_with([WARNING], {1: ("accepted", "one seed, said so", "stands")})
        code, out = gate(area)
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING: Limit (audit", out)
        self.assertIn("`stands` on an accepted WARNING not reviewed", out)
        self.assertNotIn("BLOCKER:", out)

    def test_the_reviewer_sees_the_result_as_it_renders(self):
        area, record = area_with([BLOCKER], {1: ("accepted", "in-sample", "stands")})
        _, _, _, sent = run_review(area, UPHELD)
        self.assertIn(f"===== {decision_review.RESULT_LABEL} =====", sent[0])
        self.assertIn(
            f"- **Limit (audit {record.stem} #1):** the verdicts stand", sent[0]
        )
        self.assertIn(f"- **Recorded results:** c1_pass = True (run {RUN})", sent[0])

    def test_a_changed_decision_makes_the_review_stale(self):
        area, record = area_with([BLOCKER], {1: ("accepted", "in-sample", "stands")})
        run_review(area, UPHELD)
        findings.write_decision(record, 1, "accepted", "in-sample, and more", "stands")
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
        area, record = area_with([BLOCKER], {1: ("accepted", "in-sample", "stands")})
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
        self.assertIn("`stands` on an accepted BLOCKER not reviewed", out)
        # the claim's digest reads the Conclusion and nothing generated: the
        # lines --from-run writes after the decision must not stale a review
        self.assertEqual([k for k, _ in reviews.reported_claim(text)], ["Conclusion"])
        self.assertEqual(
            reviews.claim_digest(text),
            reviews.claim_digest(text.replace("c1_pass = True", "c1_pass = False")),
        )

    def test_a_review_nobody_can_read_is_named_by_the_gate(self):
        area, _ = area_with([BLOCKER], {1: ("accepted", "in-sample", "stands")})
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

    def test_a_rejected_decision_is_not_released_by_a_later_draw(self):
        """Review 2026-10-22: the newest matching review won, so an unchanged
        rejected could be re-reviewed until an upheld came. Now every draw
        on one state counts, the command refuses another draw, and deciding
        again is the way out."""
        area, record = area_with(
            [BLOCKER], {1: ("accepted", "Finding noted", "stands")}
        )
        rc, _, _, _ = run_review(area, REJECTED)
        self.assertEqual(rc, 1)
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("another draw settles nothing", err)
        self.assertIn("decide again", err)
        rc, _, _, sent = run_review(area, UPHELD, "--again")
        self.assertEqual((rc, len(sent)), (0, 1))  # the draw itself says upheld…
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
            "accepted",
            "the Conclusion claims the in-sample fit only",
            "stands",
        )
        rc, _, _, sent = run_review(area, UPHELD)
        self.assertEqual((rc, len(sent)), (0, 1))
        rec = findings.read(record)
        self.assertTrue(reviews.upholding(rec, 1, reviews.area_reviews(area), text))

    def test_a_report_that_disagrees_with_itself_records_nothing(self):
        area, _ = area_with([BLOCKER], {1: ("accepted", "in-sample", "stands")})
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
        area, _ = area_with([BLOCKER], {1: ("accepted", "in-sample", "stands")})
        (area / "scripts" / "01_measure.py").write_text("x = 1\n", encoding="utf-8")
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual(rc, 2)
        self.assertEqual(sent, [])  # no call on a state the auditor did not read
        self.assertIn("the record's auditor read", err)

    def test_record_by_bare_name_and_a_conclusion_still_owed(self):
        """Round on 86e38bc (judge-2): `--record 2026-…-analysis.toml` as the
        gate names it was refused with "No such file"; and a review made
        while the Conclusion was a placeholder went stale when it was
        written — a second opus call. The name resolves under audits/,
        and the review asks for the Conclusion first."""
        area, record = area_with([BLOCKER], {1: ("accepted", "in-sample", "stands")})
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
                    "accepted",
                    "in-sample, said so",
                    "--effect",
                    "stands",
                    "--record",
                    record.name,
                ]
            )
        self.assertEqual(rc, 0, out.getvalue())

    def test_nothing_to_review_is_a_refusal(self):
        area, _ = area_with([BLOCKER], {1: ("fixed", "fixed it", "")})
        rc, _, err, sent = run_review(area, UPHELD)
        self.assertEqual((rc, sent), (2, []))
        self.assertIn("no accepted finding with effect `stands`", err)


class TheFile(unittest.TestCase):
    def test_counts_and_verdicts_are_held_on_read(self):
        area = Path(tempfile.mkdtemp())
        d = reviews.Decision(1, "a" * 12, "upheld", "fine")
        path = reviews.write_review(
            area, "opus", "r.toml", "s" * 12, "h" * 12, "c" * 12, [d]
        )
        self.assertEqual(reviews.read_review(path).counts, (1, 0, 0))
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
            reviews.write_review(area, "opus", "r.toml", "s", "h", "c", [d, d])
        self.assertEqual(
            findings.written_order(path),
            ("".join(path.name.split("-review")[:1]), 1, path.name),
        )
        # a second review of the minute: numbered before the suffix, read as
        # a review and never as a findings record
        path.write_text(text, encoding="utf-8")
        second = reviews.write_review(area, "opus", "r.toml", "s", "h", "c", [d])
        self.assertTrue(second.name.endswith("-review-2.toml"), second.name)
        self.assertEqual([r.path for r in reviews.area_reviews(area)], [path, second])
        self.assertEqual(findings.area_records(area), [])


if __name__ == "__main__":
    unittest.main()
