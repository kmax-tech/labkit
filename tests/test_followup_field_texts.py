"""The follow-up piece shows each field text once (`audit_prompt.
earlier_piece`): several corrections of one field name their texts by
number under `FIELD TEXTS`, each change to judge follows there once as a
word diff, and nothing is dropped — while a single correction with
distinct texts reads as it did, each value at its entry.

From changes in memory (`audit_prompt.FieldChange`); which texts a change
holds, from a repository: tests/test_registration_station.py. The records
of the verdict test are written to a temporary area, as `labkit-audit`
writes them.

    .venv/bin/python -m pytest tests/test_followup_field_texts.py
"""

from __future__ import annotations

import shutil
import tempfile
import time
import unittest
from pathlib import Path

from protocol_fixture import protocol_id_of, registration_of
from state_fixture import audit_record

from labkit.formats import findings, followup
from labkit.formats.protocol_history import ABSENT
from labkit.gates import audit_prompt
from labkit.gates.audit_reply import parse_fixes

LABEL = "Data / scope"
CORRECTION = (
    "WARNING · PROTOCOL-x.md:Data / scope · statement · Data / scope "
    "miscounts the generated scenarios · the denominator · LAB-050 Analysis "
    "audit before reporting · correct it"
)


def scope(variant: str) -> str:
    """A Data / scope paragraph of about 6.7 kB on one line, as a long
    area's field reads, its 41st sentence marked VARIANT."""
    text = " ".join(
        f"Item {i} of the generated scenarios is read from the cached set as written."
        for i in range(90)
    )
    return text.replace("Item 40 ", f"Item 40 ({variant}) ")


FIRST, AS_RUN, NOW = scope("first"), scope("as run"), scope("now")


def change(
    first: str = FIRST, as_run: str | None = AS_RUN, now: str = NOW
) -> audit_prompt.FieldChange:
    """A confirmatory correction of Data / scope: the first registration
    FIRST, the audited run's own text AS_RUN (None: no run audited), the
    field NOW."""
    return audit_prompt.FieldChange(
        LABEL,
        audit_prompt.ValueThen(first, "as its first measurement r0 at abc123"),
        None
        if as_run is None
        else audit_prompt.ValueThen(as_run, "as the run audited r9 at def456"),
        now,
        "",
        False,
    )


def followup_of(
    changes: list[audit_prompt.FieldChange], text: str = CORRECTION
) -> audit_prompt.Followup:
    """One decided correction per entry of CHANGES, each in a record of its
    own, with a finding text and a reason of about 5.5 kB together."""
    members, by_ref = [], {}
    for n, c in enumerate(changes, 1):
        f = findings.Finding(
            "WARNING", f"{text} {'x' * 2400}", "fixed", "corrected " + "y" * 3000
        )
        record = audit_record(f"r{n}.toml", mode="analysis", run_id="r9", found=[f])
        member = followup.Member(record, 1, f)
        members.append(member)
        by_ref[member.ref] = c
    return audit_prompt.Followup(members, None, {}, by_ref)


def piece(shown: audit_prompt.Followup) -> str:
    ((_, text),) = audit_prompt.earlier_piece(shown)
    return text


class SeveralCorrectionsOfOneField(unittest.TestCase):
    """Four corrections of one 6.7 kB field: over the operating limit with
    every value at its entry, under it with each text once."""

    def test_each_text_once_and_under_the_limit_that_held_it_before(self):
        shown = followup_of([change() for _ in range(4)])
        # each entry alone prints its distinct values at the entry: the
        # layout four entries had before, joined as the piece joins them
        alone = [piece(followup_of([c])) for c in shown.changes.values()]
        self.assertTrue(all(FIRST in a and NOW in a for a in alone))
        before = len("\n".join(alone).encode("utf-8"))
        self.assertGreater(before, audit_prompt.EARLIER_MAX_BYTES)
        text = piece(shown)
        entries, size = audit_prompt.followup_size(shown)
        self.assertEqual(size, len(text.encode("utf-8")))
        self.assertLess(size, audit_prompt.EARLIER_MAX_BYTES)
        self.assertEqual(entries, 4)
        for value in (FIRST, AS_RUN, NOW):
            self.assertEqual(text.count(value), 1)
        for e in shown.entries:
            self.assertEqual(text.count(f"{e.ref}\n"), 1)
            self.assertIn(e.finding.text, text)
            self.assertIn(e.finding.reason, text)

    def test_entries_name_their_texts_and_the_change_is_diffed_once(self):
        lines = piece(followup_of([change(), change()])).split("\n")
        refs = [ln for ln in lines if ln.startswith("  Data / scope ")]
        self.assertEqual(
            [ln.rsplit(": ", 1)[1] for ln in refs],
            [f"field text {n}, under FIELD TEXTS below" for n in (1, 2, 3)] * 2,
        )
        heads = [ln for ln in lines if ln.startswith("field text ")]
        self.assertEqual(
            [h.split(" · ")[:2] for h in heads],
            [[f"field text {n}", LABEL] for n in (1, 2, 3)],
        )
        self.assertIn(f"{len(FIRST.encode())} bytes:", heads[0])
        at = lines.index(heads[0])
        self.assertEqual(lines[at + 1], f"  {FIRST}")
        # confirmatory: the change to judge is from the first registration
        diffs = [ln for ln in lines if ln.startswith("change to judge, ")]
        self.assertEqual(
            diffs, ["change to judge, field text 1 → field text 3 (Data / scope):"]
        )
        diff = lines[lines.index(diffs[0]) + 1]
        self.assertIn("Item 40 [-(first)-] {+(now)+} of the", diff)
        self.assertTrue(diff.startswith("  … ") and diff.endswith(" …"), diff)

    def test_two_runs_audited_add_their_own_texts_and_no_second_copy(self):
        other = scope("as another run")
        text = piece(followup_of([change(), change(as_run=other)]))
        for value in (FIRST, AS_RUN, other, NOW):
            self.assertEqual(text.count(value), 1)
        self.assertIn("field text 3 · ", text)  # NOW, the third text printed
        self.assertIn("field text 4 · ", text)  # OTHER, printed after NOW

    def test_the_decisions_and_their_verdicts_stay_bound_to_the_records(self):
        """The layout touches neither what a verdict binds nor what
        `decisions_moved` compares: both read the records, not the text."""
        area = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, area)
        for minute in range(3):
            path = findings.write(
                area,
                "analysis",
                "opus",
                "0" * 12,
                "b" * 12,
                (0, 1, 0),
                [("WARNING", f"{CORRECTION} ({minute})")],
                registration=registration_of(area),
                protocol_id=protocol_id_of(area),
                run_id="r9",
                shown_sha="1" * 12,
                now=time.mktime((2026, 11, 24, 9, minute, 0, 0, 0, -1)),
            )
            findings.write_decision(path, 1, "fixed", "Data / scope now counts 12")
        members = followup.chain(findings.area_records(area)).members.values()
        entries = list(members)
        shown = audit_prompt.Followup(
            entries, None, {}, {e.ref: change() for e in entries}
        )
        self.assertIn(audit_prompt.FIELD_TEXTS, piece(shown))
        reply = "\n".join(
            f"FIX · {e.ref} · resolved · the text now counts what the run read"
            for e in entries
        )
        fixes = parse_fixes(f"{reply}\nverdict: 0 blockers, 0 warnings, 0 notes", shown)
        self.assertEqual(
            [(v.ref, v.decision_sha) for v in fixes],
            [(e.ref, findings.decision_digest(e.finding)) for e in entries],
        )
        self.assertEqual(audit_prompt.decisions_moved(entries, area), [])


class OneCorrection(unittest.TestCase):
    """The twin: a single correction whose texts differ prints each value
    at its entry, as before, and no `FIELD TEXTS`."""

    def test_distinct_texts_stand_at_the_entry(self):
        short = change("4 documents", "2 documents", "3 documents")
        text = piece(followup_of([short]))
        self.assertNotIn(audit_prompt.FIELD_TEXTS, text)
        self.assertEqual(
            audit_prompt.field_change_lines(short, {}),
            audit_prompt.field_change_lines(short),
        )
        lines = text.split("\n")
        self.assertIn(
            "  Data / scope as first registered (as its first measurement r0 at "
            "abc123): 4 documents",
            lines,
        )
        self.assertIn(
            "  Data / scope in the audited run's own text (as the run audited r9 "
            "at def456): 2 documents",
            lines,
        )
        self.assertIn("  Data / scope now: 3 documents", lines)

    def test_a_text_the_run_shares_with_the_first_registration_is_shown_once(self):
        """One correction whose run saw the first text: that text would be
        printed twice, so the piece numbers both texts and diffs the
        change to judge."""
        text = piece(followup_of([change(as_run=FIRST)]))
        self.assertEqual(text.count(FIRST), 1)
        self.assertEqual(text.count(NOW), 1)
        self.assertIn("as first registered (as its first measurement r0 at", text)
        self.assertEqual(text.count("): field text 1, under FIELD TEXTS below"), 2)
        self.assertIn("Data / scope now: field text 2, under FIELD TEXTS below", text)
        self.assertIn("change to judge, field text 1 → field text 2", text)

    def test_a_short_text_repeated_stays_at_each_entry(self):
        """The run saw the corrected text, so "3 documents" stands twice:
        too short to be worth a number, it is printed at the entry."""
        short = change("4 documents", "3 documents", "3 documents")
        text = piece(followup_of([short, short]))
        self.assertNotIn(audit_prompt.FIELD_TEXTS, text)
        self.assertEqual(text.count("Data / scope now: 3 documents"), 2)

    def test_a_text_without_the_field_stays_its_marker(self):
        """`ABSENT` marks a text that does not hold the field: it is no
        field text, so it is printed as the marker at every entry and
        numbers nothing, however often it stands."""
        absent = change(ABSENT, None, NOW)
        self.assertEqual(
            audit_prompt.field_text_numbers([absent, absent]), {(LABEL, NOW): 1}
        )
        self.assertIsNone(audit_prompt.judged_pair(absent))
        self.assertEqual(audit_prompt.field_text_numbers([change(ABSENT, ABSENT)]), {})


class TheChangeToJudge(unittest.TestCase):
    """`audit_prompt.judged_pair`: the two texts the `change to judge` line
    names, or None where there is nothing to diff."""

    def test_confirmatory_from_the_first_registration(self):
        self.assertEqual(audit_prompt.judged_pair(change()), (FIRST, NOW))

    def test_exploratory_from_the_audited_runs_own_text(self):
        exploring = change()._replace(compared_with_run_audited=True)
        self.assertEqual(audit_prompt.judged_pair(exploring), (AS_RUN, NOW))

    def test_none_without_a_benchmark_or_a_difference(self):
        untold = change()._replace(first_untold="run r1: its record names p-1")
        self.assertIsNone(audit_prompt.judged_pair(untold))
        self.assertIsNone(audit_prompt.judged_pair(change(now=FIRST)))
        unread = change()._replace(
            first_measured=audit_prompt.ValueThen(None, "no commit recorded")
        )
        self.assertIsNone(audit_prompt.judged_pair(unread))


class WordDiff(unittest.TestCase):
    """`audit_prompt.word_diff` with hand-checked lines."""

    def test_a_replaced_word_between_cut_context(self):
        old = " ".join(f"w{i}" for i in range(30))
        new = old.replace("w15", "W")
        self.assertEqual(
            audit_prompt.word_diff(old, new),
            "… w7 w8 w9 w10 w11 w12 w13 w14 [-w15-] {+W+} "
            "w16 w17 w18 w19 w20 w21 w22 w23 …",
        )

    def test_an_insertion_and_a_deletion_at_the_ends(self):
        self.assertEqual(audit_prompt.word_diff("a b c", "b c d"), "[-a-] b c {+d+}")

    def test_a_short_unchanged_run_between_changes_stays_whole(self):
        self.assertEqual(audit_prompt.word_diff("a x b", "a y b"), "a [-x-] {+y+} b")

    def test_whitespace_alone_is_named(self):
        self.assertEqual(
            audit_prompt.word_diff("a  b", "a b"),
            "the two texts differ in whitespace only",
        )


if __name__ == "__main__":
    unittest.main()
