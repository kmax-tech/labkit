"""`report_decisions`' stations as gate tests: what each adds to the pure
checks it composes — which records it reads, the way out it hands in, and
what it makes of an input that does not read — from a context built in
memory (`state_fixture.checked`). The conditions themselves are rule tests
(`tests/test_rules_report_decisions.py`).
"""

from __future__ import annotations

import dataclasses
import unittest
from unittest import mock

from labkit.formats import findings, followup
from labkit.formats.gate import BLOCKER, NOT_EXECUTABLE, OPEN_RULE, VIOLATED, WARNING
from labkit.formats.standard_contract import ANALYSIS_AUDIT
from labkit.gates import report_decisions
from protocol_fixture import head
from state_fixture import AREA, area_evidence, audit_record, checked

RUN_ID = "2026-11-10T10-00-00_ab12"
RUN = AREA / "runs" / RUN_ID
REPORTED = head(repeat_cost="low", result=RUN_ID)
CONCLUSION = "\n- **Conclusion:** the fit is in-sample; nothing more is claimed.\n"
RECORD = "2026-11-10T10-00-analysis.toml"


def finding(status: str, *, effect: str = "", carries: str = "") -> findings.Finding:
    """A BLOCKER in the measuring script, decided STATUS with EFFECT;
    CARRIES the earlier finding it continues."""
    return findings.Finding(
        BLOCKER,
        "BLOCKER · scripts/01_measure.py:3 · statement · the target leaks",
        status,
        "the column is a constant",
        effect=effect,
        carries=carries,
    )


def covering(*found: findings.Finding) -> mock._patch:
    """`covering_analysis` answering one analysis record that holds FOUND —
    the station's read of the area, replaced."""
    record = audit_record(RECORD, mode=ANALYSIS_AUDIT, run_id=RUN_ID, found=found)
    return mock.patch.object(
        report_decisions, "covering_analysis", return_value=[record]
    )


class TheResultSectionCannotBeRendered(unittest.TestCase):
    """`limit_gaps`: a result that does not render from the run is one
    blocker naming why, after the limits without an effect — never a pass."""

    def _gaps(self, raised: BaseException):
        with (
            covering(finding("limitation")),
            mock.patch.object(report_decisions, "rendering", side_effect=raised),
        ):
            return report_decisions.limit_gaps(checked(REPORTED, run=RUN))

    def test_metrics_that_do_not_read_block_beside_the_limit_without_effect(self):
        effect, f = self._gaps(ValueError("metrics.json: not JSON"))
        self.assertIn("owes its effect on the verdicts", effect.text)
        # the command as the station spells it, for this record
        self.assertIn(
            f'--decide 1 limitation --why "<why>" --record {RECORD}', effect.fix or ""
        )
        self.assertEqual(
            (f.grade, f.rule, f.check_outcome), (BLOCKER, OPEN_RULE, VIOLATED)
        )
        self.assertEqual(
            f.text,
            f"the result cannot be rendered from {RUN_ID}: metrics.json: not JSON",
        )
        self.assertIn("protocol-fill", f.fix or "")

    def test_a_refused_access_leaves_the_check_not_executed(self):
        _, f = self._gaps(PermissionError("metrics.json refused"))
        self.assertEqual(f.check_outcome, NOT_EXECUTABLE)

    def test_the_twin_nothing_reported_owes_no_rendering(self):
        with (
            covering(finding("limitation", effect=findings.EFFECT_STANDS)),
            mock.patch.object(report_decisions, "rendering") as rendering,
        ):
            gaps = report_decisions.limit_gaps(
                checked(head(repeat_cost="low"), run=RUN)
            )
        self.assertEqual(gaps, [])
        rendering.assert_not_called()


class TheReviewStationHandsTheWayIn(unittest.TestCase):
    """`review_findings`: every check of a covering record runs, an unread
    review is named first, and the way out is the review as it can be
    followed — after the Conclusion, while that is unwritten."""

    def test_an_unread_review_is_named_and_the_decisions_stay_held(self):
        evidence = dataclasses.replace(
            area_evidence(), reviews_unread="audits/reviews/x.toml: not TOML"
        )
        with covering(
            finding("limitation", effect=findings.EFFECT_STANDS),
            finding("false-positive"),
        ):
            unread, stands, dismissed = report_decisions.review_findings(
                checked(REPORTED + CONCLUSION, run=RUN, evidence=evidence)
            )
        self.assertEqual(unread.grade, WARNING)
        self.assertIn("`stands` on a BLOCKER decided limitation", stands.text)
        self.assertIn("`false-positive` on a BLOCKER not reviewed", dismissed.text)
        assert stands.fix is not None
        self.assertTrue(
            stands.fix.startswith(
                f"`labkit-audit area --review --record {RECORD}` asks"
            ),
            stands.fix,
        )

    def test_an_unwritten_conclusion_comes_before_the_review(self):
        with covering(finding("false-positive")):
            (f,) = report_decisions.review_findings(checked(REPORTED, run=RUN))
        assert f.fix is not None
        self.assertTrue(
            f.fix.startswith(
                "write the Conclusion in PROTOCOL-x.md first (the review judges that "
                f"claim, and refuses without it), then `labkit-audit area --review "
                f"--record {RECORD}` asks"
            ),
            f.fix,
        )

    def test_the_twin_no_run_and_no_covering_record_hold_nothing(self):
        self.assertEqual(
            report_decisions.review_findings(checked(REPORTED, run=None)), []
        )
        with mock.patch.object(report_decisions, "covering_analysis", return_value=[]):
            self.assertEqual(
                report_decisions.review_findings(checked(REPORTED, run=RUN)), []
            )


class TheCarriedFindingsFormNoChain(unittest.TestCase):
    """`followup_findings`: carried findings that form no chain are one
    blocker — the release cannot be judged, and nothing passes for it."""

    def test_a_carry_that_names_no_finding_blocks_with_the_record_way(self):
        dangling = audit_record(
            RECORD,
            mode=ANALYSIS_AUDIT,
            run_id=RUN_ID,
            found=[finding("open", carries="no-such-record.toml#1")],
        )
        with (
            mock.patch.object(
                report_decisions, "covering_analysis", return_value=[dangling]
            ),
            mock.patch.object(followup, "protocol_records", return_value=[dangling]),
        ):
            (f,) = report_decisions.followup_findings(checked(REPORTED, run=RUN))
        self.assertEqual(
            (f.grade, f.rule, f.check_outcome), (BLOCKER, OPEN_RULE, VIOLATED)
        )
        self.assertTrue(
            f.text.startswith("the carried findings of area do not form a chain: "),
            f.text,
        )
        self.assertEqual(f.fix, findings.record_way(AREA, AREA / "PROTOCOL-x.md"))

    def test_the_twin_a_chain_that_reads_holds_the_carried_closing_alone(self):
        earlier = audit_record(
            "2026-11-09T10-00-analysis.toml",
            mode=ANALYSIS_AUDIT,
            run_id=RUN_ID,
            found=[finding("fixed")],
        )
        carried = audit_record(
            RECORD,
            mode=ANALYSIS_AUDIT,
            run_id=RUN_ID,
            found=[finding("false-positive", carries=f"{earlier.path.name}#1")],
        )
        with (
            mock.patch.object(
                report_decisions, "covering_analysis", return_value=[carried]
            ),
            mock.patch.object(
                followup, "protocol_records", return_value=[earlier, carried]
            ),
        ):
            (f,) = report_decisions.followup_findings(
                checked(REPORTED + CONCLUSION, run=RUN)
            )
        self.assertIn(
            f"a carried finding (from {earlier.path.name}#1) `false-positive`", f.text
        )
