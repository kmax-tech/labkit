"""Rule tests of `run_record_check`'s pure checks: each condition from typed
data in memory, its violation and its valid twin (docs/architecture.md,
"Checks and their tests"). The gate that composes them is finalize
(`tests/test_finalize_steps.py` for its stations).
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from pathlib import Path

import pytest

from check_guards import pure_call
from labkit.checks.run_record_check import (
    LAB_027,
    StoringRun,
    call_log_model_findings,
    criterion_n_input_mismatches,
    criterion_ns,
    null_lane_findings,
    output_record_findings,
    SourceNow,
    source_finding,
)
from labkit.formats.gate import (
    BLOCKER,
    DEVIATION,
    GUARANTEED,
    KNOWN_RULE,
    NOT_EXECUTABLE,
    OPEN_RULE,
    TECHNICAL_RULE,
    cited_rule,
    STATIC_EVIDENCE,
    WARNING,
    RuleAssignment,
)
from labkit.formats.runs import (
    DataEntry,
    KeptRows,
    ModelCall,
    OutputEntry,
    OutputNow,
)

pytestmark = pytest.mark.rule

ITEMS = DataEntry("items", "data/items.jsonl", "ab", 12, None, False, ())
ROWS = OutputEntry(Path("out.jsonl"), "cd", 12)

LAB_017 = cited_rule("LAB-017 The number of audits follows the cost tier")


class ACriterionDenominatorIsAnInputCount(unittest.TestCase):
    """A `criterion_<i>_n` that matches no input count the run recorded is a
    warning, never a blocker (`criterion_n_input_mismatches`)."""

    def _held(self, metrics: dict[str, object], inputs=(ITEMS,), outputs=(ROWS,)):
        return pure_call(
            criterion_n_input_mismatches,
            pure_call(criterion_ns, metrics),
            list(inputs),
            list(outputs),
        )

    def test_a_shrunk_denominator_warns_naming_the_counts(self):
        # criterion_1_n = 7 against 12 recorded rows: the denominator shrank
        (f,) = self._held({"criterion_1_pass": True, "criterion_1_n": 7})
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (WARNING, STATIC_EVIDENCE, OPEN_RULE)
        )
        self.assertIn("criterion_1_n = 7", f.text)
        self.assertIn("data[items].rows = 12", f.text)
        self.assertIn("out.jsonl lines = 12", f.text)

    def test_a_denominator_without_any_recorded_count_warns(self):
        (f,) = self._held({"criterion_1_n": 12}, inputs=(), outputs=())
        self.assertIn(
            "criterion_1_n present, but the run recorded no input count", f.text
        )

    def test_the_twin_a_matching_denominator_passes(self):
        self.assertEqual(
            self._held({"criterion_1_pass": True, "criterion_1_n": 12}), []
        )

    def test_no_denominator_nothing_to_hold(self):
        self.assertEqual(self._held({"criterion_1_pass": True}), [])
        # an admissibility count is no criterion denominator
        self.assertEqual(self._held({"quality_check_1_n": 3}), [])

    def test_a_bool_is_no_count(self):
        self.assertEqual(pure_call(criterion_ns, {"criterion_1_n": True}), {})
        self.assertEqual(
            pure_call(criterion_ns, {"criterion_1_n": 12}), {"criterion_1_n": 12}
        )


def _lanes(null_pred) -> list[dict[str, object]]:
    """Two lanes over four items; the null lane's answer as given, gold kept."""
    gold = [0, 1, 0, 1]
    return [
        {"lane": "registered", "item": str(i), "pred": g, "gold": g}
        for i, g in enumerate(gold)
    ] + [
        {"lane": "null", "item": str(i), "pred": null_pred(g), "gold": g}
        for i, g in enumerate(gold)
    ]


class TheNullLaneMoved(unittest.TestCase):
    """LAB-034 Null condition in the same run: a kept output whose null lane
    answers what the registered lane answers on every item measures no noise
    floor — a warning, static evidence (`null_lane_findings`)."""

    AREA = Path("area")

    def _held(self, rows: list[dict[str, object]]):
        kept = [KeptRows(OutputEntry(Path("out/rows.jsonl"), None, len(rows)), rows)]
        return pure_call(null_lane_findings, kept, self.AREA)

    def test_an_unmoved_null_lane_warns(self):
        held = self._held(_lanes(lambda g: g))
        self.assertEqual(held.examined, 1)
        (f,) = held.unmoved
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule),
            (
                WARNING,
                STATIC_EVIDENCE,
                RuleAssignment(KNOWN_RULE, "LAB-034", "Null condition in the same run"),
            ),
        )
        self.assertTrue(
            f.text.startswith("rows.jsonl: the null lane's answer and gold equal")
        )
        self.assertIn("permuted gold", f.fix or "")

    def test_the_twin_a_moved_null_lane_passes(self):
        held = self._held(_lanes(lambda g: 0))
        self.assertEqual((held.examined, held.unmoved), (1, []))

    def test_an_output_without_both_lanes_is_not_examined(self):
        held = self._held([{"item": "1", "n": 3}])
        self.assertEqual((held.examined, held.unmoved), (0, []))


class AnOutputIsTheFileTheRunRecorded(unittest.TestCase):
    """A registered output whose file is gone, was never recorded, or holds
    other bytes than outputs.json records blocks (`output_record_findings`)."""

    AREA = Path("area")
    RECORDED = OutputEntry(Path("out/rows.jsonl"), "ab12", 4)

    def _held(
        self,
        now: str | None,
        recorded: str | None = "ab12",
        stands: bool | None = None,
    ):
        entry = OutputEntry(self.RECORDED.path, recorded, 4)
        if stands is None:
            stands = now is not None or recorded is None
        return pure_call(
            output_record_findings, [OutputNow(entry, stands, now)], "r1", self.AREA
        )

    def test_a_gone_an_unrecorded_and_a_changed_file_block(self):
        unrecorded = "outputs.json records no sha256 for it"
        # a comparison that cannot run is the technical contract and a check
        # not executable; only compared bytes that differ are a deviation
        cannot_compare = (TECHNICAL_RULE, NOT_EXECUTABLE)
        for now, recorded, stands, said, basis in (
            (None, "ab12", False, "the file is gone", cannot_compare),
            # nothing recorded to compare with: the file is not read, and
            # whether one stands at the path now does not change the cause
            (None, None, True, unrecorded, cannot_compare),
            (None, None, False, unrecorded, cannot_compare),
            (
                "cd34" + "0" * 60,
                "ab12",
                True,
                "its sha256 cd34 is not the recorded ab12",
                (OPEN_RULE, DEVIATION),
            ),
        ):
            with self.subTest(said=said, stands=stands):
                (f,) = self._held(now, recorded, stands)
                self.assertEqual((f.grade, f.evidence_kind), (BLOCKER, GUARANTEED))
                self.assertEqual((f.rule, f.outcome), basis)
                self.assertEqual(
                    f.text, f"out/rows.jsonl: not the file run r1 recorded — {said}"
                )
                self.assertIn("measure anew", f.fix or "")

    def test_only_a_gone_file_may_be_restored_and_only_to_the_recorded_bytes(self):
        """Restoring is a way out where nothing stands to be overwritten
        and a checksum holds the restored file; it is not told as a repair
        without loss."""
        (gone,) = self._held(None, "ab12", False)
        self.assertIn("restore the file", gone.fix or "")
        self.assertIn("sha256 ab12", gone.fix or "")
        self.assertIn("rows written to the file after the run", gone.fix or "")
        for now, recorded, stands in (
            (None, None, False),  # no checksum a restored file could be held to
            ("cd34" + "0" * 60, "ab12", True),  # a restore would overwrite it
        ):
            with self.subTest(recorded=recorded):
                (f,) = self._held(now, recorded, stands)
                self.assertNotIn("restore", f.fix or "")

    def test_why_no_sha256_was_recorded_is_the_records_note_not_the_checks_claim(self):
        """A missing sha256 alone does not show that the run ended without
        the file; where runlog noted it, the note is quoted."""
        entry = OutputEntry(
            self.RECORDED.path, None, None, "registered, but absent at end of run"
        )
        (f,) = pure_call(
            output_record_findings, [OutputNow(entry, False, None)], "r1", self.AREA
        )
        self.assertEqual(
            f.text,
            "out/rows.jsonl: not the file run r1 recorded — outputs.json records "
            'no sha256 for it; the record notes: "registered, but absent at end of run"',
        )

    def test_the_twin_the_recorded_bytes_pass(self):
        self.assertEqual(self._held("ab12" + "0" * 60), [])


class ASourceIsTheBytesTheRunRead(unittest.TestCase):
    """A run's source at low repeat cost: gone, neither tracked nor ignored,
    or other bytes than the record blocks; kept outside git by a rule or
    lying outside the repository is a note (`source_finding`, over the
    facts `source_now` reads)."""

    AREA = Path("area")
    SOURCE = Path("data/items.jsonl")
    SHA = "ab12"

    def _decided(self, **facts: object):
        now = SourceNow(self.SOURCE, self.SHA, **facts)  # type: ignore[arg-type] — the facts per case
        return pure_call(source_finding, now, self.AREA)

    def _blocker(self, rule: RuleAssignment, **facts: object):
        found, note = self._decided(**facts)
        assert found is not None
        self.assertIsNone(note)
        self.assertEqual(
            (found.grade, found.evidence_kind, found.rule),
            (BLOCKER, GUARANTEED, rule),
        )
        return found

    def test_a_gone_source_blocks(self):
        f = self._blocker(TECHNICAL_RULE, kind=None)
        self.assertIn("is not at its recorded path on this machine", f.text)
        self.assertIn("git checkout HEAD -- data/items.jsonl", f.fix or "")

    def test_an_untracked_file_blocks_though_its_bytes_match(self):
        f = self._blocker(LAB_017, kind="file", loose=(self.SOURCE,), untracked=True)
        self.assertIn("neither tracked in git nor ignored by a rule", f.text)
        self.assertIn("git add -- data/items.jsonl", f.fix or "")
        self.assertIn("sha256 ab12", f.fix or "")

    def test_an_untracked_directory_names_its_loose_files(self):
        loose = tuple(Path("data/d") / f"{n}.txt" for n in "abcd")
        f = self._blocker(LAB_017, kind="dir", loose=loose, untracked=True)
        self.assertIn("4 file(s) under it", f.text)
        self.assertIn(", …", f.text)
        self.assertIn(
            "git add -- data/d/a.txt data/d/b.txt data/d/c.txt data/d/d.txt",
            f.fix or "",
        )

    def test_other_bytes_block(self):
        f = self._blocker(
            LAB_017,
            kind="file",
            drift="its sha256 is now cd34",
        )
        self.assertIn("is not the bytes the run read: its sha256 is now cd34", f.text)

    def test_a_source_kept_out_by_a_rule_or_outside_the_repo_is_a_note(self):
        found, note = self._decided(
            kind="file", untracked=True, ignore_rules=(".gitignore:3:data/",)
        )
        self.assertIsNone(found)
        self.assertIn(
            "kept outside git by an ignore rule (.gitignore:3:data/)", note or ""
        )
        found, note = self._decided(kind="file", beyond=True)
        self.assertIsNone(found)
        self.assertIn("lies outside the repository", note or "")

    def test_the_twin_a_tracked_source_with_its_bytes_passes(self):
        self.assertEqual(self._decided(kind="file"), (None, None))


def _call(alias: str, *, hit: bool, origin_run: str | None = None) -> ModelCall:
    """One line of a run's `llm-calls.jsonl` as the reader returns it."""
    return ModelCall(alias=alias, hit=hit, origin_run=origin_run, usage={})


class TheCallLogAgreesWithTheModelRecords(unittest.TestCase):
    """LAB-027 Model discipline: every line of a run's call log has a record
    naming its alias — the run's own, or for an answer a run stored, that
    run's; else a blocker, guaranteed (`call_log_model_findings`). A
    derived run, whose record runlog never fills, gets a warning instead."""

    RUN = "2026-11-21T10-55-52_a997"
    PARENT = "2026-11-20T09-00-00_bb22"
    NAMED: Mapping[str, object] = {"standin": {"backend": "openai"}}

    def _held(
        self,
        calls: list[ModelCall],
        models_resolved: Mapping[str, object],
        *,
        derived_from: str | None = None,
        storing_runs: dict[str, StoringRun] | None = None,
    ):
        return pure_call(
            call_log_model_findings,
            self.RUN,
            calls,
            models_resolved,
            derived_from=derived_from,
            storing_runs=storing_runs or {},
        )

    def _stored(self, n: int = 1) -> list[ModelCall]:
        return [_call("standin", hit=True, origin_run=self.PARENT)] * n

    # -- a fresh run (also a repeat, also an exploratory step: neither
    # -- carries derived_from, and runlog records their models) ------------

    def test_stand_in_answers_stored_outside_a_run_block_without_the_alias(self):
        # the a997 case: two replayed stand-in answers, models_resolved empty
        calls = [_call("standin", hit=True), _call("standin", hit=True)]
        (f,) = self._held(calls, {})
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (BLOCKER, GUARANTEED, LAB_027)
        )
        self.assertIn(
            f"{self.RUN}'s call log holds 2 answers of alias `standin` (2 stored "
            f"outside any run), but its models_resolved does not name `standin`",
            f.text,
        )
        self.assertIn("`model`", f.fix or "")

    def test_a_call_that_asked_the_model_blocks_without_the_alias(self):
        # a repeat asks anew: its lines are all of this kind
        (f,) = self._held([_call("haiku", hit=False)], {})
        self.assertIn("holds 1 answer of alias `haiku` (1 asked the model)", f.text)

    def test_another_alias_named_does_not_cover_the_one_that_answered(self):
        calls = [_call("haiku", hit=False), _call("judge", hit=False)]
        (f,) = self._held(calls, {"haiku": {"backend": "claude-cli"}})
        self.assertIn("alias `judge`", f.text)

    def test_the_twin_a_named_alias_passes(self):
        calls = [_call("standin", hit=True), _call("standin", hit=False)]
        self.assertEqual(self._held(calls, self.NAMED), [])

    def test_the_twin_a_run_without_calls_passes(self):
        self.assertEqual(self._held([], {}), [])

    # -- an answer a run stored ---------------------------------------------

    def test_an_answer_whose_storing_run_names_the_alias_passes(self):
        stored = {self.PARENT: StoringRun(self.NAMED, None)}
        self.assertEqual(self._held(self._stored(2), {}, storing_runs=stored), [])

    def test_an_answer_whose_storing_run_does_not_name_the_alias_blocks(self):
        stored = {self.PARENT: StoringRun({"haiku": {}}, None)}
        (f,) = self._held(self._stored(2), {}, storing_runs=stored)
        self.assertEqual((f.grade, f.rule), (BLOCKER, LAB_027))
        self.assertIn(
            f"holds 2 answers of alias `standin` stored by run {self.PARENT}, but "
            f"the models_resolved of run {self.PARENT} names `haiku`, not `standin`",
            f.text,
        )

    def test_an_answer_whose_storing_run_cannot_be_read_blocks(self):
        gone = f"no run {self.PARENT} is in this area or another area of the lab"
        stored = {self.PARENT: StoringRun(None, gone)}
        (f,) = self._held(self._stored(), {}, storing_runs=stored)
        self.assertIn(f"stored by run {self.PARENT}, but {gone}", f.text)
        self.assertIn(f"restore the record of run {self.PARENT}", f.fix or "")

    def test_the_run_s_own_record_vouches_for_a_stored_answer_too(self):
        stored = {self.PARENT: StoringRun(None, "gone")}
        self.assertEqual(
            self._held(self._stored(), self.NAMED, storing_runs=stored), []
        )

    def test_an_origin_run_without_its_record_given_is_the_caller_s_error(self):
        with self.assertRaisesRegex(ValueError, "no record given for origin run"):
            self._held(self._stored(), {})

    # -- a derived run: no record of its own, and no model calls ----------

    def test_a_derived_run_asking_the_model_blocks(self):
        (f,) = self._held([_call("standin", hit=False)], {}, derived_from=self.PARENT)
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (BLOCKER, GUARANTEED, LAB_027)
        )
        self.assertIn(
            f"{self.RUN} is a derived run (derived_from {self.PARENT}), and a "
            f"derived run re-reads its parent's rows and makes no model calls — "
            f"yet its call log holds 1 call of alias `standin` that asked the model",
            f.text,
        )
        self.assertIn("fresh run", f.fix or "")

    def test_a_derived_run_reading_answers_stored_outside_any_run_blocks(self):
        (f,) = self._held([_call("standin", hit=True)], {}, derived_from=self.PARENT)
        self.assertEqual(f.grade, BLOCKER)
        self.assertIn("1 answer of alias `standin` stored outside any run", f.text)

    def test_a_derived_run_replaying_its_parent_s_named_answers_passes(self):
        stored = {self.PARENT: StoringRun(self.NAMED, None)}
        self.assertEqual(
            self._held(
                self._stored(2), {}, derived_from=self.PARENT, storing_runs=stored
            ),
            [],
        )

    def test_a_derived_run_replaying_answers_no_record_names_blocks(self):
        stored = {self.PARENT: StoringRun({}, None)}
        (f,) = self._held(
            self._stored(), {}, derived_from=self.PARENT, storing_runs=stored
        )
        self.assertEqual(f.grade, BLOCKER)
        self.assertNotIn("`model`", f.fix or "", "a derived run cannot name it")


if __name__ == "__main__":
    unittest.main()
