"""The measuring bar for the 1.0 line — today's mechanical contract at every
transition the migration replaces, pinned literally (TODO "Reihenfolge",
2026-10-21, phase 1).

The line: machine contracts structured, the explanation as prose, the
result rendered from bound sources. Phases 2–5 move what the gates read out
of the Markdown prose and into the TOML head, the run records and the
findings files. This file names what reads prose for a decision today, what
declares a result reported, which fields each lane owes and what
`--from-run` writes — so that every phase changes a line here on purpose
and nothing changes by accident. What a cold probe measures (the number,
its binding, misuse, cost) lives in `docs/usability/`; the flows are in
`tests/test_end_to_end.py`; this is the inventory between them.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.checks import prompt_check, run_record_check  # noqa: E402
from labkit.formats import protocol_block, protocol_check  # noqa: E402
from labkit.gates import finalize, report_check  # noqa: E402
from labkit.tools import protocol_fill  # noqa: E402
from protocol_fixture import head  # noqa: E402

RUN = "2026-10-21T10-00-00_abcd"


class ProseValueReaders(unittest.TestCase):
    """Every function that reads a value out of the protocol's prose and
    steers a decision with it — the inventory phases 3–5 shrink. A reader
    leaves this list when its question is answered from a typed source
    (`[result]`, `[model]`, `[gate]`, the run record, `audits/*.toml`), and
    the removal is a conscious edit here, never a side effect."""

    READERS = (
        (protocol_check, "fields"),  # the label parser every reader below rests on
        (protocol_check, "answer_field"),  # the Answer line: a generated section
        (protocol_check, "answer_without_run"),  # an Answer without a declaration
        (protocol_check, "model_named_in"),  # Model / tool decides the cut
        (
            protocol_check,
            "measure_runs",
        ),  # run ids in the Runs list make the result due
        (run_record_check, "arm_findings"),  # Arm lines held to the run
        (prompt_check, "prompt_blocks"),  # the Prompt block held to the constants
        (report_check, "limit_gaps"),  # Limit lines held to the record
    )
    #: left since phase 3 (2026-10-21): the declaration is `[result] run` in the
    #: head — `answering_run_field`, `answering_run_open`, `finalize.cited_runs`,
    #: `finalize.cited_run_gaps` read prose for it
    GONE = ("answering_run_field", "answering_run_open", "cited_runs", "cited_run_gaps")

    def test_the_inventory_is_exactly_these(self):
        for module, name in self.READERS:
            with self.subTest(reader=f"{module.__name__}.{name}"):
                self.assertTrue(callable(getattr(module, name)))
        self.assertEqual(len(self.READERS), 8)
        for name in self.GONE:
            self.assertFalse(hasattr(protocol_check, name) or hasattr(finalize, name))


class Declaration(unittest.TestCase):
    """What declares a result reported since phase 3: `[result] run` in the
    TOML head, written by `--from-run`. The four shapes it tells apart;
    the Answer line is a generated section and declares nothing by itself."""

    def protocol(self, answer: str, declared: str | None = None) -> str:
        return (
            head(cost="seconds", result=declared)
            + "\n## Result\n\n"
            + f"- **Answer to the question:** {answer}\n"
        )

    def test_no_table_declares_nothing(self):
        text = self.protocol("<per registered id its verdict, and the run_id…>")
        self.assertIsNone(protocol_block.declared_run(text))
        self.assertIsNone(protocol_check.answer_without_run(text))

    def test_the_table_declares_the_run_and_the_answer_is_held_to_it(self):
        text = self.protocol(f"c1_pass = True (run {RUN})", declared=RUN)
        self.assertEqual(protocol_block.declared_run(text), RUN)
        self.assertIsNone(protocol_check.answer_without_run(text))
        self.assertIsNone(finalize.declared_run_mismatch(text, Path("runs") / RUN))

    def test_a_typed_id_does_not_read_and_a_shaped_one_must_be_a_run(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            typed = self.protocol("c1_pass = True").replace(
                'preflight_audit = ""\n',
                'preflight_audit = ""\n\n[result]\nrun = "2026-10-21T12-48-00_final"\n',
            )
            with self.assertRaisesRegex(
                protocol_block.BlockError, "no run id runlog writes"
            ):
                protocol_block.declared_run(typed)
            (gap,) = finalize.declared_run_gaps(area, typed)
            self.assertIn("no run id runlog writes", gap)
            shaped = self.protocol(f"c1_pass = True (run {RUN})", declared=RUN)
            (gap,) = finalize.declared_run_gaps(area, shaped)
            self.assertIn(f"no runs/{RUN}/", gap)

    def test_an_answer_without_a_declaration_is_a_warning_not_a_declaration(self):
        text = self.protocol("c1_pass = True, see the run")
        self.assertIsNone(protocol_block.declared_run(text))
        warning = protocol_check.answer_without_run(text)
        assert warning is not None
        self.assertTrue(warning.startswith("WARNING"))


class LaneDuties(unittest.TestCase):
    """Which prose fields each lane owes today, as `protocol_check.owed`
    answers from the head and the Model / tool line. The lists are the
    standard's decision (LAB-003, LAB-004, LAB-017), not the format's:
    phase 5 may change how a field is recognised, not whether it is owed —
    a change to a list here is a change of the standard."""

    SECONDS = [
        "Terms of this protocol",
        "Question / hypothesis",
        "Data / scope",
        "Exclusions / filters",
        "Unit",
    ]
    SECONDS_MODEL = [
        "Terms of this protocol",
        "Question / hypothesis",
        "Success / failure criterion",
        "Admissibility condition",
        "Data / scope",
        "Data profile",
        "Model / tool",
        "Prompt",
        "Null condition / anchors",
        "Exclusions / filters",
        "Unit",
    ]
    FULL_MUST = [
        "Terms of this protocol",
        "Question / hypothesis",
        "Success / failure criterion",
        "Admissibility condition",
        "Data / scope",
        "Data profile",
        "Model / tool",
        "Model I/O",
        "Prompt",
        "Null condition / anchors",
        "Exclusions / filters",
        "Unit",
    ]
    FULL_SHOULD = [
        "Problem in one sentence",
        "Why this design",
        "Rival explanations",
        "Out of scope",
        "Gate labels",
        "Data preparation",
        "Meaning of the gold label",
        "Answer form + resolution",
        "How measured",
        "Validation",
        "Noise ceiling → threshold",
        "Free knobs",
        "Randomness controls",
        "Instrument check",
        "Yield per stage",
        "Resolution check",
        "Prediction for the follow-up run",
    ]
    REPORT = [
        "Question",
        "Did",
        "Outcome",
        "Rival check",
        "Caps/drops",
        "Analysis audit",
    ]

    @staticmethod
    def owed(text: str) -> tuple[list[str], list[str]]:
        must, should = protocol_check.owed(text, protocol_block.head(text))
        return [f.label for f in must], [f.label for f in should]

    def test_seconds_owes_the_cut_and_nothing_graduates(self):
        self.assertEqual(self.owed(head(cost="seconds")), (self.SECONDS, []))
        with_model = head(cost="seconds") + "- **Model / tool:** haiku\n"
        self.assertEqual(self.owed(with_model), (self.SECONDS_MODEL, []))
        no_model = (
            head(cost="seconds") + "- **Model / tool:** n/a — a count, no model\n"
        )
        self.assertEqual(self.owed(no_model), (self.SECONDS, []))

    def test_the_full_form_graduates_its_shoulds_at_the_freeze(self):
        self.assertEqual(
            self.owed(head(cost="minutes")), (self.FULL_MUST, self.FULL_SHOULD)
        )
        frozen = head(cost="minutes", frozen=True, preflight_audit="2026-10-21 · x")
        self.assertEqual(self.owed(frozen), (self.FULL_MUST + self.FULL_SHOULD, []))

    def test_a_documented_measure_run_makes_the_report_fields_due(self):
        frozen = head(cost="minutes", frozen=True, preflight_audit="2026-10-21 · x")
        with_run = frozen + f"\n## Runs\n\n- {RUN} — the run\n"
        self.assertEqual(
            self.owed(with_run), (self.FULL_MUST + self.FULL_SHOULD + self.REPORT, [])
        )
        prepared = frozen + f"\n## Runs\n\n- {RUN} — prepare: the data\n"
        self.assertEqual(protocol_check.measure_runs(prepared), [])


class WriteBack(unittest.TestCase):
    """What `--from-run` writes from the run and what stays the author's.
    Phase 3 renders the Answer and the Limit lines from the run and the
    record instead; the Result stays the author's two sentences throughout."""

    def test_from_run_writes_the_answer_and_the_author_writes_the_rest(self):
        self.assertEqual(protocol_fill.WRITTEN_BY_RUN, ("Answer to the question",))
        self.assertIn("Result", protocol_fill.WRITTEN_AFTER_RUN)
        self.assertIn("Raw output", protocol_fill.WRITTEN_AFTER_RUN)
        self.assertNotIn("Result", protocol_fill.WRITTEN_BY_RUN)


if __name__ == "__main__":
    unittest.main()
