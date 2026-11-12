"""claim_review: the decision on a report review's claim and its
confirmation by a second reviewer, through `labkit-audit` in a small
repository — the six acceptance cases of the contract
(docs/notes/2026-11-10-report-claim-decisions.md), each with its twin.
Both models are faked: whether a reviewer judges a decision right is
measured, not tested. The rules the commands compose are tested from data
in `tests/test_rules_report_claims.py`.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.formats import attempts, evidence, handovers, report_reviews  # noqa: E402
from labkit.gates import audit, claim_review, report_hold, report_review  # noqa: E402
from test_report_review import MARKED, Area  # noqa: E402

#: the first reviewer names the report's line 11 — MARKED's last line, a
#: verdict on the criterion beside a discussed run
CLAIMED = (
    "CLAIM #1 · line 11 · result · criterion-1 PASS is the discussed run's verdict\n"
    "verdict: 1 claim(s)\n"
)
CLEAN = "verdict: 0 claim(s)\n"
UPHELD = (
    "DECISION #1 · upheld · the line names the run as discussed, not reported\n"
    "verdict: 1 upheld, 0 rejected, 0 insufficient\n"
)
REJECTED = (
    "DECISION #1 · rejected · the line states the verdict outside the block\n"
    "verdict: 0 upheld, 1 rejected, 0 insufficient\n"
)
WHY = "line 11 repeats the discussion block's own why"


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


class Lab:
    """`test_report_review.Area` in a git repository, with the report
    MARKED, and `labkit-audit` run on it with the model's answer given."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.a = Area(str(self.root))
        self.area = self.a.area
        self.report = self.a.report(MARKED)
        #: every prompt a model was sent, in order
        self.prompts: list[str] = []
        git(self.root, "init", "-q")
        self.commit("area")

    def commit(self, message: str) -> str:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", message)
        return git(self.root, "rev-parse", "HEAD")

    def audit(self, *args: str, reply: str = "") -> tuple[int, str, str, int]:
        """(exit, stdout, stderr, model calls) of `labkit-audit AREA ARGS`
        with REPLY as the model's answer."""
        calls: list[str] = []

        def fake(alias: str, prompt: str, **kw: object) -> str:
            calls.append(prompt)
            self.prompts.append(prompt)
            return reply

        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", fake),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
            contextlib.suppress(SystemExit),
        ):
            rc = audit.main([str(self.area), "--model", "m", *args])
            return rc, out.getvalue(), err.getvalue(), len(calls)
        return 2, out.getvalue(), err.getvalue(), len(calls)  # argparse refused

    def review(self, reply: str, *extra: str) -> tuple[int, str, str, int]:
        return self.audit("--report-review", str(self.report), *extra, reply=reply)

    def decide(self, status: str, why: str = WHY, n: int = 1, *extra: str):
        return self.audit(
            "--report-review",
            str(self.report),
            "--decide",
            str(n),
            status,
            "--why",
            why,
            *extra,
        )

    def confirm(self, reply: str, *extra: str) -> tuple[int, str, str, int]:
        return self.audit(
            "--review", "--record", self.records()[-1].path.name, *extra, reply=reply
        )

    def records(self) -> list[report_reviews.ReportReview]:
        return report_reviews.area_report_reviews(self.area)

    def gate(self):
        """The hold report-check and the stop place on the report
        (`report_hold.review_gap` on the tree), None when it is released.
        What the commit adds — only records the index holds count — is
        `tests/test_report_hold_stations.py`'s."""
        text = self.report.read_text(encoding="utf-8")
        protocol = self.area / "PROTOCOL-x.md"
        return report_hold.review_gap(
            self.report,
            "REPORT.md",
            text,
            protocol,
            protocol.read_text(encoding="utf-8"),
            report_review.discussed_under(self.report, text, protocol),
            "discusses a run as not reported",
            report_hold.Sources.blank(self.root, staged=False),
        )


class AMisreadingIsAnswered(unittest.TestCase):
    """Acceptance 1 and 6: decided `false-positive`, upheld, released; the
    same decision rejected holds, no further draw releases it, a revised
    reason does once upheld."""

    def setUp(self) -> None:
        self.lab = Lab()
        rc, _, _, _ = self.lab.review(CLAIMED)
        self.assertEqual(rc, 1)

    def test_decided_false_positive_and_upheld_the_report_is_released(self):
        lab = self.lab
        held = lab.gate()
        assert held is not None
        self.assertIn("— open", held.text)
        self.assertIn("--decide 1 false-positive --why", held.fix or "")
        rc, out, _, calls = lab.decide("false-positive")
        self.assertEqual((rc, calls), (0, 0))
        self.assertIn("claim 1: false-positive", out)
        self.assertIn("the decision alone releases nothing", out)
        # decided, not confirmed: held, and the hold names the confirmation
        held = lab.gate()
        assert held is not None
        self.assertIn("not yet judged by a second reviewer", held.text)
        self.assertIn(f"--review --record {lab.records()[0].path.name}", held.fix or "")
        rc, out, _, calls = lab.confirm(UPHELD)
        self.assertEqual((rc, calls), (0, 1))
        self.assertIn("claim review state: every decision reviewed is released", out)
        self.assertIn("report review state: this state is released", out)
        self.assertIsNone(lab.gate())
        # nothing more to do, and no call is made to say so
        self.assertEqual(lab.confirm(UPHELD)[::3], (0, 0))
        self.assertEqual(lab.review(CLEAN)[::3], (0, 0))

    def test_the_twin_the_same_decision_rejected_holds(self):
        lab = self.lab
        lab.decide("false-positive")
        rc, out, _, _ = lab.confirm(REJECTED)
        self.assertEqual(rc, 1)
        self.assertIn("held — the decision on claim(s) 1 is not released", out)
        held = lab.gate()
        assert held is not None
        self.assertIn("rejected by the second reviewer", held.text)
        self.assertIn("decided again with a revised reason", held.fix or "")

    def test_the_second_reviewer_reads_the_claim_the_reason_and_the_report(self):
        lab = self.lab
        lab.decide("false-positive")
        lab.confirm(UPHELD)
        prompt = lab.prompts[-1]
        self.assertIn("Claim review", prompt)
        self.assertIn("#1 · line 11 · result · criterion-1 PASS is the", prompt)
        self.assertIn("   the line: criterion-1 PASS, AUROC 0.7795", prompt)
        self.assertIn(f"   reason: {WHY}", prompt)
        self.assertIn("11: criterion-1 PASS, AUROC 0.7795", prompt)  # the report
        self.assertIn("===== AUDITS =====", prompt)
        self.assertIn("LAB-104", prompt)

    def test_a_rejected_decision_is_not_released_by_another_draw(self):
        lab = self.lab
        lab.decide("false-positive")
        lab.confirm(REJECTED)
        rc, _, err, calls = lab.confirm(UPHELD)
        self.assertEqual((rc, calls), (2, 0))
        self.assertIn("reviewed as it stands and not upheld", err)
        self.assertIn("another draw settles nothing", err)
        # asked for, a draw counts and releases nothing
        rc, out, _, calls = lab.confirm(UPHELD, "--again")
        self.assertEqual((rc, calls), (1, 1))
        self.assertIsNotNone(lab.gate())

    def test_a_rejected_decision_does_not_keep_another_claim_from_its_review(self):
        """Two claims of one record: the rejection of the first leaves the
        second, decided and never judged, its one draw — and only it."""
        lab = Lab()
        lab.review(
            "CLAIM #1 · line 11 · result · the verdict of a discussed run\n"
            "CLAIM #2 · line 1 · contradiction · the title says reported\n"
            "verdict: 2 claim(s)\n"
        )
        lab.decide("false-positive")
        lab.confirm(REJECTED)
        lab.decide("false-positive", "the title names no result", 2)
        rc, out, _, calls = lab.confirm(
            "DECISION #2 · upheld · the title states no finding\n"
            "verdict: 1 upheld, 0 rejected, 0 insufficient\n"
        )
        self.assertEqual((rc, calls), (0, 1))
        self.assertNotIn("#1 · line 11", lab.prompts[-1].split("===== REPORT")[0])
        held = lab.gate()
        assert held is not None
        self.assertIn("CLAIM #1", held.text)
        self.assertNotIn("CLAIM #2", held.text)

    def test_a_revised_reason_is_released_once_upheld_and_the_rejection_stays(self):
        lab = self.lab
        lab.decide("false-positive")
        lab.confirm(REJECTED)
        rc, _, _, _ = lab.decide(
            "false-positive", "lines 3–9 are the generated discussion block"
        )
        self.assertEqual(rc, 0)
        held = lab.gate()
        assert held is not None
        self.assertIn("not yet judged by a second reviewer", held.text)
        self.assertIn("an earlier decision on it was rejected", held.text)
        rc, _, _, calls = lab.confirm(UPHELD)
        self.assertEqual((rc, calls), (0, 1))
        self.assertIsNone(lab.gate())
        first, second = report_reviews.area_claim_reviews(lab.area)
        self.assertEqual(
            [v.verdict for v in (*first.verdicts, *second.verdicts)],
            ["rejected", "upheld"],
        )
        self.assertNotEqual(
            first.verdicts[0].decision_sha, second.verdicts[0].decision_sha
        )

    def test_a_claim_review_is_journaled_and_no_handover_binds_its_lines(self):
        lab = self.lab
        lab.decide("false-positive")
        lab.confirm(UPHELD)
        last = attempts.read_journal(lab.area)[-1]
        self.assertEqual(last.mode, report_reviews.CLAIM_ATTEMPT_MODE)
        self.assertEqual(
            (last.outcome, last.file.split("/")[0]), ("record", "report-reviews")
        )
        self.assertTrue(handovers.review_trace(last.file))
        self.assertTrue(handovers.review_trace(last.answer))
        self.assertEqual(attempts.area_gaps(lab.area).blockers, [])


class ARealClaimStaysHeld(unittest.TestCase):
    """Acceptance 2: `limitation` and `fixed` are refused with their
    sentence, the record untouched; nothing but an upheld `false-positive`
    releases."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.lab.review(CLAIMED)
        self.path = self.lab.records()[0].path
        self.before = self.path.read_bytes()

    def test_a_limitation_and_a_fixed_are_refused_and_nothing_is_written(self):
        for status, said in (
            ("limitation", "a `result` claim is no limitation"),
            ("fixed", "a claim is not decided `fixed`"),
            ("settled", "one of open, false-positive"),
        ):
            rc, _, err, _ = self.lab.decide(status)
            self.assertEqual(rc, 2, status)
            self.assertIn(said, err)
        rc, _, err, _ = self.lab.decide("false-positive", " ")
        self.assertEqual(rc, 2)
        self.assertIn("owes a reason", err)
        rc, _, err, _ = self.lab.decide("false-positive", WHY, 2)
        self.assertEqual(rc, 2)
        self.assertIn("no claim 2", err)
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertIsNotNone(self.lab.gate())

    def test_the_twin_a_false_positive_is_stored_and_keeps_every_other_byte(self):
        rc, _, _, _ = self.lab.decide("false-positive")
        self.assertEqual(rc, 0)
        after = self.path.read_text(encoding="utf-8")
        self.assertEqual(
            report_reviews.without_claim_decisions(after),
            report_reviews.without_claim_decisions(self.before.decode("utf-8")),
        )
        (claim,) = self.lab.records()[0].claims
        self.assertEqual((claim.status, claim.reason), ("false-positive", WHY))

    def test_nothing_decided_leaves_nothing_to_confirm(self):
        rc, _, err, calls = self.lab.confirm(UPHELD)
        self.assertEqual((rc, calls), (2, 0))
        self.assertIn("no claim decided `false-positive` — nothing to review", err)

    def test_a_usage_that_mixes_a_claim_and_a_finding_is_refused(self):
        rc, _, err, _ = self.lab.decide("false-positive", WHY, 1, "--again")
        self.assertEqual(rc, 2)
        self.assertIn("a claim's decision takes --why and --record", err)

    def test_an_audit_record_named_to_review_is_not_taken_for_a_report_review(self):
        (record,) = (self.lab.area / "audits").glob("*-analysis.toml")
        self.assertIsNone(claim_review.report_review_named(self.lab.area, record))
        self.assertEqual(
            claim_review.report_review_named(self.lab.area, Path(self.path.name)),
            self.path,
        )


class AChangedStateOwesANewReview(unittest.TestCase):
    """Acceptance 3: a decision is bound to the state its record saw."""

    def test_a_changed_report_line_makes_the_decision_stale(self):
        lab = Lab()
        lab.review(CLAIMED)
        lab.decide("false-positive")
        lab.confirm(UPHELD)
        self.assertIsNone(lab.gate())
        lab.report.write_text(MARKED + "\nA sentence added.\n", encoding="utf-8")
        held = lab.gate()
        assert held is not None
        self.assertIn("has no clean report review of this state", held.text)
        # neither a decision nor a confirmation on the old record answers it
        rc, _, err, _ = lab.decide("false-positive")
        self.assertEqual(rc, 2)
        self.assertIn("no review of this state names a claim", err)
        old = lab.records()[0].path.name
        rc, _, err, _ = lab.decide("false-positive", WHY, 1, "--record", old)
        self.assertEqual(rc, 2)
        self.assertIn("read another state of REPORT.md", err)
        rc, _, err, calls = lab.confirm(UPHELD)
        self.assertEqual((rc, calls), (2, 0))
        self.assertIn("read another state of REPORT.md", err)
        # the next reader is cold: the decision is not carried, its claim holds
        rc, _, _, _ = lab.review(CLAIMED)
        self.assertEqual(rc, 1)
        self.assertEqual(lab.records()[-1].claims[0].status, "open")
        self.assertIn("— open", (lab.gate() or held).text)


class AnotherDraw(unittest.TestCase):
    """Acceptance 4: an `--again` draw releases no open claim, and a claim
    it adds holds until decided and upheld."""

    def test_an_again_draw_releases_no_open_claim(self):
        lab = Lab()
        lab.review(CLAIMED)
        rc, _, _, calls = lab.review(CLEAN, "--again")
        self.assertEqual((rc, calls), (1, 1))
        self.assertIn("— open", (lab.gate() or self.fail("released")).text)

    def test_a_claim_an_again_draw_adds_holds_until_decided_and_upheld(self):
        lab = Lab()
        self.assertEqual(lab.review(CLEAN)[0], 0)
        self.assertIsNone(lab.gate())
        rc, _, _, _ = lab.review(CLAIMED, "--again")
        self.assertEqual(rc, 1)
        self.assertIsNotNone(lab.gate())
        added = lab.records()[-1].path.name
        self.assertEqual(lab.decide("false-positive", WHY, 1, "--record", added)[0], 0)
        self.assertIsNotNone(lab.gate())
        self.assertEqual(lab.confirm(UPHELD)[0], 0)
        self.assertIsNone(lab.gate())


class ARecordWithoutDecisions(unittest.TestCase):
    """Acceptance 5: a review written before a claim could be decided is
    refused naming the release that reads it and the move that keeps it;
    moved, the new review runs and nothing holds the record as lost."""

    def setUp(self) -> None:
        self.lab = Lab()
        # written in an earlier minute, as a record of an earlier release
        # is: the review that replaces it takes a name of its own
        earlier = time.strptime("2026-11-01 10:00", "%Y-%m-%d %H:%M")
        with mock.patch.object(
            report_reviews.time, "localtime", lambda now=None: earlier
        ):
            self.lab.review(CLAIMED)
        self.old = self.lab.records()[0].path
        self.aside = self.old.parent / report_reviews.SUPERSEDED / self.old.name

    def age(self) -> None:
        """Rewrite the record as labkit 0.112.0 wrote it — no decision
        lines — and commit it."""
        text = self.old.read_text(encoding="utf-8")
        self.old.write_text(
            text.replace('status = "open"\nreason = ""\n', ""), encoding="utf-8"
        )
        self.first = self.lab.commit("a review of labkit 0.112.0")

    def move(self) -> None:
        self.aside.parent.mkdir()
        git(self.lab.root, "mv", str(self.old), str(self.aside))

    def test_it_is_refused_naming_the_release_and_the_move(self):
        self.age()
        rc, _, err, calls = self.lab.review(CLEAN)
        self.assertEqual((rc, calls), (2, 0))
        self.assertIn("claim 1 carries no `status`", err)
        self.assertIn("0.112.0 is the last release that reads it", err)
        self.assertIn(f"git mv {self.old} {self.aside}", err)
        held = self.lab.gate()
        assert held is not None
        self.assertIn("its report review cannot be told", held.text)

    def test_moved_the_new_review_runs_and_no_gate_holds_the_record_as_lost(self):
        lab = self.lab
        self.age()
        self.move()
        self.assertEqual(attempts.area_gaps(lab.area).blockers, [])
        self.assertEqual(attempts.area_gaps(lab.area, staged=True).blockers, [])
        self.assertEqual(evidence.change_findings(lab.area), [])
        self.assertEqual(evidence.change_findings(lab.area, staged=True), [])
        rc, _, err, calls = lab.review(CLEAN)
        self.assertEqual((rc, calls, err.count("refused")), (0, 1, 0))
        self.assertIsNone(lab.gate())
        lab.commit("the old review moved aside, the report reviewed again")
        self.assertEqual(attempts.area_gaps(lab.area).blockers, [])
        self.assertEqual(evidence.commit_changes(lab.area, self.first), [])
        self.assertTrue(self.aside.is_file())

    def test_the_twin_a_record_that_reads_moved_aside_is_named_as_gone(self):
        lab = self.lab
        first = lab.commit("a review this labkit reads")
        self.move()
        (gone,) = attempts.area_gaps(lab.area).blockers[:1]
        self.assertIn(f"report-reviews/{self.old.name}", gone)
        self.assertIn("gone from the tree", gone)
        self.assertNotEqual(attempts.area_gaps(lab.area, staged=True).blockers, [])
        lab.commit("moved past the hook")
        (told,) = evidence.commit_changes(lab.area, first)
        self.assertIn(f"report-reviews/{self.old.name}: deleted by commit", told)


class ADecisionIsNoEvidenceChange(unittest.TestCase):
    def test_deciding_a_committed_review_breaks_nothing_and_a_rewrite_does(self):
        lab = Lab()
        lab.review(CLAIMED)
        lab.commit("reviewed")
        path = lab.records()[0].path
        lab.decide("false-positive")
        self.assertEqual(evidence.change_findings(lab.area), [])
        path.write_text(
            path.read_text(encoding="utf-8").replace("line = 11", "line = 4"),
            encoding="utf-8",
        )
        ((why, fix),) = evidence.change_findings(lab.area)
        self.assertIn("changed beyond its claims' decision lines", why)
        self.assertIn("--decide N false-positive", fix)


if __name__ == "__main__":
    unittest.main()
