"""Rule tests of `model_check`'s pure checks: each condition from typed data
in memory, its violation and its valid twin (docs/architecture.md, "Checks
and their tests"). The gate that composes them is finalize
(`tests/test_finalize_steps.py` for its stations).
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping

import pytest

from check_guards import pure_call
from labkit.checks.model_check import (
    StoringRun,
    call_log_model_findings,
    stand_in_findings,
)
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    LAB_027,
    WARNING,
)
from labkit.formats.runs import ModelCall

pytestmark = pytest.mark.rule


def _call(
    alias: str, *, hit: bool, origin_run: str | None = None, stand_in: bool = False
) -> ModelCall:
    """One line of a run's `llm-calls.jsonl` as the reader returns it."""
    return ModelCall(
        alias=alias, hit=hit, origin_run=origin_run, stand_in=stand_in, usage={}
    )


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
            f"outside any run, not marked as stand-ins), but its models_resolved "
            f"does not name `standin`",
            f.text,
        )
        self.assertIn("`model`", f.fix or "")

    def test_marked_stand_ins_are_counted_apart_from_other_stored_answers(self):
        calls = [
            _call("standin", hit=True, stand_in=True),
            _call("standin", hit=True, stand_in=True),
            _call("standin", hit=True),
            _call("standin", hit=False),
        ]
        (f,) = self._held(calls, {})
        self.assertIn(
            "holds 4 answers of alias `standin` (1 asked the model, 2 stand-ins, "
            "1 stored outside any run, not marked as a stand-in), but its "
            "models_resolved does not name "
            "`standin` — no record says which model the alias stood for",
            f.text,
        )

    def test_the_twin_stand_ins_whose_alias_the_record_names_pass(self):
        calls = [_call("standin", hit=True, stand_in=True)] * 2
        self.assertEqual(self._held(calls, self.NAMED), [])

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
        self.assertIn(
            "1 answer of alias `standin` stored outside any run, which", f.text
        )

    def test_a_derived_run_reading_stand_ins_blocks_naming_them(self):
        calls = [
            _call("standin", hit=True, stand_in=True),
            _call("standin", hit=True),
        ]
        (f,) = self._held(calls, {}, derived_from=self.PARENT)
        self.assertEqual(f.grade, BLOCKER)
        self.assertIn(
            "2 answers of alias `standin` stored outside any run (1 of them "
            "a stand-in)",
            f.text,
        )

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


class StandInsAreNamed(unittest.TestCase):
    """LAB-027 Model discipline: a run whose call log holds stand-ins —
    fixed answers `llm_cache.store_stand_in` stored, no model's — gets one
    warning naming them, guaranteed (`stand_in_findings`); an answer stored
    outside any run without the mark is not taken for one."""

    RUN = "2026-11-21T10-55-52_a997"

    def test_stand_ins_get_one_warning_naming_alias_and_count(self):
        calls = [
            _call("standin", hit=True, stand_in=True),
            _call("standin", hit=True, stand_in=True),
            _call("judge", hit=True, stand_in=True),
            _call("haiku", hit=False),
        ]
        (f,) = pure_call(stand_in_findings, self.RUN, calls, [])
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (WARNING, GUARANTEED, LAB_027)
        )
        self.assertIn(
            f"{self.RUN} read stand-in answers (1 logged use of alias `judge`, "
            f"2 logged uses of alias `standin`): fixed answers stored with "
            f"`llm_cache.store_stand_in`, not answers of a model",
            f.text,
        )
        self.assertNotIn("source runs", f.text)

    def test_stand_ins_of_source_runs_are_named_apart_from_its_own(self):
        """The runs it rests on (derived_from, continued rows, input
        origins) count as in the result label; the warning names their
        uses apart, so they do not read as calls of this run."""
        own = [_call("standin", hit=True, stand_in=True)]
        sources = [_call("standin", hit=True, stand_in=True)] * 2
        (f,) = pure_call(stand_in_findings, self.RUN, own, sources)
        self.assertIn(
            f"{self.RUN} read stand-in answers (1 logged use of alias `standin`); "
            f"the runs it rests on (derived_from, continued rows, input origins) "
            f"logged more (2 logged uses of alias `standin`) — uses those runs "
            f"logged, not calls of {self.RUN}: fixed answers stored with ",
            f.text,
        )
        (only,) = pure_call(stand_in_findings, self.RUN, [], sources)
        self.assertIn(
            f"{self.RUN} read no stand-in itself; the runs it rests on "
            f"(derived_from, continued rows, input origins) logged stand-in "
            f"answers (2 logged uses of alias `standin`) — uses those runs "
            f"logged, not calls of {self.RUN}: fixed answers",
            only.text,
        )

    def test_the_twin_model_answers_and_unmarked_stored_answers_get_none(self):
        calls = [
            _call("haiku", hit=False),
            _call("standin", hit=True),
            _call("haiku", hit=True, origin_run="2026-11-20T09-00-00_bb22"),
        ]
        self.assertEqual(pure_call(stand_in_findings, self.RUN, calls, calls), [])


if __name__ == "__main__":
    unittest.main()
