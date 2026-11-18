"""Rule tests of the correction in place: which change of what the number is
about a follow-up's `resolved` releases (`followup.released_corrections`,
`registration_hold.split_released`), which correction a follow-up would
judge (`followup.awaited_corrections`, `registration_hold.waiting_refs`),
and the way out each scope hold names first (`registration_hold.seen_hold`,
`now_hold`, `description_added`) — each condition from typed data in
memory, the release and its refusals (docs/architecture.md,
"Checks and their tests"). The gate that reads the records and the protocol texts is
`registration_hold.scope_changes`, finalize's station 2; the route through
the commands: tests/test_end_to_end.py, `CorrectedDescription` and
`CorrectionThenNewRun`.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from check_guards import pure_call
from labkit.formats import findings
from labkit.formats.commands import AUDIT, MEASURE, RESTORE, WITHDRAW, Command
from labkit.formats.followup import (
    Correction,
    awaited_corrections,
    chain,
    released_corrections,
)
from labkit.formats.gate import (
    BLOCKER,
    NOT_EXECUTABLE,
    OPEN_RULE,
    TECHNICAL_RULE,
    WARNING,
    GateFinding,
    cited_rule,
)
from labkit.formats.protocol_history import STANDS_AS_REGISTERED, scope_differences
from labkit.formats.standard_contract import ANALYSIS_AUDIT
from labkit.gates import registration_hold
from labkit.gates.audit_prompt import Followup, carried_of
from labkit.gates.registration_hold import (
    CORRECTION_ROUTE,
    DESCRIPTION_ADDED,
    FirstMeasurement,
    description_added,
    lost_record_warnings,
    now_hold,
    seen_hold,
    split_released,
    waiting_refs,
)
from labkit.formats.area_state import (
    CLOCKS_ASSUMED,
    UNASSIGNED_LEAVES_OPEN,
    Measured,
    WithoutRecord,
    measurements_without_record,
)
from labkit.formats.runs import RunDir, parse_run_config
from labkit.gates.ways_out import HANDOVER
from protocol_fixture import run_record
from state_fixture import AREA, area_evidence, area_state, audit_record, run_dir

pytestmark = pytest.mark.rule

PROTOCOL = AREA / "PROTOCOL-x.md"
TEXT = (
    "- **Question / hypothesis:** How many lines does a document hold on average?\n"
    "- **Data / scope:** data/raw/docs, 3 documents, read directly\n"
    "- **Unit:** one document of data/raw/docs\n"
)
AUDITED = "2026-11-10T10-00-analysis.toml"  # the audit that found it
FOLLOW_UP = "2026-11-10T11-00-analysis.toml"  # the follow-up that judged it


def finding(
    place: str, *, grade: str = "WARNING", status: str = "fixed"
) -> findings.Finding:
    """A finding whose grade line names PLACE of PROTOCOL, decided STATUS."""
    return findings.Finding(
        grade,
        f"{grade} · PROTOCOL-x.md:{place} · statement · Data / scope says 4 · "
        f"the denominator · LAB-050 Analysis audit before reporting · correct it",
        status,
        "corrected as the audit asked",
    )


def field_of(f: findings.Finding) -> str | None:
    """The field F corrects in TEXT, as the gate reads it."""
    return findings.corrected_field(f, PROTOCOL, TEXT)


def verdict(
    on: findings.Finding, n: int = 1, *, said: str = "resolved", sha: str | None = None
) -> findings.FixVerdict:
    """A follow-up's verdict SAID on finding N of AUDITED, bound to ON as
    decided (or to SHA)."""
    return findings.FixVerdict(
        AUDITED,
        n,
        sha if sha is not None else findings.decision_digest(on),
        said,
        "the field now says 3 documents, as the run read",
    )


def released(
    found: list[findings.Finding],
    verdicts: list[findings.FixVerdict],
    *,
    covers: bool = True,
) -> dict[str, Correction]:
    """What the follow-up releases: AUDITED holding FOUND, the follow-up
    holding VERDICTS, covering the area now where COVERS."""
    audited = audit_record(AUDITED, mode=ANALYSIS_AUDIT, run_id="r1", found=found)
    follow_up = audit_record(
        FOLLOW_UP, mode=ANALYSIS_AUDIT, run_id="r1", fix_verdicts=verdicts
    )
    members = chain([audited, follow_up]).members
    return pure_call(
        released_corrections, [follow_up] if covers else [], members, field_of
    )


class AResolvedCorrectionReleasesItsField(unittest.TestCase):
    """A field changed after the first measurement is released only by a
    follow-up's `resolved` on a finding that names the field as its place,
    decided `fixed`, in a record that covers the area now, bound to the
    decision as it stands."""

    def test_a_resolved_correction_releases_its_field(self):
        f = finding("Data / scope")
        self.assertEqual(
            released([f], [verdict(f)]),
            {
                "data / scope": Correction(
                    f"{AUDITED}#1",
                    FOLLOW_UP,
                    "the field now says 3 documents, as the run read",
                )
            },
        )

    def test_a_blocker_and_a_warning_are_released_alike(self):
        for grade in (BLOCKER, "WARNING"):
            with self.subTest(grade):
                f = finding("Data / scope", grade=grade)
                self.assertIn("data / scope", released([f], [verdict(f)]))

    def test_the_refusals_release_nothing(self):
        f = finding("Data / scope")
        for why, found, verdicts, covers in (
            ("judged unresolved", [f], [verdict(f, said="unresolved")], True),
            ("not assessable", [f], [verdict(f, said="not_assessable")], True),
            ("a fresh audit without a verdict", [f], [], True),
            (
                "the verdict bound to an earlier decision",
                [f],
                [verdict(f, sha="0" * 12)],
                True,
            ),
            ("a record that no longer covers the area", [f], [verdict(f)], False),
            ("a verdict on a finding no record holds", [f], [verdict(f, n=2)], True),
        ):
            with self.subTest(why):
                self.assertEqual(released(found, verdicts, covers=covers), {})

    def test_no_field_named_releases_nothing(self):
        """The place must name a field a correction can release: a line
        number, the question, a finding not decided `fixed` name none
        (`findings.corrected_field`)."""
        for why, f in (
            ("a line number", finding("2")),
            ("the question", finding("Question / hypothesis")),
            ("decided limitation", finding("Data / scope", status="limitation")),
        ):
            with self.subTest(why):
                self.assertEqual(released([f], [verdict(f)]), {})

    def test_a_verdict_on_one_field_releases_that_field_alone(self):
        unit, scope = finding("Unit"), finding("Data / scope")
        self.assertEqual(set(released([unit, scope], [verdict(unit, 1)])), {"unit"})
        self.assertEqual(
            set(released([unit, scope], [verdict(unit, 1), verdict(scope, 2)])),
            {"unit", "data / scope"},
        )

    def test_a_field_whose_place_cannot_be_told_is_raised_not_skipped(self):
        """FIELD_OF's error comes through: which field the correction is
        bound to cannot be told, and the gate holds that."""
        f = finding("Data / scope")
        audited = audit_record(AUDITED, mode=ANALYSIS_AUDIT, run_id="r1", found=[f])
        follow_up = audit_record(
            FOLLOW_UP, mode=ANALYSIS_AUDIT, run_id="r1", fix_verdicts=[verdict(f)]
        )

        def unclear(_: findings.Finding) -> str | None:
            raise ValueError("begins several fields")

        with self.assertRaisesRegex(ValueError, "begins several fields"):
            pure_call(
                released_corrections,
                [follow_up],
                chain([audited, follow_up]).members,
                unclear,
            )


class TheReleaseHoldsEachFieldOnItsOwn(unittest.TestCase):
    """`split_released`: a difference is released where its field's
    correction is resolved and the field reads the same in the protocol as
    the run saw it and as it stands."""

    SCOPE = ("Data / scope", "data/raw/docs, 4 documents", "data/raw/docs, 3 documents")
    UNIT = ("Unit", "one document", "one text document")
    C = Correction(f"{AUDITED}#1", FOLLOW_UP, "as read")

    def test_a_resolved_field_is_released_and_another_kept(self):
        kept, corrected = pure_call(
            split_released, [self.SCOPE, self.UNIT], {"data / scope": self.C}, set()
        )
        self.assertEqual(kept, [self.UNIT])
        self.assertEqual(corrected, [(self.SCOPE, self.C)])

    def test_the_twin_a_field_edited_after_the_run_saw_it_is_kept(self):
        kept, corrected = pure_call(
            split_released, [self.SCOPE], {"data / scope": self.C}, {"Data / scope"}
        )
        self.assertEqual((kept, corrected), ([self.SCOPE], []))


class TheReleaseReadsWhichFieldTheRunSawOtherwise(unittest.TestCase):
    """`released_fields`: what the caller adds to `split_released` — it
    tells from the protocol as the run saw it and as it stands which field
    was edited since (`moved_fields`) and hands that on. Which corrections
    are resolved is given here; `resolved_corrections` reads the area's
    records."""

    SCOPE = TheReleaseHoldsEachFieldOnItsOwn.SCOPE
    C = TheReleaseHoldsEachFieldOnItsOwn.C
    SCOPE_EDITED = TEXT.replace("read directly", "read through the loader")
    UNIT_EDITED = TEXT.replace("one document of", "one text document of")

    def released(self, seen: str, text: str):
        with mock.patch.object(
            registration_hold,
            "resolved_corrections",
            return_value={"data / scope": self.C},
        ):
            return registration_hold.released_fields(
                [self.SCOPE],
                AREA,
                AREA / "PROTOCOL-x.md",
                text,
                AREA / "runs" / "r1",
                seen,
                area_evidence(),
            )

    def test_a_field_edited_after_the_run_saw_it_stays_held(self):
        """Its correction is resolved on the text as it stands, but the run
        measured under another description."""
        self.assertNotEqual(self.SCOPE_EDITED, TEXT)
        self.assertEqual(self.released(TEXT, self.SCOPE_EDITED), ([self.SCOPE], []))

    def test_the_twin_a_field_that_reads_as_the_run_saw_it_is_released(self):
        self.assertEqual(self.released(TEXT, TEXT), ([], [(self.SCOPE, self.C)]))

    def test_another_field_edited_after_the_run_holds_this_one_not(self):
        self.assertNotEqual(self.UNIT_EDITED, TEXT)
        self.assertEqual(
            self.released(TEXT, self.UNIT_EDITED), ([], [(self.SCOPE, self.C)])
        )


def awaited(records: list[findings.Record], current: set[str]) -> dict[str, str]:
    return pure_call(
        awaited_corrections, records, lambda r: r.path.name in current, field_of
    )


class AFollowUpJudgesTheDecidedCorrection(unittest.TestCase):
    """`awaited_corrections`: the corrections a follow-up audit of the state
    now would be shown and judge — a finding decided `fixed` that names a
    field, in a record that does not cover the state now."""

    def test_a_decided_correction_of_an_earlier_state_is_awaited(self):
        for grade in (BLOCKER, "WARNING"):
            with self.subTest(grade):
                record = audit_record(
                    AUDITED,
                    mode=ANALYSIS_AUDIT,
                    run_id="r1",
                    found=[finding("Data / scope", grade=grade)],
                )
                self.assertEqual(
                    awaited([record], set()), {"data / scope": f"{AUDITED}#1"}
                )

    def test_the_twins_are_awaited_not(self):
        for why, f, current in (
            ("its record covers the state now", finding("Data / scope"), {AUDITED}),
            ("a line number names no field", finding("2"), set()),
            ("the question has no correction", finding("Question / hypothesis"), set()),
            ("not decided fixed", finding("Data / scope", status="open"), set()),
        ):
            with self.subTest(why):
                record = audit_record(
                    AUDITED, mode=ANALYSIS_AUDIT, run_id="r1", found=[f]
                )
                self.assertEqual(awaited([record], current), {})


class TheRefsAHoldLeadsWith(unittest.TestCase):
    """`waiting_refs`: a hold leads with the follow-up only where every
    held field's correction is awaited."""

    def test_a_ref_per_difference_none_for_a_field_without_or_moved(self):
        diffs = [("Data / scope", "a", "b"), ("Question / hypothesis", "c", "d")]
        waiting = {"data / scope": f"{AUDITED}#1"}
        self.assertEqual(
            pure_call(waiting_refs, diffs, waiting), [f"{AUDITED}#1", None]
        )
        self.assertEqual(
            pure_call(waiting_refs, diffs[:1], waiting, {"Data / scope"}), [None]
        )


FIRST = FirstMeasurement(
    "2026-11-10T09-00-00_aaaa",
    " (`git show abc123:PROTOCOL-x.md`)",
    Command(RESTORE, "protocol-fill PROTOCOL-x.md --force …"),
)
ANALYSIS = Command(AUDIT, "labkit-audit area --mode analysis")
MEASURE_AGAIN = Command(MEASURE, "python area/scripts/01_measure.py")
SCOPE = [("Data / scope", "data/raw/docs, 4 documents", "data/raw/docs, 3 documents")]
QUESTION = [("Question / hypothesis", "the mean?", "the median?")]
REF = f"{AUDITED}#1"
PID = "p-0123456789abcdef"


class TheFollowUpLeadsOnlyForAFieldTheRunSawAsItStands(unittest.TestCase):
    """`_scope_held`, the hold of the answering run's text: what the gate
    adds to `waiting_refs` — it tells which field was edited after the run
    (`moved_fields`), and for that field no follow-up leads the way out,
    since no verdict on today's text covers the run. What the run saw, the
    difference to the first measurement and the decided correction are
    given; their readers open the repository and the records."""

    LEADS = "the follow-up analysis audit on r2 "

    def fix(self, text: str) -> str:
        state = area_state(
            protocols=[PROTOCOL], protocol_texts={PROTOCOL.resolve(): text}
        )
        history = registration_hold.protocol_history
        with (
            mock.patch.object(registration_hold, "read_run_dir"),
            mock.patch.object(history, "as_measured", return_value=(TEXT, "")),
            mock.patch.object(
                history, "first_measured_differences", return_value=(None, SCOPE)
            ),
            mock.patch.object(
                registration_hold, "resolved_corrections", return_value={}
            ),
            mock.patch.object(
                registration_hold,
                "awaiting_followup",
                return_value={"data / scope": REF},
            ),
            mock.patch.object(
                registration_hold, "first_measurement", return_value=FIRST
            ),
        ):
            (f,) = registration_hold._scope_held(
                AREA,
                PROTOCOL,
                PID,
                AREA / "runs" / "r2",
                None,
                [],  # no first measurements to hold to each other
                [mock.sentinel.first_measurement],
                Measured(AREA, PID, (), (), (), ()),
                state,
                area_evidence(),
            )
        assert f.fix is not None
        return f.fix

    def test_a_field_edited_after_the_run_saw_it_gets_no_follow_up_first(self):
        edited = TEXT.replace("read directly", "read through the loader")
        self.assertNotEqual(edited, TEXT)
        self.assertFalse(self.fix(edited).startswith(self.LEADS), self.fix(edited))

    def test_the_twin_a_field_that_reads_as_the_run_saw_it_leads_with_it(self):
        self.assertTrue(self.fix(TEXT).startswith(self.LEADS), self.fix(TEXT))

    def test_another_field_edited_after_the_run_changes_nothing_for_this_one(self):
        edited = TEXT.replace("one document of", "one text document of")
        self.assertNotEqual(edited, TEXT)
        self.assertTrue(self.fix(edited).startswith(self.LEADS), self.fix(edited))


class TheRuleAScopeHoldRecords(unittest.TestCase):
    """`scope_rule`: LAB-003's text names the fields, LAB-035's the
    registered comparison; the head's `kind` and `[kept]` no rule's — a
    hold on those records an open assignment. The comparison beside
    another part is two causes, refused here and parted before
    (`by_cause`)."""

    LAB_003 = cited_rule("LAB-003 No run without an intent paragraph")
    LAB_035 = cited_rule("LAB-035 Thresholds belong to the run, not to the measure")
    REFERENCE = ("[reference]", "a", "b")

    def test_a_field_the_rule_names_records_the_rule(self):
        self.assertEqual(registration_hold.scope_rule(SCOPE), self.LAB_003)

    def test_a_head_part_no_rule_names_is_open_alone_or_among_others(self):
        self.assertEqual(registration_hold.UNNAMED_HEAD_PARTS, ("kind", "[kept]"))
        for part in registration_hold.UNNAMED_HEAD_PARTS:
            diff = (part, "a", "b")
            with self.subTest(part=part):
                self.assertEqual(registration_hold.scope_rule([diff]), OPEN_RULE)
                self.assertEqual(
                    registration_hold.scope_rule([*SCOPE, diff]), OPEN_RULE
                )

    def test_the_comparison_alone_records_the_rule_that_fixes_it(self):
        self.assertEqual(registration_hold.scope_rule([self.REFERENCE]), self.LAB_035)

    def test_the_comparison_beside_another_part_is_refused_as_two_causes(self):
        for other in (*SCOPE, ("kind", "a", "b")):
            with self.subTest(other=other[0]):
                with self.assertRaisesRegex(ValueError, "records one rule"):
                    registration_hold.scope_rule([other, self.REFERENCE])

    def test_the_hold_blocks_whatever_rule_it_records(self):
        (f,) = pure_call(
            seen_hold, PID, "r2", FIRST, [("[kept]", "a", "b")], [None], ANALYSIS
        )
        self.assertEqual((f.grade, f.rule), (BLOCKER, OPEN_RULE))


class TheComparisonAndTheFieldsAreTwoFindings(unittest.TestCase):
    """`by_cause`, and both holds through it: the registered comparison
    changed together with a field is two findings — the fields under
    LAB-003, the comparison under LAB-035 —, each a BLOCKER with its own
    way out; one cause stays one finding."""

    LAB_003 = cited_rule("LAB-003 No run without an intent paragraph")
    LAB_035 = cited_rule("LAB-035 Thresholds belong to the run, not to the measure")
    REFERENCE = ("[reference]", "0.70", "0.60")

    def both(self, diffs, refs, *, measure=None, withdraw=None):
        seen = pure_call(seen_hold, PID, "r2", FIRST, diffs, refs, ANALYSIS)
        now = pure_call(
            now_hold,
            PID,
            "r1",
            FIRST,
            diffs,
            refs,
            ANALYSIS,
            measure=measure,
            withdraw=withdraw,
        )
        return seen, now

    def test_the_refs_stay_with_their_differences(self):
        mixed = [self.REFERENCE, *SCOPE, ("kind", "a", "b")]
        self.assertEqual(
            registration_hold.by_cause(mixed, [None, REF, None]),
            [
                ([*SCOPE, ("kind", "a", "b")], [REF, None]),
                ([self.REFERENCE], [None]),
            ],
        )
        self.assertEqual(registration_hold.by_cause([], []), [])
        with self.assertRaises(ValueError):  # a ref per difference
            registration_hold.by_cause(SCOPE, [])

    def test_each_cause_blocks_under_its_rule_with_its_own_way_out(self):
        for held in self.both([*SCOPE, self.REFERENCE], [None, None]):
            with self.subTest(held=held[0].text[-40:]):
                fields, comparison = held
                self.assertEqual(
                    [(f.grade, f.rule) for f in held],
                    [(BLOCKER, self.LAB_003), (BLOCKER, self.LAB_035)],
                )
                self.assertIn("Data / scope", fields.text)
                self.assertNotIn("[reference]", fields.text)
                self.assertIn('[reference] "0.70" → "0.60"', comparison.text)
                self.assertNotIn("Data / scope", comparison.text)
                assert fields.fix is not None and comparison.fix is not None
                self.assertTrue(fields.fix.startswith("restore Data / scope as"))
                self.assertIn(CORRECTION_ROUTE, fields.fix)
                # the comparison has no correction in place: restore or anew
                self.assertTrue(comparison.fix.startswith("restore [reference] as"))
                self.assertNotIn(CORRECTION_ROUTE, comparison.fix)
                self.assertIn("register anew", comparison.fix)

    def test_a_decided_correction_leads_its_own_cause_only(self):
        """The field's correction is decided: its finding leads with the
        follow-up, the comparison's still with the restore."""
        for fields, comparison in self.both([*SCOPE, self.REFERENCE], [REF, None]):
            assert fields.fix is not None and comparison.fix is not None
            self.assertTrue(fields.fix.startswith("the follow-up analysis audit on"))
            self.assertIn(REF, fields.fix)
            self.assertTrue(comparison.fix.startswith("restore [reference] as"))
            self.assertNotIn(REF, comparison.fix)

    def test_a_head_part_beside_the_comparison_keeps_its_open_assignment(self):
        seen, now = self.both([("kind", "a", "b"), self.REFERENCE], [None, None])
        for held in (seen, now):
            self.assertEqual([f.rule for f in held], [OPEN_RULE, self.LAB_035])

    def test_a_standing_adoption_is_withdrawn_first_in_each(self):
        withdraw = Command(WITHDRAW, "protocol-fill --withdraw")
        _, now = self.both([*SCOPE, self.REFERENCE], [None, None], withdraw=withdraw)
        self.assertEqual([f.withdraw_first for f in now], [withdraw, withdraw])

    def test_the_twin_one_cause_is_one_finding(self):
        for diffs, rule in ((SCOPE, self.LAB_003), ([self.REFERENCE], self.LAB_035)):
            with self.subTest(rule=rule.rule_id):
                for held in self.both(diffs, [None] * len(diffs)):
                    self.assertEqual([f.rule for f in held], [rule])


class TheHoldAsTheRunSawIt(unittest.TestCase):
    """`seen_hold`: a change the answering run measured under."""

    def test_a_decided_correction_leads_with_the_follow_up_on_this_run(self):
        (f,) = pure_call(seen_hold, PID, "r2", FIRST, SCOPE, [REF], ANALYSIS)
        self.assertEqual(
            (f.grade, f.rule, f.step),
            (
                BLOCKER,
                cited_rule("LAB-003 No run without an intent paragraph"),
                FIRST.step,
            ),
        )
        self.assertIn(
            f"after the first measurement {FIRST.run_id}: Data / scope", f.text
        )
        self.assertIn("(as the answering run r2 saw the protocol)", f.text)
        assert f.fix is not None
        self.assertTrue(
            f.fix.startswith(
                f"the follow-up analysis audit on r2 (`{ANALYSIS}`) judges {REF}"
            ),
            f.fix,
        )
        self.assertIn("a verdict on an earlier run releases nothing", f.fix)
        self.assertIn("restore Data / scope", f.fix)
        self.assertIn("register anew", f.fix)

    def test_the_twin_a_field_without_a_correction_leads_with_the_restore(self):
        """The question has no correction in place: the hold leads with the
        way back and says the question stands as registered."""
        (f,) = pure_call(seen_hold, PID, "r2", FIRST, QUESTION, [None], ANALYSIS)
        assert f.fix is not None
        self.assertTrue(f.fix.startswith("restore Question / hypothesis"), f.fix)
        self.assertNotIn("the follow-up analysis audit on", f.fix)
        self.assertIn(f"Question / hypothesis {STANDS_AS_REGISTERED}", f.fix)
        self.assertIn("register anew", f.fix)
        # a correctable field held without a decided correction: the route named
        (f,) = pure_call(seen_hold, PID, "r2", FIRST, SCOPE, [None], ANALYSIS)
        assert f.fix is not None
        self.assertIn(
            f"Data / scope misdescribing the unchanged run: {CORRECTION_ROUTE}", f.fix
        )


class TheHoldAsTheProtocolStands(unittest.TestCase):
    """`now_hold`: a change no run measured under yet."""

    def hold(self, refs, *, measure=None, withdraw=None, kept=SCOPE):
        return pure_call(
            now_hold,
            PID,
            "r1",
            FIRST,
            kept,
            refs,
            ANALYSIS,
            measure=measure,
            withdraw=withdraw,
        )

    def test_a_decided_correction_leads_with_the_follow_up_no_measurement(self):
        (f,) = self.hold([REF])
        self.assertIn(
            "(as the protocol stands now; no run measured under it yet)", f.text
        )
        assert f.fix is not None
        self.assertTrue(
            f.fix.startswith(
                f"the follow-up analysis audit on the run as it stands (`{ANALYSIS}`) judges {REF}"
            ),
            f.fix,
        )
        self.assertIn("no new measurement is owed", f.fix)
        self.assertIsNone(f.withdraw_first)

    def test_a_code_change_beside_it_measures_again_first(self):
        (f,) = self.hold([REF], measure=MEASURE_AGAIN)
        assert f.fix is not None
        self.assertTrue(
            f.fix.startswith(
                f"the measuring code changed since r1 ran: measure again (`{MEASURE_AGAIN}`)"
            ),
            f.fix,
        )
        self.assertIn(
            f"then the follow-up analysis audit on that run (`{ANALYSIS}`)", f.fix
        )

    def test_the_twin_without_a_decided_correction_the_restore_comes_first(self):
        for measure in (None, MEASURE_AGAIN):
            with self.subTest(measure=measure):
                (f,) = self.hold([None], measure=measure, kept=QUESTION)
                assert f.fix is not None
                self.assertTrue(
                    f.fix.startswith("restore Question / hypothesis"), f.fix
                )
                self.assertNotIn("follow-up analysis audit", f.fix)
                self.assertNotIn("measure again", f.fix)
                self.assertIn(f"Question / hypothesis {STANDS_AS_REGISTERED}", f.fix)

    def test_a_standing_adoption_is_withdrawn_first(self):
        withdraw = Command(WITHDRAW, "protocol-fill PROTOCOL-x.md --withdraw --why x")
        (f,) = self.hold([REF], measure=MEASURE_AGAIN, withdraw=withdraw)
        self.assertEqual(f.withdraw_first, withdraw)


class AnAdditionIsToldWhereItBelongs(unittest.TestCase):
    """`description_added`: where every held field only grew, the hold
    names the Conclusion or the report for the addition; the hold itself
    is the same."""

    def test_a_field_that_only_grew_names_where_the_addition_belongs(self):
        grew = [("Data / scope", "4 documents", "4 documents; two held out")]
        self.assertEqual(pure_call(description_added, grew), DESCRIPTION_ADDED)

    def test_the_twins_a_rewrite_or_one_rewritten_field_name_nothing(self):
        for diffs in (
            [("Data / scope", "4 documents", "3 documents")],
            [
                ("Data / scope", "4 documents", "4 documents; two held out"),
                ("Unit", "one document", "one text"),
            ],
            [],
        ):
            with self.subTest(diffs):
                self.assertEqual(pure_call(description_added, diffs), "")


class AReflowedFieldIsNoChange(unittest.TestCase):
    """What the number is about is compared with its whitespace folded
    (`protocol_history.scope_value`): a field re-spaced is no change, a
    word changed is."""

    def test_a_reflowed_question_is_no_difference_and_a_reworded_one_is(self):
        reflowed = TEXT.replace(" a document ", "  a   document ")
        self.assertNotEqual(reflowed, TEXT)
        self.assertEqual(pure_call(scope_differences, TEXT, reflowed), [])
        reworded = TEXT.replace("on average", "at the median")
        self.assertEqual(
            [what for what, _, _ in pure_call(scope_differences, TEXT, reworded)],
            ["Question / hypothesis"],
        )


class AnUnresolvedCorrectionIsCarriedOnlyAsABlocker(unittest.TestCase):
    """`audit_prompt.carried_of`: a follow-up's verdict other than
    `resolved` carries a shown BLOCKER into the new record, open; a
    correction of another grade is not carried — without its `resolved`
    the field's change stays held where finalize compares it."""

    def carried(self, grade: str, said: str) -> list[findings.Finding]:
        f = finding("Data / scope", grade=grade)
        record = audit_record(AUDITED, mode=ANALYSIS_AUDIT, run_id="r1", found=[f])
        (member,) = chain([record]).members.values()
        shown = Followup([member], None, {member.ref: f}, {})
        return pure_call(carried_of, shown, [verdict(f, said=said)])

    def test_an_unresolved_blocker_is_carried_open(self):
        (c,) = self.carried(BLOCKER, "unresolved")
        self.assertEqual(
            (c.grade, c.status, c.carries), (BLOCKER, "open", f"{AUDITED}#1")
        )

    def test_the_twins_a_warning_or_a_resolved_verdict_carry_nothing(self):
        for grade, said in (
            ("WARNING", "unresolved"),
            ("WARNING", "not_assessable"),
            (BLOCKER, "resolved"),
        ):
            with self.subTest(grade=grade, said=said):
                self.assertEqual(self.carried(grade, said), [])


class TheWayBackNamesWhatEachFieldHas(unittest.TestCase):
    """The restore-first way of both holds: the correction route for a
    field that has one, the question as registered, the addition's place
    when a field only grew — and a field without a decided correction
    beside one with it leads with the restore, not the follow-up."""

    def ways(self, diffs, refs) -> list[str]:
        (seen,) = pure_call(seen_hold, PID, "r2", FIRST, diffs, refs, ANALYSIS)
        (now,) = pure_call(
            now_hold,
            PID,
            "r1",
            FIRST,
            diffs,
            refs,
            ANALYSIS,
            measure=None,
            withdraw=None,
        )
        assert seen.fix is not None and now.fix is not None
        return [seen.fix, now.fix]

    def test_a_correctable_field_is_offered_the_route_and_no_addition(self):
        for fix in self.ways(SCOPE, [None]):
            with self.subTest(fix=fix[:40]):
                self.assertTrue(fix.startswith("restore Data / scope as"), fix)
                self.assertIn(
                    f"Data / scope misdescribing the unchanged run: {CORRECTION_ROUTE}",
                    fix,
                )
                self.assertNotIn(STANDS_AS_REGISTERED, fix)
                self.assertNotIn(DESCRIPTION_ADDED, fix)

    def test_the_question_has_no_route(self):
        for fix in self.ways(QUESTION, [None]):
            with self.subTest(fix=fix[:40]):
                self.assertIn(f"Question / hypothesis {STANDS_AS_REGISTERED}", fix)
                self.assertNotIn(CORRECTION_ROUTE, fix)
                self.assertNotIn("misdescribing the unchanged run", fix)
                self.assertIn("register anew", fix)

    def test_a_field_that_only_grew_is_told_where_the_addition_belongs(self):
        grew = [("Data / scope", "4 documents", "4 documents; two held out")]
        for fix in self.ways(grew, [None]):
            with self.subTest(fix=fix[:40]):
                self.assertTrue(fix.startswith("restore Data / scope as"), fix)
                self.assertIn(DESCRIPTION_ADDED, fix)

    def test_a_question_beside_a_decided_correction_leads_with_the_restore(self):
        for fix in self.ways(SCOPE + QUESTION, [REF, None]):
            with self.subTest(fix=fix[:40]):
                self.assertTrue(
                    fix.startswith("restore Data / scope, Question / hypothesis as"),
                    fix,
                )
                self.assertNotIn("the follow-up analysis audit on", fix)
                self.assertIn(f"Question / hypothesis {STANDS_AS_REGISTERED}", fix)


class TheRuleAChangedRegistrationRecords(unittest.TestCase):
    """`registration_rule`: the rule's text names a promise's sentence, key
    and constant; a changed declared scope is named by no sentence of it."""

    LAB_003 = cited_rule("LAB-003 No run without an intent paragraph")

    @staticmethod
    def snap(sha: str, **ids: dict) -> dict:
        return {"block_sha": sha, "ids": ids}

    C1 = {"key": "criterion_1_pass", "constants": {"margin": 0.1}, "scope": ["a.py"]}

    def rule(self, **now_ids: dict):
        was = self.snap("s1", **{"criterion-1": self.C1})
        return registration_hold.registration_rule(was, self.snap("s2", **now_ids))

    def test_a_constant_a_key_or_a_sentence_changed_records_the_rule(self):
        for part, value in (
            ("constants", {"margin": 0.2}),
            ("key", "criterion_1_ok"),
            ("scope", ["a.py"]),  # only the sentence differs: the block's sha
        ):
            with self.subTest(part=part):
                changed = {"criterion-1": {**self.C1, part: value}}
                self.assertEqual(self.rule(**changed), self.LAB_003)

    def test_a_promise_added_or_dropped_records_the_rule(self):
        added = {"criterion-1": self.C1, "criterion-2": {**self.C1, "scope": ["b.py"]}}
        self.assertEqual(self.rule(**added), self.LAB_003)
        self.assertEqual(self.rule(), self.LAB_003)

    def test_a_declared_scope_changed_is_open_alone_or_beside_a_constant(self):
        moved = {**self.C1, "scope": ["b.py"]}
        self.assertEqual(self.rule(**{"criterion-1": moved}), OPEN_RULE)
        both = {**moved, "constants": {"margin": 0.2}}
        self.assertEqual(self.rule(**{"criterion-1": both}), OPEN_RULE)

    def test_the_twin_the_same_paths_in_another_order_are_no_scope_change(self):
        two = {**self.C1, "scope": ["a.py", "b.py"]}
        was = self.snap("s1", **{"criterion-1": two})
        now = self.snap("s2", **{"criterion-1": {**two, "scope": ["b.py", "a.py"]}})
        self.assertEqual(registration_hold.registration_rule(was, now), self.LAB_003)


class ARunWithoutItsRecord(unittest.TestCase):
    """`area_state.measurements_without_record` sorts the runs without a
    record by what each means for one protocol, and the registration
    station acts on each sort: `lost_record_hold` blocks where the run may
    have been the first measurement — none that reads is known to precede
    it, or the start record does not tell their order —,
    `lost_record_warnings` names a run the start record puts after a
    measurement that reads and a record whose protocol cannot be
    determined. Two runs are ordered only where the start record holds a
    UTC start for both; which protocol a run belongs to is `Measured`'s
    (tests/test_area_state.py)."""

    FIRST = run_dir(
        "2026-10-07T10-00-00_ab12",
        config=parse_run_config(run_record(protocol={"id": PID, "path": "P.md"})),
    )
    GONE = "2026-10-07T10-00-05_105e"
    DEAD = run_dir(GONE, error="config.json: not JSON")
    NOON = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
    BEFORE, AFTER = NOON - timedelta(seconds=1), NOON + timedelta(seconds=1)

    def sorted_out(
        self,
        runs: tuple[RunDir, ...] = (),
        lost: tuple[str, ...] = (),
        unassigned: tuple[str, ...] = (),
        started_only: tuple[str, ...] = (),
        started: dict[str, datetime] | None = None,
    ) -> WithoutRecord:
        """The sort for PID over its RUNS, its LOST runs, the runs only the
        start record names, the area's UNASSIGNED records and the starts
        the start record holds (run id → UTC)."""
        measured = Measured(
            AREA, PID, runs, lost, (), (), unassigned, started_only, started or {}
        )
        return pure_call(measurements_without_record, measured, lost)

    def held(self, without: WithoutRecord) -> list[GateFinding]:
        return pure_call(
            registration_hold.lost_record_hold, PID, AREA, without, HANDOVER
        )

    def test_a_lost_run_no_measurement_that_reads_precedes_holds(self):
        first = self.FIRST.dir.name
        for name, runs, started in (
            ("nothing else measured", (), {}),
            (
                "started before the one that reads",
                (self.FIRST,),
                {self.GONE: self.BEFORE, first: self.NOON},
            ),
        ):
            with self.subTest(name):
                without = self.sorted_out(runs, (self.GONE,), started=started)
                self.assertEqual(len(without.may_be_first), 1)
                self.assertEqual(
                    (without.unordered, without.later, without.unassigned),
                    ((), (), ()),
                )
                (hold,) = self.held(without)
                self.assertEqual(
                    (hold.grade, hold.rule, hold.outcome),
                    (BLOCKER, TECHNICAL_RULE, NOT_EXECUTABLE),
                )
                self.assertIn(f"run {self.GONE} is gone", hold.text)
                self.assertIn("may have been the first", hold.text)
                self.assertIn("does not stand in for it", hold.text)
                self.assertNotIn("is unknown", hold.text)
                for way in ("a copy that holds it", "register anew", HANDOVER):
                    self.assertIn(way, hold.fix or "")
                self.assertEqual(pure_call(lost_record_warnings, without), [])

    def test_a_run_only_the_start_record_names_holds_like_a_lost_one(self):
        """A measurement that started and left nothing else — it broke off,
        or was deleted before it finished — keeps counting."""
        without = self.sorted_out(started_only=(self.GONE,))
        (hold,) = self.held(without)
        self.assertIn(
            f"run {self.GONE} is gone (the start record lists it as a measurement that "
            f"started",
            hold.text,
        )
        self.assertIn("may have been the first", hold.text)

    def test_an_order_the_start_record_does_not_tell_holds_and_says_so(self):
        """A start missing for either run, or two in one second, orders
        nothing — whatever the run ids or the index say: the run may have
        been the first, and the hold names the order as unknown with what
        is missing; its own case, on neither side silently."""
        first = self.FIRST.dir.name
        for name, started, why in (
            (
                "no start for the lost run",
                {first: self.NOON},
                f"the start record holds no start for {self.GONE}",
            ),
            (
                "no start for the one that reads",
                {self.GONE: self.AFTER},
                f"the start record holds no start for {first}",
            ),
            (
                "no start for either",
                {},
                f"the start record holds no start for {self.GONE}, {first}",
            ),
            (
                "the same second",
                {self.GONE: self.NOON, first: self.NOON},
                "the start record gives it the same second as one of them",
            ),
        ):
            with self.subTest(name):
                without = self.sorted_out((self.FIRST,), (self.GONE,), started=started)
                self.assertEqual((without.may_be_first, without.later), ((), ()))
                (hold,) = self.held(without)
                self.assertEqual(hold.outcome, NOT_EXECUTABLE)
                self.assertIn(f"run {self.GONE} is gone", hold.text)
                self.assertIn(
                    "whether it started before the measurements that read is unknown",
                    hold.text,
                )
                self.assertIn(why, hold.text)
                self.assertEqual(pure_call(lost_record_warnings, without), [])

    def test_a_lost_run_started_after_a_measurement_that_reads_is_named_not_held(
        self,
    ):
        started = {self.FIRST.dir.name: self.NOON, self.GONE: self.AFTER}
        without = self.sorted_out((self.FIRST,), (self.GONE,), started=started)
        self.assertEqual(without.held, ())
        self.assertEqual(self.held(without), [])
        (warning,) = pure_call(lost_record_warnings, without)
        self.assertEqual((warning.grade, warning.rule), (WARNING, TECHNICAL_RULE))
        self.assertIn(f"run {self.GONE} is gone", warning.text)
        self.assertIn("the comparison with the first measurement runs", warning.text)
        # a UTC start removes the zone, not the clock: the assumption is said
        self.assertIn("the start record puts its start after", warning.text)
        self.assertIn(CLOCKS_ASSUMED, warning.text)
        self.assertIn("which labkit does not check", warning.text)
        self.assertIn("a copy that holds it", warning.fix or "")

    def test_a_repeat_or_a_probe_that_reads_orders_nothing(self):
        """Only a measurement that registers — no repeat, no probe — tells
        what stood registered before a later run."""
        bound = {"protocol": {"id": PID, "path": "P.md"}}
        for name, fields in (
            ("a repeat", {"repeat_of": "2026-10-01T10-00-00_0000", "draw": 2}),
            ("a probe", {"run_kind": "probe"}),
        ):
            with self.subTest(name):
                cfg = parse_run_config(run_record({**bound, **fields}))
                other = run_dir(self.FIRST.dir.name, config=cfg)
                started = {other.dir.name: self.NOON, self.GONE: self.AFTER}
                without = self.sorted_out((other,), (self.GONE,), started=started)
                self.assertEqual(len(without.may_be_first), 1)

    def test_a_record_that_does_not_read_is_sorted_like_a_lost_run(self):
        """Among the protocol's runs by the start record or the index
        (`Measured.runs`): it holds or is named by the same rule."""
        first, dead = self.FIRST.dir.name, self.DEAD.dir.name
        (hold,) = self.held(
            self.sorted_out(
                (self.DEAD, self.FIRST), started={dead: self.BEFORE, first: self.NOON}
            )
        )
        self.assertIn(f"the record of run {dead} does not read", hold.text)
        self.assertIn("written anew from memory settles nothing", hold.fix or "")
        without = self.sorted_out(
            (self.FIRST, self.DEAD), started={dead: self.AFTER, first: self.NOON}
        )
        self.assertEqual(self.held(without), [])
        self.assertEqual(len(without.later), 1)

    def test_the_twin_a_record_the_start_row_lists_as_a_probe_holds_nothing(self):
        """A start row says what a run started as: a probe or a preparation
        whose record does not read measured nothing, alone or beside a
        measurement that reads; without a start row the same record may
        have measured, and holds."""
        dead = self.DEAD.dir.name
        for kind in ("probe", "preparation"):
            with self.subTest(kind):
                measured = Measured(
                    AREA, PID, (self.DEAD,), (), (), (), started_as={dead: kind}
                )
                without = pure_call(measurements_without_record, measured, ())
                self.assertEqual(without, WithoutRecord((), (), (), ()))
                self.assertFalse(measured.has_measured)
        unlisted = Measured(AREA, PID, (self.DEAD,), (), (), ())
        self.assertTrue(unlisted.has_measured)
        self.assertEqual(
            len(pure_call(measurements_without_record, unlisted, ()).may_be_first), 1
        )

    def test_a_record_no_protocol_can_be_assigned_holds_none_and_is_warned_of(self):
        """Its protocol cannot be determined: no hold for any protocol, and
        a warning of a check not executable that names the run and the way
        back — never a silent pass."""
        dead = self.DEAD.dir.name
        without = self.sorted_out((self.FIRST,), unassigned=(dead,))
        self.assertEqual(without, WithoutRecord((), (), (), (dead,)))
        self.assertEqual(self.held(without), [])
        (warning,) = pure_call(lost_record_warnings, without)
        self.assertEqual((warning.grade, warning.outcome), (WARNING, NOT_EXECUTABLE))
        self.assertIn(f"the record of run {dead} does not read", warning.text)
        self.assertIn("which protocol it belongs to cannot be determined", warning.text)
        self.assertIn(UNASSIGNED_LEAVES_OPEN, warning.text)
        self.assertIn("nor that none came before", warning.text)
        self.assertIn("it is counted for no protocol", warning.text)
        self.assertIn("no hold follows from it", warning.text)
        self.assertIn("written anew from memory settles nothing", warning.fix or "")

    def test_the_twins_every_measurement_with_its_record_and_none_pass(self):
        from_git = run_dir(
            self.FIRST.dir.name, config=self.FIRST.config, from_commit="c0ffee"
        )
        for name, runs in (
            ("never measured", ()),
            ("a measurement that reads", (self.FIRST,)),
            ("a deleted run a commit holds", (from_git,)),
        ):
            with self.subTest(name):
                without = self.sorted_out(runs)
                self.assertEqual(without, WithoutRecord((), (), (), ()))
                self.assertEqual(self.held(without), [])
                self.assertEqual(pure_call(lost_record_warnings, without), [])


class ABindingTheFilesContradict(unittest.TestCase):
    """`binding_conflict_hold`: the start record, the run index and a run's
    own record name different protocols — which runs the protocol measured
    cannot be told, a BLOCKER of a check not executable; no file wins."""

    CLAUSE = (
        "run 2026-10-07T10-00-00_ab12: the start record names p-0123456789abcdef, "
        "the run index names p-fedcba9876543210"
    )

    def test_a_contradiction_blocks_with_every_way_out(self):
        (hold,) = pure_call(
            registration_hold.binding_conflict_hold, PID, AREA, (self.CLAUSE,), HANDOVER
        )
        self.assertEqual(
            (hold.grade, hold.rule, hold.outcome),
            (BLOCKER, TECHNICAL_RULE, NOT_EXECUTABLE),
        )
        self.assertIn(self.CLAUSE, hold.text)
        self.assertIn("no file is taken over another", hold.text)
        for way in ("never delete a row", "register anew", HANDOVER):
            self.assertIn(way, hold.fix or "")

    def test_the_twin_files_that_agree_hold_nothing(self):
        self.assertEqual(
            pure_call(registration_hold.binding_conflict_hold, PID, AREA, (), HANDOVER),
            [],
        )
