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

from labkit.checks import prompt_check, result_render  # noqa: E402
from labkit.formats import protocol_block, protocol_check  # noqa: E402
from labkit.gates import finalize  # noqa: E402
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
        (
            protocol_check,
            "recorded_results_field",
        ),  # the Recorded results line: a generated section
        (
            protocol_check,
            "recorded_results_without_run",
        ),  # an Answer without a declaration
        (prompt_check, "prompt_blocks"),  # the Prompt block held to the constants
    )
    #: left since phase 3 (2026-10-21): the declaration is `[result] run` in the
    #: head — `answering_run_field`, `answering_run_open`, `finalize.cited_runs`,
    #: `finalize.cited_run_gaps` read prose for it
    #: left since phase 4: `[model]` decides the cut and carries the arms
    GONE = (
        "answering_run_field",
        "answering_run_open",
        "cited_runs",
        "cited_run_gaps",
        "model_named_in",
        "measure_runs",  # phase 5: the declaration makes the result due
    )
    #: the one reader of generated sections: exact equality with the rendering
    GENERATED = ((result_render, "render_gaps"),)

    def test_the_inventory_is_exactly_these(self):
        for module, name in self.READERS:
            with self.subTest(reader=f"{module.__name__}.{name}"):
                self.assertTrue(callable(getattr(module, name)))
        self.assertEqual(len(self.READERS), 4)
        for module, name in self.GENERATED:
            self.assertTrue(callable(getattr(module, name)))
        for name in self.GONE:
            self.assertFalse(hasattr(protocol_check, name) or hasattr(finalize, name))


class Declaration(unittest.TestCase):
    """What declares a result reported since phase 3: `[result] run` in the
    TOML head, written by `--from-run`. The four shapes it tells apart;
    the Recorded results line is a generated section and declares nothing by itself."""

    def protocol(self, answer: str, declared: str | None = None) -> str:
        return (
            head(repeat_cost="low", result=declared)
            + "\n## Result\n\n"
            + f"- **Recorded results:** {answer}\n"
        )

    def test_no_table_declares_nothing(self):
        text = self.protocol("<per registered id its verdict, and the run_id…>")
        self.assertIsNone(protocol_block.declared_run(text))
        self.assertIsNone(protocol_check.recorded_results_without_run(text))

    def test_the_table_declares_the_run_and_the_answer_is_held_to_it(self):
        text = self.protocol(f"C1 met · recorded: (run {RUN})", declared=RUN)
        self.assertEqual(protocol_block.declared_run(text), RUN)
        self.assertIsNone(protocol_check.recorded_results_without_run(text))
        self.assertIsNone(
            finalize.declared_run_mismatch(
                text, Path("runs") / RUN, Path("PROTOCOL-x.md")
            )
        )

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
            protocol = area / "PROTOCOL-x.md"
            (gap,) = finalize.declared_run_gaps(area, typed, protocol)
            self.assertIn("no run id runlog writes", gap.text)
            shaped = self.protocol(f"C1 met · recorded: (run {RUN})", declared=RUN)
            (gap,) = finalize.declared_run_gaps(area, shaped, protocol)
            self.assertIn(f"no runs/{RUN}/", gap.text)

    def test_an_answer_without_a_declaration_is_a_warning_not_a_declaration(self):
        text = self.protocol("c1_pass = True, see the run")
        self.assertIsNone(protocol_block.declared_run(text))
        warning = protocol_check.recorded_results_without_run(text)
        assert warning is not None
        self.assertTrue(warning.startswith("WARNING"))


class LaneDuties(unittest.TestCase):
    """Which prose fields each lane owes today, as `protocol_check.owed`
    answers from the head — its `[model]` table decides the cut. The lists are the
    standard's decision (LAB-003, LAB-004, LAB-017), not the format's:
    phase 5 may change how a field is recognised, not whether it is owed —
    a change to a list here is a change of the standard."""

    LOW = [
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

    def test_low_owes_the_cut_and_nothing_graduates(self):
        self.assertEqual(self.owed(head(repeat_cost="low")), (self.LOW, []))
        with_model = head(repeat_cost="low", model="haiku")
        self.assertEqual(self.owed(with_model), (self.SECONDS_MODEL, []))
        prose_only = head(repeat_cost="low") + "- **Model / tool:** haiku\n"
        self.assertEqual(self.owed(prose_only), (self.LOW, []))  # prose decides nothing

    def test_the_full_form_graduates_its_shoulds_at_the_freeze(self):
        self.assertEqual(
            self.owed(head(repeat_cost="high", kind="fit", model="haiku")),
            (self.FULL_MUST, self.FULL_SHOULD),
        )
        frozen = head(
            repeat_cost="high",
            kind="fit",
            model="haiku",
            frozen=True,
            preflight_audit="2026-10-21 · x",
        )
        self.assertEqual(self.owed(frozen), (self.FULL_MUST + self.FULL_SHOULD, []))

    def test_the_full_form_owes_model_and_criterion_fields_only_with_them(self):
        # a high computation without a model was asked for its data profile,
        # prompt, instrument and resolution checks (audit 2026-10-27, third,
        # I9); a fit without a model keeps its instrument and criterion fields
        def must(kind: str, model: str | None = None) -> list[str]:
            text = head(
                repeat_cost="high",
                kind=kind,
                model=model,
                frozen=True,
                preflight_audit="2026-10-21 · x",
            )
            return self.owed(text)[0]

        compute, fit, apply_model = must("compute"), must("fit"), must("apply", "haiku")
        for label in ("Data profile", "Prompt", "Model I/O", "Instrument check",
                      "Resolution check", "Noise ceiling → threshold"):  # fmt: skip
            with self.subTest(label=label):
                self.assertNotIn(label, compute)
                self.assertIn(label, apply_model)
        for label in ("Model I/O", "Instrument check", "Resolution check"):
            self.assertIn(label, fit)
        for label in ("Data profile", "Prompt"):
            self.assertNotIn(label, fit)

    def test_a_declared_result_makes_the_report_fields_due(self):
        """Since phase 5 the declaration makes the result due; a run id in the
        Runs list declares nothing (until 0.101.0 it did, minus "prepare")."""
        frozen = head(
            repeat_cost="high",
            kind="fit",
            model="haiku",
            frozen=True,
            preflight_audit="2026-10-21 · x",
        )
        declared = head(
            repeat_cost="high",
            kind="fit",
            model="haiku",
            frozen=True,
            preflight_audit="2026-10-21 · x",
            result=RUN,
        )
        self.assertEqual(
            self.owed(declared), (self.FULL_MUST + self.FULL_SHOULD + self.REPORT, [])
        )
        listed = frozen + f"\n## Runs\n\n- {RUN} — the run\n"
        self.assertEqual(self.owed(listed), (self.FULL_MUST + self.FULL_SHOULD, []))


class WriteBack(unittest.TestCase):
    """What `--from-run` writes from the run and what stays the author's.
    Phase 3 renders Recorded results and the Limit lines from the run and the
    record instead; the Result stays the author's two sentences throughout."""

    def test_from_run_writes_the_answer_and_the_author_writes_the_rest(self):
        self.assertEqual(protocol_fill.WRITTEN_BY_RUN, ("Recorded results",))
        self.assertIn("Conclusion", protocol_fill.WRITTEN_AFTER_RUN)
        self.assertIn("Raw output", protocol_fill.WRITTEN_AFTER_RUN)
        self.assertNotIn("Conclusion", protocol_fill.WRITTEN_BY_RUN)


if __name__ == "__main__":
    unittest.main()
