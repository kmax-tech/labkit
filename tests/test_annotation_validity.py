"""Tests for what a computation over a model's outputs claims (`[model]
number_describes`, `annotation_validity`).

Why this exists: until the 0.22 rename a `compute` head with a `[model]`
table was refused — a model in the loop was taken to judge predictions. A
share of model labels judges none, but it may claim a property of the data
through the model as annotator ("30 % of the texts are causal"), and then
the annotator's suitability needs evidence (TODO, `compute` plan item 2).
labkit holds the claim and the evidence to each other and binds a protocol
reference; whether the evidence carries the annotation stays the audit's.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import (  # noqa: E402
    protocol_block,
    protocol_check,
    protocol_history,
    standard_contract,
)
from labkit.formats.gate import BLOCKER  # noqa: E402
from labkit.probes import usability  # noqa: E402
from labkit.tools import scaffold  # noqa: E402
from protocol_fixture import head  # noqa: E402

VALIDATION_ID = "p-1111111111111111"
RUN = "2026-10-23T10-00-00_ab12"
DOI = "10.18653/v1/2023.acl-long.1"


def _compute(claim: str) -> str:
    return head(cost="minutes", kind="compute", model="haiku", claim=claim)


def _gap(text: str) -> str | None:
    return protocol_check.kind_gap(text, protocol_block.head(text))


class Parse(unittest.TestCase):
    """The claim keys are exact keys with typed values: a typo is a loud
    error naming the field, never a silent absence."""

    def test_a_value_outside_the_two_is_refused(self):
        with self.assertRaisesRegex(protocol_block.BlockError, "model_outputs"):
            protocol_block.model(_compute('number_describes = "texts"'))

    def test_the_evidence_is_one_protocol_id_or_one_doi(self):
        for bad in (
            '{ protocol = "p-1", doi = "10.1000/x" }',
            '{ url = "https://x" }',
            '{ protocol = "p-123" }',
            '{ doi = "doi:10.1000/x" }',
            '"p-1111111111111111"',
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(protocol_block.BlockError):
                    protocol_block.model(
                        _compute(
                            'number_describes = "target_property"\n'
                            f"annotation_validity = {bad}"
                        )
                    )

    def test_a_stamped_placeholder_reads_as_unset_but_present(self):
        m = protocol_block.model(_compute(scaffold.COMPUTE_CLAIM))
        assert m is not None
        self.assertIsNone(m.number_describes)
        self.assertEqual(m.claim_keys, frozenset({"number_describes"}))

    def test_both_forms_of_evidence_parse(self):
        for raw, want in (
            (f'{{ protocol = "{VALIDATION_ID}" }}', ("protocol", VALIDATION_ID)),
            (f'{{ doi = "{DOI}" }}', ("doi", DOI)),
        ):
            m = protocol_block.model(
                _compute(
                    f'number_describes = "target_property"\nannotation_validity = {raw}'
                )
            )
            assert m is not None and m.annotation_validity is not None
            self.assertEqual(
                (m.annotation_validity.key, m.annotation_validity.value), want
            )


class KindGap(unittest.TestCase):
    """The claim and the evidence held to each other and to the kind."""

    def test_a_computation_with_a_model_says_what_its_number_describes(self):
        for claim in ("", scaffold.COMPUTE_CLAIM):
            with self.subTest(claim=claim):
                gap = _gap(_compute(claim))
                assert gap is not None
                self.assertIn("number_describes", gap)
                self.assertIn("model_outputs", gap)
                self.assertIn("target_property", gap)

    def test_the_model_outputs_owe_no_evidence(self):
        self.assertIsNone(_gap(_compute('number_describes = "model_outputs"')))

    def test_evidence_with_model_outputs_claims_more_than_the_number(self):
        gap = _gap(
            _compute(
                'number_describes = "model_outputs"\n'
                f'annotation_validity = {{ doi = "{DOI}" }}'
            )
        )
        assert gap is not None
        self.assertIn('"model_outputs"', gap)

    def test_a_property_of_the_data_owes_the_evidence(self):
        gap = _gap(_compute('number_describes = "target_property"'))
        assert gap is not None
        self.assertIn("annotation_validity", gap)

    def test_a_property_of_the_data_with_evidence_holds(self):
        for raw in (f'{{ protocol = "{VALIDATION_ID}" }}', f'{{ doi = "{DOI}" }}'):
            with self.subTest(raw=raw):
                self.assertIsNone(
                    _gap(
                        _compute(
                            'number_describes = "target_property"\n'
                            f"annotation_validity = {raw}"
                        )
                    )
                )

    def test_a_fit_or_an_apply_carries_no_claim_keys(self):
        for kind, claim in (
            ("apply", 'number_describes = "model_outputs"'),
            ("fit", f'annotation_validity = {{ doi = "{DOI}" }}'),
        ):
            with self.subTest(kind=kind):
                gap = _gap(head(cost="minutes", kind=kind, model="haiku", claim=claim))
                assert gap is not None
                self.assertIn(f'kind = "{kind}"', gap)
        self.assertIsNone(_gap(head(cost="minutes", kind="apply", model="haiku")))

    def test_a_computation_with_a_model_owes_no_bar(self):
        """compute judges no prediction, with or without a model: the
        registration adds the data profile, never the criterion."""
        self.assertEqual(
            standard_contract.registration_fields("compute", True),
            ("Question / hypothesis", "Data profile"),
        )
        bar = [f for f in protocol_check.FIELDS if f.seconds == "sb"]
        self.assertTrue(bar)
        self.assertFalse(any(protocol_check.bar_owed(f, "compute") for f in bar))


class Binding(unittest.TestCase):
    """`{ protocol = … }` names one apply protocol of the repo with a
    declared result; a DOI is held to its form only."""

    def _bound(self, d: str, text: str) -> dict[str, list[Path]]:
        p = Path(d) / "PROTOCOL-validation.md"
        p.write_text(text, encoding="utf-8")
        return {VALIDATION_ID: [p]}

    def _findings(self, d: str, ids: dict[str, list[Path]], raw: str):
        path = Path(d) / "PROTOCOL-share.md"
        text = _compute(
            f'number_describes = "target_property"\nannotation_validity = {raw}'
        )
        path.write_text(text, encoding="utf-8")
        return protocol_history.check_annotation_validity(path, text, ids)

    def test_an_apply_with_a_declared_result_binds(self):
        with tempfile.TemporaryDirectory() as d:
            ids = self._bound(
                d, head(id=VALIDATION_ID, kind="apply", model="haiku", result=RUN)
            )
            found = self._findings(d, ids, f'{{ protocol = "{VALIDATION_ID}" }}')
        self.assertEqual(found, [])

    def test_a_computation_is_no_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            ids = self._bound(d, head(id=VALIDATION_ID, kind="compute", result=RUN))
            found = self._findings(d, ids, f'{{ protocol = "{VALIDATION_ID}" }}')
        self.assertEqual([f.grade for f in found], [BLOCKER])
        self.assertIn('kind = "compute"', found[0].text)

    def test_an_apply_without_its_number_is_no_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            ids = self._bound(d, head(id=VALIDATION_ID, kind="apply", model="haiku"))
            found = self._findings(d, ids, f'{{ protocol = "{VALIDATION_ID}" }}')
        self.assertEqual([f.grade for f in found], [BLOCKER])
        self.assertIn("declares no result", found[0].text)

    def test_an_id_of_no_protocol_here_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            found = self._findings(d, {}, f'{{ protocol = "{VALIDATION_ID}" }}')
        self.assertEqual([f.grade for f in found], [BLOCKER])
        self.assertIn("no protocol of this repo", found[0].text)

    def test_a_doi_is_bound_to_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self._findings(d, {}, f'{{ doi = "{DOI}" }}'), [])

    def test_the_repo_index_resolves_the_reference(self):
        """Through `repo_protocol_ids`, the one index of the repo's ids."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            self._bound(
                d, head(id=VALIDATION_ID, kind="apply", model="haiku", result=RUN)
            )
            share = Path(d) / "PROTOCOL-share.md"
            share.write_text(
                _compute(
                    'number_describes = "target_property"\n'
                    f'annotation_validity = {{ protocol = "{VALIDATION_ID}" }}'
                ),
                encoding="utf-8",
            )
            ids = protocol_history.repo_protocol_ids(share)
            self.assertIn(VALIDATION_ID, ids)
            found = protocol_history.check_annotation_validity(
                share, share.read_text(encoding="utf-8"), ids
            )
        self.assertEqual(found, [])


class Stamp(unittest.TestCase):
    """`labkit-init exp --kind compute --model` stamps the claim keys
    instead of refusing; the usability staging no longer rewrites it."""

    def test_a_computation_with_a_model_is_stamped_with_its_claim(self):
        tmpl = scaffold.template(scaffold.PROTOCOL_TEMPLATE.name)
        with tempfile.TemporaryDirectory() as d:
            text = scaffold.stamped_head(tmpl, Path(d), "x", "seconds", "compute", True)
        self.assertEqual(scaffold.asked_kind("compute"), "compute")
        self.assertIn(scaffold.COMPUTE_CLAIM, text)
        scaffold.check_stamped_head(text, "seconds", "compute", True)

    def test_an_apply_is_stamped_without_it(self):
        tmpl = scaffold.template(scaffold.PROTOCOL_TEMPLATE.name)
        with tempfile.TemporaryDirectory() as d:
            text = scaffold.stamped_head(tmpl, Path(d), "x", "seconds", "apply", True)
        m = protocol_block.model(text)
        assert m is not None
        self.assertEqual(m.claim_keys, frozenset())

    def test_the_staging_keeps_the_computation(self):
        self.assertEqual(
            usability.stamp_flags("count", None, True), ("seconds", "compute", True)
        )


if __name__ == "__main__":
    unittest.main()
