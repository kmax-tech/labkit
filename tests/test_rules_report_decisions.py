"""Rule tests of `report_decisions`' pure checks: when a decision behind a
reported number owes a second auditor, each condition from records and
reviews in memory, its violation and its valid twin (docs/architecture.md,
"Checks and their tests"). The stations that compose them are tested in
`tests/test_report_decisions_stations.py`.
"""

from __future__ import annotations

import dataclasses
import unittest

import pytest

from check_guards import pure_call
from labkit.formats import findings, followup, reviews
from labkit.formats.commands import DECIDE, Command
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    KNOWN_RULE,
    TECHNICAL_RULE,
    VIOLATED,
    WARNING,
    GateFinding,
    RuleAssignment,
)
from labkit.formats.standard_contract import ANALYSIS_AUDIT
from labkit.gates.report_decisions import (
    check_carried_closings_upheld,
    check_contested_closings_upheld,
    check_decision_reviews_read,
    check_earlier_blockers_released,
    check_first_dismissals_upheld,
    check_limit_effects_decided,
    check_repaired_claims_upheld,
    check_stands_upheld,
)
from protocol_fixture import head
from state_fixture import AREA, area_evidence, audit_record

pytestmark = pytest.mark.rule

LAB_015 = RuleAssignment(KNOWN_RULE, "LAB-015", "Preflight audit before freezing")
TEXT = (
    head(repeat_cost="low")
    + "\n- **Conclusion:** the fit is in-sample; nothing more is claimed.\n"
)
RECORD = "2026-11-10T10-00-analysis.toml"
EARLIER = "2026-11-09T10-00-analysis.toml"
#: the way to the decision review, as a station would hand it in
STEP = "`labkit-audit area --review --record R`"
IN_CODE = "scripts/01_measure.py:3"
ON_CONCLUSION = "PROTOCOL-x.md:Conclusion"


def finding(
    grade: str,
    status: str,
    *,
    effect: str = "",
    carries: str = "",
    place: str = IN_CODE,
    check: str = "",
) -> findings.Finding:
    """An audit finding of GRADE at PLACE as the auditor writes its line,
    decided STATUS with EFFECT; CARRIES the earlier finding it continues,
    CHECK the metrics key its repair must show."""
    return findings.Finding(
        grade,
        f"{grade} · {place} · statement · the target leaks",
        status,
        "" if status == "open" else "the column is a constant",
        effect=effect,
        carries=carries,
        check=check,
    )


def record(*found: findings.Finding, name: str = RECORD) -> findings.Record:
    """The analysis record NAME of run r1 holding FOUND."""
    return audit_record(name, mode=ANALYSIS_AUDIT, run_id="r1", found=found)


def review(
    rec: findings.Record,
    verdict: str,
    *,
    of: findings.Finding | None = None,
    again: bool = False,
) -> reviews.Review:
    """A decision review of REC under the claim TEXT makes, saying VERDICT on
    its finding 1 — as decided now, or as OF when the review judged an
    earlier decision of it; AGAIN marks an `--again` draw."""
    decision = reviews.Decision(
        1,
        findings.decision_digest(of or rec.findings[0]),
        verdict,
        "the reviewer's why",
    )
    return reviews.Review(
        path=AREA / "audits" / "reviews" / "r.toml",
        date="2026-11-11",
        model="test-model",
        record=rec.path.name,
        scope_sha=rec.scope_sha,
        shown_sha=rec.shown_sha or "",
        claim_sha=reviews.claim_digest(TEXT),
        again=again,
        counts=reviews.counts_of([decision]),
        decisions=(decision,),
    )


class ALimitHasItsEffect(unittest.TestCase):
    """LAB-015 Preflight audit before freezing: a BLOCKER decided
    `limitation` carries its effect on the verdicts
    (`check_limit_effects_decided`)."""

    @staticmethod
    def _decide_again(n: int) -> Command:
        return Command(DECIDE, f"labkit-audit area --decide {n} limitation")

    def test_a_blocker_limitation_without_an_effect_blocks(self):
        rec = record(finding(BLOCKER, "limitation"))
        (f,) = pure_call(
            check_limit_effects_decided, rec, decide_again=self._decide_again
        )
        self.assertEqual(
            (f.grade, f.evidence_kind, f.outcome), (BLOCKER, GUARANTEED, VIOLATED)
        )
        self.assertEqual(f.rule, LAB_015)
        self.assertEqual(
            f.text,
            f"Limitation (audit {rec.path.stem} #1): a BLOCKER decided limitation "
            f"owes its effect on the verdicts",
        )
        self.assertEqual(
            f.fix, "decide it again: `labkit-audit area --decide 1 limitation`"
        )

    def test_the_twin_an_effect_decided_and_a_warning_without_one_pass(self):
        rec = record(
            finding(BLOCKER, "limitation", effect=findings.EFFECT_STANDS),
            finding(WARNING, "limitation"),
        )
        self.assertEqual(
            pure_call(
                check_limit_effects_decided, rec, decide_again=self._decide_again
            ),
            [],
        )


class TheDecisionReviewsRead(unittest.TestCase):
    """A review file nobody can read is named, not passed over
    (`check_decision_reviews_read`)."""

    def test_an_unread_review_warns_with_its_sentence(self):
        evidence = dataclasses.replace(
            area_evidence(), reviews_unread="audits/reviews/x.toml: not TOML"
        )
        (f,) = pure_call(check_decision_reviews_read, evidence)
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (WARNING, GUARANTEED, TECHNICAL_RULE)
        )
        self.assertEqual(
            f.text, "a review nobody can read: audits/reviews/x.toml: not TOML"
        )

    def test_the_twin_reviews_that_read(self):
        self.assertEqual(pure_call(check_decision_reviews_read, area_evidence()), [])


def _held(check, rec: findings.Record, *found: reviews.Review) -> list[GateFinding]:
    """CHECK on REC with the reviews FOUND, under TEXT's claim."""
    return pure_call(check, rec, list(found), text=TEXT, review_way=lambda: STEP)


class AStandsIsUpheld(unittest.TestCase):
    """LAB-015 Preflight audit before freezing: a limitation whose effect is
    `stands` owes a second auditor, at the finding's grade
    (`check_stands_upheld`)."""

    def test_a_blocker_limitation_that_stands_unreviewed_blocks(self):
        rec = record(finding(BLOCKER, "limitation", effect=findings.EFFECT_STANDS))
        (f,) = _held(check_stands_upheld, rec)
        self.assertEqual(
            (f.grade, f.evidence_kind, f.outcome), (BLOCKER, GUARANTEED, VIOLATED)
        )
        self.assertEqual(f.rule, LAB_015)
        self.assertEqual(
            f.text,
            f"Limitation (audit {rec.path.stem} #1): `stands` on a BLOCKER decided "
            f"limitation not reviewed — no decision review upholds that the "
            f"reported claim stands within this limit (LAB-015 Preflight audit "
            f"before freezing)",
        )
        self.assertEqual(
            f.fix,
            f"{STEP} asks a second auditor (owed at every repeat cost); after a "
            f"rejection, decide again",
        )

    def test_a_warning_limitation_that_stands_unreviewed_warns(self):
        rec = record(finding(WARNING, "limitation", effect=findings.EFFECT_STANDS))
        (f,) = _held(check_stands_upheld, rec)
        self.assertEqual((f.grade, f.rule), (WARNING, LAB_015))

    def test_a_rejection_and_an_again_draw_release_nothing(self):
        rec = record(finding(BLOCKER, "limitation", effect=findings.EFFECT_STANDS))
        (f,) = _held(check_stands_upheld, rec, review(rec, "rejected"))
        self.assertIn("limitation rejected: the reviewer's why —", f.text)
        # a later `upheld` does not outvote the rejection
        (f,) = _held(
            check_stands_upheld,
            rec,
            review(rec, "rejected"),
            review(rec, reviews.UPHELD),
        )
        self.assertEqual(f.grade, BLOCKER)
        (f,) = _held(check_stands_upheld, rec, review(rec, reviews.UPHELD, again=True))
        self.assertIn("only `--again` draws said upheld", f.text)

    def test_the_twin_an_upheld_stands_and_a_limit_not_assessable_pass(self):
        rec = record(finding(BLOCKER, "limitation", effect=findings.EFFECT_STANDS))
        self.assertEqual(
            _held(check_stands_upheld, rec, review(rec, reviews.UPHELD)), []
        )
        narrowed = record(
            finding(BLOCKER, "limitation", effect="criterion-1 not assessable")
        )
        self.assertEqual(_held(check_stands_upheld, narrowed), [])


class AContestedClosingIsUpheld(unittest.TestCase):
    """LAB-015 Preflight audit before freezing: a decision a second auditor
    once did not uphold owes a review of what it was changed to
    (`check_contested_closings_upheld`)."""

    #: the decision the reviewer rejected, before it was closed
    BEFORE = finding(BLOCKER, "limitation", effect=findings.EFFECT_STANDS)

    def test_closing_a_rejected_decision_holds_at_the_findings_grade(self):
        for grade, status in ((BLOCKER, "false-positive"), (WARNING, "fixed")):
            with self.subTest(grade=grade, status=status):
                rec = record(finding(grade, status))
                (f,) = _held(
                    check_contested_closings_upheld,
                    rec,
                    review(rec, "rejected", of=self.BEFORE),
                )
                self.assertEqual(
                    (f.grade, f.evidence_kind, f.rule), (grade, GUARANTEED, LAB_015)
                )
                self.assertTrue(
                    f.text.startswith(
                        f"audit {rec.path.stem} #1: `{status}` on a {grade} a review "
                        f"said rejected on (the reviewer's why) — closing a finding a "
                        f"reviewer did not uphold settles nothing by itself"
                    ),
                    f.text,
                )
        assert f.fix is not None
        self.assertEqual(
            f.fix,
            f"{STEP} asks a second auditor whether the reason shows it gone in the "
            f"files as audited",
        )

    def test_the_twin_the_new_decision_upheld_and_one_never_contested_pass(self):
        rec = record(finding(BLOCKER, "false-positive"))
        self.assertEqual(
            _held(
                check_contested_closings_upheld,
                rec,
                review(rec, "rejected", of=self.BEFORE),
                review(rec, reviews.UPHELD),
            ),
            [],
        )
        # never contested: the first dismissal's rule, not this one's
        self.assertEqual(_held(check_contested_closings_upheld, rec), [])


class ARepairedClaimIsUpheld(unittest.TestCase):
    """LAB-015 Preflight audit before freezing: a BLOCKER on the Conclusion
    decided `fixed` owes a second auditor, since no follow-up audit is shown
    a repaired claim (`check_repaired_claims_upheld`)."""

    def test_a_fixed_conclusion_blocker_unreviewed_blocks(self):
        rec = record(finding(BLOCKER, "fixed", place=ON_CONCLUSION))
        (f,) = _held(check_repaired_claims_upheld, rec)
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (BLOCKER, GUARANTEED, LAB_015)
        )
        self.assertEqual(
            f.text,
            f"audit {rec.path.stem} #1: `fixed` on a BLOCKER on the Conclusion not "
            f"reviewed — no follow-up audit is shown a repaired claim; a second "
            f"auditor judges the Conclusion as it stands (LAB-015 Preflight audit "
            f"before freezing)",
        )
        self.assertEqual(
            f.fix,
            f"{STEP} asks a second auditor whether the Conclusion as it stands no "
            f"longer makes the claim the finding names; no new measurement and no "
            f"analysis audit",
        )

    def test_the_twin_upheld_fixed_in_code_and_once_contested_pass(self):
        rec = record(finding(BLOCKER, "fixed", place=ON_CONCLUSION))
        self.assertEqual(
            _held(check_repaired_claims_upheld, rec, review(rec, reviews.UPHELD)), []
        )
        # a repair in code is the follow-up audit's to see
        self.assertEqual(
            _held(check_repaired_claims_upheld, record(finding(BLOCKER, "fixed"))), []
        )
        # once not upheld: the contested closing's rule holds it, once
        before = finding(BLOCKER, "false-positive", place=ON_CONCLUSION)
        contested = review(rec, "insufficient", of=before)
        self.assertEqual(_held(check_repaired_claims_upheld, rec, contested), [])
        self.assertEqual(len(_held(check_contested_closings_upheld, rec, contested)), 1)


class AFirstDismissalIsUpheld(unittest.TestCase):
    """LAB-015 Preflight audit before freezing: a BLOCKER decided
    `false-positive` is not released by the deciding agent's own decision
    (`check_first_dismissals_upheld`)."""

    def test_a_dismissed_blocker_unreviewed_blocks(self):
        rec = record(finding(BLOCKER, "false-positive"))
        (f,) = _held(check_first_dismissals_upheld, rec)
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (BLOCKER, GUARANTEED, LAB_015)
        )
        self.assertEqual(
            f.text,
            f"audit {rec.path.stem} #1: `false-positive` on a BLOCKER not reviewed "
            f"— a blocking finding is not released by the deciding agent's own "
            f"decision (LAB-015 Preflight audit before freezing)",
        )
        self.assertEqual(
            f.fix,
            f"{STEP} asks a second auditor whether the reason shows it does not "
            f"apply to the code and run as audited",
        )

    def test_the_twin_upheld_a_warning_and_a_carried_one_pass(self):
        rec = record(finding(BLOCKER, "false-positive"))
        self.assertEqual(
            _held(check_first_dismissals_upheld, rec, review(rec, reviews.UPHELD)), []
        )
        self.assertEqual(
            _held(
                check_first_dismissals_upheld,
                record(finding(WARNING, "false-positive")),
            ),
            [],
        )
        # a carried one is the carried closing's, held once
        carried = record(finding(BLOCKER, "false-positive", carries=f"{EARLIER}#1"))
        self.assertEqual(_held(check_first_dismissals_upheld, carried), [])
        self.assertEqual(len(_held(check_carried_closings_upheld, carried)), 1)


class ACarriedClosingIsUpheld(unittest.TestCase):
    """LAB-015 Preflight audit before freezing: a carried BLOCKER the
    follow-up did not find resolved, then closed `false-positive`, owes a
    second auditor (`check_carried_closings_upheld`)."""

    def test_a_carried_finding_closed_unreviewed_blocks(self):
        rec = record(finding(BLOCKER, "false-positive", carries=f"{EARLIER}#1"))
        (f,) = _held(check_carried_closings_upheld, rec)
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (BLOCKER, GUARANTEED, LAB_015)
        )
        self.assertEqual(
            f.text,
            f"audit {rec.path.stem} #1: a carried finding (from {EARLIER}#1) "
            f"`false-positive` — the follow-up did not find the fault gone, so "
            f"closing it settles nothing by itself (LAB-015 Preflight audit before "
            f"freezing)",
        )
        self.assertEqual(
            f.fix,
            f"{STEP} asks a second auditor whether the reason shows it does not "
            f"apply to the code and run as audited",
        )

    def test_the_twin_upheld_and_a_carried_finding_still_open_pass(self):
        rec = record(finding(BLOCKER, "false-positive", carries=f"{EARLIER}#1"))
        self.assertEqual(
            _held(check_carried_closings_upheld, rec, review(rec, reviews.UPHELD)), []
        )
        still_open = record(finding(BLOCKER, "open", carries=f"{EARLIER}#1"))
        self.assertEqual(_held(check_carried_closings_upheld, still_open), [])


class AnEarlierBlockerIsReleased(unittest.TestCase):
    """LAB-015 Preflight audit before freezing: an earlier decided BLOCKER
    holds the state reported now until a follow-up releases it (`check_earlier_blockers_released`, the rule in
    `followup.release_holds`)."""

    def test_one_never_followed_up_blocks_with_the_follow_up_audit(self):
        earlier = record(finding(BLOCKER, "false-positive"), name=EARLIER)
        cover = record()
        (f,) = pure_call(
            check_earlier_blockers_released, [earlier, cover], [cover], None
        )
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (BLOCKER, GUARANTEED, LAB_015)
        )
        self.assertEqual(
            f.text,
            f"audit {EARLIER}#1: decided `false-positive`, never followed up "
            f"(LAB-015 Preflight audit before freezing)",
        )
        self.assertEqual(f.fix, followup.STEP_AUDIT)

    def test_without_a_cover_only_a_hold_that_owes_more_than_the_audit_stays(self):
        # the missing analysis audit names the follow-up audit once
        earlier = record(finding(BLOCKER, "false-positive"), name=EARLIER)
        self.assertEqual(
            pure_call(check_earlier_blockers_released, [earlier], [], None), []
        )
        owes_a_check = record(
            finding(BLOCKER, "fixed", check="leak_rows"), name=EARLIER
        )
        (f,) = pure_call(check_earlier_blockers_released, [owes_a_check], [], None)
        self.assertIn("the run lacks the required check `leak_rows`", f.text)

    def test_the_twin_a_valid_resolved_of_the_covering_record_releases(self):
        decided = finding(BLOCKER, "false-positive")
        earlier = record(decided, name=EARLIER)
        cover = audit_record(
            RECORD,
            mode=ANALYSIS_AUDIT,
            run_id="r1",
            fix_verdicts=[
                findings.FixVerdict(
                    EARLIER, 1, findings.decision_digest(decided), "resolved", "gone"
                )
            ],
        )
        self.assertEqual(
            pure_call(check_earlier_blockers_released, [earlier, cover], [cover], None),
            [],
        )

    def test_carried_findings_that_form_no_chain_raise(self):
        dangling = record(finding(BLOCKER, "open", carries="no-such-record.toml#1"))
        with self.assertRaises(findings.FindingsError):
            pure_call(check_earlier_blockers_released, [dangling], [dangling], None)
