"""The decisions on a finding that a later one replaced: which are kept,
how they read, and what a commit holds of them (`decision_history`)."""

from __future__ import annotations

import tomllib
import unittest
from dataclasses import dataclass

from labkit.formats import decision_history
from labkit.formats.decision_history import ReplacedDecision

FIXED = ReplacedDecision("fixed", "seed set", "", "2026-11-24T14:02")
TAKEN_BACK = ReplacedDecision("open", "set after the split", "", "2026-11-24T15:10")


@dataclass(frozen=True)
class Decided:
    """A finding as this module reads it."""

    status: str
    reason: str = ""
    effect: str = ""
    replaced_decisions: tuple[ReplacedDecision, ...] = ()

    @property
    def never_decided(self) -> bool:
        return (self.status, self.reason, self.effect) == ("open", "", "")


def row(**changed: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "status": "fixed",
        "reason": "seed set",
        "effect": "",
        "until": "2026-11-24T14:02",
    }
    entry.update(changed)
    return entry


class ReadEntries(unittest.TestCase):
    def test_an_absent_key_is_no_history(self):
        self.assertEqual(decision_history.read_entries(None), ())

    def test_entries_read_in_their_order(self):
        second = row(status="open", reason="set after the split")
        second["until"] = "2026-11-24T15:10"
        self.assertEqual(
            decision_history.read_entries([row(), second]), (FIXED, TAKEN_BACK)
        )

    def test_each_form_labkit_does_not_write_is_refused_by_name(self):
        without_until = row()
        del without_until["until"]
        for value, said in (
            ("fixed", "not an array of at least one entry"),
            ([], "not an array of at least one entry"),
            (["fixed"], "entry 1 is not a table of exactly"),
            ([row(), without_until], "entry 2 is not a table of exactly"),
            ([row(by="hand")], "entry 1 is not a table of exactly"),
            ([row(reason=3)], "entry 1: reason is not a string"),
            ([row(until="2026-11-24 14:02")], "entry 1: until .* is not a minute"),
            ([row(until="yesterday")], "entry 1: until .* is not a minute"),
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    decision_history.DecisionHistoryError, said
                ):
                    decision_history.read_entries(value)


class AfterReplacing(unittest.TestCase):
    def replacing(
        self, current: Decided, status: str, reason: str, effect: str
    ) -> tuple[ReplacedDecision, ...]:
        return decision_history.after_replacing(
            current, status, reason, effect, "2026-11-25T09:00"
        )

    def test_the_first_decision_replaces_none(self):
        self.assertEqual(self.replacing(Decided("open"), "fixed", "seed set", ""), ())

    def test_a_decision_taken_back_is_kept(self):
        self.assertEqual(
            self.replacing(Decided("fixed", "seed set"), "open", "does not hold", ""),
            (ReplacedDecision("fixed", "seed set", "", "2026-11-25T09:00"),),
        )

    def test_the_take_back_is_kept_when_the_finding_is_decided_again(self):
        taken_back = Decided("open", "does not hold", "", (FIXED,))
        self.assertEqual(
            self.replacing(taken_back, "limitation", "known", "stands"),
            (FIXED, ReplacedDecision("open", "does not hold", "", "2026-11-25T09:00")),
        )

    def test_a_corrected_reason_or_effect_is_another_decision(self):
        limit = Decided("limitation", "known", "stands")
        for new in (
            ("limitation", "known for 12 rows", "stands"),
            ("limitation", "known", "criterion-1 not assessable"),
        ):
            with self.subTest(new=new):
                self.assertEqual(
                    self.replacing(limit, *new),
                    (
                        ReplacedDecision(
                            "limitation", "known", "stands", "2026-11-25T09:00"
                        ),
                    ),
                )

    def test_the_same_decision_given_again_adds_nothing(self):
        decided = Decided("fixed", "seed set", "", (TAKEN_BACK,))
        self.assertEqual(
            self.replacing(decided, "fixed", "seed set", ""), (TAKEN_BACK,)
        )


class HistoryKept(unittest.TestCase):
    """What a later version must keep of the version a commit holds."""

    def kept(self, committed: Decided, now: Decided) -> bool:
        return decision_history.history_kept(committed, now)

    def test_an_unchanged_finding_keeps_it(self):
        for finding in (
            Decided("open"),
            Decided("fixed", "seed set"),
            Decided("open", "does not hold", "", (FIXED,)),
        ):
            with self.subTest(finding=finding):
                self.assertTrue(self.kept(finding, finding))

    def test_the_first_decision_owes_no_entry(self):
        self.assertTrue(self.kept(Decided("open"), Decided("fixed", "seed set")))
        # decided and replaced again before the next commit: no witness
        self.assertTrue(self.kept(Decided("open"), Decided("open", "no", "", (FIXED,))))

    def test_a_replaced_committed_decision_is_the_next_entry(self):
        committed = Decided("fixed", "seed set")
        self.assertTrue(
            self.kept(committed, Decided("open", "does not hold", "", (FIXED,)))
        )
        # restored before the next commit: the committed decision first, then the take-back
        self.assertTrue(
            self.kept(committed, Decided("fixed", "seed set", "", (FIXED, TAKEN_BACK)))
        )

    def test_a_replaced_committed_decision_that_is_not_kept_is_lost(self):
        committed = Decided("fixed", "seed set")
        for now in (
            Decided("open", "does not hold"),
            Decided("fixed", "another reason"),
            Decided("open", "does not hold", "", (TAKEN_BACK,)),
            Decided("open", "x", "", (ReplacedDecision("fixed", "seed", "", "t"),)),
        ):
            with self.subTest(now=now):
                self.assertFalse(self.kept(committed, now))

    def test_a_committed_entry_changed_removed_or_moved_is_lost(self):
        committed = Decided("open", "does not hold", "", (FIXED, TAKEN_BACK))
        edited = ReplacedDecision("fixed", "seed set in main", "", FIXED.until)
        for entries in ((), (FIXED,), (TAKEN_BACK, FIXED), (edited, TAKEN_BACK)):
            with self.subTest(entries=entries):
                now = Decided("open", "does not hold", "", entries)
                self.assertFalse(self.kept(committed, now))

    def test_entries_added_after_the_committed_ones_keep_it(self):
        committed = Decided("open", "does not hold", "", (FIXED,))
        added = ReplacedDecision("open", "does not hold", "", "2026-11-25T09:00")
        now = Decided("limitation", "known", "stands", (FIXED, added))
        self.assertTrue(self.kept(committed, now))


class ArrayLines(unittest.TestCase):
    def test_the_lines_read_back_as_the_entries(self):
        awkward = ReplacedDecision(
            "limitation", 'a "quoted" ] line\nand a second', "stands", FIXED.until
        )
        lines = decision_history.array_lines((FIXED, awkward))
        self.assertEqual(len(lines), 4)  # one line per entry between the brackets
        self.assertTrue(decision_history.ARRAY_OPENING.match(lines[0]))
        self.assertEqual(
            [bool(decision_history.ARRAY_CLOSING.match(line)) for line in lines],
            [False, False, False, True],
        )
        read = tomllib.loads("\n".join(lines))[decision_history.KEY]
        self.assertEqual(decision_history.read_entries(read), (FIXED, awkward))

    def test_no_history_adds_nothing_to_a_digest_and_each_entry_adds_its_values(self):
        self.assertEqual(decision_history.digest_fields(()), [])
        self.assertEqual(
            decision_history.digest_fields((FIXED, TAKEN_BACK)),
            [
                decision_history.KEY,
                *("fixed", "seed set", "", "2026-11-24T14:02"),
                *("open", "set after the split", "", "2026-11-24T15:10"),
            ],
        )

    def test_the_array_ends_after_its_closing_line_or_never(self):
        lines = [
            "x = 1\n",
            *(s + "\r\n" for s in decision_history.array_lines((FIXED,))),
        ]
        self.assertEqual(decision_history.array_end(lines, 1), 4)
        self.assertIsNone(decision_history.array_end(lines[:3], 1))


if __name__ == "__main__":
    unittest.main()
