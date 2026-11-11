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
from labkit.formats.gate import BLOCKER, OPEN_RULE
from labkit.formats.protocol_history import STANDS_AS_REGISTERED, scope_differences
from labkit.formats.standard_contract import ANALYSIS_AUDIT
from labkit.gates import registration_hold
from labkit.gates.audit_prompt import Followup, carried_of
from labkit.gates.registration_hold import (
    CORRECTION_ROUTE,
    DESCRIPTION_ADDED,
    FirstMeasurement,
    description_added,
    now_hold,
    seen_hold,
    split_released,
    waiting_refs,
)
from state_fixture import AREA, area_evidence, audit_record

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


class TheHoldAsTheRunSawIt(unittest.TestCase):
    """`seen_hold`: a change the answering run measured under."""

    def test_a_decided_correction_leads_with_the_follow_up_on_this_run(self):
        f = pure_call(seen_hold, PID, "r2", FIRST, SCOPE, [REF], ANALYSIS)
        self.assertEqual((f.grade, f.rule, f.step), (BLOCKER, OPEN_RULE, FIRST.step))
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
        f = pure_call(seen_hold, PID, "r2", FIRST, QUESTION, [None], ANALYSIS)
        assert f.fix is not None
        self.assertTrue(f.fix.startswith("restore Question / hypothesis"), f.fix)
        self.assertNotIn("the follow-up analysis audit on", f.fix)
        self.assertIn(f"Question / hypothesis {STANDS_AS_REGISTERED}", f.fix)
        self.assertIn("register anew", f.fix)
        # a correctable field held without a decided correction: the route named
        f = pure_call(seen_hold, PID, "r2", FIRST, SCOPE, [None], ANALYSIS)
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
        seen = pure_call(seen_hold, PID, "r2", FIRST, diffs, refs, ANALYSIS)
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
